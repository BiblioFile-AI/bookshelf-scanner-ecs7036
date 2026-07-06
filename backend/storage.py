import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# All fields expected from a Google Books API lookup result.
# Any field absent from the incoming dict is stored as None.
_BOOK_FIELDS = [
    "query_title",
    "query_author",
    "found",
    "title",
    "authors",
    "categories",
    "averageRating",
    "pageCount",
    "publishedDate",
]


def normalize_book(raw: dict) -> dict:
    """
    Coerce a raw Google Books API result dict into a fixed-shape book object.
    Missing or null fields are stored as None so the frontend always gets a
    consistent structure regardless of what the API returned.
    """
    return {field: raw.get(field) for field in _BOOK_FIELDS}


def _profile_path(user_id: str) -> str:
    """Return the file path for a given user's JSON profile."""
    safe_id = "".join(c for c in user_id if c.isalnum() or c in ("_", "-"))
    return os.path.join(DATA_DIR, f"{safe_id}.json")


def load_profile(user_id: str) -> dict:
    """
    Load a user's profile from disk.
    If no file exists yet, returns a fresh empty profile.
    """
    path = _profile_path(user_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"user_id": user_id, "books": []}


def save_profile(user_id: str, profile: dict) -> None:
    """Persist a user's profile dict to their JSON file in data/."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _profile_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
