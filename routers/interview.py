import os
import json
from datetime import datetime
from fastapi import APIRouter, Query
from schemas.interview import StartRequest
from services.session_store import get_result, get_session, is_configured, save_result, update_session
from services.question_loader import load_questions, load_coding_questions
from services.prompt_builder import build as build_prompt
from services.resume_service import generate_coding_question
from services.judge0_service import run_tests as judge0_run_tests
from services.evaluation_service import evaluate as evaluate_interview

router = APIRouter()


def _public_coding_question(cq: dict | None) -> dict | None:
    """Return only candidate-visible coding data; hidden tests stay server-side."""
    if not cq or not str(cq.get("problem") or "").strip():
        return None
    return {
        "id": cq.get("id"),
        "difficulty": cq.get("difficulty", 5),
        "problem": str(cq["problem"]).strip(),
        "parameters": cq.get("parameters", ["nums"]),
        "examples": cq.get("examples", []),
        "language_options": ["python", "javascript"],
    }

@router.post("/start")
async def start_interview(payload: StartRequest):
    """
    Builds the dynamic system prompt and initiates the VAPI call.
    Returns VAPI call ID, status, and the generated system prompt.
    """
    session_key = payload.resume_session_key
    role = payload.role
    duration_mins = 23
    
    # 1. Load session data
    session_data = get_session(session_key)
    if session_data is None:
        return {
            "success": False,
            "data": None,
            "error": "Invalid resume session key. Please upload a resume first."
        }
        
    
    try:
        # 2. Load preset questions for the role
        preset_questions = load_questions(role)
        opening_candidates = preset_questions + session_data.get("resume_questions", [])
        opening_question = next(
            (str(item.get("question", "")).strip() for item in opening_candidates if str(item.get("question", "")).strip()),
            f"Tell me about one technically challenging project relevant to the {role} role.",
        )
        candidate_name = session_data.get("analysis", {}).get("candidate_name", "Candidate")
        first_name = candidate_name.split()[0] if candidate_name else "Candidate"
        first_message = (
            f"Hello {first_name}. Let us begin your interview for the {role} position. "
            f"Here is your first question. {opening_question}"
        )
        
        # 3. Pre-fetch or load coding question (needed for the system prompt Part 2 description)
        coding_question = session_data.get("coding_question")
        if not coding_question:
            # Try loading preset coding question
            presets = load_coding_questions(role)
            if presets:
                coding_question = presets[0]
            else:
                try:
                    # Fallback to dynamic Groq generation
                    coding_question = generate_coding_question(session_data["analysis"], role)
                except Exception as e:
                    print(f"Failed to dynamically generate coding question for start: {e}")
                    coding_question = None
            # Cache it in the session
            update_session(session_key, {"coding_question": coding_question})
            
        # 4. Compile the system prompt
        system_prompt = build_prompt(
            role=role,
            duration_mins=duration_mins,
            resume_questions=session_data.get("resume_questions", []),
            preset_questions=preset_questions,
            resume_analysis=session_data.get("analysis", {}),
            coding_question=coding_question
        )
        
        # Print compiled prompt to terminal console for direct visibility
        print("\n==================================================")
        print("COMPILED SYSTEM PROMPT (SESSION BRIEF) FOR VAPI:")
        print("==================================================")
        print(system_prompt[:2500])
        print("... [TRUNCATED FOR CONSOLE PRINTING] ...")
        print("==================================================\n")
        
        # 5. Prepare WebRTC session metadata
        max_duration_seconds = duration_mins * 60
        call_id = f"web-{session_key}"
        update_session(session_key, {"call_id": call_id})
        
        vapi_public_key = (os.getenv("VAPI_PUBLIC_KEY") or "").strip().strip('"').strip("'")
        vapi_assistant_id = (os.getenv("VAPI_ASSISTANT_ID") or "").strip().strip('"').strip("'")
        vapi_ready = bool(
            vapi_public_key
            and vapi_assistant_id
            and not vapi_public_key.startswith("your_")
            and not vapi_assistant_id.startswith("your_")
        )
        
        return {
            "success": True,
            "data": {
                "call_id": call_id,
                "status": "prepared",
                "system_prompt": system_prompt,
                "max_duration_seconds": max_duration_seconds,
                # A browser call only uses the public key.  Never return the private key.
                "vapi_enabled": vapi_ready,
                "vapi_public_key": vapi_public_key if vapi_ready else None,
                "vapi_assistant_id": vapi_assistant_id if vapi_ready else None,
                # Vapi's Groq model catalogue is separate from direct Groq API
                # availability. Keep the realtime model independently configurable.
                "vapi_model": (os.getenv("VAPI_GROQ_MODEL") or "llama-3.1-8b-instant").strip(),
                "first_message": first_message,
                "vapi_setup_error": None if vapi_ready else (
                    "Live voice is not configured. Set VAPI_PUBLIC_KEY and "
                    "VAPI_ASSISTANT_ID in .env, then restart the server."
                ),
                "coding_question": _public_coding_question(coding_question)
            },
            "error": None
        }
        
    except Exception as e:
        print(f"Error starting interview: {e}")
        return {
            "success": False,
            "data": None,
            "error": f"An error occurred while setting up the interview call: {str(e)}"
        }

@router.get("/coding-question")
async def get_interview_coding_question(
    role: str = Query(..., description="Interview role"),
    resume_session_key: str = Query(..., description="Unique resume session key")
):
    """
    Returns the coding question assigned to the candidate.
    Uses caching and optimizes by serving preset questions first.
    """
    session_data = get_session(resume_session_key)
    if session_data is None:
        return {
            "success": False,
            "data": None,
            "error": "Invalid resume session key."
        }
        
    
    # 1. Check if already cached in session
    if "coding_question" in session_data and session_data["coding_question"]:
        cq = session_data["coding_question"]
        return {
            "success": True,
            "data": _public_coding_question(cq),
            "error": None
        }
        
    try:
        # 2. Check preset question bank first (Optimization)
        presets = load_coding_questions(role)
        if presets:
            cq = presets[0]
            print(f"Serving preset coding question for role: {role}")
        else:
            # 3. Fallback to generating dynamically via Groq
            print(f"No preset coding question found. Generating dynamically for role: {role}")
            cq = generate_coding_question(session_data.get("analysis", {}), role)
            
        # 4. Cache and return
        update_session(resume_session_key, {"coding_question": cq})
        
        return {
            "success": True,
            "data": _public_coding_question(cq),
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": f"Failed to retrieve coding question: {str(e)}"
        }

@router.post("/transcript")
async def save_interview_transcript(payload: dict):
    """
    Saves the interview transcript. Supports both VAPI webhook formats
    (end-of-call-report) and standard direct POST payloads.
    """
    # 1. Check if this is a VAPI end-of-call webhook
    is_vapi_webhook = "message" in payload and isinstance(payload["message"], dict)
    if is_vapi_webhook:
        message = payload["message"]
        event_type = message.get("type")
        
        if event_type == "end-of-call-report":
            call = message.get("call", {})
            call_id = call.get("id")
            
            # Extract metadata
            metadata = call.get("metadata", {})
            role = metadata.get("role", "Unknown")
            duration = call.get("duration", 0)
            timestamp = message.get("timestamp") or datetime.utcnow().isoformat()
            completion_reason = message.get("endedReason") or call.get("endedReason") or "vapi-end-of-call"
            # Provider end reports may represent a disconnect. The browser's
            # official timer/manual completion request is authoritative.
            completed = False
            
            # Normalize Vapi transcript messages to a clean structure
            raw_messages = message.get("artifact", {}).get("messages", [])
            transcript = []
            for msg in raw_messages:
                msg_role = msg.get("role")
                msg_content = msg.get("message") or msg.get("content")
                if msg_role and msg_content:
                    # Vapi uses 'bot'/'assistant' or 'user'/'customer'
                    normalized_role = "interviewer" if msg_role in ["bot", "assistant"] else "candidate"
                    transcript.append({
                        "role": normalized_role,
                        "content": msg_content
                    })
                    
            if not transcript and "transcript" in message.get("artifact", {}):
                # Fallback if messages list is empty but raw transcript string exists
                transcript = [{"role": "system", "content": message["artifact"]["transcript"]}]
        else:
            # Ignore other events like 'speech-started' or 'assistant-request'
            return {
                "success": True,
                "data": {
                    "saved": False,
                    "ignored": True,
                    "reason": f"Ignored event type: {event_type}"
                },
                "error": None
            }
    else:
        # 2. Standard direct payload (e.g., Postman unit tests)
        call_id = payload.get("call_id")
        transcript = payload.get("transcript", [])
        duration = payload.get("duration", 0)
        timestamp = payload.get("timestamp") or datetime.utcnow().isoformat()
        role = payload.get("role", "Unknown")
        completion_reason = payload.get("completion_reason", "manual")
        completed = bool(payload.get("completed", False))
        
    if not call_id:
        return {
            "success": False,
            "data": None,
            "error": "call_id is required."
        }
        
    # 3. Save to disk
    storage_dir = "storage/transcripts"
    os.makedirs(storage_dir, exist_ok=True)
    
    file_path = os.path.join(storage_dir, f"{call_id}.json")
    
    save_data = {
        "call_id": call_id,
        "role": role,
        "duration": duration,
        "completion_reason": completion_reason,
        "completed": completed,
        "timestamp": timestamp,
        "transcript": transcript,
        "code_result": payload.get("code_result"),
        "evaluation": payload.get("evaluation")
    }

    if is_configured():
        session_key = payload.get("resume_session_key") or (call_id[4:] if call_id.startswith("web-") else None)
        save_result(call_id, session_key, save_data)
        return {"success": True, "data": {"saved": True, "call_id": call_id}, "error": None}
    
    try:
        # Webhook and browser saves can race. Never let a delayed provider
        # webhook downgrade a timer-completed interview back to partial.
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as existing_file:
                    existing = json.load(existing_file)
                if existing.get("completed"):
                    save_data["completed"] = True
                    save_data["completion_reason"] = existing.get("completion_reason", "timer")
                for field in ("evaluation", "code_result"):
                    if save_data.get(field) is None and existing.get(field) is not None:
                        save_data[field] = existing[field]
            except (OSError, json.JSONDecodeError):
                pass
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
            
        return {
            "success": True,
            "data": {
                "saved": True,
                "call_id": call_id
            },
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": f"Failed to save transcript file: {str(e)}"
        }

@router.get("/transcript/{call_id}")
async def get_interview_transcript(call_id: str):
    """
    Fetches the saved interview transcript for the given call ID.
    """
    if is_configured():
        result = get_result(call_id)
        if result is None:
            return {"success": False, "data": None, "error": f"Transcript not found for call ID: {call_id}"}
        return {"success": True, "data": result, "error": None}
    file_path = os.path.join("storage/transcripts", f"{call_id}.json")
    
    if not os.path.exists(file_path):
        return {
            "success": False,
            "data": None,
            "error": f"Transcript not found for call ID: {call_id}"
        }
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        return {
            "success": True,
            "data": data,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": f"Failed to read transcript file: {str(e)}"
        }

@router.post("/run-code")
async def run_candidate_code(payload: dict):
    """
    Executes Python candidate code against provided test cases and returns execution output.
    """
    code = payload.get("code", "")
    session = get_session(payload.get("resume_session_key", "")) or {}
    test_cases = (session.get("coding_question") or {}).get("test_cases", [])
    
    if not code.strip():
        return {
            "success": False,
            "data": None,
            "error": "No code provided to execute."
        }
    if not test_cases:
        return {"success": False, "data": None, "error": "No server-side test cases are available for this interview."}

    try:
        judged = await judge0_run_tests(code, payload.get("language", "python"), test_cases)
        return {"success": True, "data": judged, "error": None}
    except (ValueError, RuntimeError) as exc:
        return {"success": False, "data": None, "error": str(exc)}
    except Exception as exc:
        return {"success": False, "data": None, "error": f"Judge0 execution failed: {exc}"}

@router.post("/evaluate")
async def evaluate_completed_interview(payload: dict):
    """Creates an evidence-based report after the call; never a hiring decision."""
    transcript = payload.get("transcript", [])
    if not transcript:
        return {"success": False, "data": None, "error": "A transcript is required for evaluation."}
    try:
        report = evaluate_interview(payload.get("role", "Technical"), transcript, payload.get("code", ""), payload.get("code_result", {}), payload.get("evaluation_scope", "full"))
        return {"success": True, "data": report, "error": None}
    except Exception as exc:
        return {"success": False, "data": None, "error": f"Evaluation failed: {exc}"}

