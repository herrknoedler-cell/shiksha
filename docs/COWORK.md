# Was bleibt in Cowork

SHIKSHA hat zwei Heimaten: dieses Git-Repo (Code, Deploy, Doku) und
Cowork (strategische Sketches, Visualisierungen, Outreach). Die
Trennung ist bewusst — Cowork ist gut im Skizzieren und Strategie-
Pingpong, ein Git-Repo ist gut im sauberen Versions-Tracking. Was wo
hingehört:

---

## Hier (Git-Repo)

- Code (`server/`, UI-Subdirs)
- DB-Migrations (`server/*_migration.sql`)
- Templates (`server/marketing_templates/`)
- Deploy-Skripte (`deploy/scripts/`)
- Build-Packs als lebende Dokumente (`docs/build-packs/`)
- Architektur-Map (`docs/architecture-map.md` — wird hier weiter gepflegt)
- Tech-Debt-Tracker (`docs/tech-debt.md`)
- Test-Daten + Smoke-Tests (`tests/`)
- Legacy-Code-Snippets (`docs/legacy/`) — Audit-Refs für noch-im-Omnibus-
  lebende Cowork-Originale

## In Cowork

Pfad zu den Cowork-Outputs (auf Thomas's Mac):

```
~/Library/Application Support/Claude/local-agent-mode-sessions/<session-id>/
   …/local_<id>/outputs/
```

### Tagebuchartige Dokumente

Datums-kontextuelle Snapshots — gehören in Cowork:

- `MASTER_INDEX.md`, `MASTER_INDEX_V2.md` — File-Listen aus früheren
  Sessions (~Apr 25/26)
- `WAS_DU_JETZT_TUN_KANNST.md` — Action-Item-Sammlung aus früherem
  Reality-Check
- `MIGRATION_PROMPT.md` — der Sprint-Prompt zur Cowork→Git-Migration selbst
- `SHIKSHA_MARKTANALYSE_SCHULE_CAMPING_V1.md` — Marktanalyse zum Stichtag
  25.04.2026

### Outreach + Pilot-Onboarding

Marketing- und Pilot-Material:

- `outreach/OUTREACH_EMAILS_PACK.md` — E-Mail-Templates für Pilot-Akquise
- `outreach/PILOT_ONBOARDING_8_WOCHEN.md` — Onboarding-Plan
- `outreach/PILOT_VERTRAG_TEMPLATE.md` — Vertrags-Vorlage
- `outreach/FOTO_DEMO_STORYBOARD.md` — Demo-Storyboard
- `outreach/pilot_demo_walkthrough.html` — Demo-Walkthrough

### Strategie-Sketches und Visualisierungen

Frühe Architektur-Skizzen, die teils ins Repo migriert wurden, teils
als Ideenarchiv in Cowork bleiben — z.B. die early Module-Overview-
HTMLs, Edition-Sketches, die nie zu Code wurden.

---

## Migration zwischen den Welten

Wenn ein Cowork-Dokument von "Skizze" zu "lebendes Doku" wird:
manuell ins Repo migrieren (`docs/`), Stand-Datum als Anker im
Frontmatter behalten. Phase 2 dieser Migration hat das mit dem
Architecture-Map und allen Build-Packs gemacht — sie sind seither
hier zuhause.

Wenn etwas im Repo veraltet und tagebuchartig wird: nach `docs/legacy/`
verschieben oder löschen (Git-History bleibt).

Wenn unsicher: **lieber in Cowork halten und manuell ziehen, wenn
nötig.** Das Repo soll der einzige Quell-State für *Code* sein, nicht
unbedingt für jede strategische Notiz.
