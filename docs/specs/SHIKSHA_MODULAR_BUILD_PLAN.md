# SHIKSHA — Modular Build Plan

**Status:** Bauplan · konsolidiert · verbindlich
**Stand:** 11. Mai 2026
**Cross-Reference:**
- `SHIKSHA_DEV_PORTAL_ARCHITECTURE.md` — Backend-Foundation
- `SHIKSHA_DEV_PORTAL_ROADMAP.md` — Backend-Phasen (technisch)
- `SHIKSHA_HERO_JOURNEY.md` — User-Bogen (sieben Phasen)
- `SHIKSHA_RESPONSE_ENGINE.md` — 4 Modi
- `VERDICHTEN_PHASE_SPEC.md` — Kennenlernen → Verdichten

---

## 1. Die drei verbindlichen Prinzipien

```
P1 · Mira-UX-First
     SHIKSHA nutzt erst etwas, wenn alles funktioniert.
     Aber jeder Schritt muss Mira's Handhabung sichtbar verbessern,
     damit sie nicht die Lust verliert.

P2 · Edition-agnostisch
     Jedes Modul muss für KITA, Camping, Schule, Surf, Yoga, Club
     gleich funktionieren. Edition-spezifisches wird konfiguriert,
     nicht kodiert.

P3 · Längerer Weg, der richtig ist
     Nicht das schnellste, sondern das, was trägt.
```

Alles weitere folgt diesen drei.

---

## 2. Module — das Inventar

Acht Module. Jedes mit klarer Verantwortung, klarem Interface, klarem Edition-Hook.

```
01  AuthModule              Wer ist Du? Passkey, JWT, Rollen.
02  ConversationModule      Chat-Engine mit 4 Modi + Streaming.
03  ExtractionModule        Was hat Mira gesagt? Tool-Calling, Daten-Capture.
04  WiederbeginnModule      Zwischen Sessions Brücke bauen. Memory + Summary.
05  GenerationModule        Webseite + Dashboard aus Conversation-Daten.
06  DashboardModule         Card-System, Anpassungs-Trigger.
07  HandoverModule          Web → Mobile per QR + Setup-Token.
08  NotificationModule      Push, Reminder, Cross-Device-Sync.
```

Jedes Modul lebt im Backend mit einer **edition-config-Schicht**: zur Laufzeit wird die Edition reingegeben, das Modul passt sich an. Frontend-Pendants (HTML-Components) sind ebenfalls config-driven.

---

## 3. Edition-Pluggability — die Architektur-Regel

```python
# Pseudocode — gilt für jedes Modul
class ConversationModule:
    def __init__(self, edition: str, config: EditionConfig):
        self.persona_prompts = config.persona_prompts_for(edition)
        self.tool_set = config.tools_for(edition)
        self.vocabulary = config.vocabulary_for(edition)
        ...
```

Edition-Config-Inhalt pro Edition:

```yaml
kita:
  persona_prompts:
    tagesausklang: "kita.tagesausklang.v2"
    kennenlernen:  "kita.kennenlernen.v1"
  tools:
    - log_observation
    - log_friction
    - save_day_summary
    - record_kita_event       # KITA-spezifisch
  vocabulary:
    operator_role: "Trägerin"
    org_word: "KITA"
    member_word: "Kind"
    pain_words: ["Zettelei", "Wochenend-Anrufe", "Personalausfall"]
  dashboard_cards:
    - st_percent
    - compliance
    - eltern_inbox
    - beobachtungen
  site_template: "kita_v3"

camping:
  persona_prompts:
    tagesausklang: "camping.tagesausklang.v2"
    kennenlernen:  "camping.kennenlernen.v1"
  tools:
    - log_observation
    - log_friction
    - save_day_summary
    - record_booking          # Camping-spezifisch
  vocabulary:
    operator_role: "Wirt"
    org_word: "Campingplatz"
    member_word: "Gast"
    pain_words: ["Belegung", "No-Shows", "Wetter"]
  dashboard_cards:
    - belegung
    - bookings
    - weather
    - gast_inbox
  site_template: "camping_v1"

# … schule, surf, yoga, club
```

**Konsequenz für die Module:**

| Modul | Was edition-spezifisch ist | Was generisch bleibt |
|---|---|---|
| Auth | nichts | Komplettes WebAuthn-Flow |
| Conversation | Persona-Prompt, Vokabular | 4-Modus-Engine, Streaming, Signal-Detection |
| Extraction | Tool-Set, Schema-Felder | LLM-Call, Validierung, Persistenz |
| Wiederbeginn | Memory-Template-Strings | Summary-Generation, Bestätigungs-UI |
| Generation | Site-Template, Card-Set | Pipeline-Orchestration, Subdomain-Provisioning |
| Dashboard | Card-Inventory, Hero-Texte | Gridstack, Layout-Persistenz |
| Handover | nichts | QR, Setup-Token, Passkey-Registration |
| Notification | Reminder-Default-Zeit | VAPID, Push-Subscriptions, Cross-Device |

---

## 4. Build-Reihenfolge — acht Schritte

Jeder Schritt hat:
- **Ziel** (was am Ende läuft)
- **Mira-Spürbarkeit** (was Mira nach diesem Schritt anders erlebt)
- **Edition-Hook** (was eingebaut wird, damit Schritt N+1 für jede Edition trägt)

### Schritt 1 — AuthModule + Backend-Foundation (~4 Tage)

**Ziel:** Backend läuft auf `api.shiksha.world`. Passkey-Auth funktioniert. SQL-Schema `shiksha_core` ist da. Audit-Log mitläuft.

**Mira-Spürbarkeit:** noch nichts. Sie merkt's erst in Schritt 3.

**Edition-Hook:** Operator-Tabelle hat `edition`-Spalte. Organizations-Tabelle. Persona-Prompts haben `edition`-Spalte mit `*` als Wildcard.

**Dann:** `curl /api/v1/chat/respond` funktioniert mit beliebiger Edition.

---

### Schritt 2 — ConversationModule mit 4 Modi + Streaming (~2 Tage)

**Ziel:** `/api/v1/chat/stream` läuft als SSE. Persona-Prompt aus DB. Signal-Detection im Backend. Memory-Block injiziert.

**Mira-Spürbarkeit:** noch nichts.

**Edition-Hook:** `chat/stream?edition=kita` lädt KITA-Persona. Vokabular wird im System-Prompt ersetzt (Trägerin vs. Wirt vs. Lehrer).

**Dann:** Jede Edition kann mit derselben Engine sprechen — nur Worte tauschen sich.

---

### Schritt 3 — Frontend-Migration: Kennenlernen + Mira-App (~2 Tage)

**Ziel:** Beide Frontends rufen Backend an. Token statt API-Key. localStorage-Memory wandert auf Server.

**Mira-Spürbarkeit:** **GROSS.** Mira braucht keinen Anthropic-Key mehr. Login per Presence-Switch.

**Edition-Hook:** Frontends lesen `?edition=` aus URL und passen Vokabular an. `kita.shiksha.world` → KITA-Frontend. Generisches `app.shiksha.world` wählt nach Subdomain oder per Switch.

**Dann:** Mira hat saubere Erfahrung. Phase A + B fühlen sich produktiv an.

---

### Schritt 4 — ExtractionModule: Tool-Calling aktiv (~2 Tage)

**Ziel:** Anthropic ruft `log_observation`, `log_friction`, `extract_org_info` während Mira spricht. Daten landen in DB.

**Mira-Spürbarkeit:** SHIKSHA "merkt sich" Dinge sichtbar besser. Wiederbeginn am Folgetag fühlt sich präziser an.

**Edition-Hook:** Tools sind je Edition unterschiedlich. KITA hat `record_kita_event`, Camping hat `record_booking`. Persona-Prompt deklariert pro Edition welche Tools verfügbar sind.

**Dann:** Datenbank füllt sich automatisch während Conversation.

---

### Schritt 5 — WiederbeginnModule: die fehlende Phase C (~3 Tage)

**Ziel:** Wenn Mira nach Tagen wiederkommt: Wiederbeginn-Zusammenfassung wird automatisch generiert, im UI als Stage gezeigt, Bestätigungs- und Korrektur-Flow läuft. Stammdaten-Vertiefung als kompakte editierbare Karte. Generation-Trigger am Ende.

**Mira-Spürbarkeit:** **HUGE.** SHIKSHA erkennt sie wieder. Das Versprechen *„Da hört jemand zu. Und es bleibt nicht verloren."* wird sichtbar gehalten.

**Edition-Hook:** Wiederbeginn-Zusammenfassungs-Prompt ist edition-agnostisch, zieht aber edition-spezifisches Vokabular aus der Memory.

**Dann:** Phase B → C → D wird durchgängig.

---

### Schritt 6 — GenerationModule: Auto-Build der Webseite + Dashboard-Setup (~3 Tage)

**Ziel:** Aus den extrahierten Daten wird Webseite + Dashboard generiert. Subdomain provisioning via Caddy + DNS-API. Bauanimation während es läuft. Live-Update wenn fertig.

**Mira-Spürbarkeit:** **DAS WOW.** Sie sieht ihre eigene Webseite live entstehen.

**Edition-Hook:** Generation-Pipeline ist generisch, lädt aber edition-spezifische Templates + Card-Sets. KITA bekommt KITA-Site, Camping bekommt Camping-Site — gleiche Pipeline.

**Dann:** Phase D funktioniert. Schaufenster ist real.

---

### Schritt 7 — DashboardModule + Übergangs-Choreographie (~2 Tage)

**Ziel:** Chat-Raum endet, Dashboard erscheint als nächste Stage. Hero-Card mit SHIKSHA-Begrüßung. Anpassungs-Trigger aus Card-Klick öffnet Mini-Chat.

**Mira-Spürbarkeit:** Sie tritt in *ihr* SHIKSHA ein. Kein Bruch zwischen "habe gesprochen" und "habe ein Produkt".

**Edition-Hook:** Dashboard-Card-Inventar pro Edition. Hero-Texte pro Edition.

**Dann:** Phase E sitzt.

---

### Schritt 8 — HandoverModule + NotificationModule (~3 Tage)

**Ziel:** Aus Dashboard: QR-Code-Modal. Mira scannt mit Phone. PWA installiert sich. Passkey registriert. App ist auf Home-Screen. Server-Push aktiviert (VAPID + Push-Subscriptions). Tagesritual-Reminder läuft echt.

**Mira-Spürbarkeit:** SHIKSHA ist nicht mehr im Browser. SHIKSHA ist *bei ihr*.

**Edition-Hook:** App-Icon pro Edition. Reminder-Default-Zeit pro Edition (KITA 17:30, Camping 21:00, Schule 17:00, Surf 19:00, …).

**Dann:** Phase F + G sind real. Mira kann täglich dabeibleiben.

---

## 5. Aufwand-Schätzung — gesamt

```
Schritt 1  AuthModule + Backend-Foundation       ~4 Tage
Schritt 2  ConversationModule + Streaming         ~2 Tage
Schritt 3  Frontend-Migration                     ~2 Tage
Schritt 4  ExtractionModule                       ~2 Tage
Schritt 5  WiederbeginnModule (Phase C)           ~3 Tage
Schritt 6  GenerationModule (Phase D)             ~3 Tage
Schritt 7  DashboardModule + Übergang             ~2 Tage
Schritt 8  HandoverModule + NotificationModule    ~3 Tage
─────────────────────────────────────────────────
Summe                                              ~21 Tage
```

Vier bis fünf Wochen. Drei Wochen wenn parallel gearbeitet wird.

**Wann läuft was für Mira spürbar:**

```
Nach Schritt 3 (~8 Tage):   Mira-UX ist sauber, kein Hack mehr.
Nach Schritt 5 (~13 Tage):  Phase C läuft, Wiederbeginn echt.
Nach Schritt 6 (~16 Tage):  Das Wow ist da — Generation live.
Nach Schritt 8 (~21 Tage):  Alles durchgängig, alle Phasen real.
```

Das ist die Kurve, an der wir Mira halten.

---

## 6. Was nach Schritt 8 noch fehlt (Folge-Sprints)

Bewusst nicht in den ersten 21 Tagen:

```
- Public API für externe Entwickler (Phase 5 der Backend-Roadmap)
- Edition-Templates für Schule, Surf, Yoga, Club (jeweils ~2 Tage,
  reine Konfiguration + Site-Templates)
- Voice-Input für Tagesausklang
- Wochenrückblick + Insights-Visualisierung im Dashboard
- Multi-Operator-Setup (Mira + Mama, Co-Wirt:innen, etc.)
- Land-Audit-Export (KGG)
- Vertrags-Generator
- Backup/Restore-Tooling
- Monitoring/Alerting (Sentry, Grafana)
```

Diese sind alle aufbauend. Edition-Agnostizität in den ersten 21 Tagen sorgt dafür, dass jede dieser Erweiterungen schneller geht.

---

## 7. Konkreter Vorschlag: wir fangen mit Schritt 1 an

**Was ich jetzt baue:**

1. Repo-Struktur `server/shiksha_engine/`
2. FastAPI-Skelett (main.py, deps.py, settings.py)
3. Alembic-Migration für `shiksha_core`-Schema (alle Tabellen)
4. SQLAlchemy-Models (Operator, Organization, Session, Message, Memory, …)
5. WebAuthn-Auth-Endpoints (register/begin, register/finish, login/begin, login/finish, me)
6. Audit-Log-Middleware
7. Caddy-Config + systemd-Service
8. `.env`-Template + Secrets-Management
9. Seed-Script für Mira (Krummelus, KITA) + Thomas (Developer)
10. Persona-Prompts seed: `kennenlernen.kita`, `kennenlernen.*`, `tagesausklang.kita`, `tagesausklang.*`
11. Tests: pytest mit Login → /chat/respond → DB-Check

**Was Du am Ende von Schritt 1 hast:**

```
- Backend deployed auf api.shiksha.world
- curl -X POST /api/v1/auth/login/begin  → WebAuthn-Challenge
- Browser-Demo zum Registrieren (presence_switch.html erweitert)
- curl /api/v1/chat/respond mit Token → echte Anthropic-Antwort,
  edition-aware
- audit_logs in DB sieht jeden Schritt
- pgAdmin oder psql zeigt 0 Sessions, dafür seed-Daten für Mira + Thomas
```

**Aufwand:** ~4 Tage konzentrierte Arbeit. Davon ~1 Tag WebAuthn (kennt nicht jeder), ~1 Tag Schema + Migration, ~1 Tag FastAPI + Routen, ~1 Tag Tests + Deploy.

**Soll ich loslegen?** Wenn ja, beginne ich mit der Repo-Struktur und arbeite die Liste oben ab, lade Dateien iterativ in `/outputs/server/shiksha_engine/`.

---

**Plan · 11. Mai 2026 · 8 Module · 21 Tage · edition-agnostisch · Mira-UX-first**
