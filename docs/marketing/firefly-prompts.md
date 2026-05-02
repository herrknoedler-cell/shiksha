# SHIKSHA · Firefly-Prompts für den KITA-Bilderpool · Frühling

Diese 30 Prompts liefern Dir den ersten Bilderpool für die KITA-Marketing-Sites in der Frühlingsstimmung. Du generierst sie einmal in Adobe Firefly (oder Photoshop mit Firefly), exportierst als JPG (1600×1200 px, mittlere Qualität — die Dateien werden zugänglich sein, wir können sie immer schärfer machen).

**Wichtig — DSGVO + Datenschutz**:
- Keine erkennbaren Gesichter
- Keine echten Markenlogos
- Lieber Hände, Detailaufnahmen, Räume, Naturmaterial
- Falls Personen: aus dem Hintergrund, von schräg oben, unscharf, nur Teil-Körper

**Stil-Anker für alle 30 Bilder** (in jedem Prompt mit anhängen):
> *„soft natural lighting, photorealistic, warm earthy color palette with subtle pink and pastel green accents, shallow depth of field, candid editorial style, no faces visible, suitable for a kindergarten website in spring"*

---

## Innenräume / Atmosphäre (10)

1. **Lichtdurchflutetes Spielzimmer mit Holzboden, Pflanzen am Fenster, einzelnes Kinderbuch auf einem niedrigen Tisch, weicher Vormittagsschein** — *stil-anker*

2. **Lesecke mit Kissen in Erdtönen, ein offenes Bilderbuch, eine Strickdecke, Sonnenlicht durch Tüllgardine** — *stil-anker*

3. **Wachsmalstifte und Aquarellfarben in Holzkisten auf einem Maltisch, ein halbfertiges Frühlings-Bild im Vordergrund** — *stil-anker*

4. **Kinder-Garderobenhaken aus Naturholz mit kleinen Frühlingsjacken, eine vergessene Mütze** — *stil-anker*

5. **Glas-Trinkflasche, Apfelschnitze auf einem Holzbrett, eine kleine Vase mit Tulpen — gemeinsamer Frühstückstisch** — *stil-anker*

6. **Detailaufnahme von Kinderhänden (anonym, nur Hände) beim Brot teilen** — *stil-anker*

7. **Ruheraum mit Bodenmatratzen, Lichterkette, eine Plüschmaus** — *stil-anker*

8. **Lego- und Holzbausteine auf einem Teppich, halb gebaute Burg, Vormittagslicht** — *stil-anker*

9. **Filz-Pantoffeln und kleine Gummistiefel in einer Reihe vor der Tür, Sonnenstrahl durch die offene Tür** — *stil-anker*

10. **Großer Bastel-Tisch mit Naturmaterialien (Zapfen, Blätter, Federn), Kinder-Schere, eine kleine Schale Frühlingsblumen** — *stil-anker*

## Außenbereich / Garten (10)

11. **Sandkasten mit Holzlöffeln und Eimern, eine kleine Schubkarre, Frühlingssonne** — *stil-anker*

12. **Klettergerüst aus Holz im Garten, blühende Obstbäume im Hintergrund** — *stil-anker*

13. **Kindergarten-Garten: Hochbeete mit jungen Salatpflanzen, kleine Gießkanne aus Metall** — *stil-anker*

14. **Trampolin im Garten, im Rasen verstreute Gänseblümchen, Sonnenlicht** — *stil-anker*

15. **Detail: Kinderhände (anonym) pflanzen einen Setzling in dunkle Erde** — *stil-anker*

16. **Hängematte zwischen zwei jungen Bäumen, ein Bilderbuch darauf** — *stil-anker*

17. **Pfütze nach dem Frühlingsregen, Gummistiefel-Spuren, eine kleine Pusteblume daneben** — *stil-anker*

18. **Malerei mit Wasser auf einem Steinweg, schon halb wieder verdunstet** — *stil-anker*

19. **Eine Schaukel aus alten Reifen an einem dicken Ast, leerer Garten am Morgen** — *stil-anker*

20. **Wege im Garten gesäumt von kleinen Steinen, eine Schnecke auf einem Blatt** — *stil-anker*

## Aktivitäten / Symbole (10)

21. **Aufgeschlagenes Bilderbuch mit Frühlings-Illustrationen, daneben eine Tasse Kakao** — *stil-anker*

22. **Eine Wand mit Kinder-Kunstwerken in leichten Bilderrahmen — verschwommen genug, dass keine Gesichter erkennbar sind** — *stil-anker*

23. **Eine Trommel und ein Triangle auf einem Teppich, Notenheft halb sichtbar** — *stil-anker*

24. **Holz-Memory-Karten verstreut, ein Paar zusammenpassende Karten in der Mitte** — *stil-anker*

25. **Eine Kinder-Yogamatte, eine kleine Handstand-Hilfe, Wandfarbe in Pastell** — *stil-anker*

26. **Schreibtisch mit verschiedenen Stift-Sorten in Bechern, ein Notizbuch der Pädagogin (geschlossen)** — *stil-anker*

27. **Detailaufnahme: Kinder-Schere und buntes Papier, halb-fertige Schmetterlings-Form** — *stil-anker*

28. **Eine kleine Bühne mit selbstgebastelten Kostümen: Kronen aus Pappe, ein Umhang aus altem Stoff** — *stil-anker*

29. **Eine Wand mit einem großen Wochen-Plan: Tagessymbole als Zeichnungen (Sonne, Brot, Wandern, Schlafen)** — *stil-anker*

30. **Eine Schale mit frischen Erdbeeren, eine Holz-Kelle, Frühlingslicht — Symbol für gemeinsames Vesper** — *stil-anker*

---

## Anweisung zum Hochladen

Nach dem Generieren in Firefly:
1. Speichern als JPG, ~1600×1200 px, mittlere Qualität
2. Dateinamen: `kita-spring-01.jpg` bis `kita-spring-30.jpg`
3. In den Mac-Outputs-Ordner unter `marketing/pool/kita/spring/`
4. Bei Deploy nach `/opt/shiksha/marketing_assets/pool/kita/spring/`
5. Importer-Script (s. unten) füttert sie in die DB ein

Sobald der Pool da ist, sieht jede neue KITA-Site automatisch passende Vorschläge im Builder, und Du kannst auch ohne eigene Fotos eine vollständig bestückte Site live haben.

---

## Vorschlag: Mehr-Saison-Plan

Sobald Frühling steht, wir bauen analog:
- **Sommer**: warme Außen-Bilder, Wasser-Spiel, längere Tage, Schatten unter Bäumen
- **Herbst**: Blätter-Sammlung, Drachen, warme Wollkleidung, frühes Abendlicht
- **Winter**: Lichterketten, Bastel-Tisch mit Sternen, gemütliche Innen-Räume, Tee

Pro Saison wieder ~30 Bilder = ein Nachmittag Firefly-Arbeit. Skaliert über die Editionen genauso (Camping-Bilder pro Saison, Surf-Bilder pro Saison). Der Pool wächst von selbst.
