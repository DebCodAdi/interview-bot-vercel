"""Judge0-backed, isolated candidate-code execution."""
import asyncio
import json
import os
import re
from typing import Any
import httpx

LANGUAGE_IDS = {"python": 71, "javascript": 63, "java": 62, "cpp": 54}


def _source_for_test(code: str, language: str, test_input: str) -> str:
    if language == "python":
        names = re.findall(r"^\s*([A-Za-z_]\w*)\s*=", test_input, flags=re.M)
        args = ", ".join(names)
        return f"import json\n{code}\n\n{test_input}\n_result = solution({args})\nprint(json.dumps(_result) if isinstance(_result, (dict, list)) else _result)\n"
    if language == "javascript":
        names = re.findall(r"^\s*([A-Za-z_$][\w$]*)\s*=", test_input, flags=re.M)
        args = ", ".join(names)
        return f"{code}\n\n{test_input}\nconsole.log(JSON.stringify(solution({args})));\n"
    raise ValueError("Only Python and JavaScript are currently supported for function-style challenges.")


def _outputs_match(actual: str, expected: str) -> bool:
    """Compare JSON values structurally while retaining plain-text support."""
    try:
        return json.loads(actual) == json.loads(expected)
    except (TypeError, json.JSONDecodeError):
        return actual == expected


async def run_tests(code: str, language: str, test_cases: list[dict[str, Any]]) -> dict[str, Any]:
    base_url = (os.getenv("JUDGE0_API_URL") or "").rstrip("/")
    if not base_url:
        raise RuntimeError("Judge0 is not configured. Set JUDGE0_API_URL on the backend.")
    if language not in ("python", "javascript"):
        raise ValueError("Choose Python or JavaScript.")
    headers = {"Content-Type": "application/json"}
    token = os.getenv("JUDGE0_AUTH_TOKEN")
    if token:
        headers["X-Auth-Token"] = token
    submissions = [{"language_id": LANGUAGE_IDS[language], "source_code": _source_for_test(code, language, tc.get("input", ""))} for tc in test_cases]
    async with httpx.AsyncClient(timeout=20) as client:
        created = (await client.post(f"{base_url}/submissions/batch", params={"base64_encoded": "false"}, json={"submissions": submissions}, headers=headers)).raise_for_status().json()
        tokens = [item["token"] for item in created if item.get("token")]
        if len(tokens) != len(test_cases):
            raise RuntimeError("Judge0 rejected one or more test submissions.")
        results = []
        for _ in range(20):
            data = (await client.get(f"{base_url}/submissions/batch", params={"tokens": ",".join(tokens), "base64_encoded": "false", "fields": "stdout,stderr,compile_output,message,status,time,memory"}, headers=headers)).raise_for_status().json()
            results = data.get("submissions", [])
            if all((item.get("status") or {}).get("id") not in (1, 2) for item in results):
                break
            await asyncio.sleep(0.35)
    normalized = []
    for index, (result, test) in enumerate(zip(results, test_cases), 1):
        actual = (result.get("stdout") or "").strip()
        expected = str(test.get("expected_output", "")).strip()
        accepted = (result.get("status") or {}).get("id") == 3 and _outputs_match(actual, expected)
        normalized.append({"test_case": index, "actual": actual or "(no output)", "passed": accepted, "status": (result.get("status") or {}).get("description"), "error": result.get("compile_output") or result.get("stderr") or result.get("message"), "time": result.get("time"), "memory": result.get("memory")})
    return {"all_passed": bool(normalized) and all(x["passed"] for x in normalized), "results": normalized}
