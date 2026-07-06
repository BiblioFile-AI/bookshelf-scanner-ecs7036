"""
knn.py - KNN-based book recommender for the bookshelf scanner app.

Accepts pre-computed 4-dimensional feature vectors produced by
metadata_lookup.build_feature_vectors():

    [genre_index, known_author, pageCount_z, year_z]

The approach:
  1. Receive pre-computed vectors from the pipeline.
  2. Use K=3 nearest neighbours with a custom weighted distance function.
  3. Return the scanned books list with 'rank' and 'is_top_pick' added.
"""

import numpy as np
from sklearn.neighbors import NearestNeighbors


# ---------------------------------------------------------------------------
# Section 1: Genre taxonomy
#
# Kept here as a readable reference — index 0-9 maps to these labels.
# The pipeline (metadata_lookup.py) owns genre-to-index conversion;
# this file only consumes the index numbers that arrive in the vectors.
# The index order MUST match metadata_lookup.GENRE_LABELS exactly.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Section 2: Genre similarity matrix
#
# A 10x10 symmetric table. Entry [i][j] = how similar genre i is to genre j.
# Same genre = 1.0. Unrelated = 0.1. Distance = 1 - similarity.
# Index order must stay in sync with GENRE_LABELS above.
# ---------------------------------------------------------------------------

def _build_similarity_matrix():
    # Every pair starts unrelated; the diagonal and explicit pairs override this.
    matrix = np.full((10, 10), 0.1)
    np.fill_diagonal(matrix, 1.0)

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


# ---------------------------------------------------------------------------
# Section 3: Custom distance function
#
# Vector layout (matches metadata_lookup.VECTOR_COLUMNS):
#   v[0]  genre_index   : integer 0-9, looked up in GENRE_SIMILARITY
#   v[1]  known_author  : 1.0 if author is in saved profile, else 0.0
#   v[2]  pageCount_z   : z-score relative to profile mean/std
#   v[3]  year_z        : z-score relative to profile mean/std
#
# Weights: genre 60%, known_author 20%, page 10%, year 10%.
#
# Z-scores are unbounded, so abs(z1-z2) can exceed 1 and would inflate
# the 10% weight components. tanh squashes any positive value into (0,1):
#   tanh(0.5) ~ 0.46  (half a std dev apart)
#   tanh(1.0) ~ 0.76  (one std dev apart)
#   tanh(2.0) ~ 0.96  (two std devs apart, near max penalty)
# This keeps the weights meaningful regardless of scale.
# ---------------------------------------------------------------------------

def custom_distance(v1, v2):
    """
    Weighted distance between two 4-dimensional book feature vectors.
    Called by sklearn's NearestNeighbors for every pair of vectors.
    """
    # Genre: read index directly from position 0 and look up similarity.
    # round() guards against any floating-point drift from sklearn internals.
    g1 = int(round(v1[0]))
    g2 = int(round(v2[0]))
    genre_dist = 1.0 - GENRE_SIMILARITY[g1][g2]

    # Known author: already binary (0 or 1), difference is naturally in [0, 1].
    author_dist = abs(v1[1] - v2[1])

    # Z-scores: tanh maps the absolute difference to (0, 1).
    page_dist = np.tanh(abs(v1[2] - v2[2]))
    year_dist = np.tanh(abs(v1[3] - v2[3]))

    return 0.6 * genre_dist + 0.2 * author_dist + 0.1 * page_dist + 0.1 * year_dist


# ---------------------------------------------------------------------------
# Section 4: Main ranking function
# ---------------------------------------------------------------------------

def rank_books(saved_vectors, scanned_vectors, scanned_books):
    """
    Rank scanned_books by similarity to the user's saved profile.

    Algorithm
    ---------
    1. Fit a KNN model (K=3) on saved_vectors.
    2. For each scanned book find its 3 nearest saved-book neighbours and
       average their distances -> one score per scanned book.
    3. Sort by score (lowest = most similar -> rank 1).

    Parameters
    ----------
    saved_vectors   : np.ndarray, shape (n_saved, 4)
        Pre-computed feature vectors for the user's profile books.
        Produced by metadata_lookup.build_feature_vectors().
    scanned_vectors : np.ndarray, shape (n_scanned, 4)
        Pre-computed feature vectors for the scanned shelf books.
    scanned_books   : list of dict
        Original book dicts from the pipeline. Two fields are added and
        the originals are not mutated.

    Returns
    -------
    list of dict — scanned_books with two new fields on each entry:
        rank        : int, 1 = best match for this user's taste
        is_top_pick : bool, True only for rank 1
    """
    if not scanned_books:
        return []

    # No profile to compare against — return books in original order.
    if saved_vectors is None or len(saved_vectors) == 0:
        results = []
        for i, book in enumerate(scanned_books):
            entry = dict(book)
            entry["rank"] = i + 1
            entry["is_top_pick"] = (i == 0)
            results.append(entry)
        return results

    k = min(3, len(saved_vectors))

    # brute-force is required when using a callable metric.
    knn = NearestNeighbors(n_neighbors=k, metric=custom_distance, algorithm="brute")
    knn.fit(saved_vectors)

    # distances shape: (n_scanned, k)
    distances, _ = knn.kneighbors(scanned_vectors)

    # Average distance to the k nearest saved books.
    avg_distances = distances.mean(axis=1)

    # argsort: lowest distance first = best match = rank 1.
    ranked_order = np.argsort(avg_distances)

    results = [dict(book) for book in scanned_books]
    for rank, idx in enumerate(ranked_order, start=1):
        results[idx]["rank"] = rank
        results[idx]["is_top_pick"] = (rank == 1)

    return results


# ---------------------------------------------------------------------------
# Section 5: Test data and demo run
#
# Run directly to verify the ranker:  python knn.py
#
# Vectors are hand-constructed to match the format metadata_lookup.py
# produces: [genre_index, known_author, pageCount_z, year_z].
#
# Profile: a SciFi/Mystery reader (Andy Weir, Stieg Larsson, Gillian Flynn).
# Z-scores computed from that profile's statistics:
#   pageCount: mean=483 pages, std=160
#   year:      mean=2005,      std=20
#
# Expected ranking: SciFi books first, especially Artemis (Andy Weir is a
# known author). Mystery next. Unrelated genres at the bottom.
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    # Shorthand genre indices for readability in the test vectors below.
    SCIFI   = 2   # Science Fiction & Fantasy
    MYSTERY = 1   # Mystery, Thriller & Crime
    YA      = 4   # Young Adult
    BIO     = 5   # Biography & Memoir
    GENERAL = 9   # General & Contemporary Fiction

    # Profile stats used to compute z-scores manually:
    MEAN_PAGES, STD_PAGES = 483, 160
    MEAN_YEAR,  STD_YEAR  = 2005, 20

    def pz(pages): return (pages - MEAN_PAGES) / STD_PAGES
    def yz(year):  return (year  - MEAN_YEAR)  / STD_YEAR

    # --- Saved profile: [genre_index, known_author, pageCount_z, year_z] ---
    # known_author is 1 for all saved books (they define the known-author set).

    saved_vectors = np.array([
        [SCIFI,   1, pz(369), yz(2011)],   # The Martian
        [MYSTERY, 1, pz(422), yz(2012)],   # Gone Girl
        [SCIFI,   1, pz(688), yz(1965)],   # Dune
        [MYSTERY, 1, pz(672), yz(2005)],   # The Girl with the Dragon Tattoo
        [SCIFI,   1, pz(476), yz(2021)],   # Project Hail Mary
        [GENERAL, 1, pz(273), yz(2018)],   # Normal People
    ], dtype=float)

    # --- Scanned shelf: known_author=1 only for Artemis (Andy Weir) ---

    scanned_vectors = np.array([
        [SCIFI,   1, pz(305), yz(2017)],   # Artemis          SciFi + known author
        [SCIFI,   0, pz(382), yz(2014)],   # Red Rising       SciFi, new author
        [MYSTERY, 0, pz(460), yz(2014)],   # Big Little Lies  Mystery
        [YA,      0, pz(374), yz(2008)],   # The Hunger Games YA (SciFi sim=0.6)
        [BIO,     0, pz(334), yz(2018)],   # Educated         Biography
        [GENERAL, 0, pz(449), yz(1938)],   # Rebecca          General Fiction, old
    ], dtype=float)

    scanned_books = [
        {"title": "Artemis",          "categories": "Science Fiction & Fantasy"},
        {"title": "Red Rising",       "categories": "Science Fiction & Fantasy"},
        {"title": "Big Little Lies",  "categories": "Mystery, Thriller & Crime"},
        {"title": "The Hunger Games", "categories": "Young Adult"},
        {"title": "Educated",         "categories": "Biography & Memoir"},
        {"title": "Rebecca",          "categories": "General & Contemporary Fiction"},
    ]

    ranked = rank_books(saved_vectors, scanned_vectors, scanned_books)
    ranked_sorted = sorted(ranked, key=lambda b: b["rank"])

    print("=" * 72)
    print("  BOOKSHELF RECOMMENDER - KNN RESULTS")
    print("=" * 72)
    print(f"\n  Scanned shelf ({len(scanned_books)} books) ranked by fit:\n")
    print(f"  {'Rank':<6}{'Title':<38}{'Genre':<36}{'Top Pick'}")
    print(f"  {'-'*4:<6}{'-'*36:<38}{'-'*34:<36}{'-'*8}")

    for book in ranked_sorted:
        top = "** YES **" if book["is_top_pick"] else ""
        print(
            f"  {book['rank']:<6}"
            f"{book['title']:<38}"
            f"{book['categories']:<36}"
            f"{top}"
        )

    print()
