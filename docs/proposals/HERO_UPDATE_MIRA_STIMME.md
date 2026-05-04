# Hero-Update — Mira-Stimme auf shiksha.world

**Status:** Spec, Code-Umsetzung beim nächsten Polish-Sprint
**Cross-Reference:** `master_vision.md` Sektion 4.1
**Pre-Condition:** Mira-Zustimmung für Name + Zitat öffentlich (siehe Sektion 5)

---

## 1. Zielbild

Die Plattform-Site `shiksha.world` und die Edition-Sales-Pages bekommen eine **Pilot-Stimmen-Sektion** direkt unter dem Hero. Dort steht das Versprechen, formuliert von einer echten Trägerin. Damit ist die Marken-Vision nicht mehr Hoffnung, sondern bewiesen.

> ***"Ein Programm, was mir die ganze Zettelei und Denkerei abnimmt."***
> 
> — Mira F., KITA-Trägerin · Krummelus, Dornbirn

---

## 2. Aktueller Hero-Stand (shiksha.world)

```
[Hero-Video als BG, atmender Holi-Verlauf]

  Schönen Mittag · Samstag im Frühling      ← Greeting (dynamisch)

  Eine Plattform für KITAs, Campingplätze,    ← aktuelle Tagline
  Surfschulen — die mitlernt, atmet
  und sich nie wie Software anfühlt.

  [7 Tage probieren →]   [Editionen ansehen]
```

Die existierende Tagline ist gut — präzise, marken-konform, *"Lebendig, Lernend, Lieb"*. Sie soll **nicht ersetzt** werden, sondern durch eine Pilot-Stimme ergänzt werden.

---

## 3. Vorschlag — drei Varianten

### Variante A — Quote-Section direkt unter Hero (empfohlen)

Direkt nach dem Hero, vor der Editionen-Galerie, kommt eine **stille Sektion** nur mit dem Mira-Zitat:

```
[Hero — bleibt wie er ist]

         ↓ scroll

┌────────────────────────────────────────────┐
│                                            │
│                                            │
│                                            │
│      "Ein Programm, was mir die            │
│       ganze Zettelei und Denkerei          │
│       abnimmt."                            │
│                                            │
│       — Mira F.                            │
│         KITA-Trägerin · Krummelus           │
│         Dornbirn, Vorarlberg               │
│                                            │
│                                            │
│                                            │
└────────────────────────────────────────────┘

         ↓ scroll

[Editionen-Galerie]
```

**Vorteile:**
- Hero bleibt als Atmosphäre-Bühne unangetastet
- Mira-Stimme bekommt eigenen Raum, ohne sich zu drängeln
- Verbindet Marken-Vision (oben) mit konkreter Pilot-Realität (darunter)
- Apple-Style: viel Whitespace, ein Satz, ein Name, fertig

### Variante B — Inline im Hero

Die Tagline wird durch Mira-Quote ersetzt:

```
"Ein Programm, was mir die Zettelei und Denkerei abnimmt."
                                                — Mira F., Krummelus
```

**Nachteile:** Drängt sich auf, ersetzt eine bewusst formulierte Marken-Tagline mit einer einzelnen Stimme. Plus: Wer Mira nicht kennt, fragt sich *"wer ist das?"*.

→ **Nicht empfohlen.** Pilot-Stimmen brauchen Kontext.

### Variante C — Pilot-Stimmen-Karussell weit unten

Eine eigene Section "Was Pilot-Trägerinnen sagen" mit mehreren Quotes, sobald mehrere Piloten laufen.

**Heute:** zu früh (nur Mira existiert). Später (ab 3-5 Pilot-Stimmen): sinnvoll.

→ **Vertagen** auf 2-3 Monate, wenn Camping/Schule/Surf-Pilots zusätzliche Stimmen liefern.

---

## 4. Empfehlung

**Variante A jetzt, Variante C später.**

Heute Variante A mit nur Mira-Quote. In 3-6 Monaten, wenn weitere Piloten Stimmen beigetragen haben, evolvieren zu Variante C (mehrere Stimmen, Karussell oder Grid).

---

## 5. Pre-Condition — Mira-Zustimmung

Bevor Mira-Name öffentlich auf shiksha.world steht: **explizite Zustimmung einholen.** DSGVO-konforme Vorgehensweise:

```
Founder fragt Mira:

"Mira, ich würde gern Deinen Satz öffentlich zitieren —
'Ein Programm, was mir die Zettelei und Denkerei abnimmt.'
Mit Deinem Vornamen + Krummelus + Dornbirn.

Das wäre auf shiksha.world öffentlich sichtbar.

Magst Du das? Wenn nein: kein Drama, ich nehm einen
anderen Satz oder eine anonyme Form."
```

**Drei mögliche Zustimmungs-Stufen:**

| Stufe | Anzeige | Wann |
|---|---|---|
| **Volle Zustimmung** | "Mira F., KITA-Trägerin · Krummelus, Dornbirn" | nach explizitem Ja |
| **Teil-Zustimmung** | "Eine Trägerin · Krummelus, Dornbirn" (Vorname weg) | wenn sie's möchte |
| **Anonymisiert** | "Eine KITA-Trägerin aus Vorarlberg" | sofort möglich, ohne Rückfrage |

Für die ersten Wochen reicht **Anonymisiert** vollkommen — die Marken-Aussage trägt sich selbst, auch ohne Name.

---

## 6. Code-Umsetzung

### Wo im Repo

Die Plattform-Site lebt in:

```
server/marketing_templates/platform_meta.html
```

(Aus den Migrations-Build-Packs bekannt.) Die Section-Struktur ist GSAP-basiert. Die neue Pilot-Quote-Section wird zwischen Hero und Editionen-Galerie eingefügt.

### HTML-Skelett

```html
<!-- Pilot-Stimmen-Section -->
<section class="pilot-voice" data-section="pilot-voice">
  <div class="pilot-voice-inner">
    <blockquote class="pilot-quote">
      "Ein Programm, was mir die ganze Zettelei und Denkerei abnimmt."
    </blockquote>
    <cite class="pilot-attribution">
      <span class="pilot-name">Mira F.</span>
      <span class="pilot-role">KITA-Trägerin · Krummelus</span>
      <span class="pilot-location">Dornbirn, Vorarlberg</span>
    </cite>
  </div>
</section>
```

### CSS-Skelett

```css
.pilot-voice {
  min-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(40px, 8vh, 120px) clamp(24px, 5vw, 80px);
  background: transparent;  /* atmet mit dem globalen Background */
}

.pilot-voice-inner {
  max-width: 720px;
  text-align: left;
}

.pilot-quote {
  font-size: clamp(1.6rem, 3.4vw, 2.4rem);
  font-weight: 300;
  line-height: 1.3;
  letter-spacing: -0.02em;
  color: var(--fg-strong);
  margin: 0 0 clamp(24px, 4vh, 48px);
}

.pilot-quote::before { content: '"'; opacity: 0.35; }
.pilot-quote::after  { content: '"'; opacity: 0.35; }

.pilot-attribution {
  font-style: normal;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: clamp(0.95rem, 1.4vw, 1.1rem);
  color: var(--fg-soft);
}

.pilot-name {
  color: var(--fg-strong);
  font-weight: 500;
}

.pilot-role,
.pilot-location {
  color: var(--fg-soft);
}

/* Subtle scroll-trigger entrance */
.pilot-voice .pilot-quote,
.pilot-voice .pilot-attribution {
  opacity: 0;
  transform: translateY(16px);
  transition: opacity 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94),
              transform 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.pilot-voice.in-view .pilot-quote {
  opacity: 1;
  transform: translateY(0);
  transition-delay: 0.1s;
}

.pilot-voice.in-view .pilot-attribution {
  opacity: 1;
  transform: translateY(0);
  transition-delay: 0.5s;
}
```

### GSAP-ScrollTrigger-Anbindung

```javascript
// Innerhalb des existierenden GSAP-Setups
ScrollTrigger.create({
  trigger: '.pilot-voice',
  start: 'top 70%',
  onEnter: () => document.querySelector('.pilot-voice').classList.add('in-view'),
  onLeaveBack: () => document.querySelector('.pilot-voice').classList.remove('in-view')
});
```

### Mobile-Responsivität

`clamp()` regelt Schriftgrößen automatisch. Auf Mobile:
- `pilot-quote`: ~1.6rem
- `pilot-attribution`: ~0.95rem
- `min-height: 70vh` bleibt — gibt der Quote auch auf Phone Atemraum

---

## 7. Edition-Sales-Pages (später)

Wenn Edition-Sales-Pages live sind (`shiksha.world/kita`, `shiksha.world/camping`, etc.), bekommt jede ihre eigene Pilot-Stimmen-Section:

| Edition | Aktueller Pilot-Satz (anonymisiert) |
|---|---|
| KITA | *"Ein Programm, was mir die Zettelei und Denkerei abnimmt."* |
| Camping | *(noch keiner — Pilot pending)* |
| Schule | *(noch keiner)* |
| Surf | *(noch keiner)* |
| Yoga | *(noch keiner)* |
| Club | *(noch keiner)* |

Pflege: Sobald jeder Pilot durchgelaufen ist, sammelt der Founder eine Pilot-Stimme + Zustimmung.

---

## 8. Umsetzungs-Pfad

```
□ Mira-Zustimmung einholen (5 Min Gespräch)
□ Section ins platform_meta.html einfügen (~20 Min)
□ CSS + GSAP-ScrollTrigger ergänzen (~15 Min)
□ sync.sh --confirmed
□ Smoke-Test auf shiksha.world
□ Optional: A/B-Test mit/ohne Section, Conversion-Wirkung beobachten
```

**Aufwand insgesamt:** ~45 Min, sobald Mira-Zustimmung da ist.

**Cross-Reference master_vision.md:** Sektion 4.1 zitiert dieses File als Umsetzungs-Quelle.

---

## 9. Update-Pfad in `master_vision.md`

Wenn die Pilot-Stimmen-Section live geht, ergänzt sich `master_vision.md` Sektion 4.1 um den **Live-Link**:

```markdown
Live unter shiksha.world (Pilot-Stimmen-Section):
→ https://shiksha.world#pilot-voice
```

Plus: Sobald 3+ Pilot-Stimmen existieren, evolviert das Konzept zu Variante C (Karussell), und diese Spec-Datei wird zur historischen Referenz.

---

**Spec · Stand 4. Mai 2026 · Pilot-Stimme als Marken-Validierung · Mira F. als Krummelus-Pilot · Code-Umsetzung nach Zustimmung in ~45 Min**
