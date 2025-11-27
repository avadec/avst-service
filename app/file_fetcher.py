"""
File fetcher for downloading audio files from remote locations.
Supports HTTP/HTTPS URLs, SMB shares, and local file paths.
"""
import logging
import os
import tempfile
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse
import httpx
from .config import settings

logger = logging.getLogger(__name__)


def _is_remote_url(path: str) -> bool:
    """Check if path is a remote HTTP/HTTPS URL."""
    try:
        parsed = urlparse(path)
        return parsed.scheme in ('http', 'https')
    except Exception:
        return False


def _is_smb_path(path: str) -> bool:
    """Check if path is a SMB/CIFS network path."""
    return path.startswith('//') or path.startswith('\\\\') or path.startswith('smb://')


def _download_http_file(url: str, job_id: str) -> str:
    """
    Download file from HTTP/HTTPS URL with streaming.
    
    Args:
        url: HTTP/HTTPS URL to download from
        job_id: Job ID for unique temp file naming
        
    Returns:
        Local path to downloaded file
        
    Raises:
        Exception: If download fails
    """
    logger.info(f"Downloading audio file from URL: {url}")
    
    # Create temp directory if it doesn't exist
    os.makedirs(settings.TEMP_DOWNLOAD_DIR, exist_ok=True)
    
    # Generate unique temp file name
    file_extension = Path(urlparse(url).path).suffix or '.wav'
    temp_file = os.path.join(settings.TEMP_DOWNLOAD_DIR, f"{job_id}{file_extension}")
    
    try:
        # Stream download with progress logging
        with httpx.stream(
            "GET", 
            url, 
            timeout=settings.DOWNLOAD_TIMEOUT_SECONDS,
            follow_redirects=True
        ) as response:
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_bytes(chunk_size=settings.DOWNLOAD_CHUNK_SIZE):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Log progress every 10MB
                    if total_size > 0 and downloaded % (10 * 1024 * 1024) < settings.DOWNLOAD_CHUNK_SIZE:
                        progress = (downloaded / total_size) * 100
                        logger.info(f"Download progress: {progress:.1f}% ({downloaded}/{total_size} bytes)")
            
            file_size_mb = os.path.getsize(temp_file) / (1024 * 1024)
            logger.info(f"Download completed: {temp_file} ({file_size_mb:.2f} MB)")
            
            return temp_file
            
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        logger.error(f"Failed to download file from {url}: {str(e)}")
        raise


def fetch_audio_file(audio_path: str, job_id: str) -> Tuple[str, bool]:
    """
    Fetch audio file from remote location or validate local path.
    
    Args:
        audio_path: Path to audio file (can be local, HTTP URL, or SMB path)
        job_id: Job ID for unique temp file naming
        
    Returns:
        Tuple of (local_file_path, is_temporary)
        - local_file_path: Path to local file (downloaded or original)
        - is_temporary: True if file was downloaded and should be cleaned up
        
    Raises:
        FileNotFoundError: If local file doesn't exist
        ValueError: If path type is unsupported
        Exception: If download fails
    """
    # Check if it's a remote HTTP/HTTPS URL
    if _is_remote_url(audio_path):
        logger.info(f"Detected remote HTTP/HTTPS URL: {audio_path}")
        local_path = _download_http_file(audio_path, job_id)
        return local_path, True
    
    # Check if it's a SMB path
    if _is_smb_path(audio_path):
        raise ValueError(
            f"SMB/CIFS paths are not supported yet: {audio_path}. "
            "Please mount the SMB share to a local path or provide an HTTP URL."
        )
    
    # Treat as local file path
    logger.info(f"Treating as local file path: {audio_path}")
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    if not os.path.isfile(audio_path):
        raise ValueError(f"Path is not a file: {audio_path}")
    
    # Return original path, no cleanup needed
    return audio_path, False


def cleanup_temp_file(file_path: str) -> None:
    """
    Remove temporary downloaded file.
    
    Args:
        file_path: Path to temporary file
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to clean up temporary file {file_path}: {e}")
