from backend.store.retrieval import build_grounded_answer, retrieve


def test_certificate_query_ranks_certificate_policy_first():
    results = retrieve("What does a certificate of insurance prove?", k=3)
    assert results
    assert results[0][0]["id"] == "3"


def test_grounded_answer_contains_only_retrieved_citations():
    answer, citation_ids = build_grounded_answer("When should renewal begin?", k=3)
    assert citation_ids
    assert all(f"[{citation_id}]" in answer for citation_id in citation_ids)


def test_unrelated_query_returns_clarification():
    answer, citation_ids = build_grounded_answer("quantum chromodynamics recipe", k=3)
    assert citation_ids == []
    assert answer.startswith("I don't know")
