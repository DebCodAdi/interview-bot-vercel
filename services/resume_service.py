import os
import re
import json
try:
    import PyPDF2
except ImportError:
    import pypdf as PyPDF2
from groq import Groq
from typing import Dict, List, Any

# Can be overridden per deployment without code changes.  GPT-OSS 20B is
# currently available to the project's Groq account and is optimized for
# low-latency structured generation.
GROQ_MODEL = (os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b").strip()

def clean_json_response(raw_text: str) -> str:
    """
    Cleans markdown wrappers and extra text from LLM JSON responses.
    """
    # Remove markdown code blocks if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
    if match:
        cleaned = match.group(1).strip()
    else:
        cleaned = raw_text.strip()
    return cleaned

def extract_text(pdf_path: str) -> str:
    """
    Extracts text from a local PDF file path using PyPDF2.
    """
    text = ""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")
        
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
                
    # Clean up double whitespace and normalize line endings
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r" +", " ", text)
    return text.strip()

def analyse_resume(resume_text: str, role: str) -> Dict[str, Any]:
    """
    Sends the resume text to Groq to analyze candidate experience.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables.")
        
    client = Groq(api_key=api_key)
    
    prompt = f"""You are analysing a resume for a technical interview.
Role the candidate is applying for: {role}

Resume content:
{resume_text}

Extract and return ONLY this JSON structure, no conversation, no markdown blocks, no leading/trailing text:
{{
  "candidate_name": "full name",
  "key_skills": ["skill1", "skill2"],
  "experience_years": 2,
  "notable_projects": [
    {{
      "name": "project name",
      "tech_stack": ["tech1", "tech2"],
      "description": "one sentence"
    }}
  ],
  "education": "degree and college",
  "resume_summary": "3 sentence profile summary",
  "strong_areas": ["area1", "area2"],
  "weak_areas_to_probe": ["area1", "area2"]
}}"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are a specialized data extractor. Always output strict valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        # Resume parsing is a constrained extraction task; keep reasoning light
        # and reserve sufficient output space for the JSON payload.
        reasoning_effort="low",
        max_completion_tokens=4096,
    )
    
    raw_content = response.choices[0].message.content
    cleaned_json = clean_json_response(raw_content)
    
    try:
        return json.loads(cleaned_json)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error in analyse_resume: {e}. Raw content: {raw_content}")
        # Fallback dictionary
        return {
            "candidate_name": "Candidate Name",
            "key_skills": [],
            "experience_years": 0,
            "notable_projects": [],
            "education": "Unknown",
            "resume_summary": "Resume parsed with fallback due to JSON decoding error.",
            "strong_areas": [],
            "weak_areas_to_probe": []
        }

def generate_resume_questions(resume_analysis: Dict[str, Any], role: str) -> List[Dict[str, Any]]:
    """
    Generates 5 technical questions based on the candidate's specific resume analysis.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables.")
        
    client = Groq(api_key=api_key)
    
    prompt = f"""You are a senior technical interviewer preparing questions for a {role} candidate.

Candidate profile:
{json.dumps(resume_analysis, indent=2)}

Generate exactly 5 technical questions based on their specific resume.

Rules:
- Tie questions directly to their skills and projects
- Start at difficulty 3 and increase to difficulty 8
- Probe areas they claimed expertise in
- Include one question about a specific project they listed
- Include one question about their strongest skill

Return ONLY this JSON array structure, no extra text, no conversation, no markdown blocks:
[
  {{
    "id": "resume_001",
    "difficulty": 3,
    "question": "question text",
    "based_on": "which part of resume",
    "concepts": ["concept1", "concept2"],
    "follow_up_hints": [
      "follow up direction 1",
      "follow up direction 2"
    ]
  }}
]"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are a senior technical interviewer. Always output strict valid JSON array."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        # Five detailed question objects can exceed the provider's default
        # completion length, producing truncated invalid JSON.
        reasoning_effort="low",
        max_completion_tokens=4096,
    )
    
    raw_content = response.choices[0].message.content
    cleaned_json = clean_json_response(raw_content)
    
    try:
        return json.loads(cleaned_json)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error in generate_resume_questions: {e}. Raw content: {raw_content}")
        return []

def generate_coding_question(resume_analysis: Dict[str, Any], role: str) -> Dict[str, Any]:
    """
    Generates exactly 1 coding problem relevant to the candidate's profile.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables.")
        
    client = Groq(api_key=api_key)
    
    prompt = f"""You are a senior technical interviewer preparing a coding challenge for a {role} candidate.

Candidate profile:
{json.dumps(resume_analysis, indent=2)}

Generate exactly 1 coding problem relevant to {role}.

Rules:
- Problem should be solvable in 10-15 minutes
- Tie it to their tech stack if possible
- Include 2 clear examples
- Include 3 test cases with exact inputs and outputs
- Difficulty should match their experience level
- The candidate function must be named solution
- parameters must list every solution argument in order
- Every test input must contain named assignments for those parameters, one per line
- Inputs must be valid simple literals in both Python and JavaScript

Return ONLY this JSON structure, no extra text, no conversation, no markdown blocks:
{{
  "id": "coding_groq_001",
  "difficulty": 5,
  "parameters": ["nums", "target"],
  "problem": "full problem statement",
  "examples": [
    {{ "input": "example input", "output": "example output" }}
  ],
  "test_cases": [
    {{ "input": "test 1 input", "expected_output": "test 1 output" }},
    {{ "input": "test 2 input", "expected_output": "test 2 output" }},
    {{ "input": "test 3 input", "expected_output": "test 3 output" }}
  ],
  "concepts": ["concept1", "concept2"],
  "language_options": ["python", "javascript"]
}}"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are a senior technical interviewer. Always output strict valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        reasoning_effort="low",
        max_completion_tokens=4096,
    )
    
    raw_content = response.choices[0].message.content
    cleaned_json = clean_json_response(raw_content)
    
    try:
        return json.loads(cleaned_json)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error in generate_coding_question: {e}. Raw content: {raw_content}")
        # Return a simple fallback coding question
        return {
            "id": "coding_fallback_001",
            "difficulty": 5,
            "parameters": ["nums"],
            "problem": "Given an array of integers, write a function to reverse the array in place.",
            "examples": [
                { "input": "nums = [1, 2, 3]", "output": "[3, 2, 1]" }
            ],
            "test_cases": [
                { "input": "nums = [1,2,3]", "expected_output": "[3,2,1]" },
                { "input": "nums = [5,4]", "expected_output": "[4,5]" }
            ],
            "concepts": ["Arrays"],
            "language_options": ["python", "javascript"]
        }
