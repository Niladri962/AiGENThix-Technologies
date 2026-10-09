# Deployment Roadmap: Indian Market RAG

Practical path from the local build in `indian-market-rag/` to a live,
internet-reachable service. Assumes the FastAPI app (`app.api:app`) as the
thing being deployed; the Gradio UI is optional and can point at the same
API or run as a second small service.

## 1. Hosting options

| Option | When to use it | Notes |
|---|---|---|
| Single VM (e.g. a $10–40/mo droplet/EC2/Lightsail box) | Default choice for this project's scale | Runs the API container, Chroma data on a mounted disk, and (optionally) Ollama on the same box if it has enough RAM/CPU for `qwen3.5:4b` |
| Managed container platform (Fly.io, Render, Railway, Cloud Run) | You want push-to-deploy and don't want to manage a VM | Cloud Run/Fly scale to zero, which kills in-memory session history and the SentenceTransformer warm cache on every cold start — expect a multi-second first request after idling |
| Kubernetes | Only if you already run k8s for other services | Overkill for a single-container RAG API; skip unless there's an existing cluster |

**Recommendation**: one VM with Docker Compose running two containers (API,
Ollama) plus a persistent volume. It matches the "offline mode" design goal
(no external LLM dependency) and avoids managed-platform cold-start quirks.
Move to Groq (`LLM_PROVIDER=groq`) instead of a VM-hosted Ollama if you'd
rather not provision GPU/CPU for the model at all.

## 2. Containerization

- The existing `Dockerfile` is sufficient for the API. Add a
  `docker-compose.yml` with two services:
  - `api`: builds from `Dockerfile`, depends on a populated `data/chroma`
    volume.
  - `ollama`: official `ollama/ollama` image, with `ollama pull qwen3.5:4b`
    run once after first start (or baked into a custom image's entrypoint).
- Run the API as a non-root user in the image (`USER app` after a
  `RUN useradd -m app`) — the stock `python:3.11-slim` image runs as root by
  default.
- Pin the base image digest (not just the tag) once the build is stable, to
  avoid silent upstream base-image changes breaking a rebuild.

## 3. Embedding and LLM dependencies in production

- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (~90MB) downloads
  from Hugging Face on first use unless baked into the image. For a
  reproducible deploy, download it at build time (`RUN python -c "from
  sentence_transformers import SentenceTransformer;
  SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"`) so the
  running container never needs Hugging Face reachability. Cache it in a
  Docker layer so rebuilds that only change app code don't re-download it.
- **Ollama**: `qwen3.5:4b` needs the model pulled once per host/volume, not
  per container restart — pull it into a named volume that both the
  `ollama` container and any replacement container reuse.
- **Groq**: no local dependency, but it's a hard external dependency at
  request time — treat its outage as a user-facing failure mode (surface the
  Groq error, don't retry silently and don't fall back to a different model
  without telling anyone).
- Keep `EMBED_DEVICE=cpu` in production unless you've specifically
  provisioned a GPU box; `auto`/`cuda` will silently fail or fall back if no
  GPU driver is present.

## 4. Data persistence

- `data/chroma/` (the vector index) and `logs/traces.jsonl` must live on a
  volume that survives container restarts and redeploys — never bake them
  into the image or let them live only in the container's writable layer.
- Ingestion (`python -m ingest.build_index` / `cli.py index`) is a one-time
  or occasional batch job, not something the API runs on every request. Run
  it as a separate deploy step or a manually-triggered job against the same
  volume the API reads from, and avoid running it concurrently with live
  traffic against the same Chroma directory (SQLite-backed, single-writer).
- Back up `data/chroma/` and `data/manifest.csv` together — the index is
  only reproducible if you still have the source PDFs and manifest that
  built it, since the PDFs themselves are never committed to git.
- Rotate or ship `logs/traces.jsonl` off the box periodically (it grows
  unbounded, one line per request) — a simple logrotate rule or a scheduled
  upload to object storage is enough at this scale.

## 5. Security basics

- **Secrets**: `GROQ_API_KEY` goes in the platform's secret store (Docker
  secrets, the VM's `.env` with `chmod 600`, or the managed platform's env-var
  vault) — never in the image, never in git. `.env` is already git-ignored;
  keep it that way.
- **Network exposure**: put the API behind a reverse proxy (Caddy or nginx)
  terminating TLS; don't expose uvicorn directly on port 8000 to the
  internet. Don't expose Ollama's port (11434) publicly at all — it has no
  auth — bind it to localhost or the Docker-internal network only.
- **Access control**: there is no auth on `/ask` or `/health` today. Before
  going live, add at minimum an API key header check (FastAPI dependency) or
  put the proxy in charge of auth, especially since each `/ask` call costs
  an LLM request.
- **Rate limiting**: add a basic per-IP or per-key rate limit at the proxy
  (or `slowapi`) — unauthenticated or lightly-authenticated LLM endpoints are
  a common cost-abuse target.
- **Input size**: the 500-character question limit (section 10.1) is
  already enforced by the schema; keep it — it bounds prompt-injection
  surface and token cost per request.
- **PII**: traces already store only the redacted question (section 8.2) —
  don't add a debug path that logs the raw question anywhere (stdout,
  reverse-proxy access logs with query strings, etc.).

## 6. Ordered steps

1. Bake the embedding model into the Docker image at build time; confirm
   `docker build` succeeds offline after that (no network needed at
   container start).
2. Write `docker-compose.yml` wiring the API container to a named volume for
   `data/chroma` and `logs/`, plus the `ollama` service with its own named
   volume for pulled models.
3. Provision the VM (or managed platform), install Docker/Compose, copy
   `docker-compose.yml`, `.env` (secrets filled in, not from git), and the
   sourced `data/raw/*.pdf` + `data/manifest.csv`.
4. Run `cli.py index` (or `docker compose run api python cli.py index`)
   once against the mounted volume to build the real index; confirm
   `documents`/`chunks` counts look right.
5. Start the stack (`docker compose up -d`), pull the Ollama model into its
   volume, hit `/health` locally on the box to confirm `chunks > 0` and the
   configured provider/model.
6. Put a reverse proxy in front with TLS and an API-key check; confirm
   `/ask` is unreachable without the key and reachable with it.
7. Point DNS at the box/platform, confirm end-to-end over HTTPS from
   outside the network.
8. Set up log rotation for `logs/traces.jsonl` and a backup job for
   `data/chroma/` + `data/manifest.csv`.
9. Run `python -m eval.run_eval --provider ollama` (and `--provider groq` if
   that key is configured) against the live deployment's data to confirm
   production RAG quality matches the local evaluation before announcing it
   as live.
