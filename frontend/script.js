// ---------- element references ----------
const photoInput = document.getElementById('photo-input');
const mainButton = document.getElementById('main-button');
const scanScreen = document.getElementById('scan-screen');
const loadingScreen = document.getElementById('loading-screen');
const resultsScreen = document.getElementById('results-screen');
const errorScreen = document.getElementById('error-screen');
const emptyScreen = document.getElementById('empty-screen');
const cardList = document.getElementById('card-list');
const resultsCount = document.getElementById('results-count');
const scanAgainButton = document.getElementById('scan-again');
const errorRetryButton = document.getElementById('error-retry');
const emptyRetryButton = document.getElementById('empty-retry');

let selectedFile = null;

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
  scanScreen.hidden = true;
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
      emptyScreen.hidden = false;
    } else {
      renderResults(data.books);
      resultsScreen.hidden = false;
    }
  } catch (err) {
    console.error('Scan failed:', err);
    errorScreen.hidden = false;
  } finally {
    loadingScreen.hidden = true;
  }
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ---------- building the results ----------
function renderResults(books) {
  cardList.innerHTML = '';
  resultsCount.textContent =
    `${books.length} books identified · ranked by match to your taste`;

  books.forEach(book => {
    const card = document.createElement('a');
    card.className = 'book-card' + (book.is_top_pick ? ' top-pick' : '');
    card.href = goodreadsUrl(book);
    card.target = '_blank';

    card.innerHTML = `
      ${book.is_top_pick ? '<span class="top-pick-badge">TOP PICK</span>' : ''}
      <span class="book-title">${book.title}</span>
      <span class="book-author">${book.author}</span>
      <span class="book-meta">${book.genre} · ${book.year} · ${book.pages} pp</span>
    `;

    cardList.appendChild(card);
  });
}

function goodreadsUrl(book) {
  const query = encodeURIComponent(book.title);
  return `https://www.goodreads.com/search?q=${query}&search%5Bfield%5D=title`;
}

// ---------- retry / reset ----------
scanAgainButton.addEventListener('click', () => window.location.reload());
errorRetryButton.addEventListener('click', () => window.location.reload());
emptyRetryButton.addEventListener('click', () => window.location.reload());