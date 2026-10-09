# Indian Market RAG: Build Specification

Version 1.3 (frozen). This document is the single source of truth for every build of this project. The same spec is given unchanged to each coding assistant.

## 0. Rules for the coding assistant

- Build one phase per session (section 12). Read sections 1 to 4 once, then only the sections listed for the current phase.
- Do not change any contract in sections 4 to 10: file paths, function names and signatures, JSON fields, environment variable names, fixed strings.
- No orchestration frameworks (no LangChain, LlamaIndex, Haystack or similar). Ask before adding any dependency that is not in section 2.
- Every phase ends with `pytest -q` passing offline: no network, no API keys, no model downloads.
- If the spec is ambiguous, choose the simplest option and record it in `DECISIONS.md` in one line.
- Keep modules small. Do not add features, endpoints or config that the spec does not ask for.
- A phase is not finished until its entry in `build_metrics.json` and `BUILD_LOG.md` is written (section 15.1).
- In `build_metrics.json`, fill only the fields section 15.1 assigns to you and leave the rest as `null`. Never estimate tokens, requests or timestamps.

## 1. Purpose and scope

A question-answering assistant that explains how the Indian stock market works. Every answer is grounded in a fixed document corpus and carries citations.

- In scope: concepts, instruments, market structure, regulation, investor processes, index construction, and the trading, taxation and personal finance topics the corpus covers.
- Out of scope, must refuse: buy, sell or hold advice and stock picking; live or current prices and index levels; anything the corpus does not support.
- Two run modes with identical behaviour: online (Groq) and fully offline (Ollama with `qwen3.5:4b`). Only the generator changes between them.

## 2. Fixed stack

| Area | Choice |
|---|---|
| Language | Python 3.11 |
| PDF parsing | PyMuPDF |
| Embeddings | sentence-transformers, model `sentence-transformers/all-MiniLM-L6-v2`, normalised vectors |
| Embedding device | Ingestion: CUDA if available, else CPU. Query time: CPU |
| Vector store | chromadb, persistent client, one collection `market_docs`, cosine distance |
| LLM, online | Groq SDK, model from `GROQ_MODEL`; verify the model is available at startup |
| LLM, offline | Ollama HTTP API, model `qwen3.5:4b`, thinking disabled, context 4096 |
| LLM, tests | `FakeProvider`: deterministic, no network |
| Embeddings, tests | `FakeEmbedder`: deterministic hashed bag-of-words vectors, no model download |
| API | FastAPI with uvicorn |
| UI | Gradio |
| Tests | pytest |
| Packaging | `requirements.txt` with exact pins (freeze after first install), Dockerfile, GitHub Actions |
| Environment | A virtual environment in `.venv` at the repo root, git-ignored. Every command runs inside it |

## 3. Repository layout

```
indian-market-rag/
  SPEC.md                 this file
  DECISIONS.md            one line per judgment call
  BUILD_LOG.md            per-phase notes: what was built, what failed, how it was fixed
  build_metrics.json      per-phase build metrics (section 15.1)
  README.md
  .env.example
  requirements.txt
  Dockerfile
  .github/workflows/ci.yml
  data/
    manifest.csv
    raw/                  source PDFs (git-ignored)
    chroma/               built index (git-ignored)
  ingest/
    load.py  chunk.py  embed.py  build_index.py
  app/
    config.py  schemas.py  retriever.py  guardrails.py  router.py
    memory.py  prompts.py  pipeline.py  tracing.py  api.py
    llm/
      base.py  groq_provider.py  ollama_provider.py  fake_provider.py
  ui/
    app.py
  eval/
    golden.jsonl  run_eval.py
  logs/                   traces.jsonl (git-ignored)
  tests/
    fixtures/  test_*.py
```

## 4. Configuration

All settings are read from environment variables in `app/config.py`. `.env.example` lists every one.

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | One of groq, ollama, fake. Anything else raises a clear error |
| `GROQ_API_KEY` | empty | Required only when provider is groq |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Checked against the provider's model list at startup |
| `OLLAMA_HOST` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | `qwen3.5:4b` | |
| `OLLAMA_NUM_CTX` | `4096` | |
| `EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | The value `fake` selects `FakeEmbedder`. Changing the model requires a rebuild |
| `EMBED_DEVICE` | `auto` | One of auto, cpu, cuda |
| `CHROMA_DIR` | `data/chroma` | |
| `COLLECTION` | `market_docs` | |
| `CHUNK_SIZE` | `1000` | Characters |
| `CHUNK_OVERLAP` | `150` | Characters |
| `TOP_K` | `5` | |
| `MIN_SCORE` | `0.30` | Cosine similarity gate. Starting value, tuned in phase P6 |
| `HISTORY_TURNS` | `3` | |
| `MAX_TOKENS` | `512` | |
| `TEMPERATURE` | `0.1` | |
| `TRACE_PATH` | `logs/traces.jsonl` | |

## 5. Data contracts

### 5.1 Manifest

`data/manifest.csv` has one row per source document with these columns:

`doc_id, title, publisher, url, licence_note, filename, sha256, fetched_on`

Ingestion stops with a clear error if a listed file is missing from `data/raw/` or its SHA-256 does not match.

### 5.2 Corpus, version 1

| doc_id | Title | Publisher | Where to get it |
|---|---|---|---|
| `sebi_booklet` | Booklet on Securities Market (English) | SEBI | sice.nism.ac.in or nsdl.com (Booklet on Securities Market) |
| `nism_xii` | NISM Series XII: Securities Markets Foundation workbook | NISM | api.nism.ac.in/cmp |
| `varsity_m1` | Introduction to Stock Markets | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m2` | Technical Analysis | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m3` | Fundamental Analysis | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m4` | Futures Trading | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m5` | Options Theory for Professional Trading | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m6` | Option Strategies | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m7` | Markets and Taxation | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m8` | Currency and Commodity Futures | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m9` | Risk Management and Trading Psychology | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m10` | Trading Systems | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m11` | Personal Finance | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `varsity_m14` | Personal Finance: Insurance | Zerodha Varsity | zerodha.com/varsity, module PDF |
| `nifty50_factsheet` | NIFTY 50 factsheet | NSE Indices | niftyindices.com, Factsheet |
| `nifty_methodology` | Methodology document for equity indices | NSE Indices | niftyindices.com, Methodology |

Each file is stored in `data/raw/` as `{doc_id}.pdf`. The PDFs are third-party copyright and are never committed. The manifest stores URLs and checksums only.

### 5.3 Chunk metadata

Every chunk stored in Chroma carries: `chunk_id, doc_id, title, publisher, url, page, section, text`.

- `chunk_id` is `{doc_id}:{page}:{index}`, deterministic across runs.
- `page` is 1-based. `section` is the nearest preceding heading, or an empty string.

### 5.4 Chunking rules

- Clean each page: remove headers and footers that repeat across pages, collapse whitespace, skip pages with fewer than 50 characters.
- Split on paragraph boundaries, targeting `CHUNK_SIZE` characters with `CHUNK_OVERLAP` characters of overlap. Never split inside a word.
- Prefer to start a new chunk at a heading line (a short line with no closing full stop, followed by body text).
- Re-running ingestion upserts by `chunk_id`, so it never creates duplicates.

## 6. Module contracts

Names and signatures are fixed. Models may be dataclasses or pydantic models.

```python
# app/schemas.py
Document(doc_id, title, publisher, url, pages: list[tuple[int, str]])
Chunk(chunk_id, doc_id, title, publisher, url, page, section, text)
RetrievedChunk(chunk: Chunk, score: float)        # cosine similarity
GuardResult(allowed: bool, category: str | None, text: str, message: str | None)
LLMResult(text: str, prompt_tokens: int, completion_tokens: int, model: str)
Citation(n: int, title: str, publisher: str, url: str, page: int)
AnswerResponse(answer: str, citations: list[Citation], refused: bool,
               refusal_category: str | None, trace_id: str, provider: str, model: str)

# ingest/load.py
load_documents(manifest_path: str, raw_dir: str) -> list[Document]
# ingest/chunk.py
chunk_document(doc: Document, size: int, overlap: int) -> list[Chunk]
# ingest/embed.py
class Embedder:        __init__(model_name: str, device: str); embed(texts) -> list[list[float]]
class FakeEmbedder:    embed(texts) -> list[list[float]]
get_embedder(settings, for_query: bool) -> Embedder
# ingest/build_index.py      CLI: python -m ingest.build_index
build_index(settings) -> dict                     # {"documents": n, "chunks": n}

# app/retriever.py
retrieve(query: str, k: int) -> list[RetrievedChunk]          # sorted by score, highest first
# app/guardrails.py
check_input(question: str) -> GuardResult         # .text is the PII-redacted question
check_output(answer: str, chunks: list[RetrievedChunk]) -> GuardResult
# app/router.py
route_input(guard: GuardResult) -> str            # "retrieve" or "refuse"
route_context(chunks: list[RetrievedChunk], min_score: float) -> str   # "generate" or "refuse"
# app/memory.py
class SessionMemory:   add(session_id, role, text); history(session_id) -> list[dict]
rewrite_question(question: str, history: list[dict], llm) -> str
# app/prompts.py
build_messages(question, chunks, history) -> tuple[str, list[dict]]    # (system, messages)
# app/llm/base.py
class LLMProvider(Protocol):   name: str; generate(system: str, messages: list[dict]) -> LLMResult
get_provider(settings) -> LLMProvider
# app/pipeline.py
answer(question: str, session_id: str | None = None) -> AnswerResponse
# app/tracing.py
write_trace(record: dict) -> None                 # appends one JSON line to TRACE_PATH
```

`answer()` is the only entry point used by the API, the UI and the evaluation script.

## 7. Request flow

1. `check_input`: redact PII, then classify. If refused, return the fixed refusal and write a trace. No retrieval and no LLM call.
2. If the session has history, `rewrite_question` makes the question standalone with one LLM call. With no history, skip this step.
3. `retrieve` the top `TOP_K` chunks.
4. `route_context`: if no chunk scores at least `MIN_SCORE`, refuse with category `no_context`. No LLM call.
5. `build_messages` with numbered context blocks, then `generate`.
6. `check_output`: the answer must cite at least one valid context number. If not, replace it with the `no_context` refusal.
7. Append the disclaimer, map cited numbers to `Citation` objects, save the turn to memory, write the trace, return.

## 8. Guardrails

### 8.1 Input rules

The input guard is rule-based only. It makes no LLM call. All patterns live in one list in `app/guardrails.py`.

| Category | Triggers, case-insensitive | Action |
|---|---|---|
| `advice` | Asking whether or what to buy, sell, hold or invest in; "which stock", "best stock", "best share", "recommend", "target price", "will it go up" | Refuse |
| `live_data` | "price", "level", "NAV" or "trading at" together with "today", "now", "current", "latest" or "live" | Refuse |
| `pii` | Any pattern in 8.2 | Redact and continue |

Questions that are simply off-topic are caught by the score gate in step 4, not by keywords.

### 8.2 PII patterns

| Type | Pattern | Replacement |
|---|---|---|
| PAN | `\b[A-Z]{5}[0-9]{4}[A-Z]\b` | `[PAN]` |
| Aadhaar | `\b\d{4}\s?\d{4}\s?\d{4}\b` | `[AADHAAR]` |
| Mobile | `\b(?:\+91[\s-]?)?[6-9]\d{9}\b` | `[PHONE]` |
| Email | `[\w.+-]+@[\w-]+\.[\w.-]+` | `[EMAIL]` |

Only the redacted text reaches retrieval, the LLM, memory and traces. The raw question is never stored.

### 8.3 Output rules

- The answer must contain at least one citation `[n]` where n is between 1 and the number of context blocks supplied. Otherwise refuse with `no_context`.
- Remove any citation number outside that range.
- Append the disclaimer to every answer that is not a refusal.

### 8.4 Fixed strings

```python
REFUSE_ADVICE     = "I can explain how the market works, but I can't give buy, sell or hold recommendations."
REFUSE_LIVE       = "I don't have live market data. I can explain concepts and rules from my source documents."
REFUSE_NO_CONTEXT = "I couldn't find this in my source documents."
DISCLAIMER        = "Educational information only, not investment advice."
```

## 9. Prompt contract

The system prompt must tell the model to:

- Answer only from the numbered context. If the context does not contain the answer, reply with exactly `REFUSE_NO_CONTEXT`.
- Put a citation `[n]` after every factual sentence.
- Give no advice, no predictions and no prices.
- Write plain English, at most 150 words, with no tables.

Each context block is formatted as:

```
[1] {title} (p.{page})
{text}
```

The last `HISTORY_TURNS` turns are passed as prior messages. Generation uses `TEMPERATURE` and `MAX_TOKENS`. The Ollama provider disables thinking mode and sets the context length to `OLLAMA_NUM_CTX`.

## 10. API, response and trace schemas

### 10.1 Endpoints

| Endpoint | Request | Response |
|---|---|---|
| `POST /ask` | `{"question": str, "session_id": str or null}`; question is 1 to 500 characters | 200 with `AnswerResponse`; 422 on invalid input |
| `GET /health` | none | `{"status": "ok", "provider": str, "model": str, "chunks": int}` |

### 10.2 Response example

```json
{
  "answer": "NIFTY 50 is rebalanced semi-annually [1]. Educational information only, not investment advice.",
  "citations": [{"n": 1, "title": "NIFTY 50 factsheet", "publisher": "NSE Indices",
                 "url": "https://www.niftyindices.com", "page": 1}],
  "refused": false,
  "refusal_category": null,
  "trace_id": "b1c6...",
  "provider": "ollama",
  "model": "qwen3.5:4b"
}
```

### 10.3 Trace record

One JSON object per request, appended to `TRACE_PATH`:

`trace_id, ts, session_id, question, rewritten_question, route, guard_category, pii_found, retrieved, provider, model, prompt_tokens, completion_tokens, latency_ms, refused, error`

- `ts` is ISO 8601 in UTC. `question` is the redacted text.
- `route` is one of `refuse_input`, `refuse_context`, `refuse_output`, `answer`.
- `retrieved` is a list of `{"chunk_id": str, "score": float}`.
- `latency_ms` is `{"guard": n, "rewrite": n, "retrieve": n, "generate": n, "total": n}`.

## 11. Evaluation

`eval/golden.jsonl` holds one question per line (Appendix A):

```json
{"id": "Q11", "type": "answer", "question": "How often is the NIFTY 50 rebalanced?",
 "expect_docs": ["nifty50_factsheet", "nifty_methodology"], "expect_category": null, "after": null}
```

`python -m eval.run_eval --provider ollama` runs every question through `answer()`, prints a summary table and writes `eval/report_{provider}.json`. Run it once per provider to compare offline against online.

| Metric | Definition | Target |
|---|---|---|
| Hit rate at 5 | Answer-type questions where a chunk from `expect_docs` is in the top 5 | At least 0.80 |
| Refusal accuracy | Refuse-type questions refused with the expected category | 1.00 |
| Citation rate | Answered questions with at least one valid citation | 1.00 |
| False refusal rate | Answer-type questions that were refused | At most 0.15 |
| Latency | p50 and p95 of total milliseconds | Report only |
| Faithfulness | Optional LLM judge: is each sentence supported by its cited chunk | Report only |

## 12. Build phases

One phase per session. Finish and commit a phase before starting the next. Every phase also ends by recording its build metrics (section 15.1).

| Phase | Build | Read sections | Done when |
|---|---|---|---|
| P0 Scaffold | Layout, config, schemas, `.env.example`, requirements, `FakeProvider`, `FakeEmbedder`, CI skeleton | 2, 3, 4, 6 | `pytest -q` runs clean and `import app` works |
| P1 Ingestion | Load, clean, chunk, embed, build index, manifest checks | 5, 6 | AT-01 to AT-04 pass |
| P2 Retrieve and generate | Retriever, prompts, three providers, happy-path pipeline | 6, 7, 9 | AT-05 to AT-07 pass |
| P3 Guardrails and routing | Input guard, score gate, output guard | 7, 8 | AT-08 to AT-12 pass |
| P4 Memory and tracing | Session memory, question rewrite, trace records | 6, 7, 10 | AT-13 and AT-14 pass |
| P5 API and UI | FastAPI endpoints, Gradio chat with citations shown | 10 | AT-15 passes |
| P6 Evaluation and packaging | Evaluation script, Dockerfile, CI workflow | 11 | AT-16 passes and both evaluation reports exist |

## 13. Acceptance tests

All tests use `LLM_PROVIDER=fake`, `EMBED_MODEL=fake` and small PDFs generated in `tests/fixtures`. They never touch the network.

Each acceptance test is one test function named after its ID, for example `test_at01_index_has_metadata`, so the tests can be counted by ID. Extra tests are welcome but are not counted.

| ID | Phase | Test |
|---|---|---|
| AT-01 | P1 | Building the index from fixtures creates chunks, each with all eight metadata fields |
| AT-02 | P1 | Building twice leaves the chunk count unchanged |
| AT-03 | P1 | No chunk exceeds `CHUNK_SIZE` by more than 10 percent, and consecutive chunks overlap |
| AT-04 | P1 | A missing file or a wrong checksum stops ingestion with a clear error |
| AT-05 | P2 | `retrieve` returns at most k results, sorted by score, with metadata |
| AT-06 | P2 | A supported question returns an answer with a valid citation and the disclaimer |
| AT-07 | P2 | `LLM_PROVIDER` selects groq, ollama or fake; an unknown value raises a clear error |
| AT-08 | P3 | An advice question is refused with category `advice` and no LLM call is made |
| AT-09 | P3 | A live-price question is refused with category `live_data` |
| AT-10 | P3 | PAN, Aadhaar, mobile and email are redacted before the LLM sees the question |
| AT-11 | P3 | An off-topic question is refused with `no_context` and no LLM call is made |
| AT-12 | P3 | An LLM answer with no citation is replaced by the `no_context` refusal |
| AT-13 | P4 | A follow-up triggers one rewrite call; history never exceeds `HISTORY_TURNS` |
| AT-14 | P4 | Each request writes exactly one trace with every field and no raw PII |
| AT-15 | P5 | `/health` and `/ask` match their schemas; an empty question returns 422 |
| AT-16 | P6 | The whole suite passes with networking disabled and no keys set, locally and in CI |

## 14. Where the six pillars live

| Pillar | Implemented in |
|---|---|
| Data governance | `data/manifest.csv` with licence note, date and checksum; PDFs kept out of git; PII never stored |
| Guardrails | `app/guardrails.py`: input rules, score gate, output citation check, disclaimer |
| Tool orchestration | `app/router.py` decides between retrieve, generate and refuse; the retriever is the one tool |
| Memory management | `app/memory.py`: capped per-session history and follow-up rewriting |
| Evaluation metrics | `eval/run_eval.py` and the 40-question golden set |
| Observability and traceability | `app/tracing.py`: one JSON trace per request with latency, tokens and chunk ids |

## 15. Build metrics and cross-assistant comparison

The same project is built once with each coding assistant. This section defines what is recorded so the builds can be compared on equal terms.

### 15.1 Recorded at the end of every phase

Append one entry per phase to `build_metrics.json`, and three to six lines to `BUILD_LOG.md` covering what was built, what failed and how it was fixed.

```json
{
  "assistant": "codex",
  "phases": [
    {
      "phase": "P1",
      "model": "model name and version as reported by the tool, or null",
      "started": null,
      "finished": null,
      "tokens": {"input": null, "output": null, "cached": null, "total": null, "source": null},
      "requests": null,
      "human_prompts": null,
      "fix_prompts": null,
      "tests_expected": 4,
      "tests_passed_first_run": 3,
      "tests_passed_final": 4,
      "quota_hit": null,
      "stopped_at_boundary": true,
      "new_dependencies": [],
      "notes": ""
    }
  ]
}
```

Filled by the assistant:

- `phase`, and `model` if the tool tells you which model is running; otherwise `null`.
- `tests_expected`: the number of acceptance tests that section 13 lists for this phase. For P0 it is 0.
- `tests_passed_first_run`: how many of those acceptance tests passed the first time the suite was run after the code was written. `tests_passed_final`: how many pass at the end. Neither can exceed `tests_expected`, and extra tests are not counted.
- `stopped_at_boundary`: false if you built anything belonging to a later phase.
- `new_dependencies`: packages added in this phase that are not named in section 2. Packages from section 2 are not listed.
- `notes`: one or two sentences.

Left as `null` by the assistant and filled in afterwards by the human:

- `started` and `finished`: UTC timestamps.
- `tokens` and `requests`: read from the tool's own usage readout, with `source` naming where. If the tool shows none, `source` is `not_exposed`. `input` is new input plus cache writes, `cached` is cache reads, and `total` is input plus cached plus output.
- `human_prompts`: every message the human sent in the phase. `fix_prompts`: the subset sent to correct a failure or a spec deviation.
- `quota_hit`: true if a usage limit interrupted the phase.

### 15.2 Measured by the human after phase P6

These are measured the same way in every repository, by the human and not by the assistant, so that no build grades itself.

| Measurement | How |
|---|---|
| Final test result | `pytest -q` on a clean checkout: tests passed out of 16 |
| RAG quality | `python -m eval.run_eval --provider ollama` on the same machine, same corpus, same model |
| Source size | Non-blank lines in `app/`, `ingest/`, `ui/` and `eval/`; test lines counted separately |
| Dependencies | Top-level packages in `requirements.txt` that are not listed in section 2 |
| Lint issues | `ruff check .` with default rules: number of issues |
| Contract deviations | Mismatches against sections 3, 4, 6, 8.4 and 10: paths, env names, signatures, fixed strings, JSON fields |

### 15.3 Comparison scorecard

One column per assistant. Totals are summed over phases P0 to P6.

| Group | Metric | Definition | Better |
|---|---|---|---|
| Cost | Total tokens | Sum of `tokens.total`, with input and output shown separately | Lower |
| Cost | Requests | Sum of `requests` | Lower |
| Cost | Build time | Sum of `finished` minus `started`, in minutes | Lower |
| Cost | Quota interruptions | Number of phases with `quota_hit` true | Lower |
| Effort | Human prompts | Sum of `human_prompts`; the minimum possible is 7 | Lower |
| Effort | Fix prompts | Sum of `fix_prompts` | Lower |
| Correctness | First-run pass rate | Sum of `tests_passed_first_run` divided by 16 | Higher |
| Correctness | Final tests passed | From 15.2, out of 16 | Higher |
| Correctness | Contract deviations | From 15.2 | Lower |
| Correctness | Phase discipline | Phases with `stopped_at_boundary` true, out of 7 | Higher |
| RAG quality | Hit rate at 5 | Section 11 | Higher |
| RAG quality | Refusal accuracy | Section 11 | Higher |
| RAG quality | Citation rate | Section 11 | Higher |
| RAG quality | False refusal rate | Section 11 | Lower |
| RAG quality | Latency p50 | Section 11, milliseconds | Lower |
| Code | Source lines | From 15.2 | Report only |
| Code | Extra dependencies | From 15.2 | Lower |
| Code | Lint issues | From 15.2 | Lower |
| Experience | Setup ease | Human rating, 1 to 5 | Higher |
| Experience | Clarity of plan and explanations | Human rating, 1 to 5 | Higher |
| Experience | Recovery from errors | Human rating, 1 to 5 | Higher |
| Experience | Customisation depth | Human rating, 1 to 5: instruction file, rules, skills, MCP, hooks | Higher |

### 15.4 Fairness rules

- Use the same opening prompt for each phase, word for word, in every assistant. Any further message counts as a human prompt.
- Run every phase in a fresh session, so no build carries conversation history from one phase into the next.
- Start each build in a fresh repository containing only `SPEC.md`, `data/manifest.csv` and `data/raw/`. Do not carry code or hints from one build to the next.
- Always record the model. A result describes the assistant together with the model it used, not the assistant alone.
- Token counts are not exactly comparable between tools, because caching and counting differ. Read them alongside requests, build time and quota interruptions.
- Run the RAG evaluation with the same provider, model and hardware for all five builds.

## Appendix A. Golden set

The expected documents below are best guesses made before ingestion. Check each one against the real corpus after phase P1 and correct `expect_docs` where needed.

| ID | Type | Question | Expect |
|---|---|---|---|
| Q01 | answer | What is SEBI and what is its role? | sebi_booklet, nism_xii |
| Q02 | answer | What is the difference between the primary market and the secondary market? | sebi_booklet, nism_xii, varsity_m1 |
| Q03 | answer | What is a demat account and why is it needed? | sebi_booklet, varsity_m1 |
| Q04 | answer | What does a stock broker do? | sebi_booklet, varsity_m1 |
| Q05 | answer | What is an IPO? | varsity_m1, sebi_booklet |
| Q06 | answer | What are the key risks of investing in the securities market? | sebi_booklet |
| Q07 | answer | How can an investor raise a grievance against a stock broker? | sebi_booklet |
| Q08 | answer | What is the Investor Protection Fund? | sebi_booklet |
| Q09 | answer | What is a depository? | sebi_booklet, nism_xii |
| Q10 | answer | What is the NIFTY 50? | nifty50_factsheet, varsity_m1 |
| Q11 | answer | How often is the NIFTY 50 rebalanced? | nifty50_factsheet, nifty_methodology |
| Q12 | answer | What method is used to compute the NIFTY 50? | nifty50_factsheet, nifty_methodology |
| Q13 | answer | What are the eligibility criteria for a stock to be included in the NIFTY 50? | nifty_methodology |
| Q14 | answer | What is market capitalisation? | varsity_m1, varsity_m3 |
| Q15 | answer | What is a candlestick chart? | varsity_m2 |
| Q16 | answer | What are support and resistance levels? | varsity_m2 |
| Q17 | answer | What is the price to earnings ratio? | varsity_m3 |
| Q18 | answer | What does a company's annual report contain? | varsity_m3 |
| Q19 | answer | What is a futures contract? | varsity_m4, varsity_m8, sebi_booklet |
| Q20 | answer | What is margin in futures trading? | varsity_m4, varsity_m8 |
| Q21 | answer | What is the difference between a call option and a put option? | varsity_m5, varsity_m6 |
| Q22 | answer | What is an option premium? | varsity_m5, varsity_m6 |
| Q23 | answer | How does a futures contract differ from an options contract? | varsity_m4, varsity_m5, sebi_booklet |
| Q24 | followup | (asked after Q10) How many companies are in it? | nifty50_factsheet |
| Q25 | pii | My PAN is ABCDE1234F. How do I open a demat account? | Answered; PAN redacted in trace |
| Q26 | refuse | Should I buy Reliance shares now? | advice |
| Q27 | refuse | Which stock will give the best return this year? | advice |
| Q28 | refuse | What is the NIFTY 50 level today? | live_data |
| Q29 | refuse | What is the current share price of TCS? | live_data |
| Q30 | refuse | What is the capital of France? | no_context |
| Q31 | answer | What is a bull call spread? | varsity_m6 |
| Q32 | answer | What is a long straddle? | varsity_m6 |
| Q33 | answer | What is securities transaction tax? | varsity_m7 |
| Q34 | answer | How is income from trading classified for tax purposes? | varsity_m7 |
| Q35 | answer | What is a currency pair? | varsity_m8 |
| Q36 | answer | What is position sizing? | varsity_m9 |
| Q37 | answer | What is pair trading? | varsity_m10 |
| Q38 | answer | What is the expense ratio of a mutual fund? | varsity_m11 |
| Q39 | answer | What is the difference between a direct plan and a regular plan of a mutual fund? | varsity_m11 |
| Q40 | answer | What is term insurance? | varsity_m14 |
