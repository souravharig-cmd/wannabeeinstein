import os
import csv
import json
import sqlite3
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("TaskPilot MCP Server")

DATA_DIR = os.environ.get("TASKPILOT_DATA_DIR", "data")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
DRAFTS_DIR = os.path.join(DATA_DIR, "drafts")

os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(DRAFTS_DIR, exist_ok=True)

# Sample database of computer science internship opportunities
SAMPLE_INTERNSHIPS = [
    {
        "id": "intern_001",
        "title": "Software Engineering Intern - AI Systems",
        "organization": "Google",
        "eligibility": "Currently enrolled in a BS/MS in CS or related technical field, proficiency in Python or C++",
        "deadline": "2025-04-15",
        "location": "Mountain View, CA / Remote",
        "source_url": "https://careers.google.com/jobs/results/intern-ai-systems",
        "match_score": 95,
        "match_explanation": "Direct alignment with CS student profile and software development skills."
    },
    {
        "id": "intern_002",
        "title": "Backend Engineering Intern",
        "organization": "Stripe",
        "eligibility": "CS or Engineering major graduating in 2026, experience with REST APIs and databases",
        "deadline": "2025-04-30",
        "location": "San Francisco, CA / Remote",
        "source_url": "https://stripe.com/jobs/careers/backend-intern",
        "match_score": 92,
        "match_explanation": "Excellent fit for CS students seeking scalable systems development experience."
    },
    {
        "id": "intern_003",
        "title": "Machine Learning Research Intern",
        "organization": "Meta",
        "eligibility": "CS / Data Science major, familiar with PyTorch, linear algebra, and data analytics",
        "deadline": "2025-05-10",
        "location": "Menlo Park, CA",
        "source_url": "https://metacareers.com/jobs/ml-research-intern",
        "match_score": 89,
        "match_explanation": "Ideal for students pursuing AI/ML specialization within Computer Science."
    },
    {
        "id": "intern_004",
        "title": "Frontend Engineering Intern",
        "organization": "Vercel",
        "eligibility": "CS major with experience in React, TypeScript, and modern Web APIs",
        "deadline": "2025-05-01",
        "location": "Remote",
        "source_url": "https://vercel.com/careers/frontend-intern",
        "match_score": 88,
        "match_explanation": "Strong candidate for web application and UI specialization."
    }
]

# Track failure state for simulation
failure_simulated_tracker = {}

@mcp.tool()
def search_internships(query: str, target_count: int = 3) -> Dict[str, Any]:
    """Search for internship opportunities matching the criteria."""
    query_lower = query.lower()
    matches = [i for i in SAMPLE_INTERNSHIPS if any(kw in i["title"].lower() or kw in i["eligibility"].lower() for kw in query_lower.split())]
    if not matches:
        matches = SAMPLE_INTERNSHIPS[:target_count]
    else:
        matches = matches[:target_count]
        
    return {
        "query": query,
        "count": len(matches),
        "results": matches
    }

@mcp.tool()
def compare_opportunities(opportunity_ids: List[str]) -> Dict[str, Any]:
    """Compare selected internship opportunities by eligibility, deadlines, and relevance."""
    selected = [i for i in SAMPLE_INTERNSHIPS if i["id"] in opportunity_ids]
    if not selected:
        selected = SAMPLE_INTERNSHIPS[:3]
        
    comparisons = []
    for opp in selected:
        comparisons.append({
            "id": opp["id"],
            "title": opp["title"],
            "organization": opp["organization"],
            "eligibility": opp["eligibility"],
            "deadline": opp["deadline"],
            "match_score": opp["match_score"],
            "match_explanation": opp["match_explanation"]
        })
        
    return {
        "total_compared": len(comparisons),
        "opportunities": comparisons
    }

@mcp.tool()
def save_opportunities(task_id: str, opportunity_ids: List[str], simulate_failure: bool = False) -> Dict[str, Any]:
    """Save selected opportunities to a CSV file. Demonstrates failure simulation and idempotency."""
    global failure_simulated_tracker
    
    should_simulate_failure = not failure_simulated_tracker.get(task_id, False)
    db_path = os.environ.get("TASKPILOT_DB_PATH", "data/taskpilot.db")

    # Each MCP invocation starts a fresh stdio process, so use the persisted retry count.
    if simulate_failure and os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                """SELECT retry_count
                   FROM task_steps
                   WHERE task_id = ? AND tool_name = 'save_opportunities'
                   ORDER BY step_order DESC
                   LIMIT 1""",
                (task_id,),
            ).fetchone()
            if row is not None:
                should_simulate_failure = row[0] == 0
        finally:
            conn.close()

    if simulate_failure and should_simulate_failure:
        failure_simulated_tracker[task_id] = True
        raise RuntimeError("Simulated Database/CSV write permission error on initial attempt!")

    selected = [i for i in SAMPLE_INTERNSHIPS if i["id"] in opportunity_ids]
    if not selected:
        selected = SAMPLE_INTERNSHIPS[:3]

    file_path = os.path.join(EXPORTS_DIR, f"internships_{task_id}.csv")

    # Read existing IDs if file exists to enforce idempotency / avoid duplicate rows
    existing_ids = set()
    if os.path.exists(file_path):
        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get("id"):
                    existing_ids.add(r.get("id"))

    fieldnames = ["id", "title", "organization", "eligibility", "deadline", "source_url", "match_explanation"]
    
    write_header = not os.path.exists(file_path) or os.path.getsize(file_path) == 0
    saved_count = 0

    with open(file_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for item in selected:
            if item["id"] not in existing_ids:
                writer.writerow({
                    "id": item["id"],
                    "title": item["title"],
                    "organization": item["organization"],
                    "eligibility": item["eligibility"],
                    "deadline": item["deadline"],
                    "source_url": item["source_url"],
                    "match_explanation": item["match_explanation"]
                })
                existing_ids.add(item["id"])
                saved_count += 1

    return {
        "status": "success",
        "file_path": file_path,
        "rows_added": saved_count,
        "total_records": len(existing_ids)
    }

@mcp.tool()
def create_email_draft(task_id: str, opportunity_id: str, student_name: str = "Computer Science Student") -> Dict[str, Any]:
    """Generate personalized application email draft for a specific opportunity."""
    opp = next((i for i in SAMPLE_INTERNSHIPS if i["id"] == opportunity_id), SAMPLE_INTERNSHIPS[0])
    
    draft_filename = f"email_draft_{task_id}_{opp['id']}.txt"
    file_path = os.path.join(DRAFTS_DIR, draft_filename)
    
    content = f"""Subject: Application for {opp['title']} - {student_name}

Dear University Recruiting Team at {opp['organization']},

I am writing to express my strong interest in the {opp['title']} position. As a Computer Science student passionate about technology and practical software execution, I am eager to contribute to {opp['organization']}.

Key Qualifications & Match:
- Eligibility: {opp['eligibility']}
- Alignment: {opp['match_explanation']}

I have attached my resume for your review and look forward to the opportunity to discuss how my background fits your team's needs before the deadline on {opp['deadline']}.

Best regards,
{student_name}
Email: candidate@university.edu
GitHub: github.com/candidate
"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "opportunity_id": opp["id"],
        "organization": opp["organization"],
        "file_path": file_path,
        "preview": content[:200] + "..."
    }

@mcp.tool()
def read_saved_results(file_path: str) -> Dict[str, Any]:
    """Read saved CSV results from storage."""
    # Resolve full path safely
    if os.path.isabs(file_path):
        full_path = file_path
    else:
        full_path = os.path.join(DATA_DIR, file_path)
        if not os.path.exists(full_path):
            full_path = os.path.abspath(file_path)

    if not os.path.exists(full_path):
        return {"status": "error", "message": f"File not found: {full_path}"}
        
    records = []
    with open(full_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(dict(row))
            
    return {
        "status": "success",
        "file_path": full_path,
        "record_count": len(records),
        "records": records
    }

@mcp.tool()
def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get persistent task status and step execution progress."""
    db_path = os.environ.get("TASKPILOT_DB_PATH", "data/taskpilot.db")
    if not os.path.exists(db_path):
        return {"status": "error", "message": "Database not initialized"}
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        conn.close()
        return {"status": "error", "message": "Task not found"}
        
    cursor.execute("SELECT * FROM task_steps WHERE task_id = ? ORDER BY step_order ASC", (task_id,))
    steps = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    return {
        "task_id": task_id,
        "status": task["status"],
        "goal": task["goal"],
        "steps": steps
    }

if __name__ == "__main__":
    mcp.run()
