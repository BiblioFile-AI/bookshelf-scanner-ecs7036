import json
import re
import time
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from sklearn.preprocessing import StandardScaler

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
OPEN_LIBRARY_URL = "https://openlibrary.org/search.json"

# The six volumeInfo fields our pipeline uses downstream
FIELDS = ["title", "authors", "categories", "averageRating", "pageCount", "publishedDate"]
FALLBACK_FIELDS = ["pageCount", "categories", "publishedDate"]

#API KEY HANDLING
def load_api_key(path="../api_key.txt"):
    """Read the Google Books API key from a local file kept out of git.
    
    Returns the key as a string, or None if the file is missing or still
    contains the placeholder. The volumes endpoint also works without a key,
    just with a lower anonymous quota, so None is not fatal.
    """
    key_file = Path(path)
    if not key_file.exists():
        print("No api_key.txt found - continuing without a key (lower quota).")
        return None
    key = key_file.read_text().strip()
    if not key or key.startswith("PASTE_"):
        print("api_key.txt still has the placeholder - continuing without a key.")
        return None
    return key

API_KEY = load_api_key()

#RESPONSE CACHE LAYER
CACHE_PATH = Path("../data/api_cache.json")
NOT_FOUND = "__NOT_FOUND__"  # marker for a confirmed catalogue miss

def load_cache(path=CACHE_PATH):
    """Load the response cache from disk, or start an empty one.
    
    One entry per (source, title, author): the raw record the source
    returned, or the NOT_FOUND marker when the source confirmed it has
    no such book. The JSON file survives kernel restarts, so a popular
    book is only ever fetched once - which saves quota and time, and
    makes reruns reproducible (live API results can differ between
    calls; cached ones cannot).
    """
    if path.exists():
        try:
            return json.loads(path.read_text())
        except ValueError:
            print("[CACHE] api_cache.json unreadable - starting fresh")
    return {"google": {}, "openlibrary": {}}

def save_cache(cache, path=CACHE_PATH):
    """Write the cache to disk (called after every new entry)."""
    path.write_text(json.dumps(cache))

def cache_key(title, author):
    """One key per book request: title and author, case-folded."""
    return f"{title.strip().lower()}|{author.strip().lower()}"

def cache_get(source, title, author):
    """Return the cached record, NOT_FOUND, or None if never fetched."""
    return API_CACHE[source].get(cache_key(title, author))

def cache_put(source, title, author, record):
    """Store a confirmed answer (a record or NOT_FOUND) and persist it.
    
    Errors, timeouts and quota replies are deliberately never cached:
    they are transient, and caching one would freeze a temporary
    failure into a permanent wrong answer.
    """
    API_CACHE[source][cache_key(title, author)] = record
    save_cache(API_CACHE)

API_CACHE = load_cache()
print(f"Cache loaded: {len(API_CACHE['google'])} Google Books entries, "
      f"{len(API_CACHE['openlibrary'])} Open Library entries")

#MATCHING & FETCHING LOGIC
def pick_best_match(items, query_title):
    """Choose the most suitable edition from a list of API results.
    
    Google Books ranks results by the caller's locale, so from a Swiss IP
    the first hit is often a German translation (langRestrict does not
    reliably prevent this). Instead we fetch several results and score
    each one: +4 if the edition is in English, +2 if its title matches
    the query exactly, +1 if it has a page count. The highest-scoring
    item wins; ties go to Google's original ranking.
    """
    def score(item):
        vi = item.get("volumeInfo", {})
        s = 0
        if vi.get("language") == "en":
            s += 4
        if vi.get("title", "").strip().lower() == query_title.strip().lower():
            s += 2
        if vi.get("pageCount", 0) > 0:
            s += 1
        return s
    return max(items, key=score)

def fetch_google_books(title, author, api_key=None, pause=0.5, retries=2):
    """Look one book up on the Google Books volumes endpoint.

    Checks the response cache first: a cached record (or a cached
    confirmed miss) is returned immediately, with no pause and no
    network call. Only confirmed answers are written to the cache;
    errors and quota replies are not.

    Parameters
    ----------
    title : str
        Book title as guessed by the vision step.
    author : str
        Author name as guessed by the vision step.
    api_key : str or None
        Google Books API key. If None the request is sent anonymously.
    pause : float
        Seconds to sleep before each network request, to stay under
        the free-tier rate limit (~15 requests per minute).
    retries : int
        How many extra attempts to make on transient server errors
        (HTTP 5xx), waiting 2 seconds between attempts.

    Returns
    -------
    dict or None
        The volumeInfo record of the best-matching result (see
        pick_best_match), or None when the book was not found, the
        request failed, or the quota was hit. Each failure prints a
        clear message so we can see it in the run log.
    """
    cached = cache_get("google", title, author)
    if cached == NOT_FOUND:
        print(f"[CACHE] '{title}' is a known Google Books miss - no request sent")
        return None
    if cached is not None:
        return cached # cache hit: no pause, no network call

    params = {
        "q": f'intitle:"{title}" inauthor:"{author}"',
        "maxResults": 10, # fetch several editions, pick_best_match chooses
    }
    if api_key:
        params["key"] = api_key

    for attempt in range(retries + 1):
        time.sleep(pause) # rate-limit courtesy pause
        
        try:
            response = requests.get(GOOGLE_BOOKS_URL, params=params, timeout=10)
        except requests.exceptions.RequestException as err:
            print(f"[ERROR] Request failed for '{title}' by {author}: {err}")
            return None

        if response.status_code >= 500: # transient server error -> retry
            if attempt < retries:
                print(f"[RETRY] HTTP {response.status_code} for '{title}' - trying again...")
                time.sleep(2)
                continue
            print(f"[ERROR] HTTP {response.status_code} for '{title}' by {author} (gave up)")
            return None

        if response.status_code == 429 or (response.status_code == 403 and "quota" in response.text.lower()):
            print(f"[QUOTA] Rate limit or daily quota reached at '{title}' - stop and retry later.")
            return None
        if response.status_code != 200:
            print(f"[ERROR] HTTP {response.status_code} for '{title}' by {author}")
            return None

        data = response.json()
        if data.get("totalItems", 0) == 0 or "items" not in data:
            print(f"[NOT FOUND] Google Books has no match for '{title}' by {author}")
            cache_put("google", title, author, NOT_FOUND)
            return None

        best = pick_best_match(data["items"], title)["volumeInfo"]
        cache_put("google", title, author, best)
        return best

def parse_volume_info(volume_info):
    """Reduce a raw volumeInfo record to the six fields the pipeline uses.
    
    Missing fields become None, so blanks are visible in the table
    (the missing-data policy in build task 3 deals with them).
    A pageCount of 0 also becomes None, because Google Books uses 0
    to mean 'unknown page count'. 'authors' and 'categories' arrive
    as lists and are joined with '; ' so each fits in one DataFrame cell.
    """
    row = {}
    for field in FIELDS:
        value = volume_info.get(field)
        if field == "pageCount" and value == 0:
            value = None # Google Books uses 0 for 'unknown page count'
        if isinstance(value, list):
            value = "; ".join(str(v) for v in value)
        row[field] = value
    return row

def build_metadata_table(books, api_key=None):
    """Fetch metadata for a list of (title, author) pairs.
    
    Returns a DataFrame with one row per book: the original query columns
    plus the six Google Books fields, plus a 'found' flag. Books that were
    not found keep their row (all fields None) so the coverage count in
    phase 3 stays honest.
    """
    rows = []
    for title, author in books:
        volume_info = fetch_google_books(title, author, api_key=api_key)
        row = {"query_title": title, "query_author": author, "found": volume_info is not None}
        row.update(parse_volume_info(volume_info) if volume_info else {f: None for f in FIELDS})
        rows.append(row)
    return pd.DataFrame(rows)

#OPEN LIBRARY FALLBACK

# The Open Library fields we request, and (below) how they map onto our names
OL_FIELDS = "title,author_name,subject,number_of_pages_median,first_publish_year"

def pick_best_ol_doc(docs, query_title, query_author):
    """Choose the most suitable record from Open Library search results.
    
    Open Library's first hit is not always the right book (searching
    'The Alchemist' returns a graphic novel first). Score each result:
    +4 if the author's surname appears in the record's author list,
    +2 if the title matches the query exactly, +1 if a page count is
    present. Highest score wins; ties keep Open Library's own ranking.
    """
    def score(doc):
        s = 0
        authors = " ".join(doc.get("author_name", [])).lower()
        if query_author.split()[-1].lower() in authors:
            s += 4
        if doc.get("title", "").strip().lower() == query_title.strip().lower():
            s += 2
        if doc.get("number_of_pages_median"):
            s += 1
        return s
    return max(docs, key=score)

def fetch_open_library(title, author, pause=1.0, retries=2):
    """Look one book up on the Open Library search endpoint.
    
    Same contract as fetch_google_books, including the cache check
    first: a cached record or confirmed miss returns immediately with
    no pause and no network call, and only confirmed answers are ever
    cached. Open Library is a donation-funded service and asks
    automated users to be gentle, hence the full one-second pause
    before real requests. It is also slower and flakier than Google:
    read timeouts and, when throttling, HTML replies instead of JSON
    both happen in practice, so both are treated as transient errors
    and retried.
    """
    cached = cache_get("openlibrary", title, author)
    if cached == NOT_FOUND:
        print(f"[CACHE] '{title}' is a known Open Library miss - no request sent")
        return None
    if cached is not None:
        return cached # cache hit: no pause, no network call

    params = {"title": title, "author": author, "fields": OL_FIELDS, "limit": 10}
    for attempt in range(retries + 1):
        time.sleep(pause) # be polite to a free service
        try:
            response = requests.get(OPEN_LIBRARY_URL, params=params, timeout=20)
        except requests.exceptions.RequestException as err:
            if attempt < retries: # timeouts are usually transient here
                time.sleep(2)
                continue
            print(f"[OL ERROR] Request failed for '{title}' by {author}: {err}")
            return None

        if response.status_code >= 500 or response.status_code == 429:
            if attempt < retries:
                print(f"[OL RETRY] HTTP {response.status_code} for '{title}' - trying again...")
                time.sleep(2)
                continue
            print(f"[OL ERROR] HTTP {response.status_code} for '{title}' by {author} (gave up)")
            return None
        if response.status_code != 200:
            print(f"[OL ERROR] HTTP {response.status_code} for '{title}' by {author}")
            return None

        try:
            docs = response.json().get("docs", [])
        except ValueError: # throttling can return HTML instead of JSON
            if attempt < retries:
                time.sleep(2)
                continue
            print(f"[OL ERROR] Non-JSON reply for '{title}' by {author} (gave up)")
            return None

        if not docs:
            print(f"[OL NOT FOUND] Open Library has no match for '{title}' by {author}")
            cache_put("openlibrary", title, author, NOT_FOUND) # confirmed miss
            return None

        best = pick_best_ol_doc(docs, title, author)
        cache_put("openlibrary", title, author, best)
        return best

def parse_ol_doc(doc):
    """Translate an Open Library record into our Google Books field names.
    
    pageCount comes from number_of_pages_median (the median page count
    across all editions Open Library knows - a sensible single number),
    publishedDate from first_publish_year (the original publication year,
    not the year of some later reprint). Subject tags can run to dozens,
    so we keep the first three. There is no averageRating key: Open
    Library has no ratings, and the field is display-only anyway.
    """
    subjects = doc.get("subject") or []
    return {
        "title": doc.get("title"),
        "authors": "; ".join(doc.get("author_name", [])) or None,
        "categories": "; ".join(subjects[:3]) or None,
        "pageCount": doc.get("number_of_pages_median"),
        "publishedDate": doc.get("first_publish_year"),
    }

def apply_fallback(df):
    """Fill the holes Google Books left, using Open Library.
    
    Trigger rule: a book qualifies when Google found nothing at all, or
    when pageCount, categories or publishedDate is blank. Books whose
    Google record is complete are skipped, so we never double the
    request count for no reason.

    Tie-break rule: Google Books wins. Only blank fields are filled;
    existing values are never overwritten.

    Returns a copy of the DataFrame with the blanks filled where
    possible, plus a 'source' column ('google', 'google+openlibrary'
    or 'openlibrary') so every value's origin stays traceable. Prints
    one line per fallback call so the run log shows what happened.
    """
    df = df.copy()
    df["source"] = df["found"].map({True: "google", False: None})
    for idx, row in df.iterrows():
        blanks = [f for f in FALLBACK_FIELDS if pd.isna(row[f])]
        if row["found"] and not blanks:
            continue # Google delivered everything - no request wasted

        doc = fetch_open_library(row["query_title"], row["query_author"])
        if doc is None:
            continue # both sources failed; build task 3 decides what happens

        ol_record = parse_ol_doc(doc)
        # A book Google missed entirely takes every field Open Library has;
        # otherwise only the blanks may be filled (tie-break rule).
        targets = FIELDS if not row["found"] else blanks
        filled = []
        for field in targets:
            if ol_record.get(field) is not None and pd.isna(row[field]):
                df.at[idx, field] = ol_record[field]
                filled.append(field)
        if filled:
            df.at[idx, "source"] = "google+openlibrary" if row["found"] else "openlibrary"
            df.at[idx, "found"] = True
            print(f"[FALLBACK] '{row['query_title']}': filled {', '.join(filled)} from Open Library")
        else:
            print(f"[FALLBACK] '{row['query_title']}': Open Library had nothing new to add")

    return df

#MISSING DATA
def extract_year(published_date):
    """Pull a four-digit year out of whatever the sources sent.
    
    Google Books delivers strings like '2014-07-15' or '2007', Open
    Library a plain integer year. The feature vector needs one number,
    so everything is reduced to an int - or None when no year is there.
    """
    if pd.isna(published_date):
        return None
    match = re.search(r"\d{4}", str(published_date))
    return int(match.group()) if match else None

def apply_missing_data_policy(df):
    """Apply the three written missing-data rules, in order.
    
     Rule 1 - drop unmatched books. A book neither source could confirm
        is removed and counted; the drop count measures how often the
        vision step hallucinated a title (a group evaluation metric).
    Rule 2 - impute missing numerics with the median. A blank pageCount
        or year is filled with the median of the books we do have (the
        median resists outliers where the mean does not). Every fill is
        flagged in a *_imputed column so nothing happens silently.
    Rule 3 - never impute averageRating. Present for only a third of
        books, so it passes through untouched: displayed where it
        exists, excluded from the feature vector.

    Returns
    -------
    (pandas.DataFrame, int)
        The cleaned table, and the number of dropped books for the
        Results and Discussion section.
    """
    df = df.copy()

    # Rule 1: drop and count the books no source could confirm
    dropped = int((~df["found"]).sum())
    df = df[df["found"]].copy()

    # publishedDate arrives in mixed formats; the vector needs a number
    df["year"] = df["publishedDate"].map(extract_year)

    # Rule 2: median imputation, flagged so every fill stays visible
    for col in ["pageCount", "year"]:
        median_value = df[col].median()
        df[f"{col}_imputed"] = df[col].isna()
        df[col] = df[col].fillna(median_value)
        print(f"{col}: median = {median_value:.0f}, "
              f"imputed {int(df[f'{col}_imputed'].sum())} value(s)")

    # Rule 3: averageRating passes through untouched
    print(f"Dropped books (no source could confirm them): {dropped}")

    return df, dropped

#FEATURE VECTOR
# The ten genre labels, exact spelling confirmed with Katy. The list
# position of each label is its index 0-9, and that index order must
# match Alexa's similarity matrix below - do not reorder either side.
GENRE_LABELS = [
    "Romance",                          # 0
    "Mystery, Thriller & Crime",        # 1
    "Science Fiction & Fantasy",        # 2
    "Children",                         # 3
    "Young Adult",                      # 4
    "Biography & Memoir",               # 5
    "History & Politics",               # 6
    "Science, Tech & Nature",           # 7
    "Self-Help & Lifestyle",            # 8
    "General & Contemporary Fiction",   # 9
]

GENRE_TO_INDEX = {label: i for i, label in enumerate(GENRE_LABELS)}

def _build_similarity_matrix():
    """Alexa's genre similarity matrix (agreed group code, do not edit).

    10x10, symmetric: 1.0 on the diagonal (same genre), 0.1 default for
    unrelated pairs, hand-set values for genres that share readers.
    Her ranker uses it to score the genre part of the distance between
    two books via their genre indices.
    """
    # Start with 0.1 for every pair (the "unrelated" default).
    matrix = np.full((10, 10), 0.1)
    # Same genre is perfectly similar.
    np.fill_diagonal(matrix, 1.0)

    # Override specific pairs that have a defined relationship.
    # Each tuple is (genre_index_A, genre_index_B, similarity_score).
    # The matrix is symmetric so we set both [i][j] and [j][i].
    explicit_pairs = [
        (0, 9, 0.6),   # Romance <-> General Fiction
        (0, 4, 0.5),   # Romance <-> Young Adult
        (0, 8, 0.2),   # Romance <-> Self Help
        (1, 6, 0.4),   # Mystery/Thriller <-> History
        (1, 9, 0.4),   # Mystery/Thriller <-> General Fiction
        (1, 2, 0.3),   # Mystery/Thriller <-> SciFi/Fantasy
        (1, 5, 0.2),   # Mystery/Thriller <-> Biography
        (2, 4, 0.6),   # SciFi/Fantasy <-> Young Adult
        (2, 3, 0.4),   # SciFi/Fantasy <-> Children
        (2, 7, 0.4),   # SciFi/Fantasy <-> SciTech
        (3, 4, 0.5),   # Children <-> Young Adult
        (4, 9, 0.5),   # Young Adult <-> General Fiction
        (5, 6, 0.7),   # Biography <-> History
        (5, 7, 0.4),   # Biography <-> SciTech
        (5, 8, 0.3),   # Biography <-> Self Help
        (6, 7, 0.4),   # History <-> SciTech
        (6, 9, 0.3),   # History <-> General Fiction
        (7, 8, 0.3),   # SciTech <-> Self Help
        (8, 9, 0.2),   # Self Help <-> General Fiction
    ]

    for i, j, sim in explicit_pairs:
        matrix[i][j] = sim
        matrix[j][i] = sim

    return matrix

GENRE_SIMILARITY = _build_similarity_matrix()

def genre_to_index(label):
    """Translate Katy's genre label into its matrix index (0-9).

    The spelling must match GENRE_LABELS exactly - that is the agreed
    interface between her classifier and this step. An unknown label
    falls back to General & Contemporary Fiction (index 9) with a loud
    warning, so one upstream typo cannot crash the whole ranking.
    """

    if label in GENRE_TO_INDEX:
        return GENRE_TO_INDEX[label]
    print(f"[WARNING] Unknown genre label {label!r} - "
          f"falling back to 'General & Contemporary Fiction'")
    return GENRE_TO_INDEX["General & Contemporary Fiction"]

# The exact vector layout agreed with Alexa. Genre travels as its matrix
# index (her ranker looks pairs up in GENRE_SIMILARITY); the two numeric
# features are z-scores from a scaler fitted once on the profile.

VECTOR_COLUMNS = ["genre_index", "known_author", "pageCount_z", "year_z"]

def fit_profile_scaler(profile_df):
    """Fit the StandardScaler once, on the user's profile books only.

    z = (x - mean) / standard deviation, per column, for pageCount and
    year. Fitting on the profile and reusing that same scaler for every
    shelf book keeps all vectors on one common scale; refitting per
    shelf upload would move the goalposts between photos.
    """
    return StandardScaler().fit(profile_df[["pageCount", "year"]])

def is_known_author(book_authors, profile_authors):
    """Return 1.0 if any profile author appears in the book's author
    string, else 0.0 (case-insensitive full-name match)."""
    haystack = str(book_authors).lower()
    return float(any(a.lower() in haystack for a in profile_authors))

def build_feature_vectors(df, genre_labels, profile_authors, scaler):
    """Turn each book row into the four-number vector for Alexa's ranker.

    Parameters
    ----------
    df : pandas.DataFrame
        Clean metadata table (after the missing-data policy, so pageCount
        and year are guaranteed present).
    genre_labels : iterable of str
        One genre label per row, from Katy's classifier, in the agreed
        spelling.
    profile_authors : list of str
        Authors of the books in the user's saved profile.
    scaler : fitted StandardScaler
        From fit_profile_scaler - fitted on the profile, never on the shelf.

    Returns
    -------
    pandas.DataFrame
        One row per book, columns in VECTOR_COLUMNS order, indexed like
        df, ready for .to_numpy().
    """
    
    z_scores = scaler.transform(df[["pageCount", "year"]])
    vectors = pd.DataFrame({
        "genre_index": [genre_to_index(g) for g in genre_labels],
        "known_author": [is_known_author(a, profile_authors) for a in df["authors"]],
        "pageCount_z": z_scores[:, 0],
        "year_z": z_scores[:, 1],
    }, index=df.index)
    return vectors[VECTOR_COLUMNS]

def build_user_profile(liked_books, api_key=None):
    """Build a user's taste profile from their liked books.

    Parameters
    ----------
    liked_books : list of (title, author, genre_label) triples
        The books the user says they enjoyed - ten at onboarding,
        more as they save books. The genre label comes from Katy's
        classifier and must use the agreed spelling.
    api_key : str or None
        Google Books API key, passed through to the metadata pipeline.

    Returns
    -------
    dict with the profile's four parts:
        "books"    - the liked list itself (source of truth for rebuilds),
        "metadata" - the cleaned metadata table, one row per confirmed book,
        "scaler"   - StandardScaler fitted on THESE books' pages and years,
        "authors"  - the profile authors (drives the known_author flag),
        "vectors"  - one feature vector per book, VECTOR_COLUMNS order:
                     this is the pile of vectors Alexa's ranker consumes.

    A liked book that neither source can confirm is dropped with a
    warning: a profile entry without metadata could never be a vector.
    """
    lookups = [(title, author) for title, author, _ in liked_books]
    meta = apply_fallback(build_metadata_table(lookups, api_key=api_key))
    meta["genre"] = [genre for _, _, genre in liked_books]  # rows keep list order
    meta, dropped = apply_missing_data_policy(meta)
    if dropped:
        print(f"[PROFILE] {dropped} liked book(s) could not be confirmed - left out")

    scaler = fit_profile_scaler(meta)
    authors = list(meta["authors"])
    vectors = build_feature_vectors(meta, meta["genre"], authors, scaler)
    return {"books": list(liked_books), "metadata": meta,
            "scaler": scaler, "authors": authors, "vectors": vectors}


def add_book_to_profile(profile, title, author, genre_label, api_key=None):
    """Add one saved book and return the rebuilt profile.

    Rebuilding from the book list (rather than appending a vector) is
    deliberate: the scaler is fitted on the profile, so a new book shifts
    the profile's mean and spread, and every existing vector must be
    recomputed on the new scale. Thanks to the response cache the rebuild
    is cheap - only the newly added book causes a network request.
    """
    return build_user_profile(profile["books"] + [(title, author, genre_label)],
                              api_key=api_key)