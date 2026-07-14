import os
import re
import tempfile
import uuid
from flask import Flask, request, jsonify


# important functions from Katies and Emmas code 
import knn
import main_pipeline
import metadata_lookup
import shelf_reader
from storage import load_profile, save_profile, normalize_book

app = Flask(__name__)


# CORS — lets the browser fetch from http://localhost:5000 regardless of
# what origin the frontend HTML is served from (file://, live-server, etc.)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/scan",    methods=["OPTIONS"])
@app.route("/save",    methods=["OPTIONS"])
@app.route("/onboard", methods=["OPTIONS"])
def handle_preflight():
    return jsonify({}), 200


# Response serialiser
# The pipeline stores books in Google Books field names; script.js expects
# different keys. This function translates one book dict before sending it.

def _to_frontend(book):
    pub_date = book.get("publishedDate") or ""
    year_match = re.search(r"\d{4}", str(pub_date))
    return {
        "title":       book.get("title"),
        "author":      book.get("authors"),          # authors     -> author
        "genre":       book.get("genre_label") or book.get("categories"),  # AI-classified genre, falls back to raw category text
        "year":        int(year_match.group()) if year_match else None,
        "pages":       book.get("pageCount"),        # pageCount   -> pages
        "rank":        book.get("rank"),
        "is_top_pick": book.get("is_top_pick", False),
    }



# Profile vector builder
# main_pipeline.prep_recommendation_data returns only scanned book vectors.
# This helper runs the same metadata + genre + scaler steps for the saved
# profile books so KNN has something to compare against.
# API calls are cached, so if the pipeline already fetched a book this run
# the second call hits the cache and costs nothing.

def _build_profile_vectors(profile_books):
    profile_tuples = [
        (b.get("title") or b.get("query_title", ""),
         b.get("authors") or b.get("query_author", ""))
        for b in profile_books
    ]
    raw_df     = metadata_lookup.build_metadata_table(profile_tuples, api_keys=metadata_lookup.API_KEYS)
    full_df    = metadata_lookup.apply_fallback(raw_df)
    profile_df, _ = metadata_lookup.apply_missing_data_policy(full_df)

    if profile_df.empty:
        return None

    books_for_genre = [
        {"title": row["query_title"], "authors": row.get("query_author", "")}
        for _, row in profile_df.iterrows()
    ]
    genre_results = shelf_reader.classify_books_batch(books_for_genre)
    genre_labels = [
        genre_results.get(
            f"{row['query_title']} by {row['query_author']}".lower().strip(),
            "General & Contemporary Fiction"
        )
        for _, row in profile_df.iterrows()
    ]

    profile_authors = list(profile_df["authors"].dropna().unique())
    scaler          = metadata_lookup.fit_profile_scaler(profile_df)

    return metadata_lookup.build_feature_vectors(
        df=profile_df,
        genre_labels=genre_labels,
        profile_authors=profile_authors,
        scaler=scaler,
    ).to_numpy()



# Accepts a multipart upload:
#   shelf_photo  — the bookshelf image (any common image format)
#   user_id      — form field identifying whose profile to compare against
#
# Flow:
#   1. Save image to a temp file
#   2. shelf_reader extracts title+author pairs from the image via Gemini
#   3. main_pipeline fetches metadata, classifies genres, builds feature vectors
#      for BOTH the scanned books AND the user's saved profile
#   4. knn.rank_books ranks the scanned books against the profile vectors
#   5. Results are serialised to the field names script.js expects and returned

@app.route("/scan", methods=["POST"])
def scan():
    if "shelf_photo" not in request.files:
        return jsonify({"error": "shelf_photo field required"}), 400

    user_id    = request.form.get("user_id", "default")
    image_file = request.files["shelf_photo"]

    # Save the upload to a temp file — shelf_reader needs a file path on disk
    suffix = os.path.splitext(image_file.filename or "")[-1] or ".jpg"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        image_file.save(tmp.name)
        tmp.close()
        raw_books = shelf_reader.extract_titles_and_authors(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    if not raw_books:
        return jsonify({
            "scan_id": str(uuid.uuid4()),
            "books":   [],
            "total":   0,
            "message": "No books detected in image"
        }), 200

    # Load the user's saved profile
    profile       = load_profile(user_id)
    profile_books = profile["books"]

    # Use a placeholder if the profile is empty so the pipeline can still
    # fit the scaler; knn.rank_books handles None saved_vectors gracefully
    profile_input = profile_books if profile_books else [{"title": "Unknown", "authors": "Unknown"}]

    # Pipeline builds scanned book vectors; profile vectors are built separately
    clean_df, scanned_vectors_df = main_pipeline.prep_recommendation_data(
        raw_books, profile_input
    )

    saved_vectors   = _build_profile_vectors(profile_books) if profile_books else None
    scanned_vectors = scanned_vectors_df.to_numpy()
    scanned_list    = clean_df.to_dict(orient="records")

    ranked = knn.rank_books(saved_vectors, scanned_vectors, scanned_list)

    return jsonify({
        "scan_id": str(uuid.uuid4()),
        "books":   [_to_frontend(b) for b in ranked],
        "total":   len(ranked)
    }), 200



# POST /onboard
# Stores up to 10 book titles as minimal profile entries (no metadata).
# These give the KNN something to compare against before the first real scan.


@app.route("/onboard", methods=["POST"])
def onboard():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    user_id = data.get("user_id")
    books   = data.get("books", [])

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    if not isinstance(books, list) or len(books) > 10:
        return jsonify({"error": "books must be a list of up to 10 titles"}), 400

    profile      = load_profile(user_id)
    saved_titles = [b["title"] for b in profile["books"]]
    added        = 0

    for entry in books:
        # Accept either a plain title string or a {title, author} object —
        # the onboarding search UI knows the author; keeping it improves
        # the metadata lookup Katherine's pipeline does downstream.
        if isinstance(entry, dict):
            title  = entry.get("title")
            author = entry.get("author") or entry.get("authors")
        else:
            title  = entry
            author = None

        if not title or title in saved_titles:
            continue
        profile["books"].append(normalize_book({
            "title":        title,
            "query_title":  title,
            "query_author": author,
            "found":        False,
        }))
        saved_titles.append(title)
        added += 1

    save_profile(user_id, profile)
    return jsonify({
        "message": f"Added {added} new book(s) to '{user_id}'s profile",
        "books":   profile["books"]
    }), 200



# POST /save
# Adds one fully-enriched book (Google Books format) to the user's profile.
# Duplicate detection is by title — safe to call repeatedly.


@app.route("/save", methods=["POST"])
def save():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    user_id  = data.get("user_id")
    raw_book = data.get("book")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    if not raw_book or not isinstance(raw_book, dict):
        return jsonify({"error": "'book' must be an object"}), 400

    book = normalize_book(raw_book)

    if not book["title"]:
        return jsonify({"error": "'title' is required inside book"}), 400

    profile      = load_profile(user_id)
    saved_titles = [b["title"] for b in profile["books"]]

    if book["title"] not in saved_titles:
        profile["books"].append(book)
        save_profile(user_id, profile)
        message = f"'{book['title']}' added to {user_id}'s profile"
    else:
        message = f"'{book['title']}' is already saved"

    return jsonify({"message": message, "books": profile["books"]}), 200



# GET /profile?user_id=<id>
# Returns the user's saved book list.

@app.route("/profile", methods=["GET"])
def profile():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id query parameter is required"}), 400

    profile_data = load_profile(user_id)
    return jsonify({
        "user_id": user_id,
        "books":   profile_data["books"],
        "total":   len(profile_data["books"])
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
