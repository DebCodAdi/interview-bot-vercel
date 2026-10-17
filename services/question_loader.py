"""Question bank access.

Supabase is the production source of truth. The bundled questions.json is a
local-development fallback so the app can still be tested without credentials.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import httpx


ROLE_MAP = {
    "Software Engineer": "software_engineer",
    "Data Engineer": "data_engineer",
    "Machine Learning Engineer": "ml_engineer",
    "Full Stack Developer": "fullstack_developer",
}


def get_role_key(role: str) -> str:
    if role in ROLE_MAP.values():
        return role
    for name, key in ROLE_MAP.items():
        if name.lower() == role.lower():
            return key
    return role.lower().replace(" ", "_")


def _supabase_config() -> tuple[str, str] | None:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    return (url, key) if url and key else None


def _supabase_rows(role: str, question_type: str) -> list[dict[str, Any]] | None:
    config = _supabase_config()
    if not config:
        return None
    url, key = config
    try:
        response = httpx.get(
            f"{url}/rest/v1/question_bank",
            headers={"apikey": key},
            params={
                "select": "id,role,question_type,topic,difficulty,question,key_concepts,follow_up_hints,parameters,examples,test_cases,language_options",
                "role": f"eq.{get_role_key(role)}",
                "question_type": f"eq.{question_type}",
                "is_active": "eq.true",
                "order": "difficulty.asc",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as error:
        print(f"Supabase question-bank lookup failed: {error}")
        return None


def _local_data() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "questions.json"
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_questions(role: str) -> List[Dict[str, Any]]:
    rows = _supabase_rows(role, "technical")
    if rows is not None:
        return [
            {
                "id": row["id"],
                "difficulty": row.get("difficulty", 5),
                "question": row["question"],
                "concepts": row.get("key_concepts", []),
                "follow_up_hints": row.get("follow_up_hints", []),
            }
            for row in rows
        ]
    try:
        questions = _local_data().get("topics", {}).get(get_role_key(role), [])
        return sorted(questions, key=lambda item: item.get("difficulty", 5))
    except Exception as error:
        print(f"Local technical question-bank lookup failed: {error}")
        return []


def load_coding_questions(role: str) -> List[Dict[str, Any]]:
    rows = _supabase_rows(role, "coding")
    if rows is not None:
        return [
            {
                "id": row["id"],
                "difficulty": row.get("difficulty", 5),
                "parameters": row.get("parameters", []),
                "problem": row["question"],
                "examples": row.get("examples", []),
                "test_cases": row.get("test_cases", []),
                "concepts": row.get("key_concepts", []),
                "language_options": row.get("language_options", ["python", "javascript"]),
            }
            for row in rows
        ]
    try:
        return _local_data().get("coding", {}).get(get_role_key(role), [])
    except Exception as error:
        print(f"Local coding question-bank lookup failed: {error}")
        return []
