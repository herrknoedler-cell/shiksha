"""Personalschlüssel-Berechnung — Sweepline-Algorithmus.

Spec: SHIKSHA_ATTENDANCE_SPEC.md §5.3.

Idee: Sweepline über alle check_in_at/check_out_at-Events des Tages, finde
max gleichzeitige Anwesenheit. Vergleich gegen required_staff aus
attendance_settings.staff_ratio.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from math import ceil
from typing import Any, Optional

from shiksha_engine.models.attendance import (
    AttendanceRecord,
    AttendanceSettings,
    PRESENT_STATUS,
)
from shiksha_engine.models.person import Person


# ----------------------------------------------------------- Helpers


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=timezone.utc)


def _day_end(day: date) -> datetime:
    return datetime.combine(day, time(23, 59, 59), tzinfo=timezone.utc)


def _age_at(birth_date: Optional[date], today: date) -> Optional[int]:
    if birth_date is None:
        return None
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


# ----------------------------------------------------------- Sweepline


def max_concurrent_present(
    records: list[AttendanceRecord],
    day: date,
) -> tuple[int, Optional[datetime]]:
    """
    Sweepline über alle check_in_at/check_out_at-Events.
    Returns (peak_count, time_of_peak).

    Sonderfall: status='anwesend' aber check_in_at=NULL → zählt ganztags
    (status overrules fehlende Zeitstempel).
    """
    events: list[tuple[datetime, int, int]] = []
    # (time, +1 vor -1 bei gleicher time → priority, +/- 1)
    # priority 0 = +1 (begin), priority 1 = -1 (end) → +1 wird vor -1 verarbeitet
    for r in records:
        if r.status not in PRESENT_STATUS:
            continue
        if r.check_in_at:
            start = r.check_in_at
            end = r.check_out_at or _day_end(day)
        else:
            # status=anwesend ohne Zeitstempel → ganztags
            start = _day_start(day)
            end = _day_end(day)
        events.append((start, 0, +1))
        events.append((end, 1, -1))

    if not events:
        return 0, None

    events.sort()  # zuerst Zeit, dann priority (0 vor 1) → +1 vor -1

    cur = 0
    peak = 0
    peak_time: Optional[datetime] = None
    for ts, _prio, delta in events:
        cur += delta
        if cur > peak:
            peak = cur
            peak_time = ts
    return peak, peak_time


# ----------------------------------------------------------- Personalschlüssel


def required_staff_for_kids(
    kid_records: list[AttendanceRecord],
    persons_by_id: dict[int, Person],
    staff_ratio: dict[str, Any],
    day: date,
) -> int:
    """
    Bestimmt erforderliche Pädagoginnen für die anwesenden Kinder.

    staff_ratio-Format: {"3": 6, "6": 12}
      → Kinder bis 3 Jahre: 6 Kinder pro Päd.
      → Kinder bis 6 Jahre: 12 Kinder pro Päd.
    Älter als max(keys) wird wie max(keys)-Band behandelt.
    """
    if not staff_ratio:
        return 0

    # Konvertiere keys zu int und sortiere
    bands = sorted([(int(k), v) for k, v in staff_ratio.items()])
    if not bands:
        return 0

    # Pro Kind das passende Band finden, Kinder zählen pro Band
    band_counts: dict[int, int] = {age_max: 0 for age_max, _ in bands}
    for r in kid_records:
        if r.status not in PRESENT_STATUS:
            continue
        person = persons_by_id.get(r.person_id)
        age = _age_at(person.birth_date if person else None, day)
        if age is None:
            # Unbekanntes Alter → konservativ ins niedrigste Band
            band_counts[bands[0][0]] += 1
            continue
        # Erstes Band, wo age <= age_max
        placed = False
        for age_max, _ in bands:
            if age <= age_max:
                band_counts[age_max] += 1
                placed = True
                break
        if not placed:
            # Älter als alle Bänder → ins höchste Band
            band_counts[bands[-1][0]] += 1

    # Erforderliche Päd. pro Band, dann summieren
    total_required = 0
    for age_max, ratio in bands:
        kids_in_band = band_counts.get(age_max, 0)
        if kids_in_band > 0:
            total_required += ceil(kids_in_band / ratio)
    return total_required


def compute_ratio_status(
    records: list[AttendanceRecord],
    persons_by_id: dict[int, Person],
    settings: AttendanceSettings,
    day: date,
) -> dict[str, Any]:
    """
    Returns dict für LiveCounts:
      - kids_present_count
      - staff_present_count
      - ratio_status: 'green' | 'yellow' | 'red'
      - ratio_status_label
      - ratio_explanation
      - next_check_at
    """
    kid_records = []
    staff_records = []
    for r in records:
        person = persons_by_id.get(r.person_id)
        if person is None:
            continue
        if person.kind == "kind":
            kid_records.append(r)
        elif person.kind == "staff":
            staff_records.append(r)

    # gast zählt im Personalschlüssel (siehe Spec F5)
    if settings.gast_counts:
        gast_records = [r for r in records if persons_by_id.get(r.person_id) and persons_by_id[r.person_id].kind == "gast"]
        kid_records.extend(gast_records)

    kids_peak, kids_peak_time = max_concurrent_present(kid_records, day)
    staff_peak, _ = max_concurrent_present(staff_records, day)

    required = required_staff_for_kids(
        kid_records, persons_by_id, settings.staff_ratio, day
    )

    if required == 0:
        # Keine Kinder anwesend → Personalschlüssel trivial erfüllt
        status = "green"
        label = "grün ✓"
        explanation = None
    elif staff_peak >= required + 1:
        status = "green"
        label = "grün ✓"
        explanation = None
    elif staff_peak >= required:
        status = "yellow"
        label = "knapp ⚠"
        explanation = f"Personalschlüssel gerade erfüllt — keine Reserve."
    else:
        status = "red"
        label = "ROT ⚠"
        diff = required - staff_peak
        explanation = (
            f"Du brauchst {diff} weitere Pädagog{'in' if diff == 1 else 'innen'}"
            + (f" um {kids_peak_time.strftime('%H:%M')}." if kids_peak_time else ".")
        )

    return {
        "kids_present_count": kids_peak,
        "staff_present_count": staff_peak,
        "ratio_status": status,
        "ratio_status_label": label,
        "ratio_explanation": explanation,
        "next_check_at": kids_peak_time,
    }
