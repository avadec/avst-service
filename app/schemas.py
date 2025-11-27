"""
Pydantic models for request/response validation.
"""
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, field_validator


class TranscriptionRequest(BaseModel):
    """Request model for transcription endpoint."""
    
    audio_path: str  # Can be local path, HTTP/HTTPS URL, or network path
    agent_id: str
    callback_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('audio_path')
    @classmethod
    def validate_audio_path(cls, v: str) -> str:
        """Ensure audio_path is not empty."""
        if not v or not v.strip():
            raise ValueError("audio_path must be a non-empty string")
        return v.strip()


class TranscriptionJobResponse(BaseModel):
    """Response model for transcription job."""
    
    job_id: str
    status: Literal["queued", "processing", "done", "error"]
