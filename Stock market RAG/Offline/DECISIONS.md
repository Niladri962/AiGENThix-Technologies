# Decisions

One line per judgment call where SPEC.md was silent or ambiguous.

- `BUILD_LOG.md` and `build_metrics.json` (section 15, repo layout in section 3)
  are not created: both exist solely to support section 15's cross-assistant
  benchmarking/comparison exercise, which was explicitly excluded from this
  build. Every other phase (P0–P6) is implemented.

- Python 3.11 is pinned by SPEC.md, but only Python 3.12 was available in the
  build environment. The code uses no 3.11-only syntax; `Dockerfile` and CI
  still pin `python:3.11-slim` / `python-version: "3.11"` per the spec.
- `data/manifest.csv` lists 14 of the 16 corpus documents in section 5.2;
  `nism_xii` (NISM workbook) and `nifty_methodology` (NSE Indices methodology
  document) were not available to download, so they are omitted from the
  manifest rather than listed with a missing file. Add them with their
  checksums once sourced; ingestion will pick them up on the next build. A
  real build of this index produces 14 documents / 4294 chunks.
- `app/config.py`'s `Settings` is a frozen (hashable) dataclass so that
  `lru_cache` can memoize `get_provider()` and the retriever's Chroma
  collection/embedder per distinct configuration, avoiding a repeated Groq
  model-list network call and SentenceTransformer reload on every request.
- No `python-dotenv` dependency: it is not in section 2's fixed stack, and
  section 0 says to ask before adding dependencies outside it. `.env.example`
  documents the variables; load them via your shell or `--env-file` in Docker.
- `Citation` and `AnswerResponse` in `app/schemas.py` are pydantic models (the
  rest are dataclasses) so FastAPI can use them directly as request/response
  models, per section 6's "Models may be dataclasses or pydantic models."
- PDF page cleaning (strip repeated headers/footers, collapse whitespace, skip
  pages under 50 characters) lives in `ingest/load.py` when building each
  `Document`, since `Document.pages` is defined as already-clean text.
- Heading detection in `ingest/chunk.py` looks at a block's *first line*, not
  the whole block, because PDF text extraction does not reliably preserve the
  blank line between a heading and the paragraph that follows it. This also
  matches section 5.4's "a short line ... followed by body text" wording more
  literally than "the heading is its own paragraph" would.
- Chunk IDs (`{doc_id}:{page}:{index}`) use a per-page index starting at 0;
  `page` in the ID already disambiguates across pages.
- At a heading boundary, the chunker flushes the current buffer without
  carrying the overlap tail across it ("prefer to start a new chunk at a
  heading line" reads as a clean break, not a stitched one).
- `GuardResult.category` is `"pii"` when `check_input` redacted something but
  did not refuse, so traces can record that PII was present even on an
  answered turn; it is `None` when nothing was found.
- `SessionMemory` interprets `HISTORY_TURNS` as exchanges (user + assistant),
  so it caps stored entries at `history_turns * 2`, trimmed on `add()`.
- Session memory and the trace's `pii_found` flag are not written for
  `refuse_input` or `refuse_context`/`refuse_output` turns — only the final
  "answer" route (section 7 step 7) explicitly calls for saving to memory;
  trace writing still happens for every route.
- `FakeEmbedder` (`ingest/embed.py`) hashes words into a 1024-dim space rather
  than a smaller one, to keep accidental bucket collisions between unrelated
  words rare enough that off-topic questions reliably score under `MIN_SCORE`
  in tests.
- `FakeProvider` distinguishes a rewrite call from an answer call by comparing
  the system prompt to `REWRITE_SYSTEM` exactly; it is deterministic and
  network-free, matching section 2's requirement, not a semantically correct
  rewriter.
- `eval/run_eval.py` scores `hit_rate_at_5` and `false_refusal_rate` only over
  `type == "answer"` rows and `citation_rate` over every answered row
  (regardless of type), following section 11's wording ("Answer-type
  questions" vs. "Answered questions") literally.
- The optional LLM-judge "faithfulness" metric (section 11) is reported as
  `null` in `eval/report_{provider}.json`: it is explicitly optional, and
  adding an extra judge call was not required to meet the spec.
- `eval/run_eval.py` assigns each golden question its own session, except a
  `followup` row (`after` set), which reuses the session of the question it
  follows, so history and rewriting behave as they would in a real session.
- `MIN_SCORE` tuned from 0.30 (SPEC.md's starting value) to **0.40** in P6,
  per section 12's "starting value, tuned in phase P6." Against the real
  14-document corpus with the real MiniLM embedder, "What is the capital of
  France?" (Q30, expected `no_context`) scored 0.344 — above 0.30 — while
  every `answer`-type golden question's best chunk scored 0.53 or higher.
  0.40 sits in that gap, fixing Q30's refusal without affecting any other
  golden question. No other setting was changed to move the eval numbers.
