/* =========================================================================
   SHIKSHA UI v1.0.0 — JavaScript
   Spec: SHIKSHA_DESIGN_SYSTEM.md §6, §9
   Komponenten: Theming-Engine, Modal, Tabs, DayClock, Avatar, Toast.
   ES-Module — wird via <script type="module"> geladen.
   ========================================================================= */


/* =========================================================================
   1. THEMING-ENGINE
   Setzt data-time / data-season / data-context auf <body> basierend auf
   aktueller Zeit und Kontext-Setting. Aktualisiert sich alle 5 Minuten.
   ========================================================================= */

const SEASON_BY_MONTH = {
  // Monate sind 1-indexed
  1: 'winter',  2: 'winter',
  3: 'spring',  4: 'spring',  5: 'spring',
  6: 'summer',  7: 'summer',  8: 'summer',
  9: 'autumn', 10: 'autumn', 11: 'autumn',
  12: 'winter',
};

function _currentTimeSlot(hour) {
  if (hour >= 5  && hour <= 11) return 'morning';
  if (hour >= 12 && hour <= 16) return 'afternoon';
  if (hour >= 17 && hour <= 21) return 'evening';
  return 'night';
}

function _currentSeason(month) {
  return SEASON_BY_MONTH[month] || 'winter';
}

let _themingInterval = null;

export function applyTheming(opts = {}) {
  const { context = null, now = new Date() } = opts;
  const body = document.body;
  if (!body) return;

  body.dataset.time   = _currentTimeSlot(now.getHours());
  body.dataset.season = _currentSeason(now.getMonth() + 1);
  if (context) body.dataset.context = context;
}

export function setContext(context) {
  document.body.dataset.context = context;
}

export function startThemingClock(opts = {}) {
  applyTheming(opts);
  if (_themingInterval) clearInterval(_themingInterval);
  _themingInterval = setInterval(() => applyTheming({ context: document.body.dataset.context }), 5 * 60 * 1000);
}


/* =========================================================================
   2. MODAL
   Backdrop + Modal-Container, Open/Close mit Animation,
   Escape-Key + Backdrop-Click + Close-Button.
   ========================================================================= */

export function openModal(backdropEl) {
  if (!backdropEl) return;
  backdropEl.classList.add('is-open');
  document.body.style.overflow = 'hidden';

  // Escape-Key
  const onKeyDown = (e) => {
    if (e.key === 'Escape') closeModal(backdropEl);
  };
  backdropEl._shkKeyHandler = onKeyDown;
  document.addEventListener('keydown', onKeyDown);

  // Backdrop-Click
  const onBackdropClick = (e) => {
    if (e.target === backdropEl) closeModal(backdropEl);
  };
  backdropEl._shkBackdropHandler = onBackdropClick;
  backdropEl.addEventListener('click', onBackdropClick);

  // Schließen-Buttons im Modal
  backdropEl.querySelectorAll('[data-shk-modal-close]').forEach(btn => {
    btn.addEventListener('click', () => closeModal(backdropEl));
  });
}

export function closeModal(backdropEl) {
  if (!backdropEl) return;
  backdropEl.classList.remove('is-open');
  document.body.style.overflow = '';

  if (backdropEl._shkKeyHandler) {
    document.removeEventListener('keydown', backdropEl._shkKeyHandler);
    backdropEl._shkKeyHandler = null;
  }
  if (backdropEl._shkBackdropHandler) {
    backdropEl.removeEventListener('click', backdropEl._shkBackdropHandler);
    backdropEl._shkBackdropHandler = null;
  }
}

/**
 * Bindet einen Trigger-Button an ein Modal. Klick → open.
 *   bindModalTrigger(button, modalBackdrop)
 */
export function bindModalTrigger(triggerEl, backdropEl) {
  if (!triggerEl || !backdropEl) return;
  triggerEl.addEventListener('click', () => openModal(backdropEl));
}


/* =========================================================================
   3. TAB-SWITCH
   ========================================================================= */

/**
 * Bindet eine Tab-Leiste. Erwartet:
 *   container mit Elementen mit data-shk-tab="<key>"
 *   Panels mit data-shk-tab-panel="<key>"
 *
 *   bindTabs(container, { onSwitch: (key) => {...} })
 */
export function bindTabs(containerEl, opts = {}) {
  if (!containerEl) return;
  const tabs = containerEl.querySelectorAll('[data-shk-tab]');
  const panels = document.querySelectorAll('[data-shk-tab-panel]');

  function activate(key) {
    tabs.forEach(t => {
      t.classList.toggle('shk-tab--active', t.dataset.shkTab === key);
    });
    panels.forEach(p => {
      p.classList.toggle('shk-hidden', p.dataset.shkTabPanel !== key);
    });
    if (typeof opts.onSwitch === 'function') opts.onSwitch(key);
  }

  tabs.forEach(t => {
    t.addEventListener('click', () => activate(t.dataset.shkTab));
  });

  // Initial active
  const initialActive = containerEl.querySelector('[data-shk-tab].shk-tab--active');
  if (initialActive) {
    activate(initialActive.dataset.shkTab);
  } else if (tabs.length > 0) {
    activate(tabs[0].dataset.shkTab);
  }
}


/* =========================================================================
   4. TOAST
   ========================================================================= */

function _ensureToastStack() {
  let stack = document.querySelector('.shk-toast-stack');
  if (!stack) {
    stack = document.createElement('div');
    stack.className = 'shk-toast-stack';
    document.body.appendChild(stack);
  }
  return stack;
}

export function toast(message, opts = {}) {
  const { duration = 2500, type = 'default' } = opts;
  const stack = _ensureToastStack();
  const el = document.createElement('div');
  el.className = 'shk-toast';
  if (type !== 'default') el.classList.add(`shk-toast--${type}`);
  el.textContent = message;
  stack.appendChild(el);

  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity var(--shk-duration-medium) var(--shk-ease-out)';
    setTimeout(() => el.remove(), 400);
  }, duration);
}


/* =========================================================================
   5. AVATAR
   ========================================================================= */

/** Initialen aus einem Namen extrahieren. */
export function avatarInitials(name) {
  if (!name) return '';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Deterministische Pseudo-Hue aus Namen — gleiche Person, gleiche Farbe. */
function _nameHue(name) {
  if (!name) return 30;
  let h = 0;
  for (let i = 0; i < name.length; i++) {
    h = (h * 31 + name.charCodeAt(i)) & 0xffff;
  }
  return h % 360;
}

/**
 * Erzeugt einen <span class="shk-avatar">-Element mit Initialen + namensbasierter Farbe.
 *   const el = avatarElement('Mira Friedl', { size: 'large' });
 */
export function avatarElement(name, opts = {}) {
  const { size = null } = opts;
  const el = document.createElement('span');
  el.className = 'shk-avatar';
  if (size === 'small') el.classList.add('shk-avatar--small');
  if (size === 'large') el.classList.add('shk-avatar--large');
  el.textContent = avatarInitials(name);

  // Pastell-Hintergrund aus Namens-Hash, leicht warm getönt
  const hue = _nameHue(name);
  el.style.background = `hsl(${hue}, 55%, 65%)`;
  el.style.color = '#0e0d12';

  return el;
}


/* =========================================================================
   6. DAYCLOCK — Tages-Uhr in drei Modi
   Modi:
     'analog-12h'      Klassische Analoguhr (KITA-Default)
     'halfcircle-12h'  Halbkreis-Bogen, Tagesleiste
     'fullcircle-24h'  24h-Vollkreis, Mitternacht oben
   ========================================================================= */

const _SVG_NS = 'http://www.w3.org/2000/svg';

function _el(tag, attrs = {}, children = []) {
  const node = document.createElementNS(_SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    node.setAttribute(k, v);
  }
  for (const c of children) {
    if (typeof c === 'string') node.textContent = c;
    else if (c) node.appendChild(c);
  }
  return node;
}

/** Wandelt "HH:MM" in Stunden-als-Float um (z.B. "08:30" → 8.5). */
function _parseTime(str) {
  if (!str) return 0;
  const [h, m] = str.split(':').map(Number);
  return (h || 0) + (m || 0) / 60;
}

/** Konvertiert Stunde (0..24) zu Winkel in Radian.
 *  In allen Modi: 12 (analog) / 0 (fullcircle) oben (-90°), Uhrzeigersinn.
 *  - analog-12h: Stunde mod 12, voller Kreis = 12h
 *  - halfcircle-12h: Stunde in [startHour..endHour] mappen
 *  - fullcircle-24h: voller Kreis = 24h
 */
function _hourToAngle(hour, mode, opts = {}) {
  if (mode === 'analog-12h') {
    const h12 = ((hour % 12) + 12) % 12;
    return (h12 / 12) * 2 * Math.PI - Math.PI / 2;
  }
  if (mode === 'fullcircle-24h') {
    return (hour / 24) * 2 * Math.PI - Math.PI / 2;
  }
  if (mode === 'halfcircle-12h') {
    const start = opts.startHour ?? 6;
    const end   = opts.endHour   ?? 18;
    const frac = (hour - start) / (end - start);
    // Halbkreis von -180° (links) über -90° (oben) zu 0° (rechts)
    return Math.PI + frac * Math.PI;
  }
  return 0;
}

/** Erzeugt einen SVG-Path für einen Kreissektor (Pie-Slice).
 *  start/end: Winkel in Radian. */
function _arcPath(cx, cy, r, startAngle, endAngle) {
  const x1 = cx + r * Math.cos(startAngle);
  const y1 = cy + r * Math.sin(startAngle);
  const x2 = cx + r * Math.cos(endAngle);
  const y2 = cy + r * Math.sin(endAngle);
  const large = (endAngle - startAngle) > Math.PI ? 1 : 0;
  return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
}

/** Erzeugt einen Bogen (kein Pie) — nur für halfcircle-12h. */
function _bandPath(cx, cy, rOuter, rInner, startAngle, endAngle) {
  const x1o = cx + rOuter * Math.cos(startAngle);
  const y1o = cy + rOuter * Math.sin(startAngle);
  const x2o = cx + rOuter * Math.cos(endAngle);
  const y2o = cy + rOuter * Math.sin(endAngle);
  const x1i = cx + rInner * Math.cos(endAngle);
  const y1i = cy + rInner * Math.sin(endAngle);
  const x2i = cx + rInner * Math.cos(startAngle);
  const y2i = cy + rInner * Math.sin(startAngle);
  const large = (endAngle - startAngle) > Math.PI ? 1 : 0;
  return `M ${x1o} ${y1o}
          A ${rOuter} ${rOuter} 0 ${large} 1 ${x2o} ${y2o}
          L ${x1i} ${y1i}
          A ${rInner} ${rInner} 0 ${large} 0 ${x2i} ${y2i} Z`;
}

/** Render eine vollständige DayClock-SVG. */
export function renderDayClock(container, opts = {}) {
  const {
    mode = 'analog-12h',
    sectors = [],
    role = null,
    now = new Date(),
    startHour = 6,    // nur für halfcircle
    endHour   = 18,
    onSectorClick = null,
  } = opts;

  if (!container) return;
  container.innerHTML = '';

  const viewSize = mode === 'halfcircle-12h' ? { w: 360, h: 200 } : { w: 360, h: 360 };
  const cx = mode === 'halfcircle-12h' ? 180 : 180;
  const cy = mode === 'halfcircle-12h' ? 180 : 180;
  const r  = 150;
  const innerR = 90;

  const svg = _el('svg', {
    class: `shk-dayclock ${mode === 'halfcircle-12h' ? 'shk-dayclock--halfcircle' : ''}`.trim(),
    viewBox: `0 0 ${viewSize.w} ${viewSize.h}`,
    role: 'img',
    'aria-label': 'Tages-Uhr',
  });

  // ---- Face (Hintergrund) ----
  if (mode === 'halfcircle-12h') {
    // Halbkreis-Bogen unten oder oben? Wir wählen oben offen, Mitte unten
    const path = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy} Z`;
    svg.appendChild(_el('path', { class: 'shk-dayclock__face', d: path }));
  } else {
    svg.appendChild(_el('circle', {
      class: 'shk-dayclock__face',
      cx, cy, r,
    }));
  }

  // ---- Sektoren ----
  const filteredSectors = role
    ? sectors.filter(s => !s.visible_for || s.visible_for.includes(role))
    : sectors;

  filteredSectors.forEach((sector, idx) => {
    const startH = _parseTime(sector.start);
    const endH   = _parseTime(sector.end);
    if (endH <= startH) return; // keine umkreisenden Sektoren in v1

    const a1 = _hourToAngle(startH, mode, { startHour, endHour });
    const a2 = _hourToAngle(endH,   mode, { startHour, endHour });

    let d;
    if (mode === 'halfcircle-12h') {
      d = _bandPath(cx, cy, r, innerR, a1, a2);
    } else {
      d = _arcPath(cx, cy, r, a1, a2);
    }

    const path = _el('path', {
      class: 'shk-dayclock__sector',
      d,
      fill: sector.color || 'var(--shk-accent-warm)',
      'data-sector-id': sector.id || `sector-${idx}`,
    });

    if (typeof onSectorClick === 'function') {
      path.style.cursor = 'pointer';
      path.addEventListener('click', () => onSectorClick(sector));
    }

    // Label
    const midAngle = (a1 + a2) / 2;
    const labelRadius = mode === 'halfcircle-12h' ? (r + innerR) / 2 : r * 0.72;
    const labelX = cx + labelRadius * Math.cos(midAngle);
    const labelY = cy + labelRadius * Math.sin(midAngle);

    const label = _el('text', {
      class: 'shk-dayclock__sector-label',
      x: labelX,
      y: labelY,
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
    }, [sector.label || '']);

    svg.appendChild(path);
    svg.appendChild(label);
  });

  // ---- Stunden-Markierungen (nur analog-12h + fullcircle-24h) ----
  if (mode !== 'halfcircle-12h') {
    const hourCount = mode === 'fullcircle-24h' ? 24 : 12;
    for (let h = 0; h < hourCount; h++) {
      const a = _hourToAngle(h, mode);
      const x1 = cx + (r - 12) * Math.cos(a);
      const y1 = cy + (r - 12) * Math.sin(a);
      const x2 = cx + r * Math.cos(a);
      const y2 = cy + r * Math.sin(a);
      svg.appendChild(_el('line', {
        class: 'shk-dayclock__hour-mark',
        x1, y1, x2, y2,
      }));

      // Labels nur an Hauptpositionen
      const showLabel = (mode === 'analog-12h' && h % 3 === 0)
        || (mode === 'fullcircle-24h' && h % 6 === 0);
      if (showLabel) {
        const labelX = cx + (r - 28) * Math.cos(a);
        const labelY = cy + (r - 28) * Math.sin(a);
        const labelText = (mode === 'analog-12h' && h === 0) ? '12' : String(h);
        svg.appendChild(_el('text', {
          class: 'shk-dayclock__hour-label',
          x: labelX, y: labelY,
        }, [labelText]));
      }
    }
  }

  // ---- Zeiger / Now-Indikator ----
  const hour = now.getHours() + now.getMinutes() / 60;
  if (mode === 'analog-12h') {
    // Stunden- + Minutenzeiger
    const hourAngle = _hourToAngle(hour, mode);
    const minuteAngle = (now.getMinutes() / 60) * 2 * Math.PI - Math.PI / 2;

    svg.appendChild(_el('line', {
      class: 'shk-dayclock__hand shk-dayclock__hand--hour',
      x1: cx, y1: cy,
      x2: cx + (r * 0.55) * Math.cos(hourAngle),
      y2: cy + (r * 0.55) * Math.sin(hourAngle),
    }));
    svg.appendChild(_el('line', {
      class: 'shk-dayclock__hand shk-dayclock__hand--minute',
      x1: cx, y1: cy,
      x2: cx + (r * 0.80) * Math.cos(minuteAngle),
      y2: cy + (r * 0.80) * Math.sin(minuteAngle),
    }));
    svg.appendChild(_el('circle', {
      class: 'shk-dayclock__center',
      cx, cy, r: 5,
    }));
  } else if (mode === 'fullcircle-24h') {
    // Ein einziger Stundenzeiger (24h-Skala)
    const a = _hourToAngle(hour, mode);
    svg.appendChild(_el('line', {
      class: 'shk-dayclock__hand shk-dayclock__hand--hour',
      x1: cx, y1: cy,
      x2: cx + (r * 0.85) * Math.cos(a),
      y2: cy + (r * 0.85) * Math.sin(a),
    }));
    svg.appendChild(_el('circle', {
      class: 'shk-dayclock__center',
      cx, cy, r: 5,
    }));
  } else if (mode === 'halfcircle-12h') {
    // Punkt entlang des Bogens
    if (hour >= startHour && hour <= endHour) {
      const a = _hourToAngle(hour, mode, { startHour, endHour });
      const x = cx + ((r + innerR) / 2) * Math.cos(a);
      const y = cy + ((r + innerR) / 2) * Math.sin(a);
      svg.appendChild(_el('circle', {
        class: 'shk-dayclock__center',
        cx: x, cy: y, r: 6,
      }));
    }
  }

  container.appendChild(svg);
}

/**
 * Live-Modus: Renderer wird jede Minute neu aufgerufen, sodass die Zeiger
 * fortschreiten. Gibt eine Stop-Funktion zurück.
 *   const stop = renderDayClockLive(container, opts);
 *   stop();  // beendet den Live-Update
 */
export function renderDayClockLive(container, opts = {}) {
  renderDayClock(container, { ...opts, now: new Date() });
  const id = setInterval(() => {
    renderDayClock(container, { ...opts, now: new Date() });
  }, 60 * 1000);
  return () => clearInterval(id);
}


/* =========================================================================
   7. THEME-SWITCH  (Dark / Light, mit Persistenz + System-Preference)
   ========================================================================= */

const _THEME_KEY = 'shiksha-theme';

/** Liefert das aktuell aktive Theme: 'dark' | 'light'. */
export function getTheme() {
  const root = document.documentElement;
  const explicit = root.getAttribute('data-theme');
  if (explicit === 'dark' || explicit === 'light') return explicit;
  // Fallback auf System-Präferenz
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
    return 'light';
  }
  return 'dark';
}

/** Setzt das Theme explizit und persistiert es. */
export function setTheme(theme) {
  if (theme !== 'dark' && theme !== 'light') return;
  document.documentElement.setAttribute('data-theme', theme);
  try { localStorage.setItem(_THEME_KEY, theme); } catch (e) { /* ignore quota */ }
}

/** Schaltet zwischen Dark und Light um. */
export function toggleTheme() {
  setTheme(getTheme() === 'light' ? 'dark' : 'light');
}

/** Beim Page-Load: gespeicherte Wahl wiederherstellen. Optional. */
export function restoreTheme() {
  let saved = null;
  try { saved = localStorage.getItem(_THEME_KEY); } catch (e) {}
  if (saved === 'dark' || saved === 'light') {
    document.documentElement.setAttribute('data-theme', saved);
  }
  // sonst: kein Attribut → CSS prefers-color-scheme greift
}

/** Bindet einen Toggle-Button an die Theme-Umschaltung. */
export function bindThemeToggle(buttonEl, opts = {}) {
  if (!buttonEl) return;
  const { onChange = null } = opts;

  function updateLabel() {
    const t = getTheme();
    buttonEl.dataset.shkCurrentTheme = t;
    // Text zeigt das ZIEL des nächsten Klicks, nicht den aktuellen Stand.
    // Im Light-Mode → "Dunkel" (Klick führt dorthin), im Dark-Mode → "Hell".
    if (buttonEl.querySelector('[data-shk-theme-label]')) {
      buttonEl.querySelector('[data-shk-theme-label]').textContent =
        t === 'light' ? 'Dunkel' : 'Hell';
    }
  }

  buttonEl.addEventListener('click', () => {
    toggleTheme();
    updateLabel();
    if (typeof onChange === 'function') onChange(getTheme());
  });

  updateLabel();
}


/* =========================================================================
   8. INIT-HELPER  (optional, für Surfaces die alles in einem Aufruf wollen)
   ========================================================================= */

export function initShikshaUI(opts = {}) {
  const { context = null } = opts;

  // Theme zuerst wiederherstellen — vor allem anderen, damit kein FOUC
  restoreTheme();

  startThemingClock({ context });

  // Auto-bind aller Modal-Trigger im DOM:
  // <button data-shk-modal-trigger="modal-id">  →  <div id="modal-id" class="shk-modal-backdrop">
  document.querySelectorAll('[data-shk-modal-trigger]').forEach(trigger => {
    const targetId = trigger.dataset.shkModalTrigger;
    const backdrop = document.getElementById(targetId);
    if (backdrop) bindModalTrigger(trigger, backdrop);
  });

  // Auto-bind aller Tab-Container
  document.querySelectorAll('[data-shk-tabs]').forEach(container => {
    bindTabs(container);
  });

  // Auto-bind aller Theme-Toggle-Buttons
  document.querySelectorAll('[data-shk-theme-toggle]').forEach(btn => {
    bindThemeToggle(btn);
  });
}


/* =========================================================================
   9. DEFAULT-EXPORT — convenience namespace
   ========================================================================= */

export const ShikshaUI = {
  applyTheming,
  setContext,
  startThemingClock,
  openModal,
  closeModal,
  bindModalTrigger,
  bindTabs,
  toast,
  avatarInitials,
  avatarElement,
  renderDayClock,
  renderDayClockLive,
  getTheme,
  setTheme,
  toggleTheme,
  restoreTheme,
  bindThemeToggle,
  initShikshaUI,
  initHeimSlider,
};

export default ShikshaUI;


/* =========================================================================
   10. HEIM-SLIDER (v1.1.0, Heim-Layout-Spec §1.5)
   ========================================================================= */

/**
 * Initialisiert einen Heim-Slider mit Page-Indicator.
 *
 * Pages = direkte Kinder mit Klasse `.shk-heim-page`.
 * Indicator wird dynamisch erstellt + an document.body angehängt
 * (fixed-positioniert via CSS).
 *
 * Aktive Page wird per IntersectionObserver erkannt (threshold 0.5) —
 * funktioniert beim Swipe ohne extra Event-Listener.
 *
 * Tap auf einen Indicator-Dot scrollt sanft zur entsprechenden Page.
 */
export function initHeimSlider(container) {
  if (!container) return null;
  const pages = Array.from(container.querySelectorAll(':scope > .shk-heim-page'));
  if (pages.length === 0) return null;

  // Alte Indicator entfernen (bei Re-Init)
  document.querySelectorAll('.shk-heim-slider__indicator').forEach(el => el.remove());

  const indicator = document.createElement('div');
  indicator.className = 'shk-heim-slider__indicator';
  indicator.setAttribute('role', 'tablist');
  indicator.setAttribute('aria-label', 'Heim-Seiten');
  pages.forEach((page, i) => {
    const dot = document.createElement('button');
    dot.className = 'shk-heim-slider__dot';
    dot.type = 'button';
    dot.dataset.pageIndex = String(i);
    dot.dataset.active = String(i === 0);
    dot.setAttribute('role', 'tab');
    dot.setAttribute(
      'aria-label',
      page.getAttribute('aria-label') || `Seite ${i + 1}`,
    );
    dot.addEventListener('click', () => {
      pages[i].scrollIntoView({
        behavior: 'smooth',
        inline: 'start',
        block: 'nearest',
      });
    });
    indicator.appendChild(dot);
  });
  document.body.appendChild(indicator);

  const setActive = (idx) => {
    indicator.querySelectorAll('.shk-heim-slider__dot').forEach((dot, i) => {
      dot.dataset.active = String(i === idx);
    });
  };

  const observer = new IntersectionObserver((entries) => {
    let bestIdx = -1;
    let bestRatio = 0;
    entries.forEach((entry) => {
      if (entry.intersectionRatio > bestRatio) {
        bestRatio = entry.intersectionRatio;
        bestIdx = pages.indexOf(entry.target);
      }
    });
    if (bestIdx >= 0 && bestRatio >= 0.5) setActive(bestIdx);
  }, { root: container, threshold: [0.5, 0.75, 1.0] });

  pages.forEach(page => observer.observe(page));

  return {
    setActive,
    destroy: () => { observer.disconnect(); indicator.remove(); },
  };
}
