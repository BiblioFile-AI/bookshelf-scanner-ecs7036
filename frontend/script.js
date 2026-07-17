// ---------- element references ----------
const photoInput = document.getElementById('photo-input');
const mainButton = document.getElementById('main-button');
const scanScreen = document.getElementById('scan-screen');
const loadingScreen = document.getElementById('loading-screen');
const resultsScreen = document.getElementById('results-screen');
const errorScreen = document.getElementById('error-screen');
const emptyScreen = document.getElementById('empty-screen');
const libraryScreen = document.getElementById('library-screen');
const welcomeScreen = document.getElementById('welcome-screen');
const addBooksScreen = document.getElementById('add-books-screen');
const doneScreen = document.getElementById('done-screen');
const cardList = document.getElementById('card-list');
const resultsCount = document.getElementById('results-count');
const scanAgainButton = document.getElementById('scan-again');
const errorRetryButton = document.getElementById('error-retry');
const emptyRetryButton = document.getElementById('empty-retry');

const bottomNav = document.getElementById('bottom-nav');
const navScanBtn = document.getElementById('nav-scan');
const navLibraryBtn = document.getElementById('nav-library');
const tabSavedBtn = document.getElementById('btn-tab-saved');
const tabTasteBtn = document.getElementById('btn-tab-taste');
const savedScansList = document.getElementById('saved-scans-list');
const tasteProfileList = document.getElementById('taste-profile-list');
const segmentPill = document.getElementById('segment-pill');

const searchInput = document.getElementById('book-search-input');
const suggestionsDropdown = document.getElementById('suggestions-dropdown');
const profileCounter = document.getElementById('profile-counter');
const progressFill = document.getElementById('progress-fill');
const profileList = document.getElementById('profile-list');
const continueBtn = document.getElementById('continue-btn');
const getStartedBtn = document.getElementById('get-started-btn');
const startScanningBtn = document.getElementById('start-scanning-btn');

let selectedFile = null;
let addBooksMode = 'onboarding';

// ---------- storage ----------
const SAVED_KEY = 'bookscanner_saved_books';
const PROFILE_KEY = 'bookscanner_taste_profile';
const ONBOARDED_KEY = 'bookscanner_onboarded';
const USER_ID_KEY = 'bookscanner_user_id';
const API_BASE = 'https://bookshelf-scanner-ecs7036.onrender.com';

function bookKey(book) {
  return `${book.title}::${book.author}`;
}

// Every backend route needs a user_id to know whose profile to use.
// There's no login, so each browser gets one UUID, generated once and
// reused for every /onboard, /scan, /save and /profile call.
function getUserId() {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

// Push the local taste profile to the backend so KNN has something to
// rank scans against. Safe to call repeatedly — /onboard skips titles
// it already has.
async function syncProfileToBackend() {
  const profile = getTasteProfile();
  if (profile.length === 0) return;

  try {
    await fetch(`${API_BASE}/onboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: getUserId(),
        books: profile.map(b => ({ title: b.title, author: b.author })),
      }),
    });
  } catch (err) {
    console.error('Profile sync failed:', err);
  }
}

// Same idea, for a single book saved (starred) from scan results. Without
// this, a saved scan book only ever lived in localStorage and never became
// part of the server-side profile the KNN ranker builds vectors from.
async function syncSavedBookToBackend(book) {
  try {
    await fetch(`${API_BASE}/onboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: getUserId(),
        books: [{ title: book.title, author: book.author }],
      }),
    });
  } catch (err) {
    console.error('Saved book profile sync failed:', err);
  }
}

// Saved scans (starred from results)
function getSavedBooks() {
  const raw = localStorage.getItem(SAVED_KEY);
  return raw ? JSON.parse(raw) : [];
}

function isBookSaved(book) {
  return getSavedBooks().some(b => bookKey(b) === bookKey(book));
}

function saveBook(book) {
  const saved = getSavedBooks();
  if (!saved.some(b => bookKey(b) === bookKey(book))) {
    saved.push(book);
    localStorage.setItem(SAVED_KEY, JSON.stringify(saved));
  }
}

function unsaveBook(book) {
  const filtered = getSavedBooks().filter(b => bookKey(b) !== bookKey(book));
  localStorage.setItem(SAVED_KEY, JSON.stringify(filtered));
}

// Taste profile (onboarding books)
function getTasteProfile() {
  const raw = localStorage.getItem(PROFILE_KEY);
  return raw ? JSON.parse(raw) : [];
}

function addToProfile(book) {
  const profile = getTasteProfile();
  if (!profile.some(b => bookKey(b) === bookKey(book))) {
    profile.push(book);
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  }
}

function removeFromProfile(book) {
  const filtered = getTasteProfile().filter(b => bookKey(b) !== bookKey(book));
  localStorage.setItem(PROFILE_KEY, JSON.stringify(filtered));
}

function isOnboarded() {
  return localStorage.getItem(ONBOARDED_KEY) === 'true';
}

function markOnboarded() {
  localStorage.setItem(ONBOARDED_KEY, 'true');
}

// ---------- screen navigation ----------
function hideAllScreens() {
  welcomeScreen.hidden = true;
  addBooksScreen.hidden = true;
  doneScreen.hidden = true;
  scanScreen.hidden = true;
  loadingScreen.hidden = true;
  resultsScreen.hidden = true;
  errorScreen.hidden = true;
  emptyScreen.hidden = true;
  libraryScreen.hidden = true;
}

function hideNav() { bottomNav.hidden = true; }
function showNav() { bottomNav.hidden = false; }

function resetScanState() {
  selectedFile = null;
  photoInput.value = '';
  const preview = document.getElementById('photo-preview');
  preview.src = '';
  preview.hidden = true;
  document.querySelector('.upload-icon').hidden = false;
  document.querySelector('.upload-zone p').hidden = false;
  mainButton.textContent = 'Choose Photo';
}

function goToScan() {
  resetScanState();
  hideAllScreens();
  scanScreen.hidden = false;
  showNav();
  navScanBtn.classList.add('active');
  navLibraryBtn.classList.remove('active');
}

function goToLibrary() {
  hideAllScreens();
  libraryScreen.hidden = false;
  showNav();
  showSavedTab();
  navLibraryBtn.classList.add('active');
  navScanBtn.classList.remove('active');
}

function goToWelcome() {
  hideAllScreens();
  hideNav();
  welcomeScreen.hidden = false;
}

function goToAddBooks(mode) {
  addBooksMode = mode;
  hideAllScreens();
  if (mode === 'onboarding') hideNav(); else showNav();
  addBooksScreen.hidden = false;
  searchInput.value = '';
  hideSuggestions();
  renderProfile();
  updateContinueButton();
}

function goToDone() {
  hideAllScreens();
  hideNav();
  doneScreen.hidden = false;
}

navScanBtn.addEventListener('click', goToScan);
navLibraryBtn.addEventListener('click', goToLibrary);

// ---------- scan flow ----------
mainButton.addEventListener('click', () => {
  if (!selectedFile) {
    photoInput.click();
  } else {
    startScan();
  }
});

photoInput.addEventListener('change', () => {
  const file = photoInput.files[0];
  if (!file) return;
  selectedFile = file;

  const preview = document.getElementById('photo-preview');
  preview.src = URL.createObjectURL(file);
  preview.hidden = false;

  document.querySelector('.upload-icon').hidden = true;
  document.querySelector('.upload-zone p').hidden = true;

  mainButton.textContent = 'Scan This Shelf';
});

async function startScan() {
  hideAllScreens();
  loadingScreen.hidden = false;

  try {
    const formData = new FormData();
    formData.append('shelf_photo', selectedFile);
    formData.append('user_id', getUserId());
    const response = await fetch(`${API_BASE}/scan`, { method: 'POST', body: formData });

    if (!response.ok) throw new Error(`Server responded ${response.status}`);
    const data = await response.json();

    if (!data.books || data.books.length === 0) {
      loadingScreen.hidden = true;
      emptyScreen.hidden = false;
    } else {
      renderResults(data.books);
      loadingScreen.hidden = true;
      resultsScreen.hidden = false;
    }
  } catch (err) {
    console.error('Scan failed:', err);
    loadingScreen.hidden = true;
    errorScreen.hidden = false;
  }
}

// ---------- results cards ----------
function createBookCard(book) {
  const card = document.createElement('a');
  card.className = 'book-card' + (book.is_top_pick ? ' top-pick' : '');
  card.href = goodreadsUrl(book);
  card.target = '_blank';
  card.rel = 'noopener';

  const saved = isBookSaved(book) || book.already_saved;
  card.innerHTML = `
    <button class="card-star${saved ? ' saved' : ''}" aria-label="Save book">${saved ? '★' : '☆'}</button>
    ${book.already_saved ? '<span class="top-pick-badge already-saved-badge">Already saved in library</span>'
      : book.is_top_pick ? `<span class="top-pick-badge">#${book.rank} Pick</span>` : ''}
    <span class="book-title">${book.title}</span>
    <span class="book-author">${book.author}</span>
    <span class="book-meta">${book.genre || 'Unknown Genre'} · ${book.year || 'N/A'} · ${book.pages || '?'} pp</span>
  `;

  const star = card.querySelector('.card-star');
  star.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const nowSaved = star.classList.toggle('saved');
    star.textContent = nowSaved ? '★' : '☆';
    if (nowSaved) {
      saveBook(book);
      syncSavedBookToBackend(book);
    } else {
      unsaveBook(book);
    }
  });

  return card;
}

function renderResults(books) {
  cardList.innerHTML = '';
  resultsCount.textContent =
    `${books.length} books identified · ranked by match to your taste`;
  books.forEach(book => cardList.appendChild(createBookCard(book)));
}

function goodreadsUrl(book) {
  const query = encodeURIComponent(book.title);
  return `https://www.goodreads.com/search?q=${query}&search%5Bfield%5D=title`;
}

scanAgainButton.addEventListener('click', goToScan);
errorRetryButton.addEventListener('click', goToScan);
emptyRetryButton.addEventListener('click', goToScan);

// ---------- library tabs ----------
function showSavedTab() {
  savedScansList.hidden = false;
  tasteProfileList.hidden = true;
  tabSavedBtn.classList.add('active');
  tabTasteBtn.classList.remove('active');
  segmentPill.classList.remove('right');
  renderSavedScans();
}

function showTasteTab() {
  savedScansList.hidden = true;
  tasteProfileList.hidden = false;
  tabSavedBtn.classList.remove('active');
  tabTasteBtn.classList.add('active');
  segmentPill.classList.add('right');
  renderTasteProfileTab();
}

tabSavedBtn.addEventListener('click', showSavedTab);
tabTasteBtn.addEventListener('click', showTasteTab);

// Saved Scans tab: only books starred from scan results
function renderSavedScans() {
  const saved = getSavedBooks();
  savedScansList.innerHTML = '';

  if (saved.length === 0) {
    savedScansList.innerHTML =
      `<p class="empty-list-hint">You haven't saved any books yet.<br>Tap the star on a book from your scan results to save it here.</p>`;
    return;
  }

  saved.forEach(book => {
    const card = createBookCard(book);
    // When unstarring from the library view, refresh the list
    const star = card.querySelector('.card-star');
    star.addEventListener('click', () => {
      // Small delay so the toggle animation plays before the card disappears
      setTimeout(() => renderSavedScans(), 200);
    });
    savedScansList.appendChild(card);
  });
}

// Taste Profile tab: only onboarding books, with add-more button
function renderTasteProfileTab() {
  const profile = getTasteProfile();
  tasteProfileList.innerHTML = '';

  // Add more button at the top
  const addMoreBtn = document.createElement('button');
  addMoreBtn.className = 'btn-secondary';
  addMoreBtn.textContent = '+ Add more books to your taste profile';
  addMoreBtn.addEventListener('click', () => goToAddBooks('library'));
  tasteProfileList.appendChild(addMoreBtn);

  if (profile.length === 0) {
    const hint = document.createElement('p');
    hint.className = 'empty-list-hint';
    hint.textContent = 'Your taste profile is empty. Add some books you love.';
    tasteProfileList.appendChild(hint);
  } else {
    profile.forEach(book => {
      tasteProfileList.appendChild(
        createOnboardingBookCard(book, () => {
          removeFromProfile(book);
          renderTasteProfileTab();
        })
      );
    });
  }
}

// ---------- onboarding book card ----------
function createOnboardingBookCard(book, onRemove) {
  const card = document.createElement('div');
  card.className = 'onboarding-book-card';
  card.innerHTML = `
    <button class="card-remove" aria-label="Remove book">✕</button>
    <a class="book-link" href="${goodreadsUrl(book)}" target="_blank" rel="noopener">
      <span class="book-title">${book.title}</span>
      <span class="book-author">${book.author}</span>
    </a>
  `;
  card.querySelector('.card-remove').addEventListener('click', onRemove);
  return card;
}

// ---------- add books screen: search + profile ----------
function renderProfile() {
  const profile = getTasteProfile();
  profileCounter.textContent = `${profile.length} of 10 added`;
  progressFill.style.width = `${Math.min((profile.length / 10) * 100, 100)}%`;

  profileList.innerHTML = '';
  profile.forEach(book => {
    profileList.appendChild(
      createOnboardingBookCard(book, () => {
        removeFromProfile(book);
        renderProfile();
        updateContinueButton();
      })
    );
  });
}

function updateContinueButton() {
  const canContinue = getTasteProfile().length >= 3;
  continueBtn.disabled = !canContinue;
}

function hideSuggestions() {
  suggestionsDropdown.hidden = true;
  suggestionsDropdown.innerHTML = '';
}

// ---------- Live API Search (Open Library) ----------

let searchTimeout;

// 1. Listen for typing and apply the "Debounce"
searchInput.addEventListener('input', (e) => {
  const query = e.target.value;

  clearTimeout(searchTimeout); // Cancel the previous timer

  if (!query.trim()) {
    hideSuggestions();
    return;
  }

  // Show a quick loading state so the user knows it's working
  suggestionsDropdown.innerHTML = `<div class="suggestion-row no-match">Searching library...</div>`;
  suggestionsDropdown.hidden = false;

  // Wait 400ms after they stop typing before hitting the API
  searchTimeout = setTimeout(() => {
    fetchBooksFromAPI(query);
  }, 400);
});

// 2. Fetch the live data (Using Open Library API)
async function fetchBooksFromAPI(query) {
  try {
    // Ping the free Open Library database, limiting to 5 results
    const response = await fetch(`https://openlibrary.org/search.json?q=${encodeURIComponent(query)}&limit=5`);
    const data = await response.json();

    // Open Library stores its results in an array called "docs"
    if (!data.docs || data.docs.length === 0) {
      renderSuggestions([]); 
      return;
    }

    // Format the Open Library data into our clean Bookscanner format
    const liveMatches = data.docs.map(item => ({
      title: item.title || "Unknown Title",
      // Open Library returns authors as an array
      author: item.author_name ? item.author_name.join(', ') : "Unknown Author",
    }));

    renderSuggestions(liveMatches);

  } catch (error) {
    console.error("API Error:", error);
    suggestionsDropdown.innerHTML = `<div class="suggestion-row no-match">Connection error</div>`;
  }
}

// 3. Render the results
function renderSuggestions(matches) {
  const profile = getTasteProfile();
  const profileKeys = new Set(profile.map(bookKey));

  suggestionsDropdown.innerHTML = '';
  suggestionsDropdown.hidden = false;

  // Filter out books the user has already added to their profile
  const filteredMatches = matches.filter(b => !profileKeys.has(bookKey(b)));

  if (filteredMatches.length === 0) {
    suggestionsDropdown.innerHTML = `<div class="suggestion-row no-match">No matches found</div>`;
    return;
  }

  filteredMatches.forEach(book => {
    const row = document.createElement('button');
    row.className = 'suggestion-row';
    row.innerHTML = `
      <div class="suggestion-text">
        <span class="book-title">${book.title}</span>
        <span class="book-author">${book.author}</span>
      </div>
      <span class="suggestion-add">+</span>
    `;
    
    row.addEventListener('click', () => {
      if (getTasteProfile().length >= 10) return;
      addToProfile(book);
      searchInput.value = '';
      hideSuggestions();
      renderProfile();
      updateContinueButton();
    });
    
    suggestionsDropdown.appendChild(row);
  });
}

// Close suggestions when clicking outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('.search-input-wrap')) {
    hideSuggestions();
  }
});

continueBtn.addEventListener('click', () => {
  if (continueBtn.disabled) return;
  syncProfileToBackend();
  if (addBooksMode === 'onboarding') {
    goToDone();
  } else {
    goToLibrary();
    showTasteTab();
  }
});

getStartedBtn.addEventListener('click', () => goToAddBooks('onboarding'));

startScanningBtn.addEventListener('click', () => {
  markOnboarded();
  goToScan();
});

// ---------- initial page state ----------
if (!isOnboarded()) {
  goToWelcome();
} else {
  goToScan();
}