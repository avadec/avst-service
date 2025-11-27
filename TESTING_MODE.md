# Testing Mode Guide

## Overview

The transcriber service includes a **TESTING_MODE** that allows you to debug the E2E pipeline without requiring GPUs or actual audio processing. In testing mode:

- ✅ Whisper STT is **bypassed** - no model loading, no GPU needed
- ✅ Returns **mock transcript data** 
- ✅ Writes output to **console** and **log file** (`/app/testing_output.log`)
- ✅ Allows testing the complete pipeline: API → Redis → Worker → Callback
- ✅ Pipeline toggles are set to **skip STT, summarization, and callbacks** in the testing compose overlay

## Quick Start - Testing Mode

### Option 1: Using the testing compose file

```bash
# Build the image
docker build -t transcriber_service .

# Start services in TESTING_MODE
docker compose -f docker-compose.yml -f docker-compose.testing.yml up -d

# Run the test script
chmod +x test_e2e.sh
./test_e2e.sh https://webhook.site/your-unique-url

# View worker logs
docker logs -f transcriber_worker

# View testing output log
cat testing_output.log
```

### Option 2: Set environment variable directly

Edit `docker-compose.yml` and change:
```yaml
- TESTING_MODE=false
```
to:
```yaml
- TESTING_MODE=true
```

Then:
```bash
docker compose up -d
```

## Testing Mode Behavior

### What happens in testing mode:

1. **API receives request** - Same as production
2. **Job enqueued to Redis** - Same as production  
3. **Worker picks up job** - Same as production
4. **STT Processing** - MOCKED:
   - Logs: `STT processed (TESTING MODE): /path/to/file.wav`
   - Returns dummy transcript text
   - Returns 4 mock segments with timestamps
   - Returns language code "en"
5. **Summarization** - Same dummy behavior as production
6. **Callback sent** - Same as production

### Output locations:

1. **Console/Docker logs**:
   ```bash
   docker logs -f transcriber_worker
   ```
   Shows: `[timestamp] STT processed (TESTING MODE): /path/to/file.wav`

2. **Testing log file** (`testing_output.log`):
   - Inside container: `/app/testing_output.log`
   - On host (with testing compose): `./testing_output.log`
   
   Content example:
   ```
   [2025-11-26T10:30:45.123456] STT processed (TESTING MODE): /mnt/audio/test.wav
   [2025-11-26T10:30:45.234567] Mock STT complete - Text length: 156 chars, Segments: 4, Language: en
   ```

## Example Test

```bash
# Submit a test job
curl -X POST http://localhost:8000/transcriptions \
  -H "Content-Type: application/json" \
  -d '{
    "audio_path": "/mnt/audio/fake_file.wav",
    "agent_id": "test-agent",
    "callback_url": "https://webhook.site/your-url",
    "metadata": {"test": true}
  }'
```

Expected callback payload:
```json
{
  "job_id": "uuid-here",
  "status": "done",
  "audio_path": "/mnt/audio/fake_file.wav",
  "agent_id": "test-agent",
  "transcript": "This is a test transcription. The audio file has been processed in testing mode. No actual STT was performed. This is dummy data for E2E pipeline testing.",
  "summary": "Summary (dummy, future LLM on cuda:1): This is a test transcription. The audio file has been processed in testing mode. No actual STT was performed. This is dummy data for E2E pipeline testing.",
  "language": "en",
  "segments": [
    {"start": 0.0, "end": 3.5, "text": "This is a test transcription."},
    {"start": 3.5, "end": 7.2, "text": "The audio file has been processed in testing mode."},
    {"start": 7.2, "end": 10.8, "text": "No actual STT was performed."},
    {"start": 10.8, "end": 15.0, "text": "This is dummy data for E2E pipeline testing."}
  ],
  "metadata": {"test": true}
}
```

## Switching Back to Production Mode

```bash
# Stop containers
docker compose down

# Edit docker-compose.yml or use default compose file
# Ensure: TESTING_MODE=false

# Restart with GPU support
docker compose up -d
```

## Troubleshooting

### Testing log file not appearing
- Check worker logs: `docker logs transcriber_worker`
- Verify TESTING_MODE=true: `docker exec transcriber_worker env | grep TESTING`
- Check file permissions

### Still loading Whisper model
- Confirm TESTING_MODE=true in environment
- Rebuild image if config was changed after build
- Check logs for "TESTING MODE enabled - Whisper model NOT loaded"

## Configuration Variables

| Variable | Testing Value | Production Value |
|----------|--------------|------------------|
| `TESTING_MODE` | `true` | `false` |
| `TESTING_LOG_FILE` | `/app/testing_output.log` | `/app/testing_output.log` |
| `ENABLE_STT` | `false` | `true` |
| `ENABLE_SUMMARIZATION` | `false` | `true` |
| `ENABLE_CALLBACK` | `false` | `true` |

## Benefits of Testing Mode

1. **Fast development** - No GPU, no model loading (saves ~30s startup)
2. **Debug pipeline** - Test Redis, callbacks, error handling
3. **Local testing** - Works on any machine without NVIDIA GPU
4. **Integration tests** - Validate E2E flow before deploying
