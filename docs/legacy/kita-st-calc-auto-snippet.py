"""
SHIKSHA · KITA · kita_st_calc_auto.py — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle, am 29.04.2026 via deploy-Skript an
/opt/shiksha/kita_compliance_router.py ANGEHÄNGT — nicht als
eigenständiger Router deployed.

Der deployed-Stand lebt heute in:
    server/kita_compliance_router.py  (omnibus router, ~5389 Zeilen)

Bei einer späteren Modul-Trennung kann dieses Snippet zurück nach
server/kita_st_calc_auto.py wandern.

Original: cowork/outputs/kita/server/kita_st_calc_auto.py (2026-04-29)
Importiert: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

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
