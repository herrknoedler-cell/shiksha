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

## 🌱 INTRO-Modul "Wir lernen uns kennen"

### Build-Pack v1.0 fertig
- **Status:** done ✓
- **Quelle:** Cowork-Session 2026-05-03
- **Notizen:** Vollständige Spec in `docs/build-packs/INTRO_AND_CHAT_MODULE_BUILD_PACK_V1.md`. 16-Schritte-Sequenz für KITA, Cross-Edition-Architektur, DB-Schema, UI-Sketches.

### Phase 1.1 — Engine + KITA-Code
- **Status:** planned, nach Krummelus-Pilot-Lessons
- **Aufwand:** 1 Tag (~6h)
- **Quelle:** Cowork-Session 2026-05-03
- **Notizen:** intro_engine.py, intro_steps_kita.py, DB-Migration (intro_progress + intro_step_data), API-Endpoints, einfaches Wizard-Modal-UI. Lessons aus dem Krummelus-Manual-Lauf am 4. Mai fließen direkt in die Sequenz-Daten ein (siehe Notiz-Block in `INTRO_KITA_KRUMMELUS_KICKOFF.md`).

### Phase 1.2 — UI-Polish
- **Status:** planned, nach 1.1
- **Aufwand:** 1 Tag (~6h)
- **Notizen:** Holi-Wizard mit GSAP-Übergängen, Skip-Logik mit Defaults, Bilder-Pool-Integration in Schritt 12, Marketing-Builder-Trigger in Schritt 11, Identity-Wizard in Schritt 3.

### Phase 1.3 — Andere Editionen
- **Status:** idea, nach KITA-Stabilisierung
- **Aufwand:** ~2-3h pro Edition
- **Notizen:** intro_steps_camping.py, intro_steps_schule.py, intro_steps_yoga.py, intro_steps_surfschule.py, intro_steps_club.py. Wiederverwendung der Engine + UI, nur Sequenz-Daten edition-spezifisch. Build-Pack hat Skizzen für alle.

### Krummelus-Lessons-Loop
- **Status:** in-progress (Pilot-Lauf 4. Mai 2026)
- **Aufwand:** laufend
- **Notizen:** Nach jedem Pilot-Schritt notieren: Was war zu lang, welche Begriffe unklar, was wurde geskipt, was hat begeistert. Notiz-Felder im Kickoff-File. Auswertung am Abend des 4. Mai → konkrete Sequenz-Anpassungen für v1.1.

---

## 💬 CHAT-Modul "shiksha ist da"

### Phase 1.0 — Claude-only MVP
- **Status:** planned
- **Aufwand:** 1 Tag (~6-8h)
- **Quelle:** Cowork-Session 2026-05-03
- **Notizen:** Floating-Bubble + Chat-Window-UI im Holi-Look. Anthropic Claude API mit System-Prompt + kontextabhängigem Greeting. Memory-Loader liest BACKLOG.md, tech-debt.md, EDITIONS.md. 6 read-only Tools (get_kita_overview, get_st_calculation, list_audit_findings, get_calendar_today, get_intro_status, search_memory). Konversations-Persistenz (chat_conversations + chat_messages).

### Phase 1.1 — Multi-LLM Support
- **Status:** idea, nach 1.0 stabil
- **Aufwand:** 1 Tag (~4-6h)
- **Notizen:** OpenAI ChatGPT + Google Gemini als Provider-Adapter. Settings-UI für Provider-Wahl. Provider-Status-Check (welche API-Keys verfügbar). DSGVO-Hinweis bei Multi-LLM (KITA-Daten gehen an externe APIs).

### Phase 1.2 — Action-Tools
- **Status:** idea
- **Aufwand:** 1-2 Tage (~8-12h)
- **Notizen:** Schreibende Tools: create_anmeldung, send_email_to_parents, generate_marketing_text, create_audit_report, schedule_event. Alle mit Bestätigungs-Gate (User klickt explizit "Ja, mach"). Audit-Log für jede Aktion.

### Phase 1.3 — Voice
- **Status:** idea, optional
- **Aufwand:** mittel
- **Notizen:** Browser-Speech-API für Eingabe, TTS-Cloud-Service für Ausgabe. Nicht-Ziel für 2026, kommt wenn überhaupt nach Multi-LLM.

### Persona-Konsistenz über LLMs
- **Status:** tech-debt, ab 1.1 relevant
- **Aufwand:** Stil-Postprocessing oder Prompt-Engineering
- **Notizen:** ChatGPT und Gemini interpretieren Persona-Prompts unterschiedlich. Bei Multi-LLM darauf achten, dass die SHIKSHA-Stimme konsistent bleibt — selbe System-Prompts über alle Provider, plus eventuelle Stil-Filter.

### ANTHROPIC_API_KEY ist im Server
- **Status:** done ✓
- **Notizen:** Seit Phase 7 (2. Mai 2026) im systemd Drop-In `/etc/systemd/system/shiksha.service.d/anthropic.conf`. Chat-MVP kann direkt darauf zugreifen.

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

## 🔧 REPAIR-Network (Lokal-Reparatur-Marktplatz)

### V0.2 — Erster manueller Pilot-Auftrag (Krummelus)
- **Status:** planned, sobald Krummelus stabil läuft
- **Aufwand:** 4-6 Wochen, manuell vermittelt
- **Quelle:** `docs/build-packs/SHIKSHA_REPAIR_NETWORK_CONCEPT_V0_1.md`
- **Notizen:** Heidi nennt einen Reparatur-Bedarf (kaputtes Spielzeug, Möbel-Beschlag), Founder vermittelt manuell an FAB Lab Dornbirn oder lokalen Maker. Ohne Code, nur Process. Lessons → V1.0-Spec.

### V1.0 — MVP-Marketplace
- **Status:** idea (Code-Sprint nach Pilot-Lessons)
- **Aufwand:** 3-4 Monate
- **Quelle:** Konzept V0.1 in build-packs/
- **Notizen:** Drucker-Registry mit PostGIS, Auftrag-Routing, Stripe Connect für Marketplace-Zahlungen, Bewertungssystem, Climate-Tracker, geographischer Cluster Vorarlberg.

### Climate-Tracker als Cross-Edition-Feature
- **Status:** idea
- **Aufwand:** 1-2 Tage
- **Notizen:** Pro Reparatur-Auftrag CO2-Ersparnis berechnen (lokal vs. Versand-Alternative). Sichtbar im Trägerin/Operator-Dashboard. Auch nutzbar für andere Edition-Aktionen mit Climate-Bezug.

---

## 🌟 Vision-Layer (langfristig, Master-Vision)

### Master-Vision konsultieren
- **Status:** done ✓ (`docs/master_vision.md`)
- **Notizen:** Pflicht-Lektüre für jede Code-Session. Bei Konflikt zwischen Implementations-Idee und Vision gewinnt die Vision. Aktualisierungen via `vision:`-Commits, nur mit Founder-Beschluss.

### Sonnenstands-Farbraum (Dynamic UI)
- **Status:** idea
- **Aufwand:** 1-2h Backend + Frontend-Integration
- **Quelle:** `master_vision.md` Sektion 3
- **Notizen:** `get_color_palette(time, location)` mit `astral` oder `pyephem`. Output: Hex-Codes als CSS-Custom-Properties via SSE-Push. 07:00 = Sunrise-Yellow, 20:00 = Strategic-Deep-Blue.

### Theorie-Brücke (Wetter-API)
- **Status:** idea
- **Aufwand:** 4-6h
- **Quelle:** `master_vision.md` Sektion 3
- **Notizen:** Bei Wetterumschwung Outdoor → Indoor-Alternative vorschlagen. KITA: Bewegungsraum-Vorschläge. SCHULE: Theorie-Module statt Sport. Cross-Edition-Modul.

### GASTRO-Edition (LUNCHBOX-Konzept)
- **Status:** vision
- **Aufwand:** Build-Pack noch zu schreiben
- **Quelle:** `master_vision.md` Sektion 2
- **Notizen:** 17% Wareneinsatz-Logik, Cook&Chill (vegetarisch, 12 Tage @ 3°C), Idle-Time-Production (14-17 Uhr Kombidämpfer-Batches), Veredelungs-Modul ("Technik macht Logistik, Mensch macht das Lächeln").

### MOBILITY-Edition (Hardware-Layer)
- **Status:** vision (CAMPING-Build-Pack existiert, Hardware-Erweiterung neu)
- **Aufwand:** Build-Pack-Erweiterung + IoT-Integration
- **Quelle:** `master_vision.md` Sektion 2
- **Notizen:** GPS/Tankdaten, IoT-Schranken/Strom, Auto-Check-in via Geofencing, Dynamic Pricing nach Wetter+Auslastung.

### Efficiency-Tracker (ROI sichtbar)
- **Status:** idea
- **Aufwand:** 1-2 Tage
- **Quelle:** `master_vision.md` Sektion 4 ("Amazon-Moment")
- **Notizen:** Pro Tool-Call Zeitersparnis berechnen ("check-in spart 45s vs. manuelle Liste"). Aggregiert: ROI-Beweis fürs Sales-Pitch.

### 1€-Pricing-Vision (globale Skalierung)
- **Status:** vision (langfristig)
- **Quelle:** `master_vision.md` Sektion 1
- **Notizen:** Bei massiver Skalierung Preis-Reduktion auf 1€/Monat mit 90% Social Impact. Manifest-Vision, kein 12-Monats-Plan.

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
