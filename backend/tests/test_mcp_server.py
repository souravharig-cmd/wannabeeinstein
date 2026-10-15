import pytest
import os
import uuid
from backend.mcp_server import search_internships, compare_opportunities, save_opportunities, create_email_draft, read_saved_results

def test_mcp_tools():
    task_id = f"test_task_mcp_{uuid.uuid4().hex[:6]}"
    
    # Test search
    search_res = search_internships("software python")
    assert search_res["count"] > 0
    
    # Test compare
    opp_ids = [r["id"] for r in search_res["results"]]
    comp_res = compare_opportunities(opp_ids)
    assert comp_res["total_compared"] == len(opp_ids)
    
    # Test save without failure
    save_res = save_opportunities(task_id, opp_ids, simulate_failure=False)
    assert save_res["status"] == "success"
    assert save_res["rows_added"] == len(opp_ids)
    
    # Test read
    read_res = read_saved_results(save_res["file_path"])
    assert read_res["status"] == "success"
    assert read_res["record_count"] == len(opp_ids)
    
    # Test draft creation
    draft_res = create_email_draft(task_id, opp_ids[0])
    assert draft_res["status"] == "success"
    assert draft_res["organization"] is not None
