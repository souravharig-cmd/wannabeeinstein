import pytest
from backend.mcp_client import call_mcp_tool_sync, discover_mcp_tools_sync
from backend.planner import GoalPlanner

def test_planner():
    planner = GoalPlanner()
    plan = planner.generate_plan("Find 3 suitable internship opportunities for a computer science student")
    assert [step["tool_name"] for step in plan] == [
        "search_internships",
        "compare_opportunities",
        "save_opportunities",
        "create_email_draft",
    ]
    assert all(not step["requires_approval"] for step in plan)

def test_mcp_client_stdio():
    tools = discover_mcp_tools_sync()
    tool_names = [t["name"] for t in tools]
    assert "search_internships" in tool_names
    assert "save_opportunities" in tool_names
    
    res = call_mcp_tool_sync("search_internships", {"query": "computer science", "target_count": 2})
    assert isinstance(res, dict)
    assert res["count"] > 0
