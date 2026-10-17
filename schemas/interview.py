from pydantic import BaseModel, Field
from typing import List, Optional, Any

class StartRequest(BaseModel):
    role: str = Field(..., description="Role candidate is applying for (e.g., Software Engineer)")
    duration_mins: int = Field(23, ge=23, le=23, description="Fixed 3-minute interview plus 20-minute coding round")
    resume_session_key: str = Field(..., description="The unique session key returned after resume upload")

class CodingQuestionRequest(BaseModel):
    role: str = Field(..., description="Role name")
    resume_session_key: str = Field(..., description="Session key associated with the resume upload")

class TranscriptSave(BaseModel):
    call_id: str = Field(..., description="Unique call ID returned from VAPI")
    transcript: List[Any] = Field(..., description="List of transcript message objects containing role and content")
    duration: int = Field(..., description="Call duration in seconds")
    timestamp: str = Field(..., description="Time the call was recorded")
    role: str = Field(..., description="Interview role")
