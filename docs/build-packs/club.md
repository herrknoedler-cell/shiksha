# SHIKSHA — CLUB.EDITION BUILD PACK V1 (kompakt)

**Stand:** 25. April 2026
**Aufbaut auf:** SHIKSHA V4, CLUB-Module-Overview HTML (April 2026, 21 Module), SCHULE.EDITION + CAMPING.EDITION + safeguarding-Modul
**Zweck:** CLUB.EDITION-Profil aus der bestehenden Architektur deploy-bereit machen — kompakt, weil die Modul-Architektur bereits vollständig in `Shiksha Club Module Overview` spezifiziert ist.

---

## 1. STATUS IN EINEM SATZ

CLUB.EDITION ist die siebte SHIKSHA-Edition (nach business, restaurant, camp, stitch, schule, camping), spezialisiert auf eingetragene Vereine — Sportvereine, Musikvereine, Kulturvereine, Jugendverbände — mit **21 Modulen über drei Schichten** (3 bestehend, 15 generisch, 2 club-spezifisch + 1 optional Federation), und 8 USPs gegen ClubDesk, Easyverein, Vereinsflieger, SPG-Verein, Campai.

**Wichtig:** Die vollständige Modul-Architektur, alle Signale und USPs sind im interaktiven HTML schon dokumentiert (`Documents/Claude/Artifacts/shiksha-club-module-overview/`). Dieses Build-Pack ist die **deploy-orientierte** Verkürzung: Edition-Profil als JSON, Policies, Server-Stub.

---

## 2. EDITION-PROFIL (DEPLOY-FERTIG)

```json
{
  "edition": "club.shiksha",
  "version": "1.0.0",
  "lead_domain": "vereins_orchestrierung",
  "supporting_domains": [
    "scheduling",
    "communications",
    "payments",
    "safeguarding",
    "governance",
    "education"
  ],
  "modules_reused_phase_1": [
    "people",
    "membership",
    "participation",
    "activity",
    "resource",
    "safeguarding"
  ],
  "modules_reused_phase_2": [
    "volunteer",
    "partnership",
    "access",
    "community",
    "assembly"
  ],
  "modules_reused_phase_3": [
    "knowledge",
    "competency",
    "assessment",
    "funding"
  ],
  "modules_reused_optional": [
    "federation"
  ],
  "modules_reused_existing": [
    "document",
    "accounting",
    "calendar"
  ],
  "modules_new_club_specific": [
    "club_orchestrator",
    "club_board_copilot"
  ],
  "entities": [
    "Club",
    "Member",
    "MembershipType",
    "FeePlan",
    "Activity",
    "Group",
    "Resource",
    "Volunteer",
    "Partner",
    "Assembly",
    "Motion",
    "Vote",
    "Election",
    "Resolution",
    "Competency",
    "FundingApplication"
  ],
  "policies": [
    {
      "key": "club.no_auto_communication",
      "level": "block",
      "scope": "Gate 3 — Action",
      "rationale": "Vorstands-Kommunikation an Mitglieder NIE ohne explizite Freigabe."
    },
    {
      "key": "club.no_auto_resolution_execution",
      "level": "block",
      "scope": "Gate 3 — Action",
      "rationale": "JHV-Beschlüsse werden vom System als execution_action_json hinterlegt, aber Operator löst aus."
    },
    {
      "key": "club.safeguarding_required_for_minors",
      "level": "block",
      "scope": "Gate 1 — Intake",
      "rationale": "Bei Kinder-/Jugend-Sektionen ist safeguarding-Modul Pflicht."
    },
    {
      "key": "club.assembly_quorum_check",
      "level": "warn",
      "scope": "Gate 2 — Routing",
      "rationale": "Assembly-Beschlüsse ohne erfülltes Quorum werden als ungültig markiert."
    },
    {
      "key": "club.proxy_signature_required",
      "level": "block",
      "scope": "Gate 1 — Intake",
      "rationale": "Stimmrechts-Vollmachten bei Versammlungen sind formal validiert."
    },
    {
      "key": "club.no_auto_invoicing",
      "level": "block",
      "scope": "Gate 3 — Action",
      "rationale": "Mitgliedsbeitrags-Rechnungen sind Operator-Freigabe-pflichtig."
    },
    {
      "key": "club.discharge_protocol_complete",
      "level": "warn",
      "scope": "Gate 4 — Learning",
      "rationale": "Entlastung darf nicht übersprungen werden — System mahnt das."
    }
  ],
  "language_modes": ["flow", "action", "alert"],
  "reference_cases": [
    "CLUB_001 (Sportverein, ~250 Mitglieder, mit Jugend-Sektion und Kassenprüfung)",
    "CLUB_002 (Musikverein, ~80 Mitglieder, mit JHV und Vorstandswahlen)"
  ],
  "review_required_default": true,
  "club_module_overview_html": "Documents/Claude/Artifacts/shiksha-club-module-overview/"
}
```

---

## 3. SCHICHTEN-AUFBAU (aus dem CLUB-Overview-HTML)

```
┌── Schicht C — Club-spezifische Orchestrierung ────────┐
│  • club_orchestrator                                  │
│    Sammelt Signale, gruppiert nach Dimension,         │
│    gewichtet, erzeugt sprachfähige ClubState-Ausgabe. │
│    Sprache entsteht HIER (V4-Prinzip 3).             │
│                                                       │
│  • club_board_copilot                                 │
│    Vorstands-Assistenz: Protokoll-, Newsletter-,      │
│    Kassenprüfer-, JHV-Einladungs-Drafts.              │
│    Immer Draft, nie Versand.                          │
│    review_required = True hartverdrahtet.             │
└───────────────────────────────────────────────────────┘
              ▲ liefern Signale
┌── Schicht B — Generische Module (15) ────────────────┐
│  Phase 1: people · membership · participation        │
│           activity · resource · safeguarding         │
│  Phase 2: volunteer · partnership · access           │
│           community · assembly                       │
│  Phase 3: knowledge · competency · assessment        │
│           funding                                    │
│  Optional: federation                                │
│                                                      │
│  Diese Module sind editionsübergreifend wiederver-   │
│  wendbar (auch in SCHULE und CAMPING).               │
└──────────────────────────────────────────────────────┘
              ▲ schreiben in
┌── Schicht A — Bestehende Module (3) ─────────────────┐
│  • document   — V1.2 + V2-Erweiterung verfügbar     │
│  • accounting — Ledger, offene Posten                │
│  • calendar   — Events, Deadlines                    │
└──────────────────────────────────────────────────────┘
              ▲ liefern Daten
┌── Intelligenz-Views (keine eigenen Module) ──────────┐
│  • Retention                                         │
│  • Fördermittel-Match                                │
│  • Engagement                                        │
│  Vom Orchestrator gelesen, niemals geschrieben.      │
└──────────────────────────────────────────────────────┘
```

---

## 4. KERN-SIGNALE (Auswahl, vollständig im Overview-HTML)

| Signal-Key | Quelle | Dimension | Typische Nutzung |
|---|---|---|---|
| `membership.inactivity_detected` | membership | retention | Karteileichen-Hinweis |
| `membership.payment_late` | accounting → membership | finance | Zahlungs-Workflow |
| `participation.streak_broken` | participation | retention | Retention-Flag |
| `participation.overload_detected` | participation | volunteer | Trainer-Entlastung |
| `competency.evidence_missing` | competency | competency | Prüfungs-Planung |
| `partnership.contact_gap` | partnership | partnership | Pflege-Hinweis |
| `partnership.renewal_due` | partnership | partnership | Sponsoring-Zyklus |
| `safeguarding.credential_expiring` | safeguarding | safeguarding | Führungszeugnis-Erneuerung |
| `safeguarding.consent_missing` | safeguarding | safeguarding | Fahrten/Fotos blockieren |
| `volunteer.effort_skew` | volunteer | volunteer | „Arbeit auf drei Schultern" |
| `funding.match_found` | funding | funding | Antrags-Vorschlag |
| `community.lending_overdue` | community | community | Rückgabe-Erinnerung |
| `assembly.quorum_not_met` | assembly | assembly | Versammlung vertagen |
| `assembly.invitation_overdue` | assembly | assembly | Einladungsfrist läuft |
| `assembly.resolution_pending_execution` | assembly | assembly | Beschluss umsetzen |
| `assembly.protocol_signatures_missing` | assembly | assembly | Protokoll abschließen |
| `assembly.proxy_invalid` | assembly | assembly | Vollmacht klären |
| `assembly.discharge_skipped` | assembly | assembly | Entlastung nachholen |

---

## 5. DIE ACHT USPs (aus dem Overview-HTML, hier als Pitch-Anker)

| # | USP | Marketing-Satz |
|---|---|---|
| 1 | Lern-DNA im Kern | „Knowledge + Competency + Assessment sind im Zentrum, nicht als Bolt-on. Keine Konkurrenz positioniert einen Verein als lernende Organisation." |
| 2 | Sprachfähiger Co-Pilot | „Orchestrator erzeugt Narrative, nicht Dashboards. Vorstand bekommt ‚was ist los', nicht 47 Zahlen." |
| 3 | Safeguarding ab Tag 1 | „Schutzkonzept, Führungszeugnisse, Einverständnisse als Pflichtmodul. Großes Thema im Kinder-/Jugendbereich, das kaum eine Software sauber abbildet." |
| 4 | Signalgetrieben statt CRUD | „Module erzeugen Signale; Orchestrator interpretiert. Retention, Trainer-Entlastung, Sponsor-Chancen als proaktive Hinweise." |
| 5 | Hardware-Nähe | „access koppelt NFC, Kiosk, Spind direkt mit Teilnahme-Signalen. Löst echte Alltagsreibung." |
| 6 | Community-Layer | „Fahrten, Verleih, Mentoring bauen soziales Netz im Tool ab — nicht nur Verwaltung." |
| 7 | Beschlüsse als ausführbare Signale | „assembly liefert Resolutions mit execution_action_json — der Orchestrator überführt sie in Folge-Aktionen. Keine Konkurrenz verbindet JHV und Vereinsalltag so." |
| 8 | KI-Governance korrekt | „review_required = True, conservative_mode, explizite action_execution. KI als Entwurfs-Co-Pilot, nie Autopilot." |

---

## 6. SAFEGUARDING-INTEGRATION (kritisch für CLUB)

CLUB.EDITION nutzt das `safeguarding`-Modul (siehe `safeguarding/SAFEGUARDING_BUILD_PACK_V1.md`) als **Phase-1-Pflichtmodul**. Bei Kinder-/Jugend-Sektionen ist es **nicht optional**.

**Severity-Boost in CLUB:**

```python
CLUB_SAFEGUARDING_BOOSTERS: dict[str, str] = {
    "safeguarding.background_check_expiring": "high",   # Trainer ohne FZ darf nicht
    "safeguarding.consent_missing": "high",              # blockiert Fahrt/Foto
    "safeguarding.incident_unresolved": "high",
    "safeguarding.credential_expiring": "mid",
}
```

**Cross-Edition-Profitierung:**
CLUB lernt aus SCHULE-Yoga-Kinder und CAMPING-Familienbetrieb. Wenn dort Patterns promotet werden, erscheinen sie als info-Hinweise in CLUB.

---

## 7. WAS NOCH FEHLT FÜR CLUB-PRODUKTIV

Im Vergleich zu SCHULE und CAMPING ist CLUB **architektonisch vollständig** (das HTML-Overview hat alles), aber **deploy-technisch erst skizziert**.

Was zur Marktreife fehlt, falls ein Vereins-Pilot dazukommt:
- `club_db_migration.sql` — DB-Tabellen für die 21 Module (~25 Tabellen)
- `club_models.py` — Pydantic-Models für alle Entities
- `club_orchestrator.py` — Sprache + ClubState
- `club_board_copilot.py` — Draft-Generierung (Protokoll, Newsletter)
- 1–2 fiktive Vereins-Fixtures (Sportverein + Musikverein)
- 8–12 KI-generierte Vereins-Dokumente (JHV-Einladung, Beitragsmahnung, Förderantrag, Protokoll-Auszug etc.)
- UI-Mockups: Vorstands-Dashboard + Mitglieder-App

**Aufwand-Schätzung:** etwa wie ein SCHULE-Edition-Build-Pack — 2–3 Tage Arbeit.

**Wann lohnt sich das?**
Erst wenn ein konkreter Vereinspartner anfragt. Bis dahin reicht das interaktive HTML-Overview als Verkaufsargument („Ja, wir haben das schon durchdacht — hier ist die Architektur").

---

## 8. PILOT-ANSPRACHE

**Ideale Vereinspartner für CLUB.EDITION-Pilot:**

| Kriterium | Soll | Warum |
|---|---|---|
| Größe | 100–500 Mitglieder | Genug Komplexität, klein genug für direkten Vorstands-Draht |
| Sektionen | mindestens 2, idealerweise eine Jugend | Multi-Section-Komplexität sichtbar machen |
| Vorstand | aktiv, Übergangs-Phase ideal | Modernisierungs-Druck spürbar |
| Schutzkonzept | hat Bedarf, aber nicht Lösung | safeguarding-Modul macht direkt Wert |
| JHV-Erfahrung | mindestens eine letzte JHV strittig | assembly-Modul unmittelbar nützlich |
| Bisherige Software | ClubDesk, Easyverein oder Excel | Schmerz vorhanden |

**Konkrete Kandidaten DACH (zu validieren vor Ansprache):**

- Sportvereine in Vorarlberg (Bundesland-Sportverband-Kontakte über Bludenz-Wirtschaftsnetz)
- Musikvereine in Tirol/Bayern (Blasmusik-Verband-Strukturen)
- Yoga-/Achtsamkeits-Vereine in Wien (oft semiprofessionell organisiert)
- Tier-/Reitvereine im DACH-Alpenraum

---

## 9. WIEDEREINSTIEG NACH CHAT-VERLUST

```
1. CLUB.EDITION-Architektur ist vollständig im HTML-Overview
2. CLUB.EDITION-Build-Pack V1 (dieses File): nur Profil + Stub
3. Status:
   - Architektur: 21 Module, 8 USPs, vollständig in shiksha-club-module-overview HTML
   - Edition-Profile: section 2 (deploy-ready JSON)
   - Deploy: noch nicht gemacht — wartet auf konkreten Vereinspartner
4. Nächster Schritt:
   - Vereins-Pilot identifizieren
   - Dann analog SCHULE: DB-Migration + Models + Orchestrator + Fixtures + UI
   - safeguarding-Modul ist schon da (cross-edition), läuft sofort
```

---

## 10. LETZTER SATZ

CLUB.EDITION ist nicht erst dann real, wenn der erste Sportverein die JHV mit SHIKSHA bestreitet — sondern jetzt schon, weil 21 Module so durchdacht sind, dass ein Verein darin sich selbst wiedererkennt.

Stand: 25. April 2026 · Build-Pack V1 (kompakt) · architektonisch komplett, deploy-technisch wartet auf Pilot
