import json
import sys
from pathlib import Path

from backend.store.retrieval import retrieve


def run() -> int:
    dataset = Path(__file__).with_name("dataset.jsonl")
    cases = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    results = []

    for case in cases:
        matches = retrieve(case["question"], k=3)
        retrieved_ids = [document["id"] for document, _score in matches]
        rank = retrieved_ids.index(case["expected_top_id"]) + 1 if case["expected_top_id"] in retrieved_ids else None
        results.append({
            "id": case["id"],
            "expected": case["expected_top_id"],
            "retrieved": retrieved_ids,
            "rank": rank,
            "passed": rank == 1,
        })

    passed = sum(result["passed"] for result in results)
    summary = {"total": len(results), "passed": passed, "failed": len(results) - passed}
    print(json.dumps({"summary": summary, "results": results}, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(run())
