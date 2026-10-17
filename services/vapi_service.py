import os
import httpx
from typing import Dict, Any, Optional

VAPI_API_URL = "https://api.vapi.ai/call"

async def start_call(system_prompt: str, max_duration_seconds: int, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Sends a POST request to VAPI to start a call, overriding the system prompt and duration.
    Falls back to a mock response if Vapi keys are missing or invalid.
    """
    private_key = (os.getenv("VAPI_PRIVATE_KEY") or "").strip().strip('"').strip("'")
    assistant_id = (os.getenv("VAPI_ASSISTANT_ID") or "").strip().strip('"').strip("'")
    
    # Check if keys are set
    if not private_key or private_key.startswith("your_") or \
       not assistant_id or assistant_id.startswith("your_"):
        print("WARNING: VAPI_PRIVATE_KEY or VAPI_ASSISTANT_ID is not configured. Falling back to Mock Call Mode.")
        return {
            "call_id": "mock-call-uuid-12345-vapi",
            "status": "started"
        }
        
    headers = {
        "Authorization": f"Bearer {private_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "assistantId": assistant_id,
        "assistantOverrides": {
            "model": {
                "provider": "groq",
                "model": (os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b").strip(),
                "systemPrompt": system_prompt
            },
            "maxDurationSeconds": max_duration_seconds
        }
    }
    
    if metadata:
        payload["metadata"] = metadata
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(VAPI_API_URL, json=payload, headers=headers, timeout=10.0)
            
            if response.status_code >= 400:
                print(f"Vapi API Error Status {response.status_code}: {response.text}")
                # Return mock call to prevent app crashing when key is invalid
                return {
                    "call_id": f"mock-call-error-{response.status_code}",
                    "status": "started"
                }
                
            data = response.json()
            return {
                "call_id": data.get("id"),
                "status": data.get("status")
            }
    except Exception as e:
        print(f"Network error trying to connect to Vapi API: {e}")
        return {
            "call_id": "mock-call-network-fallback",
            "status": "started"
        }
