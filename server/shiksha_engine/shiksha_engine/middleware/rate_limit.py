"""Rate-Limit-Middleware — pro Operator pro Tag, SQL-Counter.

Was geprüft wird:
  - Endpoints unter /api/v1/chat/* und /api/v1/tools/*
  - JWT-Auth nötig (sonst kann's nicht zugeordnet werden — Auth-Layer
    wirft eh 401 davor)

Was nicht limitiert wird:
  - Auth-Endpoints (login/register)
  - Sessions-Listing, Memory-Read (kein Anthropic-Call)
  - Developer-Endpoints (developer-Rolle ist immer ohne Limit)

429-Response enthält:
  - X-RateLimit-Limit:     200
  - X-RateLimit-Remaining: 0
  - X-RateLimit-Reset:     ISO-Timestamp (Tagesende UTC)
  - Retry-After:           Sekunden bis Reset
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..db import SessionLocal
from ..models import RateLimitBucket
from ..services.jwt_service import TokenError, verify_token
from ..settings import get_settings

logger = logging.getLogger("shiksha.rate_limit")


# Limitierte Endpoint-Prefixes
_RATE_LIMITED_PREFIXES = (
    "/api/v1/chat/respond",
    "/api/v1/chat/stream",
    "/api/v1/chat/close",
    "/api/v1/tools/",
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Schnell raus wenn nicht relevant
        if not any(path.startswith(p) for p in _RATE_LIMITED_PREFIXES):
            return await call_next(request)

        # Operator aus Bearer extrahieren — Auth-Middleware verifiziert später nochmal,
        # hier nur zum Counting
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return await call_next(request)  # 401 kommt im Endpoint

        token = auth.removeprefix("Bearer ").strip()
        try:
            payload = verify_token(token)
        except TokenError:
            return await call_next(request)  # 401 kommt im Endpoint

        operator_id = payload.get("sub")
        role = payload.get("role")
        if not operator_id:
            return await call_next(request)

        # Developer hat kein Limit
        if role == "developer":
            return await call_next(request)

        # Counter prüfen + erhöhen
        settings = get_settings()
        today = date.today()
        try:
            new_count = _increment_bucket(operator_id, today)
        except Exception:
            logger.exception("Rate-limit DB-Operation fehlgeschlagen — durchlassen")
            return await call_next(request)

        limit = settings.rate_limit_per_operator_per_day
        if new_count > limit:
            return _build_429(limit, today)

        # Headers für Sichtbarkeit beim Aufrufer
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"]     = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - new_count))
        response.headers["X-RateLimit-Reset"]     = _reset_iso(today)
        return response


def _increment_bucket(operator_id: str, day: date) -> int:
    """Atomisch: INSERT mit ON CONFLICT UPDATE count = count + 1, RETURNING count."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    with SessionLocal() as db:
        stmt = (
            pg_insert(RateLimitBucket)
            .values(operator_id=operator_id, day=day, count=1)
            .on_conflict_do_update(
                index_elements=["operator_id", "day"],
                set_={
                    "count":      RateLimitBucket.__table__.c.count + 1,
                    "updated_at": datetime.utcnow(),
                },
            )
            .returning(RateLimitBucket.__table__.c.count)
        )
        result = db.execute(stmt)
        db.commit()
        row = result.first()
        return int(row[0]) if row else 1


def _reset_iso(today: date) -> str:
    """Ende des Tages in UTC als ISO-String."""
    tomorrow = today + timedelta(days=1)
    reset = datetime.combine(tomorrow, time.min, tzinfo=timezone.utc)
    return reset.isoformat()


def _build_429(limit: int, today: date) -> JSONResponse:
    tomorrow = today + timedelta(days=1)
    reset = datetime.combine(tomorrow, time.min, tzinfo=timezone.utc)
    seconds_until_reset = max(1, int((reset - datetime.now(timezone.utc)).total_seconds()))
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Tageslimit erreicht. Wir reden morgen weiter.",
            "limit":  limit,
            "reset_at": reset.isoformat(),
        },
        headers={
            "X-RateLimit-Limit":     str(limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset":     reset.isoformat(),
            "Retry-After":           str(seconds_until_reset),
        },
    )
