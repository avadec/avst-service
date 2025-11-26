#!/bin/bash
# E2E Testing script for transcriber service in TESTING_MODE

echo "==================================================="
echo "E2E Testing Mode Script"
echo "==================================================="
echo ""

# Create a dummy audio file path (doesn't need to exist in testing mode)
AUDIO_PATH="/mnt/audio/sample_call.wav"

# Webhook.site or your test callback URL
# CALLBACK_URL="${1:-https://webhook.site/unique-id}"
CALLBACK_URL=""


echo "Testing Configuration:"
echo "  Audio Path: $AUDIO_PATH"
echo "  Callback URL: $CALLBACK_URL"
echo ""

echo "Submitting transcription job..."
RESPONSE=$(curl -s -X POST http://localhost:8000/transcriptions \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_path\": \"$AUDIO_PATH\",
    \"agent_id\": \"test-agent-123\",
    \"callback_url\": \"$CALLBACK_URL\",
    \"metadata\": {
      \"test_mode\": true,
      \"call_id\": \"test_call_001\"
    }
  }")

echo "Response:"
echo "$RESPONSE" | python3 -m json.tool
echo ""

JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)

if [ -n "$JOB_ID" ]; then
  echo "Job submitted successfully: $JOB_ID"
  echo ""
  echo "Monitor worker logs with:"
  echo "  docker logs -f transcriber_worker"
  echo ""
  echo "Check testing output log inside container:"
  echo "  docker exec transcriber_worker cat /app/testing_output.log"
else
  echo "Failed to submit job"
fi
