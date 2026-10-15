import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.database import get_db

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_AWAITING_APPROVAL = "AWAITING_APPROVAL"

class ExecutionEngine:
    def __init__(self):
        pass

    def log_audit(self, conn, task_id: str, action: str, details: str):
        now = datetime.now(timezone.utc).isoformat()
        conn.cursor().execute(
            "INSERT INTO audit_logs (task_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (task_id, action, details, now)
        )

    def log_tool(self, conn, task_id: str, step_id: str, tool_name: str, input_data: Dict, output_data: Any, status: str, error_msg: Optional[str] = None):
        now = datetime.now(timezone.utc).isoformat()
        conn.cursor().execute(
            "INSERT INTO tool_logs (task_id, step_id, tool_name, input_json, output_json, status, error_message, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, step_id, tool_name, json.dumps(input_data), json.dumps(output_data) if output_data is not None else None, status, error_msg, now)
        )

    def save_task(self, task_id: str, goal: str, simulate_failure: bool = False):
        conn = get_db()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT OR REPLACE INTO tasks (id, goal, status, simulate_failure, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, goal, STATUS_PENDING, 1 if simulate_failure else 0, now, now)
        )
        self.log_audit(conn, task_id, "TASK_CREATED", f"Task created with goal: {goal} (Simulate failure: {simulate_failure})")
        conn.commit()
        conn.close()

    def set_steps(self, task_id: str, steps: List[Dict[str, Any]]):
        conn = get_db()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        for idx, step in enumerate(steps, 1):
            step_id = f"{task_id}_step_{idx}"
            cursor.execute(
                """INSERT OR REPLACE INTO task_steps 
                   (id, task_id, step_order, title, description, tool_name, status, requires_approval, approval_granted, result_json, error_message, retry_count, max_retries, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    step_id, task_id, idx, step.get("title"), step.get("description"), step.get("tool_name"),
                    STATUS_PENDING, 1 if step.get("requires_approval") else 0, 0, None, None, 0, 3, now
                )
            )
        self.log_audit(conn, task_id, "PLAN_GENERATED", f"Generated {len(steps)} plan steps.")
        conn.commit()
        conn.close()

    def update_step_status(self, step_id: str, status: str, result: Optional[Dict] = None, error_message: Optional[str] = None):
        conn = get_db()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        result_json = json.dumps(result) if result is not None else None
        
        cursor.execute(
            "UPDATE task_steps SET status = ?, result_json = COALESCE(?, result_json), error_message = ?, updated_at = ? WHERE id = ?",
            (status, result_json, error_message, now, step_id)
        )
        
        cursor.execute("SELECT task_id FROM task_steps WHERE id = ?", (step_id,))
        row = cursor.fetchone()
        if row:
            self.log_audit(conn, row["task_id"], "STEP_STATUS_CHANGED", f"Step {step_id} status changed to {status}. Error: {error_message}")
            
        conn.commit()
        conn.close()

    def grant_approval(self, step_id: str) -> bool:
        conn = get_db()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "UPDATE task_steps SET approval_granted = 1, status = ? WHERE id = ?",
            (STATUS_PENDING, step_id)
        )
        cursor.execute("SELECT task_id FROM task_steps WHERE id = ?", (step_id,))
        row = cursor.fetchone()
        if row:
            self.log_audit(conn, row["task_id"], "APPROVAL_GRANTED", f"Human approval granted for step {step_id}.")
        conn.commit()
        conn.close()
        return True

    def toggle_task_simulation(self, task_id: str, simulate_failure: bool):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET simulate_failure = ? WHERE id = ?", (1 if simulate_failure else 0, task_id))
        conn.commit()
        conn.close()

    def get_task_details(self, task_id: str) -> Dict[str, Any]:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            conn.close()
            return {}
            
        task_data = dict(task_row)
        
        cursor.execute("SELECT * FROM task_steps WHERE task_id = ? ORDER BY step_order ASC", (task_id,))
        steps = [dict(r) for r in cursor.fetchall()]
        for s in steps:
            if s["result_json"]:
                try:
                    s["result"] = json.loads(s["result_json"])
                except Exception:
                    s["result"] = s["result_json"]
            else:
                s["result"] = None
                
        cursor.execute("SELECT * FROM tool_logs WHERE task_id = ? ORDER BY id ASC", (task_id,))
        tool_logs = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM audit_logs WHERE task_id = ? ORDER BY id ASC", (task_id,))
        audit_logs = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM output_artifacts WHERE task_id = ?", (task_id,))
        artifacts = [dict(r) for r in cursor.fetchall()]

        conn.close()
        
        task_data["steps"] = steps
        task_data["tool_logs"] = tool_logs
        task_data["audit_logs"] = audit_logs
        task_data["artifacts"] = artifacts
        return task_data
