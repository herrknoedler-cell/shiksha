# SHIKSHA · Living Architecture Map
**Stand: 30.04.2026** · Aktualisieren nach jeder Reality-Check-Session

> Das ist unser gemeinsames Arbeitspapier. Es zeigt:
> - Was läuft (✓), was hakt (🟡), was fehlt (❌)
> - Welche Module miteinander reden (oder nicht)
> - Welche Tabellen wo liegen, welche Daten wo fließen

---

## Module-Übersicht

| Modul | Status | DB-Tabellen | Endpoints | UI-Pfad | Notes |
|---|---|---|---|---|---|
| **Accounting** | ✓ live | accounting_*, bank_*, documents, payment_*, ledger_*, suppliers, chart_of_accounts | `/accounting/*` | `/accounting/ui/accounting/v4` | Voll im Einsatz mit Lunchbox-Daten |
| **Calendar** | ✓ existiert | calendar_events | `/calendar/*` | (kein eigenes UI) | Frühe Iteration — noch nicht mit KITA verknüpft |
| **Documents** | ✓ live | documents, document_field_candidates, document_links | `/documents/*` | (im accounting integriert) | OCR, MRZ, Field-Extraction |
| **KITA Compliance** | ✓ live | kita_groups, kita_staff_members, kita_child_enrollments, kita_compliance_*, personnel_ratios | `/kita/*` | `/accounting/ui/kita/dashboard` | WKTG/KBBG-Engine + ST%-Rechner |
| **KITA Legacy** | 🟡 migriert, nicht synchron | kita_legacy_children, kita_legacy_staff, kita_legacy_groups, kita_legacy_areas, kita_legacy_rooms | (read-only via /kita/groups/unified) | (separate App auf Port 8001) | **18 Kinder, 5 Mitarbeiter — echte Pilot-Daten!** |
| **KITA Anmeldung** | ✓ live | kita_documents, kita_document_fields, kita_parent_accounts | `/kita/anmeldung/*` | `/accounting/ui/kita/anmeldung` | 2-Signaturen-Wizard |
| **KITA Eltern-PWA** | ✓ live | (nutzt kita_parent_accounts.login_token) | `/kita/eltern/*` | `/accounting/ui/kita/eltern?t=...` | PWA-installierbar |
| **KITA Notifications** | ✓ live | kita_notifications, kita_notification_recipients | `/kita/notifications/*` | (im Dashboard) | Mail-Versand mit Holi-Template |
| **Identity** | ✓ live | identity_persons, identity_documents, identity_authorizations, identity_audit_log | `/identity/*` | `/accounting/ui/identity/wizard` | Cross-Edition · 3-Step-Capture |

---

## Bekannte Lücken & Verbindungs-Probleme

### 🟡 Lücke 1: Legacy-Daten ↔ Neue KITA-Tabellen
**Problem:** Die echten 18 Kinder + 5 Mitarbeiter liegen in `kita_legacy_*` Tabellen. Compliance-Engine, ST%-Rechner und Eltern-App nutzen aber `kita_groups`, `kita_staff_members`, `kita_child_enrollments`. Der `/kita/groups/unified` Endpoint ist nur ein Read-Wrapper.

**Was es heißt:**
- Wenn KITA-Leitung in der alten App auf Port 8001 ein Kind hinzufügt → erscheint NICHT in unserer Compliance-Auswertung
- Wenn wir per Anmelde-App ein Kind anlegen → erscheint NICHT in der Tagesbetrieb-App
- → 2 getrennte Welten

**Optionen:**
- **A.** Bidirektionaler Sync (Cron-Job)
- **B.** Alte App auf neue PG-Tabellen umstellen
- **C.** Alte App ablösen durch neuen Tab im Dashboard

### 🟡 Lücke 2: Calendar-Modul ↔ KITA
**Problem:** `calendar_events` existiert, aber niemand nutzt es. Im KITA-Kontext bräuchten wir Termine wie:
- "Elternabend am 12. Mai"
- "Wandertag Gruppe 3"
- "Krippe geschlossen wegen Sommerfest"
- Geburtstage der Kinder
- Personal-Krankenstand

**Was es heißt:**
- Mitteilungen-Modul könnte auf Termin-Events reagieren ("Erinnerung 1 Tag vor Elternabend")
- ST%-Rechner sollte Schließtage berücksichtigen

### 🟡 Lücke 3: Identity ↔ Kinder
**Problem:** Identity-Authorizations können `target_type='child'` mit `target_id=...` haben. Aber: Welche `target_id`? Aus `kita_legacy_children`? Aus `kita_child_enrollments`? Hängt das zusammen?

### ❌ Fehlend: Pädagogen-Mobile-App + Auto-Monitoring (Task #54)
**Was es bräuchte:**
- Mobile-friendly Eingabe der täglichen Anwesenheit pro Halbtag
- Cron der monatlich automatisch ST% berechnet
- Alert bei Förder-Lücke an Leitung

### ❌ Fehlend: Trägerin-Tab "🪪 Identitäten"
- Liste aller erfassten Personen mit Foto-Vorschau
- Verifizieren-Button
- Berechtigungs-Verwaltung

---

## Datenfluss-Skizze (vereinfacht)

```
┌─────────────────────────────────────────────────────────────┐
│                       SHIKSHA (Port 8000)                    │
└─────────────────────────────────────────────────────────────┘
              │                                    │
              │                                    │
       ┌──────▼──────┐                      ┌─────▼──────┐
       │  Documents  │◄──── OCR/MRZ ────────│  Identity  │
       └──────┬──────┘                      └─────┬──────┘
              │                                    │
              │                              ┌────▼────────┐
       ┌──────▼──────┐                       │ Authorizations│
       │ Accounting  │                       │ child / pickup│
       └──────┬──────┘                       └─────┬────────┘
              │                                    │
              │     ┌──────────────────────────────┤
              │     │
       ┌──────▼─────▼──────┐         ┌─────────────────────┐
       │  KITA Compliance  │◄────────│   KITA Legacy       │
       │  - groups          │  ?     │  - 18 Kinder        │
       │  - staff           │ Sync   │  - 5 Mitarbeiter    │
       │  - enrollments     │ FEHLT  │  - 8 Räume          │
       │  - st_calculations │        │  - 3 Bereiche       │
       └────────┬──────────┘         └─────────────────────┘
                │
       ┌────────▼─────────┐         ┌─────────────────────┐
       │  Anmeldung        │────────►│  Eltern-PWA          │
       │  - parent_accounts│ Token   │  - Mitteilungen      │
       │  - documents      │         │  - Profil            │
       └───────────────────┘         └─────────────────────┘
                │
       ┌────────▼─────────┐
       │  Notifications    │
       │  - alle / Gruppe  │
       │  - per Mail       │
       └───────────────────┘

       ┌───────────────────┐
       │  Calendar          │ ←── Verbindung zu KITA fehlt
       │  - events          │     (Termine, Geburtstage,
       │                    │     Schließtage, Krankenstand)
       └───────────────────┘

       ┌────────────────────────────────────┐
       │   shiksha-kita.service (Port 8001) │
       │   /opt/shiksha-kita/                │
       │   SQLite shiksha_kita.db            │
       │   ↓                                  │
       │   manage.html UI (Tagesbetrieb)     │
       │   - Anwesenheit                      │
       │   - Beobachtungen                    │
       │   - Vorfälle                         │
       │   - Räume                            │
       └────────────────────────────────────┘
```

---

## Priorisierung der nächsten Schritte

### Quick Wins (1-2 Tage)
1. **Legacy ↔ Neu Sync** als Cron-Script — bidirektional alle 5 Min
2. **Trägerin-Tab "Kinder & Mitarbeiter"** im Dashboard — zeigt Legacy-Daten lesbar mit Such+Filter
3. **Calendar-Wrapper für KITA** — `/kita/calendar/events` mit kita-spezifischen Event-Typen

### Mittel (3-5 Tage)
4. **Trägerin-Tab "Identitäten"** mit Foto-Galerie + Verifizieren-Button
5. **Pädagogen-PWA** für tägliche Anwesenheits-Erfassung
6. **Auto-Monitoring-Cron** für ST%-Berechnung mit Alert

### Groß (1-2 Wochen)
7. **Konsolidierung** alte App → neue Welt (alles in PostgreSQL, alte Codebase ablösen)
8. **Calendar-Integration** mit Mitteilungen + Identity (wer holt wann ab)
9. **DATEV-Export** + Lohnverrechnungs-Anbindung

---

## So arbeiten wir am besten zusammen

**Was Du mir gibst:**
- **Konkrete Beobachtungen** ("Schwester sagt: X funktioniert nicht, weil Y")
- **Screenshots + Logs** wenn Bugs auftreten
- **Excel/PDF/Foto** vom realen Workflow ("So machen die das aktuell")
- **User-Stories** ("Als KITA-Leitung will ich morgens auf einen Blick sehen ...")

**Was ich Dir gebe:**
- Architektur-Skizzen
- Code in deploybarem Zustand
- DB-Migrations + Endpoints + UI in einem Wurf
- Diese Map hier — ich aktualisiere sie nach jeder Session

**Format-Tipps für Deine Beobachtungen:**

```markdown
## Reality-Check 2026-04-30 — KITA Schwester

### Was funktioniert
- ...

### Was hakt
- Beim Klick auf X passiert Y, sollte Z sein
- Schwester sagt: "Wir brauchen unbedingt..."

### Fehlt komplett
- Workflow für ...
- Anbindung an ...

### Fragen offen
- Wie macht ihr das mit ...
```

So kann ich punktgenau die Architektur erweitern statt zu raten.

---

## Was ich von Dir jetzt brauchen würde

**Für die nächste Iteration:**

1. **Konkrete Schmerzpunkte** Deiner Schwester — was hat sie heute beim Reality-Check entdeckt?
2. **Calendar-Use-Cases** — was muss da rein? (Termine, Geburtstage, Schließtage, Personal-Urlaub?)
3. **Sync-Richtung** — soll die alte App weiter genutzt werden oder ablösbar?

Kein Stress — schick es einfach in beliebiger Form (Bullet, Sprachnachricht-zu-Text, Screenshots der alten App). Ich integriere es in diese Map und wir priorisieren gemeinsam.

— Stand 30.04.2026 · SHIKSHA Living Architecture Map
