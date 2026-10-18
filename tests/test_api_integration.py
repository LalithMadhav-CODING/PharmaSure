"""Comprehensive integration tests for Telemedicon API, pipeline, and frontend delivery."""
import pytest
from fastapi.testclient import TestClient
from src.app import app
import re

client = TestClient(app)

def test_health_endpoint():
    """Verify GET /api/health exposes corpus and supported diseases."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert isinstance(data["corpus_size"], int)
    assert data["corpus_size"] > 0
    assert "supported_diseases" in data
    assert "Alzheimer's disease" in data["supported_diseases"]
    assert "Parkinson's disease" in data["supported_diseases"]
    assert "Multiple myeloma" in data["supported_diseases"]

def test_query_alzheimers():
    """Test successful POST /api/query for Alzheimer's disease."""
    response = client.post("/api/query", json={"query": "Alzheimer's disease"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["disease"]["name"] == "Alzheimer's disease"
    assert len(data["results"]) == 10
    assert len(data["known_indications"]) == 13
    assert len(data["passages"]) == 10
    assert data.get("from_cache") is True

    # Validate candidates structure
    ranks = [c["rank"] for c in data["results"]]
    assert ranks == list(range(1, 11))

    directions = set(c["direction"] for c in data["results"])
    assert "Positive" in directions
    assert "Negative" in directions
    assert "Mixed" in directions
    assert "Uncertain" in directions

    tiers = set(c["evidence"]["tier"] for c in data["results"])
    assert "Strong" in tiers
    assert "Moderate" in tiers
    assert "Preliminary" in tiers

    # Check evidence score bounds
    for c in data["results"]:
        assert 0.0 <= c["evidence"]["score"] <= 1.0
        assert c["evidence"]["support"] >= 1
        assert len(c["reason"]) > 10

    # Verify claim citation mapping & verbatim quote support
    passages_by_id = {str(p["id"]): p for p in data["passages"]}
    for c in data["results"]:
        for claim in c["claims"]:
            assert "text" in claim
            assert "verification_status" in claim
            assert claim["verification_status"] in ["verified", "needs_review"]
            for cid in claim.get("citations", []):
                assert str(cid) in passages_by_id
                passage = passages_by_id[str(cid)]
                # If verified, quote should be in passage
                if claim["verification_status"] == "verified":
                    assert claim["quote"].lower() in passage["text"].lower()

def test_all_demo_queries():
    """Verify all 5 demo queries return ok status with exact expected indications."""
    queries = [
        ("Parkinson's disease", 10, 27),
        ("Multiple myeloma", 10, 13),
        ("Type 2 diabetes", 10, 42),
        ("Asthma", 10, 28)
    ]
    for q, expected_cands, expected_known in queries:
        resp = client.post("/api/query", json={"query": q})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok", f"Query {q} failed: {data}"
        assert len(data["results"]) == expected_cands
        assert len(data["known_indications"]) == expected_known

def test_unsupported_disease():
    """Verify unsupported disease returns status 'unsupported_disease'."""
    response = client.post("/api/query", json={"query": "Ebola hemorrhagic fever"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unsupported_disease"
    assert "not in our supported disease set" in data["message"]
    assert len(data["results"]) == 0

def test_insufficient_evidence():
    """Verify insufficient evidence returns status 'insufficient_evidence'."""
    response = client.post("/api/query", json={"query": "Huntington's disease"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "insufficient_evidence"
    assert len(data["results"]) == 0
    assert len(data["known_indications"]) > 0

def test_empty_query_validation():
    """Verify 400 error on empty or missing query string."""
    resp1 = client.post("/api/query", json={"query": ""})
    assert resp1.status_code == 400
    resp2 = client.post("/api/query", json={})
    assert resp2.status_code == 400

def test_frontend_delivery():
    """Verify frontend HTML and assets are delivered at root /."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Telemedicon" in response.text
    assert "<div id=\"root\">" in response.text

def test_legacy_gradio_mounted():
    """Verify legacy Gradio UI is mounted at /gradio."""
    response = client.get("/gradio/")
    assert response.status_code == 200

if __name__ == "__main__":
    test_health_endpoint()
    print("✓ Health endpoint passed")
    test_query_alzheimers()
    print("✓ Alzheimer query and citation quote verification passed")
    test_all_demo_queries()
    print("✓ All 5 demo queries passed")
    test_unsupported_disease()
    print("✓ Unsupported disease passed")
    test_insufficient_evidence()
    print("✓ Insufficient evidence passed")
    test_empty_query_validation()
    print("✓ Empty query validation passed")
    test_frontend_delivery()
    print("✓ Frontend delivery passed")
    test_legacy_gradio_mounted()
    print("✓ Legacy Gradio mount passed")
    print("\nALL INTEGRATION TESTS PASSED!")
