# Repository Guidelines

## Project Structure & Module Organization
- Core code lives in `app/`: `main.py` (FastAPI app), `worker.py` (queue consumer), `queue.py` (Redis helpers), `stt.py` (Whisper STT), `summarizer.py` (dummy LLM placeholder), `callbacks.py` (webhook delivery), `schemas.py` (Pydantic models), and `config.py` (settings).
- Deployment assets: `Dockerfile`, `docker-compose.yml` for prod GPUs, `docker-compose.mac.yml` for local CPU/dev, `docker-compose.testing.yml` to overlay testing flags.
- Testing artifacts: `test_e2e.sh` submits a sample job; `test_audio/` holds sample audio; `testing_output.log` captures worker output in testing mode.

## Build, Test, and Development Commands
- Build image: `docker build -t transcriber_service .`
- Run stack (prod defaults): `docker compose up -d`
- Enable testing mode: `docker compose -f docker-compose.yml -f docker-compose.testing.yml up -d` (bypasses Whisper, writes mock outputs).
- Submit E2E test: `chmod +x test_e2e.sh && ./test_e2e.sh <callback_url>` after testing stack is up.
- Health check: `curl http://localhost:8000/health`
- Watch worker logs: `docker logs -f transcriber_worker`

## Coding Style & Naming Conventions
- Python 3 with FastAPI/Pydantic; follow PEP8 and 4-space indentation. Prefer type hints and explicit return types.
- HTTP models live in `schemas.py` and should be reused for request/response definitions.
- Config comes from `config.py`/environment variables; avoid hardcoding paths or secrets.
- Function and module names should describe the pipeline step (`stt`, `worker`, `callbacks`, etc.); keep snake_case for variables and functions, PascalCase for Pydantic models.

## Testing Guidelines
- Primary check is the E2E path in testing mode (no GPU): bring up the testing compose stack, run `./test_e2e.sh`, and verify the callback payload plus entries in `testing_output.log`.
- When touching queue/worker logic, also verify `docker logs -f transcriber_worker` for retries and error paths.
- No unit test suite exists yet; add targeted tests alongside new modules if you introduce pure logic (e.g., helper functions or parsers).

## Commit & Pull Request Guidelines
- Use imperative, scoped commit messages (e.g., `Add retry to callback sender`, `Refactor queue backoff`); keep them focused.
- PRs should include: what changed, why, how to test (commands run), and any deployment or env-variable impacts. Link issue IDs when available and attach sample request/response payloads for API changes.
- If behavior impacts callbacks or Redis schemas, note compatibility or migration expectations in the PR description.

## Security & Configuration Tips
- Secrets and URLs must remain in environment variables or compose files; never commit real webhook URLs, tokens, or credentials.
- Confirm GPU targeting before deploy: `WHISPER_DEVICE` (default `cuda:0`) and `LLM_DEVICE` (default `cuda:1` placeholder).
- Keep `TESTING_MODE=true` only in dev/testing; production should run with `TESTING_MODE=false` to load Whisper.
