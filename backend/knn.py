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



# Section 1: Genre taxonomy

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



# Section 2: Genre similarity matrix

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



# Section 3: Custom distance function
# Vector layout ():
#   v[0]  genre_index   : integer 0-9, looked up in GENRE_SIMILARITY
#   v[1]  known_author  : 1.0 if author is in saved profile, else 0.0
#   v[2]  pageCount_z   : z-score relative to profile mean/std
#   v[3]  year_z        : z-score relative to profile mean/std
#
# Weights: genre 60%, known_author 20%, page 10%, year 10%.
#
# tanh squashes any positive value into (0,1):
# This keeps the weights meaningful regardless of scale.

def custom_distance(v1, v2):
    """
    Weighted distance between two 4-dimensional book feature vectors.
    Called by sklearn's NearestNeighbors for every pair of vectors.
    """
    # Genre: read index directly from position 0 and look up similarity.
    g1 = int(round(v1[0]))
    g2 = int(round(v2[0]))
    genre_dist = 1.0 - GENRE_SIMILARITY[g1][g2]

    # Known author: already binary (0 or 1), difference is naturally in [0, 1].
    author_dist = abs(v1[1] - v2[1])

    # Z-scores: tanh maps the absolute difference to (0, 1).
    page_dist = np.tanh(abs(v1[2] - v2[2]))
    year_dist = np.tanh(abs(v1[3] - v2[3]))

    return 0.6 * genre_dist + 0.2 * author_dist + 0.1 * page_dist + 0.1 * year_dist


# Section 4: Main ranking function

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
            entry["is_top_pick"] = (i < 3)
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
        results[idx]["is_top_pick"] = (rank <= 3)

    # Sort best-match-first so the ranking is reflected in the returned
    # order, not just in the 'rank' field.
    results.sort(key=lambda b: b["rank"])
    return results


