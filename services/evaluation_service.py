import json
import os
from groq import Groq

MODEL = (os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b").strip()

SCORE_FIELDS = ("overall_score", "technical_score", "communication_score", "coding_score")
LIST_FIELDS = ("strengths", "gaps", "evidence", "recommended_followups")


def _normalize_report(report: dict) -> dict:
    if not isinstance(report, dict):
        raise ValueError("The evaluator did not return a JSON object.")
    normalized = {}
    for field in SCORE_FIELDS:
        try:
            normalized[field] = max(0, min(100, round(float(report.get(field, 0)))))
        except (TypeError, ValueError):
            normalized[field] = 0
    for field in LIST_FIELDS:
        value = report.get(field, [])
        if not isinstance(value, list):
            value = [value] if value else []
        normalized[field] = [str(item).strip() for item in value if str(item).strip()][:10]
    normalized["summary"] = str(report.get("summary") or "No evidence-based summary was returned.").strip()
    return normalized

def evaluate(role: str, transcript: list[dict], code: str, code_result: dict, scope: str = "full") -> dict:
    scope_instruction = {
        "technical": "Evaluate only the conversational technical interview. Ignore coding evidence and set coding_score to 0.",
        "coding": "Evaluate only the coding performance, Judge0 outcome, code quality, complexity, and coding discussion. Set technical_score to 0.",
    }.get(scope, "Evaluate the complete technical and coding interview.")
    prompt = f'''Evaluate this technical interview for a {role} role using only the supplied evidence.
EVALUATION SCOPE: {scope_instruction}
Do not infer protected traits, do not invent missing answers, and do not make a hiring decision.
Judge0 pass/fail is authoritative for functional correctness. Evaluate code quality and complexity separately.
Use these weights for overall_score: technical 40%, coding 35%, communication 25%.
If evidence is missing, say so and lower confidence rather than guessing.
Return strict JSON with exactly: overall_score (0-100), technical_score (0-100), communication_score (0-100), coding_score (0-100), strengths (array), gaps (array), evidence (array of short observations tied to an answer or judge result), recommended_followups (array), summary (string).
TRANSCRIPT={json.dumps(transcript, ensure_ascii=False)}
CODE={code[:12000]}
JUDGE0={json.dumps(code_result, ensure_ascii=False)}'''
    response = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(model=MODEL, messages=[{"role":"system","content":"You are a calibrated technical-interview evaluator. Be evidence-based and fair."},{"role":"user","content":prompt}], response_format={"type":"json_object"}, reasoning_effort="low", max_completion_tokens=2048)
    return _normalize_report(json.loads(response.choices[0].message.content))
