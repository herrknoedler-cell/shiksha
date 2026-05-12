# SHIKSHA_TOOL_USE_SPEC.md

**Status:** Bindend ab Schritt 4 des Modular Build Plan.
**Geltungsbereich:** Alle Editionen, alle Personae, alle Frontends.
**Vorrang:** Diese Spec überschreibt im Konfliktfall alle bisherigen Annahmen zu Tool-Use, Modell-Verhalten und UI-Feedback.

---

## 1. Leitprinzip — Die Zahnarzt-Regel

> Ein guter Zahnarzt sagt "wird kurz kalt", wenn die Patientin sich auf etwas einstellen muss. Sonst arbeitet er still. Niemand will hören, welches Instrument gerade aus der Schublade kommt.

SHIKSHA arbeitet still. Wenn das Modell während eines Gesprächs ein Werkzeug einsetzt — eine Beobachtung festhält, eine wiederkehrende Reibung markiert, eine Erinnerung speichert — passiert das im Hintergrund. Mira hört kein "Ich speichere das jetzt", sieht keinen Lade-Spinner, bekommt keinen Toast. Sie sieht nur ihre eigene Nachricht und SHIKSHA's Antwort.

In wenigen Fällen darf SHIKSHA eine Vorwarnung oder eine Quittung geben — aber **eingebettet in die Antwort, im Mira-Ton, nie als technisches Signal**. "Das nehme ich mit." ist erlaubt. "Memory gespeichert (ID: mem_2451)" ist Hochverrat.

Diese Regel hat Vorrang vor Transparenz, vor Erklärbarkeit, vor Vollständigkeit. SHIKSHA ist nicht das System, das alles preisgibt. SHIKSHA ist das System, das so ruhig wirkt, dass man vergisst, dass es Software ist.

---

## 2. Was Tool-Use IST und was es NICHT IST

**Tool-Use ist:** Das Modell entscheidet während des Gesprächs, dass eine Aktion mehr Wert schafft als nur Text. Es ruft ein Werkzeug auf, der Server führt es aus, das Modell sieht das Ergebnis und schreibt seine Antwort. Tool-Use ist die Art, wie SHIKSHA aus einer Chat-Schnittstelle ein lernendes System wird.

**Tool-Use ist nicht:** Ein Feature, mit dem Mira interagiert. Mira hat keine Tool-UI, keine Buttons, keine Slash-Commands. Sie spricht normal, SHIKSHA handelt unsichtbar.

**Tool-Use ist nicht:** Ein Ersatz für die Insights-Extraktion am Sessionschluss (`/chat/close`). Der Session-Close bleibt der strukturierte, garantierte Backstage-Pass, der Summary + Memory-Kandidaten + Observations in einem Rutsch destilliert. Tool-Use ergänzt das, indem es **während** der Session schon kleine Sachen festhält, statt erst am Ende. Beide Mechanismen koexistieren — Abschnitt 9 regelt das.

---

## 3. Tool-Inventar (Phase 4)

Vier Werkzeuge in Phase 4. Alle edition-agnostisch. Edition-spezifische Tools können in Phase 5 nachgereicht werden — die Runtime ist darauf vorbereitet.

### 3.1 `log_observation`

Eine neutrale Beobachtung über Mira's Welt festhalten. Keine Wertung, keine Empfehlung. Beispiele: "Mira erwähnt zum dritten Mal personalknappe Mittwoche." "Bezugskind L. ist nicht erschienen, ohne Abmeldung."

**Parameter:**
- `text` (string, required, max 500): Die Beobachtung als kompletter Satz im Indikativ.
- `category` (enum, optional): `personal | familie | kind | finanzen | raum | rhythmus | sonst`.
- `relates_to_session_id` (string, optional): wenn die Beobachtung aus einer laufenden Session stammt.

**Wirkung:** Ein Eintrag in `observations`. Wird in zukünftigen Sessions Teil des Memory-Kontexts.

**Wann SHIKSHA es nutzt:** Wenn etwas Konkretes, Faktisches gesagt wurde, das später wieder relevant werden könnte. Nicht für Gefühle, nicht für Vermutungen.

### 3.2 `log_friction`

Eine wiederkehrende Reibung markieren. Im Unterschied zu `log_observation` ist das eine **Klassifikation** — SHIKSHA sagt: "Das hier ist nicht zufällig, das ist ein Muster."

**Parameter:**
- `text` (string, required, max 500): Die Reibung als Aussage. Idealerweise mit Frequenz-Marker ("immer Mittwoch", "drittes Mal diesen Monat").
- `severity` (enum, optional): `leicht | mittel | belastend`.
- `first_observed_at` (date, optional): wenn rückwirkend datierbar.

**Wirkung:** Eintrag in `friction_points`. Spielt im Trägerin-Dashboard eine Hauptrolle.

**Wann SHIKSHA es nutzt:** Erst wenn ein Muster sichtbar ist — entweder weil Mira es selbst benennt ("das war jetzt schon drei Mal") oder weil aktive Memory bestätigt, dass das Thema vorkam. **Nicht beim ersten Auftauchen** — eine einzelne schlechte Mittwoch ist noch kein Friction Point.

### 3.3 `add_memory`

Eine konkrete Erinnerung anlegen, die in zukünftigen Sessions als Kontext geladen wird. Memory ist das, woran sich SHIKSHA "erinnert", wenn Mira morgen wieder kommt.

**Parameter:**
- `text` (string, required, max 500): Die Erinnerung in dritter Person oder als faktischer Satz. Beispiel: "Mira ist Trägerin, hat fünf Mitarbeiterinnen, plant Erweiterung in den oberen Stock im Herbst."
- `source_session_id` (string, optional): wenn aus laufender Session.

**Wirkung:** Eintrag in `memory_entries`. Wird beim nächsten `/chat/respond` automatisch in den System-Prompt injiziert.

**Wann SHIKSHA es nutzt:** Sparsam. Memory ist Knappheit-Speicher, nicht Tagebuch. Nur wenn etwas zukünftige Gespräche substanziell besser machen würde, wenn SHIKSHA es weiß. Drei Memories pro Session ist viel. Zehn pro Session ist Rauschen.

### 3.4 `save_day_summary`

Eine Tageszusammenfassung explizit festhalten, **bevor** die Session geschlossen wird. Das ist redundant zum automatischen Insights-Extract bei `/chat/close`, aber sinnvoll, wenn das Modell schon mitten in der Session merkt: "Das hier ist die Essenz des Tages."

**Parameter:**
- `summary` (string, required, max 1000): Zwei bis drei Sätze in Mira-Stimme, nicht in technischer Sprache.
- `mood` (enum, optional): `klar | belastet | aufgekratzt | leer | dankbar | sonst`.

**Wirkung:** Eintrag in `day_summaries` (neue Tabelle in Phase 4, oder als spezieller `observation`-Type — Entscheidung in 4.1).

**Wann SHIKSHA es nutzt:** Wenn Mira mitten in der Session selbst zusammenfasst ("Eigentlich war's heute… okay") oder wenn SHIKSHA eine starke, klare Verdichtung gehört hat. Nicht reflexartig am Ende — das macht `/chat/close` zuverlässiger.

---

## 4. Aufruflogik — Wann SHIKSHA Tools nutzt

Die Aufruflogik ist **nicht** im Code festgeschrieben, sondern im Persona-Prompt. Das Modell entscheidet selbst, geleitet durch eine schmale Heuristik im System-Prompt:

> Du hast Werkzeuge. Sie sind keine Pflicht. Nutze sie sparsam, wenn ein Werkzeug das Gespräch oder zukünftige Gespräche substanziell besser macht. Nutze sie nicht, um zu zeigen, dass Du sie hast. Eine Session ohne einen einzigen Tool-Call ist eine gute Session, wenn der Inhalt es nicht verlangt.

Konkrete Heuristiken pro Modus aus dem 4-Mode Response Engine:

**PRÄSENZ** — Tool-Use ist hier fast immer falsch. Wenn Mira gerade ausatmet, schweigt SHIKSHA und tippt nicht im Hintergrund. Ausnahme: ein einzelnes `log_observation` wenn sie eine harte Fakten-Information rausgelassen hat ("Übrigens, L. ist seit Montag krank").

**FOKUS** — `log_observation` ist häufiger, weil hier konkrete Momente benannt werden. `log_friction` ist möglich, wenn der fokussierte Moment Teil eines erkannten Musters ist. `add_memory` nur, wenn das Detail langfristig relevant ist.

**VERDICHTEN** — Hier liegt der natürliche Schwerpunkt von `log_friction` und `add_memory`. Wenn SHIKSHA "Das ist nicht zum ersten Mal" sagt, sollte intern auch ein `log_friction` feuern, sonst war's nur Lippenbekenntnis.

**AUSKLANG** — Tool-Use sparsam. Der Session-Close-Mechanismus macht hier den Hauptlauf. Ausnahme: `save_day_summary` wenn Mira mitten im Ausklang selbst zusammenfasst.

---

## 5. Was Mira sieht — UX-Regeln pro Tool

Pro Tool ein Eintrag, wie viel Mira davon mitbekommt.

### `log_observation`

**Mira sieht:** Nichts. Pure Hintergrund-Aktion. Die Antwort von SHIKSHA enthält keinen Hinweis darauf, dass eine Beobachtung geloggt wurde.

**Begründung:** Beobachtungen sind das Gleiche wie das, was ein aufmerksamer Mensch sich beim Zuhören merkt. Niemand sagt "Ich merke mir das mal." — man merkt sich's einfach.

### `log_friction`

**Mira sieht:** In etwa 50% der Fälle nichts. In den anderen 50% kann SHIKSHA eine Andeutung machen — aber als natürlicher Bestandteil der Antwort, nicht als UI-Signal: "Das hatten wir vor zwei Wochen schon einmal." Das ist die einzige Sichtbarkeit, die erlaubt ist.

**Verboten:** "Ich habe das als wiederkehrendes Muster markiert." "Friction-Punkt #14 erkannt." Jede Form von Meta-Sprache über die Klassifikation.

### `add_memory`

**Mira sieht:** In etwa 30% der Fälle ein einziges Wort oder einen kurzen Halbsatz: "Notiert." "Das nehme ich mit." "Behalte ich." — eingebettet in die Antwort, kein UI-Element. In den anderen 70% nichts.

**Verboten:** "Ich habe das in deine Memory gespeichert." Jede Form von expliziter Persistenz-Sprache.

**Optional in Phase 4.5:** Ein extrem subtiles Frontend-Microsignal — z.B. ein 200ms-Fade-Highlight auf der Antwort-Bubble, ohne Text. Entscheidung in 4.5 selbst, nach Vorab-Probe.

### `save_day_summary`

**Mira sieht:** Nichts während der Session. Die Summary erscheint später in der Verlauf-Ansicht als Teil des Session-Eintrags.

---

## 6. Was Mira nie sieht

Eine explizite Verbotsliste, damit Implementierer nicht "wohlmeinend" nachhelfen:

- Tool-Namen in irgendeiner Form.
- JSON-Fragmente, Argument-Listen, Schema-Andeutungen.
- Lade-Indikatoren, Spinner, Progress-Bars während Tool-Calls.
- System-Toasts oder Banner ("Erinnerung gespeichert").
- Tool-Anzahl oder -Statistik in der UI ("3 Beobachtungen heute").
- "Hinweis"-Boxen, "Tipp"-Karten, "Info"-Tooltips über das Tool-System.
- Begriffe wie *Funktion, Tool, Werkzeug, Aktion, System, Backend, Datenbank, gespeichert, geloggt, registriert*. (Außer im Trägerin-Dashboard — siehe Abschnitt 7.2.)

---

## 7. Permissions & Security

### 7.1 Operator-Skopus

Tools schreiben ausschließlich in den Datenraum des aktiven Operators (`get_current_operator` aus dem JWT). Ein Tool-Call kann nicht für eine andere Person loggen. Diese Regel ist hart — sie wird in der Tool-Runtime (4.1) als erstes geprüft, **bevor** das Tool ausgeführt wird. Eine Verletzung führt zu einem 403, das das Modell als Tool-Error sieht und sich in der nächsten Iteration anders entscheiden muss.

### 7.2 Trägerin-Sicht vs. Mira-Sicht

In der Trägerin-Dashboard-Ansicht (Phase 6) **darf** Reibung explizit angezeigt werden — als Liste, als Karte, mit Häufigkeit und erster Beobachtung. Das ist nicht widersprüchlich zur Zahnarzt-Regel, weil das Dashboard ein Reflektions-Werkzeug ist, kein Gesprächs-Kontext. Mira liest das aktiv, sucht aktiv nach Mustern — da darf Klartext stehen.

Die Zahnarzt-Regel gilt für den **Gesprächs-Kanal** (mira_app Tagesausklang, krummelus_kennenlernen). Nicht für den Reflektions-Kanal.

### 7.3 Idempotenz

Tool-Calls sind nicht implizit idempotent. Wenn das Modell zwei Mal `add_memory` mit identischem Text aufruft, gibt es zwei Memory-Einträge. Das ist eher Featue als Bug — Wiederholung deutet auf Relevanz hin. **Falls** sich das als Rauschen erweist, kommt in Phase 4.6 ein Dedup-Check auf Basis von Text-Ähnlichkeit (cosine über Embeddings oder simpler Jaccard) dazu.

### 7.4 Rate-Limiting

Tool-Calls werden nicht separat rate-limited. Sie zählen auf das bestehende Rate-Limit-Bucket pro Operator, das schon für `/chat/respond` greift. Eine Session mit 20 Tool-Calls verbraucht das Budget schneller — das ist akzeptabel und ein natürlicher Anreiz für die Modell-Heuristik, sparsam zu sein.

---

## 8. Audit & Reversibilität

Jeder Tool-Call wird im `audit_logs` festgehalten — mit Tool-Name, Operator-ID, Session-ID, Argumenten (gehasht falls sensibel), Zeitstempel. Das passiert in der Tool-Runtime automatisch, nicht als Verantwortung des einzelnen Tool-Handlers.

**Reversibilität:**
- `log_observation`, `log_friction`, `add_memory`, `save_day_summary` sind alle **soft-deletable**. In der Datenbank gibt es ein `deleted_at`-Feld. Im Trägerin-Dashboard kann Mira einzelne Einträge ausblenden.
- Die Einträge bleiben für Audit-Zwecke sichtbar bis zur expliziten harten Löschung (Phase 6 oder später).
- **Cowork-/Operator-Aspekt:** Das Frontend wird `delete_memory`-Calls (Phase 4 schon vorhanden im Memory-Router) für Eintragstyp Memory anbieten. Für Friction & Observation kommt das Lösch-UI in Phase 6.

---

## 9. Verhältnis zu `/chat/close` (Insights-Extraction)

Heute (nach Schritt 2): Wenn eine Session geschlossen wird, läuft eine separate LLM-Anfrage, die Summary + Observations + Friction-Candidates + Memory-Candidates als strukturiertes JSON zurückgibt. Die Memory-Kandidaten werden Mira nicht automatisch in den Memory-Speicher gelegt — sie müssen aktiv bestätigt werden (Stand: ja/nein-Toggle in der Verlauf-Ansicht, oder Trägerin-Dashboard-Review).

Mit Tool-Use kommen zusätzlich **inline** während der Session schon Einträge dazu. Zwei Mechanismen, die sich überschneiden. Regelung:

- **Inline-Tool-Calls** schreiben direkt (`log_observation`, `log_friction`, `save_day_summary`) oder als **vorgeschlagen** (`add_memory` → Status `proposed`, nicht `active`).
- **Close-Extraction** ergänzt das mit allem, was inline nicht gefangen wurde. Dedup gegen die Inline-Einträge der Session (gleiche Session-ID, ähnlicher Text → kein doppelter Eintrag).

Das hat den Effekt, dass die Close-Extraction kleiner und sauberer wird, je besser das Modell mit Tool-Use umgeht. Beides hat seinen Platz: Inline ist schneller und kontextnah, Close ist garantiert und strukturiert.

---

## 10. Edition-Agnostik

Die vier Phase-4-Tools sind universell — jede Edition (KITA, Schule, Surf, Yoga, Camping, Club) kann sie nutzen. Die Edition entscheidet nur, **wie sehr** sie genutzt werden, via Persona-Prompt-Heuristik.

Edition-spezifische Tools (Phase 5+) folgen demselben Schema:

- Tool-Definition in `editions/<edition>.yaml` unter `extra_tools:`.
- Handler-Implementierung in `services/tools_<edition>.py`.
- Persona-Prompt-Erweiterung pro Edition.

Beispiele für später (nicht in Phase 4):
- `kita`: `log_personalknappheit_day` mit Datum + Schwere.
- `surf`: `log_swell_session` mit Höhe + Windrichtung + Teilnehmer.
- `schule`: `log_klassen_dynamik` mit Klassen-ID + freier Text.

Die Runtime ist edition-aware — beim Laden für eine Operator-Session werden Core-Tools + Edition-Tools gemerged.

---

## 11. Fehlerverhalten

Was passiert, wenn ein Tool fehlschlägt?

**DB-Schreibfehler** (z.B. Connection-Drop): Die Runtime fängt die Exception, schreibt einen Fehler-Eintrag in `audit_logs`, und gibt dem Modell ein `tool_result` mit `is_error: true` und einer kurzen, neutralen Fehlerbeschreibung zurück. Das Modell entscheidet selbst: erneut versuchen, anderes Tool, oder einfach normal weiter-antworten. **Mira sieht in keinem Fall etwas vom Fehler.**

**Permission-Fehler** (Operator-Skopus verletzt): `tool_result` mit `is_error: true`, Text "Permission denied for this tool call". Das ist eher ein Modell-Hinweis als ein Fehlerfall — sollte praktisch nie auftreten.

**Argument-Fehler** (Validierung fehlgeschlagen): `tool_result` mit `is_error: true`, Text mit konkretem Hinweis welches Argument fehlt oder zu lang ist. Modell korrigiert sich im nächsten Turn.

**Loop-Termination:** Maximale Tool-Calls pro Mira-Nachricht: 5. Wenn das Modell mehr aufrufen will, bricht die Runtime ab und zwingt einen Text-Response. Schutz gegen Endlos-Schleifen.

---

## 12. Tech-Notiz: Multi-Turn-Loop

Implementierungs-Skizze für 4.2 — gehört nicht in die Spec, ist aber hier als Anker, damit niemand den falschen Weg geht:

```
def respond_with_tools(messages, system, tools, operator, db):
    iterations = 0
    while iterations < 5:
        iterations += 1
        result = anthropic.messages.create(
            messages=messages,
            system=system,
            tools=tools,
            ...
        )
        if result.stop_reason == "end_turn":
            return assemble_text_response(result)
        if result.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": result.content})
            tool_results = []
            for block in result.content:
                if block.type == "tool_use":
                    tool_results.append(execute_tool(
                        name=block.name,
                        args=block.input,
                        tool_use_id=block.id,
                        operator=operator,
                        db=db,
                    ))
            messages.append({"role": "user", "content": tool_results})
            continue
        # Unexpected stop reason — break with what we have
        return assemble_text_response(result)
    # Loop guard hit — force terminal text response
    return force_text_response(messages, system)
```

Streaming-Variante (4.4) buffert tool_use-Blöcke aus dem Stream, führt sie aus während weitere Deltas reinkommen, und hängt das Ergebnis im nächsten Stream-Cycle dran. Detailliert in 4.4 selbst.

---

## 13. Was diese Spec nicht regelt

- **Welches Persona-Prompt welche Heuristik konkret kriegt** — das gehört in 4.3 als Edit der Persona-YAML-Dateien.
- **Wie die DB-Tabelle `day_summaries` aussieht** — Schema-Entscheidung in 4.1 (entweder neue Tabelle oder erweitertes `observations`-Schema).
- **Wie das Trägerin-Dashboard Reibung darstellt** — gehört in Phase 6.
- **Edition-spezifische Tools** — Phase 5+.

---

## 14. Akzeptanzkriterien für Schritt 4

Die Phase ist erst dann fertig, wenn:

1. Eine Mira-Nachricht "Letzte Woche war es Mittwoch wieder so personalschwach" einen `log_friction`-Call triggert (sichtbar in audit_logs, nicht in der Antwort).
2. Eine Mira-Nachricht "Übrigens, L. ist seit Montag krank" einen `log_observation`-Call triggert (gleiche Sichtbarkeitsregel).
3. Eine reine PRÄSENZ-Antwort ("Ich höre.") **keinen** Tool-Call macht, obwohl die Runtime verfügbar ist.
4. Eine Session, in der intensive Tool-Use läuft, am Ende beim `/chat/close` **keine** Duplikate produziert — Insights-Extraction dedupliziert gegen die schon vorhandenen Inline-Einträge.
5. Die Mira-UI zeigt in **keinem** der Fälle ein Tool-Signal, einen Spinner, einen Toast, einen Tool-Namen oder JSON.
6. Audit-Logs sind vollständig — jeder Tool-Call hat einen Eintrag mit Operator, Session, Tool, Argumenten und Timestamp.

---

## Glossar

- **Tool / Werkzeug** — vom Modell aufrufbare Server-Aktion. Im Mira-Frontend nie als Begriff verwendet.
- **Inline-Call** — Tool-Aufruf während laufender Session (Phase 4-Mechanismus).
- **Close-Extract** — Insights-Extraktion am Session-Ende (Phase 2-Mechanismus, bleibt parallel zu Inline).
- **Microsignal** — eingebettete, sehr subtile Quittung in der Antwort. Kein UI-Element. Beispiel: "Notiert."
- **Zahnarzt-Regel** — siehe Abschnitt 1. Bindendes Leitprinzip für alle Tool-UX-Entscheidungen.
