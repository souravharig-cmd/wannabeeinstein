import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  FileText,
  FlaskConical,
  LoaderCircle,
  Mail,
  Play,
  Plus,
  Search,
  ShieldCheck,
  TriangleAlert,
  Workflow,
  XCircle,
} from 'lucide-react';
import './App.css';

const API_BASE = 'http://localhost:8000/api';
const STARTING_PROMPT =
  'Find three suitable internship opportunities for a computer science student, compare their eligibility criteria and deadlines, save the best matches to a spreadsheet, and prepare personalized application email drafts.';

type StepStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'AWAITING_APPROVAL';

interface TaskStep {
  id: string;
  step_order: number;
  title: string;
  description: string;
  tool_name: string;
  status: StepStatus;
  requires_approval: boolean;
  approval_granted: boolean;
  result: unknown;
  error_message: string | null;
  retry_count: number;
  max_retries: number;
  updated_at: string;
}

interface ToolLog {
  id: number;
  step_id: string | null;
  tool_name: string;
  input_json: string | null;
  output_json: string | null;
  status: string;
  error_message: string | null;
  timestamp: string;
}

interface AuditLog {
  id: number;
  action: string;
  details: string;
  timestamp: string;
}

interface TaskData {
  id: string;
  goal: string;
  status: string;
  created_at: string;
  verification_status: boolean | number | string | null;
  steps: TaskStep[];
  tool_logs: ToolLog[];
  audit_logs: AuditLog[];
}

interface MCPTool {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

interface Verification {
  overall_status: string;
  csv_verification?: {
    valid?: boolean;
    row_count?: number;
  };
  email_verification?: {
    valid?: boolean;
    draft_count?: number;
  };
}

interface ExampleTask {
  label: string;
  goal: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

async function readResponse<T>(response: Response): Promise<T> {
  const payload: unknown = await response.json();

  if (!response.ok) {
    const message =
      isRecord(payload) && typeof payload.detail === 'string'
        ? payload.detail
        : `The request failed (${response.status}).`;
    throw new Error(message);
  }

  return payload as T;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function formatJson(value: unknown): string {
  const result = JSON.stringify(value, null, 2);
  return result ?? String(value);
}

function readJson(value: string | null): unknown {
  if (!value) return null;

  try {
    return JSON.parse(value) as unknown;
  } catch {
    return value;
  }
}

function readText(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  return typeof value === 'string' || typeof value === 'number'
    ? String(value)
    : '—';
}

function deriveTaskStatus(task: TaskData | null): StepStatus {
  if (!task || task.steps.length === 0) return 'PENDING';

  const statuses = task.steps.map((step) => step.status);
  if (statuses.includes('RUNNING')) return 'RUNNING';
  if (statuses.includes('AWAITING_APPROVAL')) return 'AWAITING_APPROVAL';
  if (statuses.includes('FAILED')) return 'FAILED';
  if (
    task.verification_status === false ||
    task.verification_status === 0 ||
    task.verification_status === '0'
  ) {
    return 'FAILED';
  }
  if (statuses.every((status) => status === 'COMPLETED')) return 'COMPLETED';

  return 'PENDING';
}

function statusLabel(status: StepStatus): string {
  switch (status) {
    case 'PENDING':
      return 'Ready to run';
    case 'RUNNING':
      return 'In progress';
    case 'COMPLETED':
      return 'Completed';
    case 'FAILED':
      return 'Needs attention';
    case 'AWAITING_APPROVAL':
      return 'Approval required';
  }
}

function StepMark({ status }: { status: StepStatus }) {
  if (status === 'RUNNING') {
    return <LoaderCircle className="step-mark-icon is-spinning" aria-hidden="true" />;
  }
  if (status === 'COMPLETED') {
    return <Check aria-hidden="true" />;
  }
  if (status === 'FAILED') {
    return <XCircle aria-hidden="true" />;
  }
  if (status === 'AWAITING_APPROVAL') {
    return <ShieldCheck aria-hidden="true" />;
  }
  return <Circle aria-hidden="true" />;
}

function collectFilePaths(steps: TaskStep[]): string[] {
  const paths = new Set<string>();

  function visit(value: unknown): void {
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }

    if (!isRecord(value)) return;

    const filePath = value.file_path;
    if (typeof filePath === 'string') paths.add(filePath);

    Object.values(value).forEach(visit);
  }

  steps.forEach((step) => visit(step.result));
  return [...paths];
}

function getDownloadUrl(filePath: string): string | null {
  const parts = filePath.replace(/\\/g, '/').split('/').filter(Boolean);
  const folderIndex = parts.findIndex(
    (part) => part === 'exports' || part === 'drafts',
  );
  if (folderIndex === -1) return null;

  const folder = parts[folderIndex];
  const filename = parts.slice(folderIndex + 1).join('/');
  if (!filename) return null;

  return `${API_BASE}/download/${folder}/${filename
    .split('/')
    .map(encodeURIComponent)
    .join('/')}`;
}

function isDraftPath(filePath: string): boolean {
  const pathParts = filePath.replace(/\\/g, '/').split('/');
  return pathParts.includes('drafts');
}

function parseEmailDraft(content: string): { subject: string; body: string } {
  const normalizedContent = content.replace(/^\uFEFF/, '');
  const subjectMatch = normalizedContent.match(/^Subject:\s*(.*?)(?:\r?\n|$)/i);

  if (!subjectMatch) {
    return { subject: '', body: normalizedContent };
  }

  return {
    subject: subjectMatch[1].trim(),
    body: normalizedContent
      .slice(subjectMatch[0].length)
      .replace(/^\r?\n+/, ''),
  };
}

function getGmailComposeUrl(subject: string, body: string): string {
  const url = new URL('https://mail.google.com/mail/');
  url.searchParams.set('view', 'cm');
  url.searchParams.set('fs', '1');
  url.searchParams.set('su', subject);
  url.searchParams.set('body', body);
  return url.toString();
}

function App() {
  const [goal, setGoal] = useState(STARTING_PROMPT);
  const [simulateFailure, setSimulateFailure] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskData, setTaskData] = useState<TaskData | null>(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [approvingStepId, setApprovingStepId] = useState<string | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [mcpTools, setMcpTools] = useState<MCPTool[]>([]);
  const [mcpLoading, setMcpLoading] = useState(true);
  const [mcpError, setMcpError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [verificationLoading, setVerificationLoading] = useState(false);
  const [draftContents, setDraftContents] = useState<
    Record<string, { subject: string; body: string; error?: string }>
  >({});

  const overallStatus = deriveTaskStatus(taskData);
  const supportedToolNames = useMemo(
    () => new Set(mcpTools.map((tool) => tool.name)),
    [mcpTools],
  );
  const artifacts = useMemo(
    () => (taskData ? collectFilePaths(taskData.steps) : []),
    [taskData],
  );
  const draftPathsKey = artifacts.filter(isDraftPath).join('\n');
  const searchStep = taskData?.steps.find(
    (step) => step.tool_name === 'search_internships',
  );
  const searchResult = isRecord(searchStep?.result) ? searchStep.result : null;
  const researchResults = Array.isArray(searchResult?.results)
    ? searchResult.results.filter(isRecord)
    : [];
  const completedSteps =
    taskData?.steps.filter((step) => step.status === 'COMPLETED').length ?? 0;
  const canVerify =
    taskData !== null &&
    taskData.steps.length > 0 &&
    taskData.steps.every((step) => step.status === 'COMPLETED');

  const exampleTasks: ExampleTask[] = useMemo(() => {
    const requiredTools = [
      'search_internships',
      'compare_opportunities',
      'save_opportunities',
      'create_email_draft',
    ];
    if (!requiredTools.every((tool) => supportedToolNames.has(tool))) return [];

    return [
      {
        label: 'Find and compare internships',
        goal: STARTING_PROMPT,
      },
      {
        label: 'Focus on software roles',
        goal:
          'Find software engineering internships for a student with Python experience, compare their eligibility criteria and deadlines, and save the best matches.',
      },
      {
        label: 'Prepare application drafts',
        goal:
          'Find machine learning internship opportunities, compare the best matches, and prepare personalized application email drafts.',
      },
    ];
  }, [supportedToolNames]);

  async function fetchTaskDetails(id: string): Promise<TaskData | null> {
    try {
      const response = await fetch(`${API_BASE}/tasks/${id}`);
      const data = await readResponse<TaskData>(response);
      setTaskData(data);
      return data;
    } catch (error) {
      setActionError(
        `Could not refresh task status: ${
          error instanceof Error ? error.message : 'Unknown error.'
        }`,
      );
      return null;
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function loadTools(): Promise<void> {
      try {
        const response = await fetch(`${API_BASE}/mcp/tools`);
        const data = await readResponse<{
          status: string;
          tools: MCPTool[];
          message?: string;
        }>(response);

        if (cancelled) return;
        if (data.status !== 'success') {
          setMcpError(data.message ?? 'MCP tool discovery failed.');
          return;
        }

        setMcpTools(data.tools);
        setMcpError(null);
      } catch (error) {
        if (!cancelled) {
          setMcpError(
            error instanceof Error
              ? error.message
              : 'Could not connect to the MCP server.',
          );
        }
      } finally {
        if (!cancelled) setMcpLoading(false);
      }
    }

    void loadTools();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!taskId || (!executing && overallStatus !== 'RUNNING')) return;

    let requestInFlight = false;
    const interval = window.setInterval(() => {
      if (requestInFlight) return;
      requestInFlight = true;
      void fetchTaskDetails(taskId).finally(() => {
        requestInFlight = false;
      });
    }, 1000);

    return () => window.clearInterval(interval);
  }, [executing, overallStatus, taskId]);

  useEffect(() => {
    const draftPaths = draftPathsKey ? draftPathsKey.split('\n') : [];
    if (draftPaths.length === 0) return;

    let cancelled = false;

    async function loadDraftContents(): Promise<void> {
      const loadedDrafts = await Promise.all(
        draftPaths.map(async (path) => {
          const url = getDownloadUrl(path);
          if (!url) {
            return [
              path,
              {
                subject: '',
                body: '',
                error: 'A download URL is not available for this draft.',
              },
            ] as const;
          }

          try {
            const response = await fetch(url);
            if (!response.ok) {
              throw new Error(
                `Could not read the saved draft (${response.status}).`,
              );
            }
            const emailDraft = parseEmailDraft(await response.text());
            return [path, emailDraft] as const;
          } catch (error) {
            return [
              path,
              {
                subject: '',
                body: '',
                error:
                  error instanceof Error
                    ? error.message
                    : 'Could not read the saved draft.',
              },
            ] as const;
          }
        }),
      );

      if (cancelled) return;

      setDraftContents((previous) => ({
        ...previous,
        ...Object.fromEntries(loadedDrafts),
      }));
    }

    void loadDraftContents();
    return () => {
      cancelled = true;
    };
  }, [draftPathsKey]);

  async function handleCreateTask(): Promise<void> {
    setLoading(true);
    setVerification(null);
    setActionError(null);

    try {
      const response = await fetch(`${API_BASE}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal,
          simulate_failure: simulateFailure,
        }),
      });
      const data = await readResponse<{ task_id: string }>(response);
      setTaskId(data.task_id);
      await fetchTaskDetails(data.task_id);
      document.getElementById('current-run')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : 'Could not initialize task.',
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleExecuteAll(): Promise<void> {
    if (!taskId || !taskData?.steps || executing) return;

    setExecuting(true);
    setActionError(null);

    try {
      for (const step of taskData.steps) {
        if (step.status === 'COMPLETED') continue;

        const response = await fetch(
          `${API_BASE}/tasks/${taskId}/execute_step/${step.id}`,
          { method: 'POST' },
        );
        const result = await readResponse<{
          status: string;
          error?: string;
          message?: string;
        }>(response);
        await fetchTaskDetails(taskId);

        if (result.status === 'awaiting_approval') break;
        if (result.status === 'failed') {
          setActionError(
            result.error ?? result.message ?? 'The step failed to complete.',
          );
          break;
        }
        if (result.status !== 'success') {
          setActionError(
            result.message ?? `Unexpected step status: ${result.status}.`,
          );
          break;
        }
      }
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : 'Workflow execution failed.',
      );
      await fetchTaskDetails(taskId);
    } finally {
      setExecuting(false);
      await fetchTaskDetails(taskId);
    }
  }

  async function handleApproveStep(stepId: string): Promise<void> {
    if (!taskId || approvingStepId) return;

    setApprovingStepId(stepId);
    setActionError(null);
    try {
      const response = await fetch(
        `${API_BASE}/tasks/${taskId}/approve_step`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ step_id: stepId }),
        },
      );
      await readResponse<{ status: string }>(response);
      await fetchTaskDetails(taskId);
      await handleExecuteAll();
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : 'Could not approve this step.',
      );
    } finally {
      setApprovingStepId(null);
    }
  }

  async function handleVerifyOutputs(): Promise<void> {
    if (!taskId || verificationLoading || !canVerify) return;

    setVerificationLoading(true);
    setActionError(null);
    try {
      const response = await fetch(`${API_BASE}/tasks/${taskId}/verify`, {
        method: 'POST',
      });
      const data = await readResponse<Verification>(response);
      setVerification(data);
      await fetchTaskDetails(taskId);
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : 'Could not verify task outputs.',
      );
    } finally {
      setVerificationLoading(false);
    }
  }

  const activity = taskData
    ? [
        ...taskData.audit_logs.map((entry) => ({
          id: `audit-${entry.id}`,
          timestamp: entry.timestamp,
          type: 'audit' as const,
          title: entry.action.replaceAll('_', ' ').toLowerCase(),
          detail: entry.details,
        })),
        ...taskData.tool_logs.map((entry) => ({
          id: `tool-${entry.id}`,
          timestamp: entry.timestamp,
          type: 'tool' as const,
          title: entry.tool_name,
          detail: entry.error_message ?? `MCP tool ${entry.status.toLowerCase()}`,
        })),
      ]
        .sort(
          (a, b) =>
            new Date(b.timestamp).getTime() -
            new Date(a.timestamp).getTime(),
        )
        .slice(0, 12)
    : [];

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Workspace navigation">
        <a className="brand" href="#workspace" aria-label="TaskPilot workspace">
          <span className="brand-mark">
            <Bot size={20} strokeWidth={1.8} aria-hidden="true" />
          </span>
          <span className="brand-copy">
            <strong>TaskPilot</strong>
            <span>Agent workspace</span>
          </span>
        </a>

        <div className="sidebar-label">WORKSPACE</div>
        <nav className="side-navigation">
          <a
            className="nav-link is-active"
            href="#workspace"
            aria-label="New task"
          >
            <Workflow size={17} aria-hidden="true" />
            <span>New task</span>
          </a>
          <a
            className="nav-link"
            href="#connected-tools"
            aria-label="Connected tools"
          >
            <Activity size={17} aria-hidden="true" />
            <span>Connected tools</span>
            {!mcpLoading && !mcpError && (
              <span className="nav-count">{mcpTools.length}</span>
            )}
          </a>
          {taskId && (
            <a className="nav-link" href="#current-run" aria-label="Current run">
              <Clock3 size={17} aria-hidden="true" />
              <span>Current run</span>
            </a>
          )}
        </nav>

        <div className="sidebar-spacer" />
        <div className="sidebar-connection">
          <span
            className={`connection-dot ${
              mcpError ? 'is-offline' : mcpLoading ? 'is-loading' : ''
            }`}
            aria-hidden="true"
          />
          <span>
            {mcpLoading
              ? 'Connecting to MCP'
              : mcpError
                ? 'MCP unavailable'
                : 'MCP connected'}
          </span>
        </div>
        <p className="sidebar-caption">
          One agent. Real tools. Work you can verify.
        </p>
      </aside>

      <main className="main-area" id="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{taskId ? 'Current run' : 'New task'}</strong>
          </div>
          <a className="topbar-status" href="#connected-tools">
            <span
              className={`connection-dot ${
                mcpError ? 'is-offline' : mcpLoading ? 'is-loading' : ''
              }`}
              aria-hidden="true"
            />
            {mcpLoading
              ? 'Connecting'
              : mcpError
                ? 'MCP unavailable'
                : `${mcpTools.length} MCP tools connected`}
          </a>
        </header>

        <div className="page-content">
          <section className="intro-section">
            <div className="eyebrow">
              <span className="eyebrow-rule" />
              YOUR AI WORKSPACE
            </div>
            <h1>Give good work a clear starting point.</h1>
            <p>
              Set a goal. TaskPilot plans the steps, runs supported tools, and
              shows you what actually happened.
            </p>
          </section>

          <div className="workspace-grid">
            <div className="primary-column">
              <section className="goal-panel" aria-labelledby="goal-heading">
                <div className="panel-kicker">
                  <span className="panel-index">01</span>
                  <span>THE BRIEF</span>
                </div>
                <label className="goal-label" id="goal-heading" htmlFor="goal">
                  What would you like done?
                </label>
                <p className="goal-hint">
                  Describe an outcome. You can edit this example or start
                  somewhere else.
                </p>
                <textarea
                  id="goal"
                  className="goal-input"
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  placeholder="Describe the work you want the agent to do…"
                  rows={4}
                />

                {exampleTasks.length > 0 && (
                  <div className="examples">
                    <div className="examples-heading">A few places to start</div>
                    <div className="example-list">
                      {exampleTasks.map((example) => (
                        <button
                          className="example-button"
                          key={example.label}
                          onClick={() => setGoal(example.goal)}
                          type="button"
                        >
                          <span>{example.label}</span>
                          <ArrowRight size={14} aria-hidden="true" />
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="goal-footer">
                  <label className="simulation-option">
                    <input
                      type="checkbox"
                      checked={simulateFailure}
                      onChange={(event) =>
                        setSimulateFailure(event.target.checked)
                      }
                    />
                    <FlaskConical size={15} aria-hidden="true" />
                    <span>Simulate a recoverable spreadsheet error</span>
                  </label>
                  <div className="goal-actions">
                    <button
                      className="button button-primary"
                      onClick={() => void handleCreateTask()}
                      disabled={loading || executing || !goal.trim()}
                      type="button"
                    >
                      {loading ? (
                        <LoaderCircle
                          size={16}
                          className="is-spinning"
                          aria-hidden="true"
                        />
                      ) : (
                        <Plus size={16} aria-hidden="true" />
                      )}
                      Initialize task
                    </button>
                    {taskId && (
                      <button
                        className="button button-dark"
                        onClick={() => void handleExecuteAll()}
                        disabled={executing || loading}
                        type="button"
                      >
                        {executing ? (
                          <LoaderCircle
                            size={16}
                            className="is-spinning"
                            aria-hidden="true"
                          />
                        ) : (
                          <Play size={15} aria-hidden="true" />
                        )}
                        {executing ? 'Running workflow' : 'Run workflow'}
                      </button>
                    )}
                  </div>
                </div>
              </section>

              {actionError && (
                <div className="error-banner" role="alert">
                  <TriangleAlert size={17} aria-hidden="true" />
                  <span>{actionError}</span>
                  <button
                    type="button"
                    onClick={() => setActionError(null)}
                    aria-label="Dismiss error"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {taskData && (
                <section
                  className="run-section"
                  id="current-run"
                  aria-labelledby="run-heading"
                >
                  <div className="run-heading-row">
                    <div>
                      <div className="panel-kicker">
                        <span className="panel-index">02</span>
                        <span>EXECUTION</span>
                      </div>
                      <h2 id="run-heading">Current run</h2>
                    </div>
                    <span
                      className={`status-badge status-${overallStatus}`}
                      role="status"
                      aria-live="polite"
                    >
                      <span className="status-indicator" aria-hidden="true" />
                      {statusLabel(overallStatus)}
                    </span>
                  </div>

                  <div className="run-summary">
                    <div className="run-goal">
                      <span className="summary-label">GOAL</span>
                      <p>{taskData.goal}</p>
                    </div>
                    <div className="run-facts">
                      <div>
                        <span className="summary-label">TASK</span>
                        <span className="task-id">{taskData.id}</span>
                      </div>
                      <div>
                        <span className="summary-label">STARTED</span>
                        <time dateTime={taskData.created_at}>
                          {formatDate(taskData.created_at)}
                        </time>
                      </div>
                      <div>
                        <span className="summary-label">STEPS</span>
                        <span>
                          {completedSteps} / {taskData.steps.length} complete
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="run-grid">
                    <div className="workflow-panel">
                      <div className="section-title-row">
                        <div>
                          <h3>Execution plan</h3>
                          <p>Each step reflects the status returned by the API.</p>
                        </div>
                        <span className="step-count">
                          {taskData.steps.length} steps
                        </span>
                      </div>

                      {taskData.steps.length === 0 ? (
                        <p className="empty-state">
                          No steps were returned for this task.
                        </p>
                      ) : (
                        <ol className="workflow-list">
                          {taskData.steps.map((step) => {
                            const stepLogs = taskData.tool_logs.filter(
                              (log) => log.step_id === step.id,
                            );
                            const toolIsAvailable = supportedToolNames.has(
                              step.tool_name,
                            );

                            return (
                              <li
                                className={`workflow-item step-${step.status}`}
                                key={step.id}
                              >
                                <span className="workflow-marker">
                                  <StepMark status={step.status} />
                                </span>
                                <details className="step-details">
                                  <summary className="step-summary">
                                    <span className="step-order">
                                      {String(step.step_order).padStart(2, '0')}
                                    </span>
                                    <span className="step-main">
                                      <span className="step-title">
                                        {step.title}
                                      </span>
                                      <span className="step-meta">
                                        <code>{step.tool_name}</code>
                                        <span
                                          className={`step-status-label status-text-${step.status}`}
                                        >
                                          {statusLabel(step.status)}
                                        </span>
                                      </span>
                                    </span>
                                    <span className="step-updated">
                                      {formatDate(step.updated_at)}
                                    </span>
                                  </summary>
                                  <div className="step-body">
                                    <p className="step-description">
                                      {step.description}
                                    </p>
                                    {!toolIsAvailable && (
                                      <div className="step-error">
                                        <TriangleAlert
                                          size={15}
                                          aria-hidden="true"
                                        />
                                        This step names a tool that is not
                                        available from the connected MCP
                                        server. No operation was performed.
                                      </div>
                                    )}
                                    {step.error_message && (
                                      <div className="step-error">
                                        <TriangleAlert
                                          size={15}
                                          aria-hidden="true"
                                        />
                                        {step.error_message}
                                      </div>
                                    )}
                                    {step.retry_count > 0 && (
                                      <p className="retry-note">
                                        Retry attempts recorded by the backend:{' '}
                                        {step.retry_count} / {step.max_retries}
                                      </p>
                                    )}
                                    {step.requires_approval &&
                                      !step.approval_granted &&
                                      toolIsAvailable && (
                                        <button
                                          className="button button-primary approval-button"
                                          onClick={() =>
                                            void handleApproveStep(step.id)
                                          }
                                          disabled={
                                            executing ||
                                            approvingStepId !== null
                                          }
                                          type="button"
                                        >
                                          <ShieldCheck
                                            size={15}
                                            aria-hidden="true"
                                          />
                                          {approvingStepId === step.id
                                            ? 'Approving…'
                                            : 'Approve and continue'}
                                        </button>
                                      )}
                                    {stepLogs.map((log) => (
                                      <details
                                        className="tool-call"
                                        key={log.id}
                                      >
                                        <summary>
                                          <Activity
                                            size={14}
                                            aria-hidden="true"
                                          />
                                          MCP call · {log.tool_name} ·{' '}
                                          {log.status.toLowerCase()}
                                        </summary>
                                        <div className="tool-call-content">
                                          <div>
                                            <span className="summary-label">
                                              REQUESTED OPERATION
                                            </span>
                                            <pre>
                                              {formatJson(
                                                readJson(log.input_json),
                                              )}
                                            </pre>
                                          </div>
                                          {log.error_message && (
                                            <p className="step-error">
                                              {log.error_message}
                                            </p>
                                          )}
                                          {log.output_json && (
                                            <div>
                                              <span className="summary-label">
                                                ACTUAL MCP RESPONSE
                                              </span>
                                              <pre>
                                                {formatJson(
                                                  readJson(log.output_json),
                                                )}
                                              </pre>
                                            </div>
                                          )}
                                          <time dateTime={log.timestamp}>
                                            {formatDate(log.timestamp)}
                                          </time>
                                        </div>
                                      </details>
                                    ))}
                                    {step.result !== null && (
                                      <details className="result-details">
                                        <summary>View returned result</summary>
                                        <pre>{formatJson(step.result)}</pre>
                                      </details>
                                    )}
                                  </div>
                                </details>
                              </li>
                            );
                          })}
                        </ol>
                      )}
                    </div>

                    <aside className="run-aside">
                      <section className="aside-section">
                        <div className="section-title-row">
                          <div>
                            <div className="subsection-kicker">TASK OUTPUT</div>
                            <h3>Opportunity matches</h3>
                          </div>
                          <Search
                            size={17}
                            className="subtle-icon"
                            aria-hidden="true"
                          />
                        </div>
                        {researchResults.length === 0 ? (
                          <p className="empty-state">
                            Search results will appear here after the search
                            step returns.
                          </p>
                        ) : (
                          <div className="opportunity-list">
                            {researchResults.map((result, index) => (
                              <article
                                className="opportunity-item"
                                key={readText(result, 'id') || index}
                              >
                                <div className="opportunity-topline">
                                  <span>
                                    {readText(result, 'organization')}
                                  </span>
                                  <span className="match-score">
                                    {readText(result, 'match_score')}%
                                  </span>
                                </div>
                                <h4>{readText(result, 'title')}</h4>
                                <p className="opportunity-detail">
                                  Deadline: {readText(result, 'deadline')}
                                </p>
                                <p className="opportunity-detail">
                                  {readText(result, 'eligibility')}
                                </p>
                                {typeof result.source_url === 'string' && (
                                  <a
                                    className="source-link"
                                    href={result.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    Source provided by the result
                                    <ArrowRight
                                      size={13}
                                      aria-hidden="true"
                                    />
                                  </a>
                                )}
                              </article>
                            ))}
                          </div>
                        )}
                        <p className="data-caveat">
                          Results come from the connected tool&apos;s built-in
                          sample dataset, not a live web search.
                        </p>
                      </section>

                      <section className="aside-section outputs-section">
                        <div className="section-title-row">
                          <div>
                            <div className="subsection-kicker">DELIVERABLES</div>
                            <h3>Generated files</h3>
                          </div>
                          <FileText
                            size={17}
                            className="subtle-icon"
                            aria-hidden="true"
                          />
                        </div>
                        {artifacts.length === 0 ? (
                          <p className="empty-state">
                            Files will be listed here when an MCP tool returns
                            them.
                          </p>
                        ) : (
                          <ul className="artifact-list">
                            {artifacts.map((path) => {
                              const url = getDownloadUrl(path);
                              const emailDraft = isDraftPath(path)
                                ? draftContents[path]
                                : undefined;
                              const fileName =
                                path.replace(/\\/g, '/').split('/').pop() ??
                                path;
                              return (
                                <li className="artifact-row" key={path}>
                                  <span className="artifact-icon">
                                    <FileText
                                      size={16}
                                      aria-hidden="true"
                                    />
                                  </span>
                                  <span className="artifact-copy">
                                    <strong>{fileName}</strong>
                                    <span>
                                      {!isDraftPath(path)
                                        ? 'Spreadsheet export'
                                        : 'Email draft'}
                                    </span>
                                  </span>
                                  {isDraftPath(path) &&
                                    (emailDraft?.error ? (
                                      <span
                                        className="draft-compose-error"
                                        role="status"
                                        title={emailDraft.error}
                                      >
                                        Unavailable
                                      </span>
                                    ) : emailDraft ? (
                                      <a
                                        className="gmail-compose-link"
                                        href={getGmailComposeUrl(
                                          emailDraft.subject,
                                          emailDraft.body,
                                        )}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        aria-label={`Open ${fileName} as a prefilled Gmail draft`}
                                        title="Open a prefilled draft in Gmail"
                                      >
                                        <Mail
                                          size={14}
                                          aria-hidden="true"
                                        />
                                        Gmail
                                      </a>
                                    ) : (
                                      <span
                                        className="draft-compose-loading"
                                        role="status"
                                      >
                                        <LoaderCircle
                                          size={13}
                                          className="is-spinning"
                                          aria-hidden="true"
                                        />
                                        Loading
                                      </span>
                                    ))}
                                  {url && (
                                    <a
                                      className="download-link"
                                      href={url}
                                      target="_blank"
                                      rel="noreferrer"
                                      aria-label={`Open ${fileName}`}
                                    >
                                      <ArrowDownToLine
                                        size={16}
                                        aria-hidden="true"
                                      />
                                    </a>
                                  )}
                                </li>
                              );
                            })}
                          </ul>
                        )}
                        {artifacts.some(isDraftPath) && (
                          <p className="data-caveat">
                            Gmail opens with the saved draft&apos;s subject and
                            body. Add a recipient, review, and send manually;
                            nothing is sent automatically.
                          </p>
                        )}
                      </section>
                    </aside>
                  </div>
                </section>
              )}
            </div>

            <aside className="secondary-column">
              <section className="capabilities-panel" id="connected-tools">
                <div className="panel-kicker">
                  <span className="panel-index">TOOLS</span>
                  <span>LIVE MCP DISCOVERY</span>
                </div>
                <div className="capabilities-heading">
                  <div>
                    <h2>Connected tools</h2>
                    <p>
                      Names and descriptions reported by your MCP server.
                    </p>
                  </div>
                  <span
                    className={`connection-dot ${
                      mcpError ? 'is-offline' : mcpLoading ? 'is-loading' : ''
                    }`}
                    aria-hidden="true"
                  />
                </div>

                {mcpLoading ? (
                  <div className="tools-message">
                    <LoaderCircle
                      size={15}
                      className="is-spinning"
                      aria-hidden="true"
                    />
                    Discovering tools…
                  </div>
                ) : mcpError ? (
                  <div className="tools-error" role="status">
                    <TriangleAlert size={16} aria-hidden="true" />
                    <span>{mcpError}</span>
                  </div>
                ) : mcpTools.length === 0 ? (
                  <p className="empty-state">
                    The MCP server did not report any available tools.
                  </p>
                ) : (
                  <ul className="tool-inventory">
                    {mcpTools.map((tool) => {
                      const toolCalls =
                        taskData?.tool_logs.filter(
                          (log) => log.tool_name === tool.name,
                        ).length ?? 0;
                      return (
                        <li className="tool-inventory-item" key={tool.name}>
                          <div className="tool-inventory-topline">
                            <code>{tool.name}</code>
                            {toolCalls > 0 && (
                              <span className="tool-call-count">
                                {toolCalls} call{toolCalls === 1 ? '' : 's'}
                              </span>
                            )}
                          </div>
                          <p>{tool.description}</p>
                          <details className="schema-details">
                            <summary>Input fields</summary>
                            <pre>
                              {formatJson(
                                tool.input_schema.properties ??
                                  tool.input_schema,
                              )}
                            </pre>
                          </details>
                        </li>
                      );
                    })}
                  </ul>
                )}

                <div className="capabilities-note">
                  The planner currently builds internship research,
                  comparison, CSV export, and email-draft workflows. It does
                  not send emails or search the live web.
                </div>
              </section>

              {taskData && (
                <>
                  <section className="verification-panel">
                    <div className="panel-kicker">
                      <span className="panel-index">CHECK</span>
                      <span>OUTPUT REVIEW</span>
                    </div>
                    <div className="verification-heading">
                      <div>
                        <h2>Verify results</h2>
                        <p>
                          Validate the generated CSV and email draft files.
                        </p>
                      </div>
                      {verification?.overall_status === 'VERIFIED_SUCCESS' ? (
                        <CheckCircle2
                          size={20}
                          className="verification-success-icon"
                          aria-hidden="true"
                        />
                      ) : verification ? (
                        <XCircle
                          size={20}
                          className="verification-failed-icon"
                          aria-hidden="true"
                        />
                      ) : (
                        <ShieldCheck
                          size={20}
                          className="subtle-icon"
                          aria-hidden="true"
                        />
                      )}
                    </div>
                    <button
                      className="button button-outline verification-button"
                      onClick={() => void handleVerifyOutputs()}
                      disabled={
                        !canVerify || verificationLoading || executing
                      }
                      type="button"
                    >
                      {verificationLoading ? (
                        <LoaderCircle
                          size={15}
                          className="is-spinning"
                          aria-hidden="true"
                        />
                      ) : (
                        <ShieldCheck size={15} aria-hidden="true" />
                      )}
                      {verificationLoading
                        ? 'Checking files'
                        : 'Run verification'}
                    </button>
                    {!canVerify && (
                      <p className="verification-hint">
                        Verification becomes available after every planned step
                        completes.
                      </p>
                    )}
                    {verification && (
                      <div
                        className={`verification-result ${
                          verification.overall_status === 'VERIFIED_SUCCESS'
                            ? 'is-valid'
                            : 'is-invalid'
                        }`}
                        role="status"
                      >
                        <strong>{verification.overall_status.replaceAll('_', ' ')}</strong>
                        <span>
                          CSV: {verification.csv_verification?.valid ? 'valid' : 'not valid'}
                          {typeof verification.csv_verification?.row_count ===
                            'number' &&
                            ` · ${verification.csv_verification.row_count} rows`}
                        </span>
                        <span>
                          Email drafts:{' '}
                          {verification.email_verification?.draft_count ?? 0}
                          /3 checked
                        </span>
                      </div>
                    )}
                  </section>

                  <section className="activity-panel">
                    <div className="panel-kicker">
                      <span className="panel-index">LOG</span>
                      <span>PERSISTED ACTIVITY</span>
                    </div>
                    <div className="activity-heading">
                      <h2>Run history</h2>
                      <span>Current task only</span>
                    </div>
                    {activity.length === 0 ? (
                      <p className="empty-state">
                        Activity appears here as the backend records it.
                      </p>
                    ) : (
                      <ol className="activity-list">
                        {activity.map((event) => (
                          <li className="activity-item" key={event.id}>
                            <span
                              className={`activity-icon ${
                                event.type === 'tool' ? 'is-tool' : ''
                              }`}
                            >
                              {event.type === 'tool' ? (
                                <Activity size={13} aria-hidden="true" />
                              ) : (
                                <Clock3 size={13} aria-hidden="true" />
                              )}
                            </span>
                            <span className="activity-copy">
                              <strong>{event.title}</strong>
                              <span>{event.detail}</span>
                              <time dateTime={event.timestamp}>
                                {formatDate(event.timestamp)}
                              </time>
                            </span>
                          </li>
                        ))}
                      </ol>
                    )}
                    <p className="history-note">
                      Earlier tasks remain in persistent storage, but the
                      backend does not expose a task-history list.
                    </p>
                  </section>
                </>
              )}
            </aside>
          </div>

          <footer className="page-footer">
            <span>TaskPilot</span>
            <span>Execution states and outputs are shown from backend data.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default App;
