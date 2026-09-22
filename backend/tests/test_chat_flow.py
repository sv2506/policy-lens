import uuid

from fastapi.testclient import TestClient

from backend.app.main import app


def test_websocket_chat_streams_and_persists_grounded_answer():
    user_id = f"test-{uuid.uuid4()}"

    with TestClient(app) as client:
        created = client.post("/api/chat/session", json={"user_id": user_id})
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        assert created.json()["persisted"] is False

        with client.websocket_connect(f"/api/chat/ws/{session_id}?user_id={user_id}") as websocket:
            history = websocket.receive_json()
            assert history == {"type": "history", "history": []}

            websocket.send_json({
                "type": "user_message",
                "content": "What does a certificate of insurance prove?",
            })

            event_types = []
            final_text = ""
            while "complete" not in event_types:
                event = websocket.receive_json()
                event_types.append(event["type"])
                if event["type"] == "final":
                    final_text = event["text"]

        assert event_types[0] == "ack"
        assert "token" in event_types
        assert "[3]" in final_text

        persisted = client.get(f"/api/chat/session/{session_id}?user_id={user_id}")
        assert persisted.status_code == 200
        assert len(persisted.json()["chat_history"]) == 2

        client.delete(f"/api/chat/session/{session_id}?user_id={user_id}")
