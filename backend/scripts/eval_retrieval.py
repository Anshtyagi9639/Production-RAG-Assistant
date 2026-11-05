"""Measure retrieval against a labelled question set, to calibrate RETRIEVAL_SCORE_THRESHOLD and
to compare retrieval changes on the same data.

Run from backend/:  python scripts/eval_retrieval.py [eval/seed_retrieval.json]

Read-only: it embeds each question (a few OpenAI embedding calls) and searches the workspace
named in the file, through the app's own retrieval code with the configured TOP_K. Prints
questions, filenames and scores, never document text or credentials.

Each case lists the passage that answers it, or null when nothing in the workspace does.
Reported at the configured threshold and at a sweep of thresholds:
  hit@1 / hit@k  answerable questions whose passage is the top result / in the top k
  MRR            mean reciprocal rank of that passage (0 when missed)
  rejected       unanswerable questions where every result falls below the threshold, so
                 chat answers "not enough information" instead of calling the model
"""

import asyncio
import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.embeddings import OpenAIEmbedder
from app.ai.retrieval import KnowledgeRetriever, RetrievedChunk
from app.core.config import get_settings
from app.db.qdrant import create_qdrant

DEFAULT_SET = Path(__file__).resolve().parents[1] / "eval" / "seed_retrieval.json"
SWEEP = [round(0.15 + 0.05 * step, 2) for step in range(9)]  # 0.15 … 0.55


@dataclass(frozen=True)
class Result:
    question: str
    expected: tuple[str, int] | None
    ranked: list[RetrievedChunk]

    def rank(self, threshold: float) -> int | None:
        """1-based rank of the expected passage among results at or above `threshold`."""
        if self.expected is None:
            return None
        kept = [chunk for chunk in self.ranked if chunk.score >= threshold]
        for position, chunk in enumerate(kept, start=1):
            if (chunk.filename, chunk.chunk_index) == self.expected:
                return position
        return None

    def rejected(self, threshold: float) -> bool:
        return all(chunk.score < threshold for chunk in self.ranked)


def summarize(results: list[Result], threshold: float) -> dict[str, float]:
    answerable = [r for r in results if r.expected is not None]
    unanswerable = [r for r in results if r.expected is None]
    ranks = [r.rank(threshold) for r in answerable]
    return {
        "hit@1": sum(rank == 1 for rank in ranks) / len(answerable) if answerable else 0.0,
        "hit@k": sum(rank is not None for rank in ranks) / len(answerable) if answerable else 0.0,
        "mrr": sum(1 / rank for rank in ranks if rank) / len(answerable) if answerable else 0.0,
        "rejected": (
            sum(r.rejected(threshold) for r in unanswerable) / len(unanswerable)
            if unanswerable
            else 0.0
        ),
    }


async def main(dataset: dict[str, Any], name: str) -> int:
    settings = get_settings()
    workspace_id = uuid.UUID(dataset["workspace_id"])
    qdrant = create_qdrant(settings)
    retriever = KnowledgeRetriever(
        OpenAIEmbedder(settings),
        qdrant,
        top_k=settings.retrieval_top_k,
        # Collect every score; thresholds are applied below so one run covers the sweep.
        score_threshold=0.0,
    )
    results = []
    try:
        for case in dataset["cases"]:
            expected = case["expected"]
            ranked = await retriever.search(workspace_id, case["question"])
            results.append(
                Result(
                    question=case["question"],
                    expected=None
                    if expected is None
                    else (expected["filename"], expected["chunk_index"]),
                    ranked=ranked,
                )
            )
    finally:
        await qdrant.close()

    configured = settings.retrieval_score_threshold
    print(f"{len(results)} questions · top_k={settings.retrieval_top_k} · {name}\n")
    print(f"{'best':>5}  {'match':>5}  {'rank':>4}  question")
    for result in results:
        best = result.ranked[0].score if result.ranked else 0.0
        match = next(
            (
                chunk.score
                for chunk in result.ranked
                if (chunk.filename, chunk.chunk_index) == result.expected
            ),
            None,
        )
        rank = result.rank(0.0)
        print(
            f"{best:5.3f}  {'  —  ' if match is None else f'{match:5.3f}'}  "
            f"{'—' if rank is None else rank:>4}  "
            f"{'(unanswerable) ' if result.expected is None else ''}{result.question}"
        )

    print(f"\n{'threshold':>9}  {'hit@1':>6}  {'hit@k':>6}  {'MRR':>5}  {'rejected':>8}")
    for threshold in sorted({*SWEEP, configured}):
        row = summarize(results, threshold)
        marker = "  ← configured" if threshold == configured else ""
        print(
            f"{threshold:9.2f}  {row['hit@1']:6.0%}  {row['hit@k']:6.0%}  {row['mrr']:5.2f}  "
            f"{row['rejected']:8.0%}{marker}"
        )
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SET
    sys.exit(asyncio.run(main(json.loads(target.read_text(encoding="utf-8")), target.name)))
