"""python -m eval.run_eval --provider ollama. See SPEC.md section 11."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

GOLDEN_PATH = Path(__file__).parent / "golden.jsonl"


def _load_golden() -> list[dict]:
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))
    return ordered[idx]


def _last_trace_line(trace_path: Path) -> dict:
    with open(trace_path, encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip()]
    return json.loads(lines[-1])


def run_eval(provider: str) -> dict:
    os.environ["LLM_PROVIDER"] = provider

    # Imported after LLM_PROVIDER is set so settings read it on first use.
    from app.config import get_settings
    from app.pipeline import answer
    from app.retriever import retrieve

    settings = get_settings()
    trace_path = Path(settings.trace_path)

    golden = _load_golden()
    sessions: dict[str, str] = {}
    results = []

    for row in golden:
        session_id = sessions.get(row["after"], row["id"])
        sessions[row["id"]] = session_id

        resp = answer(row["question"], session_id)
        trace = _last_trace_line(trace_path)

        hit = None
        if row["type"] == "answer" and row["expect_docs"]:
            top_docs = {rc.chunk.doc_id for rc in retrieve(row["question"], settings.top_k)}
            hit = bool(top_docs & set(row["expect_docs"]))

        results.append(
            {
                "id": row["id"],
                "type": row["type"],
                "refused": resp.refused,
                "refusal_category": resp.refusal_category,
                "expect_category": row["expect_category"],
                "n_citations": len(resp.citations),
                "hit": hit,
                "latency_ms_total": trace["latency_ms"]["total"],
            }
        )

    answer_rows = [r for r in results if r["type"] == "answer"]
    refuse_rows = [r for r in results if r["type"] == "refuse"]
    answered_rows = [r for r in results if not r["refused"]]

    hits = [r["hit"] for r in answer_rows if r["hit"] is not None]
    hit_rate_at_5 = sum(hits) / len(hits) if hits else 0.0

    refusal_correct = [r for r in refuse_rows if r["refused"] and r["refusal_category"] == r["expect_category"]]
    refusal_accuracy = len(refusal_correct) / len(refuse_rows) if refuse_rows else 0.0

    cited = [r for r in answered_rows if r["n_citations"] >= 1]
    citation_rate = len(cited) / len(answered_rows) if answered_rows else 0.0

    false_refusals = [r for r in answer_rows if r["refused"]]
    false_refusal_rate = len(false_refusals) / len(answer_rows) if answer_rows else 0.0

    latencies = [r["latency_ms_total"] for r in results]

    report = {
        "provider": provider,
        "n_questions": len(results),
        "hit_rate_at_5": round(hit_rate_at_5, 3),
        "refusal_accuracy": round(refusal_accuracy, 3),
        "citation_rate": round(citation_rate, 3),
        "false_refusal_rate": round(false_refusal_rate, 3),
        "latency_ms_p50": _percentile(latencies, 50),
        "latency_ms_p95": _percentile(latencies, 95),
        # Faithfulness is an optional LLM-judge metric (section 11); not
        # computed here to avoid an extra, unrequested LLM dependency.
        "faithfulness": None,
    }

    report_path = Path(__file__).parent / f"report_{provider}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    _print_summary(report)
    return report


def _print_summary(report: dict) -> None:
    print(f"Provider: {report['provider']}  (n={report['n_questions']})")
    print(f"{'Metric':<20}{'Value':>10}")
    for key in (
        "hit_rate_at_5",
        "refusal_accuracy",
        "citation_rate",
        "false_refusal_rate",
        "latency_ms_p50",
        "latency_ms_p95",
    ):
        print(f"{key:<20}{report[key]:>10}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["groq", "ollama", "fake"], required=True)
    args = parser.parse_args(argv)
    run_eval(args.provider)
    return 0


if __name__ == "__main__":
    sys.exit(main())
