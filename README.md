# BiblioFile AI

### An AI-Powered Platform for Discovering Your Next Book from Any Physical Shelf

![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=flat&logo=flask)
![Gemini](https://img.shields.io/badge/Gemini-Vision%20%26%20Genre%20AI-8E75B2?style=flat)
![scikit--learn](https://img.shields.io/badge/scikit--learn-KNN-F7931E?style=flat&logo=scikit-learn)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python)
![HTML/CSS/JS](https://img.shields.io/badge/Frontend-HTML%2FCSS%2FJS-FFB13B?style=flat)
![Netlify](https://img.shields.io/badge/Deployed-Netlify-00C7B7?style=flat&logo=netlify)

---

## Overview

BiblioFile AI is an AI-powered web application that helps readers
discover their next book from any bookshelf, whether it's at a charity
shop, a secondhand bookshop, or a friend's living room. Instead of
manually searching each unfamiliar title, the user photographs the shelf
and receives an instantly ranked list of every book detected, matched
against their own reading taste.

The platform turns a wall of unfamiliar spines into a personalised,
navigable shortlist, with direct links out to Goodreads for reviews,
synopsis and further reading.

---

## Problem Statement

Physical browsing is slow, and the tools that could help don't fit the
moment:

- Existing platforms like Goodreads and LibraryThing recommend from a
  user's *entire reading history* against their own catalogue — they have
  no concept of which books are physically in front of the user right now
- Manually searching every unfamiliar spine on a phone is slow and breaks
  the flow of browsing
- Choices end up based on cover design or title alone, rather than genuine
  fit with a reader's taste

This creates a gap between what's on the shelf and *what a reader might
actually enjoy*.

---

## Solution

BiblioFile AI closes that gap with a five-stage pipeline that goes from a
single photograph to a personalised, ranked shortlist in seconds.

The platform:

- Reads every visible book spine from a single shelf photograph
- Retrieves structured metadata for each detected title
- Classifies each book into a clean, consistent genre
- Ranks the shelf against the user's own saved taste profile
- Links every result straight through to Goodreads

By combining computer vision, structured metadata retrieval, and a
custom recommendation model, BiblioFile AI answers not just **what** is on
the shelf, but **which of these books this specific reader is most likely
to enjoy**.

---

## Key Features

### Shelf Scanning

Photograph any bookshelf and receive a structured list of every book
spine the model can read, extracted directly from the image.

### Personalised Ranking

A K-Nearest-Neighbours recommender compares every detected book against
the user's own taste profile and highlights the closest matches.

### Taste Profile Onboarding

New users seed their profile with 3–10 books they've already enjoyed,
searchable and addable in seconds, and can keep adding to it at any time.

### Save and Revisit

Any book from a scan can be starred and revisited later from a personal
library, separate from the onboarding taste profile.

### Goodreads Deep-Linking

Every result links directly to a title-scoped Goodreads search, giving
the user reviews and further detail with one tap.

---

## Technology Stack

### AI / Machine Learning

| Tool               | Purpose                                                 |
| ------------------- | -------------------------------------------------------- |
| Google Gemini        | Vision-based spine extraction and genre classification  |
| Google Books API      | Primary book metadata retrieval                        |
| Open Library API      | Fallback metadata source                                |
| scikit-learn (KNN)    | Custom-weighted nearest-neighbours recommendation       |

### Development Tools

| Tool             | Purpose                                    |
| ----------------- | -------------------------------------------- |
| Python 3.10+       | Backend logic and ML pipeline               |
| Flask              | REST API connecting frontend and pipeline   |
| Pandas / NumPy     | Metadata processing and feature vectors     |
| HTML / CSS / JS    | Frontend interface, no framework            |
| Figma              | Design system and interactive prototype     |
| GitHub             | Version control and collaboration           |
| Netlify / Render   | Frontend and backend deployment             |

---

## System Architecture

```
┌─────────────────────┐
│   Shelf Photograph    │
│   (phone camera)      │
└────────┬──────────────┘
         ↓
┌─────────────────────┐
│  Gemini Vision Model   │
│  Title/Author Extract  │
└────────┬──────────────┘
         ↓
┌─────────────────────┐
│  Metadata Lookup       │
│  Google Books +        │
│  Open Library Fallback │
└────────┬──────────────┘
         ↓
┌─────────────────────┐
│  Genre Classification  │
│  Gemini (zero-shot)    │
└────────┬──────────────┘
         ↓
┌─────────────────────┐
│  Feature Vectors       │
│  genre · author ·      │
│  pages · year          │
└────────┬──────────────┘
         ↓
┌─────────────────────┐
│  KNN Recommender        │
│  Custom weighted         │
│  distance (scikit-learn) │
└────────┬──────────────┘
         ↓
┌─────────────────────┐
│  Ranked Results         │
│  Flask JSON response    │
└────────┬──────────────┘
         ↓
┌─────────────────────┐
│  Frontend Rendering     │
│  HTML/CSS/JS UI          │
└─────────────────────┘
```

---

## Setup and Running Instructions

### Prerequisites

- Python 3.10+
- A modern web browser
- A free [Gemini API key](https://aistudio.google.com/apikey)
- A free [Google Books API key](https://console.cloud.google.com/)

### Backend

```bash
cd backend
pip install -r requirements.txt --break-system-packages
```

Create a `.env` file in `backend/` with your API keys (see
`.env.example`):

```
GEMINI_API_KEY=your_key_here
GOOGLE_BOOKS_API_KEY=your_key_here
```

Run the server:

```bash
python app.py
```

### Frontend

```bash
cd frontend
```

Serve `index.html` with a local server (e.g. VS Code's Live Server
extension, or `python -m http.server`). Opening the file directly via
`file://` will not work, as the app fetches local JSON over `fetch()`.

### Full application

1. Start the backend.
2. Serve the frontend.
3. Open the frontend URL in a browser (or on a phone, for camera
   testing).
4. Complete onboarding with 3–10 books you've enjoyed.
5. Scan a shelf to see ranked recommendations.

**Live deployment:** `[INSERT NETLIFY / RENDER URLS]`

---

## Dataset

No publicly available dataset is used. Two self-generated data assets
are included in the submitted code archive:

- **Genre similarity matrix** — a hand-crafted 10×10 matrix scoring
  similarity between genre pairs, used in place of one-hot encoding for
  the KNN's genre feature.
- **API response cache** — cached Google Books / Open Library responses
  from a 32-book test set, used to evaluate metadata coverage (see the
  Results and Discussion section of the project report).

---

## Team Members

| Name    | Role                                                                  |
| ------- | ---------------------------------------------------------------------- |
| Katy    | LLM prompt design — vision extraction and genre classification         |
| Emma    | Google Books / Open Library integration, feature vector construction   |
| Alexa   | Flask backend, KNN recommender logic, storage                          |
| Anna    | Figma design system, CSS/HTML/JS front-end implementation              |

---

## Future Enhancements

- Deployment hardening for concurrent users
- Collaborative filtering across users with similar taste profiles
- Shelf memory, to avoid re-surfacing previously scanned books
- Native camera capture improvements for low-light shelf photography

---

## Impact

While artificial intelligence and digital intervention are often viewed
as antithetical to the analog joy of reading, BiblioFile AI leverages
this technology to enhance the physical experience. It takes the
overwhelming task out of browsing a bookshelf, making the act of
browsing more personalised, and thus, more enjoyable.

---

*Developed for ECS7036P Applications of AI, Queen Mary University of
London.*
