"""Anonymous interview persistence backed by Supabase in production."""
import os
from typing import Any

import httpx

# Allows local tests without Supabase. Never used when production credentials exist.
session_db: dict[str, dict[str, Any]] = {}


def _config() -> tuple[str, str] | None:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    return (url, key) if url and key else None


def is_configured() -> bool:
    return _config() is not None


def _request(method: str, table: str, *, params=None, payload=None) -> httpx.Response:
    config = _config()
    if not config:
        raise RuntimeError("Supabase is not configured")
    url, key = config
    response = httpx.request(method, f"{url}/rest/v1/{table}", headers={"apikey": key, "Content-Type": "application/json", "Prefer": "return=representation,resolution=merge-duplicates"}, params=params, json=payload, timeout=15)
    response.raise_for_status()
    return response


def _from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {"role": row["role"], "candidate_name": row.get("candidate_name") or "Candidate", "analysis": row.get("analysis") or {}, "resume_questions": row.get("resume_questions") or [], "coding_question": row.get("coding_question"), "selected_question_ids": row.get("selected_question_ids") or [], "call_id": row.get("call_id")}


def get_session(session_key: str) -> dict[str, Any] | None:
    if not _config():
        return session_db.get(session_key)
    rows = _request("GET", "interview_sessions", params={"session_key": f"eq.{session_key}", "select": "*", "limit": "1"}).json()
    return _from_row(rows[0]) if rows else None


def save_session(session_key: str, data: dict[str, Any]) -> None:
    if not _config():
        session_db[session_key] = data
        return
    row = {"session_key": session_key, "role": data["role"], "candidate_name": data.get("candidate_name"), "analysis": data.get("analysis", {}), "resume_questions": data.get("resume_questions", []), "coding_question": data.get("coding_question"), "selected_question_ids": data.get("selected_question_ids", []), "call_id": data.get("call_id")}
    _request("POST", "interview_sessions", params={"on_conflict": "session_key"}, payload=row)


def update_session(session_key: str, changes: dict[str, Any]) -> dict[str, Any] | None:
    current = get_session(session_key)
    if current is None:
        return None
    current.update(changes)
    save_session(session_key, current)
    return current


def save_result(call_id: str, session_key: str | None, payload: dict[str, Any]) -> None:
    if not _config():
        return
    row = {"call_id": call_id, "session_key": session_key, "role": payload.get("role", "Unknown"), "transcript": payload.get("transcript", []), "code_result": payload.get("code_result"), "evaluation": payload.get("evaluation"), "completion_reason": payload.get("completion_reason"), "duration_seconds": payload.get("duration", 0)}
    _request("POST", "interview_results", params={"on_conflict": "call_id"}, payload=row)


def get_result(call_id: str) -> dict[str, Any] | None:
    if not _config():
        return None
    rows = _request("GET", "interview_results", params={"call_id": f"eq.{call_id}", "select": "*", "limit": "1"}).json()
    return rows[0] if rows else None
