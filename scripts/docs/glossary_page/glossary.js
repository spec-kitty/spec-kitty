// Behaviour for the /glossary page (templates/glossary.html).
// Same-origin script: the dashboard CSP (csp.py) sets `script-src 'self'`,
// which blocks the inline <script> block this file was extracted from, so
// search / filter / alpha-nav interactivity lives here.

let TERMS = [];
let VALIDATION_ERRORS = [];

// ── State ─────────────────────────────────────────────────
let filter = 'all';
let query  = '';

// ── Fetch & bootstrap ─────────────────────────────────────
async function loadTerms() {
  try {
    const resp = await fetch('/api/glossary-terms');
    if (!resp.ok) throw new Error('fetch failed');
    TERMS = await resp.json();
  } catch (e) {
    console.warn('glossary: could not load terms', e);
    TERMS = [];
  }
  try {
    const resp = await fetch('/api/glossary-health');
    if (!resp.ok) throw new Error('health fetch failed');
    const health = await resp.json();
    VALIDATION_ERRORS = Array.isArray(health.validation_errors) ? health.validation_errors : [];
  } catch (e) {
    console.warn('glossary: could not load health', e);
    VALIDATION_ERRORS = [];
  }
  renderValidationBanner();
  updateStats();
  buildAlphaNav();
  render();
}

function renderValidationBanner() {
  const banner = document.getElementById('validation-banner');
  if (!banner) return;
  if (!VALIDATION_ERRORS.length) {
    banner.classList.add('hidden');
    banner.innerHTML = '';
    return;
  }
  const first = VALIDATION_ERRORS[0] || {};
  const count = VALIDATION_ERRORS.length;
  const file = first.file ? String(first.file).split('/').pop() : 'seed file';
  const where = first.term_index === null || first.term_index === undefined ? 'file' : `term ${first.term_index}`;
  const field = first.field ? ` · ${first.field}` : '';
  const more = count > 1 ? ` · ${count - 1} more` : '';
  banner.classList.remove('hidden');
  banner.innerHTML = `
    <strong>Glossary validation warning</strong>
    <span>${count} validation ${count === 1 ? 'error' : 'errors'}; showing recovered terms only.</span>
    <code>${esc(file)} · ${esc(where)}${esc(field)}${esc(more)}</code>
  `;
}

function updateStats() {
  const total  = TERMS.length;
  const active = TERMS.filter(t => t.status === 'active').length;
  const draft  = TERMS.filter(t => t.status === 'draft').length;
  const depr   = TERMS.filter(t => t.status === 'deprecated').length;
  document.getElementById('header-stats').innerHTML = [
    `<span class="stat-pill total">📚 ${total} terms</span>`,
    `<span class="stat-pill active">✓ ${active} active</span>`,
    `<span class="stat-pill draft">◦ ${draft} draft</span>`,
    `<span class="stat-pill depr">~ ${depr} deprecated</span>`,
  ].join('');
}

// ── Build alphabet nav ─────────────────────────────────────
function buildAlphaNav() {

// ── Build alphabet nav ─────────────────────────────────────
  const lettersWithTerms = new Set(TERMS.map(t => t.surface[0].toUpperCase()));
  const alphaNav = document.getElementById('alpha-nav');
  alphaNav.innerHTML = '';
  'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').forEach(ch => {
    const btn = document.createElement('button');
    btn.className = 'alpha-btn' + (lettersWithTerms.has(ch) ? ' has-terms' : ' inactive');
    btn.textContent = ch;
    btn.setAttribute('aria-label', `Jump to ${ch}`);
    if (lettersWithTerms.has(ch)) {
      btn.onclick = () => {
        const sec = document.getElementById('sec-' + ch);
        if (sec) sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
      };
    }
    alphaNav.appendChild(btn);
  });
}

// ── Utilities ──────────────────────────────────────────────
function esc(s) {
  return s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
}

function highlight(text, q) {
  if (!q) return esc(text);
  const escaped = esc(text);
  if (!q) return escaped;
  const re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&') + ')', 'gi');
  return escaped.replaceAll(re, '<mark class="hl">$1</mark>');
}

function badgeClass(status) {
  return status === 'active' ? 'badge-active' : status === 'draft' ? 'badge-draft' : 'badge-deprecated';
}

function badgeLabel(status) {
  return status === 'active' ? 'active' : status === 'draft' ? 'draft' : 'deprecated';
}

// ── Render ─────────────────────────────────────────────────
function render() {
  const q = query.trim().toLowerCase();
  const main = document.getElementById('main');
  main.innerHTML = '';

  const filtered = TERMS.filter(t => {
    if (filter !== 'all' && t.status !== filter) return false;
    if (q) {
      return t.surface.toLowerCase().includes(q) || t.definition.toLowerCase().includes(q);
    }
    return true;
  });

  document.getElementById('result-count').textContent =
    filtered.length === TERMS.length ? `${TERMS.length} terms` : `${filtered.length} of ${TERMS.length}`;

  if (filtered.length === 0) {
    main.innerHTML = `<div class="empty"><div class="empty-icon">🔍</div><p>No terms match "<strong>${esc(query)}</strong>"</p></div>`;
    return;
  }

  // Group by first letter
  const groups = {};
  filtered.forEach(t => {
    const ch = t.surface[0].toUpperCase();
    (groups[ch] = groups[ch] || []).push(t);
  });

  Object.keys(groups).sort((a, b) => a.localeCompare(b)).forEach(ch => {
    const section = document.createElement('section');
    section.className = 'letter-section';
    section.id = 'sec-' + ch;

    section.innerHTML = `
      <div class="letter-heading">
        <div class="letter-char">${ch}</div>
        <div class="letter-rule"></div>
      </div>
      <div class="cards-grid" id="grid-${ch}"></div>
    `;
    main.appendChild(section);

    const grid = section.querySelector('.cards-grid');
    groups[ch].forEach(t => {
      const pct = Math.round(t.confidence * 100);
      const card = document.createElement('article');
      card.className = 'card';
      card.dataset.status = t.status;
      card.innerHTML = `
        <div class="card-head">
          <div class="card-surface">${highlight(t.surface, q)}</div>
          <span class="badge ${badgeClass(t.status)}">${badgeLabel(t.status)}</span>
        </div>
        <div class="card-def">${highlight(t.definition, q)}</div>
        <div class="card-foot">
          <div class="conf-bar" title="${pct}% confidence">
            <div class="conf-fill"></div>
          </div>
          <span class="conf-label">${pct}%</span>
        </div>
      `;
      card.querySelector('.conf-fill').style.width = pct + '%';
      grid.appendChild(card);
    });
  });
}

// ── Event wiring ───────────────────────────────────────────
document.getElementById('search').addEventListener('input', e => {
  query = e.target.value;
  render();
});

document.getElementById('filter-tabs').addEventListener('click', e => {
  const btn = e.target.closest('.tab');
  if (!btn) return;
  filter = btn.dataset.filter;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active-tab'));
  btn.classList.add('active-tab');
  render();
});

document.addEventListener('DOMContentLoaded', loadTerms);
