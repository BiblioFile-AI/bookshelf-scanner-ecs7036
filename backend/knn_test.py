
# Section 5: Test data and demo run ( using made up)
import numpy as np
from sklearn.neighbors import NearestNeighbors

from knn import _build_similarity_matrix
from knn import custom_distance
from knn import rank_books

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

# works as expected - returns atermis as top ranked book and unrelated genres at the bottom
