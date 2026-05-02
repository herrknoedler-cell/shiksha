/**
 * SHIKSHA · Avatar-Engine
 * Wiederverwendbare SVG-Komponente: Initial-Buchstabe + Tortenstücke pro Bereich.
 *
 * Nutzung:
 *   <div data-shiksha-avatar
 *        data-name="Flora"
 *        data-slices='[{"area":"vormittag","color":"#ffd93d","status":"present"},...]'
 *        data-size="60"></div>
 *   <script src="/shiksha-avatar.js"></script>
 *
 * Oder programmatisch:
 *   ShikshaAvatar.render(element, { name, slices, size, status, group, ringColor });
 */
(function () {
  const NS = "http://www.w3.org/2000/svg";

  function _polarToCart(cx, cy, r, angleDeg) {
    const rad = (angleDeg - 90) * Math.PI / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  function _slicePath(cx, cy, r, startDeg, endDeg) {
    const start = _polarToCart(cx, cy, r, endDeg);
    const end = _polarToCart(cx, cy, r, startDeg);
    const largeArc = (endDeg - startDeg) > 180 ? 1 : 0;
    return [
      "M", cx, cy,
      "L", start.x, start.y,
      "A", r, r, 0, largeArc, 0, end.x, end.y,
      "Z",
    ].join(" ");
  }

  function _initialFromName(name) {
    if (!name) return "?";
    const parts = name.trim().split(/\s+/);
    return (parts[0][0] || "?").toUpperCase();
  }

  function render(el, opts) {
    const name = opts.name || el.dataset.name || "";
    const slices = opts.slices || JSON.parse(el.dataset.slices || "[]");
    const size = opts.size || parseInt(el.dataset.size || "60");
    const ringColor = opts.ringColor || el.dataset.ringColor || null; // Gruppen-Farbe
    const isAbsent = opts.absent || el.dataset.absent === "true";

    const cx = size / 2;
    const cy = size / 2;
    const outerR = size / 2 - 1;
    const innerR = size / 2 - 4; // Platz für Außenring
    const labelR = innerR * 0.55; // Innerer Bereich für Buchstabe

    // SVG bauen
    el.innerHTML = "";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
    svg.setAttribute("width", size);
    svg.setAttribute("height", size);
    svg.style.cssText = "display:block;";

    // Außenring (Gruppen-Farbe)
    if (ringColor) {
      const ring = document.createElementNS(NS, "circle");
      ring.setAttribute("cx", cx);
      ring.setAttribute("cy", cy);
      ring.setAttribute("r", outerR);
      ring.setAttribute("fill", ringColor);
      svg.appendChild(ring);
    }

    // Hintergrund-Kreis (innen, hell)
    const bg = document.createElementNS(NS, "circle");
    bg.setAttribute("cx", cx);
    bg.setAttribute("cy", cy);
    bg.setAttribute("r", innerR);
    bg.setAttribute("fill", isAbsent ? "#e0d5c0" : "#f9f4ec");
    svg.appendChild(bg);

    // Tortenstücke
    if (slices && slices.length > 0 && !isAbsent) {
      const totalDuration = slices.reduce((sum, s) => {
        const dur = s.duration || 1;
        return sum + dur;
      }, 0);
      let currentDeg = 0;
      slices.forEach(s => {
        const dur = s.duration || 1;
        const sliceDeg = (dur / totalDuration) * 360;
        const path = document.createElementNS(NS, "path");
        path.setAttribute("d", _slicePath(cx, cy, innerR, currentDeg, currentDeg + sliceDeg));
        path.setAttribute("fill", s.color || "#888");
        path.setAttribute("opacity", s.status === "absent" || s.status === "sick" ? "0.3" : "0.85");
        if (s.title) {
          const t = document.createElementNS(NS, "title");
          t.textContent = s.title;
          path.appendChild(t);
        }
        svg.appendChild(path);
        currentDeg += sliceDeg;
      });
    }

    // Mittel-Kreis (für Buchstaben-Lesbarkeit)
    const center = document.createElementNS(NS, "circle");
    center.setAttribute("cx", cx);
    center.setAttribute("cy", cy);
    center.setAttribute("r", labelR);
    center.setAttribute("fill", "#fff");
    svg.appendChild(center);

    // Initial-Buchstabe
    const text = document.createElementNS(NS, "text");
    text.setAttribute("x", cx);
    text.setAttribute("y", cy + size * 0.10);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("font-family", "-apple-system,sans-serif");
    text.setAttribute("font-weight", "700");
    text.setAttribute("font-size", size * 0.4);
    text.setAttribute("fill", "#2a2530");
    text.textContent = _initialFromName(name);
    svg.appendChild(text);

    // Status-Indikator (kleiner Punkt unten rechts wenn abwesend/krank)
    if (isAbsent || (slices.length && slices.every(s => s.status !== "present"))) {
      const dot = document.createElementNS(NS, "circle");
      dot.setAttribute("cx", size - size * 0.15);
      dot.setAttribute("cy", size - size * 0.15);
      dot.setAttribute("r", size * 0.12);
      const dotColor = slices[0]?.status === "sick" ? "#ff4d8d" : "#9a8e9e";
      dot.setAttribute("fill", dotColor);
      dot.setAttribute("stroke", "#fff");
      dot.setAttribute("stroke-width", "2");
      svg.appendChild(dot);
    }

    el.appendChild(svg);
  }

  // Auto-Initialisierung aller [data-shiksha-avatar] Elemente
  function autoInit(root) {
    (root || document).querySelectorAll("[data-shiksha-avatar]").forEach(el => {
      if (!el.dataset.rendered) {
        render(el, {});
        el.dataset.rendered = "1";
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => autoInit());
  } else {
    autoInit();
  }

  window.ShikshaAvatar = { render, autoInit };
})();
