"""Seed Supabase question_bank from the repository's questions.json.

Run locally only. SUPABASE_SERVICE_ROLE_KEY must never be sent to the browser
or committed to Git.
"""
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


def rows_from_question_file() -> list[dict]:
    source = json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))
    rows: list[dict] = []
    for role, questions in source.get("topics", {}).items():
        for item in questions:
            rows.append({
                "id": item["id"],
                "role": role,
                "question_type": "technical",
                "topic": ", ".join(item.get("concepts", [])),
                "difficulty": item.get("difficulty", 5),
                "question": item["question"],
                "key_concepts": item.get("concepts", []),
                "follow_up_hints": item.get("follow_up_hints", []),
                "parameters": [],
                "examples": [],
                "test_cases": [],
                "language_options": ["python", "javascript"],
            })
    for role, questions in source.get("coding", {}).items():
        for item in questions:
            rows.append({
                "id": item["id"],
                "role": role,
                "question_type": "coding",
                "topic": ", ".join(item.get("concepts", [])),
                "difficulty": item.get("difficulty", 5),
                "question": item["problem"],
                "key_concepts": item.get("concepts", []),
                "follow_up_hints": [],
                "parameters": item.get("parameters", []),
                "examples": item.get("examples", []),
                "test_cases": item.get("test_cases", []),
                "language_options": item.get("language_options", ["python", "javascript"]),
            })
    return rows


def main() -> None:
    load_dotenv(ROOT / ".env")
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not service_key:
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env before seeding.")

    rows = rows_from_question_file()
    response = httpx.post(
        f"{url}/rest/v1/question_bank?on_conflict=id",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
        json=rows,
        timeout=30,
    )
    if response.is_error:
        raise SystemExit(
            f"SUPABASE_SEED_FAILED: HTTP {response.status_code}\n{response.text}"
        )
    print(f"SUPABASE_SEED_OK: {len(response.json())} question rows upserted.")


if __name__ == "__main__":
    main()
