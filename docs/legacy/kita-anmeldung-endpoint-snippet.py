"""
SHIKSHA · KITA · kita_anmeldung_endpoint.py — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle, am 29.04.2026 via deploy-Skript an
/opt/shiksha/kita_compliance_router.py ANGEHÄNGT — nicht als
eigenständiger Router deployed.

Der deployed-Stand lebt heute in:
    server/kita_compliance_router.py  (omnibus router, ~5389 Zeilen)

Bei einer späteren Modul-Trennung kann dieses Snippet zurück nach
server/kita_anmeldung_endpoint.py wandern.

Original: cowork/outputs/kita/server/kita_anmeldung_endpoint.py (2026-04-29)
Importiert: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

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
