/**
 * SHIKSHA · Card-Library
 * 8 Card-Typen, jeweils mit:
 *   - render(node, config) → DOM einfügen
 *   - refresh(node) → Daten neu ziehen (für Live-Polling)
 *   - meta: name, icon, defaultSize {w,h}, accent, description
 *
 * Verwendung:
 *   ShikshaCards.render(domNode, { type: "anwesenheit-mini", config: {} });
 *   ShikshaCards.refresh(domNode);
 *
 * API-Calls gehen an /kita/dashboard/card/<endpoint>.
 */

(function () {
  const API = "/kita/dashboard/card";
  const FETCH_OPTS = { headers: { "X-Org-Slug": "kita_pilot" } };

  function _esc(s) {
    return s == null ? "" : String(s).replace(/[&<>"']/g,
      c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
  }

  function _initial(name) {
    if (!name) return "?";
    return name.trim().split(/\s+/)[0][0]?.toUpperCase() || "?";
  }

  function _fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const today = new Date(); today.setHours(0,0,0,0);
    const tomorrow = new Date(today); tomorrow.setDate(today.getDate()+1);
    if (d.toDateString() === today.toDateString()) return "Heute";
    if (d.toDateString() === tomorrow.toDateString()) return "Morgen";
    return d.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" });
  }

  function _fmtTime(t) {
    if (!t) return "";
    return t.slice(0,5);
  }

  // ============================================================
  // CARD-DEFINITIONEN
  // ============================================================
  const CARDS = {
    "shiksha-greeting": {
      name: "SHIKSHA-Begrüßung",
      icon: "☀️",
      description: "Persönliche Hero-Card mit 5 Schichten",
      defaultSize: { w: 12, h: 4 },
      accent: null,                    // eigener Akzent — kein Top-Strich
      title: null,                     // eigener Header
      pollInterval: 5 * 60 * 1000,     // alle 5 Minuten neu (Tageszeit-Wechsel)
      render: async (node, config = {}) => {
        const role = config.role || "traegerin";
        const userName = config.user_name || localStorage.getItem("shiksha.user_name") || "";
        const url = `${API}/greeting?role=${encodeURIComponent(role)}&user=${encodeURIComponent(userName)}`;
        let d = null;
        try {
          const r = await fetch(url, FETCH_OPTS);
          d = await r.json();
        } catch (e) {
          node.innerHTML = `<div class="empty"><div class="em">☀️</div><div class="lbl">Schön, dass Du da bist.</div></div>`;
          return;
        }

        // Zeit-bezogenen Akzent setzen
        const card = node.closest(".card");
        if (card) {
          const h = new Date().getHours();
          card.dataset.daypart =
            h < 11 ? "morning" :
            h < 14 ? "midday" :
            h < 18 ? "afternoon" :
            h < 22 ? "evening" : "night";
        }

        const greeting = _esc(d.greeting || "Hallo");
        const mood = _esc(d.mood || "");
        const knowledge = d.knowledge;
        const theme = d.weekly_theme;
        const insight = d.insight;

        const knowledgeHtml = knowledge ? `
          <div class="g-row knowledge">
            <span class="g-icon">💭</span>
            <div class="g-content">
              <div class="g-row-head">Wusstest Du schon?</div>
              <div class="g-row-title">${_esc(knowledge.title)}</div>
              <div class="g-row-body">${_esc(knowledge.body)}</div>
            </div>
          </div>` : "";

        const themeHtml = theme && theme.theme ? `
          <div class="g-row theme">
            <span class="g-icon">🎯</span>
            <div class="g-content">
              <div class="g-row-head">Diese Woche</div>
              <div class="g-row-title">${_esc(theme.theme)}</div>
              <div class="g-row-body">
                ${theme.set_by ? 'gesetzt von ' + _esc(theme.set_by) : ''}
                ${theme.days_left ? ' · noch ' + theme.days_left + ' Tag' + (theme.days_left !== 1 ? 'e' : '') : ''}
              </div>
            </div>
          </div>` : "";

        const insightHtml = insight ? `
          <div class="g-row insight g-insight-${_esc(insight.severity || 'info')}">
            <span class="g-icon">${_esc(insight.icon || '✨')}</span>
            <div class="g-content">
              <div class="g-row-head">SHIKSHA bemerkt</div>
              <div class="g-row-title">${_esc(insight.title)}</div>
              <div class="g-row-body">${_esc(insight.body || '')}</div>
              ${insight.action_label ? `<div class="g-actions">
                <a class="g-action-primary" href="${_esc(insight.action_url || '#')}">${_esc(insight.action_label)} →</a>
                <button class="g-action-secondary" data-dismiss="${insight.id}">Nicht jetzt</button>
              </div>` : ''}
            </div>
          </div>` : "";

        node.innerHTML = `
          <div class="g-hero">
            <div class="g-hero-text">
              <div class="g-greeting">${greeting}</div>
              ${mood ? `<div class="g-mood">${mood}</div>` : ""}
            </div>
            <div class="g-tip">${_esc(d.tip || "")}</div>
          </div>
          <div class="g-rows">
            ${knowledgeHtml}
            ${themeHtml}
            ${insightHtml}
          </div>
        `;

        // Dismiss-Click
        node.querySelectorAll("[data-dismiss]").forEach(btn => {
          btn.addEventListener("click", async (e) => {
            e.preventDefault();
            const id = btn.dataset.dismiss;
            try {
              await fetch(`/kita/dashboard/insights/${id}/dismiss`, {
                method: "POST", headers: FETCH_OPTS.headers,
              });
              btn.closest(".g-row.insight")?.remove();
            } catch {}
          });
        });
      },
    },
    "anwesenheit-mini": {
      name: "Anwesenheit (Mini)",
      icon: "✓",
      description: "Wer ist heute da",
      defaultSize: { w: 3, h: 2 },
      accent: "pink",
      title: "Anwesend heute",
      render: async (node) => {
        const r = await fetch(`${API}/anwesenheit-summary`, FETCH_OPTS);
        const d = await r.json();
        const k = d.kids || { present: 0, total: 0 };
        const s = d.staff || { present: 0, total: 0 };
        const ratio = k.total ? k.present / k.total : 0;
        const cls = ratio >= 0.8 ? "ok" : (ratio >= 0.5 ? "warn" : "alert");
        node.innerHTML = `
          <div class="num">${k.present}<span class="total"> / ${k.total}</span></div>
          <span class="delta ${cls}">${Math.round(ratio*100)}% Kinder</span>
          <div class="sub">Pädagog:innen · ${s.present}/${s.total}</div>
        `;
      },
    },

    "stprozent-mini": {
      name: "ST% (Mini)",
      icon: "📊",
      description: "Stellenprozent-Erfüllung",
      defaultSize: { w: 3, h: 2 },
      accent: "purple",
      title: "Stellenprozent",
      render: async (node) => {
        const r = await fetch(`${API}/stprozent-mini`, FETCH_OPTS);
        const d = await r.json();
        if (d.actual == null) {
          node.innerHTML = `<div class="empty"><div class="em">📊</div><div class="lbl">Noch keine ST%-Berechnung</div></div>`;
          return;
        }
        const cls = d.ratio >= 1 ? "ok" : (d.ratio >= 0.9 ? "warn" : "alert");
        node.innerHTML = `
          <div class="num">${d.actual}<span class="total">%</span></div>
          <span class="delta ${cls}">Soll · ${d.required}%</span>
          <div class="sub">Stand · ${d.date ? new Date(d.date).toLocaleDateString("de-DE") : "—"}</div>
        `;
      },
    },

    "compliance-mini": {
      name: "Compliance (Mini)",
      icon: "🛡",
      description: "Audit-Ampel",
      defaultSize: { w: 3, h: 2 },
      accent: "turquoise",
      title: "Compliance",
      render: async (node) => {
        const r = await fetch(`${API}/compliance-status`, FETCH_OPTS);
        const d = await r.json();
        const f = d.details?.audit?.findings ?? "—";
        const cls = d.audit === "ok" ? "ok" : (d.audit === "warn" ? "warn" : "alert");
        node.innerHTML = `
          <div class="num">${f}<span class="total"> Findings</span></div>
          <span class="delta ${cls}">${d.audit === "ok" ? "Alles grün" : d.audit === "warn" ? "Aufmerksam" : "Handlungsbedarf"}</span>
          <div class="sub">Letzter Audit-Run</div>
        `;
      },
    },

    "anwesenheit-live": {
      name: "Anwesenheit Live",
      icon: "👥",
      description: "Avatar-Grid pro Gruppe",
      defaultSize: { w: 6, h: 4 },
      accent: "pink",
      title: "Wer ist gerade da",
      pollInterval: 15000,
      render: async (node) => {
        try {
          const r = await fetch("/kita/anwesenheit/today", FETCH_OPTS);
          if (!r.ok) throw new Error();
          const data = await r.json();
          if (!data.sections || !data.sections.length) {
            node.innerHTML = `<div class="empty"><div class="em">👥</div><div class="lbl">Keine Sektionen heute</div></div>`;
            return;
          }
          const html = data.sections.map(sec => {
            const kids = (sec.children || []).map(p => {
              const present = p.slices?.some(s => s.status === "present");
              return `<div class="live-avatar ${present ? 'present' : 'absent'}">
                <div class="circle">${_esc(_initial(p.name))}</div>
                <div class="lbl">${_esc(p.name.split(' ')[0])}</div>
              </div>`;
            }).join("");
            return `
              <div class="live-section-title">${_esc(sec.group_name)} · ${sec.counts?.kids_present || 0}/${sec.counts?.kids_total || 0}</div>
              <div class="avatar-row">${kids}</div>
            `;
          }).join("");
          node.innerHTML = html;
        } catch (e) {
          node.innerHTML = `<div class="empty"><div class="em">👥</div><div class="lbl">Live-Daten nicht verfügbar</div></div>`;
        }
      },
    },

    "events-upcoming": {
      name: "Termine kommend",
      icon: "📅",
      description: "Nächste 14 Tage",
      defaultSize: { w: 6, h: 4 },
      accent: "purple",
      title: "Anstehende Termine",
      render: async (node, config = {}, size = {w:6, h:4}) => {
        const maxItems = Math.max(2, (size.h - 1) * 2);  // h=2 → 2, h=4 → 6, h=6 → 10
        const days = size.h >= 6 ? 30 : 14;
        const r = await fetch(`${API}/upcoming-events?days=${days}`, FETCH_OPTS);
        const d = await r.json();
        if (!d.events || !d.events.length) {
          node.innerHTML = `<div class="empty"><div class="em">📅</div><div class="lbl">Keine Termine in ${days} Tagen</div></div>`;
          return;
        }
        const items = d.events.slice(0, maxItems);
        const showLocation = size.w >= 5;
        node.innerHTML = `<ul class="event-list">${items.map(e => `
          <li class="event-row">
            <div class="event-bar" style="--ev-color:${_esc(e.color || '#888')}"></div>
            <div class="event-when">${_esc(_fmtDate(e.start_date))}${e.start_time ? '<br><span style="font-weight:500;color:var(--ink-3)">' + _esc(_fmtTime(e.start_time)) + '</span>' : ''}</div>
            <div class="event-text">
              <div class="t1">${_esc(e.title)}</div>
              <div class="t2">${_esc(e.event_type || '')}${showLocation && e.location ? ' · ' + _esc(e.location) : ''}</div>
            </div>
          </li>
        `).join("")}${d.events.length > maxItems ? `<li style="text-align:center;color:var(--ink-3);font-size:11px;padding:6px;">+${d.events.length - maxItems} weitere</li>` : ''}</ul>`;
      },
    },

    "birthday-hero": {
      name: "Geburtstage",
      icon: "🎂",
      description: "Diese Woche / heute",
      defaultSize: { w: 12, h: 3 },
      accent: "yellow",
      title: "Geburtstage diese Woche",
      render: async (node) => {
        const r = await fetch(`${API}/birthdays-week`, FETCH_OPTS);
        const d = await r.json();
        const today = d.birthdays?.find(b => b.is_today);
        const others = d.birthdays?.filter(b => !b.is_today) || [];
        if (!d.birthdays || !d.birthdays.length) {
          node.innerHTML = `
            <div class="head-row">
              <div class="ico">🌿</div>
              <div class="head-text"><div class="h">Keine Geburtstage</div><div class="s">Diese Woche herrscht Ruhe</div></div>
            </div>`;
          return;
        }
        let head;
        if (today) {
          head = `
            <div class="head-row">
              <div class="ico">🎂</div>
              <div class="head-text">
                <div class="h">Heute · ${_esc(today.name)} wird ${today.age_turning}</div>
                <div class="s">${others.length ? '+ ' + others.length + ' weitere diese Woche' : 'Glückwunsch! 🎉'}</div>
              </div>
            </div>`;
        } else {
          const next = d.birthdays[0];
          head = `
            <div class="head-row">
              <div class="ico">🎂</div>
              <div class="head-text">
                <div class="h">${d.birthdays.length} Geburtstag${d.birthdays.length > 1 ? 'e' : ''} diese Woche</div>
                <div class="s">Nächster: ${_esc(next.name)} am ${new Date(next.date).toLocaleDateString("de-DE", {weekday:"long", day:"2-digit", month:"long"})}</div>
              </div>
            </div>`;
        }
        const list = d.birthdays.map(b => `
          <div class="bday-row${b.is_today ? ' today' : ''}">
            <span class="when">${_esc(_fmtDate(b.date))}</span>
            <span class="name">${_esc(b.name)}</span>
            <span class="age">wird ${b.age_turning}</span>
            <span style="color:var(--ink-3);font-size:11px;">· ${b.type === 'staff' ? 'Pädagog:in' : 'Kind'}</span>
          </div>`).join("");
        node.innerHTML = head + `<div class="bday-list">${list}</div>`;
      },
    },

    "messages-recent": {
      name: "Mitteilungen",
      icon: "✉",
      description: "Letzte 5",
      defaultSize: { w: 6, h: 4 },
      accent: "orange",
      title: "Letzte Mitteilungen",
      render: async (node, config = {}, size = {w:6, h:4}) => {
        const limit = Math.max(2, (size.h - 1) * 2);
        const showBody = size.h >= 4;
        const r = await fetch(`${API}/messages-recent?limit=${limit}`, FETCH_OPTS);
        const d = await r.json();
        if (!d.messages || !d.messages.length) {
          node.innerHTML = `<div class="empty"><div class="em">✉</div><div class="lbl">Noch keine Mitteilungen</div></div>`;
          return;
        }
        node.innerHTML = d.messages.slice(0, limit).map(m => `
          <div class="msg-row">
            <div class="meta">
              <span class="audience">${_esc(m.audience || 'all')}</span>
              <span>${m.created_at ? new Date(m.created_at).toLocaleString("de-DE", {day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}) : ''}</span>
            </div>
            <div class="title">${_esc(m.title || '(ohne Titel)')}</div>
            ${showBody ? `<div class="body">${_esc(m.body || '')}</div>` : ''}
          </div>`).join("");
      },
    },

    "compliance-status": {
      name: "Compliance-Cockpit",
      icon: "🛡",
      description: "Vollständiger Status",
      defaultSize: { w: 6, h: 3 },
      accent: "green",
      title: "Compliance-Status",
      render: async (node) => {
        const r = await fetch(`${API}/compliance-status`, FETCH_OPTS);
        const d = await r.json();
        const items = [
          { key: "st_prozent", icon: "📊", title: "Stellenprozent (KKG)", sub: d.details?.st_prozent ? `${d.details.st_prozent.actual}% von ${d.details.st_prozent.required}%` : "—" },
          { key: "vbz",        icon: "⏰", title: "VB-Zeit", sub: "Vor-/Nachbereitung" },
          { key: "audit",      icon: "🛡", title: "Audit", sub: d.details?.audit ? `${d.details.audit.findings} Findings` : "Keine Daten" },
        ];
        node.innerHTML = items.map(i => `
          <div class="compliance-row">
            <div class="l">
              <div class="ico">${i.icon}</div>
              <div>
                <div class="t">${_esc(i.title)}</div>
                <div class="s">${_esc(i.sub)}</div>
              </div>
            </div>
            <span class="status-dot ${d[i.key] || 'unknown'}"></span>
          </div>`).join("");
      },
    },

    "action-round": {
      name: "Schnell-Button",
      icon: "⚡",
      description: "Runder Action-Button",
      defaultSize: { w: 2, h: 2 },   // 1:1 Quadrat
      noResize: true,                 // bleibt fix in der Größe
      accent: "pink",
      title: null,                 // Action-Round hat keinen Titel oben
      isRound: true,
      render: async (node, config = {}) => {
        const { label = "Aktion", icon = "⚡", url = "#" } = config;
        const wrap = node.closest(".card");
        if (wrap) wrap.style.cursor = "pointer";
        node.parentElement.classList.add("card-action-round");
        node.innerHTML = `
          <div class="ico">${_esc(icon)}</div>
          <div class="lbl">${_esc(label)}</div>
        `;
        if (url) {
          const card = node.closest(".card");
          if (card) {
            card.addEventListener("click", () => { window.location.href = url; });
          }
        }
      },
    },
  };

  // ============================================================
  // PUBLIC API
  // ============================================================
  function buildCard(item) {
    // item = { id, x, y, w, h, type, config }
    const def = CARDS[item.type];
    if (!def) return null;
    const card = document.createElement("div");
    card.className = "card";
    if (def.isRound) card.classList.add("card-action-round");
    card.classList.add(`card-${item.type}`);
    if (def.accent) card.dataset.accent = def.accent;
    // Größe für Detail-Stufen merken
    card._size = { w: item.w, h: item.h };
    card._type = item.type;
    card._config = item.config || {};
    if (def.title) {
      card.innerHTML = `
        <div class="card-head">
          <div class="card-title">${_esc(def.title)}</div>
          <button class="card-menu" data-action="menu" title="Optionen">⋯</button>
        </div>
        <div class="card-body" data-card-body></div>
      `;
    } else {
      card.innerHTML = `<div class="card-body" data-card-body></div>`;
    }
    const body = card.querySelector("[data-card-body]");
    def.render(body, card._config, card._size).catch(e => {
      body.innerHTML = `<div class="empty"><div class="em">⚠</div><div class="lbl">Fehler beim Laden</div></div>`;
    });
    // Polling falls vorgesehen
    if (def.pollInterval) {
      const intervalId = setInterval(() => {
        if (!card.isConnected) { clearInterval(intervalId); return; }
        def.render(body, card._config, card._size).catch(() => {});
      }, def.pollInterval);
      card._pollInterval = intervalId;
    }
    return card;
  }

  function refreshCard(card, newSize) {
    const def = CARDS[card._type];
    if (!def) return;
    if (newSize) card._size = newSize;
    const body = card.querySelector("[data-card-body]");
    if (body) def.render(body, card._config || {}, card._size || {w:6,h:4}).catch(() => {});
  }

  function listCards() {
    return Object.entries(CARDS).map(([key, def]) => ({
      key, name: def.name, icon: def.icon, description: def.description,
      defaultSize: def.defaultSize, accent: def.accent,
    }));
  }

  window.ShikshaCards = { buildCard, refreshCard, listCards, definitions: CARDS };
})();
