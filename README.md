# Bookshelf Scanner

An AI-powered web application that lets a user photograph a bookshelf and receive a ranked list of books matching their personal reading taste. Built for ECS7036P Applications of AI, Queen Mary University of London.

## How it works

The user uploads a photo of a physical bookshelf. A multimodal vision-language model extracts each book's title and author from the spines. The Google Books API retrieves structured metadata. An LLM zero-shot classifier assigns a clean genre label to each book. A K-Nearest Neighbours recommender ranks the shelf against the user's saved taste profile and highlights the best matches.

## Project structure

- `backend/` — Python modules for the pipeline (LLM, metadata, recommender, Flask app)
- `frontend/` — HTML, CSS, JavaScript for the web interface
- `notebooks/` — Exploratory Colab notebooks for prompt testing and API audits
- `data/` — Local storage for user profiles and the genre cache (not committed)
- `docs/` — Proposal, report, and presentation materials

## Team

- Anna Kapanadze — front-end and design
- Emma Hirayama — books and metadata
- Katherine Pietroni — LLM and extraction
- Alexa Garcia Nunez — back-end and KNN
