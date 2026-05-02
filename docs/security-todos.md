# Sicherheits-Schulden

Lebende Liste bekannter Sicherheits-Findings, die identifiziert, aber noch
nicht behoben sind. Pro Eintrag: Severity, Fundstelle, Befund, Fix-Vorschlag,
geplanter Sprint.

Sobald ein Eintrag behoben ist: Eintrag streichen *und* den Fix-Commit hier
verlinken — die Git-History dieser Datei wird so zur Audit-Spur.

---

## Critical

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
   in (1) macht das alte Passwort kraftlos. History-Cleanup wäre nur
   nötig, wenn das alte Passwort an anderer Stelle weiterverwendet
   würde (DBs, externe Dienste).
4. Pre-Commit-Hook für Secret-Detection (z.B. `gitleaks`, `trufflehog`)
   einrichten, damit Wiederholung früh auffällt.

**Plan:** Eigener Mini-Sprint nach Phase 6 — Titel-Vorschlag
`feat: env-driven config + secret rotation`. Geschätzt ~30 Min Arbeit
plus Server-Reload.

---

## Wie ein neuer Eintrag aussieht

```markdown
### <kurze Beschreibung des Befunds>

|              |                            |
| ------------ | -------------------------- |
| **Severity** | Critical / High / Medium / Low |
| **Found**    | YYYY-MM-DD (Quelle / Sprint)   |
| **File**     | `pfad/zur/datei.py:Zeile`      |

**Befund:** <was ist los, in einem Absatz>

**Fix-Pfad:** <konkrete Schritte>

**Plan:** <wann / Sprint>
```
