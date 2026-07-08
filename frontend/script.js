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

function bookKey(book) {
  return `${book.title}::${book.author}`;
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

// ---------- mock search database ----------
const SEARCH_DB = [
  { title: "Red Rising", author: "Pierce Brown" },
  { title: "Project Hail Mary", author: "Andy Weir" },
  { title: "Piranesi", author: "Susanna Clarke" },
  { title: "The Hitchhiker's Guide to the Galaxy", author: "Douglas Adams" },
  { title: "Rebecca", author: "Daphne du Maurier" },
  { title: "Normal People", author: "Sally Rooney" },
  { title: "Sapiens", author: "Yuval Noah Harari" },
  { title: "The Alchemist", author: "Paulo Coelho" },
  { title: "The Secret History", author: "Donna Tartt" },
  { title: "Klara and the Sun", author: "Kazuo Ishiguro" },
  { title: "Beloved", author: "Toni Morrison" },
  { title: "Wuthering Heights", author: "Emily Brontë" },
  { title: "Jane Eyre", author: "Charlotte Brontë" },
  { title: "The Great Gatsby", author: "F. Scott Fitzgerald" },
  { title: "To Kill a Mockingbird", author: "Harper Lee" },
  { title: "1984", author: "George Orwell" },
  { title: "The Name of the Wind", author: "Patrick Rothfuss" },
  { title: "The Way of Kings", author: "Brandon Sanderson" },
  { title: "A Little Life", author: "Hanya Yanagihara" },
  { title: "Little Women", author: "Louisa May Alcott" },
  { title: "The Song of Achilles", author: "Madeline Miller" },
  { title: "Circe", author: "Madeline Miller" },
  { title: "Emma", author: "Jane Austen" },
  { title: "Pride and Prejudice", author: "Jane Austen" },
  { title: "Dune", author: "Frank Herbert" },
  { title: "Educated", author: "Tara Westover" },
  { title: "The Midnight Library", author: "Matt Haig" },
  { title: "Where the Crawdads Sing", author: "Delia Owens" },
  { title: "Flowers for Algernon", author: "Daniel Keyes" },
  { title: "The Curious Incident of the Dog in the Night-Time", author: "Mark Haddon" }
];

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
    await wait(2500);
    const response = await fetch('mock_scan_response.json');

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

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ---------- results cards ----------
function createBookCard(book) {
  const card = document.createElement('a');
  card.className = 'book-card' + (book.is_top_pick ? ' top-pick' : '');
  card.href = goodreadsUrl(book);
  card.target = '_blank';
  card.rel = 'noopener';

  const saved = isBookSaved(book);
  card.innerHTML = `
    <button class="card-star${saved ? ' saved' : ''}" aria-label="Save book">${saved ? '★' : '☆'}</button>
    ${book.is_top_pick ? '<span class="top-pick-badge">TOP PICK</span>' : ''}
    <span class="book-title">${book.title}</span>
    <span class="book-author">${book.author}</span>
    <span class="book-meta">${book.genre} · ${book.year} · ${book.pages} pp</span>
  `;

  const star = card.querySelector('.card-star');
  star.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const nowSaved = star.classList.toggle('saved');
    star.textContent = nowSaved ? '★' : '☆';
    if (nowSaved) saveBook(book);
    else unsaveBook(book);
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
    <span class="book-title">${book.title}</span>
    <span class="book-author">${book.author}</span>
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

function renderSuggestions(query) {
  if (!query.trim()) {
    hideSuggestions();
    return;
  }

  const profile = getTasteProfile();
  const profileKeys = new Set(profile.map(bookKey));
  const q = query.toLowerCase();

  const matches = SEARCH_DB
    .filter(b => !profileKeys.has(bookKey(b)))
    .filter(b =>
      b.title.toLowerCase().includes(q) ||
      b.author.toLowerCase().includes(q)
    )
    .slice(0, 5);

  suggestionsDropdown.innerHTML = '';
  suggestionsDropdown.hidden = false;

  if (matches.length === 0) {
    suggestionsDropdown.innerHTML =
      `<div class="suggestion-row no-match">No matches found</div>`;
    return;
  }

  matches.forEach(book => {
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

searchInput.addEventListener('input', (e) => {
  renderSuggestions(e.target.value);
});

// Close suggestions when clicking outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('.search-input-wrap')) {
    hideSuggestions();
  }
});

continueBtn.addEventListener('click', () => {
  if (continueBtn.disabled) return;
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