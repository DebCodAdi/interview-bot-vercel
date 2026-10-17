# AI Engine — Detailed Implementation & Testing Plan

---

## PART 1: WHAT TO BUILD

---

### STEP 1 — supabase_service.py (Start Here)
**Location:** `services/supabase_service.py`
**Why first:** Everything else depends on this

```python
from supabase import create_client
import os

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# 1. Get resume text
def get_resume(user_id: str) -> str:
    result = supabase.table("resumes") \
                     .select("resume_text") \
                     .eq("user_id", user_id) \
                     .execute()
    return result.data[0]["resume_text"] if result.data else None

# 2. Get preset questions by role
def get_preset_questions(role: str) -> list:
    result = supabase.table("preset_questions") \
                     .select("*") \
                     .eq("role", role) \
                     .execute()
    return result.data

# 3. Save evaluation per question
def save_evaluation(data: dict):
    supabase.table("evaluations").insert(data).execute()

# 4. Save overall interview summary
def save_summary(data: dict):
    supabase.table("interview_summary").insert(data).execute()

# 5. Get all interview summaries for a user
def get_evaluations(user_id: str) -> list:
    result = supabase.table("interview_summary") \
                     .select("*") \
                     .eq("user_id", user_id) \
                     .execute()
    return result.data

# 6. Get per-question detail for single interview
def get_interview_detail(user_id: str, interview_id: str) -> list:
    result = supabase.table("evaluations") \
                     .select("*") \
                     .eq("user_id", user_id) \
                     .eq("interview_id", interview_id) \
                     .execute()
    return result.data

# 7. Get single interview summary
def get_summary(user_id: str, interview_id: str) -> dict:
    result = supabase.table("interview_summary") \
                     .select("*") \
                     .eq("user_id", user_id) \
                     .eq("interview_id", interview_id) \
                     .execute()
    return result.data[0] if result.data else None
```

**When done verify:**
```
□ Can fetch resume using user_id
□ Can fetch preset questions by role
□ Can save evaluation data
□ Can fetch evaluation data back
□ Can fetch summary back
```

---

### STEP 2 — question_loader.py (Remove JSON, Add No-Repetition Filtering)
**Location:** `services/question_loader.py`
**Change:** Remove questions.json + all 7 fallback paths, add no-repetition filter for preset questions

```python
# REMOVE all of this
# json_paths = [path1, path2, path3 ... path7]
# with open(path) as f: ...

# REPLACE WITH
from services.supabase_service import get_preset_questions

def load_preset_questions(role: str, asked_preset_ids: list = None) -> list:
    # Safe default — never use mutable default argument []
    if asked_preset_ids is None:
        asked_preset_ids = []

    all_questions = get_preset_questions(role)

    if not all_questions:
        raise Exception(f"No preset questions found for role: {role}")

    # Empty list → first interview, no history → return all (no filtering needed)
    if not asked_preset_ids:
        return all_questions

    # Filter out already-asked preset questions using their IDs (no repetition)
    unused = [q for q in all_questions if q["id"] not in asked_preset_ids]

    # All presets exhausted → full cycle reset, return all again
    return unused if unused else all_questions
```

**Key behaviours:**
- `asked_preset_ids = []` → returns all questions, no crash, no filtering (first interview)
- `asked_preset_ids = ["se_002", "se_005"]` → filters those IDs out, no repetition
- All IDs exhausted → resets and returns full list (cycle restart)
- Uses `None` default (not `[]`) to avoid Python mutable default argument bug

**When done verify:**
```
□ No reference to questions.json anywhere
□ No file path strings in code
□ Empty asked_preset_ids list → returns all questions, no crash
□ None passed → treated same as empty, no crash
□ With asked_preset_ids → already-asked IDs filtered out correctly
□ All IDs exhausted → resets and returns all (no empty result)
```

---

### STEP 3 — resume_service.py (Add Question Generation)
**Location:** `services/resume_service.py`
**Change:** Keep extract_text + analyse_resume unchanged, add generate_resume_questions

```python
# KEEP these unchanged
def extract_text(pdf_path): ...
def analyse_resume(resume_text): ...

# ADD this new function
async def generate_resume_questions(
    resume_text: str,
    preset_questions: list,
    asked_resume_questions: list = None   # None → treated as empty → generates freely, no crash
) -> list:
    # Safe default — never use mutable default argument []
    if asked_resume_questions is None:
        asked_resume_questions = []
    
    # Extract concepts from ALL presets to avoid topic overlap
    preset_concepts = []
    for q in preset_questions:
        preset_concepts.extend(q.get("concepts", []))
    
    # Only add repetition instruction if list has data
    repetition_instruction = ""
    if asked_resume_questions:
        repetition_instruction = f"""
        These resume questions were already asked in previous interviews.
        DO NOT repeat them:
        {asked_resume_questions}
        """
    
    # Only add concept instruction if presets exist
    concept_instruction = ""
    if preset_concepts:
        concept_instruction = f"""
        These concepts are already covered by preset questions.
        DO NOT generate questions about these concepts:
        {preset_concepts}
        """
    
    prompt = f"""
    You are a technical interviewer.
    
    Candidate Resume:
    {resume_text}
    
    {repetition_instruction}
    
    {concept_instruction}
    
    Generate exactly 5 unique technical questions based ONLY on:
    - Specific projects mentioned in the resume
    - Tools and technologies they actually used
    - Their real work experience
    
    Return ONLY a JSON array of 5 question strings.
    No explanations. No extra text.
    """
    
    response = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}]
    )
    
    questions = json.loads(response.choices[0].message.content)
    return questions
```

**When done verify:**
```
□ Returns exactly 5 questions
□ Questions are resume specific (not generic)
□ Works with empty asked_resume_questions (no crash)
□ Works with empty preset_questions (no crash)
□ No overlap with preset concepts when presets provided
□ No repetition from asked_resume_questions when provided
```

---

### STEP 4 — session_store.py (user_id Based)
**Location:** `services/session_store.py`
**Change:** Replace session_key with user_id

```python
# REMOVE
session_db = {}  # was keyed by session_key

# REPLACE WITH
import uuid
from datetime import datetime

session_db = {}  # keyed by user_id

def create_session(user_id: str):
    session_db[user_id] = {
        "interview_id": str(uuid.uuid4()),
        "questions": [],
        "started_at": datetime.now().isoformat()
    }

def get_session(user_id: str):
    return session_db.get(user_id)

def update_questions(user_id: str, questions: list):
    if user_id in session_db:
        session_db[user_id]["questions"] = questions

def clear_session(user_id: str):
    if user_id in session_db:
        del session_db[user_id]  # free memory after interview
```

**When done verify:**
```
□ No session_key anywhere in code
□ Sessions created and cleared correctly
□ Memory freed after interview ends
```

---

### STEP 5 — routers/resume.py (Remove Local Storage)
**Location:** `routers/resume.py`
**Change:** Remove PDF upload + local save + session_key return

```python
# REMOVE
# POST /resume/upload → accepts PDF → saves locally → returns session_key

# KEEP
# GET /resume/roles → returns list of roles (unchanged)

@router.get("/resume/roles")
def get_roles():
    return ["frontend", "backend", "fullstack", "devops"]
```

**Note:** Resume upload and storage is handled entirely by backend team.
You only fetch resume_text from Supabase using user_id.

**When done verify:**
```
□ No local file saving anywhere
□ No session_key being generated
□ /resume/roles still works
```

---

### STEP 6 — schemas/interview.py (Update Models)
**Location:** `schemas/interview.py`
**Change:** Replace session_key with user_id, split asked_before into two lists

```python
# REMOVE
class StartRequest(BaseModel):
    session_key: str  # old

# REPLACE WITH
class StartRequest(BaseModel):
    user_id: str
    role: str
    asked_preset_questions: list[str] = []   # IDs of preset Qs already asked — empty = first interview, no filtering
    asked_resume_questions: list[str] = []   # full text of resume Qs already asked — empty = generate freely

class TranscriptSave(BaseModel):
    user_id: str
    interview_id: str
    transcript: list[dict]
```

**When done verify:**
```
□ No session_key in any schema
□ Both asked lists default to empty (no crash on first interview)
□ TranscriptSave has user_id + interview_id
```

---

### STEP 7 — routers/interview.py (Core Changes)
**Location:** `routers/interview.py`
**Change:** Accept user_id + two asked lists, fetch resume, generate questions, remove local transcript save

```python
# REMOVE
# POST /interview/transcript → writes to disk
# GET  /interview/transcript/{call_id} → reads from disk

# MODIFY
@router.post("/interview/start")
async def start_interview(request: StartRequest):
    
    # 1. Fetch resume from Supabase
    resume_text = get_resume(request.user_id)
    if not resume_text:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # 2. Fetch unused preset questions (filtered by asked IDs)
    preset_questions = load_preset_questions(
        request.role,
        request.asked_preset_questions  # empty list = return all
    )
    
    # 3. Analyse resume
    candidate_summary = analyse_resume(resume_text)
    
    # 4. Generate 5 resume questions
    #    - avoids asked_resume_questions (repetition)
    #    - avoids preset concepts (overlap)
    #    - works fine if both lists are empty (first interview)
    resume_questions = await generate_resume_questions(
        resume_text,
        preset_questions,
        request.asked_resume_questions  # empty = generate freely
    )
    
    # 5. Store in session
    create_session(request.user_id)
    update_questions(request.user_id, resume_questions)
    
    # 6. Build and return prompt
    prompt = build_prompt(candidate_summary, resume_questions, preset_questions)
    interview_id = get_session(request.user_id)["interview_id"]
    
    return {
        "system_prompt": prompt,
        "interview_id": interview_id
    }


@router.post("/interview/transcript")
async def receive_transcript(request: TranscriptSave):
    
    # Get questions from session
    session = get_session(request.user_id)
    questions = session["questions"] if session else []
    
    # Evaluate immediately — transcript used here only, never saved
    await evaluate_interview(
        request.user_id,
        request.interview_id,
        questions,
        request.transcript
    )
    
    # Free memory
    clear_session(request.user_id)
    
    return {"status": "evaluation complete"}
```

**When done verify:**
```
□ No local file paths
□ user_id used everywhere instead of session_key
□ asked_preset_questions passed to load_preset_questions
□ asked_resume_questions passed to generate_resume_questions
□ Transcript never saved to disk or DB
□ Session cleared after interview ends
```

---

### STEP 8 — services/evaluator.py (New File)
**Location:** `services/evaluator.py`

```python
async def evaluate_interview(user_id, interview_id, questions, transcript):
    results = []
    
    for question in questions:
        # Extract what user said for this question from transcript
        user_answer = extract_answer_from_transcript(transcript, question)
        
        # Evaluate via Groq
        evaluation = await groq_evaluate(question, user_answer)
        
        results.append({
            "user_id": user_id,
            "interview_id": interview_id,
            "question": question,
            "user_answer": user_answer,
            "correct_answer": evaluation["correct_answer"],
            "score": evaluation["score"],
            "feedback": evaluation["feedback"]
        })
    
    # Save per question results to Supabase
    for result in results:
        save_evaluation(result)
    
    # Generate and save overall summary
    await generate_summary(user_id, interview_id, results, transcript)
    
    # Transcript ends here — never stored anywhere


async def groq_evaluate(question: str, user_answer: str) -> dict:
    prompt = f"""
    Question: {question}
    Candidate Answer: {user_answer}
    
    Return ONLY a JSON object with:
    - correct_answer: the ideal detailed answer
    - score: integer 0-10
    - feedback: specific knowledge they lacked
    
    No extra text. JSON only.
    """
    response = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.choices[0].message.content)


async def generate_summary(user_id, interview_id, results, transcript):
    prompt = f"""
    Interview Q&A results: {results}
    Full transcript: {transcript}
    
    Return ONLY a JSON object with:
    - overall_score: integer 0-100
    - communication: integer 0-10 (how clearly they spoke)
    - technical: integer 0-10 (depth of knowledge)
    - problem_solving: integer 0-10
    - weaknesses: list of topic strings they need to improve
    
    No extra text. JSON only.
    """
    response = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}]
    )
    summary = json.loads(response.choices[0].message.content)
    save_summary({"user_id": user_id, "interview_id": interview_id, **summary})


def extract_answer_from_transcript(transcript: list, question: str) -> str:
    for i, entry in enumerate(transcript):
        if entry["role"] == "assistant" and question in entry["content"]:
            if i + 1 < len(transcript):
                return transcript[i + 1]["content"]
    return "No answer provided"
```

**When done verify:**
```
□ Evaluation rows saved to Supabase
□ Summary row saved to Supabase
□ Transcript NOT in any DB table
□ Scores are between 0-10
□ correct_answer field is not empty
□ weaknesses is a list
```

---

### STEP 9 — routers/evaluation.py (New File)
**Location:** `routers/evaluation.py`

```python
@router.get("/evaluation/{user_id}")
def get_all_evaluations(user_id: str):
    results = get_evaluations(user_id)
    if not results:
        raise HTTPException(status_code=404, detail="No evaluations found")
    return results

@router.get("/evaluation/{user_id}/{interview_id}")
def get_single_interview(user_id: str, interview_id: str):
    summary = get_summary(user_id, interview_id)
    detail = get_interview_detail(user_id, interview_id)
    
    if not summary:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    return {
        "summary": summary,
        "questions": detail
    }
```

**When done verify:**
```
□ Returns list of past interviews for user
□ Returns per question detail + summary for single interview
□ 404 if user not found (not 500)
□ Register router in main.py
```

---

### STEP 10 — .env + requirements.txt

**.env — add:**
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

**requirements.txt — add:**
```
supabase
```

---

## PART 2: MANUAL TESTING

---

### BEFORE YOU START

**Insert test data in Supabase dashboard:**
```
resumes table:
  user_id    → "test_user_001"
  resume_text → paste a real resume (Python/Django developer works best)

preset_questions table:
  Insert 3-4 rows for role = "backend" if data engineering hasn't done it yet
```

**Start server:**
```bash
uvicorn main:app --reload --port 8000
```

**Open Postman or Thunder Client in VS Code**

---

### TEST 1 — Sanity Check
```
Method: GET
URL:    http://localhost:8000/resume/roles

Expected:
["frontend", "backend", "fullstack", "devops"]

✅ Server running, routing works
❌ 404 → check router registered in main.py
```

---

### TEST 2 — Start Interview (First Time, Empty History)
```
Method: POST
URL:    http://localhost:8000/interview/start
Body:
{
    "user_id": "test_user_001",
    "role": "backend",
    "asked_preset_questions": [],
    "asked_resume_questions": []
}

Expected:
{
    "system_prompt": "You are a technical interviewer...",
    "interview_id": "some-uuid"
}

✅ Has system_prompt
✅ Has interview_id (save this for TEST 4)
✅ Prompt mentions candidate's actual skills from resume
✅ Prompt has 5 resume specific questions
✅ Prompt has preset questions for backend role

❌ "Resume not found"     → check user_id matches exactly in Supabase
❌ "No preset questions"  → check preset_questions table has backend role data
❌ JSON parse error       → Groq returning non-JSON, fix prompt to say "JSON only"
```

---

### TEST 3 — Verify Questions Are Resume Specific
```
Look at system_prompt from TEST 2

✅ Questions mention specific tech from resume
   e.g. resume has Django → question about Django project specifically
✅ Questions are NOT generic
   e.g. "Explain OOP" is too generic → should NOT appear
✅ No question topic matches preset question concepts

❌ Generic questions   → tighten Groq prompt in resume_service.py
❌ Overlap with preset → check preset_concepts extraction logic
```

---

### TEST 4 — Send Mock Transcript
```
Method: POST
URL:    http://localhost:8000/interview/transcript
Body:
{
    "user_id": "test_user_001",
    "interview_id": "← use interview_id from TEST 2",
    "transcript": [
        {
            "role": "assistant",
            "content": "Can you explain your Django REST project?"
        },
        {
            "role": "user",
            "content": "I built a REST API using Django REST framework for an e-commerce platform handling authentication and orders."
        },
        {
            "role": "assistant",
            "content": "What is a REST API?"
        },
        {
            "role": "user",
            "content": "REST is an architectural style using HTTP methods to communicate between client and server."
        }
    ]
}

Expected:
{ "status": "evaluation complete" }

✅ Response is 200
✅ Supabase evaluations table → rows exist for this interview_id
✅ Supabase interview_summary → summary row exists
✅ Scores between 0-10
✅ correct_answer is not empty
✅ weaknesses list is not empty
✅ NO transcript column anywhere in Supabase (critical)
✅ Session for test_user_001 is gone from memory

❌ Evaluation not saving  → check save_evaluation in supabase_service.py
❌ Summary not saving     → check generate_summary in evaluator.py
❌ Scores all 0 or all 10 → fix Groq evaluation prompt
```

---

### TEST 5 — Fetch All Evaluations
```
Method: GET
URL:    http://localhost:8000/evaluation/test_user_001

Expected:
[
    {
        "interview_id": "...",
        "overall_score": 75,
        "communication": 7,
        "technical": 6,
        "problem_solving": 7,
        "weaknesses": ["System Design", "Database Optimization"],
        "created_at": "..."
    }
]

✅ List is not empty
✅ overall_score between 0-100
✅ weaknesses is a list of strings

❌ Empty list → check get_evaluations in supabase_service.py
❌ 404       → check router registered in main.py
```

---

### TEST 6 — Fetch Single Interview Detail
```
Method: GET
URL:    http://localhost:8000/evaluation/test_user_001/{interview_id}
        (use interview_id from TEST 2)

Expected:
{
    "summary": {
        "overall_score": 75,
        "communication": 7,
        "technical": 6,
        "problem_solving": 7,
        "weaknesses": ["..."]
    },
    "questions": [
        {
            "question": "Can you explain your Django REST project?",
            "user_answer": "I built a REST API...",
            "correct_answer": "A strong answer would cover...",
            "score": 7,
            "feedback": "Good overview but lacked depth on authentication flow"
        }
    ]
}

✅ summary has all score fields
✅ questions list matches what was in transcript
✅ user_answer matches what candidate said in mock transcript
✅ correct_answer is detailed and helpful
✅ feedback is specific not generic

❌ Empty questions → check get_interview_detail in supabase_service.py
```

---

### TEST 7 — Preset Repetition Check
```
Method: POST
URL:    http://localhost:8000/interview/start
Body:
{
    "user_id": "test_user_001",
    "role": "backend",
    "asked_preset_questions": ["se_002", "se_005"],
    "asked_resume_questions": []
}

✅ Preset questions se_002 and se_005 NOT in returned prompt
✅ Other preset questions still appear
✅ Resume questions still generated fine

❌ Still includes se_002 → check filter logic in question_loader.py
```

---

### TEST 8 — Resume Repetition Check
```
Method: POST
URL:    http://localhost:8000/interview/start
Body:
{
    "user_id": "test_user_001",
    "role": "backend",
    "asked_preset_questions": [],
    "asked_resume_questions": [
        "Can you explain your Django REST project?",
        "How did you handle authentication in your project?",
        "Tell me about your React experience"
    ]
}

✅ None of the 5 new resume questions repeat the asked_resume_questions
✅ Questions are still resume specific
✅ No crash (list provided correctly)

❌ Repeated questions → tighten Groq prompt repetition instruction
```

---

### TEST 9 — Both Lists Empty (First Interview Ever)
```
Method: POST
URL:    http://localhost:8000/interview/start
Body:
{
    "user_id": "test_user_001",
    "role": "backend",
    "asked_preset_questions": [],
    "asked_resume_questions": []
}

✅ Runs without any errors
✅ Returns all preset questions (no filtering)
✅ Returns 5 resume questions (generated freely)
✅ No mention of "empty list" errors

This is the most important test — must pass cleanly ✅
```

---

### TEST 10 — Missing Resume (Edge Case)
```
Method: POST
URL:    http://localhost:8000/interview/start
Body:
{
    "user_id": "nonexistent_user_999",
    "role": "backend",
    "asked_preset_questions": [],
    "asked_resume_questions": []
}

Expected:
HTTP 404
{ "detail": "Resume not found" }

✅ Returns 404 not 500
✅ Clear error message

❌ Returns 500 → add null check in interview.py
```

---

### TEST 11 — Invalid Role (Edge Case)
```
Method: POST
URL:    http://localhost:8000/interview/start
Body:
{
    "user_id": "test_user_001",
    "role": "nonexistent_role",
    "asked_preset_questions": [],
    "asked_resume_questions": []
}

Expected:
HTTP 404 or clear error

✅ Graceful error not server crash

❌ 500 error → add null check in question_loader.py
```

---

### TEST 12 — Session Cleanup (Edge Case)
```
After TEST 4 (transcript sent and evaluated):

Add a temporary debug endpoint:
GET /debug/session/{user_id}
→ return session_db.get(user_id) or "not found"

Hit it after transcript received:
GET http://localhost:8000/debug/session/test_user_001

✅ Returns "not found" → session cleared, memory freed
❌ Returns session data → check clear_session call in interview.py

Remove this debug endpoint before git push.
```

---

## PART 3: CHECKLIST BEFORE GIT PUSH

### Code Checks
```
□ No local file paths anywhere in code
□ No hardcoded API keys
□ No session_key references remaining
□ No questions.json references remaining
□ No asked_before (old name) — replaced with asked_preset_questions + asked_resume_questions
□ Transcript never saved (search "transcript" in all supabase calls)
□ All imports working (no missing modules)
□ requirements.txt has supabase added
□ Debug endpoints removed
□ Print statements replaced with proper logging
```

### .env Checks
```
□ .env has SUPABASE_URL
□ .env has SUPABASE_KEY
□ .env is in .gitignore (CRITICAL — never push keys)
□ .env.example created with empty values for team reference
```

### Testing Checks
```
□ TEST 1  passed → roles endpoint works
□ TEST 2  passed → interview starts with empty history
□ TEST 3  passed → questions are resume specific
□ TEST 4  passed → transcript evaluated + results saved
□ TEST 5  passed → evaluation list fetchable
□ TEST 6  passed → interview detail fetchable
□ TEST 7  passed → preset repetition filtered by ID
□ TEST 8  passed → resume repetition avoided via Groq
□ TEST 9  passed → empty lists work fine (no crash)
□ TEST 10 passed → missing resume returns 404
□ TEST 11 passed → invalid role handled gracefully
□ TEST 12 passed → session cleared after interview
```

### Supabase Checks
```
□ resumes table has test data
□ preset_questions table has data for all roles
□ evaluations table saving correctly after TEST 4
□ interview_summary table saving correctly after TEST 4
□ NO transcript column anywhere in any table
```

### Final
```
□ README updated with new endpoints + setup instructions
□ Tell backend team final endpoint contracts (see Part 4)
□ Tell data engineering team final table schemas (see Part 4)
```

---

## PART 4: TELL YOUR TEAMS

### Tell Backend Team
```
My endpoints:

POST /interview/start
Send:
{
    "user_id": "string",
    "role": "string",
    "asked_preset_questions": ["se_002", "se_005"],  ← IDs, empty on first interview
    "asked_resume_questions": ["question text..."]    ← full text, empty on first interview
}
Get back:
{
    "system_prompt": "...",
    "interview_id": "uuid"
}

POST /interview/transcript
Send:
{
    "user_id": "string",
    "interview_id": "string",
    "transcript": [{"role": "assistant/user", "content": "..."}]
}
Get back:
{ "status": "evaluation complete" }

GET /evaluation/{user_id}           → all past interview summaries
GET /evaluation/{user_id}/{interview_id} → full detail with per question scores

Your responsibilities:
→ Pass user_id on every request
→ Track asked_preset_questions (store IDs after each interview)
→ Track asked_resume_questions (store question text after each interview)
→ Handle resume upload + update resume_text in Supabase
→ Handle interview lock (block second interview if one active)
→ Pass empty lists [] on first interview — my engine handles it fine
```

### Tell Data Engineering Team
```
Tables needed in Supabase:

resumes
├── user_id (text, primary key)
└── resume_text (text)

preset_questions
├── id (text, primary key)          ← e.g. "se_002"
├── role (text)                     ← "backend", "frontend" etc
├── difficulty (integer 1-10)
├── question (text)
├── concepts (text array)           ← ["Garbage Collection", "Memory Management"]
└── follow_up_hints (text array)    ← ["Discuss generational hypothesis"]

evaluations
├── id (uuid, auto generated)
├── user_id (text)
├── interview_id (text)
├── question (text)
├── user_answer (text)
├── correct_answer (text)
├── score (integer 0-10)
└── feedback (text)

interview_summary
├── id (uuid, auto generated)
├── user_id (text)
├── interview_id (text)
├── overall_score (integer 0-100)
├── communication (integer 0-10)
├── technical (integer 0-10)
├── problem_solving (integer 0-10)
├── weaknesses (text array)
└── created_at (timestamp)

Please load all preset + coding questions into preset_questions table.
I am removing questions.json completely.
Keep the exact same JSON structure you already have —
just add a role column so I can filter by interview type.
```
