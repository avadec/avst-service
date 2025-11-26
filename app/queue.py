"""
Redis-based queue helpers for job management.
"""
import json
import logging
from typing import Optional, Dict, Any
from redis import Redis
from .config import settings


logger = logging.getLogger(__name__)

# Queue name constant
TRANSCRIPTION_QUEUE = "transcription_jobs"

# Singleton Redis client
_redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """
    Get or create a singleton Redis client.
    
    Returns:
        Redis: Connected Redis client instance.
    """
    global _redis_client
    if _redis_client is None:
        logger.info(f"Connecting to Redis at {settings.REDIS_URL}")
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
    return _redis_client


def enqueue_job(job: Dict[str, Any]) -> None:
    """
    Enqueue a job into the Redis queue.
    
    Args:
        job: Job dictionary containing job_id, audio_path, agent_id, etc.
    """
    redis_client = get_redis_client()
    job_json = json.dumps(job)
    redis_client.rpush(TRANSCRIPTION_QUEUE, job_json)
    logger.info(f"Enqueued job {job.get('job_id')} to queue")


def dequeue_job(block: bool = True, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """
    Dequeue a job from the Redis queue.
    
    Args:
        block: Whether to block waiting for a job.
        timeout: Timeout in seconds when blocking.
        
    Returns:
        Job dictionary or None if no job available.
    """
    redis_client = get_redis_client()
    
    if block:
        result = redis_client.blpop(TRANSCRIPTION_QUEUE, timeout=timeout)
        if result:
            _, job_json = result
            job = json.loads(job_json)
            logger.info(f"Dequeued job {job.get('job_id')} from queue")
            return job
    else:
        job_json = redis_client.lpop(TRANSCRIPTION_QUEUE)
        if job_json:
            job = json.loads(job_json)
            logger.info(f"Dequeued job {job.get('job_id')} from queue")
            return job
    
    return None
