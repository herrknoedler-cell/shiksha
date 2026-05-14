# SHIKSHA — Repo-Map (Cowork-Memory)

**Zweck:** Pre-Drop-Reading für alle, die Code in dieses Repo bauen — Cowork-Author, Claude Code, jeder Developer-Reviewer. Diese Datei sammelt die Konventionen, deren Verletzung in den letzten Modulen zu **wiederholten Drop-Bugs** geführt hat (siehe T-002 in SHIKSHA_TECH_DEBT.md).

**Update-Regel:** Wenn ein neuer Drop-Bug eine neue Klasse aufdeckt — diese Datei mit Lesson erweitern, plus T-002 mit Verweis darauf. Live-Dokument.

---

## 1. Repo-Struktur

```
/Users/thomasknodler/code/shiksha/
├── frontend/
│   ├── heim.html
│   ├── personen.html
│   ├── kalender.html
│   ├── presence_switch.html
│   ├── shiksha-client.js
│   ├── shiksha-ui.v1.0.0.{js,css}
│   ├── shiksha-icons.v1.0.0.svg
│   └── editions-css/kita.v1.0.0.css
├── server/shiksha_engine/
│   ├── shiksha_engine/
│   │   ├── db.py              ← Modul heißt 'db', NICHT 'database'
│   │   ├── main.py            ← Router-Prefixes kommen HIER, nicht im Router
│   │   ├── deps.py            ← Auth-Dependencies
│   │   ├── models/            ← SQLAlchemy
│   │   ├── schemas/           ← Pydantic v2
│   │   ├── routers/           ← FastAPI Routes (ohne Prefix)
│   │   ├── services/          ← Geschäftslogik
│   │   └── alembic/versions/  ← Migrations
│   ├── scripts/               ← Import-Skripte, einmalige Tasks
│   ├── tests/                 ← pytest
│   └── editions/              ← YAML: kita.yaml, core.yaml, …
└── docs/specs/                ← SHIKSHA_*_SPEC.md
```

**Server-Pfad (Hetzner):** `/opt/shiksha-engine/` — Spiegel des `server/shiksha_engine/` aus dem Repo.

---

## 2. Modul-Imports (Python)

| Falsch | Richtig |
|---|---|
| `from shiksha_engine.database import …` | `from shiksha_engine.db import …` |
| `from shiksha_engine.models import Event` | `from shiksha_engine.models.event import Event` |

Standard-Patterns:

```python
from shiksha_engine.db import SessionLocal, Base, get_db
from shiksha_engine.models.event import Event
from shiksha_engine.models.person import Person
from shiksha_engine.models.operator import Operator
from shiksha_engine.deps import (
    require_authenticated,         # Liest, alle Rollen
    require_operator_or_developer, # Schreibt, kein eltern/teilnehmer
    require_leitung_or_developer,  # Admin-Operationen
)
from shiksha_engine.services.jwt_service import issue_token
```

---

## 3. SQLAlchemy-Konventionen

**Schemas:**
- Production: `shiksha_core`
- Tests: `shiksha_core_test` (Env `DB_SCHEMA`)

**PK-Typ:** Alle Tabellen nutzen `Integer` mit `SERIAL` (Autoincrement). **NIEMALS UUID-PK setzen** — die DB macht's selbst.

```python
# RICHTIG
class Event(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
# Im Constructor: KEIN id= setzen
event = Event(tenant_org_id="krummelus", ...)

# FALSCH
event = Event(id=uuid4(), ...)  # ← uuid4 in Integer-Spalte → DataError
```

**FK-Pattern:** Dynamisch über Schema-Helper, NICHT hardkodiert.

```python
# RICHTIG (aus person.py-Pattern)
__table_args__ = (
    UniqueConstraint("legacy_id", "legacy_source", name="uq_..."),
    schema_args(),  # nutzt schema_name() intern
)
tenant_org_id: Mapped[str] = mapped_column(
    Text,
    ForeignKey(f"{schema_name()}.organizations.id", ondelete="CASCADE"),
    nullable=False,
)

# FALSCH
ForeignKey("shiksha_core.organizations.id")  # bricht im Test-Schema
```

**Time:** `TIMESTAMPTZ` für alle Datumsfelder. Storage UTC, Display-TZ aus `organizations.timezone`.

```python
start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

**metadata-Spalte:**

```python
# RICHTIG — Spaltenname mit Underscore direkt im DB-Layer
metadata_: Mapped[dict[str, Any]] = mapped_column(
    "metadata_", JSONB, nullable=False, default=dict
)
```

Migration-SQL: `sa.Column("metadata_", JSONB, ...)` — Underscore ist Teil des Spaltennamens. Umgeht SQLAlchemy-`Base.metadata`-Namespace-Kollision.

**Soft-Delete:** `deleted_at: Mapped[datetime | None]` Nullable. Read-Queries filtern auf `deleted_at IS NULL`.

**Legacy-Import:** Idempotenz über `(legacy_id, legacy_source)` UNIQUE-Constraint. Beide sind `Text`-Felder (NICHT Integer — Mira's legacy-IDs sind Strings).

---

## 4. Migration-vs-Model-Pair-Convention

**Eine Migration, die eine Tabelle ändert, MUSS im selben Drop das entsprechende Python-Model anpassen.**

Beispiel-Bug aus 5.5.4.1: Migration fügte `organizations.timezone` hinzu, aber das Python-`Organization`-Model wurde nicht parallel aktualisiert. Resultat: SQLAlchemy wusste nichts von der Spalte, Read leer, Insert SQL-Error.

Vor jedem Drop mit Migration: prüfen, dass jede `ALTER TABLE` / `ADD COLUMN` im Migration-SQL eine entsprechende Mapped-Spalte im Model hat.

---

## 5. Pydantic v2-Konventionen

**`alias` vs `validation_alias`:**

```python
# RICHTIG — validation_alias ist input-only
class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata_",  # ORM-Attribut heißt metadata_
    )                                  # JSON-Output-Key bleibt 'metadata'

# FALSCH — alias ist bidirektional, ändert auch JSON-Output zu 'metadata_'
metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
```

**`model_config = ConfigDict(from_attributes=True, populate_by_name=True)`** ist Standard für alle `*Out`-Schemas, die aus SQLAlchemy-Models gebaut werden.

---

## 6. FastAPI Router-Konventionen

**Prefix kommt aus `main.py`**, NIEMALS im Router-File selbst:

```python
# RICHTIG — routers/calendar.py
router = APIRouter(tags=["calendar"])

# main.py
from shiksha_engine.routers import calendar
app.include_router(calendar.router, prefix="/api/v1/calendar")

# FALSCH — routers/calendar.py
router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])
```

**Tag-Konvention:** Plural, lowercase, in Englisch (`calendar`, `persons`, `heim`, `bridge`).

**Dependencies:**

| Endpoint-Typ | Dependency |
|---|---|
| `GET` (lesen, auch eltern/teilnehmer) | `require_authenticated` |
| `POST` / `PATCH` / `DELETE` | `require_operator_or_developer` |
| Admin-Endpoints (Settings, Config) | `require_leitung_or_developer` |

---

## 7. Test-Konventionen (pytest + conftest)

**TRUNCATE-Liste** im conftest muss in FK-Reihenfolge gehalten werden (Child-Tabellen vor Parent-Tabellen) ODER mit `TRUNCATE … CASCADE`. Wenn neue Tabelle: vor `operators` und `organizations` einfügen.

**Fixtures:**

```python
# RICHTIG — nullable Felder weglassen
@pytest.fixture
def krummelus_kind(db_session):
    p = Person(
        tenant_org_id="krummelus",
        kind="kind",
        given_name="Test",
        active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        # legacy_id, legacy_source weggelassen (nullable)
    )
    db_session.add(p)
    db_session.commit()
    return p

# FALSCH — hardkodierte Type-Annahmen
p = Person(..., legacy_id="bday-test")  # ← String in Integer-Spalte → DataError
```

**Token-Issue in Fixtures:** über `issue_token()` direkt, mit allen aktuellen Claims:

```python
@pytest.fixture
def mira_token(mira_leitung):
    return issue_token(
        operator_id=mira_leitung.id,
        role="leitung",
        edition="kita",
        org_id="krummelus",
        org_timezone="Europe/Vienna",  # ← seit 5.5.4.1 Pflicht
    )
```

**URL-Datetime in Tests:** `Z`-Suffix erzwingen, sonst wird `+` im URL-Query zu Space:

```python
# RICHTIG
now_z = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
r = client.get(f"/api/v1/calendar/events?from={now_z}")

# Oder via urllib.parse.quote(now.isoformat())

# FALSCH
r = client.get(f"/api/v1/calendar/events?from={now.isoformat()}")  # → 422
```

---

## 8. Frontend-Konventionen

**Design-System:**
- Eine Schrift: Montserrat (von Google Fonts CDN)
- Eine CSS-Datei: `shiksha-ui.v1.0.0.css`
- Eine JS-Datei: `shiksha-ui.v1.0.0.js` mit `initShikshaUI()`, `openModal()`, `closeModal()`
- Edition-Override: `editions-css/<edition>.v1.0.0.css`

**Tab-Pattern** (konsistent über heim/personen/kalender):

```html
<div class="shk-tabs" data-shk-tabs>
  <button class="shk-tab shk-tab--active" data-shk-tab="A">A</button>
  <button class="shk-tab" data-shk-tab="B">B</button>
</div>
<section data-shk-tab-panel="A">…</section>
<section data-shk-tab-panel="B" class="shk-hidden">…</section>
```

JS-Handler nutzt `dataset.shkTab` / `dataset.shkTabPanel`. KEINE eigenen Custom-Attribute (`data-view`, `data-pane`) für Tabs einführen — die kollidieren mit `initShikshaUI()`-Auto-Handlern.

**Theme-Toggle:**

```html
<!-- Im <head>, vor allen <link>: FOUC-Schutz -->
<script>
  (function () {
    try {
      var t = localStorage.getItem('shiksha-theme');
      if (t === 'light' || t === 'dark') {
        document.documentElement.setAttribute('data-theme', t);
      }
    } catch (e) {}
  })();
</script>

<!-- Im Header: -->
<button class="shk-theme-toggle" data-shk-theme-toggle aria-label="Theme umschalten">
  <svg class="shk-icon shk-icon--sm">
    <use href="./shiksha-icons.v1.0.0.svg#icon-weather-sun"/>
  </svg>
  <span data-shk-theme-label>Modus</span>
</button>
```

**ShikshaClient-Import:**

```javascript
import { ShikshaClient, ShikshaAuthError } from './shiksha-client.js';
import { initShikshaUI, openModal, closeModal, avatarInitials } from './shiksha-ui.v1.0.0.js';

const client = new ShikshaClient();
if (!client.hasValidToken()) {
  location.replace(`./presence_switch.html?next=${encodeURIComponent(location.pathname)}`);
}
initShikshaUI({ context: '...' });
```

**Asset-Pfade:** relativ (`./shiksha-…`) — NICHT absolut (`/shiksha-…`). Macht local-server-Test einfacher.

---

## 9. Drop-Workflow

**Vor Drop-Bau:**

1. Aktuellen Repo-Stand prüfen — `git log --oneline -10` und die Files lesen, die Du editieren willst
2. Prüfen: gibt's einen `*_Veralten`-Risk? Wenn das Output-File älter sein könnte als der Repo-Stand, **als Edit-Anweisungen formulieren**, nicht als komplette Datei
3. Diese Repo-Map durchscrollen — gehört Dein Drop zu einer Klasse, die schon Bugs hatte? Konventionen checken

**Im Drop:**

- Spec-Verweis im Header (z.B. "Spec: SHIKSHA_CALENDAR_SPEC.md §6")
- Akzeptanzkriterien mit Checkboxen
- Rollback-Anleitung
- Sektion "Wahrscheinliche Drop-Bugs (preemptiv)" — was könnte schief gehen, was Claude Code antizipieren soll

**Bei kompletten Files (Rewrite):**

- Explizit als "ÜBERSCHREIBT" markieren
- Claude Code macht **immer** `diff` vor `cp`, dokumentiert die Differenzen
- Bug-Fixes, die Claude Code lokal gemacht hat, NICHT überschreiben — manuell mergen

---

## 10. Bekannte Drop-Bug-Checkliste

Vor jedem Drop diese Liste durchgehen:

- [ ] **Python-Imports:** `shiksha_engine.db` (nicht `.database`)
- [ ] **PK-Typ:** Integer-Autoincrement, kein `id=uuid4()` setzen
- [ ] **FK-Pattern:** dynamisch via `schema_name()`, nicht hartkodiertes `"shiksha_core."`
- [ ] **Migration + Model:** parallel angepasst (jede ALTER TABLE = entsprechende Mapped-Spalte)
- [ ] **Pydantic:** `validation_alias` (input-only) statt `alias` (bidirektional)
- [ ] **Pydantic:** `model_config = ConfigDict(from_attributes=True, populate_by_name=True)`
- [ ] **Router:** kein Prefix im Router, kommt aus `main.py`
- [ ] **URL-Datetime in Tests:** Z-Suffix erzwingen
- [ ] **Conftest-Fixtures:** keine hardkodierten Type-Annahmen, nullable Felder weglassen
- [ ] **Frontend-Tabs:** `data-shk-tab*` (nicht eigene Custom-Attribute)
- [ ] **Frontend-Assets:** relative Pfade (`./`)
- [ ] **Master-Code-Drift:** vor `cp` `diff` machen, lokale Bug-Fixes nicht überschreiben

---

## 11. Repository-Spezifika (Krummelus-Pilot)

| Was | Wert |
|---|---|
| Tenant | `krummelus` (Vorarlberg) |
| Timezone | `Europe/Vienna` |
| Server | `root@88.99.174.186` (Hetzner) |
| SSH-Key | `~/.ssh/shiksha_key` |
| API | `https://api.shiksha.world` |
| Frontend | `https://app.shiksha.world` |
| DB | `shiksha` (PostgreSQL), Schema `shiksha_core` |
| Engine | systemd unit `shiksha-engine` |
| JWT-Secret | aus systemd Drop-In: `/etc/systemd/system/shiksha-engine.service.d/database.conf` |
| Mira-Operator-ID | `krummelus_mira` (role=leitung, kind=staff) |
| Thomas-Operator-ID | `thomas` (role=developer, kind=system, org_id=krummelus seit 5.5.3.5-Fix) |

**SSH-Auth-Beispiel für Smoke-Tests:**

```bash
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 << 'REMOTE'
JWT_SECRET=$(systemctl show shiksha-engine -p Environment --no-pager | tr ' ' '\n' | grep JWT_SECRET | cut -d= -f2-)
DB_PW=$(grep -oP 'shiksha:\K[^@]+' /etc/systemd/system/shiksha.service.d/database.conf | head -1)
export JWT_SECRET DATABASE_URL="postgresql://shiksha:${DB_PW}@localhost:5432/shiksha"
cd /opt/shiksha-engine && source .venv/bin/activate
# Dein Smoke-Test hier
REMOTE
```

---

## 12. Wenn Du diese Datei änderst

Diese Datei ist live. Wenn ein neuer Drop-Bug eine neue Klasse aufdeckt:

1. Hier in der Repo-Map die neue Konvention dokumentieren
2. In SHIKSHA_TECH_DEBT.md T-002 um den neuen Punkt erweitern
3. Im nächsten Drop-Doc auf die Stelle in dieser Map verweisen ("siehe Repo-Map §X")

**Format-Konvention für neue Sektionen:**
- Falsch/Richtig-Tabelle wo möglich
- Code-Snippets mit Begründung
- Verweis auf den Drop, der die Lesson aufgedeckt hat

---

**Letzte Aktualisierung:** 2026-05-14 (nach Schritt 5.5.4 Abschluss)
