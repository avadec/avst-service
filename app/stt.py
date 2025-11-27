"""
Whisper STT wrapper using faster-whisper on GPU 0.
Supports TESTING_MODE for debugging E2E pipeline without GPU.
"""
import logging
import os
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional
from .config import settings

logger = logging.getLogger(__name__)

# Initialize Whisper model on GPU 0 (only if not in testing mode)
model: Optional[Any] = None

if not settings.TESTING_MODE:
    from faster_whisper import WhisperModel
    logger.info(f"Loading Whisper model '{settings.WHISPER_MODEL}' on device '{settings.WHISPER_DEVICE}'")
    model = WhisperModel(
        settings.WHISPER_MODEL,
        device=settings.WHISPER_DEVICE,  # "cuda:0"
        compute_type=settings.WHISPER_COMPUTE_TYPE
    )
    logger.info("Whisper model loaded successfully")
else:
    logger.info("TESTING MODE enabled - Whisper model NOT loaded")


def _write_testing_log(message: str) -> None:
    """Write testing mode output to log file and console."""
    timestamp = datetime.now().isoformat()
    log_message = f"[{timestamp}] {message}\n"
    
    # Write to console
    print(log_message.strip())
    
    # Write to log file
    try:
        with open(settings.TESTING_LOG_FILE, "a") as f:
            f.write(log_message)
    except Exception as e:
        logger.warning(f"Failed to write to testing log file: {e}")


def _mock_transcription(path: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """
    Mock transcription for testing mode.
    Returns dummy data instead of running Whisper.
    """
    _write_testing_log(f"STT processed (TESTING MODE): {path}")
    
    # Generate dummy transcript data
    full_text = (
        "This is a test transcription. "
        "The audio file has been processed in testing mode. "
        "No actual STT was performed. "
        "This is dummy data for E2E pipeline testing."
    )
    
    segments = [
        {
            "start": 0.0,
            "end": 3.5,
            "text": "This is a test transcription."
        },
        {
            "start": 3.5,
            "end": 7.2,
            "text": "The audio file has been processed in testing mode."
        },
        {
            "start": 7.2,
            "end": 10.8,
            "text": "No actual STT was performed."
        },
        {
            "start": 10.8,
            "end": 15.0,
            "text": "This is dummy data for E2E pipeline testing."
        }
    ]
    
    language = "en"
    
    _write_testing_log(
        f"Mock STT complete - Text length: {len(full_text)} chars, "
        f"Segments: {len(segments)}, Language: {language}"
    )
    
    return full_text, segments, language


def dummy_transcription(path: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """Dummy transcription when STT step is disabled."""
    return _mock_transcription(path)


def transcribe_audio_file(path: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """
    Run Whisper STT on the given WAV file path using GPU 0.
    If TESTING_MODE is enabled, returns mock data instead.
    
    Args:
        path: Absolute path to the audio file.
        
    Returns:
        Tuple containing:
        - full_text: str - Full transcript text
        - segments_payload: list[dict] - List of segments with start, end, and text
        - language: str - Detected language code
        
    Raises:
        Exception: If transcription fails.
    """
    logger.info(f"Starting transcription for file: {path}")
    
    # Validate the file exists before continuing (even in testing mode)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: {path}")
    
    # Use mock transcription in testing mode
    if settings.TESTING_MODE:
        logger.info("Using mock transcription (TESTING_MODE=True)")
        return _mock_transcription(path)
    
    try:
        segments, info = model.transcribe(path, beam_size=5)
        
        language = info.language
        logger.info(f"Detected language: {language}")
        
        # Build segments payload and full text
        segments_payload: List[Dict[str, Any]] = []
        full_text_parts: List[str] = []
        
        for segment in segments:
            segments_payload.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            })
            full_text_parts.append(segment.text.strip())
        
        full_text = " ".join(full_text_parts)
        
        logger.info(f"Transcription completed. Length: {len(full_text)} chars, Segments: {len(segments_payload)}")
        
        return full_text, segments_payload, language
        
    except Exception as e:
        logger.error(f"Transcription failed for {path}: {str(e)}")
        raise
