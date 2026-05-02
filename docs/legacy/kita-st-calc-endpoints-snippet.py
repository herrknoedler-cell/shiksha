"""
SHIKSHA · KITA · kita_st_calc_endpoints.py — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle, am 29.04.2026 via deploy-Skript an
/opt/shiksha/kita_compliance_router.py ANGEHÄNGT — nicht als
eigenständiger Router deployed.

Der deployed-Stand lebt heute in:
    server/kita_compliance_router.py  (omnibus router, ~5389 Zeilen)

Bei einer späteren Modul-Trennung kann dieses Snippet zurück nach
server/kita_st_calc_endpoints.py wandern.

Original: cowork/outputs/kita/server/kita_st_calc_endpoints.py (2026-04-29)
Importiert: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

"""
SHIKSHA · KITA · ST%-Rechner (Vorarlberg KKG)
Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.

Berechnungs-Logik 1:1 nach offiziellem Land-Vorarlberg-Excel (St_-Berechnung_Personaleinsatz_KKG):
- Pro Halbtag: ST% = Kinderzahl × Faktor × Öffnungsstunden
- Faktor 0,33 (Variante 1, überw. 0-1J) oder 0,20 (Variante 2, überw. 2J)
- VB-Zeit: 16h Mindest pro Gruppe + Leitungs-VBZ (gestaffelt nach Gruppenanzahl)
- Stundensatz: KV (39h → 2,564 ST%/h) oder GAG (40h → 2,5 ST%/h)
- Förder-Staffel: Jahr 1 = 80% Land, Jahr 2 = 75%, Jahr 3 = 70%, Jahr 4+ = 60%

Stand: 29.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

from datetime import date as _stc_date
from decimal import Decimal as _stc_Decimal


# ============================================================
# KONSTANTEN (1:1 aus Vorarlberg-Excel)
# ============================================================

WEEKDAYS = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag"]
HALFDAYS = ["vm", "nm"]   # 10 Halbtage = 5 × 2

# Variante 1: KKG mit überw. 0-1J (1:3 Schlüssel)
VAR1_ST_PRO_KIND = 0.33
VAR1_MAX_KINDER = 9

# Variante 2: KKG mit überw. 2J (1:5 Schlüssel)
VAR2_ST_PRO_KIND = 0.20
VAR2_MAX_KINDER = 12

# VB-Zeit
VBZ_MIN_PRO_GRUPPE_H = 16
VBZ_LEITUNG_TABLE = {1: 1, 2: 2, 3: 4}  # 4-8 Gruppen → 6h

# Stundensatz nach Lohnschema
KV_ST_PRO_STUNDE = 2.5641   # 100% / 39h
GAG_ST_PRO_STUNDE = 2.5000  # 100% / 40h

# Förder-Staffel (Jahr 1 → ab Jahr 4)
FOERDER_STAFFEL_LAND = {1: 80, 2: 75, 3: 70, 4: 60}


# ============================================================
# CORE BERECHNUNG
# ============================================================

def _stc_choose_variante(halfday: dict) -> tuple[str, float, int]:
    """
    Wählt die richtige Variante für einen Halbtag basierend auf Alters-Mix.

    Regel: Wenn ≥4 Kinder unter 2J ODER Mehrheit unter 2J → Variante 1 (strenger)
           Wenn ≥3-Jährige in Mehrheit → KIGA-Warnung (keine KKG)
           Sonst: Variante 2

    halfday: {"oz": 4.5, "n_0_1": 2, "n_2": 5, "n_3": 0, "n_4_plus": 0, "n_i_kind": 0}
    """
    n_0_1 = int(halfday.get("n_0_1") or 0)
    n_2 = int(halfday.get("n_2") or 0)
    n_3 = int(halfday.get("n_3") or 0)
    n_4_plus = int(halfday.get("n_4_plus") or 0)
    total = n_0_1 + n_2 + n_3 + n_4_plus

    if total == 0:
        return ("none", 0.0, 0)

    # Hinweis: Wenn ≥3-Jährige in Mehrheit, ist's eine KIGA-Gruppe
    if (n_3 + n_4_plus) > (n_0_1 + n_2):
        return ("kiga_warning", 0.0, total)

    # Variante 1 wenn ≥4 unter 2 ODER Mehrheit unter 2
    if n_0_1 >= 4 or n_0_1 > n_2:
        return ("variante_1", VAR1_ST_PRO_KIND, total)

    # Sonst Variante 2 (überwiegend 2-Jährige)
    return ("variante_2", VAR2_ST_PRO_KIND, total)


def _stc_calc_halfday_st(halfday: dict) -> dict:
    """Berechnet ST% für einen einzelnen Halbtag."""
    oz = float(halfday.get("oz") or 0)
    variante, faktor, n_kinder = _stc_choose_variante(halfday)

    if oz <= 0 or n_kinder == 0:
        return {"variante": variante, "n_kinder": n_kinder, "oz": oz, "st_pct": 0.0}

    if variante == "kiga_warning":
        return {
            "variante": variante, "n_kinder": n_kinder, "oz": oz,
            "st_pct": 0.0, "warning": "≥3-Jährige in Mehrheit — Kindergartengruppe!",
        }

    # Cap: nicht mehr als max-Kinder zählen für die Berechnung
    max_n = VAR1_MAX_KINDER if variante == "variante_1" else VAR2_MAX_KINDER
    effektive_n = min(n_kinder, max_n)

    st_pct = effektive_n * faktor * oz
    return {
        "variante": variante,
        "n_kinder": n_kinder,
        "n_kinder_effektiv": effektive_n,
        "oz": oz,
        "faktor": faktor,
        "st_pct": round(st_pct, 2),
        "exceeds_max": n_kinder > max_n,
    }


def _stc_calc_kinderdienst(halfday_data: dict) -> tuple[float, list, str]:
    """
    Summiert ST% Kinderdienst über alle 10 Halbtage.
    Return: (total_st_pct, [details_per_halfday], dominant_variante)
    """
    total = 0.0
    details = []
    variants_used = []
    has_kiga = False

    for wd in WEEKDAYS:
        for hd in HALFDAYS:
            key = f"{wd}_{hd}"
            halfday = halfday_data.get(key, {}) or {}
            res = _stc_calc_halfday_st(halfday)
            total += res["st_pct"]
            details.append({"halfday": key, **res})
            if res["variante"] not in ("none", "kiga_warning"):
                variants_used.append(res["variante"])
            if res["variante"] == "kiga_warning":
                has_kiga = True

    # Dominant variante
    if not variants_used:
        dominant = "none"
    elif all(v == "variante_1" for v in variants_used):
        dominant = "variante_1"
    elif all(v == "variante_2" for v in variants_used):
        dominant = "variante_2"
    else:
        dominant = "mixed"

    return round(total, 2), details, dominant, has_kiga


def _stc_calc_vbz(funding_basis: str, group_count: int) -> tuple[float, float, float]:
    """
    Berechnet VB-Zeit ST%:
    - Pro Gruppe: 16h × Stundensatz
    - Leitung: gestaffelt nach Gruppenanzahl × Stundensatz

    Return: (st_gruppe, st_leitung, total)
    """
    rate = KV_ST_PRO_STUNDE if funding_basis.upper() == "KV" else GAG_ST_PRO_STUNDE
    st_gruppe = VBZ_MIN_PRO_GRUPPE_H * rate

    if group_count <= 0:
        leitung_h = 0
    elif group_count <= 3:
        leitung_h = VBZ_LEITUNG_TABLE.get(group_count, 0)
    else:
        leitung_h = 6  # 4-8 Gruppen → 6h

    st_leitung = leitung_h * rate
    return round(st_gruppe, 2), round(st_leitung, 2), round(st_gruppe + st_leitung, 2)


def _stc_calc_ikind(i_kind_hours_per_week: float, funding_basis: str) -> float:
    """
    I-Kind-Zusatz (sofern genehmigt):
    Wochenstunden × Stundensatz × Faktor (variabel je nach Genehmigung — hier 1.0 als Standard)
    """
    if not i_kind_hours_per_week:
        return 0.0
    rate = KV_ST_PRO_STUNDE if funding_basis.upper() == "KV" else GAG_ST_PRO_STUNDE
    return round(i_kind_hours_per_week * rate, 2)


def _stc_funding_year(group_founded_at: _stc_date, current_month: _stc_date) -> int:
    """
    Berechnet das Förder-Jahr (1, 2, 3, 4+) basierend auf Gründungsdatum.
    Förderjahr beginnt in dem Monat der Gründung.
    """
    if not group_founded_at:
        return 4  # Default: ab 4. Jahr (60% Land)
    months_diff = (current_month.year - group_founded_at.year) * 12 + (current_month.month - group_founded_at.month)
    if months_diff < 12:
        return 1
    if months_diff < 24:
        return 2
    if months_diff < 36:
        return 3
    return 4


def _stc_funding_pct(funding_year: int) -> tuple[int, int]:
    """Land-/Stadt-Anteil basierend auf Förderjahr."""
    land = FOERDER_STAFFEL_LAND.get(min(funding_year, 4), 60)
    stadt = 100 - land
    return land, stadt


# ============================================================
# ENDPOINTS
# ============================================================

@kita_router.post("/st-calc/preview")
async def kita_stcalc_preview(payload: dict = Body(...)):
    """
    Live-Berechnung — kein DB-Save.
    Body:
      {
        "group_id": "grp_xyz",        // optional
        "halfday_data": {
          "montag_vm": {"oz": 4.5, "n_0_1": 2, "n_2": 5, "n_3": 0, "n_4_plus": 0, "n_i_kind": 0},
          "montag_nm": {...},
          ...
        },
        "funding_basis": "KV" | "GAG",
        "group_count": 1,             // Anzahl Gruppen der Einrichtung (für Leitung-VBZ)
        "i_kind_hours_per_week": 0,
        "snapshot_month": "2026-04-01"
      }
    """
    halfday_data = payload.get("halfday_data") or {}
    funding_basis = payload.get("funding_basis", "KV")
    group_count = int(payload.get("group_count", 1))
    i_kind_h = float(payload.get("i_kind_hours_per_week", 0) or 0)
    snapshot_month_str = payload.get("snapshot_month")
    group_id = payload.get("group_id")

    # 1. Kinderdienst (Halbtage)
    st_kinderdienst, details, dominant_variante, has_kiga = _stc_calc_kinderdienst(halfday_data)

    # 2. VB-Zeit
    st_vbz_gr, st_vbz_lt, st_vbz_total = _stc_calc_vbz(funding_basis, group_count)

    # 3. I-Kind
    st_ikind = _stc_calc_ikind(i_kind_h, funding_basis)

    # 4. Total
    st_total = round(st_kinderdienst + st_vbz_total + st_ikind, 2)

    # 5. Förder-Aufteilung (wenn Gruppe + Datum bekannt)
    funding_year = None
    land_pct = stadt_pct = None
    funding_breakdown = None
    if group_id and snapshot_month_str:
        with engine.connect() as conn:
            row = conn.execute(sa.text(
                "SELECT founded_at, name FROM kita_groups WHERE id=:id"
            ), {"id": group_id}).first()
        if row and row[0]:
            try:
                snapshot_month = _stc_date.fromisoformat(snapshot_month_str)
                funding_year = _stc_funding_year(row[0], snapshot_month)
                land_pct, stadt_pct = _stc_funding_pct(funding_year)
                # Aufteilung in ST%
                land_st = round(st_total * land_pct / 100, 2)
                stadt_st = round(st_total * stadt_pct / 100, 2)
                funding_breakdown = {
                    "funding_year": funding_year,
                    "land_pct": land_pct, "stadt_pct": stadt_pct,
                    "land_st": land_st, "stadt_st": stadt_st,
                    "group_founded_at": row[0].isoformat(),
                    "group_name": row[1],
                }
            except Exception as e:
                print(f"[stcalc] Förder-Aufteilung fehlgeschlagen: {e}")

    return {
        "st_kinderdienst": st_kinderdienst,
        "st_vbz_gruppe": st_vbz_gr,
        "st_vbz_leitung": st_vbz_lt,
        "st_vbz_total": st_vbz_total,
        "st_ikind": st_ikind,
        "st_total": st_total,
        "dominant_variante": dominant_variante,
        "has_kiga_warning": has_kiga,
        "halfday_details": details,
        "funding_breakdown": funding_breakdown,
        "constants_used": {
            "var1_st_pro_kind": VAR1_ST_PRO_KIND, "var1_max": VAR1_MAX_KINDER,
            "var2_st_pro_kind": VAR2_ST_PRO_KIND, "var2_max": VAR2_MAX_KINDER,
            "vbz_min_h": VBZ_MIN_PRO_GRUPPE_H,
            "stundensatz": KV_ST_PRO_STUNDE if funding_basis.upper() == "KV" else GAG_ST_PRO_STUNDE,
        },
    }


@kita_router.post("/st-calc/save")
async def kita_stcalc_save(payload: dict = Body(...)):
    """Speichert Berechnung als Snapshot pro Gruppe pro Monat."""
    group_id = payload.get("group_id")
    snapshot_month_str = payload.get("snapshot_month")
    if not group_id or not snapshot_month_str:
        raise HTTPException(400, "group_id + snapshot_month Pflicht")

    snapshot_month = _stc_date.fromisoformat(snapshot_month_str)

    # Erst Preview-Berechnung machen
    preview = await kita_stcalc_preview(payload)
    fb = preview.get("funding_breakdown") or {}

    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_st_calculations
              (id, group_id, snapshot_month, halfday_data,
               st_kinderdienst, st_vbz_gruppe, st_vbz_leitung, st_ikind, st_total,
               land_pct, stadt_pct, funding_year,
               variant_used, has_kiga_warning, created_by)
            VALUES (:id, :g, :m, :hd::jsonb,
                    :sk, :sg, :sl, :si, :st,
                    :lp, :sp, :fy, :v, :w, :cb)
            ON CONFLICT (group_id, snapshot_month) DO UPDATE SET
              halfday_data = EXCLUDED.halfday_data,
              st_kinderdienst = EXCLUDED.st_kinderdienst,
              st_vbz_gruppe = EXCLUDED.st_vbz_gruppe,
              st_vbz_leitung = EXCLUDED.st_vbz_leitung,
              st_ikind = EXCLUDED.st_ikind,
              st_total = EXCLUDED.st_total,
              land_pct = EXCLUDED.land_pct,
              stadt_pct = EXCLUDED.stadt_pct,
              funding_year = EXCLUDED.funding_year,
              variant_used = EXCLUDED.variant_used,
              has_kiga_warning = EXCLUDED.has_kiga_warning,
              updated_at = NOW()
        """), {
            "id": _new_id("stcalc"), "g": group_id, "m": snapshot_month,
            "hd": str(payload.get("halfday_data", {})).replace("'", '"'),
            "sk": preview["st_kinderdienst"],
            "sg": preview["st_vbz_gruppe"],
            "sl": preview["st_vbz_leitung"],
            "si": preview["st_ikind"],
            "st": preview["st_total"],
            "lp": fb.get("land_pct"),
            "sp": fb.get("stadt_pct"),
            "fy": fb.get("funding_year"),
            "v": preview.get("dominant_variante"),
            "w": preview.get("has_kiga_warning", False),
            "cb": payload.get("created_by", "kita-leitung"),
        })

    return {**preview, "saved": True, "snapshot_month": snapshot_month_str}


@kita_router.get("/st-calc/{group_id}")
async def kita_stcalc_history(group_id: str, year: int = None):
    """Historische Berechnungen pro Gruppe — Jahresübersicht."""
    sql = """
    SELECT snapshot_month, st_kinderdienst, st_vbz_gruppe, st_vbz_leitung,
           st_ikind, st_total, land_pct, stadt_pct, funding_year,
           variant_used, has_kiga_warning, updated_at
    FROM kita_st_calculations
    WHERE group_id = :g
    """
    params = {"g": group_id}
    if year:
        sql += " AND EXTRACT(YEAR FROM snapshot_month) = :y"
        params["y"] = year
    sql += " ORDER BY snapshot_month DESC"

    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).fetchall()

    return {
        "count": len(rows),
        "calculations": [
            {
                "snapshot_month": r[0].isoformat(),
                "st_kinderdienst": float(r[1]), "st_vbz_gruppe": float(r[2]),
                "st_vbz_leitung": float(r[3]), "st_ikind": float(r[4]),
                "st_total": float(r[5]),
                "land_pct": float(r[6]) if r[6] else None,
                "stadt_pct": float(r[7]) if r[7] else None,
                "funding_year": r[8],
                "variant_used": r[9],
                "has_kiga_warning": r[10],
                "updated_at": r[11].isoformat() if r[11] else None,
            }
            for r in rows
        ],
    }


@kita_router.get("/st-calc/funding/{group_id}")
async def kita_stcalc_funding_year(group_id: str, month: str = None):
    """Förder-Anteil Land/Stadt für eine Gruppe in einem Monat."""
    target_month = _stc_date.fromisoformat(month) if month else _stc_date.today().replace(day=1)
    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT founded_at, name FROM kita_groups WHERE id=:id"
        ), {"id": group_id}).first()
    if not row:
        raise HTTPException(404, "Gruppe nicht gefunden")
    if not row[0]:
        return {
            "group_id": group_id, "group_name": row[1],
            "warning": "Kein Gründungsdatum — Default 4. Jahr (60% Land)",
            "funding_year": 4, "land_pct": 60, "stadt_pct": 40,
        }
    funding_year = _stc_funding_year(row[0], target_month)
    land_pct, stadt_pct = _stc_funding_pct(funding_year)
    return {
        "group_id": group_id, "group_name": row[1],
        "founded_at": row[0].isoformat(),
        "target_month": target_month.isoformat(),
        "funding_year": funding_year,
        "land_pct": land_pct,
        "stadt_pct": stadt_pct,
    }
