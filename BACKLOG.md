# SHIKSHA · Backlog

**Zweck:** Persistenter Speicher für Themen, die wir besprochen, aber nicht sofort umgesetzt haben. Pro Eintrag: Status, Aufwand-Schätzung, Quelle der Diskussion, kurze Notizen.

**Status-Skala:**
- `idea` — angedacht, nicht durchgeplant
- `planned` — durchdacht, wartet auf Slot
- `ready-to-build` — alle Vorbedingungen erfüllt, kann sofort starten
- `in-progress` — wird gerade umgesetzt
- `tech-debt` — Technische Schuld, sollte mal angegangen werden
- `not-now` — bewusst zurückgestellt

**Letzte Aktualisierung:** 2026-05-03

---

## 🎨 Plattform-Site Premium-Polish

### Holi-Gradient auf Headlines
- **Status:** idea
- **Aufwand:** 1-2h
- **Quelle:** Cowork-Session 2026-05-02 (Premium-Vision)
- **Notizen:** Headlines auf shiksha.world mit `background-image: linear-gradient(...); -webkit-background-clip: text; color: transparent;`. Animation via `background-position`-Verschiebung. Erster Premium-Wow-Moment der Site, geringer Aufwand.

### Shiksha-Schriftzug, scroll-driven
- **Status:** idea
- **Aufwand:** 1-2 Tage
- **Quelle:** Cowork-Session 2026-05-02
- **Notizen:** SVG-Path mit `stroke-dasharray`-Animation, GSAP ScrollTrigger setzt `stroke-dashoffset` proportional zum Scroll. Brauchen den Schriftzug als SVG mit definierter Pfad-Länge (handgeschriebener Look).

### 3D-Geräte (iPad kippt, iPhone dreht, Glas-Spiegelung)
- **Status:** planned, wartet auf 3D-Models
- **Aufwand:** 4-6h Integration nach Spline/C4D-Export
- **Quelle:** Cowork-Session 2026-05-02
- **Notizen:** Thomas baut in **Spline.design** (no-code, eigene Scroll-API) oder **Cinema 4D / Blender** (Export als GLB, Three.js + GSAP). Glas-Spiegelung via `MeshPhysicalMaterial` + `envMap`. Mobile-Fallback: 2D-Slide-up wie aktuelles Demo. `prefers-reduced-motion` respektieren.

### Logo-Wipe — SVG-Maske zoomt von außen rein
- **Status:** idea
- **Aufwand:** 3-4h
- **Quelle:** Cowork-Session 2026-05-02
- **Notizen:** SVG `<mask>` mit Logo, das initial groß ist und beim Scrollen auf Normgröße schrumpft. Während Logo schrumpft, wird das Hintergrund-Video sichtbar. Apple-Keynote-Style.

### Schriften mit Hero-Video als Füllung
- **Status:** idea
- **Aufwand:** mittel
- **Quelle:** Cowork-Session 2026-05-02
- **Notizen:** SVG `<mask>` mit Text als Mask, Video als Mask-Quelle. Oder `clip-path: url(#text-mask)`. Trickreich aber spektakulär.

### Farbraum pro Edition (CSS Custom Properties)
- **Status:** idea
- **Aufwand:** gering (~1h)
- **Quelle:** Cowork-Session 2026-05-02
- **Notizen:** Pro Edition eigene `--accent-primary`, `--accent-secondary`. Override per `body.edition-camping { ... }`. Unterstützt: Wassersport (Blau-Türkis), Jagd (Erdtöne), KITA (Holi-Pink), Yoga (sanftes Pastell), etc.

### Sticky-Scroll-Section in shiksha.world einbauen
- **Status:** planned, Demo existiert
- **Aufwand:** 2-3h Integration + 4-6h Screenshot-Erstellung
- **Quelle:** Cowork-Session 2026-05-03 (Demo-HTML in /outputs/sticky-scroll-demo.html)
- **Notizen:** Pattern: Pinned Sticky Scroll mit Slide-up-Reel-Effekt + Text-Stagger. Storyboard final: 5 iPad-Steps (Trägerin-Dashboard, Kalender, Personen, SHIKSHA-Begrüßung, Marketing-Builder), Atempause-Section dazwischen, dann 3 iPhone-Steps (Pädagogen-PWA, Eltern-PWA, Identity-Wizard). Kommt nach STITCH-Migration.

---

## 🖼️ Bilder-Pool — generelles Stockmaterial-System

### Phase A — Server-Ordnerstruktur + SFTP-Setup
- **Status:** ready-to-build
- **Aufwand:** 30 Min
- **Quelle:** Cowork-Session 2026-05-03
- **Notizen:** `/opt/shiksha/static/pool/` mit `_originals/<edition>/`, `desktop/<edition>/`, `mobile/<edition>/`. Editionen: kita, camping, schule, surfschule, yoga, club, stitch, universal. SFTP-Zugang via existierendem SSH-Key.

### Phase B — pool_processor.py + Cron + API-Endpoint
- **Status:** planned
- **Aufwand:** 1-2h
- **Quelle:** Cowork-Session 2026-05-03
- **Notizen:** Python-Script via Pillow generiert Desktop (1600×1067, 3:2, JPG quality 85, ~150-250 KB) + Mobile (800×533, 3:2, ~50-100 KB) aus _originals/. Cron alle 5 Min. Manifest `pool_index.json` mit Tags + Pfaden + Datum. API-Endpoint `/api/pool?edition=kita&tags=holi,garten`.

### Phase C — Editionen-Galerie nutzt Pool
- **Status:** planned
- **Aufwand:** 1h, abhängig von Phase B
- **Quelle:** Cowork-Session 2026-05-03
- **Notizen:** Plattform-Site-Template liest pro Edition ein zufälliges oder kuratiertes Bild aus dem Pool. Card-Layout: Bild als BG mit dunklem Bottom-Gradient für Text-Lesbarkeit. Aspect 3:2 oder 4:3.

### Phase D — Pool-Browser für Pilot-Kunden
- **Status:** idea, hochwertiges Pilot-Feature
- **Aufwand:** 4-6h
- **Quelle:** Cowork-Session 2026-05-03
- **Notizen:** Trägerin/Operator sieht Pool-Browser im Backend, kann Bilder filtern (Edition, Tags), in eigene Marketing-Site übernehmen. **USP fürs Pilot-Pitch:** "Im Abo enthalten: SHIKSHA-Bildbibliothek, wöchentlich neue Holi-Atmosphären."

### Bilder-Größen festgelegt
- Original: 2400×1600 (3:2) — Master, FTP-Upload
- Desktop: 1600×1067 (3:2) — ~150-250 KB JPG
- Mobile: 800×533 (3:2) — ~50-100 KB JPG
- Naming: `YYYY-MM-DD_thema_NNN.jpg` (z.B. `2026-05-03_holi-garten_001.jpg`)

---

## 🌱 Editionen-System

### STITCH als 7. Edition in shiksha.world (mit external_url)
- **Status:** planned (DNS für stitchengine.pro schon registriert)
- **Aufwand:** 30 Min nach STITCH-Domain-Switch
- **Quelle:** Cowork-Session 2026-05-03
- **Notizen:** `editions`-Tabelle um Spalte `external_url` erweitern. STITCH-Eintrag mit slug=stitch, icon=🧵, status=live, external_url=https://stitchengine.pro. Plattform-Site-Template rendert externe Cards mit ↗-Indikator.

### Edition-spezifische Hero-Videos
- **Status:** idea
- **Aufwand:** abhängig von Bild/Video-Material
- **Quelle:** Cowork-Session 2026-05-02
- **Notizen:** Statt einem zentralen Hero-Video pro Edition ein passendes (Surfschule am Strand mit Holi, Camping am Lagerfeuer, etc.). Datenbank-driven, ähnlich Bilder-Pool.

### Edition-spezifische Sales-Pages
- **Status:** idea
- **Aufwand:** mittel pro Edition (3-5h)
- **Quelle:** Cowork-Session 2026-05-02
- **Notizen:** shiksha.world/kita, shiksha.world/camping, etc. Jede mit eigenem Storyboard, eigenem Hero, eigener Edition-Karten-Reihenfolge. Komponenten-basiert, sodass nur Daten getauscht werden.

### Camping-Edition Lagepläne als UI-Feature
- **Status:** idea
- **Aufwand:** mittel-hoch (eigener Sprint)
- **Quelle:** Cowork-Session vorher (vor Migration)
- **Notizen:** Stellplatz-Markierung auf interaktivem Lageplan, vermutlich SVG-Polygone mit Status-Farben (frei/belegt/reserviert). Erst wenn Camping-Pilotpartner anfragt.

---

## 🔧 Operations & Hygiene

### SSR-Fallback für Editionen-Galerie
- **Status:** not-now
- **Aufwand:** mittel
- **Quelle:** Cowork-Session 2026-05-03 (CLUB-Mini-Sprint)
- **Notizen:** Aktuell client-side fetched, Raw-HTML hat nur leere Hülle. Für SEO und no-JS-User: Server-side rendering der Editionen vorab ins Template. Kein Blocker, hat eigenen Sprint-Wert.

### Pre-Commit-Hook für Secret-Detection
- **Status:** planned (Folge-Sprint nach Phase 7)
- **Aufwand:** 30 Min
- **Quelle:** Cowork-Session 2026-05-02 (Phase 7 Final-Bericht)
- **Notizen:** gitleaks oder trufflehog als pre-commit-Hook. Verhindert künftiges versehentliches Hardcoden von Secrets — direkte Prävention der Phase-7-Critical-Debt.

### Document-Compression-Refactor
- **Status:** tech-debt (in tech-debt.md detailliert)
- **Aufwand:** mittel
- **Quelle:** SHIKSHA Phase 4 Sync-Drama
- **Notizen:** compression.py ↔ document_module_extensions.py — Unfinished Refactor, nicht service-kritisch. Zwei Lösungspfade in tech-debt.md dokumentiert.

### Mail-Records für info@shiksha.world
- **Status:** idea
- **Aufwand:** 30 Min DNS + Mail-Provider-Setup
- **Quelle:** Cowork-Session 2026-05-02
- **Notizen:** MX, SPF, DKIM, DMARC bei united-domains. Plus Mail-Provider (z.B. mailbox.org oder Fastmail) wählen. Wichtig für Pilot-Outreach.

### Cloudflare-DNS-Migration
- **Status:** idea, wenn Wildcard-Bedarf da ist
- **Aufwand:** 1h + 24h Propagations-Wartezeit
- **Quelle:** Cowork-Session 2026-05-02 (Domain-Setup)
- **Notizen:** Aktuell DNS bei united-domains. Migration zu Cloudflare bringt: Wildcard-Cert für *.shiksha.world, DDoS-Schutz, Analytics. Lohnt sich bei vielen Edition-Subdomains.

### Hero-Video Edition-Color-Adaptation
- **Status:** idea
- **Aufwand:** abhängig von Video-Material
- **Quelle:** Cowork-Session 2026-05-02
- **Notizen:** Falls Hero-Video pro Edition unterschiedlich, kann Color-Mood passend zur Edition (Wassersport blau-türkis, Jagd erdig). Optional via CSS `mix-blend-mode` oder echtes Edition-Video.

---

## 🌟 Pilot-Aktivierung

### Krummelus mit echten Daten onboarden
- **Status:** highest-priority
- **Aufwand:** 8-Wochen-Sprint laut Pilot-Onboarding-Checkliste
- **Quelle:** Pilot-Onboarding-Checkliste (existiert in /outputs/)
- **Notizen:** Heidi (Schwester) als erster echter Pilot. Mitarbeiter-Stammdaten, Kinder, Eltern. Anwesenheit live, Eltern-Anmeldungen, Audit-Reports mit echten Zahlen. **Aus dem Pilot kommen: Screenshots, Storys, Testimonials, Conversion-Material.**

### VAPID-Keys generieren + Push-Subscribe in Pädagogen-PWA
- **Status:** planned, blocking für echte Push-Demo
- **Aufwand:** 30 Min
- **Quelle:** SHIKSHA-Briefing (Push-Module gebaut, aber nicht aktiviert)
- **Notizen:** `web-push generate-vapid-keys`, in systemd Drop-In. Subscribe-Trigger in Pädagogen-PWA. Test-Notification senden.

### Pilot-Outreach an Camping/Surfschule/Yoga
- **Status:** idea
- **Aufwand:** laufend
- **Quelle:** 6 Erstkontakt-Email-Pakete in /outputs/ (existieren)
- **Notizen:** Camping Bayern/Tirol, Surfschule Sylt, Yogaschule Wien als ideale Pilot-Kandidaten. Outreach-Materialien fertig. Nach KITA-Pilot-Erfolg parallel ausrollen.

### Firefly-Bilder-Generation für Krummelus
- **Status:** idea, abhängig von Bilder-Pool Phase A
- **Aufwand:** laufend (täglich 10 Bilder geplant)
- **Quelle:** Cowork-Session 2026-05-03
- **Notizen:** Sobald Pool-Struktur steht, generiert Thomas täglich Holi-Bilder via Firefly. Kontinuierlicher Asset-Aufbau.

---

## 📚 Dokumentations-Schulden

### EDITIONS.md mit STITCH erweitern
- **Status:** planned (wird mit STITCH-Edition-Eintrag fällig)
- **Aufwand:** 15 Min
- **Quelle:** Cowork-Session 2026-05-03

### Cross-Reference zwischen SHIKSHA und STITCH-Repo
- **Status:** idea
- **Aufwand:** 30 Min
- **Quelle:** Cowork-Session 2026-05-03
- **Notizen:** In SHIKSHA `docs/`-Ordner ein `RELATED_PRODUCTS.md` mit Verweis auf STITCH-Repo. Umgekehrt im STITCH-Repo ein `RELATED_PRODUCTS.md` mit Verweis auf SHIKSHA-Repo.

---

## Pflege-Hinweise

- **Wann aktualisieren?** Wenn ein Eintrag erledigt ist, Status auf `done` setzen oder Eintrag streichen. Wenn neue Themen vertagt werden, in passende Sektion einordnen.
- **Wer schreibt rein?** Thomas oder Claude (in Cowork oder Claude Code).
- **Cross-Reference:** STITCH-spezifische Themen sind im STITCH-Repo `BACKLOG.md`. Hier nur SHIKSHA + Cross-Edition-Themen.
- **Priorität:** Pilot-Aktivierung > Engine-Vervollständigung > Premium-Polish > Operations-Hygiene.
