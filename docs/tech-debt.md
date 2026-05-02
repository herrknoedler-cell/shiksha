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

### Hardcoded DB-Credentials in `server/calendar_module.py`

|              |                                                          |
| ------------ | -------------------------------------------------------- |
| **Severity** | Critical                                                 |
| **Found**    | 2026-05-02 (Phase-2-Migration, A.5 Kalender)             |
| **File**     | `server/calendar_module.py:33`                           |

**Befund:**

```python
def _engine():
    return sa.create_engine("postgresql://shiksha:shiksha2026@localhost/shiksha")
```

DB-User, Passwort, Host und Datenbankname stehen im Klartext im Quellcode.
Solange das Repo privat bleibt, ist die Exposition begrenzt; sobald es
öffentlich wird (geplant für Phase 6), ist das Passwort kompromittiert —
und auch nach späterer Rotation bleibt der alte Wert in der Git-History
sichtbar.

**Sekundäre Risiken:** dasselbe Pattern könnte in weiteren Files lauern
(`database.py`, `document_module.py`, `accounting_module.py`, …) — beim
Fix systematisch suchen.

**Fix-Pfad:**

1. Passwort auf der Production-DB **zuerst** rotieren — neue Credentials
   nur in `/etc/systemd/system/shiksha.service.d/database.conf` als
   `Environment=DATABASE_URL=postgresql://…`.
2. `calendar_module.py` (und andere Funde) so umstellen, dass die
   Connection-URL aus `os.getenv("DATABASE_URL")` kommt — ohne
   Klartext-Default, harter Fail bei Abwesenheit.
3. Git-History des alten Passworts wird **nicht** rewritten — Rotation
   in (1) macht das alte Passwort kraftlos.
4. Pre-Commit-Hook für Secret-Detection (z.B. `gitleaks`, `trufflehog`)
   einrichten, damit Wiederholung früh auffällt.

**Plan:** Eigener Mini-Sprint nach Phase 6 — Titel-Vorschlag
`feat: env-driven config + secret rotation`. Geschätzt ~30 Min Arbeit
plus Server-Reload.

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
