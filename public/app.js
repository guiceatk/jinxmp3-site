let catalogData = [];
let activeAudio = null;
let activeAudioBtn = null;

async function loadCatalog() {
  const catalogGrid = document.getElementById("catalog-grid");
  const catalogCount = document.getElementById("catalog-count");
  if (!catalogGrid) return;

  try {
    const res = await fetch("catalog.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    catalogData = await res.json();

    if (catalogCount) {
      catalogCount.textContent = `${catalogData.length} Releases Catalogued`;
    }

    renderCatalog(catalogData);
    setupSearch();
  } catch (e) {
    catalogGrid.innerHTML = `
      <div class="card" style="grid-column: 1 / -1;">
        <p class="small" style="color: #ff5555;">Could not load catalog (${e.message}). Ensure generate-catalog.js has run.</p>
      </div>`;
  }
}

function renderCatalog(items) {
  const catalogGrid = document.getElementById("catalog-grid");
  if (!catalogGrid) return;

  if (items.length === 0) {
    catalogGrid.innerHTML = `
      <div class="card" style="grid-column: 1 / -1; text-align: center; padding: 2rem;">
        <p class="plain">No releases matched your search query.</p>
      </div>`;
    return;
  }

  catalogGrid.innerHTML = items
    .map(item => `
      <article class="card release-card" id="release-${item.slug}">
        <div class="card-cover-wrapper">
          <img class="card-cover" src="${escapeHtml(item.coverUrl)}" alt="${escapeHtml(item.title)}" loading="lazy" onerror="this.src='/assets/placeholder-cover.jpg';" />
          ${item.hasAudio ? `
            <button class="play-btn" onclick="toggleAudio(this, '${escapeHtml(item.audioUrl)}')">
              ▶
            </button>` : ''}
        </div>
        <div class="card-body">
          <h3 class="card-title">${escapeHtml(item.title)}</h3>
          <p class="card-artist">jinx3 · ${escapeHtml(item.producer)}</p>
          
          <div class="card-actions">
            <a class="btn primary btn-sm" href="${escapeHtml(item.hyperfollowUrl)}" target="_blank" rel="noopener noreferrer">
              HyperFollow
            </a>
            
            <!-- Shopify Buy Button Container Placeholder -->
            <div class="shopify-buy-container" data-product-id="${escapeHtml(item.shopifyProductId || '')}" data-release-id="${escapeHtml(item.slug)}">
              ${item.shopifyProductId ? `
                <button class="btn ghost btn-sm shopify-buy-btn" onclick="initShopifyCheckout('${escapeHtml(item.shopifyProductId)}')">Buy WAV</button>
              ` : `
                <a class="btn ghost btn-sm" href="/#contact" title="Direct digital purchase available via email">Buy Pack</a>
              `}
            </div>
          </div>
        </div>
      </article>
    `)
    .join("");
}

function toggleAudio(btn, audioUrl) {
  if (!audioUrl) return;

  if (activeAudio && activeAudio.src.endsWith(audioUrl)) {
    if (activeAudio.paused) {
      activeAudio.play();
      btn.innerHTML = "❚❚";
      btn.classList.add("playing");
    } else {
      activeAudio.pause();
      btn.innerHTML = "▶";
      btn.classList.remove("playing");
    }
    return;
  }

  if (activeAudio) {
    activeAudio.pause();
    if (activeAudioBtn) {
      activeAudioBtn.innerHTML = "▶";
      activeAudioBtn.classList.remove("playing");
    }
  }

  activeAudio = new Audio(audioUrl);
  activeAudioBtn = btn;
  activeAudio.play();
  btn.innerHTML = "❚❚";
  btn.classList.add("playing");

  activeAudio.onended = () => {
    btn.innerHTML = "▶";
    btn.classList.remove("playing");
    activeAudio = null;
    activeAudioBtn = null;
  };
}

function setupSearch() {
  const searchInput = document.getElementById("catalog-search");
  if (!searchInput) return;

  searchInput.addEventListener("input", (e) => {
    const query = e.target.value.toLowerCase().trim();
    if (!query) {
      renderCatalog(catalogData);
      return;
    }

    const filtered = catalogData.filter(item => 
      item.title.toLowerCase().includes(query) ||
      item.slug.toLowerCase().includes(query)
    );
    renderCatalog(filtered);
  });
}

async function loadServices() {
  const root = document.getElementById("service-cards");
  if (!root) return;
  try {
    const res = await fetch("services.json", { cache: "no-store" });
    const items = await res.json();
    root.innerHTML = items
      .map(
        (s) => `
      <article class="card" id="svc-${s.id}">
        <h3>${escapeHtml(s.title)}</h3>
        <p>${escapeHtml(s.blurb)}</p>
        <div class="price">${escapeHtml(s.price)}</div>
        <ul>${(s.bullets || []).map((b) => `<li>${escapeHtml(b)}</li>`).join("")}</ul>
      </article>`
      )
      .join("");
  } catch (e) {
    root.innerHTML = `<p class="small">Could not load services.json (${e.message})</p>`;
  }
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

document.addEventListener("DOMContentLoaded", () => {
  loadCatalog();
  loadServices();
});
