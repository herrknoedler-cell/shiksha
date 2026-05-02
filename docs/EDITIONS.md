# SHIKSHA · Editionen

> "Editionen sind Konfiguration, nicht Codeforks."

Sechs Editionen aktuell in der Pipeline. Pro Edition: ein Eintrag in
`editions` (Tabelle in der DB), ein Build-Pack
(`docs/build-packs/<edition>.md`), ggf. eigene Module
(`server/<edition>_*.py`) und eigene UIs (`server/ui/<edition>_*.html`).
Was sie teilen: Identity, Kalender, Personen, Push, Archive, Marketing-
Site-Generator, Safeguarding, Documents, Accounting — die Cross-Edition-
Module aus [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Status-Matrix

| Edition | Slug | Status | Pilot | Build-Pack |
|---|---|---|---|---|
| KITA | `kita` | **live** | `kita.shiksha.tun.zone` (Schwester, 18 Kinder, 5 Mitarbeitende) | [`kita-compliance.md`](build-packs/kita-compliance.md) |
| Camping | `camping` | **Beta** | Allweglehen Berchtesgaden + Inntalblick Tirol (Fiktiv-Pilots) | [`camping.md`](build-packs/camping.md) |
| Surfschule | `surfschule` | **geplant** | Surfschule Sylt (Fiktiv-Pilot) | [`schule.md`](build-packs/schule.md) (Schule-Familie) |
| Yogaschule | `yogaschule` | **geplant** | Yogaschule Wien (Fiktiv-Pilot) | [`schule.md`](build-packs/schule.md) |
| Schule (Reit / Tanz / Ski / generisch) | `schule` | **geplant** | — | [`schule.md`](build-packs/schule.md) |
| Club (Vereine) | `club` | **geplant** | — | [`club.md`](build-packs/club.md) |

Quelle: `GET /kita/api/platform/editions` returnt diese kuratierte Liste
live aus der DB.

---

## Pro Edition

### KITA — Compliance, Anmeldung, Eltern-Kommunikation

Kern-Modul: Vorarlberg-KBBG-konforme Compliance-Engine mit ST%-Rechner,
60-Monate-Audit, Personalschlüssel-Recommendations. Drei UIs:

- Trägerin-Dashboard — `ui/kita/dashboard_traegerin.html` (Gridstack-Cards)
- Pädagogen-PWA — `paedagogen_ui/app.html` (mobil-friendly Halbtages-Anwesenheit)
- Eltern-PWA — `kita_ui/eltern.html` (Mitteilungen, Profil)

Anmeldung als 2-Signaturen-Wizard (`kita_ui/anmeldung.html`).

**Daten heute (Pilot):** 18 Kinder, 5 Mitarbeitende, 8 Räume, 3 Bereiche.

**Bekannte Lücke:** Legacy-App auf Port 8001 hat die echten Pilot-Daten
in SQLite; neue Compliance-Engine nutzt PostgreSQL. Sync ist
unidirektional (Legacy → Compliance via `/kita/groups/unified`),
Compliance → Legacy fehlt. Cutover-Tooling unter
[`scripts/migrate-kita-legacy/`](../scripts/migrate-kita-legacy/).

### Camping — Übernachtungs-Gewerbe

Inhaber-geführte Plätze 80–250 Pitches mit Glamping-Ergänzung.
Eigene Module: `pitch`, `reservation`, `check_in_out`, `seasonal_pricing`,
`utility_metering`, `guest_journey`. Cross-Edition: `safeguarding` (Pool,
Spielplatz, Aufsichtspflicht).

**Policies:**

- `camping.no_auto_rebooking` — Pitch-Wechsel braucht Operator-Bestätigung.
- `camping.guest_data_minimal` — Meldedaten nur so lange wie behördlich
  nötig. Anonymisierung nach Abreise + 12 Monate.
- `camping.minor_supervision_required` — Aufsichtspflicht für Minderjährige
  in safeguarding-relevanten Zonen.

Build-Pack mit beiden Fiktiv-Pilots in vollem Detail:
[`build-packs/camping.md`](build-packs/camping.md).

### Schule — Yoga, Surf, Reit, Tanz, Ski

Inhaber-geführte Bildungsbetriebe. Eigene Module: `course`, `enrollment`,
`package`, `instructor_qualification`, `weather_dependency`. Drop-In-
Inhalte für Document-Module-Demos in `server/fixtures/schule/ai_documents/`
(12 Beispiel-Dokumente: Anmeldungen mit/ohne minderjährig, Mahnungen,
Lieferscheine, Versicherung, Wetter-Verschiebung, Hebammen-Bescheinigung).

**Policies:**

- `schule.no_auto_certification` — Prüfungs-Ergebnisse (Surf-Level, Yoga-
  Stufe, Reit-Abzeichen) brauchen explizite Lehrer-Bestätigung.
- `schule.no_auto_minor_communication` — Bei Schülern unter 16 geht
  jede Kommunikation an den Guardian. SHIKSHA versendet nichts ohne
  explizite Operator-Freigabe.
- `schule.consent_required_for_minors` — Einwilligung als Block-Policy.

### Club — Eingetragene Vereine

21 Module über drei Phasen: people/membership/activity →
volunteer/community/assembly → knowledge/competency/funding. Eigene
Module geplant: `club_orchestrator`, `club_board_copilot`, optional
`federation`.

**Status:** nur Build-Pack, kein Code. Entsteht erst, wenn ein konkreter
Verein als Pilot einsteigt. USPs gegen ClubDesk / Easyverein /
Vereinsflieger / SPG-Verein / Campai siehe Build-Pack.

---

## Wie eine neue Edition entsteht

1. **Build-Pack** schreiben (`docs/build-packs/<edition>.md`) — Edition-
   Profil als JSON, Policies, modules_reused, modules_new, Referenzfälle.
2. **DB-Migration**: Edition-spezifisches Schema
   (`server/<edition>_db_migration.sql`).
3. **Modelle + Orchestrator** (`server/<edition>_models.py`, `_orchestrator.py`).
4. **Router/Endpoints** — als eigenständiger FastAPI `APIRouter`
   (NICHT an `kita_compliance_router.py` anhängen — Phase 4 hat gezeigt,
   warum). Registriert in `main.py` an der richtigen Stelle.
5. **Eintrag** in `editions`-Tabelle, damit `/api/platform/editions` sie listet.
6. **Fixtures** (`server/fixtures/<edition>/`) für Demo-Daten + AI-Document-
   Beispiele für die Document-Module-Demos.
7. **UIs** in `server/ui/<edition>_*.html`.
8. **Pilot-Onboarding** (8-Wochen-Plan in Cowork — siehe
   `outreach/PILOT_ONBOARDING_8_WOCHEN.md`).
