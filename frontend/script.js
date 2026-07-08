// ---------- element references ----------
const photoInput = document.getElementById('photo-input');
const mainButton = document.getElementById('main-button');
const scanScreen = document.getElementById('scan-screen');
const loadingScreen = document.getElementById('loading-screen');
const resultsScreen = document.getElementById('results-screen');
const errorScreen = document.getElementById('error-screen');
const emptyScreen = document.getElementById('empty-screen');
const libraryScreen = document.getElementById('library-screen');
const cardList = document.getElementById('card-list');
const resultsCount = document.getElementById('results-count');
const scanAgainButton = document.getElementById('scan-again');
const errorRetryButton = document.getElementById('error-retry');
const emptyRetryButton = document.getElementById('empty-retry');

const navScanBtn = document.getElementById('nav-scan');
const navLibraryBtn = document.getElementById('nav-library');
const tabSavedBtn = document.getElementById('btn-tab-saved');
const tabTasteBtn = document.getElementById('btn-tab-taste');
const savedScansList = document.getElementById('saved-scans-list');
const tasteProfileList = document.getElementById('taste-profile-list');
const segmentPill = document.getElementById('segment-pill');

let selectedFile = null;

// ---------- saved books storage ----------
const SAVED_KEY = 'bookscanner_saved_books';

function getSavedBooks() {
  const raw = localStorage.getItem(SAVED_KEY);
  return raw ? JSON.parse(raw) : [];
}

function bookKey(book) {
  return `${book.title}::${book.author}`;
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

// ---------- choosing a photo ----------
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

// ---------- the scan flow ----------
async function startScan() {
  hideAllScreens();
  loadingScreen.hidden = false;

  try {
    // TODO integration: replace the two lines below with a real upload:
    // const formData = new FormData();
    // formData.append('shelf_photo', selectedFile);
    // const response = await fetch('http://localhost:5000/scan', { method: 'POST', body: formData });
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

// ---------- rendering book cards ----------
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

    // If we're viewing the library, unsaving should remove the card from view
    if (!libraryScreen.hidden && !nowSaved) {
      renderLibrary();
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

// ---------- navigation between top-level screens ----------
function hideAllScreens() {
  scanScreen.hidden = true;
  loadingScreen.hidden = true;
  resultsScreen.hidden = true;
  errorScreen.hidden = true;
  emptyScreen.hidden = true;
  libraryScreen.hidden = true;
}

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
  navScanBtn.classList.add('active');
  navLibraryBtn.classList.remove('active');
}

function goToLibrary() {
  hideAllScreens();
  libraryScreen.hidden = false;
  renderLibrary();
  navLibraryBtn.classList.add('active');
  navScanBtn.classList.remove('active');
}

navScanBtn.addEventListener('click', goToScan);
navLibraryBtn.addEventListener('click', goToLibrary);

scanAgainButton.addEventListener('click', goToScan);
errorRetryButton.addEventListener('click', goToScan);
emptyRetryButton.addEventListener('click', goToScan);

// ---------- library: tabs + rendering ----------
function showSavedTab() {
  savedScansList.hidden = false;
  tasteProfileList.hidden = true;
  tabSavedBtn.classList.add('active');
  tabTasteBtn.classList.remove('active');
  segmentPill.classList.remove('right');
}

function showTasteTab() {
  savedScansList.hidden = true;
  tasteProfileList.hidden = false;
  tabSavedBtn.classList.remove('active');
  tabTasteBtn.classList.add('active');
  segmentPill.classList.add('right');
}

tabSavedBtn.addEventListener('click', showSavedTab);
tabTasteBtn.addEventListener('click', showTasteTab);

function renderLibrary() {
  const saved = getSavedBooks();

  savedScansList.innerHTML = '';
  if (saved.length === 0) {
    savedScansList.innerHTML =
      `<p class="empty-list-hint">You haven't saved any books yet.<br>Tap the star on a book from your scan results to save it here.</p>`;
  } else {
    saved.forEach(book => savedScansList.appendChild(createBookCard(book)));
  }

  tasteProfileList.innerHTML =
    `<p class="empty-list-hint">Your taste profile will build up as you save books and complete onboarding.</p>`;
}