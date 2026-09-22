import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.blueprint import ArchitectureBlueprint, DomainEntity, EntityAttribute, UserStoryRecord, AcceptanceScenarioRecord
from app.services.spec_service import save_specification

client = TestClient(app)

@pytest.fixture
def sample_spec():
    bp = ArchitectureBlueprint(
        serviceName="payment-service",
        packageName="com.corp.payment",
        basePort=8081,
        entities=[
            DomainEntity(
                name="Payment",
                tableName="payments",
                attributes=[
                    EntityAttribute(name="id", type="Long", isPrimaryKey=True),
                    EntityAttribute(name="amount", type="BigDecimal", nullable=False)
                ]
            )
        ],
        userStories=[
            UserStoryRecord(
                id="US-1",
                role="Customer",
                intent="Process payment",
                benefit="Complete purchase",
                scenarios=[
                    AcceptanceScenarioRecord(
                        scenarioId="AC-1.1",
                        given="A valid cart",
                        when="Customer confirms payment",
                        then="Payment is processed"
                    )
                ]
            )
        ]
    )
    summary = save_specification(bp)
    return summary.specId

def test_create_session_success(sample_spec):
    response = client.post("/api/v1/sessions", json={"specId": sample_spec})
    assert response.status_code == 202
    data = response.json()
    assert "sessionId" in data or "session_id" in data
    sess_id = data.get("sessionId") or data.get("session_id")
    assert sess_id is not None
    assert "/stream" in (data.get("streamUrl") or data.get("stream_url"))

def test_create_session_not_found():
    response = client.post("/api/v1/sessions", json={"specId": "00000000-0000-0000-0000-000000000000"})
    assert response.status_code == 404

def test_get_session_by_id(sample_spec):
    create_resp = client.post("/api/v1/sessions", json={"specId": sample_spec})
    data = create_resp.json()
    sess_id = data.get("sessionId") or data.get("session_id")

    get_resp = client.get(f"/api/v1/sessions/{sess_id}")
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["id"] == sess_id
    assert "status" in detail

def test_broadcast_session_event_string_id():
    from app.api.routes_session import broadcast_session_event, SESSION_EVENT_HISTORY
    test_sid = "test-session-sse-id-type"
    broadcast_session_event(test_sid, "phase_transition", {"phase": "SCAFFOLDING"})
    events = SESSION_EVENT_HISTORY.get(test_sid, [])
    assert len(events) >= 1
    last_event = events[-1]
    assert isinstance(last_event["id"], str)
    assert last_event["id"] == "1"
    assert last_event["event"] == "phase_transition"


