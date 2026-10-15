# TaskPilot Research Notes & Theoretical Foundations

## 1. Agentic AI vs. Traditional Chatbots
Traditional chatbots generate conversational responses without agency or environment interaction. Agentic AI, by contrast, operates with goal orientation, multi-step planning, environmental sensing (tool execution), persistent state retention, and feedback loops. TaskPilot embodies agentic principles by converting open-ended natural-language goals into structured execution plans and invoking external tools via standardized protocols.

## 2. Fixed Automation Workflows vs. Autonomous AI Agents
Fixed automation (e.g., standard scripts or static DAGs) follows rigid, pre-defined branching paths. If an unexpected failure occurs, fixed scripts break or fail silently. Autonomous agents dynamically evaluate goals, discover tools, inspect environmental feedback, and execute bounded retry strategies with state preservation.

## 3. Model Context Protocol (MCP)
MCP is an open standard developed by Anthropic that standardizes how AI models discover, inspect, and invoke capabilities provided by external servers. TaskPilot implements genuine MCP stdio transport client-server integration, allowing dynamic discovery of tool schemas (`search_internships`, `save_opportunities`, etc.) and structured JSON-RPC execution.

## 4. Persistent State, Failure Recovery, and Idempotency
Real-world tool invocation (e.g., API calls, disk writes) can fail due to temporary network issues, permissions, or system failures. TaskPilot maintains step-level state persistence in SQLite (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `AWAITING_APPROVAL`). When an operation fails, previous steps remain intact. Upon retry, TaskPilot enforces idempotency (e.g., checking existing record IDs in CSV before appending) to prevent duplicated records.

## 5. Verification vs. LLM Self-Reported Success
A core design directive in TaskPilot is that a task is never marked complete simply because an LLM claims success. TaskPilot features a dedicated programmatic Output Verifier (`backend/verifier.py`) that reads generated CSV files back from disk, verifies required columns, checks for duplicate primary keys, and confirms email draft contents.

## 6. Human-in-the-Loop (HITL) Safety & Guardrails
Low-risk operations (research, data comparisons, draft generation) execute automatically. High-risk actions (such as sending application emails or submitting data externally) trigger an explicit `AWAITING_APPROVAL` state, halting workflow execution until a human explicitly grants approval through the interface or API.
