from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_capabilities_endpoint_documents_runtime_features():
    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pdf"]["single_upload"] is True
    assert payload["pdf"]["multi_page"] is True
    assert "cache" in payload
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time-Ms" in response.headers


def test_job_analysis_endpoint_extracts_keywords():
    response = client.post(
        "/api/v1/jobs/analyze",
        json={"job_description": "Python 后端实习生，熟悉 FastAPI、Redis、Docker、RESTful API，本科。"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Python" in payload["required_skills"]
    assert "FastAPI" in payload["required_skills"]
    assert payload["education_hint"] == "本科"


def test_validation_error_shape_is_structured():
    response = client.post("/api/v1/jobs/analyze", json={"job_description": "too short"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["details"]

