# SHIKSHA

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE.md)
[![Status](https://img.shields.io/badge/status-private%20alpha-yellow.svg)](#status)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](docs/DEPLOY.md)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](docs/ARCHITECTURE.md)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](docs/DEPLOY.md)

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

## Tech-Schulden

Bekannte Findings stehen in [`docs/tech-debt.md`](docs/tech-debt.md).
Stand: das ehemalige **Critical Security Debt** (hardcoded DB-Credentials)
ist code-seitig in Phase 7 aufgelöst — alle Connection-Strings laufen
jetzt über `DATABASE_URL` mit Hard-Fail-Pattern in `server/database.py`.
Server-seitige Passwort-Rotation und Cron-ENV-Setup folgen unmittelbar
danach.

Noch offen: ein **Unfinished Refactor** (Document-Compression-Split,
nicht Service-kritisch).

## Lizenz

MIT — siehe [`LICENSE.md`](LICENSE.md).
