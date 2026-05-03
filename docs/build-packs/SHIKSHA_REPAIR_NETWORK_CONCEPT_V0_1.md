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

## 4.4 Triage-Engine — ist 3D-Druck überhaupt der richtige Weg?

**Bevor** ein Reparatur-Auftrag in die STL-Pipeline geht, fragt SHIKSHA: *Ist 3D-Druck hier überhaupt sinnvoll?* Manche Teile gehören nicht in die Pipeline — nicht weil's technisch nicht ginge, sondern weil's praktisch oder rechtlich falscher Weg wäre.

### User-Flow

```
1. Techniker / User sieht kaputtes Teil
2. Foto / kurzer Scan mit Smartphone
3. SHIKSHA analysiert drei Dimensionen:

      • Standardteil?         → DB-Lookup gegen Modell-Bibliotheken
                                  (Printables, Thingiverse, MakerWorld)
      • Druckbar?             → Material, Größe, Komplexität,
                                  passende Drucker im Netzwerk?
      • Sicherheitsrelevant?  → KITA-Spielzeug bis 3 Jahre,
                                  Sportgeräte, druckbedingte Mechanik?

4. Triage-Entscheidung — vier Kategorien:

      A  direkt druckbar (lokal)        → STL-Pipeline (Sektion 4.5)
      B  adaptierbar (kleine Anpassung) → STL-Pipeline mit Maker-Hinweis
      C  besser reparieren lassen       → Routing an klassische Werkstatt
      D  Originalteil notwendig         → Empfehlung Hersteller / Ersatzteil-Markt

5. Ausgabe an User:

      A  → "Lass mich das drucken — hier sind drei Maker bei Dir."
      B  → "Mit kleiner Anpassung druckbar. Maker macht das mit."
      C  → "Das gehört zum Schreiner / Schuhmacher / etc. — hier
            ist einer in 3 km Entfernung."
      D  → "Original-Ersatzteil ist hier sicherer. Hersteller X
            hat es noch im Angebot, ~12€."
```

### Triage-Logik (Pseudocode)

```python
def triage_repair_request(part_image, part_meta) -> TriageResult:
    """
    Klassifiziert einen Reparatur-Bedarf in eine der vier Kategorien.
    Läuft vor der STL-Pipeline.
    """
    # 1. Sicherheits-Filter zuerst (schließt potenziell aus)
    if is_safety_critical(part_meta):
        # Spielzeug für unter 3 Jahren (Verschluck-Risiko bei
        # FDM-Druck-Layer-Lösung), Sportgeräte mit Lasten,
        # mechanische Teile mit Belastungs-Anforderung
        return TriageResult.D_ORIGINAL_PART_NEEDED

    # 2. Standardteil-Lookup
    match = lookup_standard_model(part_image, part_meta)
    if match.confidence > 0.85:
        return TriageResult.A_DIRECT_PRINT(model=match.model)

    # 3. Funktionalitäts-Check
    if is_complex_mechanism(part_meta):
        # Zahnräder mit hoher Belastung, Federelemente,
        # Pumpen, Elektronik-Gehäuse mit IP-Klasse
        return TriageResult.C_PROFESSIONAL_REPAIR

    # 4. STL-Pipeline-Vorprüfung
    mesh = quick_mesh_analysis(part_image)
    if mesh.is_clean and mesh.is_watertight:
        return TriageResult.A_DIRECT_PRINT(model=mesh)
    elif mesh.is_fixable:
        return TriageResult.B_ADAPTABLE(model=mesh, hint="slicer_repair")
    elif mesh.geometry_unclear:
        return TriageResult.B_ADAPTABLE(model=mesh, hint="rescan_or_ai_completion")
    else:
        # Keiner der A/B-Cases passt sauber → an Profi
        return TriageResult.C_PROFESSIONAL_REPAIR
```

### Vereinfachter Decision-Tree

```
IF mesh_clean AND watertight:
    → direct_print          (Triage A)

ELIF mesh_fixable:
    → slicer_repair         (Triage B → Maker fixt im Slicer)

ELIF geometry_unclear:
    → rescan_request        (Triage B → User scannt neu)
    OR ai_completion        (Triage B → optional Cloud-AI)

ELIF functional/complex:
    → route_to_repair_service  (Triage C → klassische Werkstatt)

ELIF safety_critical:
    → original_part_recommended  (Triage D → Ersatzteil-Markt)
```

### DB-Schema-Erweiterung

```sql
ALTER TABLE repair_jobs ADD COLUMN triage_classification TEXT
    CHECK (triage_classification IN (
        'A_direct_print',
        'B_adaptable',
        'C_professional_repair',
        'D_original_part_needed'
    ));

ALTER TABLE repair_jobs ADD COLUMN triage_confidence DECIMAL DEFAULT 0;
ALTER TABLE repair_jobs ADD COLUMN triage_reasoning TEXT;
    -- LLM-erzeugte Begründung der Klassifikation, transparent für User
```

### Sicherheits-Filter — was ist "sicherheitsrelevant"?

**Faustregel:** Bremshebel vs. Schrankgriff. Wenn jemand zu Schaden kommt, falls das Teil versagt → Original. Wenn es nur "passt nicht mehr" oder "sieht nicht schön aus" → druckbar.

| Kategorie | Beispiel | Triage-Default |
|---|---|---|
| KITA-Spielzeug für <3 Jahre | Beißring, Greifling | D — nie via FDM-Druck (Layer-Lösung, Verschluck-Risiko) |
| Sportgeräte mit Belastung | Klettergriff, Karabinerhaken | D — Original (Lasten-Zertifizierung) |
| **Mobilität / Fahrzeug-Sicherheit** | **Bremshebel, Lenkungs-Komponente, Helm-Verschluss** | **D — niemals via 3D-Druck-Replacement** |
| Druckbehälter | Wasserflaschen-Verschluss | C/D — nicht ohne Material-Test |
| Elektrische Komponenten mit IP-Klasse | Kabel-Tülle für Steckdose | C/D — Hersteller-Spezifikation |
| Kosmetisches Gehäuse | Lampenschirm, Knopf, **Schrankgriff** | A — risikoarm, druckbar |
| Mechanische Teile mit moderater Last | Möbel-Beschlag, Kistenlasche | A/B — druckbar mit PETG/ABS |
| Reine Form-Funktion | Halter, Aufsteller, Spielzeug-Versteck | A — unproblematisch |

**Drucker-Technologie-Match (Feasibility-Check):**

Bei A/B-Klassifikation prüft die Triage zusätzlich, welche Drucker-Technologie passt:

```python
def check_feasibility(part_meta, available_printers):
    if part_meta.requires_high_detail:        # Mini-Mechanik, feine Schrift
        return ['SLA', 'MJF']                  # nicht FDM
    elif part_meta.requires_food_safe:        # KITA-Geschirr-Replacement
        return ['FDM_PETG', 'FDM_PLA_certified']
    elif part_meta.requires_flexibility:      # Dichtungs-Ring
        return ['FDM_TPU']
    else:
        return ['FDM_PLA', 'FDM_PETG']        # Standard-Default
```

Wenn keiner der Drucker im Netzwerk die geforderte Technologie hat → Triage-Result wechselt zu C (Werkstatt) oder D (Original).

### Geschäftsmodell — wenn SHIKSHA nicht selbst druckt

**Triage C (Werkstatt) und D (Originalteil) sind keine Sackgassen — sie sind Geschäftsmodell.**

Bei jedem Triage-Result gibt es einen monetarisierbaren Pfad:

| Triage | Wer verdient woran |
|---|---|
| A (Local Print) | Maker bekommt Auftrag, SHIKSHA Provision (~6%) |
| B (AI-Adaption) | dito A, plus Cloud-AI-Service-Aufschlag falls genutzt |
| **C (Expert Connect)** | **SHIKSHA leitet an lokale Werkstatt → Vermittlungs-Provision oder Affiliate-Partnerschaft** |
| **D (Original Part)** | **SHIKSHA leitet zu Hersteller / Ersatzteil-Markt → Affiliate-Provision** |

Damit wird klar: SHIKSHA verdient nicht **nur** an erfolgreich gedruckten Teilen, sondern an **jeder Triage-Entscheidung**, die zu einer realen Lösung führt. Das ist robuster als ein reines Print-Marketplace-Modell — und es belohnt die ehrliche Empfehlung.

**Konsequenz für die Stimme:** SHIKSHA hat keinen Anreiz, jeden Auftrag in Stufe A zu pressen. Sie kann ehrlich empfehlen, weil Empfehlungen sich ebenso lohnen.

### Expert-Connect — DB-Skizze

Für Triage C: lokale Handwerker als zweites Netzwerk neben Makern.

```sql
CREATE TABLE expert_partners (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    trade           TEXT,                       -- 'schreiner' | 'schuhmacher' |
                                                --  'metallbauer' | 'elektriker'
    location        GEOGRAPHY(POINT),
    address         TEXT,
    rating_avg      DECIMAL DEFAULT 0,
    affiliate_terms JSONB,                      -- Provisions-/Abrechnungs-Modell
    available       BOOLEAN DEFAULT true
);

CREATE TABLE expert_tickets (
    id              SERIAL PRIMARY KEY,
    repair_job_id   INT REFERENCES repair_jobs(id),
    partner_id      INT REFERENCES expert_partners(id),
    status          TEXT,                       -- 'sent' | 'accepted' |
                                                --  'completed' | 'declined'
    sent_at         TIMESTAMP DEFAULT NOW()
);
```

Bei Triage-Result C wird automatisch ein `expert_ticket` an den nächsten passenden Partner geschickt — analog zur Maker-Vermittlung, nur mit anderem Daten-Modell.

### Was die Triage besonders macht

**Marketplaces wie Hubs / Treatstock** akzeptieren jeden Auftrag, den der User reinschickt — Verantwortung bleibt komplett beim User. SHIKSHA tut etwas anderes: sie *denkt mit*. Sie sagt manchmal *"das gehört nicht hierher"* — und genau das schafft Vertrauen.

**User-Wahrnehmung:** *"SHIKSHA empfiehlt mir nicht alles, sondern das Richtige."*

Dass Triage manchmal Aufträge **wegleitet** (zu klassischen Werkstätten, zum Hersteller), ist kein Verlust — es ist Marken-Differenzierung. Eine Mit-Arbeiterin würde das auch tun. Ein blinder Marketplace nicht.

### Triage in der Praxis — Beispiel-Dialog

```
Heidi:    Eine Spielzeug-Lokomotive vom Pino-Spielzeug ist gebrochen.
          Die Räder sind ab.

SHIKSHA:  [scannt das Foto]

          Pino-Spielzeug — die Lokomotive ist für unter-3-Jährige
          zugelassen. Das ist sicherheitsrelevant: bei einem
          3D-Druck-Ersatz könnten Layer-Schichten splittern,
          Verschluck-Risiko.

          Ich empfehle: Original-Räder bestellen. Pino führt sie
          noch — 8€ pro Set, Lieferung 3 Tage.

          Magst Du den Link?

          [Triage: D_original_part_needed]
          [Triage-Confidence: 0.92]

Heidi:    Schade. Aber okay, Link bitte.
```

**Plus:** Auch ein "C_professional_repair"-Fall:

```
Heidi:    Der Holz-Tisch im Kreis-Raum hat einen tiefen Riss.

SHIKSHA:  Holz-Riss ist Schreiner-Fall, nicht 3D-Druck.

          Schreinerei Lutz in Dornbirn macht solche Reparaturen
          regelmäßig — 4 km bei Euch. Soll ich anfragen?

          [Triage: C_professional_repair]
```

Die Triage macht SHIKSHA zur **Mit-Arbeiterin mit Berufs-Ehre**: nicht alles wollen, sondern das Richtige tun.

---

## 4.5 STL-Auto-Repair-Pipeline — REPAIR_PIPELINE_V0_1

### Spec

```
═══════════════════════════════════════════════════════════════════
  REPAIR_PIPELINE_V0_1
═══════════════════════════════════════════════════════════════════

  Ziel:
    Ein gescanntes Ersatzteil wird so weit wie möglich
    automatisch druckfähig gemacht.

  Pipeline:
    1. Upload STL / OBJ / GLB
    2. Server-Side Mesh-Check
    3. Auto-Repair via Trimesh
    4. Druckbarkeits-Status (printability_status):
         • ready_for_print              ✓ druckbar, Auftrag kann sofort raus
         • slicer_repair_recommended    ⚠ kleine Probleme, Maker fixt im Slicer
         • needs_better_scan            ✗ User soll nochmal scannen
         • needs_manual_help            ✗ erfahrener Maker oder AI-Repair
    5. Optional: Maker / Slicer-Reparatur (Stufe 2)
    6. Nur Spezialfälle: AI Mesh Completion oder manuelle Hilfe (Stufe 3)

  Leitprinzip:
    "Nicht jeder Fall muss automatisch gelöst werden.
     Aber jeder Fall muss verständlich eingeordnet werden."

═══════════════════════════════════════════════════════════════════
```

Diese Spec ist **kanonisch** — die vier Status-Werte sind die einzigen erlaubten Klassifikationen. Der DB-Eintrag `repair_jobs.printability_status` ist auf genau diese vier Werte enum-beschränkt.

### Hintergrund

3D-Scans liefern oft unsaubere Files (Löcher, falsche Normals, non-manifold geometry, disconnected components). Ohne Auto-Repair müsste der Maker das von Hand fixen — Hürde, die das Netzwerk bremst.

**Lösung:** dreistufige Reparatur-Logik. SHIKSHA übernimmt Stufe 1 automatisch, Stufe 2 erledigt der Maker beim Slicen ohnehin, Stufe 3 ist Cloud-Eskalation für hartnäckige Fälle.

### Stufe 1 — Server-Side Auto-Repair (Open Source, beim Upload)

Python-Library `trimesh` läuft beim Upload, repariert 60-80% der typischen Scan-Probleme automatisch:

```python
import trimesh

def repair_stl_pipeline(input_path: str, output_path: str) -> dict:
    """
    Server-Side STL-Auto-Repair.
    Läuft beim Upload, vor Auftrag-Vermittlung.
    """
    mesh = trimesh.load(input_path)

    # Standard-Cleanup
    mesh.process()
    trimesh.repair.fix_normals(mesh)
    trimesh.repair.fix_winding(mesh)
    trimesh.repair.fill_holes(mesh)
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()

    # Final-Check
    is_printable = mesh.is_watertight and mesh.is_winding_consistent

    mesh.export(output_path)

    return {
        "is_watertight": mesh.is_watertight,
        "is_winding_consistent": mesh.is_winding_consistent,
        "is_printable": is_printable,
        "vertex_count": len(mesh.vertices),
        "face_count": len(mesh.faces),
        "volume_cm3": mesh.volume / 1000 if is_printable else None,
        "needs_manual_attention": not is_printable
    }
```

**Behebt typischerweise:**
- Kleine bis mittlere Löcher
- Falsche Face-Normals (innen/außen verdreht)
- Doppelte Vertices/Faces
- Disconnected components (kleine Mesh-Splitter)
- Non-manifold edges

**Behebt NICHT (geht an Stufe 2/3):**
- Große fehlende Bereiche (>10% des Volumens)
- Komplett kaputte Topologie
- Selbst-Intersections in komplexer Geometrie

### Stufe 2 — Slicer-Auto-Repair (passiert beim Maker ohnehin)

Moderne Slicer haben Auto-Repair eingebaut. Der Maker importiert das STL, der Slicer repariert beim Import:

| Slicer | Auto-Repair |
|---|---|
| **Bambu Studio** | automatisch beim Import |
| **PrusaSlicer** | "Repair STL"-Button + integriert beim Slicing |
| **Cura** | Auto-Heal-Funktion |
| **OrcaSlicer** | erbt Bambu-Studio-Logik |

Heißt: SHIKSHA muss Stufe 2 nicht selbst implementieren — sie passiert im Maker-Workflow eh.

### Stufe 3 — Cloud-AI-Repair (für die schwierigen 5%)

Wenn Stufe 1 `needs_manual_attention=true` zurückgibt UND der Maker beim Slicen scheitert:

**Optionen:**
- **Meshy.ai API** — KI-basierte Mesh-Completion, kommerziell, ~0.10-0.50 USD/Repair
- **CSM (Common Sense Machines)** — komplexere Cases mit text-aware Reconstruction
- **Manueller Re-Scan** — SHIKSHA fragt User: *"Dein Scan ist zu unvollständig. Magst Du nochmal scannen — gleichmäßig rundherum, gutes Licht?"*

**Empfehlung MVP:** Stufe 3 nicht aktiv anbieten. Bei `needs_manual_attention` höflicher Re-Scan-Hinweis. Cloud-AI-Repair erst V1.x, wenn das Volumen Investitionen rechtfertigt.

### Visual Feedback im Dialog

Beim Upload zeigt SHIKSHA **vor** der Auftrag-Vermittlung:

```
SHIKSHA: Dein Scan ist da. Ich habe ihn kurz geprüft und repariert.
         
         ✓ Watertight (druckbar)
         ✓ Volumen: 14.3 cm³
         ✓ 8.420 Vertices, 16.760 Faces
         
         [3D-Preview anzeigen]
         
         Sieht gut aus. Soll ich Maker suchen?
```

Bei Problemen:

```
SHIKSHA: Dein Scan hat noch Lücken, die ich nicht ganz füllen konnte.
         Der Maker müsste Hand anlegen (sein Slicer hilft meistens),
         oder Du machst nochmal einen Scan — gleichmäßig rundherum.
         
         Soll ich's trotzdem an einen erfahrenen Maker schicken,
         oder lieber Re-Scan?
         
         [Trotzdem senden] [Re-Scan-Tipps]
```

### Implementierungs-Aufwand

| Stufe | Aufwand | Wer |
|---|---|---|
| 1 — trimesh-Pipeline | 1 Tag | SHIKSHA-Backend |
| 2 — Slicer | 0 (passiert eh) | Maker |
| 3 — Cloud-AI | 1-2 Tage Integration | optional, V1.x |

**Bonus-Differenzierung:** Während andere Marketplaces sagen *"laden Sie eine druckfähige STL hoch"*, sagt SHIKSHA *"lad einfach hoch, ich kümmere mich."* Das ist wieder ein **No-Configuration**-Moment, passt zur Master-Vision.

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
