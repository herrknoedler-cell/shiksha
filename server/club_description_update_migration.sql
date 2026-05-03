-- ============================================================
-- SHIKSHA · CLUB-Edition · Description-Refresh
-- Stand: 2026-05-03
-- ============================================================
-- Aktualisiert den Description-Text der CLUB-Edition in der
-- editions-Galerie. Vorher: feature-orientiert (Mitgliederverwaltung,
-- Beitrags-Automatik, ...). Nachher: zielgruppen- und architektur-
-- orientiert (Vereinstypen + 21-Module-Architektur + Safeguarding).
--
-- Idempotent — bei wiederholter Anwendung kein Effekt, weil die
-- WHERE-Klausel slug-spezifisch ist und der neue Text deterministisch.
-- ============================================================

UPDATE editions
   SET description = 'Eingetragene Vereine — Sportverein, Musikverein, Kulturverein, Jugendverband. 21 Module, sprachfähiger Vorstands-Co-Pilot, Safeguarding ab Tag 1.'
 WHERE slug = 'club';
