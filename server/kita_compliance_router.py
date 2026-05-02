"""
SHIKSHA · KITA · Compliance Router
FastAPI-Router für Vorarlberg KBBG-konforme Compliance.

Wird in main.py inkludiert mit:
  from kita_compliance_router import kita_router
  app.include_router(kita_router)

Stand: 28.04.2026
"""
from __future__ import annotations
import io
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean
from typing import List, Optional, Dict, Any

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Body, UploadFile, File, Query, Header
from fastapi.responses import FileResponse, HTMLResponse

# Engine kommt aus main.py (gemeinsame DB-Connection)




from database import engine


kita_router = APIRouter(prefix="/kita", tags=["kita-compliance"])


# ============================================================
# HELPERS
# ============================================================

def _parse_amount(s) -> Decimal:
    if s is None or s == "":
        return Decimal("0")
    s = str(s).strip().replace(' ', '').replace('€', '').replace('EUR', '')
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ============================================================
# 1. REGELWERK + KONFIG
# ============================================================

@kita_router.get("/rulesets")
async def list_rulesets():
    """Alle aktiven Regelwerke (Land + Stadt + Träger)."""
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, level, jurisdiction, name, valid_from, valid_to, source_url, notes
            FROM compliance_rulesets
            ORDER BY level, valid_from DESC
        """)).fetchall()
    return {
        "count": len(rows),
        "rulesets": [
            {
                "id": r[0], "level": r[1], "jurisdiction": r[2], "name": r[3],
                "valid_from": r[4].isoformat() if r[4] else None,
                "valid_to": r[5].isoformat() if r[5] else None,
                "source_url": r[6], "notes": r[7],
            }
            for r in rows
        ],
    }


@kita_router.get("/rulesets/{ruleset_id}/details")
async def ruleset_details(ruleset_id: str):
    """Personalschlüssel + Förder-Tagsätze für ein Regelwerk."""
    with engine.connect() as conn:
        rs = conn.execute(sa.text(
            "SELECT id, name, source_url FROM compliance_rulesets WHERE id=:id"
        ), {"id": ruleset_id}).first()
        if not rs:
            raise HTTPException(404, "Regelwerk nicht gefunden")

        ratios = conn.execute(sa.text("""
            SELECT id, group_type, subtype, age_min_months, age_max_months,
                   children_max, children_per_caregiver_max, fte_required,
                   qual_paedagoge_min_pct, qual_assistent_max_pct, qual_helfer_max_pct,
                   preparation_hours_per_week_min, notes
            FROM personnel_ratios WHERE ruleset_id=:id
            ORDER BY group_type, subtype
        """), {"id": ruleset_id}).fetchall()

        rates = conn.execute(sa.text("""
            SELECT id, group_type, rate_per_day, rate_per_month, valid_from, notes
            FROM funding_rates WHERE ruleset_id=:id
        """), {"id": ruleset_id}).fetchall()

    return {
        "ruleset": {"id": rs[0], "name": rs[1], "source_url": rs[2]},
        "personnel_ratios": [
            {
                "id": r[0], "group_type": r[1], "subtype": r[2],
                "age_range_months": [r[3], r[4]],
                "children_max": r[5], "children_per_caregiver_max": r[6],
                "fte_required": float(r[7]),
                "qualification": {
                    "paedagoge_min_pct": r[8],
                    "assistent_max_pct": r[9],
                    "helfer_max_pct": r[10],
                },
                "preparation_hours_per_week_min": r[11],
                "notes": r[12],
            }
            for r in ratios
        ],
        "funding_rates": [
            {
                "id": r[0], "group_type": r[1],
                "rate_per_day": float(r[2]),
                "rate_per_month": float(r[3]) if r[3] else None,
                "valid_from": r[4].isoformat() if r[4] else None,
                "notes": r[5],
            }
            for r in rates
        ],
    }


@kita_router.patch("/funding-rates/{rate_id}")
async def update_funding_rate(rate_id: str, payload: dict = Body(...)):
    """Förder-Tagsatz manuell aktualisieren (aus echtem Förderbescheid)."""
    fields = {}
    for k in ("rate_per_day", "rate_per_month", "notes"):
        if k in payload:
            fields[k] = payload[k]
    if not fields:
        raise HTTPException(400, "keine Felder im Payload")
    set_parts = [f"{k} = :{k}" for k in fields]
    sql = f"UPDATE funding_rates SET {', '.join(set_parts)} WHERE id = :id"
    fields["id"] = rate_id
    with engine.begin() as conn:
        result = conn.execute(sa.text(sql), fields)
        if result.rowcount == 0:
            raise HTTPException(404, "Tagsatz nicht gefunden")
    return {"id": rate_id, "updated": list(fields.keys())}


# ============================================================
# 2. KITA-GRUPPEN
# ============================================================

@kita_router.get("/groups")
async def list_groups():
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, name, group_type, location, capacity, opened_at, closed_at, notes
            FROM kita_groups
            ORDER BY name
        """)).fetchall()
    return {
        "count": len(rows),
        "groups": [
            {
                "id": r[0], "name": r[1], "group_type": r[2],
                "location": r[3], "capacity": r[4],
                "opened_at": r[5].isoformat() if r[5] else None,
                "closed_at": r[6].isoformat() if r[6] else None,
                "notes": r[7],
            }
            for r in rows
        ],
    }


@kita_router.post("/groups")
async def create_group(payload: dict = Body(...)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name ist Pflicht")
    gid = _new_id("grp")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_groups (id, name, group_type, location, capacity, opened_at, notes)
            VALUES (:id, :n, :gt, :loc, :cap, :op, :notes)
        """), {
            "id": gid, "n": name,
            "gt": payload.get("group_type", "kiga"),
            "loc": payload.get("location"),
            "cap": int(payload.get("capacity", 25)),
            "op": payload.get("opened_at") or date.today().isoformat(),
            "notes": payload.get("notes"),
        })
    return {"id": gid, "name": name}


@kita_router.delete("/groups/{group_id}")
async def delete_group(group_id: str):
    with engine.begin() as conn:
        result = conn.execute(sa.text("DELETE FROM kita_groups WHERE id=:id"), {"id": group_id})
        if result.rowcount == 0:
            raise HTTPException(404, "Gruppe nicht gefunden")
    return {"id": group_id, "deleted": True}


# ============================================================
# 3. PERSONAL
# ============================================================

@kita_router.get("/staff")
async def list_staff():
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT s.id, s.full_name, s.qualification, s.bafep_certified, s.quereinstieg_years,
                   s.hired_at, s.left_at, s.notes,
                   (SELECT contract_pct FROM kita_staff_contracts c
                    WHERE c.staff_id = s.id AND (c.valid_to IS NULL OR c.valid_to >= CURRENT_DATE)
                    ORDER BY c.valid_from DESC LIMIT 1) AS current_pct
            FROM kita_staff_members s
            ORDER BY s.full_name
        """)).fetchall()
    return {
        "count": len(rows),
        "staff": [
            {
                "id": r[0], "full_name": r[1], "qualification": r[2],
                "bafep_certified": r[3], "quereinstieg_years": r[4] or 0,
                "hired_at": r[5].isoformat() if r[5] else None,
                "left_at": r[6].isoformat() if r[6] else None,
                "notes": r[7],
                "current_contract_pct": float(r[8]) if r[8] else None,
            }
            for r in rows
        ],
    }


@kita_router.post("/staff")
async def create_staff(payload: dict = Body(...)):
    name = (payload.get("full_name") or "").strip()
    if not name:
        raise HTTPException(400, "full_name ist Pflicht")
    sid = _new_id("staff")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_staff_members
              (id, full_name, qualification, bafep_certified, quereinstieg_years, hired_at, notes)
            VALUES (:id, :n, :q, :bc, :qe, :h, :notes)
        """), {
            "id": sid, "n": name,
            "q": payload.get("qualification", "paedagoge"),
            "bc": payload.get("bafep_certified", False),
            "qe": payload.get("quereinstieg_years", 0),
            "h": payload.get("hired_at") or date.today().isoformat(),
            "notes": payload.get("notes"),
        })
        # Optional gleich Vertrag anlegen
        if payload.get("contract_pct"):
            conn.execute(sa.text("""
                INSERT INTO kita_staff_contracts
                  (id, staff_id, valid_from, contract_pct, weekly_hours, paid_hours, direct_care_hours)
                VALUES (:id, :s, :vf, :pct, :wh, :ph, :dch)
            """), {
                "id": _new_id("ctr"), "s": sid,
                "vf": payload.get("hired_at") or date.today().isoformat(),
                "pct": float(payload["contract_pct"]),
                "wh": float(payload.get("weekly_hours", 38.5)),
                "ph": float(payload.get("paid_hours", 38.5)),
                "dch": float(payload.get("direct_care_hours", 33.0)),
            })
    return {"id": sid, "full_name": name}


@kita_router.delete("/staff/{staff_id}")
async def delete_staff(staff_id: str):
    with engine.begin() as conn:
        result = conn.execute(sa.text("DELETE FROM kita_staff_members WHERE id=:id"), {"id": staff_id})
        if result.rowcount == 0:
            raise HTTPException(404, "Mitarbeiter nicht gefunden")
    return {"id": staff_id, "deleted": True}


# ============================================================
# 4. AUDIT-ENGINE
# ============================================================

def _get_active_ruleset(conn, target_date: date, jurisdiction: str = "AT-8") -> dict | None:
    """Findet das spezifischste gültige Regelwerk."""
    rows = conn.execute(sa.text("""
        SELECT id, level, jurisdiction, name
        FROM compliance_rulesets
        WHERE valid_from <= :d AND (valid_to IS NULL OR valid_to >= :d)
        ORDER BY CASE level
          WHEN 'traeger' THEN 4 WHEN 'gemeinde' THEN 3
          WHEN 'stadt' THEN 2 WHEN 'land' THEN 1 ELSE 0 END DESC
    """), {"d": target_date}).fetchall()
    for r in rows:
        if r[2].startswith(jurisdiction):
            return {"id": r[0], "level": r[1], "name": r[3]}
    return None


def _get_personnel_ratio(conn, ruleset_id: str, group_type: str) -> dict | None:
    row = conn.execute(sa.text("""
        SELECT children_max, fte_required, qual_paedagoge_min_pct,
               qual_assistent_max_pct, qual_helfer_max_pct,
               hours_threshold_high, fte_per_extra_hour
        FROM personnel_ratios
        WHERE ruleset_id=:rs AND group_type=:gt
        ORDER BY (CASE subtype WHEN 'normal' THEN 1 WHEN 'regelgruppe' THEN 1 ELSE 2 END)
        LIMIT 1
    """), {"rs": ruleset_id, "gt": group_type}).first()
    if not row:
        return None
    return {
        "children_max": row[0], "fte_required": Decimal(str(row[1])),
        "paed_min_pct": row[2], "asst_max_pct": row[3], "helf_max_pct": row[4],
        "hours_threshold_high": row[5], "fte_per_extra_hour": Decimal(str(row[6])),
    }


def _get_funding_rate(conn, group_type: str, target_date: date) -> Decimal:
    """Tagsatz für Risiko-Berechnung."""
    row = conn.execute(sa.text("""
        SELECT rate_per_day FROM funding_rates fr
        JOIN compliance_rulesets rs ON rs.id = fr.ruleset_id
        WHERE fr.group_type=:gt
          AND rs.valid_from <= :d
          AND (rs.valid_to IS NULL OR rs.valid_to >= :d)
        ORDER BY rs.valid_from DESC LIMIT 1
    """), {"gt": group_type, "d": target_date}).first()
    return Decimal(str(row[0])) if row else Decimal("12.00")


def _compute_required_fte(conn, group: dict, target_date: date, ratio: dict) -> dict:
    """Soll-FTE für einen Tag."""
    children = conn.execute(sa.text("""
        SELECT COUNT(*) AS n, COALESCE(AVG(booked_hours_per_week), 0) AS avg_h
        FROM kita_child_enrollments
        WHERE group_id=:g
          AND enrolled_from <= :d
          AND (enrolled_to IS NULL OR enrolled_to >= :d)
    """), {"g": group["id"], "d": target_date}).first()
    n = children[0] or 0
    avg_h = Decimal(str(children[1] or 0))

    if n == 0:
        return {"children_present": 0, "fte_required": Decimal("0")}

    fte = ratio["fte_required"]
    if avg_h > Decimal(str(ratio["hours_threshold_high"])):
        extra = avg_h - Decimal(str(ratio["hours_threshold_high"]))
        fte = fte + (extra * ratio["fte_per_extra_hour"])

    if n < ratio["children_max"]:
        scale = Decimal(n) / Decimal(ratio["children_max"])
        fte = fte * scale
        fte = max(fte, Decimal("1.0"))

    return {"children_present": n, "avg_hours": avg_h, "fte_required": fte.quantize(Decimal("0.01"))}


def _compute_actual_fte(conn, group: dict, target_date: date) -> dict:
    """Ist-FTE für einen Tag."""
    rows = conn.execute(sa.text("""
        SELECT a.staff_id, a.hours_actual, a.hours_planned, a.is_cooking, a.is_preparation,
               s.qualification,
               (SELECT weekly_hours FROM kita_staff_contracts c
                WHERE c.staff_id = s.id AND c.valid_from <= :d
                AND (c.valid_to IS NULL OR c.valid_to >= :d)
                ORDER BY c.valid_from DESC LIMIT 1) AS weekly_h
        FROM kita_staff_assignments a
        JOIN kita_staff_members s ON s.id = a.staff_id
        WHERE a.group_id=:g AND a.work_date=:d
    """), {"g": group["id"], "d": target_date}).fetchall()

    fte_by_qual: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for r in rows:
        if r[3] or r[4]:
            continue   # Koch-/Vorbereitungszeit nicht förderbar
        if r[5] == "praktikant":
            continue
        # Krankheit prüfen
        absent = conn.execute(sa.text("""
            SELECT 1 FROM kita_staff_absences
            WHERE staff_id=:s AND absent_from <= :d
              AND (absent_to IS NULL OR absent_to >= :d) LIMIT 1
        """), {"s": r[0], "d": target_date}).first()
        if absent:
            continue
        hours = Decimal(str(r[1] or r[2] or 0))
        weekly = Decimal(str(r[6] or 38.5))
        if weekly > 0:
            daily_full = weekly / Decimal("5")
            fte = hours / daily_full if daily_full > 0 else Decimal("0")
            fte_by_qual[r[5]] += fte

    total = sum(fte_by_qual.values()) if fte_by_qual else Decimal("0")
    return {"fte_actual": total.quantize(Decimal("0.01")), "by_qualification": {k: float(v) for k, v in fte_by_qual.items()}}


def _compute_monthly_snapshot(conn, group: dict, snapshot_month: date, jurisdiction: str = "AT-8") -> dict:
    """Aggregiert über alle Werktage des Monats."""
    if snapshot_month.month == 12:
        next_m = date(snapshot_month.year + 1, 1, 1)
    else:
        next_m = date(snapshot_month.year, snapshot_month.month + 1, 1)
    cur = snapshot_month.replace(day=1)
    days, daily_required, daily_actual, daily_children = [], [], [], []
    daily_gaps = []
    rule_versions = {}
    total_risk = Decimal("0")

    while cur < next_m:
        if cur.weekday() < 5:
            rs = _get_active_ruleset(conn, cur, jurisdiction)
            if rs:
                ratio = _get_personnel_ratio(conn, rs["id"], group["group_type"])
                if ratio:
                    rule_versions[cur.isoformat()] = rs["id"]
                    soll = _compute_required_fte(conn, group, cur, ratio)
                    ist = _compute_actual_fte(conn, group, cur)
                    daily_required.append(soll["fte_required"])
                    daily_actual.append(ist["fte_actual"])
                    daily_children.append(soll["children_present"])

                    gap = ist["fte_actual"] - soll["fte_required"]
                    if gap < Decimal("-0.05") and soll["children_present"] > 0:
                        rate = _get_funding_rate(conn, group["group_type"], cur)
                        affected = (abs(gap) / soll["fte_required"]) * Decimal(soll["children_present"]) if soll["fte_required"] > 0 else Decimal("0")
                        risk = (affected * rate).quantize(Decimal("0.01"))
                        sev = "critical" if abs(gap) / soll["fte_required"] >= Decimal("0.5") else \
                              "major" if abs(gap) / soll["fte_required"] >= Decimal("0.2") else "minor"
                        daily_gaps.append({
                            "gap_date": cur.isoformat(),
                            "severity": sev,
                            "fte_missing": float(abs(gap)),
                            "children_affected": soll["children_present"],
                            "eur_at_risk": float(risk),
                            "ruleset": rs["id"],
                        })
                        total_risk += risk
        cur += timedelta(days=1)

    children_avg = mean([c for c in daily_children if c > 0]) if any(c > 0 for c in daily_children) else 0
    fte_req_avg = mean([float(f) for f in daily_required]) if daily_required else 0
    fte_act_avg = mean([float(f) for f in daily_actual]) if daily_actual else 0
    risk_level = "red" if total_risk >= 2000 else "yellow" if total_risk >= 500 or len(daily_gaps) >= 3 else "green"

    return {
        "month": snapshot_month.replace(day=1).isoformat(),
        "group_id": group["id"],
        "group_name": group["name"],
        "children_avg": round(children_avg, 2),
        "fte_required": round(fte_req_avg, 2),
        "fte_actual": round(fte_act_avg, 2),
        "fte_gap": round(fte_act_avg - fte_req_avg, 2),
        "days_undercov": len(daily_gaps),
        "funding_at_risk_eur": float(total_risk),
        "risk_level": risk_level,
        "rule_versions_used": rule_versions,
        "gaps": daily_gaps,
    }


@kita_router.get("/audit/monthly")
async def audit_monthly(
    group_id: Optional[str] = None,
    year: int = Query(default=None),
    month: int = Query(default=None),
):
    """Audit für einen Monat — eine oder alle Gruppen."""
    today = date.today()
    if not year:
        year = today.year
    if not month:
        month = today.month
    snapshot_month = date(year, month, 1)

    with engine.connect() as conn:
        groups_q = "SELECT id, name, group_type FROM kita_groups WHERE closed_at IS NULL"
        params = {}
        if group_id:
            groups_q += " AND id = :gid"
            params["gid"] = group_id
        groups = conn.execute(sa.text(groups_q), params).fetchall()

        results = []
        for g in groups:
            group_dict = {"id": g[0], "name": g[1], "group_type": g[2]}
            snap = _compute_monthly_snapshot(conn, group_dict, snapshot_month)
            results.append(snap)

    total_risk = sum(s["funding_at_risk_eur"] for s in results)
    return {
        "month": snapshot_month.isoformat(),
        "total_groups": len(results),
        "total_funding_at_risk_eur": round(total_risk, 2),
        "snapshots": results,
    }


@kita_router.get("/audit/yearly")
async def audit_yearly(
    group_id: Optional[str] = None,
    year: int = Query(default=None),
):
    """Audit-Report über 12 Monate."""
    if not year:
        year = date.today().year

    with engine.connect() as conn:
        groups_q = "SELECT id, name, group_type FROM kita_groups WHERE closed_at IS NULL"
        params = {}
        if group_id:
            groups_q += " AND id = :gid"
            params["gid"] = group_id
        groups = conn.execute(sa.text(groups_q), params).fetchall()

        per_group: list = []
        for g in groups:
            group_dict = {"id": g[0], "name": g[1], "group_type": g[2]}
            monthly = []
            for m in range(1, 13):
                snap = _compute_monthly_snapshot(conn, group_dict, date(year, m, 1))
                monthly.append(snap)
            per_group.append({
                "group": group_dict,
                "monthly": monthly,
                "total_funding_at_risk_eur": sum(s["funding_at_risk_eur"] for s in monthly),
                "months_with_gap": sum(1 for s in monthly if s["days_undercov"] > 0),
            })

    return {
        "year": year,
        "total_groups": len(per_group),
        "total_funding_at_risk_eur": round(sum(g["total_funding_at_risk_eur"] for g in per_group), 2),
        "per_group": per_group,
    }


@kita_router.get("/audit/historical")
async def audit_historical(
    group_id: str,
    months_back: int = 60,
):
    """60-Monate-Rückwärts-Audit für eine Gruppe."""
    today = date.today().replace(day=1)
    start_y = today.year - (months_back // 12)
    start_m = today.month - (months_back % 12)
    while start_m <= 0:
        start_y -= 1
        start_m += 12

    with engine.connect() as conn:
        g = conn.execute(sa.text(
            "SELECT id, name, group_type FROM kita_groups WHERE id=:id"
        ), {"id": group_id}).first()
        if not g:
            raise HTTPException(404, "Gruppe nicht gefunden")
        group_dict = {"id": g[0], "name": g[1], "group_type": g[2]}

        snapshots = []
        cur = date(start_y, start_m, 1)
        while cur <= today:
            snap = _compute_monthly_snapshot(conn, group_dict, cur)
            snapshots.append(snap)
            cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)

    total_risk = sum(s["funding_at_risk_eur"] for s in snapshots)
    months_with_gap = sum(1 for s in snapshots if s["days_undercov"] > 0)

    return {
        "group": group_dict,
        "period_from": date(start_y, start_m, 1).isoformat(),
        "period_to": today.isoformat(),
        "months_analysed": len(snapshots),
        "months_with_gap": months_with_gap,
        "months_clean": len(snapshots) - months_with_gap,
        "total_funding_at_risk_eur": round(total_risk, 2),
        "potential_recoverable_eur": round(total_risk * 0.65, 2),
        "non_recoverable_eur": round(total_risk * 0.35, 2),
        "snapshots": snapshots,
    }


# ============================================================
# 5. STATE-Endpoint (Dashboard)
# ============================================================

@kita_router.get("/state")
async def kita_state():
    """Zusammenfassung für Dashboard-Übersicht."""
    today = date.today()
    with engine.connect() as conn:
        n_groups = conn.execute(sa.text("SELECT COUNT(*) FROM kita_groups WHERE closed_at IS NULL")).scalar() or 0
        n_staff = conn.execute(sa.text("SELECT COUNT(*) FROM kita_staff_members WHERE left_at IS NULL")).scalar() or 0
        n_children = conn.execute(sa.text("""
            SELECT COUNT(*) FROM kita_child_enrollments
            WHERE enrolled_from <= :d AND (enrolled_to IS NULL OR enrolled_to >= :d)
        """), {"d": today}).scalar() or 0

        # Aktueller Monat: Risiko & Gaps
        current_month = today.replace(day=1)
        groups = conn.execute(sa.text(
            "SELECT id, name, group_type FROM kita_groups WHERE closed_at IS NULL"
        )).fetchall()
        total_risk = Decimal("0")
        total_gaps = 0
        risk_by_group = []
        for g in groups:
            snap = _compute_monthly_snapshot(conn, {"id": g[0], "name": g[1], "group_type": g[2]}, current_month)
            total_risk += Decimal(str(snap["funding_at_risk_eur"]))
            total_gaps += snap["days_undercov"]
            risk_by_group.append({
                "group_id": g[0], "group_name": g[1],
                "fte_actual": snap["fte_actual"],
                "fte_required": snap["fte_required"],
                "fte_gap": snap["fte_gap"],
                "risk_eur": snap["funding_at_risk_eur"],
                "risk_level": snap["risk_level"],
            })

    return {
        "summary": {
            "groups_active": n_groups,
            "staff_active": n_staff,
            "children_enrolled": n_children,
            "current_month": current_month.isoformat(),
            "current_month_risk_eur": float(total_risk),
            "current_month_gap_days": total_gaps,
        },
        "risk_by_group": risk_by_group,
    }


# ============================================================
# 6. EXCEL-IMPORT
# ============================================================

@kita_router.post("/import/excel")
async def import_excel(file: UploadFile = File(...)):
    """
    Flexibler Excel-Importer mit pandas.
    Erkennt Sheets nach Name (heuristisch):
      - 'Mitarbeiter' / 'Personal' / 'Staff'
      - 'Verträge' / 'Contracts'
      - 'Kinder' / 'Belegung' / 'Children'
      - 'Dienstplan' / 'Roster'
      - 'Krankheit' / 'Absences'
    """
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(500, "pandas nicht installiert: pip install pandas openpyxl")

    content = await file.read()
    try:
        xls = pd.ExcelFile(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Excel-Datei konnte nicht gelesen werden: {e}")

    results = {"sheets_found": xls.sheet_names, "imported": {}}

    # Heuristik: Welcher Sheet enthält was?
    sheet_purposes = {}
    for sn in xls.sheet_names:
        ln = sn.lower()
        if any(k in ln for k in ("mitarb", "person", "staff")):
            sheet_purposes[sn] = "staff"
        elif any(k in ln for k in ("vertrag", "contract", "stelle")):
            sheet_purposes[sn] = "contracts"
        elif any(k in ln for k in ("kind", "belegung", "child", "enrol")):
            sheet_purposes[sn] = "children"
        elif any(k in ln for k in ("dienstplan", "roster", "schicht")):
            sheet_purposes[sn] = "assignments"
        elif any(k in ln for k in ("krank", "abwesen", "absence")):
            sheet_purposes[sn] = "absences"

    with engine.begin() as conn:
        # 1. Mitarbeiter
        for sn, purpose in sheet_purposes.items():
            if purpose != "staff":
                continue
            df = xls.parse(sn).fillna("")
            count = 0
            for _, row in df.iterrows():
                name = str(row.get("name", row.get("Name", row.get("full_name", ""))) or "").strip()
                if not name:
                    continue
                qual = str(row.get("qualifikation", row.get("qualification", "paedagoge"))).lower().strip()
                if "päd" in qual or "paed" in qual:
                    qual = "paedagoge"
                elif "assi" in qual:
                    qual = "assistent"
                elif "helf" in qual:
                    qual = "helfer"
                elif "leit" in qual:
                    qual = "leitung"
                else:
                    qual = "paedagoge"
                hired = row.get("eintritt", row.get("hired_at"))
                left = row.get("austritt", row.get("left_at"))
                sid = _new_id("staff")
                conn.execute(sa.text("""
                    INSERT INTO kita_staff_members (id, full_name, qualification, hired_at, left_at)
                    VALUES (:id, :n, :q, :h, :l) ON CONFLICT DO NOTHING
                """), {
                    "id": sid, "n": name, "q": qual,
                    "h": pd.to_datetime(hired).date() if hired else date.today(),
                    "l": pd.to_datetime(left).date() if left else None,
                })
                count += 1
            results["imported"]["staff"] = count

        # 2. Kinder-Belegung
        for sn, purpose in sheet_purposes.items():
            if purpose != "children":
                continue
            df = xls.parse(sn).fillna("")
            count = 0
            for _, row in df.iterrows():
                anon = str(row.get("kind_id", row.get("child_id", row.get("anon_id", "")))).strip()
                if not anon:
                    anon = f"k_{uuid.uuid4().hex[:8]}"
                group_name = str(row.get("gruppe", row.get("group_name", ""))).strip()
                gid = None
                if group_name:
                    g = conn.execute(sa.text(
                        "SELECT id FROM kita_groups WHERE name=:n LIMIT 1"
                    ), {"n": group_name}).first()
                    if g:
                        gid = g[0]
                if not gid:
                    continue
                from_d = row.get("von", row.get("enrolled_from", date.today()))
                to_d = row.get("bis", row.get("enrolled_to"))
                hours = float(row.get("stunden", row.get("booked_hours_per_week", 25)) or 25)
                age = int(row.get("alter_monate", row.get("age_months", 36)) or 36)
                conn.execute(sa.text("""
                    INSERT INTO kita_child_enrollments
                      (id, group_id, child_anon_id, age_months, enrolled_from, enrolled_to, booked_hours_per_week)
                    VALUES (:id, :g, :a, :am, :f, :t, :h) ON CONFLICT DO NOTHING
                """), {
                    "id": _new_id("enr"), "g": gid, "a": anon, "am": age,
                    "f": pd.to_datetime(from_d).date() if from_d else date.today(),
                    "t": pd.to_datetime(to_d).date() if to_d else None,
                    "h": hours,
                })
                count += 1
            results["imported"]["children"] = count

        # 3. Dienstplan (Roster)
        for sn, purpose in sheet_purposes.items():
            if purpose != "assignments":
                continue
            df = xls.parse(sn).fillna("")
            count = 0
            for _, row in df.iterrows():
                staff_name = str(row.get("name", row.get("mitarbeiter", ""))).strip()
                group_name = str(row.get("gruppe", row.get("group", ""))).strip()
                if not staff_name or not group_name:
                    continue
                s = conn.execute(sa.text(
                    "SELECT id FROM kita_staff_members WHERE full_name=:n LIMIT 1"
                ), {"n": staff_name}).first()
                g = conn.execute(sa.text(
                    "SELECT id FROM kita_groups WHERE name=:n LIMIT 1"
                ), {"n": group_name}).first()
                if not s or not g:
                    continue
                wd = row.get("datum", row.get("date"))
                if not wd:
                    continue
                hours_p = float(row.get("geplante_stunden", row.get("hours_planned", 8)) or 8)
                hours_a = float(row.get("ist_stunden", row.get("hours_actual", hours_p)) or hours_p)
                conn.execute(sa.text("""
                    INSERT INTO kita_staff_assignments
                      (id, staff_id, group_id, work_date, hours_planned, hours_actual)
                    VALUES (:id, :s, :g, :d, :hp, :ha) ON CONFLICT DO NOTHING
                """), {
                    "id": _new_id("ass"), "s": s[0], "g": g[0],
                    "d": pd.to_datetime(wd).date(), "hp": hours_p, "ha": hours_a,
                })
                count += 1
            results["imported"]["assignments"] = count

    return results
"""
SHIKSHA · KITA · Document-Upload-Endpoints (Foto/PDF/Scan)
Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.

Stand: 29.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import hashlib as _kd_hash
import re as _kd_re
import subprocess as _kd_subprocess
import tempfile as _kd_temp
import uuid as _kd_uuid
from datetime import date as _kd_date, datetime as _kd_dt
from pathlib import Path as _kd_Path

from fastapi import UploadFile as _kd_UploadFile, File as _kd_File, Body as _kd_Body, HTTPException as _kd_HTTP, Query as _kd_Query
from fastapi.responses import FileResponse as _kd_FileResponse

KITA_DOC_DIR = _kd_Path("/opt/shiksha/uploads/kita/documents")
KITA_DOC_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# OCR-PIPELINE
# ============================================================

def _kd_ocr_image(file_path: _kd_Path) -> str:
    """OCR mit tesseract (deutsch)."""
    try:
        result = _kd_subprocess.run(
            ["tesseract", str(file_path), "-", "-l", "deu", "--psm", "6"],
            capture_output=True, text=True, timeout=60,
        )
        return result.stdout
    except Exception as e:
        print(f"[kita-ocr] Fehler bei {file_path}: {e}")
        return ""


def _kd_ocr_pdf(file_path: _kd_Path) -> str:
    """PDF → Bilder → OCR. Probiert erst pdfplumber (Text-PDF), dann pdf2image+tesseract (Scan)."""
    text = ""
    # 1. Versuch: pdfplumber für native Text-PDFs
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        if len(text.strip()) > 50:
            return text
    except Exception:
        pass

    # 2. Versuch: pdftoppm + tesseract (für Scans)
    try:
        with _kd_temp.TemporaryDirectory() as tmp:
            tmpdir = _kd_Path(tmp)
            _kd_subprocess.run(
                ["pdftoppm", "-r", "200", "-png", str(file_path), str(tmpdir / "page")],
                capture_output=True, timeout=120,
            )
            chunks = []
            for img in sorted(tmpdir.glob("page-*.png")):
                chunks.append(_kd_ocr_image(img))
            text = "\n".join(chunks)
    except Exception as e:
        print(f"[kita-ocr-pdf] Fehler bei {file_path}: {e}")

    return text


def _kd_extract_text(file_path: _kd_Path, mime: str) -> str:
    """Routet zur richtigen OCR-Methode."""
    if "pdf" in (mime or "").lower() or file_path.suffix.lower() == ".pdf":
        return _kd_ocr_pdf(file_path)
    return _kd_ocr_image(file_path)


# ============================================================
# DOCUMENT-TYPE DETECTION + FIELD-EXTRACTION
# ============================================================

def _kd_detect_type(text: str) -> tuple[str, str]:
    """Erkennt Dokumenttyp + Subtyp anhand Schlüsselwörtern."""
    t = text.lower()
    if "betreuungsvertrag" in t or "anmeldung" in t or "wochentag" in t and ("modul" in t or "halbtag" in t):
        sub = "krummelus" if "krummelus" in t else "generic"
        return "anmeldevertrag", sub
    if "krankenstand" in t or "arbeitsunfähig" in t or "ärztliche bestätigung" in t:
        return "krankenstand", "generic"
    if "dienstplan" in t or "schichtplan" in t:
        return "dienstplan", "generic"
    if "förderbescheid" in t or "subvention" in t and "tagsatz" in t:
        return "foerderbescheid", "stadt_dornbirn" if "dornbirn" in t else "generic"
    if "dienstvertrag" in t or "arbeitsvertrag" in t and ("kindergart" in t or "krippe" in t):
        return "mitarbeitervertrag", "generic"
    return "unknown", "generic"


def _kd_extract_anmeldevertrag(text: str) -> dict:
    """Felder aus Anmeldevertrag (Krummelus + ähnliche Vorlagen)."""
    fields = {}

    # Kind: Name
    m = _kd_re.search(r"NAME\s*DES\s*KINDES[:\s]*([A-ZÄÖÜa-zäöüß\-\s]{3,50})", text, _kd_re.IGNORECASE)
    if m:
        fields["child_name"] = (m.group(1).strip().splitlines()[0]).strip()

    # Geburtsdatum
    m = _kd_re.search(r"Geburtsdatum[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})", text, _kd_re.IGNORECASE)
    if m:
        fields["birth_date"] = _kd_normalize_date(m.group(1))

    # Adresse Kind
    m = _kd_re.search(r"Adresse[:\s]*([A-ZÄÖÜa-zäöüß0-9\s,\-\.]{5,80})", text, _kd_re.IGNORECASE)
    if m:
        fields["child_address"] = m.group(1).strip().splitlines()[0]

    # Sozialversicherungsnummer
    m = _kd_re.search(r"Sozialversicherungsnummer[:\s]*([\d\s]{6,14})", text, _kd_re.IGNORECASE)
    if m:
        fields["sv_number"] = _kd_re.sub(r"\s+", " ", m.group(1).strip())

    # Vertragslaufzeit
    m = _kd_re.search(r"vom\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})\s*bis\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})", text, _kd_re.IGNORECASE)
    if m:
        fields["enrolled_from"] = _kd_normalize_date(m.group(1))
        fields["enrolled_to"] = _kd_normalize_date(m.group(2))

    # Eltern: Mutter / Vater
    m = _kd_re.search(r"MUTTER[:\s]*([A-ZÄÖÜa-zäöüß\-\s]{3,60})", text, _kd_re.IGNORECASE)
    if m:
        fields["mother_name"] = m.group(1).strip().splitlines()[0].strip()
    m = _kd_re.search(r"VATER[:\s]*([A-ZÄÖÜa-zäöüß\-\s]{3,60})", text, _kd_re.IGNORECASE)
    if m:
        fields["father_name"] = m.group(1).strip().splitlines()[0].strip()

    # Telefon-Nummern (für Eltern-Kontakt)
    phones = _kd_re.findall(r"(?:Telefon[a-z]*[:\s]*|\b)(\+?\d[\d\s]{6,18})", text)
    if len(phones) >= 1:
        fields["phone_1"] = phones[0].strip()
    if len(phones) >= 2:
        fields["phone_2"] = phones[1].strip()

    # E-Mail-Adressen
    emails = _kd_re.findall(r"[\w\.\-]+@[\w\.\-]+\.\w+", text)
    if emails:
        fields["emails"] = "; ".join(emails[:3])

    # MODULE-MATRIX (das wichtigste!)
    # Heuristik: Suche nach Wochentag-Zeilen und versuche, gebuchte Spalten zu erkennen
    # Da OCR von Häkchen schwierig ist, geben wir die rohe Zeile zurück und der User markiert nach
    module_lines = {}
    for tag in ["MONTAG", "DIENSTAG", "MITTWOCH", "DONNERSTAG", "FREITAG"]:
        m = _kd_re.search(rf"{tag}\s+([^\n]{{0,80}})", text, _kd_re.IGNORECASE)
        if m:
            module_lines[tag.lower()] = m.group(1).strip()
    if module_lines:
        # Heuristik: ein "X", "✓", "x", oder gefüllter Kreis nahe einer Zeit-Spalte = gebucht
        # Spalten-Standard: 07:15-11:30 | 11:30-12:30 | 12:30-13:30 | 13:30-17:30
        slots = ["07:15-11:30", "11:30-12:30", "12:30-13:30", "13:30-17:30"]
        booked = {}
        for tag, line in module_lines.items():
            line_clean = line.lower()
            booked_slots = []
            # Versuch 1: Wenn ein Marker (X/✓/●) im OCR-Text auftaucht
            markers = _kd_re.findall(r"([Xx✓●■◉])", line)
            if markers:
                booked_slots = ["unknown_slot"]
            booked[tag] = {"raw_line": line, "booked_slots": booked_slots}
        fields["modules_raw"] = booked

    return fields


def _kd_extract_krankenstand(text: str) -> dict:
    fields = {}
    m = _kd_re.search(r"(?:Name|Mitarbeiter)[:\s]+([A-ZÄÖÜa-zäöüß\-\s]{3,50})", text, _kd_re.IGNORECASE)
    if m:
        fields["staff_name"] = m.group(1).strip().splitlines()[0]
    m = _kd_re.search(r"(?:von|ab|seit)[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})", text, _kd_re.IGNORECASE)
    if m:
        fields["absent_from"] = _kd_normalize_date(m.group(1))
    m = _kd_re.search(r"(?:bis|voraussichtlich)[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})", text, _kd_re.IGNORECASE)
    if m:
        fields["absent_to"] = _kd_normalize_date(m.group(1))
    fields["reason"] = "krank"
    return fields


def _kd_normalize_date(s: str) -> str:
    """'08.01.2024' / '8.1.24' → '2024-01-08'."""
    s = s.strip().replace("/", ".").replace("-", ".")
    parts = s.split(".")
    if len(parts) != 3:
        return s
    d, m, y = parts
    if len(y) == 2:
        y = ("20" + y) if int(y) < 50 else ("19" + y)
    try:
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return s


def _kd_extract_fields(text: str, doc_type: str) -> dict:
    """Routet zur richtigen Extraction."""
    if doc_type == "anmeldevertrag":
        return _kd_extract_anmeldevertrag(text)
    if doc_type == "krankenstand":
        return _kd_extract_krankenstand(text)
    return {}


# ============================================================
# ENDPOINTS
# ============================================================

@kita_router.post("/documents/upload")
async def kita_upload_document(
    files: list[_kd_UploadFile] = _kd_File(...),
    force: bool = False,
):
    """
    Multi-File Upload für KITA-Dokumente (Foto/PDF/Scan).
    - Speichert Original
    - SHA256-Duplikat-Check (Override mit ?force=true)
    - OCR + Auto-Detection des Doc-Typs
    - Field-Extraction in kita_document_fields
    """
    results = []

    for file in files:
        content = await file.read()
        if not content:
            results.append({"filename": file.filename, "ok": False, "error": "leere Datei"})
            continue

        file_hash = _kd_hash.sha256(content).hexdigest()

        # Duplikat?
        if not force:
            with engine.connect() as conn:
                existing = conn.execute(sa.text(
                    "SELECT id, file_name, created_at FROM kita_documents WHERE file_hash = :h LIMIT 1"
                ), {"h": file_hash}).first()
            if existing:
                results.append({
                    "filename": file.filename, "ok": False, "duplicate": True,
                    "existing_id": existing[0], "existing_name": existing[1],
                    "error": f"Existiert bereits als: {existing[1]}",
                })
                continue

        # Speichern
        doc_id = _new_id("kdoc")
        safe_name = "".join(c for c in (file.filename or "doc") if c.isalnum() or c in "._-")[:80]
        disk_path = KITA_DOC_DIR / f"{doc_id}_{safe_name}"
        disk_path.write_bytes(content)
        mime = file.content_type or ""

        # OCR
        text = _kd_extract_text(disk_path, mime)
        doc_type, subtype = _kd_detect_type(text)
        fields = _kd_extract_fields(text, doc_type)

        # In DB
        with engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO kita_documents
                  (id, document_type, detected_subtype, raw_text, file_path, file_name,
                   file_size, file_mime, file_hash, source_type, status)
                VALUES (:id, :dt, :sub, :raw, :p, :n, :sz, :m, :h, :src, 'pending')
            """), {
                "id": doc_id, "dt": doc_type, "sub": subtype, "raw": text,
                "p": str(disk_path), "n": file.filename, "sz": len(content),
                "m": mime, "h": file_hash,
                "src": "pdf" if "pdf" in mime.lower() else "photo",
            })
            for key, val in fields.items():
                if isinstance(val, dict):
                    val = str(val)
                if not val:
                    continue
                conn.execute(sa.text("""
                    INSERT INTO kita_document_fields (id, document_id, field_key, field_value, confidence)
                    VALUES (:id, :did, :k, :v, 0.85)
                """), {
                    "id": _new_id("kfld"), "did": doc_id, "k": key, "v": str(val)[:1000],
                })

        results.append({
            "filename": file.filename, "ok": True,
            "document_id": doc_id, "document_type": doc_type, "subtype": subtype,
            "fields_extracted": len(fields),
            "ocr_chars": len(text),
        })

    return {"results": results, "count": len(results)}


@kita_router.get("/documents")
async def kita_list_documents(
    document_type: str = _kd_Query(default=None),
    status: str = _kd_Query(default=None),
    limit: int = 100,
):
    sql = """
    SELECT d.id, d.document_type, d.detected_subtype, d.status, d.file_name,
           d.file_size, d.created_at, d.applied_at, d.applied_to_table,
           (SELECT COUNT(*) FROM kita_document_fields WHERE document_id = d.id) AS field_count,
           LENGTH(d.raw_text) AS ocr_chars
    FROM kita_documents d
    WHERE 1=1
    """
    params = {"lim": limit}
    if document_type:
        sql += " AND d.document_type = :dt"
        params["dt"] = document_type
    if status:
        sql += " AND d.status = :st"
        params["st"] = status
    sql += " ORDER BY d.created_at DESC LIMIT :lim"

    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).fetchall()
    return {
        "count": len(rows),
        "documents": [
            {
                "id": r[0], "document_type": r[1], "subtype": r[2], "status": r[3],
                "file_name": r[4], "file_size": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
                "applied_at": r[7].isoformat() if r[7] else None,
                "applied_to": r[8],
                "field_count": r[9], "ocr_chars": r[10] or 0,
            }
            for r in rows
        ],
    }


@kita_router.get("/documents/{doc_id}")
async def kita_doc_detail(doc_id: str):
    with engine.connect() as conn:
        d = conn.execute(sa.text("""
            SELECT id, document_type, detected_subtype, raw_text, file_name, status,
                   applied_at, applied_to_table, applied_to_id, created_at
            FROM kita_documents WHERE id=:id
        """), {"id": doc_id}).first()
        if not d:
            raise _kd_HTTP(404, "Dokument nicht gefunden")
        fields = conn.execute(sa.text("""
            SELECT id, field_key, field_value, confidence, is_user_edited
            FROM kita_document_fields WHERE document_id=:id ORDER BY field_key
        """), {"id": doc_id}).fetchall()
    return {
        "document": {
            "id": d[0], "document_type": d[1], "subtype": d[2], "raw_text": d[3],
            "file_name": d[4], "status": d[5],
            "applied_at": d[6].isoformat() if d[6] else None,
            "applied_to": d[7], "applied_id": d[8],
            "created_at": d[9].isoformat() if d[9] else None,
        },
        "fields": [
            {
                "id": f[0], "field_key": f[1], "field_value": f[2],
                "confidence": float(f[3]) if f[3] else None,
                "is_user_edited": f[4],
            }
            for f in fields
        ],
    }


@kita_router.get("/documents/{doc_id}/file")
async def kita_doc_file(doc_id: str):
    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT file_path, file_name, file_mime FROM kita_documents WHERE id=:id"
        ), {"id": doc_id}).first()
    if not row or not row[0]:
        raise _kd_HTTP(404, "Datei nicht gefunden")
    fp = _kd_Path(row[0])
    if not fp.exists():
        raise _kd_HTTP(404, "Datei nicht auf Disk")
    return _kd_FileResponse(path=fp, media_type=row[2] or "application/octet-stream", filename=row[1])


@kita_router.delete("/documents/{doc_id}")
async def kita_doc_delete(doc_id: str):
    with engine.begin() as conn:
        row = conn.execute(sa.text(
            "SELECT file_path FROM kita_documents WHERE id=:id"
        ), {"id": doc_id}).first()
        if not row:
            raise _kd_HTTP(404, "Dokument nicht gefunden")
        conn.execute(sa.text("DELETE FROM kita_documents WHERE id=:id"), {"id": doc_id})
    if row[0]:
        try:
            _kd_Path(row[0]).unlink(missing_ok=True)
        except Exception:
            pass
    return {"id": doc_id, "deleted": True}


@kita_router.patch("/documents/{doc_id}/fields")
async def kita_doc_edit_field(doc_id: str, payload: dict = _kd_Body(...)):
    """Manuelle Korrektur eines Felds."""
    field_key = payload.get("field_key")
    field_value = payload.get("field_value")
    if not field_key:
        raise _kd_HTTP(400, "field_key ist Pflicht")

    with engine.begin() as conn:
        existing = conn.execute(sa.text(
            "SELECT id FROM kita_document_fields WHERE document_id=:d AND field_key=:k LIMIT 1"
        ), {"d": doc_id, "k": field_key}).first()
        if existing:
            conn.execute(sa.text("""
                UPDATE kita_document_fields SET field_value=:v, confidence=1.0, is_user_edited=true
                WHERE id=:id
            """), {"v": str(field_value or ""), "id": existing[0]})
        else:
            conn.execute(sa.text("""
                INSERT INTO kita_document_fields (id, document_id, field_key, field_value, confidence, is_user_edited)
                VALUES (:id, :d, :k, :v, 1.0, true)
            """), {"id": _new_id("kfld"), "d": doc_id, "k": field_key, "v": str(field_value or "")})
    return {"document_id": doc_id, "field_key": field_key, "saved": True}


@kita_router.post("/documents/{doc_id}/apply")
async def kita_doc_apply(doc_id: str, payload: dict = _kd_Body(default_factory=dict)):
    """
    Applies extracted fields into the appropriate target table.
    For 'anmeldevertrag' → kita_child_enrollments.
    """
    target_group_id = payload.get("group_id")
    if not target_group_id:
        raise _kd_HTTP(400, "group_id im Payload nötig (welche Gruppe wird das Kind zugeordnet?)")

    with engine.connect() as conn:
        d = conn.execute(sa.text(
            "SELECT document_type, status FROM kita_documents WHERE id=:id"
        ), {"id": doc_id}).first()
        if not d:
            raise _kd_HTTP(404, "Dokument nicht gefunden")
        if d[0] != "anmeldevertrag":
            raise _kd_HTTP(400, f"Apply nur für anmeldevertrag implementiert, dies ist {d[0]}")

        fields = {
            f[0]: f[1] for f in conn.execute(sa.text(
                "SELECT field_key, field_value FROM kita_document_fields WHERE document_id=:id"
            ), {"id": doc_id}).fetchall()
        }

    enrollment_id = _new_id("enr")
    child_anon = _kd_hash.sha256((fields.get("child_name", "") + fields.get("birth_date", "")).encode()).hexdigest()[:16]

    # Alter berechnen
    age_months = 36
    if fields.get("birth_date") and fields.get("enrolled_from"):
        try:
            bd = _kd_dt.fromisoformat(fields["birth_date"]).date()
            ef = _kd_dt.fromisoformat(fields["enrolled_from"]).date()
            age_months = (ef.year - bd.year) * 12 + (ef.month - bd.month)
        except Exception:
            pass

    # Stunden aus modules_raw schätzen — als Fallback 25h/Wo
    booked_hours = float(payload.get("booked_hours_per_week", 25))

    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_child_enrollments
              (id, group_id, child_anon_id, age_months, enrolled_from, enrolled_to,
               booked_hours_per_week, notes)
            VALUES (:id, :g, :a, :am, :f, :t, :h, :n)
        """), {
            "id": enrollment_id, "g": target_group_id, "a": "k_" + child_anon,
            "am": age_months,
            "f": fields.get("enrolled_from") or _kd_date.today().isoformat(),
            "t": fields.get("enrolled_to"),
            "h": booked_hours,
            "n": f"Importiert aus Anmeldevertrag {fields.get('child_name', '')}",
        })
        conn.execute(sa.text("""
            UPDATE kita_documents SET status='applied', applied_at=NOW(),
              applied_to_table='kita_child_enrollments', applied_to_id=:eid
            WHERE id=:id
        """), {"eid": enrollment_id, "id": doc_id})

    return {
        "document_id": doc_id, "enrollment_id": enrollment_id,
        "applied_to": "kita_child_enrollments", "child_anon_id": "k_" + child_anon,
    }
"""
SHIKSHA · KITA · Eltern-Anmeldung — Public Endpoint
Public-API ohne Auth — Eltern bekommen Link, füllen aus, unterschreiben.

Speichert in kita_documents mit type='anmeldevertrag', subtype='digital_signed'.

Stand: 29.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import base64 as _ka_b64
from datetime import date as _ka_date


"""
SHIKSHA · KITA · Eltern-Anmeldung — Public Endpoint
Public-API ohne Auth — Eltern bekommen Link, füllen aus, unterschreiben.

Speichert in kita_documents mit type='anmeldevertrag', subtype='digital_signed'.

Stand: 29.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import base64 as _ka_b64
from datetime import date as _ka_date


"""
SHIKSHA · KITA · Notifications + Eltern-Accounts + Bestätigungs-Mails
Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.

Stand: 29.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import os as _kn_os
import secrets as _kn_secrets
import smtplib as _kn_smtp
from email.mime.multipart import MIMEMultipart as _kn_MIME
from email.mime.text import MIMEText as _kn_MIMEText


# ============================================================
# E-MAIL-VERSAND
# ============================================================

KITA_BASE_URL = _kn_os.environ.get("KITA_BASE_URL", "https://shiksha.tun.zone")
SMTP_HOST = _kn_os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(_kn_os.environ.get("SMTP_PORT", "587"))
SMTP_USER = _kn_os.environ.get("SMTP_USER", "")
SMTP_PASS = _kn_os.environ.get("SMTP_PASS", "")
MAIL_FROM = _kn_os.environ.get("KITA_MAIL_FROM", "kita@shiksha.tun.zone")
MAIL_FROM_NAME = _kn_os.environ.get("KITA_MAIL_FROM_NAME", "SHIKSHA · KITA")


def _kn_send_mail(to_email: str, subject: str, body_html: str, body_text: str = None) -> tuple[bool, str]:
    """E-Mail-Versand. Returns (success, error_msg)."""
    if not to_email:
        return False, "keine Empfänger-E-Mail"
    if not SMTP_HOST:
        # Demo-Modus: Mail-Body in Logs
        print(f"[kita-mail-demo] Würde senden an {to_email}:")
        print(f"  Subject: {subject}")
        print(f"  Body: {body_html[:200]}...")
        return True, "demo-mode"
    msg = _kn_MIME("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
    msg["To"] = to_email
    if body_text:
        msg.attach(_kn_MIMEText(body_text, "plain", "utf-8"))
    msg.attach(_kn_MIMEText(body_html, "html", "utf-8"))
    try:
        with _kn_smtp.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls()
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True, ""
    except Exception as e:
        print(f"[kita-mail] SMTP-Fehler: {e}")
        return False, str(e)


def _kn_holi_mail_template(content_html: str, footer_html: str = "") -> str:
    """Wrapper-Template mit Holi-Look für alle KITA-Mails."""
    return f"""<!DOCTYPE html>
<html><body style="margin:0; padding:0; background:#fff8f0; font-family:-apple-system,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#fff8f0 0%,#ffe4f0 50%,#e4f8ff 100%); padding:24px 12px;">
<tr><td align="center">
  <table width="100%" style="max-width:540px;" cellpadding="0" cellspacing="0">
    <tr><td style="padding:20px 0;">
      <table cellpadding="0" cellspacing="0">
        <tr>
          <td style="background:linear-gradient(135deg,#ff4d8d 0%,#a855f7 100%); width:44px; height:44px; border-radius:14px; text-align:center; color:#fff; font-weight:700; font-size:22px;">K</td>
          <td style="padding-left:12px;">
            <div style="font-size:18px; font-weight:700; color:#2a2530;">SHIKSHA · KITA</div>
            <div style="font-size:12px; color:#9a8e9e;">Spielgruppen · Kindergarten · Hort</div>
          </td>
        </tr>
      </table>
    </td></tr>
    <tr><td style="background:#ffffff; border-radius:20px; padding:28px 24px; box-shadow:0 4px 16px rgba(255,77,141,0.10);">
      {content_html}
    </td></tr>
    <tr><td style="padding:20px 8px; text-align:center; font-size:11px; color:#9a8e9e;">
      {footer_html or 'Geschützt durch <strong style="color:#ff4d8d;">SHIKSHA · KITA</strong> · Daten in der EU'}
    </td></tr>
  </table>
</td></tr>
</table>
</body></html>"""


# ============================================================
# ELTERN-ACCOUNTS + AUTO-CREATE BEI ANMELDUNG
# ============================================================

def _kn_create_or_update_parent(conn, full_name: str, email: str, phone: str, role: str,
                                 enrollment_id: str, child_name: str, doc_id: str) -> str:
    """Legt Eltern-Account an oder erweitert bestehenden um neues Kind."""
    if not full_name or not email:
        return None
    existing = conn.execute(sa.text("""
        SELECT id, enrollment_ids, child_names FROM kita_parent_accounts WHERE LOWER(email)=LOWER(:e) LIMIT 1
    """), {"e": email}).first()

    token = _kn_secrets.token_urlsafe(32)

    if existing:
        # Update: Kind ergänzen
        existing_eids = list(existing[1] or [])
        existing_names = (existing[2] or "").strip()
        if enrollment_id and enrollment_id not in existing_eids:
            existing_eids.append(enrollment_id)
        if child_name and child_name not in existing_names:
            existing_names = (existing_names + ", " + child_name) if existing_names else child_name
        conn.execute(sa.text("""
            UPDATE kita_parent_accounts SET
              enrollment_ids = :eids, child_names = :cn,
              login_token = :tok, token_expires_at = NOW() + INTERVAL '90 days',
              updated_at = NOW()
            WHERE id = :id
        """), {"eids": existing_eids, "cn": existing_names, "tok": token, "id": existing[0]})
        return existing[0]
    else:
        pid = _new_id("par")
        conn.execute(sa.text("""
            INSERT INTO kita_parent_accounts
              (id, full_name, email, phone, role, enrollment_ids, child_names,
               source_doc_id, consent_given, login_token, token_expires_at)
            VALUES (:id, :n, :e, :p, :r, :eids, :cn, :sd, true, :tok, NOW() + INTERVAL '90 days')
        """), {
            "id": pid, "n": full_name, "e": email, "p": phone, "r": role,
            "eids": [enrollment_id] if enrollment_id else [],
            "cn": child_name, "sd": doc_id, "tok": token,
        })
        return pid


# ============================================================
# BESTÄTIGUNGS-MAIL (nach Anmeldung)
# ============================================================

def _kn_send_anmeldung_confirmation(parent_email: str, parent_name: str, child_name: str,
                                     modules: dict, hours: float, login_token: str,
                                     enrolled_from: str = None):
    """Schöne Bestätigungs-Mail mit App-Link + Install-Anleitung."""
    if not parent_email:
        return False

    # Module-Liste menschenlesbar
    weekday_de = {"monday": "Mo", "tuesday": "Di", "wednesday": "Mi", "thursday": "Do", "friday": "Fr"}
    slot_de = {"07:15-11:30": "Vormittag", "11:30-12:30": "Mittagsbetreuung",
               "12:30-13:30": "Mittagsruhe", "13:30-17:30": "Nachmittag"}
    module_lines = []
    for day, slots in (modules or {}).items():
        for slot in slots:
            module_lines.append(f"<li><strong>{weekday_de.get(day, day)}</strong> · {slot_de.get(slot, slot)} <small style=\"color:#9a8e9e;\">({slot})</small></li>")
    modules_html = "<ul style='padding-left:20px; margin:0;'>" + "".join(module_lines) + "</ul>" if module_lines else "<em>keine Module gewählt</em>"

    eltern_app_url = f"{KITA_BASE_URL}/accounting/ui/kita/eltern?t={login_token}"

    content = f"""
    <h1 style="margin:0 0 8px; font-size:24px; background:linear-gradient(120deg,#ff4d8d,#a855f7); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;">
      Anmeldung bestätigt 🎉
    </h1>
    <p style="margin:0 0 18px; color:#5a5060; font-size:15px;">
      Hallo {parent_name},<br>
      vielen Dank für die Anmeldung von <strong>{child_name}</strong>. Wir freuen uns!
    </p>

    <div style="background:#fffbf0; border:2px dashed #ffd93d; border-radius:14px; padding:16px; margin-bottom:18px;">
      <strong style="color:#2a2530;">📋 Eure Anmelde-Daten</strong>
      <table style="width:100%; margin-top:8px; font-size:14px;">
        <tr><td style="color:#9a8e9e; padding:4px 0;">Kind:</td><td><strong>{child_name}</strong></td></tr>
        <tr><td style="color:#9a8e9e; padding:4px 0;">Vertrag ab:</td><td>{enrolled_from or '—'}</td></tr>
        <tr><td style="color:#9a8e9e; padding:4px 0; vertical-align:top;">Module:</td><td>{modules_html}</td></tr>
        <tr><td style="color:#9a8e9e; padding:4px 0;">Wochenstunden:</td><td><strong style="color:#2d7a5f;">{hours:.1f} h</strong></td></tr>
      </table>
    </div>

    <div style="background:linear-gradient(135deg,#ff4d8d 0%,#a855f7 100%); color:#fff; padding:20px; border-radius:16px; margin-bottom:18px; text-align:center;">
      <strong style="display:block; font-size:13px; opacity:0.9; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px;">📱 Eltern-App</strong>
      <p style="margin:0 0 14px; font-size:14px;">
        Krankmeldungen, Mitteilungen, wichtige Updates — alles in der App.
      </p>
      <a href="{eltern_app_url}" style="display:inline-block; padding:12px 24px; background:#fff; color:#a855f7; text-decoration:none; border-radius:10px; font-weight:700; font-size:14px;">
        App öffnen →
      </a>
    </div>

    <details style="margin-bottom:14px;">
      <summary style="cursor:pointer; font-weight:600; color:#2a2530; padding:8px 0;">📲 So installiert ihr die App auf dem Handy</summary>
      <div style="padding:12px; background:#f9f4ec; border-radius:10px; font-size:13px; color:#5a5060;">
        <p style="margin:0 0 8px;"><strong>iPhone (Safari):</strong></p>
        <ol style="padding-left:20px; margin:0 0 12px;">
          <li>Den App-Link oben in Safari öffnen</li>
          <li>Auf das Teilen-Symbol tippen ⬆️</li>
          <li>„Zum Home-Bildschirm" wählen</li>
          <li>Mit „Hinzufügen" bestätigen</li>
        </ol>
        <p style="margin:0 0 8px;"><strong>Android (Chrome):</strong></p>
        <ol style="padding-left:20px; margin:0;">
          <li>Den App-Link oben in Chrome öffnen</li>
          <li>Drei Punkte oben rechts ⋮</li>
          <li>„App installieren" oder „Zum Startbildschirm" wählen</li>
          <li>Bestätigen</li>
        </ol>
      </div>
    </details>

    <p style="color:#9a8e9e; font-size:12px; margin:16px 0 0; line-height:1.6;">
      Der Link oben ist persönlich für euch und 90 Tage gültig. Bei Fragen einfach in der KITA melden.
    </p>
    """
    html = _kn_holi_mail_template(content)
    text = f"""Hallo {parent_name},

vielen Dank für die Anmeldung von {child_name}.

Wochenstunden: {hours:.1f}h
Vertrag ab: {enrolled_from or '—'}

Eltern-App: {eltern_app_url}

(Link 90 Tage gültig)

SHIKSHA · KITA"""
    ok, err = _kn_send_mail(parent_email, f"Anmeldung bestätigt: {child_name}", html, text)
    return ok


# ============================================================
# ENDPOINTS — ELTERN-ACCOUNTS
# ============================================================

@kita_router.get("/eltern/me")
async def kita_eltern_me(t: str = ""):
    """Token-Login: Eltern öffnen App via Link mit ?t=XYZ aus Mail."""
    if not t:
        raise HTTPException(401, "kein Token")
    with engine.connect() as conn:
        row = conn.execute(sa.text("""
            SELECT id, full_name, email, phone, role, enrollment_ids, child_names,
                   notification_email_optin, notification_push_optin
            FROM kita_parent_accounts
            WHERE login_token = :t AND (token_expires_at IS NULL OR token_expires_at > NOW())
            LIMIT 1
        """), {"t": t}).first()
    if not row:
        raise HTTPException(401, "Token ungültig oder abgelaufen")
    return {
        "id": row[0], "full_name": row[1], "email": row[2], "phone": row[3], "role": row[4],
        "enrollment_ids": list(row[5] or []), "child_names": row[6],
        "notification_email_optin": row[7],
        "notification_push_optin": row[8],
    }


@kita_router.get("/eltern/notifications")
async def kita_eltern_notifications(t: str = ""):
    """Mitteilungen, die diesen Eltern zugestellt wurden."""
    if not t:
        raise HTTPException(401, "kein Token")
    with engine.connect() as conn:
        parent = conn.execute(sa.text("SELECT id FROM kita_parent_accounts WHERE login_token=:t LIMIT 1"),
                              {"t": t}).first()
        if not parent:
            raise HTTPException(401, "Token ungültig")
        rows = conn.execute(sa.text("""
            SELECT n.id, n.title, n.body, n.body_html, n.priority, n.sent_at, r.opened_at
            FROM kita_notification_recipients r
            JOIN kita_notifications n ON n.id = r.notification_id
            WHERE r.parent_id = :pid AND n.status = 'sent'
            ORDER BY n.sent_at DESC LIMIT 50
        """), {"pid": parent[0]}).fetchall()
    return {
        "count": len(rows),
        "notifications": [
            {
                "id": r[0], "title": r[1], "body": r[2], "body_html": r[3],
                "priority": r[4],
                "sent_at": r[5].isoformat() if r[5] else None,
                "opened_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ],
    }


# ============================================================
# ENDPOINTS — BENACHRICHTIGUNGEN (Trägerin)
# ============================================================

@kita_router.get("/notifications")
async def kita_notif_list(limit: int = 50):
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT n.id, n.title, n.body, n.target_type, n.target_group_id, n.target_enrollment_ids,
                   n.target_parent_ids, n.include_staff, n.priority, n.status, n.sent_at, n.created_at,
                   (SELECT COUNT(*) FROM kita_notification_recipients WHERE notification_id = n.id) AS recip_count,
                   (SELECT COUNT(*) FROM kita_notification_recipients WHERE notification_id = n.id AND delivery_status = 'sent') AS sent_count
            FROM kita_notifications n
            ORDER BY n.created_at DESC LIMIT :lim
        """), {"lim": limit}).fetchall()
    return {
        "count": len(rows),
        "notifications": [
            {
                "id": r[0], "title": r[1], "body": r[2],
                "target_type": r[3], "target_group_id": r[4],
                "target_enrollment_count": len(r[5] or []),
                "target_parent_count": len(r[6] or []),
                "include_staff": r[7], "priority": r[8],
                "status": r[9],
                "sent_at": r[10].isoformat() if r[10] else None,
                "created_at": r[11].isoformat() if r[11] else None,
                "recipients_total": r[12], "recipients_sent": r[13],
            }
            for r in rows
        ],
    }


@kita_router.post("/notifications")
async def kita_notif_create(payload: dict = Body(...)):
    """Erstellt eine Mitteilung als Draft (noch nicht versendet)."""
    title = (payload.get("title") or "").strip()
    body = (payload.get("body") or "").strip()
    if not title or not body:
        raise HTTPException(400, "title + body Pflicht")
    target_type = payload.get("target_type", "all")
    if target_type not in ("all", "group", "children", "parent"):
        raise HTTPException(400, "target_type muss all|group|children|parent sein")

    nid = _new_id("notif")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_notifications
              (id, title, body, body_html, target_type, target_group_id,
               target_enrollment_ids, target_parent_ids, include_staff,
               send_via_email, priority, status, created_by)
            VALUES (:id, :t, :b, :bh, :tt, :tg, :te, :tp, :is_, :em, :pr, 'draft', :cb)
        """), {
            "id": nid, "t": title, "b": body, "bh": payload.get("body_html"),
            "tt": target_type, "tg": payload.get("target_group_id"),
            "te": payload.get("target_enrollment_ids", []),
            "tp": payload.get("target_parent_ids", []),
            "is_": bool(payload.get("include_staff", False)),
            "em": bool(payload.get("send_via_email", True)),
            "pr": payload.get("priority", "normal"),
            "cb": payload.get("created_by", "kita-leitung"),
        })
    return {"id": nid, "status": "draft"}


@kita_router.post("/notifications/{nid}/send")
async def kita_notif_send(nid: str):
    """Resolves Empfänger, erstellt recipient-Datensätze, schickt E-Mails."""
    with engine.begin() as conn:
        n = conn.execute(sa.text("""
            SELECT id, title, body, body_html, target_type, target_group_id,
                   target_enrollment_ids, target_parent_ids, include_staff,
                   send_via_email, priority, status
            FROM kita_notifications WHERE id=:id
        """), {"id": nid}).first()
        if not n:
            raise HTTPException(404, "Mitteilung nicht gefunden")
        if n[11] == "sent":
            raise HTTPException(400, "Bereits versendet")

        # Empfänger ermitteln
        recipients = []  # list of (parent_id, email, full_name, child_names)
        if n[4] == "all":
            rows = conn.execute(sa.text("""
                SELECT id, email, full_name, child_names FROM kita_parent_accounts
                WHERE notification_email_optin = true AND email IS NOT NULL AND email != ''
            """)).fetchall()
            recipients = [(r[0], r[1], r[2], r[3]) for r in rows]
        elif n[4] == "group" and n[5]:
            rows = conn.execute(sa.text("""
                SELECT DISTINCT pa.id, pa.email, pa.full_name, pa.child_names
                FROM kita_parent_accounts pa,
                     unnest(pa.enrollment_ids) AS eid
                JOIN kita_child_enrollments ce ON ce.id = eid
                WHERE ce.group_id = :g AND pa.notification_email_optin = true
            """), {"g": n[5]}).fetchall()
            recipients = [(r[0], r[1], r[2], r[3]) for r in rows]
        elif n[4] == "children" and n[6]:
            target_eids = list(n[6] or [])
            rows = conn.execute(sa.text("""
                SELECT DISTINCT pa.id, pa.email, pa.full_name, pa.child_names
                FROM kita_parent_accounts pa,
                     unnest(pa.enrollment_ids) AS eid
                WHERE eid = ANY(:eids) AND pa.notification_email_optin = true
            """), {"eids": target_eids}).fetchall()
            recipients = [(r[0], r[1], r[2], r[3]) for r in rows]
        elif n[4] == "parent" and n[7]:
            target_pids = list(n[7] or [])
            rows = conn.execute(sa.text("""
                SELECT id, email, full_name, child_names FROM kita_parent_accounts
                WHERE id = ANY(:pids) AND notification_email_optin = true
            """), {"pids": target_pids}).fetchall()
            recipients = [(r[0], r[1], r[2], r[3]) for r in rows]

        # Optional: Mitarbeiter (Betreuer)
        staff_recipients = []
        if n[8]:
            srows = conn.execute(sa.text("""
                SELECT id, full_name FROM kita_staff_members WHERE left_at IS NULL
            """)).fetchall()
            staff_recipients = [(r[0], r[1]) for r in srows]

        # Insert recipient-Datensätze
        for pid, email, name, child in recipients:
            conn.execute(sa.text("""
                INSERT INTO kita_notification_recipients
                  (id, notification_id, recipient_type, parent_id, email, delivery_status)
                VALUES (:id, :nid, 'parent', :p, :e, 'pending')
            """), {"id": _new_id("rec"), "nid": nid, "p": pid, "e": email})
        for sid, sname in staff_recipients:
            conn.execute(sa.text("""
                INSERT INTO kita_notification_recipients
                  (id, notification_id, recipient_type, staff_id, delivery_status)
                VALUES (:id, :nid, 'staff', :s, 'pending')
            """), {"id": _new_id("rec"), "nid": nid, "s": sid})

        conn.execute(sa.text("UPDATE kita_notifications SET status='sending' WHERE id=:id"), {"id": nid})

    # E-Mails versenden
    sent_count = 0
    failed_count = 0
    if n[9]:  # send_via_email
        title, body, body_html = n[1], n[2], n[3]
        priority = n[10]
        prio_emoji = {"urgent": "🚨", "high": "⚠️", "normal": "📩", "low": "💬"}.get(priority, "📩")
        for pid, email, name, child in recipients:
            if not email:
                continue
            content_html = (body_html or f"<p>{body}</p>")
            full_html = _kn_holi_mail_template(f"""
                <h1 style="margin:0 0 8px; font-size:22px; color:#2a2530;">
                  {prio_emoji} {title}
                </h1>
                <p style="margin:0 0 4px; color:#9a8e9e; font-size:13px;">Hallo {name or 'Eltern'},</p>
                <div style="font-size:15px; color:#2a2530; line-height:1.7; margin:14px 0;">
                  {content_html}
                </div>
                <p style="margin:18px 0 0; color:#9a8e9e; font-size:12px;">
                  Diese Mitteilung betrifft: <strong>{child or 'eure Familie'}</strong>
                </p>
            """)
            ok, err = _kn_send_mail(email, f"{prio_emoji} {title}", full_html, body)
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    UPDATE kita_notification_recipients
                    SET delivery_status = :st, sent_at = NOW(), error_message = :err
                    WHERE notification_id = :nid AND parent_id = :pid
                """), {"st": "sent" if ok else "failed", "err": err if not ok else None,
                       "nid": nid, "pid": pid})
            if ok:
                sent_count += 1
            else:
                failed_count += 1

    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE kita_notifications SET status='sent', sent_at=NOW() WHERE id=:id"),
                     {"id": nid})

    return {
        "id": nid, "status": "sent",
        "recipients_total": len(recipients) + len(staff_recipients),
        "emails_sent": sent_count, "emails_failed": failed_count,
    }


@kita_router.get("/notifications/{nid}/recipients")
async def kita_notif_recipients(nid: str):
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT r.id, r.recipient_type, r.email, r.delivery_status, r.sent_at, r.opened_at,
                   COALESCE(p.full_name, s.full_name) AS name
            FROM kita_notification_recipients r
            LEFT JOIN kita_parent_accounts p ON p.id = r.parent_id
            LEFT JOIN kita_staff_members s ON s.id = r.staff_id
            WHERE r.notification_id = :nid
            ORDER BY r.delivery_status DESC, name
        """), {"nid": nid}).fetchall()
    return {
        "count": len(rows),
        "recipients": [
            {
                "id": r[0], "type": r[1], "email": r[2],
                "status": r[3],
                "sent_at": r[4].isoformat() if r[4] else None,
                "opened_at": r[5].isoformat() if r[5] else None,
                "name": r[6],
            }
            for r in rows
        ],
    }


@kita_router.delete("/notifications/{nid}")
async def kita_notif_delete(nid: str):
    with engine.begin() as conn:
        result = conn.execute(sa.text("DELETE FROM kita_notifications WHERE id=:id"), {"id": nid})
        if result.rowcount == 0:
            raise HTTPException(404, "Mitteilung nicht gefunden")
    return {"id": nid, "deleted": True}


# ============================================================
# HOOK: Bestätigungs-Mail nach Anmeldung
# ============================================================

def _kn_post_anmeldung_hook(doc_id: str, payload: dict, modules: dict, hours: float):
    """
    Wird in submit_anmeldung am Ende aufgerufen.
    Legt Eltern-Account(s) an, schickt Bestätigungs-Mail.
    """
    child_name = payload.get("child_name") or payload.get("child_first_name", "") + " " + payload.get("child_last_name", "")
    enrolled_from = payload.get("enrolled_from")

    with engine.begin() as conn:
        for role, name_key, email_key, phone_key in [
            ("mutter", "mother_name", "mother_email", "mother_phone"),
            ("vater", "father_name", "father_email", "father_phone"),
        ]:
            email = (payload.get(email_key) or "").strip()
            name = (payload.get(name_key) or "").strip()
            if not email or not name:
                continue
            phone = (payload.get(phone_key) or "").strip()
            pid = _kn_create_or_update_parent(
                conn, full_name=name, email=email, phone=phone, role=role,
                enrollment_id=None,  # noch keine — bei "apply" gesetzt
                child_name=child_name, doc_id=doc_id,
            )
            # Token holen für Mail
            row = conn.execute(sa.text(
                "SELECT login_token FROM kita_parent_accounts WHERE id=:id"
            ), {"id": pid}).first()
            token = row[0] if row else None
            if token:
                _kn_send_anmeldung_confirmation(
                    parent_email=email, parent_name=name, child_name=child_name,
                    modules=modules, hours=hours, login_token=token,
                    enrolled_from=enrolled_from,
                )


"""
SHIKSHA · KITA · Eltern-Anmeldung — Public Endpoint
Public-API ohne Auth — Eltern bekommen Link, füllen aus, unterschreiben.

Speichert in kita_documents mit type='anmeldevertrag', subtype='digital_signed'.

Stand: 29.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import base64 as _ka_b64
from datetime import date as _ka_date


@kita_router.post("/anmeldung/submit")
async def kita_anmeldung_submit(payload: dict = Body(...)):
    """
    Speichert eine digital signierte Anmeldung.
    Public — ohne Auth (über sharbaren Link erreichbar).
    """
    # Pflicht-Felder
    child_name = (payload.get("child_name") or "").strip()
    child_birth = (payload.get("birth_date") or "").strip()
    signature_data = payload.get("signature_data_url", "")  # data:image/png;base64,XXXX

    if not child_name or not child_birth:
        raise HTTPException(400, "Kind-Name und Geburtsdatum sind Pflicht")
    if not signature_data.startswith("data:image"):
        raise HTTPException(400, "Unterschrift fehlt")

    doc_id = _new_id("kdoc")

    # Signatur 1 als PNG speichern (Pflicht)
    KITA_DOC_DIR.mkdir(parents=True, exist_ok=True)
    sig_filename = f"{doc_id}_signature_1.png"
    sig_path = KITA_DOC_DIR / sig_filename
    try:
        header, b64data = signature_data.split(",", 1)
        sig_bytes = _ka_b64.b64decode(b64data)
        sig_path.write_bytes(sig_bytes)
    except Exception as e:
        raise HTTPException(400, f"Signatur konnte nicht gespeichert werden: {e}")

    # Signatur 2 (optional)
    sig_path_2 = None
    signature_data_2 = payload.get("signature_data_url_2") or ""
    if signature_data_2.startswith("data:image"):
        try:
            sig_filename_2 = f"{doc_id}_signature_2.png"
            sig_path_2 = KITA_DOC_DIR / sig_filename_2
            _, b64data_2 = signature_data_2.split(",", 1)
            sig_path_2.write_bytes(_ka_b64.b64decode(b64data_2))
        except Exception as e:
            print(f"[anmeldung] Signatur 2 konnte nicht gespeichert werden: {e}")
            sig_path_2 = None

    # Module-Matrix: {monday: ['07:15-11:30'], wednesday: ['13:30-17:30'], ...}
    modules = payload.get("modules", {})
    booked_hours_per_week = 0.0
    SLOT_HOURS = {
        "07:15-11:30": 4.25, "11:30-12:30": 1.0,
        "12:30-13:30": 1.0, "13:30-17:30": 4.0,
    }
    for day_slots in modules.values():
        for slot in day_slots:
            booked_hours_per_week += SLOT_HOURS.get(slot, 0)

    # In DB
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_documents
              (id, document_type, detected_subtype, file_path, file_name,
               file_size, file_mime, source_type, status, raw_text, notes)
            VALUES (:id, 'anmeldevertrag', 'digital_signed', :p, :n, :sz, 'image/png', 'web_form', 'pending', :rt, :no)
        """), {
            "id": doc_id, "p": str(sig_path), "n": sig_filename,
            "sz": sig_path.stat().st_size,
            "rt": f"Digital signiert von {child_name} (Geb. {child_birth})",
            "no": f"Digitale Anmeldung über Web-Formular am {datetime.now().isoformat()}",
        })

        # Alle Felder aus dem Payload übernehmen
        field_map = {
            "child_name": child_name,
            "child_first_name": payload.get("child_first_name"),
            "child_last_name": payload.get("child_last_name"),
            "birth_date": child_birth,
            "child_address": payload.get("child_address"),
            "child_postal_code": payload.get("child_postal_code"),
            "child_city": payload.get("child_city"),
            "mother_tongue": payload.get("mother_tongue"),
            "languages_learned": payload.get("languages_learned"),
            "nationality": payload.get("nationality"),
            "sv_number": payload.get("sv_number"),
            "mother_name": payload.get("mother_name"),
            "mother_email": payload.get("mother_email"),
            "mother_phone": payload.get("mother_phone"),
            "mother_employer": payload.get("mother_employer"),
            "father_name": payload.get("father_name"),
            "father_email": payload.get("father_email"),
            "father_phone": payload.get("father_phone"),
            "father_employer": payload.get("father_employer"),
            "enrolled_from": payload.get("enrolled_from"),
            "enrolled_to": payload.get("enrolled_to"),
            "modules_json": str(modules),
            "booked_hours_per_week": str(booked_hours_per_week),
            "kita_name": payload.get("kita_name"),
            "consent_given": "true" if payload.get("consent") else "false",
            "signed_at": datetime.now().isoformat(),
            "signed_location": payload.get("signed_location"),
            "signed_by_1_label": payload.get("signed_by_1_label"),
            "signed_by_2_label": payload.get("signed_by_2_label"),
            "signature_1_path": str(sig_path),
            "signature_2_path": str(sig_path_2) if sig_path_2 else None,
            "signed_by_count": "2" if sig_path_2 else "1",
        }
        for key, val in field_map.items():
            if val is None or val == "":
                continue
            conn.execute(sa.text("""
                INSERT INTO kita_document_fields (id, document_id, field_key, field_value, confidence, is_user_edited)
                VALUES (:id, :did, :k, :v, 1.0, true)
            """), {
                "id": _new_id("kfld"), "did": doc_id, "k": key, "v": str(val)[:1000],
            })

    # Hook: Eltern-Account anlegen + Bestätigungs-Mail
    try:
        _kn_post_anmeldung_hook(doc_id, payload, modules, booked_hours_per_week)
    except Exception as e:
        print(f"[anmeldung] Mail-Hook fehlgeschlagen: {e}")

    return {
        "ok": True,
        "document_id": doc_id,
        "child_name": child_name,
        "booked_hours_per_week": booked_hours_per_week,
        "signed_by_count": 2 if sig_path_2 else 1,
        "message": "Anmeldung erfolgreich — Bestätigungs-Mail mit App-Link wurde verschickt.",
    }


@kita_router.get("/anmeldung/info")
async def kita_anmeldung_info():
    """Stammdaten für Anmelde-Form (Gruppen, gültiges Regelwerk)."""
    with engine.connect() as conn:
        groups = conn.execute(sa.text("""
            SELECT id, name, group_type, capacity FROM kita_groups WHERE closed_at IS NULL
        """)).fetchall()
    return {
        "available_groups": [
            {"id": g[0], "name": g[1], "type": g[2], "capacity": g[3]}
            for g in groups
        ],
        "modules": [
            {"label": "Vormittag", "slot": "07:15-11:30", "hours": 4.25, "price": 0},
            {"label": "Mittagsbetreuung", "slot": "11:30-12:30", "hours": 1.0, "price": 14, "currency": "EUR"},
            {"label": "Mittagsruhe", "slot": "12:30-13:30", "hours": 1.0, "price": 8, "currency": "EUR"},
            {"label": "Nachmittag", "slot": "13:30-17:30", "hours": 4.0, "price": 0},
        ],
        "weekdays": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "weekday_labels": {"monday": "Montag", "tuesday": "Dienstag", "wednesday": "Mittwoch",
                           "thursday": "Donnerstag", "friday": "Freitag"},
    }
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
"""
SHIKSHA · KITA · ST%-Auto-Calc aus existierenden DB-Daten
Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.

Endpoints:
  - GET  /kita/groups/unified            (Legacy + neue Gruppen mit Kinderzahlen)
  - POST /kita/st-calc/auto/{group_id}   (Auto-Berechnung aus DB)
  - GET  /kita/staff/total-st            (Ist-ST% aller aktiven Mitarbeiter)

Stand: 29.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===


@kita_router.get("/groups/unified")
async def kita_groups_unified():
    """Vereinigt neue + Legacy-Gruppen mit aktueller Kinder-Anzahl."""
    result = []
    with engine.connect() as conn:
        # Neue Gruppen
        try:
            for r in conn.execute(sa.text("""
                SELECT g.id, g.name, g.group_type, g.capacity, g.founded_at,
                  (SELECT COUNT(*) FROM kita_child_enrollments e
                   WHERE e.group_id = g.id
                     AND (e.enrolled_to IS NULL OR e.enrolled_to >= CURRENT_DATE)) AS n_children
                FROM kita_groups g
                WHERE g.closed_at IS NULL ORDER BY g.name
            """)).fetchall():
                result.append({
                    "id": r[0], "name": r[1], "group_type": r[2], "capacity": r[3],
                    "founded_at": r[4].isoformat() if r[4] else None,
                    "n_children": r[5] or 0, "source": "new",
                })
        except Exception as e:
            print(f"[unified] new groups: {e}")

        # Legacy-Gruppen
        try:
            for r in conn.execute(sa.text("""
                SELECT g.id, g.name, g.capacity,
                  (SELECT COUNT(*) FROM kita_legacy_children c
                   WHERE c.group_id = g.id AND c.active = true) AS n_children
                FROM kita_legacy_groups g
                WHERE g.active = true ORDER BY g.name
            """)).fetchall():
                result.append({
                    "id": f"legacy_{r[0]}", "name": f"{r[1]}", "group_type": "kkg_legacy",
                    "capacity": r[2], "founded_at": None,
                    "n_children": r[3] or 0, "source": "legacy", "legacy_id": r[0],
                })
        except Exception as e:
            print(f"[unified] legacy groups: {e}")
    return {"count": len(result), "groups": result}


def _stc_auto_warnings(n_0_1, n_2, n_3, n_4_plus, capacity):
    warnings = []
    total = n_0_1 + n_2 + n_3 + n_4_plus

    if (n_3 + n_4_plus) > (n_0_1 + n_2) and total > 0:
        warnings.append(f"Mehrheit ≥3-Jährige ({n_3 + n_4_plus} von {total}) — formal KIGA-Gruppe, nicht KKG. Anderer Schlüssel anwenden.")

    if (n_0_1 >= 4 or n_0_1 > n_2) and total > 9:
        warnings.append(f"Variante 1 (überw. 0-1J) erfordert max 9 Kinder — angemeldet: {total}. Berechnung wird auf 9 gecapt.")

    if not (n_0_1 >= 4 or n_0_1 > n_2) and total > 12:
        warnings.append(f"Variante 2 (überw. 2J) erfordert max 12 Kinder — angemeldet: {total}. Berechnung wird auf 12 gecapt.")

    if capacity and total > capacity:
        warnings.append(f"Gruppen-Kapazität laut Bewilligung: {capacity}, angemeldet: {total}.")

    return warnings


@kita_router.post("/st-calc/auto/{group_id}")
async def kita_stcalc_auto(
    group_id: str,
    payload: dict = Body(default_factory=dict),
):
    """
    Auto-Berechnung: Liest Kinderdaten aus DB,
    erzeugt halfday_data mit Vollbelegung-Annahme,
    rechnet ST% wie /st-calc/preview.

    Body (optional):
      {
        "snapshot_month": "2026-04-01",
        "default_oz_vm": 4.5,
        "default_oz_nm": 4.0,
        "funding_basis": "KV",
        "group_count": 1
      }
    """
    snapshot_month_str = payload.get("snapshot_month") or _stc_date.today().replace(day=1).isoformat()
    target_month = _stc_date.fromisoformat(snapshot_month_str)

    # Stichtag: 31.8. des aktuellen Schuljahres
    schuljahr_year = target_month.year if target_month.month >= 9 else target_month.year - 1
    stichtag = _stc_date(schuljahr_year, 8, 31)

    default_oz_vm = float(payload.get("default_oz_vm") or 4.5)
    default_oz_nm = float(payload.get("default_oz_nm") or 4.0)
    funding_basis = payload.get("funding_basis", "KV")
    group_count = int(payload.get("group_count") or 1)

    is_legacy = group_id.startswith("legacy_")
    children = []
    group_info = {}

    with engine.connect() as conn:
        if is_legacy:
            try:
                legacy_id = int(group_id.replace("legacy_", ""))
            except ValueError:
                raise HTTPException(400, f"Ungültige Legacy-ID: {group_id}")
            children = conn.execute(sa.text("""
                SELECT name, birth_year FROM kita_legacy_children
                WHERE group_id = :g AND active = true
            """), {"g": legacy_id}).fetchall()
            grow = conn.execute(sa.text(
                "SELECT name, capacity FROM kita_legacy_groups WHERE id=:id"
            ), {"id": legacy_id}).first()
            if grow:
                group_info = {"name": grow[0], "capacity": grow[1]}
        else:
            children_raw = conn.execute(sa.text("""
                SELECT child_anon_id, age_months FROM kita_child_enrollments
                WHERE group_id = :g
                  AND (enrolled_to IS NULL OR enrolled_to >= CURRENT_DATE)
            """), {"g": group_id}).fetchall()
            for c in children_raw:
                bm = c[1] or 36
                approx_birth_year = stichtag.year - (bm // 12)
                children.append((c[0], approx_birth_year))
            grow = conn.execute(sa.text(
                "SELECT name, capacity FROM kita_groups WHERE id=:id"
            ), {"id": group_id}).first()
            if grow:
                group_info = {"name": grow[0], "capacity": grow[1]}

    if not children:
        raise HTTPException(404, f"Keine Kinder gefunden für Gruppe {group_id}")

    # Aufteilung Altersgruppen
    n_0_1 = n_2 = n_3 = n_4_plus = 0
    for c in children:
        by = c[1] or 0
        age = stichtag.year - by
        if age <= 1:
            n_0_1 += 1
        elif age == 2:
            n_2 += 1
        elif age == 3:
            n_3 += 1
        else:
            n_4_plus += 1

    # Halfday-data: alle 10 Halbtage mit gleicher Belegung (Vollbelegung)
    halfday_data = {}
    for wd in WEEKDAYS:
        for hd, oz in [("vm", default_oz_vm), ("nm", default_oz_nm)]:
            halfday_data[f"{wd}_{hd}"] = {
                "oz": oz, "n_0_1": n_0_1, "n_2": n_2, "n_3": n_3, "n_4_plus": n_4_plus,
            }

    # Innere Berechnung
    inner_payload = {
        "halfday_data": halfday_data,
        "funding_basis": funding_basis,
        "group_count": group_count,
    }
    if not is_legacy:
        inner_payload["group_id"] = group_id
        inner_payload["snapshot_month"] = target_month.isoformat()

    result = await kita_stcalc_preview(inner_payload)

    return {
        **result,
        "auto_filled": True,
        "is_legacy": is_legacy,
        "stichtag": stichtag.isoformat(),
        "default_oz_vm": default_oz_vm,
        "default_oz_nm": default_oz_nm,
        "children_count": len(children),
        "age_distribution": {
            "n_0_1": n_0_1, "n_2": n_2, "n_3": n_3, "n_4_plus": n_4_plus,
        },
        "group_info": group_info,
        "halfday_data": halfday_data,
        "warnings": _stc_auto_warnings(n_0_1, n_2, n_3, n_4_plus, group_info.get("capacity")),
    }


@kita_router.get("/staff/total-st")
async def kita_staff_total_st(funding_basis: str = "KV"):
    """
    Berechnet das Ist-Stellenprozent aller aktiven Mitarbeiter (Legacy + neue).
    Vergleichsbasis: KV (39h) oder GAG (40h).
    """
    rate = KV_ST_PRO_STUNDE if funding_basis.upper() == "KV" else GAG_ST_PRO_STUNDE
    legacy_staff = []
    new_staff = []
    with engine.connect() as conn:
        # Legacy
        try:
            for r in conn.execute(sa.text("""
                SELECT id, name, role, weekly_hours, group_id
                FROM kita_legacy_staff WHERE active = true
            """)).fetchall():
                hours = float(r[3] or 0)
                legacy_staff.append({
                    "id": r[0], "name": r[1], "role": r[2],
                    "weekly_hours": hours,
                    "st_pct": round(hours * rate, 2),
                    "group_id": r[4], "source": "legacy",
                })
        except Exception:
            pass
        # Neue
        try:
            for r in conn.execute(sa.text("""
                SELECT s.id, s.full_name, s.qualification,
                  (SELECT weekly_hours FROM kita_staff_contracts c
                   WHERE c.staff_id = s.id
                     AND (c.valid_to IS NULL OR c.valid_to >= CURRENT_DATE)
                   ORDER BY c.valid_from DESC LIMIT 1) AS wh
                FROM kita_staff_members s WHERE s.left_at IS NULL
            """)).fetchall():
                hours = float(r[3] or 0)
                new_staff.append({
                    "id": r[0], "name": r[1], "role": r[2],
                    "weekly_hours": hours,
                    "st_pct": round(hours * rate, 2),
                    "source": "new",
                })
        except Exception:
            pass

    all_staff = legacy_staff + new_staff
    total_hours = sum(s["weekly_hours"] for s in all_staff)
    total_st = sum(s["st_pct"] for s in all_staff)

    return {
        "count": len(all_staff),
        "funding_basis": funding_basis,
        "total_weekly_hours": round(total_hours, 2),
        "total_st_pct": round(total_st, 2),
        "staff": all_staff,
    }
"""
SHIKSHA · KITA · Anwesenheit + Daily Assignments + Archiv

Endpoints:
  GET  /kita/anwesenheit/today         — Live-Snapshot für Polling (15s)
  GET  /kita/anwesenheit?date=YYYY-MM-DD
  POST /kita/anwesenheit/assign        — Person zu Bereich/Gruppe zuordnen
  PATCH /kita/anwesenheit/{id}/status  — Status ändern (anwesend/krank/...)
  GET  /kita/group-merges              — aktive Gruppen-Merges (Sommersprossen)
  POST /kita/group-merges              — Merge anlegen
  GET  /archive/documents              — Cross-Edition Archiv-Liste
  GET  /archive/documents/{id}/file    — Original mit Audit-Log
  POST /archive/snapshot/attendance    — On-demand PDF generieren

Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.

Stand: 30.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import hashlib as _aw_hash
import json as _aw_json
from datetime import date as _aw_date, datetime as _aw_dt, time as _aw_time, timedelta as _aw_td
from pathlib import Path as _aw_Path
from fastapi.responses import FileResponse as _aw_FileResponse


ARCHIVE_DIR = _aw_Path("/opt/shiksha/archive")
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


# Bereich-Reihenfolge + Default-Farben (Holi-Palette)
AREA_ORDER = ["vormittag", "mittagessen", "ruhe", "nachmittag", "vbz", "pause", "kuechendienst"]
AREA_COLORS = {
    "vormittag": "#ffd93d",      # Yellow
    "mittagessen": "#ff8c42",    # Orange
    "ruhe": "#a855f7",           # Purple
    "nachmittag": "#00d4d4",     # Turquoise
    "vbz": "#c8e6c0",            # Green-Soft
    "pause": "#d8d4ce",          # Grey-Soft
    "kuechendienst": "#c76b30",  # Brown-Red
}
STATUS_COLORS = {
    "planned": "#9a8e9e",
    "present": "#6dd47e",
    "absent": "#9a8e9e",
    "sick": "#ff4d8d",
    "vacation": "#ffd93d",
    "course": "#a855f7",
    "other": "#9a8e9e",
}


# ============================================================
# ANWESENHEIT — heutiger Snapshot
# ============================================================

@kita_router.get("/anwesenheit/today")
async def kita_anwesenheit_today():
    """Live-Snapshot pro Gruppe + Mitarbeiter, optimiert für 15s-Polling."""
    today = _aw_date.today()
    return await _aw_anwesenheit_for_date(today)


@kita_router.get("/anwesenheit")
async def kita_anwesenheit_for_date(date: str):
    target = _aw_date.fromisoformat(date)
    return await _aw_anwesenheit_for_date(target)


async def _aw_anwesenheit_for_date(target: _aw_date):
    """Zentrale Logik — gibt Sektionen pro Gruppe zurück mit Avatar-Daten."""
    weekday_key = target.strftime("%A").lower()  # 'monday', 'tuesday', ...

    with engine.connect() as conn:
        # 1. Aktive Gruppen-Merges für diesen Tag
        merges_today = conn.execute(sa.text("""
            SELECT id, merged_name, from_group_legacy_ids, time_from, time_to, weekdays
            FROM kita_group_merges
            WHERE active = true
              AND (valid_from_date IS NULL OR valid_from_date <= :d)
              AND (valid_to_date IS NULL OR valid_to_date >= :d)
              AND (:wd = ANY(weekdays) OR weekdays IS NULL)
        """), {"d": target, "wd": weekday_key}).fetchall()

        # 2. Alle aktiven Gruppen (Legacy)
        groups = conn.execute(sa.text("""
            SELECT id, name, capacity FROM kita_legacy_groups WHERE active = true ORDER BY name
        """)).fetchall()

        # 3. Alle Daily-Assignments für heute
        assigns = conn.execute(sa.text("""
            SELECT da.id, da.person_type, da.legacy_staff_id, da.legacy_child_id,
                   da.group_legacy_id, da.area, da.status,
                   da.time_from, da.time_to, da.note, da.note_visible_to_parents
            FROM kita_daily_assignments da
            WHERE da.work_date = :d
        """), {"d": target}).fetchall()

        # 4. Stammdaten Mitarbeiter + Kinder (alle aktiv)
        staff = {r[0]: {"id": r[0], "name": r[1], "role": r[2], "weekly_hours": r[3], "group_id": r[4]}
                 for r in conn.execute(sa.text("""
                     SELECT id, name, role, weekly_hours, group_id
                     FROM kita_legacy_staff WHERE active = true
                 """)).fetchall()}
        children = {r[0]: {"id": r[0], "name": r[1], "birth_year": r[2], "group_id": r[3]}
                    for r in conn.execute(sa.text("""
                        SELECT id, name, birth_year, group_id
                        FROM kita_legacy_children WHERE active = true
                    """)).fetchall()}

    # Hilfsfunktion: Slices für eine Person aus den Assignments bauen
    def _slices_for_person(person_type: str, person_id: int):
        slices = []
        for a in assigns:
            pt = a[1]
            if pt != person_type:
                continue
            pid = a[2] if pt == "staff" else a[3]
            if pid != person_id:
                continue
            slices.append({
                "area": a[5], "status": a[6],
                "time_from": str(a[7]) if a[7] else None,
                "time_to": str(a[8]) if a[8] else None,
                "note": a[9],
                "note_visible_to_parents": bool(a[10]),
                "color": AREA_COLORS.get(a[5], "#888"),
                "status_color": STATUS_COLORS.get(a[6], "#888"),
            })
        # Sort by AREA_ORDER
        slices.sort(key=lambda x: AREA_ORDER.index(x["area"]) if x["area"] in AREA_ORDER else 99)
        return slices

    # Ist diese Gruppe aktuell in einem Merge enthalten?
    def _check_merge(group_id: int) -> dict | None:
        for m in merges_today:
            from_ids = list(m[2] or [])
            if group_id in from_ids:
                return {
                    "merge_id": m[0],
                    "merged_name": m[1],
                    "time_from": str(m[3]) if m[3] else None,
                    "time_to": str(m[4]) if m[4] else None,
                }
        return None

    # 5. Sektionen aufbauen pro Gruppe
    sections = []
    for g in groups:
        gid, gname, gcap = g[0], g[1], g[2]
        merge_info = _check_merge(gid)

        # Mitarbeiter dieser Gruppe (über kita_legacy_staff.group_id ODER tagesaktuelle Zuordnung)
        section_staff = []
        for sid, sdata in staff.items():
            slices = _slices_for_person("staff", sid)
            assigned_to_group_today = any(
                a[1] == "staff" and a[2] == sid and a[4] == gid for a in assigns
            )
            if sdata["group_id"] == gid or assigned_to_group_today:
                # Initial = erstes Zeichen Vorname
                initial = (sdata["name"] or "?").split()[0][:1].upper()
                section_staff.append({
                    "id": sid, "name": sdata["name"], "initial": initial,
                    "role": sdata["role"], "weekly_hours": sdata["weekly_hours"],
                    "type": "staff",
                    "slices": slices,
                    "is_paedagoge": sdata["role"] == "educator",
                })

        section_children = []
        for cid, cdata in children.items():
            slices = _slices_for_person("child", cid)
            assigned_to_group_today = any(
                a[1] == "child" and a[3] == cid and a[4] == gid for a in assigns
            )
            if cdata["group_id"] == gid or assigned_to_group_today:
                initial = (cdata["name"] or "?")[:1].upper()
                section_children.append({
                    "id": cid, "name": cdata["name"], "initial": initial,
                    "birth_year": cdata["birth_year"],
                    "type": "child",
                    "slices": slices,
                })

        # Counts
        present_kids = sum(1 for c in section_children if any(s["status"] == "present" for s in c["slices"]))
        present_staff = sum(1 for s in section_staff if any(sl["status"] == "present" for sl in s["slices"]))
        has_paedagoge = any(s["is_paedagoge"] and any(sl["status"] == "present" for sl in s["slices"]) for s in section_staff)

        sections.append({
            "group_id": gid,
            "group_name": gname,
            "capacity": gcap,
            "merged_into": merge_info,
            "staff": section_staff,
            "children": section_children,
            "counts": {
                "kids_total": len(section_children),
                "kids_present": present_kids,
                "staff_total": len(section_staff),
                "staff_present": present_staff,
                "has_paedagoge": has_paedagoge,
            },
        })

    return {
        "date": target.isoformat(),
        "weekday": weekday_key,
        "sections": sections,
        "merges_active_today": [
            {"id": m[0], "merged_name": m[1], "time_from": str(m[3]) if m[3] else None,
             "time_to": str(m[4]) if m[4] else None}
            for m in merges_today
        ],
        "areas": AREA_ORDER,
        "area_colors": AREA_COLORS,
        "status_colors": STATUS_COLORS,
    }


# ============================================================
# DAILY-ASSIGNMENTS CRUD
# ============================================================

@kita_router.post("/anwesenheit/assign")
async def kita_anwesenheit_assign(payload: dict = Body(...)):
    """Person zu Bereich/Gruppe zuordnen."""
    work_date = payload.get("work_date") or _aw_date.today().isoformat()
    person_type = payload.get("person_type")
    if person_type not in ("staff", "child"):
        raise HTTPException(400, "person_type muss 'staff' oder 'child' sein")

    aid = _new_id("dassign")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_daily_assignments
              (id, work_date, person_type,
               legacy_staff_id, new_staff_id, legacy_child_id, new_enrollment_id,
               group_legacy_id, group_new_id,
               area, status, time_from, time_to, note, note_visible_to_parents, created_by)
            VALUES (:id, :d, :pt,
                    :ls, :ns, :lc, :ne,
                    :gl, :gn,
                    :a, :s, :tf, :tt, :n, :nvp, :cb)
        """), {
            "id": aid, "d": work_date, "pt": person_type,
            "ls": payload.get("legacy_staff_id"), "ns": payload.get("new_staff_id"),
            "lc": payload.get("legacy_child_id"), "ne": payload.get("new_enrollment_id"),
            "gl": payload.get("group_legacy_id"), "gn": payload.get("group_new_id"),
            "a": payload.get("area", "vormittag"),
            "s": payload.get("status", "planned"),
            "tf": payload.get("time_from"), "tt": payload.get("time_to"),
            "n": payload.get("note"),
            "nvp": payload.get("note_visible_to_parents", False),
            "cb": payload.get("created_by", "system"),
        })
    return {"id": aid}


@kita_router.patch("/anwesenheit/{aid}/status")
async def kita_anwesenheit_status(aid: str, payload: dict = Body(...)):
    new_status = payload.get("status")
    if new_status not in ("planned", "present", "absent", "sick", "vacation", "course", "other"):
        raise HTTPException(400, f"Ungültiger Status: {new_status}")
    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            UPDATE kita_daily_assignments SET status = :s, updated_at = NOW() WHERE id = :id
        """), {"s": new_status, "id": aid})
        if result.rowcount == 0:
            raise HTTPException(404, "Assignment nicht gefunden")
    return {"id": aid, "status": new_status}


@kita_router.delete("/anwesenheit/{aid}")
async def kita_anwesenheit_delete(aid: str):
    with engine.begin() as conn:
        result = conn.execute(sa.text("DELETE FROM kita_daily_assignments WHERE id = :id"),
                              {"id": aid})
        if result.rowcount == 0:
            raise HTTPException(404, "Assignment nicht gefunden")
    return {"id": aid, "deleted": True}


# ============================================================
# GROUP-MERGES
# ============================================================

@kita_router.get("/group-merges")
async def kita_group_merges_list():
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, merged_name, from_group_legacy_ids, valid_from_date, valid_to_date,
                   weekdays, time_from, time_to, room_id, notes, active
            FROM kita_group_merges WHERE active = true
        """)).fetchall()
    return {
        "count": len(rows),
        "merges": [
            {
                "id": r[0], "merged_name": r[1], "from_group_ids": list(r[2] or []),
                "valid_from": r[3].isoformat() if r[3] else None,
                "valid_to": r[4].isoformat() if r[4] else None,
                "weekdays": list(r[5] or []),
                "time_from": str(r[6]) if r[6] else None,
                "time_to": str(r[7]) if r[7] else None,
                "room_id": r[8], "notes": r[9], "active": r[10],
            }
            for r in rows
        ],
    }


@kita_router.post("/group-merges")
async def kita_group_merge_create(payload: dict = Body(...)):
    name = payload.get("merged_name")
    if not name:
        raise HTTPException(400, "merged_name Pflicht")
    mid = _new_id("merge")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_group_merges
              (id, merged_name, from_group_legacy_ids, weekdays, time_from, time_to, room_id, notes)
            VALUES (:id, :n, :fg, :wd, :tf, :tt, :r, :no)
        """), {
            "id": mid, "n": name,
            "fg": payload.get("from_group_legacy_ids", []),
            "wd": payload.get("weekdays", ["monday","tuesday","wednesday","thursday","friday"]),
            "tf": payload.get("time_from", "13:30:00"),
            "tt": payload.get("time_to", "17:30:00"),
            "r": payload.get("room_id"), "no": payload.get("notes"),
        })
    return {"id": mid, "merged_name": name}


# ============================================================
# ARCHIV-MODUL
# ============================================================

def _aw_archive_save(edition: str, doc_type: str, target_id: str | None,
                     content_bytes: bytes, file_name: str, mime: str = "application/pdf",
                     period_from: _aw_date | None = None, period_to: _aw_date | None = None,
                     snapshot_for: _aw_date | None = None,
                     metadata: dict | None = None,
                     retention_years: int = 7,
                     legal_basis: str = "KBBG-Aufbewahrungsfrist"):
    """Speichert Datei im Archiv mit SHA256-Hash + Retention."""
    # Pfad-Konvention: archive/YYYY/MM/DD/
    today = snapshot_for or _aw_date.today()
    folder = ARCHIVE_DIR / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.day:02d}"
    folder.mkdir(parents=True, exist_ok=True)

    doc_id = _new_id("arc")
    safe_name = "".join(c for c in file_name if c.isalnum() or c in "._-")[:80]
    disk_path = folder / f"{doc_id}_{safe_name}"
    disk_path.write_bytes(content_bytes)

    file_hash = _aw_hash.sha256(content_bytes).hexdigest()
    retention_until = _aw_date.today().replace(year=_aw_date.today().year + retention_years)

    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO shiksha_archive_documents
              (id, edition, doc_type, target_id, file_path, file_name, file_mime, file_size, file_hash,
               period_from, period_to, snapshot_for, generated_by, retention_until, legal_basis, metadata)
            VALUES (:id, :ed, :dt, :ti, :p, :n, :m, :sz, :h,
                    :pf, :pt, :sf, :gb, :ru, :lb, CAST(:md AS jsonb))
        """), {
            "id": doc_id, "ed": edition, "dt": doc_type, "ti": target_id,
            "p": str(disk_path), "n": file_name, "m": mime,
            "sz": len(content_bytes), "h": file_hash,
            "pf": period_from, "pt": period_to, "sf": snapshot_for,
            "gb": "system",
            "ru": retention_until, "lb": legal_basis,
            "md": _aw_json.dumps(metadata or {}),
        })

    return {
        "id": doc_id, "file_path": str(disk_path), "file_hash": file_hash,
        "size": len(content_bytes), "retention_until": retention_until.isoformat(),
    }


@kita_router.post("/archive/snapshot/attendance")
async def archive_attendance_today(payload: dict = Body(default_factory=dict)):
    """On-demand: erzeugt PDF der Anwesenheitsliste + speichert im Archiv."""
    target_date_str = payload.get("date") or _aw_date.today().isoformat()
    target_date = _aw_date.fromisoformat(target_date_str)
    snapshot = await _aw_anwesenheit_for_date(target_date)

    # Einfaches HTML→PDF mittels reportlab (oder weasyprint)
    pdf_bytes = _aw_render_attendance_pdf(snapshot)
    result = _aw_archive_save(
        edition="kita", doc_type="attendance_list",
        target_id="all", content_bytes=pdf_bytes,
        file_name=f"attendance_{target_date.isoformat()}.pdf",
        snapshot_for=target_date,
        metadata={"sections": len(snapshot["sections"]),
                  "total_kids": sum(s["counts"]["kids_total"] for s in snapshot["sections"]),
                  "total_staff": sum(s["counts"]["staff_total"] for s in snapshot["sections"])},
        retention_years=7,
        legal_basis="KBBG · 7 Jahre Aufbewahrungspflicht",
    )
    return result


def _aw_render_attendance_pdf(snapshot: dict) -> bytes:
    """Rendert Anwesenheitsliste als simples PDF (reportlab)."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
    except ImportError:
        # Fallback: nur Text als PDF-ähnlicher Bytes-Stream
        return f"SHIKSHA · KITA Anwesenheitsliste {snapshot['date']}\n(reportlab nicht installiert)".encode()

    from io import BytesIO
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=1*cm, bottomMargin=1*cm,
                             leftMargin=1*cm, rightMargin=1*cm)
    styles = getSampleStyleSheet()
    story = []
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#ff4d8d"))
    story.append(Paragraph(f"SHIKSHA · KITA Anwesenheitsliste · {snapshot['date']}", title))
    story.append(Spacer(1, 0.3*cm))

    for section in snapshot["sections"]:
        section_title = ParagraphStyle("sec", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#2d7a5f"))
        story.append(Paragraph(f"{section['group_name']} · {section['counts']['kids_present']}/{section['counts']['kids_total']} Kinder · {section['counts']['staff_present']}/{section['counts']['staff_total']} Mitarbeiter", section_title))

        # Mitarbeiter
        if section["staff"]:
            staff_data = [["Mitarbeiter", "Rolle", "Bereiche", "Status"]]
            for s in section["staff"]:
                areas = ", ".join(sl["area"] for sl in s["slices"]) or "—"
                statuses = ", ".join(set(sl["status"] for sl in s["slices"])) or "—"
                staff_data.append([s["name"], s["role"], areas, statuses])
            t = Table(staff_data, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2d7a5f")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 9),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#e6e4de")),
                ("PADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.2*cm))

        # Kinder
        if section["children"]:
            kids_data = [["Kind", "Geb.-Jahr", "Bereiche", "Status"]]
            for c in section["children"]:
                areas = ", ".join(sl["area"] for sl in c["slices"]) or "—"
                statuses = ", ".join(set(sl["status"] for sl in c["slices"])) or "—"
                kids_data.append([c["name"], str(c["birth_year"] or "—"), areas, statuses])
            t = Table(kids_data, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#ffd93d")),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 9),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#e6e4de")),
                ("PADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.5*cm))

    # Footer mit Hash-Hinweis
    story.append(Spacer(1, 1*cm))
    footer = ParagraphStyle("footer", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#9a8e9e"))
    story.append(Paragraph(f"Generiert: {_aw_dt.now().isoformat()} · Manipulationsschutz: SHA-256 · SHIKSHA · DSGVO-konform · EU-Hosting", footer))

    doc.build(story)
    return buf.getvalue()


@kita_router.get("/archive/documents")
async def archive_list(edition: str = None, doc_type: str = None, limit: int = 100):
    sql = "SELECT id, edition, doc_type, target_id, file_name, file_size, file_hash, generated_at, retention_until, snapshot_for FROM shiksha_archive_documents WHERE 1=1"
    params = {"lim": limit}
    if edition:
        sql += " AND edition = :ed"; params["ed"] = edition
    if doc_type:
        sql += " AND doc_type = :dt"; params["dt"] = doc_type
    sql += " ORDER BY generated_at DESC LIMIT :lim"
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).fetchall()
    return {
        "count": len(rows),
        "documents": [
            {
                "id": r[0], "edition": r[1], "doc_type": r[2], "target_id": r[3],
                "file_name": r[4], "file_size": r[5], "file_hash_short": r[6][:16] if r[6] else None,
                "generated_at": r[7].isoformat() if r[7] else None,
                "retention_until": r[8].isoformat() if r[8] else None,
                "snapshot_for": r[9].isoformat() if r[9] else None,
            }
            for r in rows
        ],
    }


@kita_router.get("/archive/documents/{doc_id}/file")
async def archive_doc_file(doc_id: str):
    with engine.connect() as conn:
        r = conn.execute(sa.text(
            "SELECT file_path, file_name, file_mime, file_hash FROM shiksha_archive_documents WHERE id=:id"
        ), {"id": doc_id}).first()
        if not r:
            raise HTTPException(404, "Archiv-Dokument nicht gefunden")
        # Audit-Log
        conn.execute(sa.text("""
            INSERT INTO shiksha_archive_audit (id, archive_doc_id, action)
            VALUES (:id, :did, 'download')
        """), {"id": _new_id("audit"), "did": doc_id})
    fp = _aw_Path(r[0])
    if not fp.exists():
        raise HTTPException(404, "Datei auf Disk nicht gefunden")
    # Hash-Verifikation
    actual_hash = _aw_hash.sha256(fp.read_bytes()).hexdigest()
    if actual_hash != r[3]:
        with engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO shiksha_archive_audit (id, archive_doc_id, action, action_status)
                VALUES (:id, :did, 'hash_mismatch', 'tamper_detected')
            """), {"id": _new_id("audit"), "did": doc_id})
        raise HTTPException(500, "⚠ Tamper-Detection: Datei-Hash stimmt nicht mit DB überein!")
    return _aw_FileResponse(path=fp, media_type=r[2] or "application/pdf", filename=r[1])

# === CALENDAR-ROUTER ===
"""
SHIKSHA · KITA · Calendar-Router
Endpoints:
  GET  /kita/calendar/events?from=YYYY-MM-DD&to=YYYY-MM-DD&types=...
  POST /kita/calendar/events
  PATCH /kita/calendar/events/{id}
  DELETE /kita/calendar/events/{id}
  POST /kita/calendar/auto-birthdays    — generiert Geburtstage aus kita_legacy_children
  GET  /kita/calendar/event-types       — Liste der Typen + Default-Farben

Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.
Stand: 30.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

from datetime import date as _cal_date, timedelta as _cal_td


# Default-Farben pro Event-Typ (Holi-Palette)
EVENT_TYPE_COLORS = {
    "meeting":         "#a855f7",
    "birthday":        "#ffd93d",
    "closing":         "#a0391f",
    "event":           "#ff8c42",
    "training":        "#00d4d4",
    "celebration":     "#ff4d8d",
    "parent_meeting":  "#6dd47e",
    "vacation":        "#5ec5ff",
    "absence":         "#b8a8c4",
    "course":          "#ffb347",
    "other":           "#9a8e9e",
}

EVENT_TYPE_LABELS = {
    "meeting":         "Meeting",
    "birthday":        "Geburtstag 🎂",
    "closing":         "KITA geschlossen",
    "event":           "Veranstaltung",
    "training":        "Fortbildung",
    "celebration":     "Feier",
    "parent_meeting":  "Elterngespräch",
    "vacation":        "Urlaub",
    "absence":         "Abwesenheit",
    "course":          "Kurs",
    "other":           "Sonstiges",
}


@kita_router.get("/calendar/event-types")
async def calendar_event_types():
    return {
        "types": [
            {"key": k, "label": EVENT_TYPE_LABELS[k], "color": EVENT_TYPE_COLORS[k]}
            for k in EVENT_TYPE_COLORS
        ],
    }


@kita_router.get("/calendar/events")
async def calendar_events_in_range(
    from_date: str = None, to_date: str = None,
    types: str = None, audience: str = "traegerin",
):
    """Events im Zeitraum. Expandiert recurrence (yearly für Geburtstage)."""
    today = _cal_date.today()
    f = _cal_date.fromisoformat(from_date) if from_date else today.replace(day=1)
    t = _cal_date.fromisoformat(to_date) if to_date else f.replace(year=f.year + 1)

    type_list = [x.strip() for x in (types or "").split(",") if x.strip()]

    where = ["1=1"]
    params = {"f": f, "t": t}
    if type_list:
        where.append("event_type = ANY(:types)")
        params["types"] = type_list
    if audience == "paedagogin":
        where.append("visible_paedagogin = true")
    elif audience == "eltern":
        where.append("visible_eltern = true")
    elif audience == "traegerin":
        where.append("visible_traegerin = true")

    sql = f"""
    SELECT id, title, description, event_type,
           start_date, start_time, end_date, end_time, all_day,
           recurrence, recurrence_until, recurrence_weekdays,
           target_type, target_legacy_group_ids, target_legacy_staff_ids, target_legacy_child_ids,
           visible_traegerin, visible_paedagogin, visible_eltern,
           color, location, auto_source, created_by, created_at
    FROM kita_calendar_events
    WHERE {' AND '.join(where)}
    """

    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).fetchall()

    # Events expandieren (z.B. yearly Geburtstag — alle Jahre im Range)
    expanded = []
    for r in rows:
        event = {
            "id": r[0], "title": r[1], "description": r[2], "event_type": r[3],
            "start_date": r[4].isoformat() if r[4] else None,
            "start_time": str(r[5]) if r[5] else None,
            "end_date": r[6].isoformat() if r[6] else None,
            "end_time": str(r[7]) if r[7] else None,
            "all_day": r[8],
            "recurrence": r[9], "recurrence_until": r[10].isoformat() if r[10] else None,
            "recurrence_weekdays": list(r[11] or []),
            "target_type": r[12],
            "target_legacy_group_ids": list(r[13] or []),
            "target_legacy_staff_ids": list(r[14] or []),
            "target_legacy_child_ids": list(r[15] or []),
            "visible_traegerin": r[16], "visible_paedagogin": r[17], "visible_eltern": r[18],
            "color": r[19] or EVENT_TYPE_COLORS.get(r[3], "#888"),
            "color_default": EVENT_TYPE_COLORS.get(r[3], "#888"),
            "label": EVENT_TYPE_LABELS.get(r[3], r[3]),
            "location": r[20], "auto_source": r[21],
            "created_by": r[22],
        }
        # Wenn Range-Filter relevant: wenn Event nicht in Range, expandiere recurrence
        if event["recurrence"] == "yearly" and r[4]:
            # Zeige Geburtstag in jedem Jahr im Range
            base = r[4]
            year = f.year
            while year <= t.year:
                try:
                    new_date = base.replace(year=year)
                    if f <= new_date <= t:
                        ev_copy = dict(event)
                        ev_copy["start_date"] = new_date.isoformat()
                        ev_copy["end_date"] = new_date.isoformat()
                        ev_copy["display_year"] = year
                        ev_copy["age_at_event"] = year - base.year if base.year < year else None
                        expanded.append(ev_copy)
                except ValueError:
                    pass  # 29.02. in Nicht-Schaltjahr
                year += 1
        else:
            # Nicht-rekurrent oder andere Rekurrenz: nur wenn im Range
            sd = r[4]
            ed = r[6] or sd
            if sd and ed and sd <= t and ed >= f:
                expanded.append(event)

    expanded.sort(key=lambda e: (e["start_date"] or "", e.get("start_time") or ""))
    return {"count": len(expanded), "events": expanded, "range": {"from": f.isoformat(), "to": t.isoformat()}}


@kita_router.post("/calendar/events")
async def calendar_event_create(payload: dict = Body(...)):
    title = payload.get("title")
    if not title:
        raise HTTPException(400, "title Pflicht")
    eid = _new_id("ev")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_calendar_events
              (id, title, description, event_type,
               start_date, start_time, end_date, end_time, all_day,
               recurrence, recurrence_until, recurrence_weekdays,
               target_type, target_legacy_group_ids, target_legacy_staff_ids, target_legacy_child_ids,
               visible_traegerin, visible_paedagogin, visible_eltern,
               color, location, created_by)
            VALUES (:id, :t, :d, :et,
                    :sd, :st_, :ed, :et_, :ad,
                    :r, :ru, :rw,
                    :tt, :tg, :ts, :tc,
                    :vt, :vp, :ve,
                    :c, :l, :cb)
        """), {
            "id": eid, "t": title, "d": payload.get("description"),
            "et": payload.get("event_type", "meeting"),
            "sd": payload.get("start_date"),
            "st_": payload.get("start_time"),
            "ed": payload.get("end_date"),
            "et_": payload.get("end_time"),
            "ad": bool(payload.get("all_day", False)),
            "r": payload.get("recurrence", "none"),
            "ru": payload.get("recurrence_until"),
            "rw": payload.get("recurrence_weekdays", []),
            "tt": payload.get("target_type", "all"),
            "tg": payload.get("target_legacy_group_ids", []),
            "ts": payload.get("target_legacy_staff_ids", []),
            "tc": payload.get("target_legacy_child_ids", []),
            "vt": bool(payload.get("visible_traegerin", True)),
            "vp": bool(payload.get("visible_paedagogin", True)),
            "ve": bool(payload.get("visible_eltern", False)),
            "c": payload.get("color"),
            "l": payload.get("location"),
            "cb": payload.get("created_by", "system"),
        })
    return {"id": eid, "title": title}


@kita_router.patch("/calendar/events/{eid}")
async def calendar_event_update(eid: str, payload: dict = Body(...)):
    fields = {}
    for k in ("title","description","event_type","start_date","start_time","end_date","end_time",
              "all_day","recurrence","recurrence_until","recurrence_weekdays",
              "target_type","target_legacy_group_ids","target_legacy_staff_ids","target_legacy_child_ids",
              "visible_traegerin","visible_paedagogin","visible_eltern",
              "color","location"):
        if k in payload:
            fields[k] = payload[k]
    if not fields:
        raise HTTPException(400, "keine Felder")
    set_parts = [f"{k} = :{k}" for k in fields]
    set_parts.append("updated_at = NOW()")
    sql = f"UPDATE kita_calendar_events SET {', '.join(set_parts)} WHERE id = :id"
    fields["id"] = eid
    with engine.begin() as conn:
        result = conn.execute(sa.text(sql), fields)
        if result.rowcount == 0:
            raise HTTPException(404, "Event nicht gefunden")
    return {"id": eid, "updated": list(fields.keys())}


@kita_router.delete("/calendar/events/{eid}")
async def calendar_event_delete(eid: str):
    with engine.begin() as conn:
        result = conn.execute(sa.text("DELETE FROM kita_calendar_events WHERE id = :id"), {"id": eid})
        if result.rowcount == 0:
            raise HTTPException(404, "Event nicht gefunden")
    return {"id": eid, "deleted": True}


@kita_router.post("/calendar/auto-birthdays")
async def calendar_auto_birthdays():
    """
    Generiert für jedes aktive Kind ein yearly-recurring Geburtstag-Event.
    Idempotent: bestehende Auto-Birthdays werden übersprungen.
    """
    today = _cal_date.today()
    created = 0
    with engine.connect() as conn:
        children = conn.execute(sa.text("""
            SELECT id, name, birth_year FROM kita_legacy_children WHERE active = true
        """)).fetchall()

    # Wir nehmen für Geburtstag den 1. Januar des Geburtsjahres als Default,
    # weil wir nur birth_year haben, nicht das exakte Datum.
    # Für echtes Datum: später Feld birth_date hinzufügen.
    with engine.begin() as conn:
        for c in children:
            cid, name, birth_year = c
            if not birth_year:
                continue
            # Idempotent: prüfen ob schon vorhanden
            existing = conn.execute(sa.text("""
                SELECT id FROM kita_calendar_events
                WHERE auto_source = 'birthday_from_child' AND auto_source_id = :cid
            """), {"cid": str(cid)}).first()
            if existing:
                continue
            event_id = _new_id("ev")
            # Default: 1. Januar (User soll es manuell anpassen)
            base_date = _cal_date(birth_year, 1, 1)
            conn.execute(sa.text("""
                INSERT INTO kita_calendar_events
                  (id, title, event_type, start_date, all_day, recurrence,
                   target_type, target_legacy_child_ids,
                   visible_traegerin, visible_paedagogin, visible_eltern,
                   auto_source, auto_source_id, created_by)
                VALUES (:id, :t, 'birthday', :sd, true, 'yearly',
                        'child', ARRAY[:cid],
                        true, true, true,
                        'birthday_from_child', :csid, 'system')
            """), {
                "id": event_id,
                "t": f"🎂 Geburtstag {name}",
                "sd": base_date,
                "cid": cid, "csid": str(cid),
            })
            created += 1

    return {
        "created": created,
        "total_children": len(children),
        "note": "Defaultdatum 1. Januar — bitte echtes Datum manuell setzen via PATCH",
    }

# === PERSONEN-ROUTER ===
"""
SHIKSHA · KITA · Personen-Stammdaten Router
Endpoints:
  GET    /kita/staff                  — Liste aller Mitarbeiter
  POST   /kita/staff                  — anlegen
  GET    /kita/staff/{id}             — Detail
  PATCH  /kita/staff/{id}             — bearbeiten
  DELETE /kita/staff/{id}             — soft-delete (active=false)
  GET    /kita/children               — Liste aller Kinder
  POST   /kita/children               — anlegen
  GET    /kita/children/{id}          — Detail
  PATCH  /kita/children/{id}          — bearbeiten
  DELETE /kita/children/{id}          — soft-delete
  POST   /kita/children/{id}/sync-birthday  — manuelle Re-Sync des Geburtstag-Events

Side-Effects:
  - Anlegen/Bearbeiten/Löschen eines Kindes synct automatisch das
    Geburtstag-Event in kita_calendar_events (idempotent).
  - Mitarbeiter:innen-Geburtstage genauso (visible_paedagogin = true).

Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.
Stand: 01.05.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import json as _pers_json


def _sync_birthday_event(conn, person_type, person_id, name, birth_date, active):
    """
    Idempotenter Birthday-Sync:
    - Existiert kein Event → anlegen (wenn aktiv + birth_date)
    - Existiert Event → updaten (Datum/Titel) bzw. löschen wenn inaktiv/kein Datum
    """
    auto_source = f"birthday_from_{person_type}"  # 'birthday_from_child' / 'birthday_from_staff'
    existing = conn.execute(sa.text("""
        SELECT id FROM kita_calendar_events
        WHERE auto_source = :src AND auto_source_id = :pid
    """), {"src": auto_source, "pid": str(person_id)}).first()

    if not active or not birth_date:
        if existing:
            conn.execute(sa.text("DELETE FROM kita_calendar_events WHERE id = :id"),
                         {"id": existing[0]})
        return None

    emoji_title = "🎂 Geburtstag " + name
    target_field = "target_legacy_child_ids" if person_type == "child" else "target_legacy_staff_ids"
    target_type = "child" if person_type == "child" else "staff"

    if existing:
        conn.execute(sa.text(f"""
            UPDATE kita_calendar_events
            SET title = :t, start_date = :sd, updated_at = NOW(),
                {target_field} = ARRAY[:pid]::INTEGER[],
                target_type = :tt
            WHERE id = :id
        """), {"t": emoji_title, "sd": birth_date, "id": existing[0],
               "pid": int(person_id), "tt": target_type})
        return existing[0]
    else:
        new_id = _new_id("ev")
        conn.execute(sa.text(f"""
            INSERT INTO kita_calendar_events
              (id, title, event_type, start_date, all_day, recurrence,
               target_type, {target_field},
               visible_traegerin, visible_paedagogin, visible_eltern,
               auto_source, auto_source_id, created_by)
            VALUES (:id, :t, 'birthday', :sd, true, 'yearly',
                    :tt, ARRAY[:pid]::INTEGER[],
                    true, true, :ve,
                    :src, :sid, 'system')
        """), {"id": new_id, "t": emoji_title, "sd": birth_date,
               "tt": target_type, "pid": int(person_id),
               "ve": (person_type == "child"),  # Eltern sehen nur Kinder-Geb.
               "src": auto_source, "sid": str(person_id)})
        return new_id


# ============================================================
# MITARBEITER:INNEN
# ============================================================

@kita_router.get("/staff")
async def staff_list(active_only: bool = True):
    sql = "SELECT * FROM kita_legacy_staff"
    if active_only:
        sql += " WHERE active = true"
    sql += " ORDER BY name"
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql)).mappings().fetchall()
    return {"count": len(rows), "staff": [dict(r) for r in rows]}


@kita_router.get("/staff/{sid}")
async def staff_detail(sid: int):
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT * FROM kita_legacy_staff WHERE id = :id"),
                           {"id": sid}).mappings().first()
    if not row:
        raise HTTPException(404, "Mitarbeiter:in nicht gefunden")
    return dict(row)


@kita_router.post("/staff")
async def staff_create(payload: dict = Body(...)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name Pflicht")
    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            INSERT INTO kita_legacy_staff
              (name, role, weekly_hours, birth_date, email, phone, address,
               emergency_contact, employment_start, employment_end, contract_type,
               qualification, notes, active)
            VALUES (:n, :r, :wh, :bd, :em, :ph, :ad,
                    :ec, :es, :ee, :ct, :q, :no, true)
            RETURNING id
        """), {
            "n": name, "r": payload.get("role", "educator"),
            "wh": payload.get("weekly_hours") or 0,
            "bd": payload.get("birth_date"),
            "em": payload.get("email"), "ph": payload.get("phone"),
            "ad": payload.get("address"), "ec": payload.get("emergency_contact"),
            "es": payload.get("employment_start"), "ee": payload.get("employment_end"),
            "ct": payload.get("contract_type"), "q": payload.get("qualification"),
            "no": payload.get("notes"),
        })
        new_id = result.scalar()
        # Birthday-Sync
        if payload.get("birth_date"):
            _sync_birthday_event(conn, "staff", new_id, name, payload["birth_date"], True)
    return {"id": new_id, "name": name}


@kita_router.patch("/staff/{sid}")
async def staff_update(sid: int, payload: dict = Body(...)):
    allowed = ("name","role","weekly_hours","birth_date","email","phone","address",
               "emergency_contact","employment_start","employment_end","contract_type",
               "qualification","notes","active")
    fields = {k: payload[k] for k in allowed if k in payload}
    if not fields:
        raise HTTPException(400, "keine Felder")
    set_parts = [f"{k} = :{k}" for k in fields]
    set_parts.append("updated_at = NOW()")
    sql = f"UPDATE kita_legacy_staff SET {', '.join(set_parts)} WHERE id = :id RETURNING name, birth_date, active"
    fields["id"] = sid
    with engine.begin() as conn:
        row = conn.execute(sa.text(sql), fields).first()
        if not row:
            raise HTTPException(404, "Mitarbeiter:in nicht gefunden")
        # Birthday-Sync (immer durchziehen — _sync entscheidet)
        _sync_birthday_event(conn, "staff", sid, row[0], row[1], row[2])
    return {"id": sid, "updated": list(fields.keys())}


@kita_router.delete("/staff/{sid}")
async def staff_delete(sid: int, hard: bool = False):
    with engine.begin() as conn:
        if hard:
            conn.execute(sa.text("DELETE FROM kita_calendar_events WHERE auto_source='birthday_from_staff' AND auto_source_id=:p"),
                         {"p": str(sid)})
            r = conn.execute(sa.text("DELETE FROM kita_legacy_staff WHERE id = :id"), {"id": sid})
        else:
            r = conn.execute(sa.text("UPDATE kita_legacy_staff SET active=false, updated_at=NOW() WHERE id = :id RETURNING name, birth_date"),
                             {"id": sid})
            row = r.first()
            if row:
                _sync_birthday_event(conn, "staff", sid, row[0], row[1], False)
        if r.rowcount == 0:
            raise HTTPException(404, "Mitarbeiter:in nicht gefunden")
    return {"id": sid, "deleted": True, "hard": hard}


# ============================================================
# KINDER
# ============================================================

@kita_router.get("/children")
async def children_list(active_only: bool = True):
    sql = "SELECT * FROM kita_legacy_children"
    if active_only:
        sql += " WHERE active = true"
    sql += " ORDER BY name"
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql)).mappings().fetchall()
    return {"count": len(rows), "children": [dict(r) for r in rows]}


@kita_router.get("/children/{cid}")
async def children_detail(cid: int):
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT * FROM kita_legacy_children WHERE id = :id"),
                           {"id": cid}).mappings().first()
    if not row:
        raise HTTPException(404, "Kind nicht gefunden")
    return dict(row)


@kita_router.post("/children")
async def children_create(payload: dict = Body(...)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name Pflicht")
    birth_date = payload.get("birth_date")
    birth_year = payload.get("birth_year")
    if birth_date and not birth_year:
        # auto-derivate
        try:
            birth_year = int(birth_date[:4])
        except Exception:
            pass
    parents_json = _pers_json.dumps(payload.get("parents") or [])
    pickup_json = _pers_json.dumps(payload.get("pickup_authorized") or [])

    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            INSERT INTO kita_legacy_children
              (name, birth_year, birth_date, gender, address, nationality,
               native_language, allergies, medications, medical_notes, dietary_notes,
               entry_date, exit_date, parents, pickup_authorized,
               emergency_contact, notes, photo_consent, active)
            VALUES (:n, :by, :bd, :g, :ad, :nat,
                    :lang, :al, :med, :mn, :dn,
                    :ed, :xd, CAST(:par AS jsonb), CAST(:pk AS jsonb),
                    :ec, :no, :pc, true)
            RETURNING id
        """), {
            "n": name, "by": birth_year, "bd": birth_date,
            "g": payload.get("gender"), "ad": payload.get("address"),
            "nat": payload.get("nationality"), "lang": payload.get("native_language"),
            "al": payload.get("allergies"), "med": payload.get("medications"),
            "mn": payload.get("medical_notes"), "dn": payload.get("dietary_notes"),
            "ed": payload.get("entry_date"), "xd": payload.get("exit_date"),
            "par": parents_json, "pk": pickup_json,
            "ec": payload.get("emergency_contact"), "no": payload.get("notes"),
            "pc": bool(payload.get("photo_consent", False)),
        })
        new_id = result.scalar()
        if birth_date:
            _sync_birthday_event(conn, "child", new_id, name, birth_date, True)
    return {"id": new_id, "name": name}


@kita_router.patch("/children/{cid}")
async def children_update(cid: int, payload: dict = Body(...)):
    # JSONB-Felder gesondert behandeln
    json_cols = {"parents", "pickup_authorized"}
    plain_cols = ("name","birth_year","birth_date","gender","address","nationality",
                  "native_language","allergies","medications","medical_notes","dietary_notes",
                  "entry_date","exit_date","emergency_contact","notes","photo_consent","active")

    fields = {}
    set_parts = []
    for k in plain_cols:
        if k in payload:
            fields[k] = payload[k]
            set_parts.append(f"{k} = :{k}")
    for k in json_cols:
        if k in payload:
            fields[k] = _pers_json.dumps(payload[k] or [])
            set_parts.append(f"{k} = CAST(:{k} AS jsonb)")
    if not set_parts:
        raise HTTPException(400, "keine Felder")

    # birth_year aus birth_date ableiten falls fehlt
    if "birth_date" in fields and "birth_year" not in fields and fields["birth_date"]:
        try:
            fields["birth_year"] = int(str(fields["birth_date"])[:4])
            set_parts.append("birth_year = :birth_year")
        except Exception:
            pass

    set_parts.append("updated_at = NOW()")
    fields["id"] = cid
    sql = f"UPDATE kita_legacy_children SET {', '.join(set_parts)} WHERE id = :id RETURNING name, birth_date, active"

    with engine.begin() as conn:
        row = conn.execute(sa.text(sql), fields).first()
        if not row:
            raise HTTPException(404, "Kind nicht gefunden")
        _sync_birthday_event(conn, "child", cid, row[0], row[1], row[2])
    return {"id": cid, "updated": [k for k in fields if k != "id"]}


@kita_router.delete("/children/{cid}")
async def children_delete(cid: int, hard: bool = False):
    with engine.begin() as conn:
        if hard:
            conn.execute(sa.text("DELETE FROM kita_calendar_events WHERE auto_source='birthday_from_child' AND auto_source_id=:p"),
                         {"p": str(cid)})
            r = conn.execute(sa.text("DELETE FROM kita_legacy_children WHERE id = :id"), {"id": cid})
        else:
            r = conn.execute(sa.text("UPDATE kita_legacy_children SET active=false, updated_at=NOW() WHERE id = :id RETURNING name, birth_date"),
                             {"id": cid})
            row = r.first()
            if row:
                _sync_birthday_event(conn, "child", cid, row[0], row[1], False)
        if r.rowcount == 0:
            raise HTTPException(404, "Kind nicht gefunden")
    return {"id": cid, "deleted": True, "hard": hard}


@kita_router.post("/children/{cid}/sync-birthday")
async def children_sync_birthday(cid: int):
    with engine.begin() as conn:
        row = conn.execute(sa.text("SELECT name, birth_date, active FROM kita_legacy_children WHERE id = :id"),
                           {"id": cid}).first()
        if not row:
            raise HTTPException(404, "Kind nicht gefunden")
        eid = _sync_birthday_event(conn, "child", cid, row[0], row[1], row[2])
    return {"event_id": eid, "synced": True}

# === PUSH-ROUTER ===
"""
SHIKSHA · Web-Push-Router
Endpoints:
  GET  /push/vapid-public-key         — Public-Key fürs Frontend
  POST /push/subscribe                — Browser-Subscription speichern
  POST /push/unsubscribe              — Subscription löschen
  POST /push/send                     — Notification an Audience senden (Trägerin)
  GET  /push/log                      — Send-Log

Voraussetzungen (im venv):
  pip install pywebpush

Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.
"""

import os as _push_os
import json as _push_json
from pywebpush import webpush, WebPushException

VAPID_PRIVATE_KEY = _push_os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = _push_os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT     = _push_os.environ.get("VAPID_SUBJECT", "mailto:thomas@shiksha.tun.zone")


@kita_router.get("/push/vapid-public-key")
async def push_get_vapid_pub():
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(503, "VAPID_PUBLIC_KEY nicht gesetzt")
    return {"public_key": VAPID_PUBLIC_KEY}


@kita_router.post("/push/subscribe")
async def push_subscribe(payload: dict = Body(...)):
    """
    Erwartet:
      {
        "audience": "paedagogin" | "eltern" | "traegerin",
        "person_type": "staff" | "parent" | "system",
        "person_id": "...",          // optional
        "subscription": {
            "endpoint": "...",
            "keys": {"p256dh": "...", "auth": "..."}
        },
        "user_agent": "..."
      }
    """
    sub = payload.get("subscription") or {}
    keys = sub.get("keys") or {}
    endpoint = sub.get("endpoint")
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise HTTPException(400, "Subscription unvollständig")

    audience = payload.get("audience") or "traegerin"
    with engine.begin() as conn:
        # Upsert
        existing = conn.execute(sa.text("SELECT id FROM push_subscriptions WHERE endpoint = :e"),
                                {"e": endpoint}).first()
        if existing:
            conn.execute(sa.text("""
                UPDATE push_subscriptions
                   SET p256dh_key = :p, auth_key = :a, audience = :au,
                       person_type = :pt, person_id = :pid,
                       user_agent = :ua, active = true, last_used_at = NOW()
                 WHERE id = :id
            """), {"p": keys["p256dh"], "a": keys["auth"], "au": audience,
                   "pt": payload.get("person_type"), "pid": str(payload.get("person_id") or ""),
                   "ua": payload.get("user_agent"), "id": existing[0]})
            return {"id": existing[0], "updated": True}
        result = conn.execute(sa.text("""
            INSERT INTO push_subscriptions
              (audience, person_type, person_id, endpoint, p256dh_key, auth_key, user_agent)
            VALUES (:au, :pt, :pid, :e, :p, :a, :ua)
            RETURNING id
        """), {"au": audience, "pt": payload.get("person_type"),
               "pid": str(payload.get("person_id") or ""),
               "e": endpoint, "p": keys["p256dh"], "a": keys["auth"],
               "ua": payload.get("user_agent")})
    return {"id": result.scalar(), "created": True}


@kita_router.post("/push/unsubscribe")
async def push_unsubscribe(payload: dict = Body(...)):
    endpoint = payload.get("endpoint")
    if not endpoint:
        raise HTTPException(400, "endpoint fehlt")
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE push_subscriptions SET active = false WHERE endpoint = :e"),
                     {"e": endpoint})
    return {"ok": True}


def _push_send_one(sub_row, payload):
    """Sende an eine Subscription. Returnt (ok, error_msg)."""
    try:
        webpush(
            subscription_info={
                "endpoint": sub_row["endpoint"],
                "keys": {"p256dh": sub_row["p256dh_key"], "auth": sub_row["auth_key"]},
            },
            data=_push_json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True, None
    except WebPushException as e:
        # 410 Gone → Subscription abgelaufen → deaktivieren
        return False, str(e)


@kita_router.post("/push/send")
async def push_send(payload: dict = Body(...)):
    """
    Sendet eine Notification.
      {
        "audience": "paedagogin" | "eltern" | "traegerin" | "all",
        "person_id": "..."           // optional, gezielt einzelne Person
        "title": "...",
        "body":  "...",
        "url":   "/accounting/ui/paedagogen/app",   // Click-Ziel
        "icon":  "...",                              // optional
        "tag":   "termin-erinnerung"                 // optional, gruppiert auf iOS
      }
    """
    if not VAPID_PRIVATE_KEY:
        raise HTTPException(503, "VAPID_PRIVATE_KEY nicht gesetzt")
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title Pflicht")

    audience = payload.get("audience") or "all"
    person_id = payload.get("person_id")
    notif_payload = {
        "title": title,
        "body": payload.get("body") or "",
        "url": payload.get("url") or "/",
        "icon": payload.get("icon") or "/accounting/ui/kita/app-icon.svg",
        "tag": payload.get("tag") or "shiksha",
    }

    where = ["active = true"]
    params = {}
    if audience != "all":
        where.append("audience = :au")
        params["au"] = audience
    if person_id:
        where.append("person_id = :pid")
        params["pid"] = str(person_id)

    sql = f"SELECT id, endpoint, p256dh_key, auth_key FROM push_subscriptions WHERE {' AND '.join(where)}"
    sent, failed = 0, 0
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).mappings().fetchall()

    for row in rows:
        ok, err = _push_send_one(row, notif_payload)
        if ok:
            sent += 1
            with engine.begin() as conn:
                conn.execute(sa.text("UPDATE push_subscriptions SET last_used_at = NOW(), last_error = NULL WHERE id = :id"),
                             {"id": row["id"]})
        else:
            failed += 1
            with engine.begin() as conn:
                # Bei 410 Gone direkt deaktivieren
                if "410" in (err or "") or "404" in (err or ""):
                    conn.execute(sa.text("UPDATE push_subscriptions SET active = false, last_error = :e WHERE id = :id"),
                                 {"e": err[:500], "id": row["id"]})
                else:
                    conn.execute(sa.text("UPDATE push_subscriptions SET last_error = :e WHERE id = :id"),
                                 {"e": err[:500], "id": row["id"]})

    # Log
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO push_send_log
              (audience_filter, title, body, url, sent_count, failed_count, sender)
            VALUES (:af, :t, :b, :u, :sc, :fc, :sd)
        """), {"af": audience, "t": title, "b": notif_payload["body"],
               "u": notif_payload["url"], "sc": sent, "fc": failed,
               "sd": payload.get("sender", "system")})

    return {"sent": sent, "failed": failed, "total": len(rows)}


@kita_router.get("/push/log")
async def push_log(limit: int = 50):
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT * FROM push_send_log ORDER BY sent_at DESC LIMIT :l
        """), {"l": limit}).mappings().fetchall()
    return {"count": len(rows), "log": [dict(r) for r in rows]}


# === DASHBOARD-ROUTER ===
"""
SHIKSHA · Dashboard-Router
Layout-Persistierung + Card-Daten-Endpoints.

Endpoints:
  GET  /kita/dashboard/layout?key=traegerin           — Layout laden (X-User-ID Header)
  PUT  /kita/dashboard/layout                         — Layout speichern
  GET  /kita/dashboard/card/anwesenheit-summary       — {present, total, paedagogin_count}
  GET  /kita/dashboard/card/birthdays-week            — diese Woche Geburtstage
  GET  /kita/dashboard/card/upcoming-events           — nächste 14 Tage
  GET  /kita/dashboard/card/messages-recent           — letzte 5 Mitteilungen
  GET  /kita/dashboard/card/compliance-status         — VBZ/ST/Audit-Ampel
  GET  /kita/dashboard/card/spotlight/{type}/{id}     — Person/Kind im Detail

Anhängen an /opt/shiksha/kita_compliance_router.py.
"""

import json as _dash_json
from datetime import date as _dash_date, timedelta as _dash_td

# ============================================================
# DEFAULT-LAYOUT (Trägerin)
# ============================================================
_DEFAULT_TRAEGERIN_LAYOUT = [
    # Hero: SHIKSHA-Begrüßung — der Tag beginnt mit Persönlichkeit
    {"id": "greeting",   "x": 0, "y": 0, "w": 12, "h": 4, "type": "shiksha-greeting",
     "config": {"role": "traegerin"}},

    # Mini-Stats-Row + runde Buttons
    {"id": "anw-mini",   "x": 0, "y": 4, "w": 3, "h": 2, "type": "anwesenheit-mini"},
    {"id": "st-mini",    "x": 3, "y": 4, "w": 3, "h": 2, "type": "stprozent-mini"},
    {"id": "act-pers",   "x": 6, "y": 4, "w": 2, "h": 2, "type": "action-round",
     "config": {"label": "Personen", "icon": "👥", "url": "/accounting/ui/kita/personen", "color": "pink"}},
    {"id": "act-cal",    "x": 8, "y": 4, "w": 2, "h": 2, "type": "action-round",
     "config": {"label": "Kalender", "icon": "📅", "url": "/accounting/ui/kita/calendar", "color": "purple"}},
    {"id": "act-push",   "x": 10, "y": 4, "w": 2, "h": 2, "type": "action-round",
     "config": {"label": "Push", "icon": "📣", "url": "/accounting/ui/kita/push", "color": "turquoise"}},

    # Compliance-Mini
    {"id": "comp-mini",  "x": 0, "y": 6, "w": 3, "h": 2, "type": "compliance-mini"},

    # Mid: Live-Anwesenheit + Termine
    {"id": "anw-live",   "x": 0, "y": 8, "w": 6, "h": 4, "type": "anwesenheit-live"},
    {"id": "ev-up",      "x": 6, "y": 8, "w": 6, "h": 4, "type": "events-upcoming"},

    # Geburtstag-Hero
    {"id": "bday-hero",  "x": 0, "y": 12, "w": 12, "h": 3, "type": "birthday-hero"},

    # Footer
    {"id": "msg-rec",    "x": 0, "y": 15, "w": 6, "h": 4, "type": "messages-recent"},
    {"id": "comp-stat",  "x": 6, "y": 15, "w": 6, "h": 4, "type": "compliance-status"},
]

_DEFAULT_PAEDAGOGIN_LAYOUT = [
    {"id": "greeting",  "x": 0, "y": 0,  "w": 12, "h": 4, "type": "shiksha-greeting",
     "config": {"role": "paedagogin"}},
    {"id": "anw-live",  "x": 0, "y": 4,  "w": 12, "h": 4, "type": "anwesenheit-live"},
    {"id": "ev-up",     "x": 0, "y": 8,  "w": 6,  "h": 4, "type": "events-upcoming"},
    {"id": "bday-hero", "x": 6, "y": 8,  "w": 6,  "h": 4, "type": "birthday-hero"},
    {"id": "msg-rec",   "x": 0, "y": 12, "w": 12, "h": 3, "type": "messages-recent"},
]


def _default_layout(key):
    if key == "paedagogin":
        return _DEFAULT_PAEDAGOGIN_LAYOUT
    return _DEFAULT_TRAEGERIN_LAYOUT


# ============================================================
# LAYOUT GET / PUT
# ============================================================

@kita_router.get("/dashboard/layout")
async def dashboard_layout_get(
    key: str = "traegerin",
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    with engine.connect() as conn:
        row = conn.execute(sa.text("""
            SELECT layout, edit_mode FROM dashboard_layouts
            WHERE user_id = :uid AND dashboard_key = :dk
        """), {"uid": user_id, "dk": key}).first()
    if not row:
        return {"layout": _default_layout(key), "is_default": True, "edit_mode": False}
    return {"layout": row[0], "is_default": False, "edit_mode": bool(row[1])}


@kita_router.put("/dashboard/layout")
async def dashboard_layout_put(
    payload: dict = Body(...),
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    key = payload.get("key", "traegerin")
    layout = payload.get("layout", [])
    edit_mode = bool(payload.get("edit_mode", False))
    layout_json = _dash_json.dumps(layout)
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO dashboard_layouts (user_id, dashboard_key, layout, edit_mode)
            VALUES (:uid, :dk, CAST(:l AS jsonb), :em)
            ON CONFLICT (user_id, dashboard_key)
            DO UPDATE SET layout = CAST(:l AS jsonb),
                          edit_mode = :em,
                          updated_at = NOW()
        """), {"uid": user_id, "dk": key, "l": layout_json, "em": edit_mode})
    return {"ok": True, "saved": len(layout)}


@kita_router.post("/dashboard/layout/reset")
async def dashboard_layout_reset(
    payload: dict = Body(default={}),
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    key = payload.get("key", "traegerin")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            DELETE FROM dashboard_layouts WHERE user_id = :uid AND dashboard_key = :dk
        """), {"uid": user_id, "dk": key})
    return {"ok": True, "layout": _default_layout(key)}


# ============================================================
# CARD-DATEN-ENDPOINTS
# ============================================================

@kita_router.get("/dashboard/card/anwesenheit-summary")
async def card_anwesenheit_summary():
    today = _dash_date.today()
    with engine.connect() as conn:
        # Kinder gesamt + heute anwesend (per kita_daily_assignments)
        kids_total = conn.execute(sa.text("SELECT COUNT(*) FROM kita_legacy_children WHERE active = true")).scalar() or 0
        try:
            kids_present = conn.execute(sa.text("""
                SELECT COUNT(DISTINCT legacy_child_id) FROM kita_daily_assignments
                WHERE work_date = :d AND status = 'present' AND person_type = 'child'
            """), {"d": today}).scalar() or 0
        except Exception:
            kids_present = 0
        staff_total = conn.execute(sa.text("SELECT COUNT(*) FROM kita_legacy_staff WHERE active = true")).scalar() or 0
        try:
            staff_present = conn.execute(sa.text("""
                SELECT COUNT(DISTINCT legacy_staff_id) FROM kita_daily_assignments
                WHERE work_date = :d AND status = 'present' AND person_type = 'staff'
            """), {"d": today}).scalar() or 0
        except Exception:
            staff_present = 0
    return {
        "kids": {"present": int(kids_present), "total": int(kids_total)},
        "staff": {"present": int(staff_present), "total": int(staff_total)},
        "date": today.isoformat(),
    }


@kita_router.get("/dashboard/card/birthdays-week")
async def card_birthdays_week():
    today = _dash_date.today()
    end = today + _dash_td(days=7)
    out = []
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, name, birth_date, 'child' as type FROM kita_legacy_children
            WHERE active = true AND birth_date IS NOT NULL
            UNION ALL
            SELECT id, name, birth_date, 'staff' as type FROM kita_legacy_staff
            WHERE active = true AND birth_date IS NOT NULL
        """)).mappings().fetchall()
    for r in rows:
        bd = r["birth_date"]
        try:
            this_year = bd.replace(year=today.year)
        except ValueError:
            continue
        if today <= this_year <= end:
            age = today.year - bd.year
            out.append({
                "id": r["id"], "name": r["name"], "type": r["type"],
                "date": this_year.isoformat(), "age_turning": age,
                "is_today": this_year == today,
            })
    out.sort(key=lambda x: x["date"])
    return {"birthdays": out, "range": {"from": today.isoformat(), "to": end.isoformat()}}


@kita_router.get("/dashboard/card/upcoming-events")
async def card_upcoming_events(days: int = 14):
    today = _dash_date.today()
    end = today + _dash_td(days=days)
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, title, event_type, start_date, start_time, location, color
            FROM kita_calendar_events
            WHERE start_date BETWEEN :a AND :b
              AND visible_traegerin = true
            ORDER BY start_date, start_time
            LIMIT 20
        """), {"a": today, "b": end}).mappings().fetchall()
    events = []
    for r in rows:
        d = dict(r)
        if d.get("start_date"): d["start_date"] = d["start_date"].isoformat()
        if d.get("start_time"): d["start_time"] = str(d["start_time"])
        # Default-Farbe nachziehen
        if not d.get("color"):
            d["color"] = EVENT_TYPE_COLORS.get(d.get("event_type"), "#888")
        events.append(d)
    return {"events": events, "count": len(events)}


@kita_router.get("/dashboard/card/messages-recent")
async def card_messages_recent(limit: int = 5):
    try:
        with engine.connect() as conn:
            rows = conn.execute(sa.text("""
                SELECT id, title, body, audience, created_at
                FROM kita_notifications
                ORDER BY created_at DESC LIMIT :l
            """), {"l": limit}).mappings().fetchall()
        return {"messages": [
            {**dict(r), "created_at": r["created_at"].isoformat() if r.get("created_at") else None}
            for r in rows
        ]}
    except Exception:
        return {"messages": []}


@kita_router.get("/dashboard/card/compliance-status")
async def card_compliance_status():
    """Liefert Ampel-Status für ST%, VBZ, Audit."""
    out = {"st_prozent": "ok", "vbz": "ok", "audit": "ok", "details": {}}
    try:
        with engine.connect() as conn:
            # ST% — ist eine Spalte in kita_audit_runs / kita_compliance, je nach DB-Version
            try:
                row = conn.execute(sa.text("""
                    SELECT * FROM kita_st_prozent_calculations
                    ORDER BY calculation_date DESC LIMIT 1
                """)).mappings().first()
                if row:
                    fulfilled = float(row.get("st_prozent_actual") or 0) >= float(row.get("st_prozent_required") or 100)
                    out["st_prozent"] = "ok" if fulfilled else "warn"
                    out["details"]["st_prozent"] = {
                        "actual": float(row.get("st_prozent_actual") or 0),
                        "required": float(row.get("st_prozent_required") or 0),
                    }
            except Exception:
                out["st_prozent"] = "unknown"

            # Audits — letzter Audit-Run
            try:
                row = conn.execute(sa.text("""
                    SELECT findings_count, run_at FROM kita_audit_runs
                    ORDER BY run_at DESC LIMIT 1
                """)).mappings().first()
                if row:
                    cnt = int(row.get("findings_count") or 0)
                    out["audit"] = "ok" if cnt == 0 else ("warn" if cnt < 5 else "alert")
                    out["details"]["audit"] = {"findings": cnt}
            except Exception:
                out["audit"] = "unknown"
    except Exception as e:
        out["error"] = str(e)
    return out


@kita_router.get("/dashboard/card/stprozent-mini")
async def card_stprozent_mini():
    try:
        with engine.connect() as conn:
            row = conn.execute(sa.text("""
                SELECT st_prozent_actual, st_prozent_required, calculation_date
                FROM kita_st_prozent_calculations
                ORDER BY calculation_date DESC LIMIT 1
            """)).mappings().first()
        if not row:
            return {"actual": None, "required": None, "ratio": None}
        actual = float(row["st_prozent_actual"] or 0)
        required = float(row["st_prozent_required"] or 0)
        ratio = (actual / required) if required else None
        return {
            "actual": round(actual, 1),
            "required": round(required, 1),
            "ratio": round(ratio, 2) if ratio else None,
            "date": row["calculation_date"].isoformat() if row.get("calculation_date") else None,
        }
    except Exception:
        return {"actual": None, "required": None, "ratio": None}


# === GREETING-ROUTER ===
"""
SHIKSHA · Greeting & Insights Router
Liefert die 5-Schichten-Begrüßung an die Hero-Card auf dem Dashboard.

Endpoints:
  GET   /kita/dashboard/card/greeting?role=traegerin&user=heidi
  GET   /kita/dashboard/weekly-theme
  PUT   /kita/dashboard/weekly-theme
  GET   /kita/dashboard/insights?audience=traegerin
  POST  /kita/dashboard/insights/{id}/dismiss

Anhängen an /opt/shiksha/kita_compliance_router.py.
Knowledge-Bites werden aus /opt/shiksha/data/knowledge_bites.json gelesen.
"""

import json as _grt_json
import random as _grt_random
import pathlib as _grt_path
from datetime import date as _grt_date, timedelta as _grt_td, datetime as _grt_dt

KNOWLEDGE_PATH = "/opt/shiksha/data/knowledge_bites.json"


def _load_knowledge():
    try:
        return _grt_json.loads(_grt_path.Path(KNOWLEDGE_PATH).read_text())
    except Exception:
        return []


def _current_season():
    m = _grt_date.today().month
    if m in (3, 4, 5):    return "spring"
    if m in (6, 7, 8):    return "summer"
    if m in (9, 10, 11):  return "autumn"
    return "winter"


def _greeting_phrase(role, user, hour, weekday):
    """Anrede — tageszeit-, person-, team-bewusst."""
    if 5 <= hour < 11:
        time_word = "Guten Morgen"
    elif 11 <= hour < 14:
        time_word = "Schönen Mittag"
    elif 14 <= hour < 18:
        time_word = "Hallo"
    elif 18 <= hour < 22:
        time_word = "Guten Abend"
    else:
        time_word = "Hallo"

    name = (user or "").strip()
    if name and name.lower() not in ("default", "anonymous"):
        # Vorname extrahieren wenn voller Name
        first = name.split()[0]
        if first.startswith(("traegerin", "paedagogin")):
            return f"{time_word}, Krummelus-Team"
        return f"{time_word}, {first.capitalize()}"
    if role == "paedagogin":
        return f"{time_word}, liebes Krummelus-Team"
    if role == "traegerin":
        return f"{time_word}"
    return f"{time_word} im Krummelus"


def _mood_sentence(role):
    """Stimmungs-Satz aus den letzten 7 Tagen Daten."""
    today = _grt_date.today()
    week_ago = today - _grt_td(days=7)
    parts = []
    try:
        with engine.connect() as conn:
            # Wie viele Krankmeldungen letzte Woche?
            try:
                sick = conn.execute(sa.text("""
                    SELECT COUNT(DISTINCT (work_date, COALESCE(legacy_child_id::text, legacy_staff_id::text)))
                    FROM kita_daily_assignments
                    WHERE work_date BETWEEN :a AND :b AND status = 'sick'
                """), {"a": week_ago, "b": today}).scalar() or 0
            except Exception:
                sick = 0
            # Wie viele Events gab's letzte Woche?
            events = conn.execute(sa.text("""
                SELECT COUNT(*) FROM kita_calendar_events
                WHERE start_date BETWEEN :a AND :b
                  AND event_type IN ('event', 'celebration', 'training')
            """), {"a": week_ago, "b": today}).scalar() or 0
            # Aktuelle Anwesenheit
            try:
                present_now = conn.execute(sa.text("""
                    SELECT COUNT(DISTINCT legacy_child_id) FROM kita_daily_assignments
                    WHERE work_date = :d AND status = 'present' AND person_type = 'child'
                """), {"d": today}).scalar() or 0
            except Exception:
                present_now = 0

        # Erzähl-Logik: bevorzuge die markanteste Beobachtung
        if today.weekday() == 0:  # Montag
            if sick >= 4:
                return f"Letzte Woche war intensiv — {sick} Krankmeldungen, dafür liegt jetzt eine frische Woche vor uns."
            if events >= 2:
                return f"Letzte Woche {events} Veranstaltungen — was für eine erlebnisreiche Phase. Heute starten wir ruhig in die neue."
            return "Eine neue Woche steht an. Wir wünschen einen guten Start!"
        if today.weekday() == 4:  # Freitag
            return "Endspurt der Woche — gleich Wochenende. Was ist heute noch dran?"
        # Wochentags-Default
        if present_now > 0:
            return f"Gerade sind {present_now} Kinder bei Euch. Schöner Tag dafür."
        if events >= 1:
            return "Heute steht etwas Besonderes an — wir freuen uns darauf!"
        if sick >= 3:
            return "Wir denken an alle, die diese Woche krank sind. Gute Besserung!"
        return "Einen schönen Tag im Krummelus."
    except Exception:
        return "Schön, dass Du da bist."


def _pick_knowledge_bite(role):
    """Wissens-Snippet — kontext-passend, mit etwas Zufall."""
    bites = _load_knowledge()
    if not bites:
        return None
    season = _current_season()
    # Filter: Audience + Saison
    candidates = [
        b for b in bites
        if (not b.get("audience") or role in b["audience"] or "all" in b["audience"])
        and (b.get("season", "always") in ("always", season))
    ]
    if not candidates:
        candidates = bites
    # Tagesbasierter Pseudo-Zufall, damit Bite einen ganzen Tag stabil bleibt
    seed = _grt_date.today().toordinal() + (1 if role == "traegerin" else 2)
    rng = _grt_random.Random(seed)
    return rng.choice(candidates)


def _current_weekly_theme():
    today = _grt_date.today()
    monday = today - _grt_td(days=today.weekday())
    try:
        with engine.connect() as conn:
            row = conn.execute(sa.text("""
                SELECT theme, set_by, note, week_start FROM weekly_themes
                WHERE week_start = :w
            """), {"w": monday}).mappings().first()
    except Exception:
        row = None
    if not row:
        return None
    days_left = 7 - today.weekday()
    return {
        "theme": row["theme"],
        "set_by": row.get("set_by"),
        "note": row.get("note"),
        "week_start": row["week_start"].isoformat(),
        "days_left": days_left,
    }


def _top_insight(role, user_id):
    """Den am stärksten gewichteten aktiven Insight für die Persona."""
    today = _grt_date.today()
    try:
        with engine.connect() as conn:
            row = conn.execute(sa.text("""
                SELECT i.id, i.title, i.body, i.icon, i.severity, i.action_label, i.action_url,
                       i.metadata, i.generated_at
                FROM shiksha_insights i
                LEFT JOIN shiksha_insight_dismisses d ON d.insight_id = i.id AND d.user_id = :uid
                WHERE i.active = true
                  AND (i.audience = :aud OR i.audience = 'all')
                  AND (i.valid_until IS NULL OR i.valid_until >= :today)
                  AND d.user_id IS NULL
                ORDER BY
                  CASE i.severity WHEN 'warn' THEN 1 WHEN 'notice' THEN 2 ELSE 3 END,
                  i.generated_at DESC
                LIMIT 1
            """), {"aud": role, "uid": user_id, "today": today}).mappings().first()
    except Exception:
        return None
    if not row:
        return None
    out = dict(row)
    if out.get("generated_at"):
        out["generated_at"] = out["generated_at"].isoformat()
    return out


# ============================================================
# ENDPOINTS
# ============================================================

@kita_router.get("/dashboard/card/greeting")
async def card_greeting(
    role: str = "traegerin",
    user: str = "",
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    now = _grt_dt.now()
    return {
        "greeting": _greeting_phrase(role, user, now.hour, now.weekday()),
        "mood": _mood_sentence(role),
        "knowledge": _pick_knowledge_bite(role),
        "weekly_theme": _current_weekly_theme(),
        "insight": _top_insight(role, user_id),
        "time": now.isoformat(),
        "tip": "SHIKSHA lernt — mit jedem Tag mehr.",
    }


@kita_router.get("/dashboard/weekly-theme")
async def weekly_theme_get(week_start: str = None):
    if week_start:
        d = _grt_date.fromisoformat(week_start)
    else:
        today = _grt_date.today()
        d = today - _grt_td(days=today.weekday())
    with engine.connect() as conn:
        row = conn.execute(sa.text("""
            SELECT * FROM weekly_themes WHERE week_start = :w
        """), {"w": d}).mappings().first()
    if not row:
        return {"week_start": d.isoformat(), "theme": None}
    return {**dict(row), "week_start": row["week_start"].isoformat(),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None}


@kita_router.put("/dashboard/weekly-theme")
async def weekly_theme_put(payload: dict = Body(...)):
    today = _grt_date.today()
    monday = today - _grt_td(days=today.weekday())
    week_start = payload.get("week_start")
    if week_start:
        week_start = _grt_date.fromisoformat(week_start)
    else:
        week_start = monday
    theme = (payload.get("theme") or "").strip()
    if not theme:
        raise HTTPException(400, "theme Pflicht")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO weekly_themes (week_start, theme, set_by, note)
            VALUES (:w, :t, :s, :n)
            ON CONFLICT (week_start) DO UPDATE
              SET theme = :t, set_by = :s, note = :n
        """), {
            "w": week_start, "t": theme,
            "s": payload.get("set_by", "leitung"),
            "n": payload.get("note"),
        })
    return {"ok": True, "week_start": week_start.isoformat(), "theme": theme}


@kita_router.get("/dashboard/insights")
async def insights_list(
    audience: str = "all",
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    today = _grt_date.today()
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT i.*, (d.user_id IS NOT NULL) AS dismissed
            FROM shiksha_insights i
            LEFT JOIN shiksha_insight_dismisses d ON d.insight_id = i.id AND d.user_id = :uid
            WHERE i.active = true
              AND (i.audience = :aud OR i.audience = 'all' OR :aud = 'all')
              AND (i.valid_until IS NULL OR i.valid_until >= :today)
            ORDER BY i.generated_at DESC
            LIMIT 20
        """), {"aud": audience, "uid": user_id, "today": today}).mappings().fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("generated_at", "valid_until"):
            if d.get(k):
                d[k] = d[k].isoformat() if hasattr(d[k], "isoformat") else d[k]
        out.append(d)
    return {"insights": out}


@kita_router.post("/dashboard/insights/{insight_id}/dismiss")
async def insight_dismiss(
    insight_id: int,
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO shiksha_insight_dismisses (insight_id, user_id)
            VALUES (:id, :uid)
            ON CONFLICT DO NOTHING
        """), {"id": insight_id, "uid": user_id})
    return {"ok": True}


# === MARKETING-ROUTER ===
"""
SHIKSHA · Marketing-Sites Router
Phase 1 — KITA-Pilot Krummelus.

Endpoints:
  Builder/Admin:
    POST   /admin/marketing/sites             — neue Site anlegen
    GET    /admin/marketing/sites/{slug}      — Site laden
    PUT    /admin/marketing/sites/{slug}      — bearbeiten
    POST   /admin/marketing/sites/{slug}/generate  — Claude-AI-Content
    POST   /admin/marketing/sites/{slug}/publish   — live schalten
    POST   /admin/marketing/sites/{slug}/upload    — Asset hochladen
    GET    /admin/marketing/pool/images?edition=kita&season=spring — Pool-Bilder

  Public:
    GET    /m/{slug}                          — Marketing-Site rendern
    GET    /m/asset/{asset_id}                — Asset ausliefern
    POST   /m/{slug}/anmeldung                — Anmelde-Formular submitten

Voraussetzungen (im venv):
  pip install anthropic httpx jinja2

Env (in /opt/shiksha/.env):
  ANTHROPIC_API_KEY=sk-ant-...
  MARKETING_ASSETS_DIR=/opt/shiksha/marketing_assets
  MARKETING_TEMPLATES_DIR=/opt/shiksha/marketing_templates

Anhängen an /opt/shiksha/kita_compliance_router.py.
"""

import os as _mk_os
import json as _mk_json
import hashlib as _mk_hash
import pathlib as _mk_path
import shutil as _mk_shutil
import datetime as _mk_dt
from datetime import date as _mk_date

import httpx as _mk_httpx
from fastapi import UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from jinja2 import Environment as _mk_jinja_env, FileSystemLoader as _mk_fs_loader, select_autoescape

ANTHROPIC_API_KEY = _mk_os.environ.get("ANTHROPIC_API_KEY", "")
ASSETS_DIR = _mk_path.Path(_mk_os.environ.get("MARKETING_ASSETS_DIR", "/opt/shiksha/marketing_assets"))
TEMPLATES_DIR = _mk_path.Path(_mk_os.environ.get("MARKETING_TEMPLATES_DIR", "/opt/shiksha/marketing_templates"))

ASSETS_DIR.mkdir(parents=True, exist_ok=True)

_mk_jinja = _mk_jinja_env(
    loader=_mk_fs_loader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


# ============================================================
# JAHRESZEITEN-LOGIK
# ============================================================

def _mk_season(today=None):
    today = today or _mk_date.today()
    m = today.month
    if m in (3, 4, 5):    return "spring"
    if m in (6, 7, 8):    return "summer"
    if m in (9, 10, 11):  return "autumn"
    return "winter"


# ============================================================
# GEOCODING + POIs (OpenStreetMap, gratis)
# ============================================================

async def _mk_geocode(address):
    """Adresse → (lat, lng, country, region)."""
    if not address:
        return None
    async with _mk_httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": address, "format": "json", "addressdetails": 1, "limit": 1},
                headers={"User-Agent": "SHIKSHA-Marketing-Builder/1.0"},
            )
            arr = r.json()
            if not arr:
                return None
            x = arr[0]
            ad = x.get("address", {})
            return {
                "lat": float(x["lat"]), "lng": float(x["lon"]),
                "country": ad.get("country", ""),
                "country_code": ad.get("country_code", "").upper(),
                "region": ad.get("state") or ad.get("region") or "",
                "city": ad.get("city") or ad.get("town") or ad.get("village") or "",
                "display": x.get("display_name", ""),
            }
        except Exception as e:
            print(f"[mk_geocode] {e}")
            return None


async def _mk_nearby_pois(lat, lng, radius_m=3000):
    """OpenStreetMap Overpass-API: Bahnhof, Flughafen, Sehenswürdigkeiten."""
    if not lat or not lng:
        return {}
    query = f"""
    [out:json][timeout:25];
    (
      node(around:{radius_m},{lat},{lng})["railway"="station"];
      node(around:{radius_m * 5},{lat},{lng})["aeroway"="aerodrome"];
      node(around:{radius_m},{lat},{lng})["tourism"~"attraction|museum|viewpoint"];
      node(around:{radius_m},{lat},{lng})["shop"="supermarket"];
    );
    out body 20;
    """
    async with _mk_httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post("https://overpass-api.de/api/interpreter", data={"data": query})
            elements = r.json().get("elements", [])
        except Exception as e:
            print(f"[mk_nearby_pois] {e}")
            return {}
    out = {"trains": [], "airports": [], "attractions": [], "supermarkets": []}
    for e in elements:
        t = e.get("tags", {})
        name = t.get("name") or t.get("name:de")
        if not name: continue
        if t.get("railway") == "station":
            out["trains"].append(name)
        elif t.get("aeroway") == "aerodrome":
            out["airports"].append(name)
        elif t.get("tourism"):
            out["attractions"].append(name)
        elif t.get("shop") == "supermarket":
            out["supermarkets"].append(name)
    # Deduplicate
    for k in out: out[k] = list(dict.fromkeys(out[k]))[:5]
    return out


# ============================================================
# CLAUDE-AI CONTENT-GENERATION
# ============================================================

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"   # aktuelles Standardmodell


async def _mk_claude_call(system_prompt, user_prompt, max_tokens=2000):
    """Direkt-Call zur Claude API (ohne SDK-Abhängigkeit)."""
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY nicht gesetzt"}

    async with _mk_httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            CLAUDE_API_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        if r.status_code != 200:
            return {"error": f"Claude API {r.status_code}: {r.text[:300]}"}
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []))
        return {"text": text, "usage": data.get("usage", {})}


def _mk_cache_key(*parts):
    raw = "|".join(str(p) for p in parts)
    return _mk_hash.sha256(raw.encode()).hexdigest()[:32]


async def _mk_generate_kita_content(site_data, geo, pois):
    """KITA-Content über Claude generieren. Cached."""
    cache_key = _mk_cache_key("kita-v1", site_data.get("business_name"),
                              site_data.get("address_line"), site_data.get("city"))
    with engine.connect() as conn:
        cached = conn.execute(sa.text("SELECT response FROM marketing_llm_cache WHERE cache_key = :k"),
                              {"k": cache_key}).first()
    if cached:
        return cached[0]

    system = """Du bist die Stimme von SHIKSHA, einer Plattform für KITAs im DACH-Raum.
Schreibe warm, persönlich, präzise — wie ein erfahrener Kollege, nicht wie eine Werbeagentur.
Sprache: Deutsch, du-Form bei Eltern-Anrede, Sie-Form bei formellen Sektionen.
Vermeide Floskeln wie 'liebevoll', 'ganzheitlich', 'individuell'. Sei konkret.
Antworte ausschließlich als JSON-Objekt mit den genau angeforderten Feldern."""

    user = f"""Generiere die Texte für die Marketing-Webseite einer KITA mit diesen Daten:

Name: {site_data.get('business_name')}
Adresse: {site_data.get('address_line')}, {site_data.get('postal_code')} {site_data.get('city')}
Region: {geo.get('region') if geo else 'unbekannt'}
Land: {geo.get('country') if geo else 'unbekannt'}
Nahegelegene Bahnhöfe: {', '.join((pois or {}).get('trains', [])) or 'nichts gefunden'}
Nahegelegene Flughäfen: {', '.join((pois or {}).get('airports', [])) or 'nichts gefunden'}
Nahegelegene Sehenswürdigkeiten: {', '.join((pois or {}).get('attractions', [])) or 'nichts gefunden'}

Liefere folgende Felder zurück (JSON):
- "tagline": eine prägnante Zeile (max 50 Zeichen), z.B. "Eine KITA, die mitwächst."
- "description": 2-3 Sätze als Hero-Untertitel
- "about_text": 3 Absätze über die KITA, ihre Werte, ihre Atmosphäre. Erzählend, nicht aufzählend.
- "concept_text": 2-3 Absätze zum pädagogischen Ansatz. Konkret und greifbar, keine Buzzwords.
- "arrival_text": 1 Absatz Anfahrt mit den realen Bahnhof/Flughafen-Daten oben — wie man am besten herfindet."""

    res = await _mk_claude_call(system, user, max_tokens=2500)
    if res.get("error"):
        return {"error": res["error"]}

    # JSON aus Antwort extrahieren
    text = res["text"].strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = _mk_json.loads(text)
    except Exception:
        return {"error": "Claude-Antwort war kein gültiges JSON", "raw": text[:500]}

    # Cache schreiben
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO marketing_llm_cache (cache_key, response, model, tokens_used)
            VALUES (:k, CAST(:r AS jsonb), :m, :t)
            ON CONFLICT (cache_key) DO NOTHING
        """), {
            "k": cache_key, "r": _mk_json.dumps(parsed),
            "m": CLAUDE_MODEL,
            "t": (res.get("usage") or {}).get("input_tokens", 0) + (res.get("usage") or {}).get("output_tokens", 0),
        })
    return parsed


# ============================================================
# ADMIN-ENDPOINTS
# ============================================================

@kita_router.post("/admin/marketing/sites")
async def mk_site_create(payload: dict = Body(...)):
    slug = (payload.get("slug") or "").strip().lower()
    name = (payload.get("business_name") or "").strip()
    if not slug or not name:
        raise HTTPException(400, "slug und business_name Pflicht")
    edition = payload.get("edition", "kita")
    with engine.begin() as conn:
        try:
            result = conn.execute(sa.text("""
                INSERT INTO marketing_sites
                  (slug, edition, business_name, address_line, postal_code, city, country,
                   contact_email, phone, status)
                VALUES (:s, :e, :n, :a, :pc, :c, :co, :em, :ph, 'draft')
                RETURNING id
            """), {
                "s": slug, "e": edition, "n": name,
                "a": payload.get("address_line"), "pc": payload.get("postal_code"),
                "c": payload.get("city"), "co": payload.get("country", "AT"),
                "em": payload.get("contact_email"), "ph": payload.get("phone"),
            })
            new_id = result.scalar()
        except Exception as e:
            raise HTTPException(400, f"Slug existiert? {e}")
    return {"id": new_id, "slug": slug, "edition": edition}


@kita_router.get("/admin/marketing/sites/{slug}")
async def mk_site_get(slug: str):
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT * FROM marketing_sites WHERE slug = :s"),
                           {"s": slug}).mappings().first()
    if not row:
        raise HTTPException(404, "Site nicht gefunden")
    out = dict(row)
    for k in ("created_at", "updated_at", "last_published_at"):
        if out.get(k): out[k] = out[k].isoformat()
    if out.get("trial_until"): out["trial_until"] = out["trial_until"].isoformat()
    return out


@kita_router.put("/admin/marketing/sites/{slug}")
async def mk_site_update(slug: str, payload: dict = Body(...)):
    allowed = ("business_name", "tagline", "description", "address_line", "postal_code",
               "city", "country", "lat", "lng", "contact_email", "phone", "website_external",
               "opening_hours", "about_text", "concept_text", "arrival_text", "excursions_text",
               "accent_color", "season_override",
               "logo_asset_id", "hero_asset_id", "gallery_asset_ids")
    fields = {k: payload[k] for k in allowed if k in payload}
    if not fields:
        raise HTTPException(400, "keine Felder")
    set_parts = [f"{k} = :{k}" for k in fields]
    set_parts.append("updated_at = NOW()")
    fields["s"] = slug
    sql = f"UPDATE marketing_sites SET {', '.join(set_parts)} WHERE slug = :s"
    with engine.begin() as conn:
        result = conn.execute(sa.text(sql), fields)
        if result.rowcount == 0:
            raise HTTPException(404, "Site nicht gefunden")
    return {"slug": slug, "updated": list(fields.keys())}


@kita_router.post("/admin/marketing/sites/{slug}/generate")
async def mk_site_generate(slug: str):
    """Claude-AI generiert Texte aus Standort-Daten."""
    with engine.connect() as conn:
        site = conn.execute(sa.text("SELECT * FROM marketing_sites WHERE slug = :s"),
                            {"s": slug}).mappings().first()
    if not site:
        raise HTTPException(404, "Site nicht gefunden")
    site_d = dict(site)

    # Geocoding
    full_address = ", ".join(filter(None, [
        site_d.get("address_line"), site_d.get("postal_code"),
        site_d.get("city"), site_d.get("country")
    ]))
    geo = await _mk_geocode(full_address)
    pois = await _mk_nearby_pois(geo["lat"], geo["lng"]) if geo else {}

    # Claude
    if site_d["edition"] == "kita":
        result = await _mk_generate_kita_content(site_d, geo, pois)
    else:
        result = {"error": f"Edition '{site_d['edition']}' noch nicht unterstützt"}

    if result.get("error"):
        return {"ok": False, "error": result["error"]}

    # Update Site
    with engine.begin() as conn:
        conn.execute(sa.text("""
            UPDATE marketing_sites SET
              tagline = :tl, description = :d, about_text = :a,
              concept_text = :c, arrival_text = :ar,
              lat = :lat, lng = :lng,
              extra = CAST(:x AS jsonb),
              updated_at = NOW()
            WHERE slug = :s
        """), {
            "s": slug,
            "tl": result.get("tagline"), "d": result.get("description"),
            "a": result.get("about_text"), "c": result.get("concept_text"),
            "ar": result.get("arrival_text"),
            "lat": geo["lat"] if geo else None,
            "lng": geo["lng"] if geo else None,
            "x": _mk_json.dumps({"geo": geo, "pois": pois}),
        })
    return {"ok": True, "generated": result, "geo": geo, "pois": pois}


@kita_router.post("/admin/marketing/sites/{slug}/publish")
async def mk_site_publish(slug: str):
    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            UPDATE marketing_sites
              SET status = 'live', last_published_at = NOW()
            WHERE slug = :s
            RETURNING id, status
        """), {"s": slug})
        if result.rowcount == 0:
            raise HTTPException(404, "Site nicht gefunden")
    return {"slug": slug, "status": "live"}


@kita_router.post("/admin/marketing/sites/{slug}/upload")
async def mk_site_upload(slug: str, role: str = Form(...), file: UploadFile = File(...)):
    """Lädt ein Asset hoch und verknüpft es mit der Site (role: logo|hero|gallery)."""
    with engine.connect() as conn:
        site = conn.execute(sa.text("SELECT id FROM marketing_sites WHERE slug = :s"),
                            {"s": slug}).first()
    if not site:
        raise HTTPException(404, "Site nicht gefunden")
    site_id = site[0]

    site_dir = ASSETS_DIR / slug
    site_dir.mkdir(parents=True, exist_ok=True)
    safe_name = file.filename.replace("/", "_").replace("..", "_")
    timestamp = _mk_dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    final_path = site_dir / f"{role}-{timestamp}-{safe_name}"
    with final_path.open("wb") as f:
        _mk_shutil.copyfileobj(file.file, f)

    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            INSERT INTO marketing_assets (site_id, file_path, mime_type, source)
            VALUES (:sid, :fp, :mt, 'upload')
            RETURNING id
        """), {"sid": site_id, "fp": str(final_path), "mt": file.content_type})
        asset_id = result.scalar()

        if role == "logo":
            conn.execute(sa.text("UPDATE marketing_sites SET logo_asset_id = :a WHERE id = :s"),
                         {"a": asset_id, "s": site_id})
        elif role == "hero":
            conn.execute(sa.text("UPDATE marketing_sites SET hero_asset_id = :a WHERE id = :s"),
                         {"a": asset_id, "s": site_id})
        elif role == "gallery":
            conn.execute(sa.text("""
                UPDATE marketing_sites
                  SET gallery_asset_ids = array_append(gallery_asset_ids, :a)
                WHERE id = :s
            """), {"a": asset_id, "s": site_id})
    return {"asset_id": asset_id, "role": role, "url": f"/m/asset/{asset_id}"}


@kita_router.get("/admin/marketing/pool/images")
async def mk_pool_images(edition: str = "kita", season: str = None):
    season = season or _mk_season()
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, file_path, alt_text, pool_tags FROM marketing_assets
            WHERE site_id IS NULL
              AND pool_edition = :e
              AND (pool_season = :ss OR pool_season = 'all')
            ORDER BY id
        """), {"e": edition, "ss": season}).mappings().fetchall()
    return {"season": season, "images": [
        {"id": r["id"], "url": f"/m/asset/{r['id']}", "alt": r["alt_text"], "tags": r.get("pool_tags") or []}
        for r in rows
    ]}


# ============================================================
# PUBLIC-ENDPOINTS
# ============================================================

@kita_router.get("/m/asset/{asset_id}")
async def mk_asset(asset_id: int):
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT file_path, mime_type FROM marketing_assets WHERE id = :i"),
                           {"i": asset_id}).first()
    if not row:
        raise HTTPException(404)
    fp = row[0]
    if not _mk_path.Path(fp).exists():
        raise HTTPException(404, "Datei nicht da")
    return FileResponse(fp, media_type=row[1] or "application/octet-stream")


@kita_router.get("/m/{slug}", response_class=HTMLResponse)
async def mk_public_site(slug: str):
    with engine.connect() as conn:
        site = conn.execute(sa.text("SELECT * FROM marketing_sites WHERE slug = :s"),
                            {"s": slug}).mappings().first()
    if not site:
        return HTMLResponse(content="<h1>Diese Seite gibt es noch nicht.</h1>", status_code=404)

    site_d = dict(site)
    season = site_d.get("season_override") or _mk_season()
    edition = site_d.get("edition", "kita")

    # Live-Daten holen
    today = _mk_date.today()
    live = {}
    try:
        with engine.connect() as conn:
            kids_total = conn.execute(sa.text("SELECT COUNT(*) FROM kita_legacy_children WHERE active = true")).scalar() or 0
            try:
                kids_present = conn.execute(sa.text("""
                    SELECT COUNT(DISTINCT legacy_child_id) FROM kita_daily_assignments
                    WHERE work_date = :d AND status = 'present' AND person_type = 'child'
                """), {"d": today}).scalar() or 0
            except Exception:
                kids_present = 0
            # Wochen-Theme
            monday = today - _mk_dt.timedelta(days=today.weekday())
            wt = conn.execute(sa.text("SELECT theme FROM weekly_themes WHERE week_start = :w"),
                              {"w": monday}).first()
            # Bevorstehende Eltern-sichtbare Termine
            events = conn.execute(sa.text("""
                SELECT title, event_type, start_date, color FROM kita_calendar_events
                WHERE start_date BETWEEN :a AND :b AND visible_eltern = true
                ORDER BY start_date LIMIT 5
            """), {"a": today, "b": today + _mk_dt.timedelta(days=30)}).mappings().fetchall()
        live = {
            "kids_present": kids_present,
            "kids_total": kids_total,
            "weekly_theme": wt[0] if wt else None,
            "events": [dict(e, start_date=e["start_date"].isoformat()) for e in events],
        }
    except Exception:
        live = {}

    # Wissens-Snippet (Eltern-Audience)
    try:
        bites = _grt_json.loads(_mk_path.Path("/opt/shiksha/data/knowledge_bites.json").read_text())
        eltern_bites = [b for b in bites if "eltern" in b.get("audience", []) or not b.get("audience")]
        import random as _mk_rand
        seed = today.toordinal()
        knowledge = _mk_rand.Random(seed).choice(eltern_bites) if eltern_bites else None
    except Exception:
        knowledge = None

    # Greeting
    hour = _mk_dt.datetime.now().hour
    greeting = ("Guten Morgen" if hour < 11 else
                "Schönen Mittag" if hour < 14 else
                "Hallo" if hour < 18 else "Guten Abend")

    # Gallery-Bilder
    gallery = []
    if site_d.get("gallery_asset_ids"):
        with engine.connect() as conn:
            for gid in site_d["gallery_asset_ids"]:
                row = conn.execute(sa.text("SELECT id, alt_text FROM marketing_assets WHERE id = :i"),
                                   {"i": gid}).first()
                if row:
                    gallery.append({"id": row[0], "url": f"/m/asset/{row[0]}", "alt": row[1] or ""})

    # Logo / Hero URLs
    logo_url = f"/m/asset/{site_d['logo_asset_id']}" if site_d.get("logo_asset_id") else None
    hero_url = f"/m/asset/{site_d['hero_asset_id']}" if site_d.get("hero_asset_id") else None

    # Template rendern
    try:
        tmpl_name = f"{edition}_{season}.html"
        tmpl = _mk_jinja.get_template(tmpl_name)
    except Exception:
        try:
            tmpl = _mk_jinja.get_template(f"{edition}_spring.html")  # fallback auf spring
        except Exception:
            return HTMLResponse(content=f"<h1>Template fehlt: {edition}_{season}.html</h1>", status_code=500)

    html = tmpl.render(
        site=site_d, live=live, knowledge=knowledge,
        greeting=greeting, gallery=gallery,
        logo_url=logo_url, hero_url=hero_url,
        season=season, today=today.isoformat(),
    )
    return HTMLResponse(content=html)


@kita_router.post("/m/{slug}/anmeldung")
async def mk_public_anmeldung(slug: str, payload: dict = Body(...)):
    """Anmelde-Formular submitted — speichert in der existierenden Eltern-Anmeldungs-Tabelle."""
    with engine.connect() as conn:
        site = conn.execute(sa.text("SELECT id, edition, business_name, contact_email FROM marketing_sites WHERE slug = :s"),
                            {"s": slug}).mappings().first()
    if not site:
        raise HTTPException(404)
    # Schreibt in eine "soft-Anmeldung"-Tabelle, die wir (sofern existent) nutzen.
    # Für MVP: einfach in marketing_sites.extra anhängen
    entry = {
        "received_at": _mk_dt.datetime.now().isoformat(),
        "site_slug": slug,
        **{k: payload.get(k) for k in ("name", "email", "phone", "child_name", "child_birth", "message")},
    }
    with engine.begin() as conn:
        conn.execute(sa.text("""
            UPDATE marketing_sites
              SET extra = jsonb_set(extra,
                    '{anmeldungen}',
                    COALESCE(extra->'anmeldungen', '[]'::jsonb) || CAST(:e AS jsonb))
            WHERE slug = :s
        """), {"e": _mk_json.dumps(entry), "s": slug})
    return {"ok": True, "message": "Wir haben Ihre Nachricht erhalten und melden uns bald."}
