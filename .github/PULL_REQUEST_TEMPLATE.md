## Was diese PR tut

<!-- 1–3 Sätze: was, warum, betroffene Module/Editionen. -->

## Checklist

- [ ] Code läuft lokal (Python compile, betroffene Smoke-Tests durchgespielt)
- [ ] `bash deploy/scripts/sync.sh` (Dry-Run) zeigt erwartete Änderungen — Lösch-Liste geprüft
- [ ] Doku aktualisiert wenn nötig: `docs/ARCHITECTURE.md`, `docs/EDITIONS.md`, `docs/DEPLOY.md`, `CLAUDE.md`
- [ ] Neue Findings in [`docs/tech-debt.md`](../docs/tech-debt.md) getrackt (wenn relevant)
- [ ] Commit-Messages ehrlich (Was, Warum, Wie) — Conventional-Commit-Prefixe (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`) willkommen
- [ ] Wenn Endpoints geändert: keine an `kita_compliance_router.py` angehängt — neue `APIRouter`-Module bevorzugen

## Verwandte Issues / Schulden

<!-- "Closes #X", "Refs docs/tech-debt.md > Unfinished Refactors > …", oder Build-Pack-Hinweis -->
