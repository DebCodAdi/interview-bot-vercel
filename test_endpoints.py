import os
import shutil
import json
from fastapi.testclient import TestClient
from main import app
from services.session_store import session_db

client = TestClient(app)

def run_tests():
    print("==================================================")

    # ------------------------------------------------
    # TEST 0: Frontend lifecycle regression guards
    # ------------------------------------------------
    print("\n[Test 0] Frontend timer/Vapi lifecycle invariants...")
    frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
    with open(frontend_path, "r", encoding="utf-8") as frontend_file:
        frontend = frontend_file.read()
    assert "timerDeadlineMs = Date.now() + (totalSeconds * 1000)" in frontend
    assert "const runId = ++interviewRunId" in frontend
    assert "if (runId !== interviewRunId) return" in frontend
    assert "if (codingTransitionRequested && !codingModeActive) enterCodingRound()" in frontend
    assert "retrying plain start(assistantId)" not in frontend
    assert "currentSession.code_result = null" in frontend
    assert "FINAL CODE SUBMISSION:" in frontend
    assert "Recommended for Hire" not in frontend
    assert "Overall Score: 8.5 / 10" not in frontend
    assert "function resetCodingWorkspaceUI()" in frontend
    assert 'classList.remove("coding-mode", "split-view")' in frontend
    assert 'editorPane.style.display = "none"' in frontend
    assert 'const codingQuestion = startData.data.coding_question' in frontend
    assert 'const codingRequest = fetch(`/interview/coding-question' not in frontend
    assert "beginBackgroundEvaluation();" in frontend
    assert "finalEvaluationPromise()" in frontend
    launch_reset_block = frontend.split("async function startInterviewStudio()", 1)[1].split("showToast(\"Preparing questions", 1)[0]
    assert "resetCodingWorkspaceUI();" in launch_reset_block
    transition_block = frontend.split("function transitionToCodingOnSchedule()", 1)[1].split("// Add message to transcript", 1)[0]
    delayed_block = transition_block.split("codingTransitionFallbackTimer = setTimeout", 1)[1]
    assert "enterCodingRound();" not in delayed_block.split("}, 12000)", 1)[0]
    print("[OK] Fresh-run timer, stale-event guard, audio-led coding transition, and safe Vapi startup verified.")
    print("STARTING FASTAPI ENDPOINTS TESTS (TestClient)")
    print("==================================================")
    
    # ------------------------------------------------
    # TEST 1: Health Check
    # ------------------------------------------------
    print("\n[Test 1] GET / (Health Check)...")
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "ai-engine"
    print("[OK] Health Check Passed:", data)
    
    # ------------------------------------------------
    # TEST 2: Supported Roles
    # ------------------------------------------------
    print("\n[Test 2] GET /resume/roles...")
    res = client.get("/resume/roles")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Software Engineer" in data["data"]["roles"]
    assert "Data Engineer" in data["data"]["roles"]
    print("[OK] Supported Roles Passed:", data["data"]["roles"])
    
    # ------------------------------------------------
    # TEST 3: Resume Upload (using a real PDF from Downloads if available)
    # ------------------------------------------------
    print("\n[Test 3] POST /resume/upload...")
    downloads_pdf_win = "C:\\Users\\adity\\Downloads\\AdiRes12.pdf"
    downloads_pdf_linux = "/home/aditya/Downloads/AdiRes12.pdf"
    ruhani_pdf_win = "C:\\Users\\adity\\VMWork\\Ruhani Sachdeva.pdf"
    ruhani_pdf_linux = "/home/aditya/VMWork/Ruhani Sachdeva.pdf"
    ruhani_pdf_rel = "../Ruhani Sachdeva.pdf"
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    sample_pdf = os.path.join(curr_dir, "sample_resume.pdf")
    local_pdf = os.path.join(curr_dir, "test_resume.pdf")
    
    # Resolve the path dynamically based on OS and availability
    pdf_paths = [
        sample_pdf,
        ruhani_pdf_rel,
        ruhani_pdf_win,
        ruhani_pdf_linux,
        downloads_pdf_win,
        downloads_pdf_linux
    ]
    
    downloads_pdf = None
    for path in pdf_paths:
        if os.path.exists(path):
            downloads_pdf = path
            break
        
    # Copy file if it exists, otherwise create a minimal mock PDF file structure
    if downloads_pdf:
        print(f"Using resume PDF from {downloads_pdf}...")
        if os.path.abspath(downloads_pdf) != os.path.abspath(local_pdf):
            shutil.copy(downloads_pdf, local_pdf)
    else:
        print("Real PDF not found. Creating a valid mock PDF file...")
        pdf_body = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >> endobj\n"
            b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
            b"5 0 obj << /Length 55 >> stream\nBT /F1 12 Tf 72 712 Td (Aditya Kumar - Python Engineer) Tj ET\nendstream endobj\n"
        )
        p1 = 9
        p2 = pdf_body.find(b"2 0 obj")
        p3 = pdf_body.find(b"3 0 obj")
        p4 = pdf_body.find(b"4 0 obj")
        p5 = pdf_body.find(b"5 0 obj")
        xref_offset = len(pdf_body)
        xref_table = (
            f"xref\n0 6\n"
            f"0000000000 65535 f \n"
            f"{p1:010d} 00000 n \n"
            f"{p2:010d} 00000 n \n"
            f"{p3:010d} 00000 n \n"
            f"{p4:010d} 00000 n \n"
            f"{p5:010d} 00000 n \n"
            f"trailer << /Size 6 /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
        with open(local_pdf, "wb") as f:
            f.write(pdf_body + xref_table)
            
    try:
        with open(local_pdf, "rb") as f:
            res = client.post(
                "/resume/upload",
                files={"file": (local_pdf, f, "application/pdf")},
                data={"role": "Data Engineer"}
            )
            
        assert res.status_code == 200
        data = res.json()
        if not data["success"]:
            print("ERROR: Resume upload failed. Response:")
            print(json.dumps(data, indent=2))
            print("\nTIP: If text extraction failed on the mock PDF, please place any real technical PDF resume")
            print("     named 'test_resume.pdf' in this folder and run tests again.")
        assert data["success"] is True
        session_key = data["data"]["session_key"]
        candidate_name = data["data"]["candidate_name"]
        assert session_key is not None
        print(f"[OK] Resume Upload Passed. Session Key: {session_key}, Candidate: {candidate_name}")
        
        # Verify it was added to in-memory session_db
        assert session_key in session_db
        print("[OK] Session Cached in session_db:", list(session_db.keys()))
        
        # ------------------------------------------------
        # TEST 4: Start Interview Call
        # ------------------------------------------------
        print("\n[Test 4] POST /interview/start...")
        start_payload = {
            "role": "Data Engineer",
            "duration_mins": 23,
            "resume_session_key": session_key
        }
        res = client.post("/interview/start", json=start_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        call_id = data["data"]["call_id"]
        status = data["data"]["status"]
        assert call_id is not None
        print(f"[OK] Start Interview Passed. Call ID: {call_id}, Status: {status}")
        
        # Verify the prompt builder compiled the prompt successfully
        system_prompt = data["data"]["system_prompt"]
        assert "SESSION BRIEF" in system_prompt
        assert "DYNAMIC QUESTIONING ENGINE" in system_prompt
        assert data["data"]["coding_question"]["problem"]
        assert "test_cases" not in data["data"]["coding_question"]
        print("[OK] System Prompt Compiled Successfully (Length:", len(system_prompt), ")")
        
        # ------------------------------------------------
        # TEST 5: Get Coding Question
        # ------------------------------------------------
        print("\n[Test 5] GET /interview/coding-question...")
        res = client.get(f"/interview/coding-question?role=Data+Engineer&resume_session_key={session_key}")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "problem" in data["data"]
        assert data["data"]["parameters"] == ["nums"]
        assert set(data["data"]["language_options"]) == {"python", "javascript"}
        assert len(data["data"]["examples"]) >= 1
        print("[OK] Coding Question Retrieve Passed. Problem statement:")
        print("  ", data["data"]["problem"][:100] + "...")
        print("   Visible examples count:", len(data["data"]["examples"]))

        # ------------------------------------------------
        # TEST 5B: Execute a real solution through Judge0
        # ------------------------------------------------
        code_result = {}
        if os.getenv("JUDGE0_API_URL"):
            print("\n[Test 5B] POST /interview/run-code (Real Judge0 CE execution)...")
            solution = """def solution(nums):
    best = current = nums[0]
    for number in nums[1:]:
        current = max(number, current + number)
        best = max(best, current)
    return best
"""
            res = client.post("/interview/run-code", json={
                "code": solution,
                "language": "python",
                "resume_session_key": session_key
            })
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True, data
            assert data["data"]["all_passed"] is True, data
            assert len(data["data"]["results"]) == 3
            code_result = data["data"]
            print("[OK] Judge0 accepted all 3 hidden test cases.")
        else:
            print("\n[Test 5B] SKIPPED: JUDGE0_API_URL is not configured.")
        
        # ------------------------------------------------
        # TEST 6: Save Transcript (VAPI Webhook Event Simulate)
        # ------------------------------------------------
        print("\n[Test 6] POST /interview/transcript (Simulate VAPI End-Of-Call Webhook)...")
        webhook_payload = {
            "message": {
                "type": "end-of-call-report",
                "call": {
                    "id": call_id,
                    "duration": 150,
                    "metadata": {
                        "role": "Data Engineer",
                        "resume_session_key": session_key
                    }
                },
                "artifact": {
                    "transcript": "Hello, welcome. Thank you.",
                    "messages": [
                        {"role": "assistant", "message": "What is partition skew?"},
                        {"role": "user", "message": "It is when one partition has way more data than others."}
                    ]
                },
                "timestamp": "2026-06-12T17:40:00Z"
            }
        }
        res = client.post("/interview/transcript", json=webhook_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["saved"] is True
        print(f"[OK] Webhook Transcript Save Passed for Call ID: {call_id}")
        
        # Verify file exists on disk
        transcript_file = f"storage/transcripts/{call_id}.json"
        assert os.path.exists(transcript_file)
        with open(transcript_file, "r", encoding="utf-8") as saved_file:
            saved_webhook = json.load(saved_file)
        assert saved_webhook["completed"] is False
        assert saved_webhook["completion_reason"] == "vapi-end-of-call"
        print("[OK] Transcript File saved to disk at:", transcript_file)

        # Mark the same interview complete from the authoritative browser timer,
        # then replay the webhook to verify it cannot downgrade final state.
        final_payload = {
            "call_id": call_id,
            "role": "Data Engineer",
            "duration": 300,
            "completion_reason": "timer",
            "completed": True,
            "timestamp": "2026-06-12T17:45:00Z",
            "transcript": [
                {"role": "interviewer", "content": "What is partition skew?"},
                {"role": "candidate", "content": "It is when one partition has much more data than others."}
            ]
        }
        assert client.post("/interview/transcript", json=final_payload).json()["success"] is True
        assert client.post("/interview/transcript", json=webhook_payload).json()["success"] is True
        with open(transcript_file, "r", encoding="utf-8") as saved_file:
            saved_after_race = json.load(saved_file)
        assert saved_after_race["completed"] is True
        assert saved_after_race["completion_reason"] == "timer"
        print("[OK] Delayed webhook cannot downgrade a completed interview.")
        
        # ------------------------------------------------
        # TEST 7: Save Transcript (Manual Direct Post)
        # ------------------------------------------------
        print("\n[Test 7] POST /interview/transcript (Manual Direct Post)...")
        manual_payload = {
            "call_id": "manual-test-call-999",
            "role": "Software Engineer",
            "duration": 90,
            "completion_reason": "timer",
            "completed": True,
            "timestamp": "2026-06-12T17:45:00Z",
            "transcript": [
                {"role": "interviewer", "content": "Tell me about memory leaks."},
                {"role": "candidate", "content": "Closures holding references can cause them."}
            ],
            "code_result": {"all_passed": True, "results": []},
            "evaluation": {"overall_score": 75, "summary": "Evidence-backed test report."}
        }
        res = client.post("/interview/transcript", json=manual_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        with open("storage/transcripts/manual-test-call-999.json", "r", encoding="utf-8") as saved_file:
            saved_manual = json.load(saved_file)
        assert saved_manual["completed"] is True
        assert saved_manual["completion_reason"] == "timer"
        assert saved_manual["evaluation"]["overall_score"] == 75
        assert saved_manual["code_result"]["all_passed"] is True
        print("[OK] Manual Transcript Save Passed.")
        
        # ------------------------------------------------
        # TEST 8: Fetch Transcript
        # ------------------------------------------------
        print("\n[Test 8] GET /interview/transcript/{call_id}...")
        res = client.get(f"/interview/transcript/{call_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["call_id"] == call_id
        assert data["data"]["role"] == "Data Engineer"
        assert len(data["data"]["transcript"]) == 2
        assert data["data"]["transcript"][1]["role"] == "candidate"
        print("[OK] Fetch Transcript Passed. Content verified.")
        
        # Test 404
        res = client.get("/interview/transcript/non-existent-id")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert "not found" in data["error"].lower()
        print("[OK] Fetch Transcript 404 Handling Passed.")

        # ------------------------------------------------
        # TEST 9: Evidence-based Groq evaluation
        # ------------------------------------------------
        if os.getenv("GROQ_API_KEY"):
            print("\n[Test 9] POST /interview/evaluate (Real Groq evaluation)...")
            res = client.post("/interview/evaluate", json={
                "role": "Data Engineer",
                "transcript": final_payload["transcript"],
                "code": solution if os.getenv("JUDGE0_API_URL") else "",
                "code_result": code_result
            })
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True, data
            assert 0 <= data["data"]["overall_score"] <= 100
            assert isinstance(data["data"]["evidence"], list)
            assert set(data["data"]) == {
                "overall_score", "technical_score", "communication_score", "coding_score",
                "strengths", "gaps", "evidence", "recommended_followups", "summary"
            }
            print("[OK] Groq evaluation returned a structured evidence-based report.")
        else:
            print("\n[Test 9] SKIPPED: GROQ_API_KEY is not configured.")
        
    finally:
        # Cleanup local test files
        if os.path.exists(local_pdf):
            os.remove(local_pdf)
            
    print("\n==================================================")
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
