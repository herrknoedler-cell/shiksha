# SHIKSHA

> **Lebendig · Lernend · Lieb**

SHIKSHA ist eine Plattform für KITAs, Campingplätze, Surf- und Yogaschulen,
Vereine und Schulen. Jede Edition teilt sich denselben Kern — Personen,
Identity, Kalender, Mitteilungen, Push, Archive, Marketing-Site-Generator —
und ergänzt nur das, was ihr Kontext braucht. Pilot ist die KITA-Edition,
seit Frühjahr 2026 mit 18 Kindern und 5 Mitarbeitenden im laufenden Betrieb;
sie bringt Compliance-Engine, Stellenprozent-Rechner, Trägerin-Dashboard
und je eine PWA für Pädagogen und Eltern mit.

Der Stack ist bewusst klein gehalten: Python 3.12 mit FastAPI, PostgreSQL 16,
Vanilla HTML/CSS/JS — Gridstack für Dashboards, GSAP für die Plattform-Site.
Ein Server, ein Service, ein Deploy. Editionen sind Konfiguration, nicht
Codeforks.

Dieses Repo enthält Code, Migrations, Templates, Deploy-Skripte und Doku.
Strategische Sketches, Visualisierungen und Outreach bleiben in Cowork —
siehe [`docs/COWORK.md`](docs/COWORK.md).

## Status

| Edition                         | Status   | Pilot                    |
|---------------------------------|----------|--------------------------|
| KITA                            | live     | `kita.shiksha.tun.zone`  |
| Camping                         | Beta     | —                        |
| Schule (Yoga / Surf / Reit / …) | geplant  | —                        |
| Club / Verein                   | geplant  | —                        |

## Schnellstart

```bash
git clone <repo> shiksha && cd shiksha
# Backend lokal: siehe docs/DEPLOY.md
# Deploy auf Server: deploy/scripts/sync.sh
```

Mehr: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) ·
[`docs/EDITIONS.md`](docs/EDITIONS.md) ·
[`docs/DEPLOY.md`](docs/DEPLOY.md)

## Sicherheits-Schulden

Bekannte, noch nicht behobene Findings stehen in
[`docs/security-todos.md`](docs/security-todos.md). Aktuell: ein
Critical-Finding (hardcoded DB-Credentials in `server/calendar_module.py`).
Wird nach der Migration in einem eigenen Sprint behoben.

## Lizenz

MIT — siehe [`LICENSE.md`](LICENSE.md).
