# SHIKSHA Dev-Portal — Roadmap

**Stand:** 11. Mai 2026
**Foundation-Spec:** `SHIKSHA_DEV_PORTAL_ARCHITECTURE.md`
**Hinweis:** Strategisch — kein Pilot-Druck. Reihenfolge ist sauber, nicht eilig.

---

## Übersicht

```
Phase 1 · Foundation        →  ~3 Tage  · API steht, ein End-zu-End-Pfad funktioniert
Phase 2 · Frontend-Migration →  ~2 Tage · Mira-App + Kennenlernen auf Backend
Phase 3 · Dev-Console        →  ~3 Tage · Sessions-Browser, Persona-Editor, Memory
Phase 4 · Tools + Insights   →  ~2 Tage · Tool-Calling, Insight-Extraktion server-side
Phase 5 · Public API + Docs  →  später · OpenAPI, SDK, externe Devs
```

Gesamt grob ~10 Arbeitstage bis Phase 4. Public API als Phase 5 wenn die internen Strukturen tragen.

---

## Phase 1 — Foundation (~4 Tage)

**Ziel:** Backend läuft auf `api.shiksha.world`. Operator authentifiziert sich via Passkey im Presence-Switch. `POST /api/v1/chat/stream` streamt eine kontextuelle Antwort. Audit-Log läuft mit. Tool-Endpoints stehen als Skelett.

### Schritte

```
Repo + Foundation
  □ Repo-Struktur anlegen          (server/shiksha_engine/)
  □ FastAPI-Skelett                (main.py, deps.py, settings.py)
  □ Postgres-Schema shiksha_core    (Alembic-Migrations)
  □ SQLAlchemy-Models              (operators, organizations, sessions, …)
  □ Audit-Log-Middleware            (loggt Mutations automatisch)
  □ Caddy-Config                   (api.shiksha.world + dev.shiksha.world, TLS, CORS)
  □ systemd-Service                (shiksha-engine.service)
  □ .env mit Anthropic-Key         (chmod 600, owner shiksha-app)

Auth — WebAuthn / Passkey
  □ python-fido2 oder webauthn-py einbinden
  □ /api/v1/auth/register/begin     (challenge ausstellen)
  □ /api/v1/auth/register/finish    (Public-Key speichern)
  □ /api/v1/auth/login/begin        (assertion challenge)
  □ /api/v1/auth/login/finish       (signature prüfen, JWT)
  □ /api/v1/auth/me                 (Token-Verifizierung)
  □ /api/v1/auth/email-code         (Notausgang, E-Mail-OTP)

Chat — mit Streaming
  □ Persona-Loader                  (persona_prompts-Tabelle + In-Memory-Cache)
  □ /api/v1/chat/respond            (Block-Antwort)
  □ /api/v1/chat/stream             (SSE-Streaming, ab Phase 1 dabei)
  □ Memory-Injection                 (operator's memory → System-Prompt)
  □ Modus-Annotation                 (response wird mit PRÄSENZ/FOKUS/… markiert)

Tools — Skelett (echte Nutzung in Phase 4)
  □ /api/v1/tools/log_observation    (Endpoint da, von Anthropic noch nicht aufgerufen)
  □ /api/v1/tools/log_friction
  □ /api/v1/tools/save_day_summary
  □ Tool-Registry-Modul              (Vorbereitung für Function-Calling)

Seed
  □ Mira als Seed-Operator           (script: seed_mira.py)
  □ Thomas als Seed-Developer
  □ "tagesausklang"-Persona seeden    (aus SHIKSHA_RESPONSE_ENGINE.md)
  □ "kennenlernen"-Persona seeden
  □ Krummelus als Seed-Organization

Tests + Deploy
  □ curl-Tests                       (passkey register → login → /chat/stream)
  □ Deploy + Smoke-Test               (sync.sh-Style)
```

**Abnahme:** Thomas öffnet `api.shiksha.world/docs` (OpenAPI), authentifiziert sich mit Passkey, ruft `/chat/stream` und sieht Mira-typische SHIKSHA-Antworten Wort-für-Wort eintröpfeln. Im Audit-Log steht jeder Schritt.

**Warum SSE + Tool-Skelett + Audit-Log schon in Phase 1:**

```
SSE        → schwer nachzurüsten, macht alles spürbar lebendiger,
              halber Tag Mehraufwand der sich später zigfach zahlt
Tool-Skelett → die Endpoints anlegen kostet nichts, in Phase 4 sind sie
                schon da, Migration entfällt
Audit-Log    → Persona-Edits in Phase 3 wollen geloggt sein,
                Middleware nachträglich einbauen ist Refactor-Pain
```

**Warum kein Magic-Link/E-Mail-System in Phase 1:**

```
Passkey ist der Default. E-Mail-Code-Endpoint steht für Notausgang
da, SMTP-Setup kommt erst wenn der Notausgang wirklich gebraucht
wird — wahrscheinlich Phase 2 wenn Mira sich aus dem Bahnhof
einloggen will.
```

---

## Phase 2 — Frontend-Migration (~2 Tage)

**Ziel:** Mira-App und Kennenlernen-HTML rufen das Backend an. Browser hat keinen Anthropic-Key mehr.

### Schritte

```
□ ShikshaClient JS-Helper        (mira-app.js, kennenlernen.js):
                                  - login()
                                  - chatRespond()
                                  - getSessions()
                                  - getMemory()
                                  - addMemory()
□ Mira-App umbauen:
   - localStorage anthropic-key  → entfernt
   - localStorage shiksha-token  → neu (Bearer-Token)
   - Erst-Login-Flow             (Token via Magic-Link oder Init-Passwort)
   - chat/respond statt fetch    direkt zu Anthropic
   - Sessions vom Server laden   (nicht mehr localStorage)
   - Memory vom Server laden     (mit Cache für Offline)
□ Kennenlernen-HTML:
   - gleiche Migration
   - Token-Eingabe vereinfacht   (URL-Param ?token=… für Erst-Login)
□ Offline-Modus:
   - Service-Worker cacht letzte 10 Sessions
   - Bei Connection-Loss: Queue, später syncen
□ Smoke-Tests auf realen Geräten (Mira's iPhone, Thomas-Laptop)
```

**Abnahme:** Mira öffnet App auf iPhone, sieht Sessions, führt Tagesausklang, alles ohne Anthropic-Key im Browser.

---

## Phase 3 — Developer-Console (~3 Tage)

**Ziel:** Thomas hat einen Browser-Tab, in dem er das Pilot-System komplett überblickt und steuert.

### Schritte

```
□ /dev/index.html mit Tab-Skelett
□ /dev/login.html                (Master-Passwort + TOTP)
□ Dashboard-Tab:
   - Sessions-Count (heute/Woche/gesamt)
   - Streaks pro Trägerin
   - Avg. Session-Dauer
   - Token-Verbrauch
□ Sessions-Tab:
   - Tabelle mit Filter (Trägerin, Datum, Persona, Modus)
   - Klick → Modal mit Transkript + Insights
   - Export als JSON
□ Personae-Tab:
   - Liste aller Personae
   - Monaco-Editor für system_prompt
   - Speichern → neue Version anlegen
   - "Live testen"-Button (öffnet Test-Chat mit aktueller Prompt-Version)
□ Memory-Tab:
   - Pro Trägerin alle Einträge
   - Inline-Edit
   - Manueller Hinzufüger
   - Soft-Delete
□ Statistik-Endpoints (/api/v1/dev/stats)
□ Persona-Editor-Endpoints (/api/v1/dev/persona-prompts)
□ Master-Token-Auth-Middleware
□ Audit-Log (alle Dev-Actions in audit_logs-Tabelle)
```

**Abnahme:** Thomas öffnet `dev.shiksha.tun.zone`, loggt sich ein, sieht alle Mira-Sessions live, ändert den Tagesausklang-Prompt, neue Version greift sofort.

---

## Phase 4 — Tools + Insights (~2 Tage)

**Ziel:** SHIKSHA nutzt Function-Calling. Beobachtungen, Friction-Points und Insights landen automatisch in der DB — ohne dass Mira etwas explizit speichert.

### Schritte

```
□ Anthropic Tool-Definitions:
   - log_observation(kind, text)
   - log_friction(where, text)
   - save_day_summary(summary, highlights)
□ Tool-Handler im Backend:
   - tools/log_observation Endpoint
   - tools/log_friction Endpoint
   - tools/save_day_summary Endpoint
□ Persona-Prompts updaten:
   - Tagesausklang darf Tools nutzen
   - Wann: nach Pfad 1 (Liebevoller Satz) oder Pfad 5 (Frage)
   - Persona-Hint: "Wenn Mira eine Beobachtung erwähnt, log_observation aufrufen"
□ /api/v1/chat/respond erweitern:
   - Tool-Calls erkennen
   - Tools server-side ausführen
   - Tool-Results an Anthropic zurückspielen
   - Finale Antwort an Frontend
□ Insight-Extraktion bei Session-Close:
   - Eigener LLM-Call mit Sonder-Prompt
   - Insights → memory_entries
   - Summary → sessions.summary
□ Live-Stream-Endpoint (/api/v1/dev/sessions/live, SSE)
□ Dev-Console: Live-Stream-Tab
```

**Abnahme:** Mira erzählt "Lukas war heute toll", Backend ruft `log_observation` auf, Eintrag landet in DB, sichtbar in Dev-Console.

---

## Phase 5 — Public API + Docs (später)

**Ziel:** Externe Entwickler können auf SHIKSHA's Engine zugreifen. Edition-Builder, Plugins, Integrations.

### Schritte

```
□ OpenAPI-Auto-Generation        (FastAPI hat's eingebaut, nur sauber annotieren)
□ Public API-Surface trennen     (/api/v1/public/* vs. /api/v1/internal/*)
□ API-Keys statt JWT             (für externe Devs)
□ Rate-Limit-Tiers               (Free, Pilot, Production)
□ Python-SDK                     (shiksha-py via openapi-generator)
□ JS-SDK                         (shiksha-js)
□ Docs-Site                      (docs.shiksha.world)
□ Beispiel-Apps                  (Edition-Template, Plugin-Template)
□ Developer-Onboarding-Flow      (Sign-up, Verifizierung, erster Key)
```

**Abnahme:** Externer Entwickler kann in <30 Min eine eigene Edition-Variante bauen, die auf SHIKSHA-Engine aufsetzt.

---

## Abhängigkeiten + Kritischer Pfad

```
Phase 1 → blockiert alle anderen
Phase 2 → braucht Phase 1
Phase 3 → kann parallel zu Phase 2 starten (eigene Endpoints)
Phase 4 → braucht Phase 1 (für Tool-Endpoints)
Phase 5 → braucht Phase 1+2+3+4 (Public API auf reifem Internal)
```

Praktische Reihenfolge falls solo:

```
1 → 2 → 3 → 4 → 5
```

Falls zu zweit (Thomas + Co-Dev):

```
1 → (2 || 3) → 4 → 5
```

---

## Architektur-Entscheidungen — getroffen 11. Mai 2026

```
✓ Subdomain      → api.shiksha.world (Engine) + dev.shiksha.world (Console)
✓ DB             → existierende Postgres, neues Schema shiksha_core
                   edition-agnostisch für KITA/Camping/Schule/Surf/Yoga/Club
✓ Auth           → WebAuthn/Passkey via Presence-Switch-UI
                   E-Mail-OTP als Notausgang
✓ Streaming      → SSE schon in Phase 1
✓ Tool-Calling   → Skelett in Phase 1, aktive Nutzung in Phase 4
✓ Audit-Log      → in Phase 1 mit dabei
```

---

## Was nicht in dieser Roadmap steht

```
- Native iOS/Android-Apps (PWA bleibt vorerst)
- Voice-Input (separater Spec)
- Multi-Tenant-Billing (irrelevant bis kommerzielle Kunden)
- Backup/Restore-Tooling (Standard pg_dump reicht für Pilot)
- Monitoring/Alerting (Phase nach 5, wenn Produktion läuft)
```

---

**Roadmap · 11. Mai 2026 · 5 Phasen · ~10 Tage bis interner Stand · Phase 5 später**
