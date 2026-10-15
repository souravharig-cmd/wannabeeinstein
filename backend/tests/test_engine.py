import pytest
from backend.database import init_db, get_db
from backend.engine import ExecutionEngine, STATUS_PENDING, STATUS_AWAITING_APPROVAL

def test_execution_engine():
    init_db()
    engine = ExecutionEngine()
    
    task_id = "test_task_1"
    engine.save_task(task_id, "Test Goal", simulate_failure=True)
    
    steps = [
        {"title": "Step 1", "description": "Search", "tool_name": "search_internships", "requires_approval": False},
        {"title": "Step 2", "description": "Send", "tool_name": "send_email", "requires_approval": True}
    ]
    engine.set_steps(task_id, steps)
    
    details = engine.get_task_details(task_id)
    assert details["goal"] == "Test Goal"
    assert len(details["steps"]) == 2
    assert details["steps"][0]["status"] == STATUS_PENDING
    assert details["steps"][1]["requires_approval"] == 1
    
    # Test approval
    engine.update_step_status("test_task_1_step_2", STATUS_AWAITING_APPROVAL)
    engine.grant_approval("test_task_1_step_2")
    
    details_after = engine.get_task_details(task_id)
    assert details_after["steps"][1]["approval_granted"] == 1
    assert details_after["steps"][1]["status"] == STATUS_PENDING
