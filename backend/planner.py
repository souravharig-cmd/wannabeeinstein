import os
import json
from typing import Dict, Any, List

class GoalPlanner:
    def __init__(self):
        pass

    def generate_plan(self, goal: str) -> List[Dict[str, Any]]:
        """
        Transforms a natural-language goal into a structured multi-step plan.
        Supports the internship research scenario and generic automation goals.
        """
        goal_lower = goal.lower()
        
        if "internship" in goal_lower or "opportunity" in goal_lower or "job" in goal_lower:
            return [
                {
                    "step_order": 1,
                    "title": "Search Suitable Internship Opportunities",
                    "description": "Discover 3 computer science internship positions based on relevance and requirements.",
                    "tool_name": "search_internships",
                    "requires_approval": False
                },
                {
                    "step_order": 2,
                    "title": "Compare Eligibility Criteria and Deadlines",
                    "description": "Evaluate qualifications, deadlines, match scores, and relevance across candidates.",
                    "tool_name": "compare_opportunities",
                    "requires_approval": False
                },
                {
                    "step_order": 3,
                    "title": "Save Best Matches to CSV Spreadsheet",
                    "description": "Persist curated internship results into a validated CSV file.",
                    "tool_name": "save_opportunities",
                    "requires_approval": False
                },
                {
                    "step_order": 4,
                    "title": "Prepare Personalized Email Application Drafts",
                    "description": "Draft tailored application cover emails for selected organizations.",
                    "tool_name": "create_email_draft",
                    "requires_approval": False
                }
            ]
            
        # Default fallback generic plan
        return [
            {
                "step_order": 1,
                "title": "Analyze Goal Requirements",
                "description": f"Interpret target parameters for: {goal}",
                "tool_name": "search_internships",
                "requires_approval": False
            },
            {
                "step_order": 2,
                "title": "Process and Structured Comparison",
                "description": "Evaluate options and criteria.",
                "tool_name": "compare_opportunities",
                "requires_approval": False
            },
            {
                "step_order": 3,
                "title": "Export Data Record",
                "description": "Save structured results to persistent storage.",
                "tool_name": "save_opportunities",
                "requires_approval": False
            }
        ]
