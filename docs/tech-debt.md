# Tech-Schulden

Lebende Liste bekannter Findings, die identifiziert, aber noch nicht
behoben sind — getrennt in **Critical Security Debt** (etwas, was uns
beim öffentlichen Repo-Push beißt) und **Unfinished Refactors**
(angefangene Umbauten, deren beide Hälften nie zusammen deployt wurden).

Pro Eintrag: Severity bzw. Risiko, Fundstelle, Befund, Fix-Pfad,
geplanter Sprint. Sobald ein Eintrag behoben ist: streichen **und**
den Fix-Commit hier verlinken — die Git-History dieser Datei wird so
zur Audit-Spur.

---

## Critical Security Debt

### ~~Hardcoded DB-Credentials in `server/calendar_module.py`~~

> ✅ **Code-Refactor erledigt am 2026-05-02 in Phase 7** — Commit
> [`0c4864a`](../../../commit/0c4864a). Der Audit hat **9 Files** mit
> hardcoded `postgresql://shiksha:shiksha2026@…` aufgedeckt (nicht nur
> `calendar_module.py`); alle wurden auf zentrale env-driven Engine in
> `server/database.py` umgestellt, mit Hard-Fail-Pattern bei fehlender
> `DATABASE_URL`. Plus Vereinheitlichung der psycopg-Scripts auf dieselbe
> Konvention (`SHIKSHA_DB_*` → `DATABASE_URL`). Setup-Doku in
> [`DEPLOY.md`](DEPLOY.md#required-environment-variables).
>
> **Noch offen (Phase 7 Schritte 3 + 4):** server-seitige `database.conf`
> anlegen, Cron-Job-Aufrufpfad bestätigen, DB-Passwort rotieren. Dieser
> Eintrag wird beim finalen Phase-7-Commit komplett entfernt.

<details>
<summary>Original-Eintrag (historisch, durchgestrichen)</summary>

|              |                                                          |
| ------------ | -------------------------------------------------------- |
| **Severity** | Critical                                                 |
| **Found**    | 2026-05-02 (Phase-2-Migration, A.5 Kalender)             |
| **File**     | `server/calendar_module.py:33` (plus 8 weitere, beim Audit aufgedeckt) |

**Befund:**

```python
def _engine():
    return sa.create_engine("postgresql://shiksha:shiksha2026@localhost/shiksha")
```

DB-User, Passwort, Host und Datenbankname standen im Klartext im
Quellcode. Mehrfach repliziert in `database.py`, `main.py` (4×),
`accounting_router.py`, `accounting_module.py`, `documents_endpoint.py`,
`document_module.py`, plus Migrations-Skript.

**Fix-Pfad (umgesetzt):**

1. ~~Passwort rotieren~~ → Phase 7 Schritt 4.
2. ✓ Code: `database.py` zentral, env-driven, hard-fail bei fehlender
   `DATABASE_URL`. Alle Caller importieren `engine` von dort.
3. Git-History des alten Passworts wurde **nicht** rewritten — Rotation
   macht den alten Wert kraftlos. Repo bleibt privat bis Rotation läuft.
4. Pre-Commit-Hook für Secret-Detection (z.B. `gitleaks`, `trufflehog`)
   bleibt offen — eigener kleiner Folge-Sprint.

</details>

---

## Unfinished Refactors

Angefangene Umbauten, deren beide Hälften nie zusammen deployt wurden.
Solche WIP-Drafts sind tickende Bomben: harmlos solange niemand sie
anfasst, aber bei der nächsten Migration brechen sie was — siehe
Phase-4-Recovery weiter unten.

### Document-Compression-Refactor (`compression.py` ↔ `document_module_extensions.py`)

|             |                                                              |
| ----------- | ------------------------------------------------------------ |
| **Risiko**  | Medium — Service-Crash beim nächsten falschen Overlay        |
| **Found**   | 2026-05-02 (Phase 4 — erster `sync.sh --confirmed`-Lauf)     |
| **Files**   | `server/compression.py` (production), `server/document_module_extensions.py` (orphan) |

**Befund:** In Cowork wurde ein Refactor begonnen, der die generische
`compress(analysis) → DocumentSummary`-API in Per-Document-Type-
Funktionen aufspaltet:

```
compress_invoice / _dunning / _enrollment_form / _meter_reading /
_behoerden_bescheid / _delivery_note / _weather_postponement /
_guest_complaint  →  DocumentDigest
```

`document_module_extensions.py` enthält die zugehörigen Pydantic-Models
für die neuen Doc-Types. **Aber:** `main.py` wurde nie auf die neue
API umgestellt, kein Doc-Type-Routing eingebaut. Die Files sind
zusammen nur halb da.

In Phase 4 hat ein "newer-wins"-Overlay die neue `compression.py`
deployt; Service ist im ImportError gelandet (`from compression import
compress` schlug fehl). Recovery: chirurgischer Revert zur alten Version
in Commit `181cd87`.

`document_module_extensions.py` liegt seither als **Orphan** im Repo —
nicht importiert, harmlos für den Moment, aber jeder, der es liest,
wird sich fragen, was es soll.

**Fix-Pfad — zwei Optionen:**

A) **Refactor zu Ende bringen.** `main.py` auf Doc-Type-Detection
   umstellen, Routing der eingehenden Documents in den richtigen
   `compress_*`-Pfad, `compression.py` auf die neue API ziehen,
   `document_module_extensions.py` ans Doc-Type-Routing andocken.
   Schätzung: 1-2 Stunden, plus Test.

B) **Refactor verwerfen.** `document_module_extensions.py` löschen,
   alte `compression.py` als kanonisch markieren. Schätzung: 5 Minuten.

Entscheidung hängt davon ab, ob die Per-Doc-Type-Compression einen
echten Mehrwert bringt (besseres Field-Extraction-Routing, klarere
Domain-Models pro Doc-Type) oder nur Komplexität ohne Gegenleistung.

**Plan:** Eigener Mini-Sprint nach Phase 6, parallel oder nach dem
Security-Sprint.

---

## Wie ein neuer Eintrag aussieht

```markdown
### <kurze Beschreibung des Befunds>

|             |                                |
| ----------- | ------------------------------ |
| **Severity** oder **Risiko** | Critical / High / Medium / Low |
| **Found**   | YYYY-MM-DD (Quelle / Sprint)   |
| **File(s)** | `pfad/zur/datei.py:Zeile`      |

**Befund:** <was ist los, in einem Absatz>

**Fix-Pfad:** <konkrete Schritte>

**Plan:** <wann / Sprint>
```
