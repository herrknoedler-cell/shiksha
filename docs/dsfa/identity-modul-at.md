# Datenschutz-Folgenabschätzung — Identity-Modul (AT)

**Verantwortlicher (Auftraggeber):** &lt;&lt;TRÄGER-NAME&gt;&gt;
**Anschrift:** &lt;&lt;TRÄGER-ANSCHRIFT&gt;&gt;
**Kontakt:** &lt;&lt;TRÄGER-EMAIL&gt;&gt; · &lt;&lt;TRÄGER-TELEFON&gt;&gt;
**Datenschutzbeauftragte/r:** &lt;&lt;DSB-NAME&gt;&gt; · &lt;&lt;DSB-EMAIL&gt;&gt;
**Stand:** &lt;&lt;DATUM&gt;&gt; · **Version:** 1.0-DRAFT
**Prüfungs-Zyklus:** jährlich + ad-hoc bei substanziellen Änderungen
**Software-Version:** SHIKSHA Identity-Modul 5.5.6
**Referenz-Spezifikation:** `docs/specs/SHIKSHA_IDENTITY_SPEC.md` v1.0

> **Hinweis:** Dieses Skelett ist Strukturvorlage. Für die produktive DSFA ist juristische Begutachtung durch den/die Datenschutzbeauftragte/n oder einen DSGVO-Anwalt erforderlich. Platzhalter `<<…>>` markieren träger- oder einrichtungsspezifische Felder. Score-Werte in Sektion 3 sind nach Einrichtungs-Kontext zu validieren.

---

## 1. Beschreibung der Verarbeitungsvorgänge (Art. 35(7)(a) DSGVO)

### 1.1 Zweck der Verarbeitung

Verifikation der Identität von Personen, die berechtigt sind, ein bestimmtes Kind aus der Einrichtung abzuholen oder andere kindbezogene Berechtigungen wahrzunehmen (Buchungen, Kursteilnahme, Berechtigungs-Übertragungen). Ziel ist der Schutz des Kindes vor unbefugter Mitnahme sowie eine dokumentierte Beweiskette gegenüber Aufsichtsbehörden und in Streitfällen (z. B. Sorgerechts-Konflikt).

### 1.2 Kategorien betroffener Personen

- Abhol-Berechtigte (Eltern, Großeltern, Tageseltern, andere benannte Vertrauenspersonen)
- Mitarbeitende der Einrichtung (Bestätiger-Operatoren), insoweit sie als Akteure im Audit-Log erscheinen

### 1.3 Kategorien personenbezogener Daten

- **Stammdaten:** Vorname, Nachname, Geburtsdatum
- **Ausweis-Auszug (gefiltert):** Ausweistyp, Ablaufdatum, Ausweisnummer als kryptographischer Hash (`sha256(doc_number + tenant_salt)[:24]`)
- **Verifikations-Metadata:** Zeitstempel, OCR-Konfidenz, MRZ-Check-Ergebnis, Bestätiger-Operator-ID
- **Authorisierungs-Daten:** Zuordnung zu betreutem Kind, Gültigkeitszeitraum, Widerrufs-Information
- **DSGVO-Audit-Log:** Wer hat wann auf welche Identity-Daten zugegriffen
- **Während Scan-Verarbeitung (max. 30 Tage):** JPG/PNG der Ausweis-Vorder- und -Rückseite

### 1.4 Empfänger der Daten

- **Intern:** berechtigte Mitarbeitende mit role_scope `leitung` (voller Zugriff) oder `padagoge` (Metadata + Verifikations-Tap, kein Datei-Zugriff)
- **Extern:** keine, außer auf Auskunfts- oder Löschverlangen der betroffenen Person bzw. behördlich angeordnete Datenherausgabe
- **Auftragsverarbeiter:** Hosting-Provider &lt;&lt;HOSTING-ANBIETER&gt;&gt; mit Auftragsverarbeitungs-Vertrag nach Art. 28 DSGVO

### 1.5 Aufbewahrungsfristen

Konfiguriert in `editions/jurisdictions/at.yaml`, jurisdiktions-spezifisch überschreibbar:

- **Scan-Datei (Tier 1):** max. 30 Tage nach Verifikation, dann Hard-Delete
- **Strukturierte Stammdaten + Authorizations (Tier 2):** bis Ende des Betreuungsverhältnisses + 3 Jahre (§ 1489 ABGB Verjährungs-Anlehnung)
- **DSGVO-Audit-Log (Tier 3):** 7 Jahre nach geloggtem Ereignis
- **Legal-Hold-Flag** pausiert automatische Löschung in dokumentierten Sonderfällen (Sorgerechtsstreit, gerichtliches Verfahren)

### 1.6 Verarbeitungsschritte (technisch)

1. Mitarbeiter erfasst Stammdaten und holt schriftliche Einwilligung der/des Abholberechtigten ein
2. Foto-Capture des Ausweises (Vorder- + Rückseite) durch Tablet oder Webcam
3. OCR + MRZ-Parsing **lokal** auf dem Server, kein externer Cloud-Service
4. Whitelist-Filter `_filter_mrz_to_whitelist()` blockiert nicht-erlaubte MRZ-Felder vor DB-Insert; Ausweisnummer wird normalisiert und gehasht
5. Verifikations-Bestätigung durch berechtigte/n Mitarbeiter/in mit lückenloser Dokumentation im Audit-Log (Operator-ID, Zeitstempel, Aktion); in Tenant-Konfigurationen mit `four_eyes_required: true` zusätzlich durch eine zweite Person gegengezeichnet
6. Verifikations-Status auf `verified` gesetzt; Bild-Datei wird nach 30 Tagen automatisch unwiderruflich gelöscht
7. Authorisierungs-Anlage: leitende Person ordnet verifizierte Identität einem konkreten Kind zu

---

## 2. Bewertung der Notwendigkeit und Verhältnismäßigkeit (Art. 35(7)(b))

### 2.1 Erforderlichkeit

Die Verarbeitung ist erforderlich zur Erfüllung der Aufsichtspflicht der Einrichtung gemäß § 1309 ABGB iVm dem Vorarlberger Kinderbildungs- und -betreuungsgesetz (KBBG, LGBl. Nr. 72/2022) und der dazu ergangenen Personaleinsatz- und Gruppengrößenverordnung (LGBl. Nr. 78/2022) sowie dem zwischen Träger und Erziehungsberechtigten geschlossenen Betreuungsvertrag; Ziel ist der Schutz des betreuten Kindes. Ohne dokumentierte Abholberechtigung kann die Einrichtung im Streitfall (z. B. Sorgerechts-Konflikt, getrennt lebende Eltern, Hausverbot gegen Elternteil) nicht nachweisen, dass die Übergabe rechtmäßig erfolgte.

### 2.2 Geprüfte Alternativen

- **Passkey/Smartphone-basierte Verifikation:** derzeit nicht praktikabel, weil ein relevanter Anteil der Abholberechtigten (Großeltern, ältere Tageseltern) keine Smartphones nutzt oder nutzen will. Vorgesehen als Phase 2.1 parallel zur Ausweis-Lösung, nicht als Ersatz.
- **Rein mündliche Verifikation ohne Dokumentation:** rechtlich unzureichend, keine Beweiskette im Streitfall, erfüllt die Aufsichtspflicht der Einrichtung nicht.
- **Externer Identitäts-Dienstleister (z. B. IDnow, WebID):** würde zusätzliche Auftragsverarbeitung und Drittland-Datenübermittlungen schaffen — datenschutzrechtlich aufwendiger als die On-Premises-Lösung.

### 2.3 Datenminimierung

- Ausweisnummer wird **niemals im Klartext** nach der initialen OCR-Pipeline gespeichert, sondern ausschließlich als per-tenant gesalzener kryptographischer Hash
- MRZ-Whitelist filtert die Mehrzahl der MRZ-Felder vor Persistierung weg: kein Lichtbild, keine biometrischen Marker, keine Nationalitäts-Speicherung
- Bild-Datei wird nach maximal 30 Tagen unwiderruflich gelöscht; Hash der Datei bleibt als Integritäts-Nachweis
- Selfie wird **nicht** erhoben (Architektur-Entscheidung in SHIKSHA_IDENTITY_SPEC §10.2, wegen fehlendem Eingangs-Tablet-Abgleichs-Workflow)

### 2.4 Zweckbindung

Identity-Daten werden ausschließlich zur Abhol-/Berechtigungsverifikation verwendet. Keine Verwendung für Marketing, Profiling, automatisierte Einzelfallentscheidungen nach Art. 22 DSGVO oder Weitergabe an Dritte ohne ausdrückliche zusätzliche Einwilligung bzw. gesetzliche Pflicht.

---

## 3. Risiko-Identifikation und -Bewertung (Art. 35(7)(c))

**Bewertungs-Skala**
Eintrittswahrscheinlichkeit (W): 1 = sehr selten, 2 = möglich, 3 = wahrscheinlich
Schwere (S): 1 = geringfügig, 2 = erheblich, 3 = schwerwiegend
Score: W × S; ab Score ≥ 6 = hohes Risiko

| # | Risiko | W | S | Score | Begründung |
|---|---|---|---|---|---|
| R1 | Daten-Abfluss aus DB durch externen Angriff | 2 | 3 | 6 | Identitäts-Stammdaten + Hashes können bei Server-Breach zugreifbar werden. |
| R2 | Unbefugter interner Zugriff (Insider-Missbrauch) | 1 | 3 | 3 | role_scope-Beschränkung + lückenloses Audit-Log + jährliche Audit-Reviews mitigieren. |
| R3 | Cross-Tenant-Identity-Korrelation | 1 | 2 | 2 | Per-Tenant-Salt verhindert systematische Hash-Korrelation. |
| R4 | Identitätsdiebstahl durch gestohlene Bild-Datei | 2 | 3 | 6 | Bild max. 30 Tage online; File-System verschlüsselt. |
| R5 | Fehlerhafter OCR-Auto-Fill → falsche Verifikation | 2 | 2 | 4 | Mitarbeiter-Bestätigung mit Audit-Eintrag mitigiert; OCR-Konfidenz geloggt und bei niedrigen Werten in der UI angezeigt. |
| R6 | Auto-Löschung scheitert (Bug, Disk-Full) | 2 | 2 | 4 | Nightly-Job + Monitoring auf File-Counter-Diff. |
| R7 | DSGVO-Auskunfts-Anfrage kann nicht erfüllt werden | 1 | 2 | 2 | Standard-Export-Funktion vorhanden; Audit-Log durchsuchbar. |
| R8 | Legal-Hold-Versäumnis (Auto-Löschung im laufenden Verfahren) | 1 | 3 | 3 | Legal-Hold-Flag dokumentiert, Lösch-Job respektiert es. |

---

## 4. Maßnahmen zur Risikobehandlung (Art. 35(7)(d))

### 4.1 Technische Maßnahmen

- **Pseudonymisierung:** Ausweisnummer ausschließlich als per-tenant gesalzener SHA-256-Hash, Salt niemals exportierbar via Public-API
- **MRZ-Whitelist:** technischer Filter (`_filter_mrz_to_whitelist`) blockiert nicht-erlaubte Felder vor DB-Insert, dokumentiert in `SHIKSHA_IDENTITY_SPEC §3.3`
- **Verschlüsselung at rest:** DB-Tablespace und File-Storage verschlüsselt mit &lt;&lt;VERSCHLÜSSELUNGS-VERFAHREN&gt;&gt;
- **Verschlüsselung in transit:** TLS 1.3 für alle Backend-Calls; HSTS aktiviert
- **Auto-Löschung:** Nightly-Job entfernt Scan-Dateien nach 30 Tagen, strukturierte Daten gemäß Betreuungsende+3J, Audit-Log nach 7 Jahren
- **Backup-Retention:** maximal 30 Tage rolling; Backups verschlüsselt; Backup-Lösch-Test einmal jährlich
- **Authentifizierung:** JWT-Token mit kurzer Gültigkeit, role_scope-Prüfung pro Endpoint, Rate-Limiting
- **Audit-Log:** jeder Zugriff (Read und Write) auf Identity-Daten wird geloggt mit Operator-ID, Zeitstempel, Aktion, betroffener Record-ID
- **Bridge-Whitelist-Trim:** `kita/identity` aus Bridge-Routing entfernt nach Migration, verhindert externe Aufrufe ohne Auth-Schicht

### 4.2 Organisatorische Maßnahmen

- **Verifikations-Dokumentation:** jede Verifikation wird mit Operator-ID, Zeitstempel und Aktion im Audit-Log dokumentiert. In Tenant-Konfigurationen mit `four_eyes_required: true` (siehe `editions/jurisdictions/<code>.yaml`) zusätzlich Bestätigung durch eine zweite berechtigte Person erforderlich. Für Krummelus als Einrichtung mit einer dauerhaft anwesenden Leitungsperson aktuell deaktiviert; siehe Tech-Schuld T-012 für die Multi-Leitung-Erweiterung.
- **Schulung:** DSGVO-Grundlagen-Schulung pro Mitarbeitende mit Identity-Modul-Zugang; jährliche Auffrischung dokumentiert
- **Berechtigungs-Konzept:** rollen-bezogene Zugriffsmatrix dokumentiert, Review zweimal jährlich
- **Lösch-Konzept:** dokumentierte Lösch-Prozesse für Manual-Löschung auf Antrag (Art. 17 DSGVO), Bearbeitungs-Zeit ≤ 30 Tage
- **Vorfalls-Reaktion:** dokumentierter Meldepfad an DSB binnen 72h bei Datenpanne (Art. 33 DSGVO)
- **Legal-Hold-Prozess:** dokumentierter Workflow für gerichtliche Anordnungen, die Auto-Löschung pausieren
- **Onboarding-Hinweis:** neue Mitarbeitende werden vor Erhalt von Identity-Berechtigungen schriftlich auf DSGVO-Pflichten verpflichtet

### 4.3 Vertragliche Maßnahmen

- AVV mit Hosting-Provider &lt;&lt;HOSTING-ANBIETER&gt;&gt; nach Art. 28 DSGVO (Datum: &lt;&lt;DATUM&gt;&gt;)
- AVV mit ggf. weiteren Auftragsverarbeitern (z. B. Backup-Dienstleister, Monitoring): &lt;&lt;LISTE&gt;&gt;

---

## 5. Restrisiko-Bewertung (Art. 35(11))

Nach Anwendung der Maßnahmen verbleiben folgende Restrisiken:

- **Server-Breach trotz Verschlüsselung (R1, R4):** Bei kompromittiertem Server-Master-Key wären Daten lesbar. Mitigation durch jährliche Schlüssel-Rotation, separate Key-Storage, Einbruchs-Erkennung. Restrisiko: tragbar.
- **Insider-Missbrauch durch leitende Person (R2):** role_scope `leitung` hat substanziellen Zugriff. Mitigation durch lückenloses Audit-Log und jährliche Audit-Reviews. Restrisiko: tragbar.
- **OCR-Fehler bei seltenen Ausweis-Typen (R5):** mitigiert durch Mitarbeiter-Bestätigung mit dokumentiertem Audit-Eintrag, aber Mitarbeiter-Fehler bei der Bestätigung bleibt menschlich. Restrisiko: gering, durch Schulung adressiert.

**Gesamtbewertung:** Restrisiko ist tragbar im Sinne der DSGVO. Keine Zustimmungspflicht der Aufsichtsbehörde nach Art. 36 DSGVO erforderlich — **außer** die DSB-Vorprüfung (Sektion 7) ergibt anderes.

---

## 6. Stellungnahme der Betroffenen (Art. 35(9))

&lt;&lt;OPTIONAL — wenn die Einrichtung vor Inbetriebnahme eine Elternversammlung oder Stichproben-Befragung zur Identity-Verifikation durchgeführt hat, hier dokumentieren: Datum, Teilnehmerzahl, zentrale Rückmeldungen, ggf. Anpassungen die daraufhin vorgenommen wurden.&gt;&gt;

---

## 7. Konsultation der Aufsichtsbehörde (Art. 36 DSGVO)

**DSB-Anfrage-Status:** &lt;&lt;ausstehend / eingereicht am DATUM / Antwort eingegangen am DATUM&gt;&gt;

**Anschreiben-Vorlage:** `docs/dsfa/dsb-anschreiben-at.md` (v1.0-DRAFT) — vor Versand juristisch prüfen und `<<…>>`-Platzhalter befüllen.

**Anfrage-Inhalt:**

- Beschreibung des Verarbeitungsvorgangs (Sektionen 1-2 dieses Dokuments)
- Bewertung der Risiken und Maßnahmen (Sektionen 3-5)
- Konkrete Fragen an die DSB:
  1. Bestätigung der Default-Aufbewahrungsfristen (30 Tage Scan / 3 Jahre Stammdaten / 7 Jahre Audit-Log) als verhältnismäßig
  2. Akzeptanz der Hash-Pseudonymisierung der Ausweisnummer als ausreichende Maßnahme zur Datenminimierung
  3. Anforderungen an die Einwilligungs-Dokumentation (siehe `consent_de_AT.md`)
  4. Sonstige Empfehlungen aus DSB-Sicht

**DSB-Antwort:** &lt;&lt;TEXT NACH EINGANG, ggf. mit Auflagen, die in Spec und Konfiguration einzupflegen sind&gt;&gt;

---

## 8. Aktualisierungs-Trigger

Diese DSFA wird überprüft und ggf. aktualisiert bei:

- Substanziellen Änderungen am Identity-Modul (z. B. Phase-2.1 Passkey-Integration, neue Auftragsverarbeiter, geänderte Aufbewahrungsfristen)
- Hinzukommen neuer Datenkategorien
- Wesentlichen Änderungen der Rechtslage (DSGVO-Novellierung, DSG-Novelle, neue DSB-Bescheide zu Identitätsprüfung)
- Datenpannen, die die Risiko-Bewertung beeinflussen
- Jährlicher Routine-Review (Stichtag: &lt;&lt;DATUM&gt;&gt;)

---

## Anhang A — Referenzdokumente

- `docs/specs/SHIKSHA_IDENTITY_SPEC.md` v1.0 — technische Spezifikation
- `editions/jurisdictions/at.yaml` — Konfigurationswerte für AT
- `editions/jurisdictions/at-8.yaml` — Vorarlberg-Override (für Krummelus)
- `editions/jurisdictions/at/consent_de_AT.md` — Einwilligungserklärungs-Master
- Auftragsverarbeitungs-Vertrag mit &lt;&lt;HOSTING-ANBIETER&gt;&gt;, Stand &lt;&lt;DATUM&gt;&gt;
- DSB-Bescheid DSB-D123.901/0002-DSB/2019 (zur Identitätsprüfung allgemein)
- &lt;&lt;ggf. einrichtungs-eigenes Datenschutz-Handbuch&gt;&gt;

## Anhang B — Glossar

- **MRZ:** Machine-Readable Zone, maschinenlesbare Zone auf Ausweisdokumenten (TD1 für Personalausweise, TD3 für Reisepässe)
- **role_scope:** rollenbasierte Zugriffsbeschränkung auf Endpoint-Ebene; im SHIKSHA-Kontext z. B. `leitung`, `padagoge`, `developer`
- **per-tenant Salt:** kryptographisches Salt, das für jeden Mandanten der Software einzeln generiert wird, um Cross-Mandanten-Korrelation zu verhindern
- **Vier-Augen-Prinzip:** Geschäftsregel, dass eine sicherheitsrelevante Aktion (hier: Verifikations-Bestätigung) durch zwei separate Personen erfolgen muss
- **Legal Hold:** technisches Flag, das automatische Löschung für eine Person/einen Record pausiert, solange ein gerichtliches oder behördliches Verfahren läuft

---

**Unterschriften**

Verantwortliche/r: __________________________ Datum: __________
Datenschutzbeauftragte/r: ___________________ Datum: __________
