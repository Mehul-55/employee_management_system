"""
FastAPI layer for the Employee Management System.

Run with:
    uvicorn api_main:app --reload
"""

from time import perf_counter
from time import time
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import auth_model
import audit_log
import db_config
import db_indexes
from app_time import today_iso


app = FastAPI(
    title="Employee Management System API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CACHE_TTL_SECONDS = 10
_cache = {}


def _cache_get(key):
    item = _cache.get(key)
    if not item:
        return None
    if time() - item["stored_at"] > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return item["value"]


def _cache_set(key, value):
    _cache[key] = {
        "stored_at": time(),
        "value": value,
    }
    return value


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class EmployeeLoginRequest(BaseModel):
    emp_id: int
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    success: bool
    role: str
    user_id: str
    name: Optional[str] = None
    message: str
    elapsed_ms: int


@app.on_event("startup")
def warm_database_connection():
    try:
        db_config.client.admin.command("ping")
        created = db_indexes.ensure_indexes()
        auth_model.employees_col.find_one({}, {"_id": 1})
        print(f"[API] Warmed {db_config.connection_label()} connection.")
        print(f"[API] Ensured {len(created)} MongoDB indexes.")
    except Exception as exc:
        print(f"[API WARNING] Database warmup failed: {exc}")


@app.get("/api/health")
def health_check():
    try:
        db_config.client.admin.command("ping")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {exc}",
        )

    return {
        "success": True,
        "database": db_config.DB_NAME,
        "connection": db_config.connection_label(),
        "message": "API and database are healthy",
    }


@app.get("/api/dashboard/admin-summary")
def admin_dashboard_summary(audit_limit: int = 25, important_only: bool = False):
    started = perf_counter()
    cache_key = ("admin-summary", audit_limit, important_only)
    cached = _cache_get(cache_key)
    if cached:
        elapsed_ms = int((perf_counter() - started) * 1000)
        response = dict(cached)
        response["cached"] = True
        response["elapsed_ms"] = elapsed_ms
        print(f"[API] admin dashboard summary served from cache in {elapsed_ms} ms")
        return response

    employees = auth_model.get_all_employees()
    employees.sort(key=lambda item: int(item["id"]) if str(item["id"]).isdigit() else 0)

    today = today_iso()
    logs = audit_log.get_recent_logs(
        limit=max(1, min(audit_limit, 100)),
        important_only=important_only,
    )
    elapsed_ms = int((perf_counter() - started) * 1000)
    print(f"[API] admin dashboard summary completed in {elapsed_ms} ms")

    return _cache_set(cache_key, {
        "success": True,
        "cached": False,
        "stats": {
            "total_employees": len(employees),
            "active_accounts": sum(1 for item in employees if not item.get("deleted")),
            "registered_today": sum(
                1 for item in employees
                if str(item.get("created_at", "")).startswith(today)
            ),
        },
        "recent_employees": employees[:6],
        "audit_logs": logs,
        "elapsed_ms": elapsed_ms,
    })


@app.get("/api/audit-logs")
def audit_logs(limit: int = 100, important_only: bool = False):
    started = perf_counter()
    cache_key = ("audit-logs", limit, important_only)
    cached = _cache_get(cache_key)
    if cached:
        elapsed_ms = int((perf_counter() - started) * 1000)
        response = dict(cached)
        response["cached"] = True
        response["elapsed_ms"] = elapsed_ms
        print(f"[API] audit logs served from cache in {elapsed_ms} ms")
        return response

    logs = audit_log.get_recent_logs(
        limit=max(1, min(limit, 200)),
        important_only=important_only,
    )
    elapsed_ms = int((perf_counter() - started) * 1000)
    print(f"[API] audit logs completed in {elapsed_ms} ms")
    return _cache_set(cache_key, {
        "success": True,
        "cached": False,
        "logs": logs,
        "elapsed_ms": elapsed_ms,
    })


@app.post("/api/auth/admin-login", response_model=LoginResponse)
def admin_login(payload: LoginRequest):
    started = perf_counter()
    ok, role, message = auth_model.admin_login(
        payload.username.strip(),
        payload.password,
    )
    elapsed_ms = int((perf_counter() - started) * 1000)
    print(f"[API] admin-login completed in {elapsed_ms} ms")

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
        )

    return {
        "success": True,
        "role": role,
        "user_id": payload.username.strip(),
        "name": "Admin",
        "message": "Login successful",
        "elapsed_ms": elapsed_ms,
    }


@app.post("/api/auth/employee-login", response_model=LoginResponse)
def employee_login(payload: EmployeeLoginRequest):
    started = perf_counter()
    ok, emp_id, message = auth_model.employee_login(
        payload.emp_id,
        payload.password,
    )
    elapsed_ms = int((perf_counter() - started) * 1000)
    print(f"[API] employee-login completed in {elapsed_ms} ms")

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
        )

    return {
        "success": True,
        "role": "employee",
        "user_id": str(emp_id),
        "name": message,
        "message": "Login successful",
        "elapsed_ms": elapsed_ms,
    }
