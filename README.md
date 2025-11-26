# Transcriber Service

GPU-enabled audio processing microservice with FastAPI, Whisper STT, and placeholder for future LLM summarisation.

## Overview

This service provides a complete audio transcription pipeline:
1. **FastAPI API** - Accepts transcription requests via HTTP
2. **Redis Queue** - Manages job queue between API and worker
3. **Worker Process** - Processes jobs using:
   - **Whisper STT on GPU 0** - Speech-to-text using faster-whisper
   - **Summarisation on GPU 1** - Currently dummy implementation, ready for future LLM integration

## Architecture

```
┌─────────────┐      ┌─────────┐      ┌──────────────┐
│   Client    │─────▶│   API   │─────▶│    Redis     │
└─────────────┘      └─────────┘      └──────────────┘
                                              │
                                              ▼
                                       ┌──────────────┐
                                       │    Worker    │
                                       │              │
                                       │  GPU 0: STT  │
                                       │  GPU 1: LLM  │
                                       └──────────────┘
                                              │
                                              ▼
                                       ┌──────────────┐
                                       │   Callback   │
                                       └──────────────┘
```

## Requirements

- Docker with NVIDIA GPU support (nvidia-docker2)
- Two NVIDIA GPUs (e.g., RTX 5090 x2)
- Network-mounted audio folder accessible to the host

## Quick Start

### 1. Build the Docker image

```bash
cd transcriber_service
docker build -t transcriber_service .
```

### 2. Configure your environment

Edit `docker-compose.yml` to:
- Update the audio volume mount path (currently `/mnt/audio:/mnt/audio:ro`)
- Set your default callback URL in environment variables
- Adjust Whisper model if needed (default: `large-v3`)

### 3. Start the services

```bash
docker compose up -d
```

This starts:
- **Redis** on port 6379
- **API** on port 8000
- **Worker** with access to both GPUs

### 4. Check service health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "ok"}
```

## Usage

### Submit a transcription job

```bash
curl -X POST http://localhost:8000/transcriptions \
  -H "Content-Type: application/json" \
  -d '{
    "audio_path": "/mnt/audio/calls/2025-11-25/call_123.wav",
    "agent_id": "agent-42",
    "callback_url": "https://webhook.site/your-test-url",
    "metadata": {
      "call_id": "call_123",
      "direction": "inbound"
    }
  }'
```

### Response

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued"
}
```

### Callback Payload (Success)

The worker will POST to your callback URL:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "done",
  "audio_path": "/mnt/audio/calls/2025-11-25/call_123.wav",
  "agent_id": "agent-42",
  "transcript": "Full transcript text here...",
  "summary": "Summary (dummy, future LLM on cuda:1): Full transcript text...",
  "language": "en",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Hello, how can I help you?"
    }
  ],
  "metadata": {
    "call_id": "call_123",
    "direction": "inbound"
  }
}
```

### Callback Payload (Error)

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "error",
  "error": "Audio file not found: /mnt/audio/calls/2025-11-25/call_123.wav",
  "audio_path": "/mnt/audio/calls/2025-11-25/call_123.wav",
  "agent_id": "agent-42",
  "metadata": {
    "call_id": "call_123",
    "direction": "inbound"
  }
}
```

## Configuration

Environment variables (set in `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `DEFAULT_CALLBACK_URL` | None | Default callback URL if not provided in request |
| `WHISPER_MODEL` | `large-v3` | Whisper model to use (tiny, base, small, medium, large-v3) |
| `WHISPER_DEVICE` | `cuda:0` | GPU device for Whisper STT |
| `WHISPER_COMPUTE_TYPE` | `float16` | Compute precision (float16, int8) |
| `LLM_DEVICE` | `cuda:1` | GPU device for future LLM (currently unused) |
| `CALLBACK_TIMEOUT_SECONDS` | `30` | HTTP timeout for callbacks |
| `CALLBACK_RETRY_COUNT` | `3` | Number of callback retry attempts |
| `CALLBACK_RETRY_DELAY_SECONDS` | `3` | Delay between callback retries |

## Project Structure

```
transcriber_service/
├── app/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # FastAPI application
│   ├── schemas.py           # Pydantic models
│   ├── config.py            # Configuration management
│   ├── queue.py             # Redis queue helpers
│   ├── worker.py            # Worker main loop
│   ├── stt.py               # Whisper STT wrapper (GPU 0)
│   ├── summarizer.py        # Dummy summarizer (future GPU 1)
│   └── callbacks.py         # Callback sending logic
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Multi-container orchestration
└── README.md                # This file
```

## Future LLM Integration

The summarisation is currently a **dummy implementation** in `app/summarizer.py`. To integrate a real LLM on GPU 1:

### Current Implementation (Dummy)

```python
def summarize_text(text: str, max_chars: int = 500) -> str:
    trimmed_text = text[:max_chars]
    if len(text) > max_chars:
        trimmed_text += "..."
    return f"Summary (dummy, future LLM on {settings.LLM_DEVICE}): {trimmed_text}"
```

### Future Implementation (Example with HuggingFace)

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
from .config import settings

# Load model on GPU 1
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-2-7b-chat-hf")
model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-2-7b-chat-hf")
model = model.to(settings.LLM_DEVICE)  # cuda:1

def summarize_text(text: str, max_chars: int = 2000) -> str:
    prompt = f"Summarize this conversation:\n\n{text[:max_chars]}"
    inputs = tokenizer(prompt, return_tensors="pt").to(settings.LLM_DEVICE)
    outputs = model.generate(**inputs, max_new_tokens=200)
    summary = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return summary
```

Simply replace the function in `app/summarizer.py` with your LLM implementation.

## Logs

View logs for each service:

```bash
# API logs
docker logs -f transcriber_api

# Worker logs
docker logs -f transcriber_worker

# Redis logs
docker logs -f transcriber_redis
```

## Troubleshooting

### GPU not accessible in worker

Ensure NVIDIA Docker runtime is installed:

```bash
# Check NVIDIA Docker runtime
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

### Audio file not found

Ensure:
1. The network share is mounted on the host at `/mnt/audio`
2. The path in `docker-compose.yml` matches your mount point
3. The path in the API request matches the path inside the container

### Worker not processing jobs

Check:
1. Redis is running: `docker logs transcriber_redis`
2. Worker is running: `docker logs transcriber_worker`
3. Jobs are being enqueued: Check API logs

## Development

Run locally without Docker:

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis
redis-server

# Run API
uvicorn app.main:app --reload

# Run worker (in another terminal)
python -m app.worker
```

## License

[Your License Here]
