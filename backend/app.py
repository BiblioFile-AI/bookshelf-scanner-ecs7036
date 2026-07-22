import os
import re
import tempfile
import uuid
from flask import Flask, request, jsonify


# important functions from Katies and Emmas code 
import knn
import main_pipeline
import shelf_reader
from storage import load_profile, save_profile, normalize_book

app = Flask(__name__)


# Lets the frontend (a different origin) read responses from this backend
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


# Converts one book from pipeline format to the format the frontend expects

def _to_frontend(book):
    # Pull the year out of the publish date string, e.g. "2020-03-15" -> 2020
    pub_date = book.get("publishedDate") or ""
    year_match = re.search(r"\d{4}", str(pub_date))
    #  Use the AI-classified genre if there is one; otherwise fall back to
    # Google Books' own category text
    genre_label = book.get("genre_label")
    genre = genre_label if genre_label and genre_label != "Unknown" else (book.get("categories") or "Unknown")
    return {
        "title":       book.get("title"),
        "author":      book.get("authors"),          # authors     -> author
        "genre":       genre,
        "year":        int(year_match.group()) if year_match else None,
        "pages":       book.get("pageCount"),        # pageCount   -> pages
        "rank":        book.get("rank"),
        "is_top_pick": book.get("is_top_pick", False),
    }



#  Takes a bookshelf photo, runs the full pipeline, and returns ranked books
# 1. Save the photo to a temp file
# 2. shelf_reader reads titles and authors off the spines using Gemini
# 3. main_pipeline fetches metadata, classifies genres, builds feature vectors
# 4. knn.rank_books ranks the scanned books against the user's profile
# 5. Convert the ranked books to frontend format and return them

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

    # Builds feature vectors for both the scanned shelf and the saved profile
    # saved_vectors is None if the profile is empty, knn.rank_books handles that
    clean_df, scanned_vectors_df, saved_vectors = main_pipeline.prep_recommendation_data(
        raw_books, profile_books
    )

    scanned_vectors = scanned_vectors_df.to_numpy()
    scanned_list    = clean_df.to_dict(orient="records")

    ranked = knn.rank_books(saved_vectors, scanned_vectors, scanned_list)

    return jsonify({
        "scan_id": str(uuid.uuid4()),
        "books":   [_to_frontend(b) for b in ranked],
        "total":   len(ranked)
    }), 200



# Saves up to 10 onboarding titles so the KNN has something to compare to

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
      # Entry can be a plain title string or a {title, author} object
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




# Adds one book to the user's profile, skips it if the title is already saved

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
