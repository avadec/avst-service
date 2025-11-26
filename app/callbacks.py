"""
Callback sending logic with retry support.
"""
import logging
import time
from typing import Dict, Any
import httpx
from .config import settings


logger = logging.getLogger(__name__)


def send_callback(callback_url: str, payload: Dict[str, Any]) -> None:
    """
    Send payload to callback_url via HTTP POST with retry logic.
    
    Args:
        callback_url: The URL to send the callback to.
        payload: The JSON payload to send.
        
    The function will retry up to CALLBACK_RETRY_COUNT times with
    CALLBACK_RETRY_DELAY_SECONDS seconds between retries.
    Errors are logged but do not crash the worker.
    """
    if not callback_url:
        logger.warning("No callback URL provided, skipping callback")
        return
    
    logger.info(f"Sending callback to {callback_url}")
    
    for attempt in range(1, settings.CALLBACK_RETRY_COUNT + 1):
        try:
            with httpx.Client(timeout=settings.CALLBACK_TIMEOUT_SECONDS) as client:
                response = client.post(
                    callback_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                
            logger.info(
                f"Callback sent successfully to {callback_url} "
                f"(attempt {attempt}/{settings.CALLBACK_RETRY_COUNT}). "
                f"Status: {response.status_code}"
            )
            return
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Callback failed with HTTP error (attempt {attempt}/{settings.CALLBACK_RETRY_COUNT}): "
                f"{e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            logger.error(
                f"Callback failed with request error (attempt {attempt}/{settings.CALLBACK_RETRY_COUNT}): "
                f"{str(e)}"
            )
        except Exception as e:
            logger.error(
                f"Callback failed with unexpected error (attempt {attempt}/{settings.CALLBACK_RETRY_COUNT}): "
                f"{str(e)}"
            )
        
        # Sleep before retry (except on last attempt)
        if attempt < settings.CALLBACK_RETRY_COUNT:
            logger.info(f"Retrying in {settings.CALLBACK_RETRY_DELAY_SECONDS} seconds...")
            time.sleep(settings.CALLBACK_RETRY_DELAY_SECONDS)
    
    logger.error(
        f"All {settings.CALLBACK_RETRY_COUNT} callback attempts failed for {callback_url}"
    )
