"""
FastAPI application for the transcriber service.
Provides the API endpoint for submitting transcription jobs.
"""
import logging
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from .schemas import TranscriptionRequest, TranscriptionJobResponse
from .config import settings
from .queue import enqueue_job


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Transcriber Service",
    description="GPU-enabled audio processing microservice with Whisper STT",
    version="1.0.0"
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/transcriptions", response_model=TranscriptionJobResponse)
async def create_transcription(request: TranscriptionRequest):
    """
    Create a new transcription job.
    
    The audio_path can be:
    - HTTP/HTTPS URL: File will be downloaded before processing
    - Local file path: File will be validated and processed directly
    - Network path: Should be mounted/accessible to the worker
    
    Args:
        request: TranscriptionRequest containing audio_path, agent_id, etc.
        
    Returns:
        TranscriptionJobResponse with job_id and status.
    """
    logger.info(f"Received transcription request for audio: {request.audio_path}")
    
    # Generate unique job ID
    job_id = str(uuid4())
    
    # Resolve callback URL (use request callback_url or fall back to default)
    callback_url = request.callback_url or settings.DEFAULT_CALLBACK_URL
    
    if not callback_url:
        logger.warning(f"No callback URL provided for job {job_id}")
    
    # Build job payload
    job = {
        "job_id": job_id,
        "audio_path": request.audio_path,
        "agent_id": request.agent_id,
        "callback_url": callback_url,
        "metadata": request.metadata or {}
    }
    
    try:
        # Enqueue job to Redis
        enqueue_job(job)
        logger.info(f"Job {job_id} queued successfully")
        
        return TranscriptionJobResponse(
            job_id=job_id,
            status="queued"
        )
        
    except Exception as e:
        logger.error(f"Failed to enqueue job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enqueue transcription job: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
