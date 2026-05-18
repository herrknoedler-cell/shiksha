# DSB-Anschreiben — Konsultation Art. 36 DSGVO zu Identity-Modul

> Skelett für den formalen Brief an die österreichische Datenschutzbehörde. Vor Versand juristisch prüfen und Träger-Platzhalter `<<…>>` befüllen.

---

```
<<TRÄGER-NAME>>
<<TRÄGER-ANSCHRIFT>>
<<TRÄGER-PLZ ORT>>
<<TRÄGER-TELEFON>>
<<TRÄGER-EMAIL>>


An die
Datenschutzbehörde
Barichgasse 40-42
1030 Wien

per E-Mail an: dsb@dsb.gv.at


<<ORT>>, am <<DATUM>>


Betreff: Konsultation nach Art. 36 DSGVO — Identitätsverifikations-Modul "SHIKSHA Identity"
         (Aufbewahrungsfristen, Pseudonymisierungs-Maßnahmen, Einwilligungs-Dokumentation)


Sehr geehrte Damen und Herren,

als Verantwortlicher gemäß Art. 4 Z 7 DSGVO bzw. § 36 Z 8 DSG plant <<TRÄGER-NAME>>
(ZVR <<ZVR-NUMMER>>, Sitz in <<ORT>>) die Inbetriebnahme eines softwaregestützten
Identitätsverifikations-Moduls zur Dokumentation von Abholberechtigten für die
in unserer Einrichtung betreuten Kinder. Die Verarbeitung umfasst die einmalige
Erfassung eines Lichtbild-Ausweises, die OCR-/MRZ-Auswertung, die Speicherung
ausgewählter strukturierter Daten sowie die Verknüpfung mit konkreten
Berechtigungen (Abholung, Buchungen, Kursteilnahme).

Im Rahmen der Datenschutz-Folgenabschätzung nach Art. 35 DSGVO (Anlage 1)
haben wir die Verarbeitung beschrieben, das Risiko bewertet und konkrete
technische sowie organisatorische Maßnahmen zur Risikominimierung vorgesehen.
Da unsere DSFA an mehreren Stellen Auslegungs-Spielräume identifiziert hat,
deren Entscheidung wir nicht ohne Bestätigung der Aufsichtsbehörde treffen
möchten, bitten wir die Datenschutzbehörde um Konsultation gemäß Art. 36 DSGVO
zu folgenden vier konkreten Punkten:

  1. Aufbewahrungsfristen
     Wir planen eine drei-stufige Retention:
       - Scan-Dateien (Vorder-/Rückseite des Ausweises): maximal 30 Tage
         nach erfolgreicher Verifikation, danach automatischer Hard-Delete
       - Strukturierte Stammdaten + Berechtigungs-Records:
         Speicherung bis zum Ende des Betreuungsverhältnisses zuzüglich
         drei Jahre (analog § 1489 ABGB)
       - DSGVO-Audit-Log: sieben Jahre nach geloggtem Ereignis
         (Rechenschaftspflicht Art. 5 Abs. 2 DSGVO + WKO-Leitlinie)
     Bestätigt die Datenschutzbehörde diese Fristen als verhältnismäßig im
     Sinne von Art. 5 Abs. 1 lit. e DSGVO, oder hält sie eine kürzere bzw.
     differenzierte Aufbewahrung für angezeigt?

  2. Hash-Pseudonymisierung der Ausweisnummer
     Die Ausweisnummer wird ausschließlich als per-Mandanten gesalzener
     SHA-256-Hash (96-bit Trunkierung) gespeichert; der Salt selbst ist
     nicht über die Anwendungs-Schnittstelle exportierbar.
     Wird diese Maßnahme als ausreichende Pseudonymisierung im Sinne von
     Art. 4 Z 5 DSGVO bewertet, oder soll der Hash nach erfolgreicher
     Verifikation ebenfalls gelöscht werden?

  3. Einwilligungs-Dokumentation
     Wir verwenden eine schriftliche Einwilligungs-Erklärung gemäß
     Art. 13/Art. 7 DSGVO (Anlage 2), unterzeichnet durch die abhol-
     berechtigte Person, gegengezeichnet durch zwei Mitarbeitende
     (Vier-Augen-Prinzip).
     Entspricht diese Form den Anforderungen der Aufsichtsbehörde, oder
     wären zusätzliche Inhalte/Formerfordernisse zu ergänzen?

  4. Sonstige Empfehlungen
     Welche weiteren technischen oder organisatorischen Aspekte sollten
     wir aus Sicht der Datenschutzbehörde vor Inbetriebnahme berücksichtigen?

Als Anlagen übermitteln wir:

  - Anlage 1: Datenschutz-Folgenabschätzung
              (docs/dsfa/identity-modul-at.md, Version 1.0-DRAFT)
  - Anlage 2: Einwilligungs-Erklärung
              (editions/jurisdictions/at/consent_de_AT.md, Version 1.0-DRAFT)
  - Anlage 3: Technische Spezifikation des Identity-Moduls, Auszug §1-2
              (docs/specs/SHIKSHA_IDENTITY_SPEC.md, Version 1.0)

Die Inbetriebnahme des Moduls ist für <<GEPLANTER LIVE-TERMIN>> geplant; eine
Rückmeldung der Datenschutzbehörde bis spätestens <<RÜCKMELDE-DATUM, z. B.
6 Wochen vor Live-Termin>> wäre uns daher sehr wertvoll. Selbstverständlich
stehen wir für Rückfragen und ergänzende Auskünfte gerne zur Verfügung.

Mit freundlichen Grüßen


_____________________________________
<<NAME-DES-VERTRETUNGSBEFUGTEN>>
<<FUNKTION, z. B. Obfrau / Obmann / Geschäftsführerin>>
<<TRÄGER-NAME>>
```

---

**Hinweise zur Verwendung:**

- Brief auf Träger-Briefpapier ausdrucken oder als PDF mit Briefkopf-Layout exportieren
- Anlagen als PDF beilegen (DSFA und Consent aus den `.md`-Quellen exportiert)
- Versand bevorzugt per E-Mail mit Bestätigungs-Quittung; alternativ per Einschreiben
- Eingangs-Bestätigung der DSB schriftlich verlangen und in der DSFA §7 dokumentieren
- DSB-Antwortzeit erfahrungsgemäß 4-12 Wochen — daher früh starten, parallel zum Cowork-Code-Lauf für 5.5.6.1+
- Falls die DSB Auflagen formuliert, diese in DSFA §7 dokumentieren und ggf. Spec sowie `editions/jurisdictions/at.yaml` anpassen
