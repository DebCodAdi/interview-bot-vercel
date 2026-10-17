"""Standalone live coding interview APIs.

This router intentionally owns a separate session store so the coding studio can
be tested and evolved without depending on resume-upload or interview state.
"""
import os
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from services.evaluation_service import evaluate as evaluate_interview
from services.judge0_service import run_tests as judge0_run_tests
from services.question_loader import load_coding_questions

router = APIRouter()
coding_sessions: dict[str, dict[str, Any]] = {}


def _all_questions() -> list[dict[str, Any]]:
    roles = ["Software Engineer", "Data Engineer", "Machine Learning Engineer", "Full Stack Developer"]
    questions: list[dict[str, Any]] = []
    for role in roles:
        for question in load_coding_questions(role):
            item = dict(question)
            item["role"] = role
            questions.append(item)
    return questions


def _public_question(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": question.get("id"),
        "role": question.get("role"),
        "difficulty": question.get("difficulty", 5),
        "problem": question.get("problem"),
        "parameters": question.get("parameters", ["nums"]),
        "examples": question.get("examples", []),
        "language_options": ["python", "javascript"],
    }


def _coding_prompt(question: dict[str, Any], duration_seconds: int) -> str:
    examples = "\n\n".join(
        f"Example {index}: Input: {example.get('input')} Output: {example.get('output')}"
        for index, example in enumerate(question.get("examples", []), 1)
    )
    return f"""You are a fair, concise senior software interviewer conducting a live coding interview.
The candidate has {duration_seconds // 60} minutes. Ask exactly one question at a time.

Start by saying exactly: "Now let's move to a coding challenge."
Then read the problem and visible examples below clearly. Say: "Take your time to code your solution."
After that, stay silent while the candidate codes. Answer only direct clarification questions.
You will receive silent messages named CODING MODE UPDATE with editor snapshots. Do not respond to them.
When you receive CODING CHECKPOINT, inspect the latest snapshot and ask exactly one concise question about the apparent approach, complexity, invariant, or edge case. There can be more than one checkpoint during the session, but ask only one question per checkpoint. Do not give hints or feedback.
When you receive FINAL CODE SUBMISSION, ask exactly one concise question about correctness or complexity. Never reveal hidden tests or pass/fail results.

CODING PROBLEM:
{question.get('problem')}

VISIBLE EXAMPLES:
{examples}
"""


@router.get("/questions")
async def list_questions():
    return {"success": True, "data": [_public_question(q) for q in _all_questions()], "error": None}


@router.post("/start")
async def start_coding_session(payload: dict):
    question_id = payload.get("question_id")
    duration_mins = 20
    question = next((q for q in _all_questions() if q.get("id") == question_id), None)
    if not question:
        raise HTTPException(status_code=404, detail="Coding question not found.")

    session_id = str(uuid.uuid4())
    coding_sessions[session_id] = {"question": question, "transcript": []}
    public_key = (os.getenv("VAPI_PUBLIC_KEY") or "").strip().strip('"').strip("'")
    assistant_id = (os.getenv("VAPI_ASSISTANT_ID") or "").strip().strip('"').strip("'")
    vapi_enabled = bool(public_key and assistant_id and not public_key.startswith("your_") and not assistant_id.startswith("your_"))
    return {
        "success": True,
        "data": {
            "session_id": session_id,
            "question": _public_question(question),
            "duration_seconds": duration_mins * 60,
            "system_prompt": _coding_prompt(question, duration_mins * 60),
            "vapi_public_key": public_key if vapi_enabled else None,
            "vapi_assistant_id": assistant_id if vapi_enabled else None,
        },
        "error": None,
    }


@router.post("/run")
async def run_code(payload: dict):
    session = coding_sessions.get(payload.get("session_id", ""))
    if not session:
        raise HTTPException(status_code=404, detail="Coding session not found.")
    code = str(payload.get("code") or "")
    if not code.strip():
        return {"success": False, "data": None, "error": "Write a solution before running tests."}
    try:
        result = await judge0_run_tests(code, payload.get("language", "python"), session["question"].get("test_cases", []))
        session["code"] = code
        session["language"] = payload.get("language", "python")
        session["code_result"] = result
        return {"success": True, "data": result, "error": None}
    except (ValueError, RuntimeError) as error:
        return {"success": False, "data": None, "error": str(error)}


@router.post("/evaluate")
async def evaluate_coding_session(payload: dict):
    session = coding_sessions.get(payload.get("session_id", ""))
    if not session:
        raise HTTPException(status_code=404, detail="Coding session not found.")
    transcript = payload.get("transcript") or session.get("transcript") or []
    if not transcript:
        return {"success": False, "data": None, "error": "A coding transcript is required."}
    try:
        report = evaluate_interview(
            session["question"].get("role", "Software Engineer"),
            transcript,
            payload.get("code", session.get("code", "")),
            payload.get("code_result", session.get("code_result", {})),
        )
        return {"success": True, "data": report, "error": None}
    except Exception as error:
        return {"success": False, "data": None, "error": f"Evaluation failed: {error}"}
