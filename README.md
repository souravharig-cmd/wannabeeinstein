# TaskPilot — Autonomous AI Workflow Operator

**Tagline:** From natural-language goals to verified results.

TaskPilot is a hackathon-ready Autonomous AI Workflow Operator that transforms complex user goals into multi-step execution plans, interacts with tools via the official **Model Context Protocol (MCP)**, recovers gracefully from simulated failures without duplicating work, and programmatically verifies final outputs.

---

## Key Features

1. **Natural-Language Goal Decomposition**: Breaks down broad goals (e.g., internship research and application preparation) into structured, ordered plans.
2. **Genuine MCP Integration**: Implements client-server tool discovery and invocation over `stdio` transport using `mcp`.
3. **Persistent State & Failure Recovery**: Tracks step status (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `AWAITING_APPROVAL`) in SQLite.
4. **Simulated Tool Failure & Idempotent Recovery**: Demonstrates spreadsheet write failure handling and seamless retry without row duplication.
5. **Programmatic Output Verification**: Verifies CSV files (schema, row count, uniqueness) and email drafts independently from LLM text output.
6. **Explicit Action Boundaries**: Application emails are prepared as drafts only. The available MCP tools do not send email; the API retains approval-state support for plans that require it.
7. **Clean Professional Dashboard**: Minimalist visual design with visual hierarchy, avoiding generic AI gradients or clutter.

---

## Quickstart & Setup Instructions

### Prerequisites
- Python 3.12+
- Node.js 20+ / npm 10+

### Environment Setup

1. **Clone the repository and install backend dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Install frontend dependencies:**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

3. **Configure Environment Variables (Optional):**
   Copy `.env.example` to `.env` if custom API keys or paths are needed.

---

## Running the Application

### Option A: Run Backend & Frontend Separately

1. **Start FastAPI Backend (Port 8000):**
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```

2. **Start React Vite Frontend (Port 5173):**
   ```bash
   cd frontend
   npm run dev
   ```

Open your browser at `http://localhost:5173`.

---

## Running Tests

Execute the backend test suite:
```bash
python3 -m pytest backend/tests/
```

Verify frontend compilation:
```bash
cd frontend && npm run build
```

---

## Main Demonstration Workflow

1. Open the TaskPilot dashboard at `http://localhost:5173`.
2. Select **"Find and compare internships"** or enter:
   > *"Find three suitable internship opportunities for a computer science student, compare their eligibility criteria and deadlines, save the best matches to a spreadsheet, and prepare personalized application email drafts."*
3. Enable **"Simulate Tool Failure"** toggle to test fault recovery.
4. Click **"Initialize Task"** and then **"Run Workflow"**.
5. Observe:
   - Ordered execution plan generation.
   - MCP tool discovery and execution.
   - Initial simulated failure on CSV write, followed by retry and successful row persistence without duplicate IDs.
   - Four supported workflow steps: search, compare, save a CSV, and prepare email drafts.
   - The failure state and recorded retry on the spreadsheet step, followed by a successful retry without duplicate rows.
6. Click **"Run verification"** to inspect programmatic CSV and email draft validation.
7. Download the generated CSV, open each saved email draft prefilled in Gmail, or inspect its original text file. Gmail requires you to add a recipient and manually review and send the message.
8. Email drafts are not sent: the available MCP tools do not provide email delivery.

---

## Judging Demo Script (3 Minutes) & Expected Questions

### 3-Minute Script
- **0:00 - 0:30**: Introduction & Identity — Show TaskPilot dashboard, highlight natural-language goal input and MCP connection status.
- **0:30 - 1:15**: Goal Initialization & MCP Discovery — Click "Initialize task". Show the four supported steps and discovered MCP tool activity.
- **1:15 - 2:00**: Failure Simulation & Idempotency — Show how TaskPilot handles a simulated spreadsheet write error, preserves state, retries, and avoids duplicate CSV rows.
- **2:00 - 2:30**: Results — Review the actual research results, MCP request/response logs, and generated output files.
- **2:30 - 3:00**: Verification & Outputs — Run verification and show the validated CSV and draft files available for download.

### Top Judge Questions & Technical Answers
1. **Q: Is this real MCP or a mock?**  
   *A: It is a genuine MCP integration using the official MCP Python SDK (`mcp`). The client launches `backend/mcp_server.py` via `stdio` transport, discovers tool schemas dynamically, and executes tools over JSON-RPC.*
2. **Q: How does TaskPilot handle duplicate data on retries?**  
   *A: `save_opportunities` reads existing primary key IDs from the target CSV file before appending rows, guaranteeing idempotency during retries.*
3. **Q: How do you verify outputs aren't hallucinated?**  
   *A: The Output Verifier (`backend/verifier.py`) reads files directly from disk, verifies headers, checks row counts, and tests structural rules independently of the model.*
