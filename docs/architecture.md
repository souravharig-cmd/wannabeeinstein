# TaskPilot Architecture & System Design

## Overview
TaskPilot is an Autonomous AI Workflow Operator designed to convert natural-language goals into multi-step execution plans, invoke modular tools via Model Context Protocol (MCP), recover gracefully from tool/storage failures, and verify output integrity.

```
+-------------------------------------------------------+
|                 User Interface (React)                |
+---------------------------+---------------------------+
                            | HTTP / REST API
                            v
+-------------------------------------------------------+
|              FastAPI Backend Application              |
+---------------------------+---------------------------+
                            |
           +----------------+----------------+
           |                                 |
           v                                 v
+-----------------------+        +-----------------------+
| Execution Engine &    |        |  Goal Planner Engine  |
| State Machine         |        |  (Step Decomposition) |
+-----------+-----------+        +-----------------------+
            |
            +--------------------------------+
            |                                |
            v                                v
+-----------------------+        +-----------------------+
|  Output Verifier      |        |   MCP Client          |
|  (CSV & Email Auditing)|       |   (Stdio Protocol)    |
+-----------+-----------+        +-----------+-----------+
            |                                | MCP JSON-RPC
            |                                v
            |                    +-----------------------+
            |                    |   MCP FastMCP Server  |
            |                    |   (Exposed Tools)     |
            |                    +-----------+-----------+
            v                                |
+--------------------------------------------+-----------+
|               Persistent SQLite Storage                 |
|       (Tasks, Steps, Tool Logs, Audit Logs)            |
+--------------------------------------------------------+
```

## Component Breakdown

1. **User Interface (`frontend/`)**: React + Vite application displaying backend-reported plan steps, discovered MCP tools, tool activity, research results, output download links, failure simulation, verification results, and audit logs.
2. **FastAPI Backend (`backend/main.py`)**: REST API handling the task lifecycle, execution step triggers, approval state, simulation toggles, and file-serving routes. The current planner does not schedule an email-sending step because the available MCP tools do not provide email delivery.
3. **Execution Engine (`backend/engine.py`)**: Manages step state transitions (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `AWAITING_APPROVAL`), bounded retry counts, and audit logging.
4. **MCP Client & Server (`backend/mcp_client.py` & `backend/mcp_server.py`)**: Genuine MCP connection over stdio protocol. Exposes tools (`search_internships`, `compare_opportunities`, `save_opportunities`, `create_email_draft`, `read_saved_results`, `get_task_status`).
5. **Output Verifier (`backend/verifier.py`)**: Programmatic validation for CSV existence, columns, and unique record IDs, as well as email draft file existence and formatting.
6. **SQLite Storage (`backend/database.py`)**: Persistent DB for tasks, execution steps, tool call logs, and audit trails.
