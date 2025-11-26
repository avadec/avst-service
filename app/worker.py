"""
Worker process for processing transcription jobs.

This worker:
1. Dequeues jobs from Redis
2. Runs Whisper STT on GPU 0
3. Runs summarisation (currently dummy, future LLM on GPU 1)
4. Sends results to callback URL

Run with: python -m app.worker
"""
import logging
import os
import sys
from typing import Dict, Any
from .queue import dequeue_job
from .stt import transcribe_audio_file
from .summarizer import summarize_text
from .callbacks import send_callback


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def process_job(job: Dict[str, Any]) -> None:
    """
    Process a single transcription job.
    
    Args:
        job: Job dictionary containing job_id, audio_path, agent_id, callback_url, metadata.
    """
    job_id = job.get("job_id", "unknown")
    audio_path = job.get("audio_path", "")
    agent_id = job.get("agent_id", "")
    callback_url = job.get("callback_url", "")
    metadata = job.get("metadata", {})
    
    logger.info(f"Processing job {job_id} for audio: {audio_path}")
    
    try:
        # Step 1: Verify file exists
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        logger.info(f"Audio file exists: {audio_path}")
        
        # Step 2: Run Whisper STT on GPU 0
        logger.info("Running Whisper STT...")
        full_text, segments, language = transcribe_audio_file(audio_path)
        
        # Step 3: Run summarisation (dummy for now, future LLM on GPU 1)
        logger.info("Running summarisation...")
        summary = summarize_text(full_text)
        
        # Step 4: Build success payload
        success_payload = {
            "job_id": job_id,
            "status": "done",
            "audio_path": audio_path,
            "agent_id": agent_id,
            "transcript": full_text,
            "summary": summary,
            "language": language,
            "segments": segments,
            "metadata": metadata
        }
        
        # Step 5: Send callback
        logger.info(f"Job {job_id} completed successfully")
        send_callback(callback_url, success_payload)
        
    except Exception as e:
        # Handle any errors
        logger.error(f"Job {job_id} failed with error: {str(e)}", exc_info=True)
        
        # Build error payload
        error_payload = {
            "job_id": job_id,
            "status": "error",
            "error": str(e),
            "audio_path": audio_path,
            "agent_id": agent_id,
            "metadata": metadata
        }
        
        # Send error callback
        send_callback(callback_url, error_payload)


def main():
    """Main worker loop."""
    logger.info("Worker starting...")
    logger.info("Waiting for jobs from Redis queue...")
    
    try:
        while True:
            # Dequeue job with blocking wait
            job = dequeue_job(block=True, timeout=5)
            
            if job is None:
                # No job available, continue waiting
                continue
            
            # Process the job
            process_job(job)
            
    except KeyboardInterrupt:
        logger.info("Worker shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker crashed with error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
