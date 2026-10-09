# Indian Market RAG

A question-answering assistant that explains how the Indian stock market
works. Every answer is grounded in a fixed, local document corpus and
carries citations. Out of scope — and refused — are buy/sell/hold advice and
live or current prices (see `SPEC.md`, the single source of truth for this
build).

Two interchangeable run modes:

- **Offline**: `LLM_PROVIDER=ollama`, local `qwen3.5:4b` via the Ollama HTTP
  API. No network calls at all once the model is pulled.
- **Online**: `LLM_PROVIDER=groq`, hosted via the Groq API.

Only the generator differs between the two; retrieval, guardrails, memory
and tracing are identical.

## Setup

```bash
python -m venv .venv
. .venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # then edit values as needed
```

Load `.env` into your shell before running anything (there is no
`python-dotenv` dependency — see `DECISIONS.md`):

```bash
set -a; source .env; set +a      # bash/zsh
```

On PowerShell:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') { Set-Item "Env:$($Matches[1])" $Matches[2] }
}
```

### Corpus

Place the source PDFs listed in `data/manifest.csv` into `data/raw/` as
`{doc_id}.pdf` (see SPEC.md section 5.2 for where to get each one; they are
third-party copyright and are never committed to git). `nism_xii` and
`nifty_methodology` are not yet in this build's manifest — see
`DECISIONS.md`. The 14 documents that are present build to 4294 chunks.

### Offline mode (Ollama)

Install [Ollama](https://ollama.com), then:

```bash
ollama pull qwen3.5:4b
ollama serve   # if not already running
```

## Usage

Build the index, then ask a question:

```bash
python cli.py index
python cli.py ask "What is a demat account?"
python cli.py ask "How many companies are in it?" --session-id s1   # follow-up, same session
```

`cli.py index` and `cli.py ask` give a clear error and a non-zero exit code
if `data/manifest.csv`, `data/raw/*.pdf`, or the question text is missing.

Or run the API and UI:

```bash
uvicorn app.api:app --reload
python ui/app.py
```

```bash
curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"question": "What is a demat account?", "session_id": null}'
curl localhost:8000/health
```

## Tests

All 16 acceptance tests (SPEC.md section 13) plus a few extras run fully
offline, with `LLM_PROVIDER=fake` and `EMBED_MODEL=fake` set per-test by
`tests/conftest.py` — no network, no API keys, no model downloads:

```bash
pytest -q
```

## Evaluation

```bash
python -m eval.run_eval --provider ollama
python -m eval.run_eval --provider groq
```

Each run scores the 40-question golden set (`eval/golden.jsonl`, SPEC.md
Appendix A) and writes `eval/report_{provider}.json`.

## Docker

```bash
docker build -t indian-market-rag .
docker run -p 8000:8000 --env-file .env indian-market-rag
```

The container serves the FastAPI app; mount `data/` as a volume if you want
the index to persist outside the container.

## Project layout

See SPEC.md section 3. The only entry point used by the API, the UI and the
evaluation script is `app.pipeline.answer()`.

## Deployment

See `DEPLOYMENT_ROADMAP.md` (in the parent `RAGs/` folder) for hosting,
containerization and production-persistence notes.
