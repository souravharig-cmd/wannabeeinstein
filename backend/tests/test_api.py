import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db, init_db

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_task_lifecycle_and_unsupported_email_sending():
    init_db()
    
    # 1. Create Task
    res = client.post("/api/tasks", json={
        "goal": "Find 3 suitable internship opportunities for a computer science student",
        "simulate_failure": False
    })
    assert res.status_code == 200
    data = res.json()
    task_id = data["task_id"]
    steps = data["plan_steps"]
    assert len(steps) == 4
    assert all(step["tool_name"] != "send_application_emails" for step in steps)
    
    # 2. Execute Step 1 (Search)
    step1_id = f"{task_id}_step_1"
    res1 = client.post(f"/api/tasks/{task_id}/execute_step/{step1_id}")
    assert res1.status_code == 200
    assert res1.json()["status"] == "success"

    # A stale or manually supplied email-sending step must never report a fake success.
    legacy_step_id = f"{task_id}_step_4"
    conn = get_db()
    conn.execute(
        """UPDATE task_steps
           SET tool_name = ?, requires_approval = 0
           WHERE id = ?""",
        ("send_application_emails", legacy_step_id),
    )
    conn.commit()
    conn.close()

    res_send = client.post(
        f"/api/tasks/{task_id}/execute_step/{legacy_step_id}"
    )
    assert res_send.status_code == 200
    assert res_send.json()["status"] == "failed"
    assert "Only application drafts can be created" in res_send.json()["error"]

    task = client.get(f"/api/tasks/{task_id}").json()
    assert task["steps"][3]["status"] == "FAILED"
    assert not any(
        log["tool_name"] == "send_application_emails" for log in task["tool_logs"]
    )


def test_simulated_mcp_failure_is_reported_and_can_be_retried():
    init_db()
    response = client.post(
        "/api/tasks",
        json={
            "goal": "Find internship opportunities and prepare application drafts",
            "simulate_failure": True,
        },
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    for step_order in (1, 2):
        step_id = f"{task_id}_step_{step_order}"
        step_response = client.post(
            f"/api/tasks/{task_id}/execute_step/{step_id}"
        )
        assert step_response.json()["status"] == "success"

    save_step_id = f"{task_id}_step_3"
    first_attempt = client.post(
        f"/api/tasks/{task_id}/execute_step/{save_step_id}"
    )
    assert first_attempt.json()["status"] == "failed"
    assert "Simulated Database/CSV write permission error" in first_attempt.json()["error"]

    task = client.get(f"/api/tasks/{task_id}").json()
    assert task["steps"][2]["status"] == "FAILED"
    assert task["steps"][2]["retry_count"] == 1

    retry = client.post(f"/api/tasks/{task_id}/execute_step/{save_step_id}")
    assert retry.json()["status"] == "success"
    task = client.get(f"/api/tasks/{task_id}").json()
    assert task["steps"][2]["status"] == "COMPLETED"
    assert task["steps"][2]["retry_count"] == 1
