import os
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.database import init_db, get_db
from backend.engine import ExecutionEngine, STATUS_PENDING, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED, STATUS_AWAITING_APPROVAL
from backend.planner import GoalPlanner
from backend.mcp_client import call_mcp_tool_sync, discover_mcp_tools_sync
from backend.verifier import OutputVerifier

# Initialize FastAPI App
app = FastAPI(
    title="TaskPilot API",
    description="Autonomous AI Workflow Operator API",
    version="1.0.0"
)

# Enable CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ExecutionEngine()
planner = GoalPlanner()
verifier = OutputVerifier()

@app.on_event("startup")
def startup_event():
    init_db()

# Request Models
class TaskCreateRequest(BaseModel):
    goal: str
    simulate_failure: bool = False

class TaskApproveRequest(BaseModel):
    step_id: str

class TaskSimulationToggleRequest(BaseModel):
    task_id: str
    simulate_failure: bool

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "TaskPilot Autonomous AI Operator",
        "version": "1.0.0"
    }

@app.get("/api/mcp/tools")
def list_mcp_tools():
    try:
        tools = discover_mcp_tools_sync()
        return {"status": "success", "tools": tools}
    except Exception as e:
        return {"status": "error", "message": str(e), "tools": []}

@app.post("/api/tasks")
def create_task(req: TaskCreateRequest):
    if not req.goal or not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty")
        
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    engine.save_task(task_id, req.goal, req.simulate_failure)
    
    # Generate Plan Steps
    plan_steps = planner.generate_plan(req.goal)
    engine.set_steps(task_id, plan_steps)
    
    return {
        "status": "success",
        "task_id": task_id,
        "goal": req.goal,
        "plan_steps": plan_steps
    }

@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    task_data = engine.get_task_details(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_data

@app.post("/api/tasks/{task_id}/execute_step/{step_id}")
def execute_step(task_id: str, step_id: str):
    task_data = engine.get_task_details(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
        
    step = next((s for s in task_data["steps"] if s["id"] == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if step["tool_name"] == "send_application_emails":
        error_msg = (
            "Email delivery is not supported by the available MCP tools. "
            "Only application drafts can be created."
        )
        engine.update_step_status(step_id, STATUS_FAILED, error_message=error_msg)
        return {
            "status": "failed",
            "step_id": step_id,
            "error": error_msg,
            "retry_count": step["retry_count"],
        }
        
    # Check if step requires approval and if approval was granted
    if step["requires_approval"] and not step["approval_granted"]:
        engine.update_step_status(step_id, STATUS_AWAITING_APPROVAL)
        return {
            "status": "awaiting_approval",
            "message": f"Step '{step['title']}' requires explicit human approval before execution."
        }
        
    engine.update_step_status(step_id, STATUS_RUNNING)
    
    # Tool Execution Logic
    tool_name = step["tool_name"]
    simulate_failure = bool(task_data["simulate_failure"])
    retry_count = step["retry_count"]
    max_retries = step["max_retries"]
    
    try:
        tool_args = {}
        if tool_name == "search_internships":
            tool_args = {"query": task_data["goal"], "target_count": 3}
        elif tool_name == "compare_opportunities":
            # Extract collected opportunity IDs from previous search step if available
            prev_search = next((s for s in task_data["steps"] if s["tool_name"] == "search_internships" and s["result"]), None)
            opp_ids = ["intern_001", "intern_002", "intern_003"]
            if prev_search and isinstance(prev_search["result"], dict) and "results" in prev_search["result"]:
                opp_ids = [item["id"] for item in prev_search["result"]["results"]]
            tool_args = {"opportunity_ids": opp_ids}
        elif tool_name == "save_opportunities":
            prev_search = next((s for s in task_data["steps"] if s["tool_name"] == "search_internships" and s["result"]), None)
            opp_ids = ["intern_001", "intern_002", "intern_003"]
            if prev_search and isinstance(prev_search["result"], dict) and "results" in prev_search["result"]:
                opp_ids = [item["id"] for item in prev_search["result"]["results"]]
            tool_args = {"task_id": task_id, "opportunity_ids": opp_ids, "simulate_failure": simulate_failure}
        elif tool_name == "create_email_draft":
            prev_search = next((s for s in task_data["steps"] if s["tool_name"] == "search_internships" and s["result"]), None)
            opp_ids = ["intern_001", "intern_002", "intern_003"]
            if prev_search and isinstance(prev_search["result"], dict) and "results" in prev_search["result"]:
                opp_ids = [item["id"] for item in prev_search["result"]["results"]]
            
            draft_results = []
            for opp_id in opp_ids[:3]:
                draft_args = {"task_id": task_id, "opportunity_id": opp_id}
                res = call_mcp_tool_sync("create_email_draft", draft_args)
                conn = get_db()
                engine.log_tool(
                    conn,
                    task_id,
                    step_id,
                    "create_email_draft",
                    draft_args,
                    res,
                    STATUS_COMPLETED,
                )
                conn.commit()
                conn.close()
                draft_results.append(res)
            
            engine.update_step_status(step_id, STATUS_COMPLETED, result={"drafts": draft_results})
            return {"status": "success", "step_id": step_id, "result": {"drafts": draft_results}}
        # Execute tool call
        result = call_mcp_tool_sync(tool_name, tool_args)
        
        # Log tool call
        conn = get_db()
        engine.log_tool(conn, task_id, step_id, tool_name, tool_args, result, STATUS_COMPLETED)
        conn.commit()
        conn.close()
        
        engine.update_step_status(step_id, STATUS_COMPLETED, result=result)
        return {"status": "success", "step_id": step_id, "result": result}

    except Exception as e:
        error_msg = str(e)
        conn = get_db()
        engine.log_tool(conn, task_id, step_id, tool_name, tool_args if 'tool_args' in locals() else {}, None, STATUS_FAILED, error_msg)
        
        # Increment retry count in database
        cursor = conn.cursor()
        cursor.execute("UPDATE task_steps SET retry_count = retry_count + 1 WHERE id = ?", (step_id,))
        conn.commit()
        conn.close()
        
        engine.update_step_status(step_id, STATUS_FAILED, error_message=error_msg)
        return {"status": "failed", "step_id": step_id, "error": error_msg, "retry_count": retry_count + 1}

@app.post("/api/tasks/{task_id}/approve_step")
def approve_step(task_id: str, req: TaskApproveRequest):
    engine.grant_approval(req.step_id)
    return {"status": "success", "message": f"Approval granted for step {req.step_id}"}

@app.post("/api/tasks/{task_id}/toggle_simulation")
def toggle_simulation(task_id: str, req: TaskSimulationToggleRequest):
    engine.toggle_task_simulation(task_id, req.simulate_failure)
    return {"status": "success", "simulate_failure": req.simulate_failure}

@app.post("/api/tasks/{task_id}/verify")
def verify_task_outputs(task_id: str):
    csv_path = os.path.join("exports", f"internships_{task_id}.csv")
    csv_verification = verifier.verify_csv(csv_path)
    
    draft_paths = [
        os.path.join("drafts", f"email_draft_{task_id}_intern_001.txt"),
        os.path.join("drafts", f"email_draft_{task_id}_intern_002.txt"),
        os.path.join("drafts", f"email_draft_{task_id}_intern_003.txt")
    ]
    email_verification = verifier.verify_email_drafts(draft_paths)
    
    overall_valid = csv_verification["valid"] and email_verification["valid"]
    
    verification_summary = {
        "overall_status": "VERIFIED_SUCCESS" if overall_valid else "VERIFICATION_FAILED",
        "csv_verification": csv_verification,
        "email_verification": email_verification
    }
    
    # Store summary in task
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET verification_status = ?, status = ? WHERE id = ?", 
                   (overall_valid, STATUS_COMPLETED if overall_valid else STATUS_FAILED, task_id))
    conn.commit()
    conn.close()
    
    return verification_summary

@app.get("/api/download/{folder}/{filename}")
def download_file(folder: str, filename: str):
    if folder not in ["exports", "drafts"]:
        raise HTTPException(status_code=400, detail="Invalid folder")
        
    safe_path = os.path.join("data", folder, filename)
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(safe_path)
