# SHIKSHA.REPAIR — Lokal-Netzwerk-Konzept V0.1

**Stand:** 3. Mai 2026
**Status:** Konzept-Skizze (Vision-Layer, kein Code-Sprint vor 2027)
**Cross-Reference:** `master_vision.md` Sektion 7

---

## 1. Die Position — was SHIKSHA hier ist

**SHIKSHA baut keinen Scanner. SHIKSHA baut keinen Drucker. SHIKSHA baut keinen Repair-Algorithmus.**

SHIKSHA baut das **Lokal-Netzwerk**, das vorhandene Geräte mit vorhandenem Bedarf verbindet — und damit den Lieferweg radikal verkürzt.

### Analogie

| Plattform | baut nicht | baut |
|---|---|---|
| Uber | Autos | Routing-Logik |
| Airbnb | Hotels | Vertrauens-Marktplatz |
| Spotify | Musik | Distribution + Discovery |
| **SHIKSHA.REPAIR** | **Drucker / Scanner / Repair-KI** | **lokales Reparatur-Netzwerk** |

### Strategischer Kern

Drei Werte gleichzeitig in einem Auftrag:

```
Climate-Win   →  Ersatzteil aus Nachbardorf statt aus China
                 (CO2-Ersparnis pro Auftrag berechnet)

Time-Win      →  4 Stunden statt 4 Tage
                 (gerade bei kleinen Reparaturen Game-Changer)

Community-Win →  Lokale Maker, Werkstätten, Schul-3D-Drucker
                 verdienen mit. Geld bleibt im Tal.
```

Das ist eine **dreifach-positive Geschichte**, die keine zentrale Plattform (Amazon, Alibaba) erzählen kann.

---

## 2. Die Akteure

### User (Bedarf)

Mitglieder der SHIKSHA-Editionen, die ein Reparatur-Bedürfnis haben:

- **KITA-Trägerin:** "Die Lasche von der Bauklotz-Kiste ist abgebrochen, das Modell gibt's nicht mehr."
- **Camping-Betreiber:** "Stellplatz-7-Strom-Anschluss-Klappe hängt durch, Original-Hersteller ist insolvent."
- **Boots-Vercharterer:** "Ruder-Halterung an Boot 12 ist gerissen, ein Pin fehlt."
- **Privatperson** (später, bei Public-Launch): "Mein Kaffeemaschinen-Trichter ist gebrochen."

**Was sie mitbringen:** Ein Foto oder eine fertige `.stl`-Datei. Das war's.

### Maker (Angebot)

Lokale 3D-Druck-Kapazität:

- **Hobby-Maker** mit FDM-Drucker zu Hause (Prusa, Bambu, Creality)
- **Maker-Spaces** (Vorarlberg hat z.B. die FAB Lab Dornbirn)
- **Schulen / HTLs** mit 3D-Druck-Werkstatt
- **Lokale Werkstätten** mit professionellen Geräten (SLA, MJF)

**Was sie mitbringen:** Zeit + Material + Drucker. Plus Bereitschaft, Aufträge anzunehmen.

### SHIKSHA (Vermittler)

Was SHIKSHA als Vermittler leistet:

- **Drucker-Registry** mit Geo-Standort + Material-Inventar + Auslastung
- **Auftrag-Routing** nach Distanz, Material, Druckvolumen, Bewertung
- **Trust-Layer** — Bewertungen, Streitschlichtung, Garantie
- **Bezahlungsabwicklung** (Stripe Connect oder ähnlich)
- **Marken-Klammer** — *"shiksha-smart Reparaturservice"*

---

## 3. Was SHIKSHA NICHT bauen muss

Klare Liste, was wir an existierende Tools auslagern:

| Aufgabe | Existierender Service / Tool |
|---|---|
| 3D-Scan vom Smartphone | **Polycam**, **Luma AI**, **Apple Object Capture**, **Kiri Engine** |
| Scan-Reparatur (Mesh-Holes) | **Meshmixer** (gratis), **Meshy.ai**, manuell durch Maker im Slicer |
| Slicer (Modell → G-Code) | **Cura**, **PrusaSlicer**, **Bambu Studio** — kostenlos, vom Maker betrieben |
| Modell-Bibliothek (für Standard-Teile) | **Printables**, **Thingiverse**, **MakerWorld** |
| Bezahl-Infrastruktur | **Stripe Connect** (Marketplace-Mode) |
| Kartendienst für Geo-Routing | **OpenStreetMap** + **Mapbox/Leaflet** |

Jeder Akteur bringt seine eigenen Werkzeuge mit. SHIKSHA verbindet, statt zu rebuild'en.

---

## 4. Was SHIKSHA baut — die Reparatur-Engine

### 4.1 Drucker-Registry

```sql
CREATE TABLE printers (
    id              SERIAL PRIMARY KEY,
    operator_id     INT REFERENCES users(id),
    name            TEXT NOT NULL,             -- "Bambu Lab P1S in Dornbirn-Süd"
    location        GEOGRAPHY(POINT),          -- PostGIS für Geo-Queries
    address         TEXT,                       -- für Abholung/Versand
    technology      TEXT,                       -- 'FDM' | 'SLA' | 'MJF' | 'SLS'
    build_volume    JSONB,                      -- {x: 256, y: 256, z: 256}
    materials       TEXT[],                     -- ['PLA', 'PETG', 'TPU']
    hourly_rate     DECIMAL,                    -- € pro Stunde Druckzeit
    pickup_options  TEXT[],                     -- ['pickup', 'local_post', 'delivery']
    rating_avg      DECIMAL DEFAULT 0,
    rating_count    INT DEFAULT 0,
    available       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_printers_location ON printers USING GIST(location);
```

### 4.2 Reparatur-Aufträge

```sql
CREATE TABLE repair_jobs (
    id                  SERIAL PRIMARY KEY,
    requester_id        INT REFERENCES users(id),
    edition             TEXT NOT NULL,          -- 'kita', 'camping', 'mobility'
    title               TEXT NOT NULL,          -- "Bauklotz-Kiste Lasche"
    description         TEXT,
    requester_location  GEOGRAPHY(POINT),
    
    -- Was gedruckt werden soll
    model_file          TEXT,                   -- S3-URL der .stl/.obj
    material_preferred  TEXT,                   -- 'PLA' / 'PETG'
    quantity            INT DEFAULT 1,
    
    -- Wirtschaft
    budget_max          DECIMAL,                -- € (User legt Maximum fest)
    actual_price        DECIMAL,                -- nach Zuschlag
    
    -- Status
    status              TEXT NOT NULL,          -- 'open' | 'matched' | 'printing' | 'ready' | 'delivered' | 'completed' | 'cancelled'
    matched_printer_id  INT REFERENCES printers(id),
    
    -- Climate-Tracking
    co2_saved_kg        DECIMAL,                -- berechnet vs. Versand-Alternative
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE repair_messages (
    id          SERIAL PRIMARY KEY,
    job_id      INT REFERENCES repair_jobs(id),
    sender_id   INT REFERENCES users(id),
    content     TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE repair_ratings (
    id          SERIAL PRIMARY KEY,
    job_id      INT REFERENCES repair_jobs(id),
    rater_id    INT REFERENCES users(id),
    rated_id    INT REFERENCES users(id),     -- Maker oder Requester
    score       INT,                            -- 1-5
    comment     TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);
```

### 4.3 Routing-Algorithmus

```python
def find_best_printer(job: RepairJob) -> Optional[Printer]:
    """
    Findet den passenden Drucker für einen Reparatur-Auftrag.
    
    Kriterien (gewichtet):
    1. Distanz (kleiner = besser, Climate + Time)
    2. Material verfügbar
    3. Druckvolumen passt
    4. Drucker verfügbar (nicht ausgelastet)
    5. Bewertung (Trust)
    6. Preis im Budget
    """
    candidates = (
        Printer.query
        .filter(Printer.available == True)
        .filter(Printer.materials.contains([job.material_preferred]))
        .filter(Printer.build_volume_fits(job.model_dimensions))
        .filter(Printer.hourly_rate * job.estimated_hours <= job.budget_max)
        .order_by(
            Printer.location.distance(job.requester_location),  # erst nach Distanz
            -Printer.rating_avg,                                  # dann nach Bewertung
        )
        .limit(5)
        .all()
    )
    
    return candidates[0] if candidates else None
```

### 4.4 Climate-Tracker

Pro Auftrag berechnen + sichtbar machen:

```python
def calculate_co2_saved(job: RepairJob, printer: Printer) -> float:
    """
    CO2-Ersparnis vs. Alternative (Versand aus China).
    
    Annahme: Original-Ersatzteil hätte ~0.5 kg CO2 pro 100g 
    Material in Versand-Footprint. Lokal gedruckt: ~0.05 kg pro 100g.
    """
    weight_g = estimate_weight(job.model_file, job.material_preferred)
    distance_km = job.requester_location.distance(printer.location)
    
    co2_shipping = (weight_g / 100) * 0.5
    co2_local    = (weight_g / 100) * 0.05 + distance_km * 0.0002
    
    return max(co2_shipping - co2_local, 0)
```

Sichtbar im Dashboard: *"Mit dieser Reparatur hast Du 380 g CO2 gespart. SHIKSHA-KITA-Krummelus: 4.2 kg dieses Jahr."*

---

## 5. User-Flow (MVP)

### Auftrag stellen — KITA-Trägerin Heidi

```
1. Heidi sieht: "Bauklotz-Kiste hat eine kaputte Lasche, ich brauche
   ein Ersatzteil."

2. Heidi klickt im SHIKSHA-Dashboard auf "Reparatur-Auftrag stellen".

3. SHIKSHA fragt im Chat:
   - "Hast Du eine Datei für das Teil? Wenn nicht, mach 5-10 Fotos
      mit der Polycam-App und lade die fertige .stl bei mir hoch."
   - "Welches Material soll's sein? Bei KITA-Spielzeug empfehle
      ich PETG (lebensmittelecht, robust)."
   - "Wann brauchst Du's? Eilig (24h)? Diese Woche?"
   - "Was zahlst Du maximal?"

4. SHIKSHA findet drei Drucker im Umkreis (10/25/40 km).
   Heidi bekommt eine Übersicht:
   - Anna F. (Maker-Space FAB Lab Dornbirn) — 12 km, ★★★★★, 8€
   - Tobias H. (privat, Bregenz) — 25 km, ★★★★☆, 5€
   - HTL Rankweil (3D-Werkstatt) — 35 km, ★★★★★, 6€

5. Heidi wählt Anna F. → Auftrag wird geschickt.

6. Anna druckt, schreibt im Chat: "Fertig, kannst Du Donnerstag
   abholen oder soll ich's vorbeibringen?"

7. Heidi: "Ich komme. Donnerstag 16 Uhr passt."

8. Heidi holt ab, zahlt 8€ via SHIKSHA (Stripe), bewertet Anna mit 5
   Sternen.

9. Climate-Tracker im Dashboard: "Du hast 380g CO2 gespart. Plus
   Anna 8€ verdient. Plus Du musstest nicht 14 Tage auf China-Versand
   warten."
```

### Maker-Onboarding — Anna F.

```
1. Anna sieht auf shiksha.world/repair-network: "Wirst Du Maker
   im SHIKSHA-Netzwerk?"

2. Sie klickt → Conversational-Onboarding:
   - "Hallo. Schön, dass Du dabei sein willst."
   - "Wie heißt Du?"
   - "Wo druckst Du?"
   - "Welcher Drucker? Welches Material?"
   - "Welche Stundenrate findest Du fair?"
   - "Wie soll man bei Dir abholen?"

3. Anna registriert ihren Bambu Lab P1S, materials=["PLA","PETG","TPU"],
   hourly_rate=2€, pickup_options=["pickup"].

4. Sie ist live im Netzwerk. SHIKSHA pushed ihr passende Aufträge.
```

---

## 6. Trust + Bezahlung

### Trust-Layer (MVP)

**Phase 1 (Pilot):** Maker und Requester sind beide SHIKSHA-Mitglieder. Vertrauen via Mitgliedschaft. Keine externe Verifikation.

**Phase 2 (Public):** Bewertungssystem (5-Sterne, Kommentare). Ab 5 Aufträgen wird Bewertung sichtbar. Streit-Mediation durch SHIKSHA-Support.

**Phase 3 (Skalierung):** Verifizierungs-Stufen:
- ★ Maker (registriert)
- ★★ Maker (5+ Aufträge, ⩾4.5★)
- ★★★ Trusted Maker (Identitäts-Verifikation, Versicherung)

### Bezahlung — Stripe Connect

**Marketplace-Modell:**

```
User zahlt 8 €  →  Stripe hält Geld in Escrow
                ↓
      Auftrag erfolgreich abgeschlossen
                ↓
           Auszahlung:
           - 7,50 € an Maker (Anna)
           - 0,50 € an SHIKSHA (Provision, ~6%)
```

Bei Streit: SHIKSHA-Support entscheidet, Stripe friert Geld ein.

---

## 7. Krummelus als erster Test-Case

### Warum Krummelus

- Heidi ist bereits SHIKSHA-Pilot, kennt die Marke, vertraut.
- KITA hat permanent kleine Reparatur-Bedürfnisse (Spielzeug, Möbel-Beschläge, Lego-Ersatz).
- Vorarlberg hat eine starke Maker-Community + Schulen mit 3D-Druckern.

### Konkreter erster Auftrag (geplant innerhalb der nächsten 4 Wochen)

```
Heidi notiert ein kaputtes Teil in der KITA. SHIKSHA fragt:
"Magst Du das als Reparatur-Auftrag stellen? Ich habe einen
Maker im Maker-Space FAB Lab gefunden, 12 km entfernt."

Heidi sagt ja. Auftrag läuft durch. Pilotergebnis dokumentiert.

Aus den Erkenntnissen entsteht V0.2 des Konzepts.
```

### Was wir aus dem ersten Auftrag lernen

- Welche Reibungspunkte hat Heidi bei der Datei-Beschaffung (.stl)?
- Wie reagiert der Maker (Anna) auf den Auftrag-Flow?
- Wo hakt's bei der Bezahlung?
- Welche Climate/Trust-Aussagen wirken überzeugend, welche pathetisch?

---

## 8. Phasen-Plan

```
V0.1 — Konzept (heute)
       Vision festgehalten, Tech-Stack klar, kein Code

V0.2 — Pilot-Auftrag Krummelus (4-6 Wochen)
       Manuell vermittelt, Lessons sammeln, KEIN automatisierter
       Marketplace — nur SHIKSHA-Mensch (Founder oder Operator)
       als Vermittler

V1.0 — MVP-Marketplace (3-4 Monate Code-Sprint)
       Drucker-Registry, Auftrag-Routing, Stripe Connect,
       Bewertungssystem. Lokal Vorarlberg-Cluster.

V1.1 — Public Launch (12+ Monate)
       Self-Service-Maker-Onboarding, Marketing-Push,
       Cross-Edition-Integration

V2.0+ — Internationale Skalierung
        Mehrsprachigkeit, Mehr-Länder-Stripe, lokale
        Trust-Anpassungen
```

---

## 9. Risiken + Mitigationen

### Hühner-Ei-Problem

**Risiko:** Marketplace funktioniert erst, wenn Maker UND Requester da sind. Wenn Maker keine Aufträge sehen, melden sie sich ab. Wenn Requester keine Maker sehen, posten sie nicht.

**Mitigation:** 
- Phase V0.2 manuell-vermittelt (kein Cold-Start)
- V1.0 fokussiert auf einen geographischen Cluster (Vorarlberg)
- Maker-Onboarding-Bonus in den ersten 3 Monaten (z.B. SHIKSHA übernimmt Provision auf erste 5 Aufträge)

### Qualitäts-Problem

**Risiko:** Hobby-Maker liefert minderwertigen Druck, Requester ist enttäuscht.

**Mitigation:**
- Bewertungs-System sichtbar
- "Test-Druck" optional (Maker druckt erst 1 Stück, Requester bestätigt Qualität, dann Voll-Auftrag)
- Bei klaren Mängeln: Geld-zurück-Garantie via Stripe, Maker bekommt Strike

### Rechtliches (Produkthaftung)

**Risiko:** Heidi nutzt das gedruckte Teil, Kind verschluckt sich daran, Hersteller-Haftung greift nicht.

**Mitigation:**
- Klare Disclaimer: "Reparatur-Druck ist privates Replacement, kein zertifiziertes Bauteil. Verwendung auf eigenes Risiko."
- Bei sicherheitskritischen Anwendungen: SHIKSHA leitet zu professionellen Anbietern weiter
- Optional V2: Versicherungs-Layer (Allianz oder Helvetia haben Maker-Insurance-Produkte)

### IP / Urheberrecht

**Risiko:** User reicht .stl-Datei ein, die er nicht selbst gemacht hat (z.B. Lego-Klon).

**Mitigation:**
- Nutzungsbedingungen: User bestätigt Nutzungsrechte
- Bei offensichtlichem IP-Verletzung: Auftrag wird nicht vermittelt
- Im Zweifel: SHIKSHA leitet auf legale Alternativen (Printables-Modelle mit CC-Lizenz)

---

## 10. Marketing-Hook (für später)

> ### *"Was kaputt ist, wird repariert.*  
> *Im Nachbardorf gedruckt, nicht aus China verschickt.*  
> *In 4 Stunden statt 4 Wochen.*  
> *Geld bleibt im Tal."*
>
> **shiksha-smart Reparaturservice**

Dieser Vier-Zeiler steht später als Hero auf shiksha.world/repair-network — wenn das Konzept Realität ist.

---

## 11. Status

```
V0.1 Konzept            ✓ heute fertig
V0.2 Pilot-Auftrag       ○ Krummelus, 4-6 Wochen
V1.0 MVP-Marketplace     ○ 3-4 Monate Code-Sprint, planbar
V1.1 Public Launch        ○ 12+ Monate
```

**Bis dahin:** Vision dokumentiert, im Backlog, ruht. Wenn Krummelus stabil läuft und Heidi den ersten Reparatur-Bedarf nennt, springt V0.2 los — manuell vermittelt, ohne Code.

---

**Konzept V0.1 · 3. Mai 2026 · SHIKSHA verbindet, baut nicht selbst · Lieferweg-Verkürzung als Markenversprechen**
