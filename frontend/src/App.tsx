import { useEffect, useState, type ReactNode } from "react";
import axios from "axios";
import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8000/api";

type Page =
  | "dashboard"
  | "requirements"
  | "journeys"
  | "executions"
  | "coverage"
  | "bugs"
  | "healing";

type Requirement = {
  requirement_id: string;
  title: string;
  description: string;
  type: string;
  priority: string;
  acceptance_criteria?: string[];
};

type Journey = {
  title: string;
  description: string;
  type: string;
  priority: string;
  preconditions?: string[];
  actions?: {
    action: string;
    target: string;
    value: string;
  }[];
  expected_result: string;
};

type ExecutionStep = {
  action: string;
  target: string;
  value: string;
  status: string;
  locator_strategy?: string;
  healed?: boolean;
  error?: string;
};

type ExecutionJourney = {
  journey_index: number;
  title: string;
  status: string;
  total_steps: number;
  passed_steps: number;
  failed_steps: number;
  healed_steps: number;
  steps?: ExecutionStep[];
};

type CoverageItem = {
  requirement_id: string;
  title: string;
  priority: string;
  coverage_level: string;
  matching_journeys: string[];
  passed_journeys: string[];
  failed_journeys: string[];
  missing_coverage: string[];
  recommendation: string;
};

type Bug = {
  bug_id: string;
  title: string;
  severity: string;
  priority: string;
  category: string;
  status: string;
  summary: string;
  actual_result: string;
  expected_result: string;
  root_cause: string;
  suggested_fix: string;
};

type DashboardData = {
  execution?: {
    total_journeys?: number;
    passed_journeys?: number;
    failed_journeys?: number;
    total_steps?: number;
    passed_steps?: number;
    failed_steps?: number;
    healed_steps?: number;
  };

  coverage?: {
    requirements?: {
      total?: number;
      fully_covered?: number;
      partially_covered?: number;
      not_covered?: number;
      coverage_percentage?: number;
    };
  };

  bugs?: {
    total_bugs?: number;
    bugs?: Bug[];
  };
};

type ExecutionStatus = {
  status: string;
  message: string;
  updated_at?: string | null;
};

type TargetResponse = {
  status: string;
  target_url: string | null;
  generation_status?: string;
  message?: string;
};

function App() {
  const [page, setPage] =
    useState<Page>("dashboard");

  const [dashboard, setDashboard] =
    useState<DashboardData | null>(null);

  const [requirements, setRequirements] =
    useState<Requirement[]>([]);

  const [journeys, setJourneys] =
    useState<Journey[]>([]);

  const [executions, setExecutions] =
    useState<ExecutionJourney[]>([]);

  const [coverage, setCoverage] =
    useState<CoverageItem[]>([]);

  const [bugs, setBugs] =
    useState<Bug[]>([]);

  const [executionStatus, setExecutionStatus] =
    useState<ExecutionStatus>({
      status: "idle",
      message: "",
    });

  const [targetUrl, setTargetUrl] =
    useState(
      "https://www.saucedemo.com/"
    );

  const [targetSaved, setTargetSaved] =
    useState(false);

  const [savingTarget, setSavingTarget] =
    useState(false);

  const [generationMessage, setGenerationMessage] =
    useState("");

  const [loading, setLoading] =
    useState(true);

  const [running, setRunning] =
    useState(false);

  const [error, setError] =
    useState("");

  useEffect(() => {
    loadData();
    loadTarget();
  }, []);

  useEffect(() => {
    if (!running) {
      return;
    }

    const interval = setInterval(
      async () => {
        try {
          const response =
            await axios.get<ExecutionStatus>(
              `${API_BASE_URL}/execution/status`
            );

          setExecutionStatus(
            response.data
          );

          if (
            response.data.status !==
            "running"
          ) {
            setRunning(false);

            await loadData();
          }
        } catch (err) {
          console.error(err);
        }
      },
      2000
    );

    return () =>
      clearInterval(interval);
  }, [running]);

  async function loadData() {
    try {
      setLoading(true);
      setError("");

      const [
        dashboardResponse,
        requirementsResponse,
        journeysResponse,
        executionResponse,
        coverageResponse,
      ] = await Promise.all([
        axios.get(
          `${API_BASE_URL}/artifacts/summary/dashboard`
        ),

        axios.get(
          `${API_BASE_URL}/requirements`
        ),

        axios.get(
          `${API_BASE_URL}/journeys`
        ),

        axios.get(
          `${API_BASE_URL}/execution/results`
        ),

        axios.get(
          `${API_BASE_URL}/requirements/coverage/report`
        ),
      ]);

      setDashboard(
        dashboardResponse.data
      );

      setRequirements(
        requirementsResponse.data
          .requirements || []
      );

      setJourneys(
        journeysResponse.data
          .journeys || []
      );

      setExecutions(
        executionResponse.data
          .journeys || []
      );

      setCoverage(
        coverageResponse.data
          .coverage || []
      );

      setBugs(
        dashboardResponse.data?.bugs
          ?.bugs || []
      );
    } catch (err) {
      console.error(err);

      setError(
        "Unable to connect to the FastAPI backend. Make sure Uvicorn is running on port 8000."
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadTarget() {
    try {
      const response =
        await axios.get<TargetResponse>(
          `${API_BASE_URL}/analysis/target`
        );

      if (
        response.data.target_url
      ) {
        setTargetUrl(
          response.data.target_url
        );
      }
    } catch (err) {
      console.error(
        "Unable to load target URL:",
        err
      );
    }
  }

  async function saveTargetUrl() {
    try {
      setSavingTarget(true);
      setError("");
      setTargetSaved(false);

      const cleanUrl =
        targetUrl.trim();

      if (!cleanUrl) {
        setError(
          "Please enter an application URL."
        );

        return;
      }

      const response =
        await axios.post<TargetResponse>(
          `${API_BASE_URL}/analysis/target`,
          {
            url: cleanUrl,
          }
        );

      if (
        response.data.status ===
        "configured"
      ) {
        setTargetUrl(
          response.data.target_url ||
            cleanUrl
        );

        setJourneys([]);
        setGenerationMessage("Exploring target and generating new test cases...");

        let generationStatus = "running";
        while (generationStatus === "running") {
          await new Promise((resolve) => setTimeout(resolve, 2000));
          const statusResponse = await axios.get<ExecutionStatus>(
            `${API_BASE_URL}/analysis/generation`
          );
          generationStatus = statusResponse.data.status;
          setGenerationMessage(statusResponse.data.message);
        }

        if (generationStatus !== "completed") {
          throw new Error("Test generation failed. Check the backend generation status.");
        }

        await loadData();
        setTargetSaved(true);
        setTimeout(() => setTargetSaved(false), 3000);
      }
    } catch (err: any) {
      console.error(err);

      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Unable to configure target URL."
      );
    } finally {
      setSavingTarget(false);
    }
  }

  async function runTests() {
    try {
      setError("");
      setRunning(true);

      setExecutionStatus({
        status: "running",
        message:
          "Starting Playwright execution...",
      });

      const response =
        await axios.post(
          `${API_BASE_URL}/execution/run`
        );

      setExecutionStatus({
        status:
          response.data.status,
        message:
          response.data.message,
        updated_at:
          response.data.started_at,
      });
    } catch (err) {
      console.error(err);

      setRunning(false);

      setExecutionStatus({
        status: "failed",
        message:
          "Unable to start test execution.",
      });

      setError(
        "The test execution could not be started."
      );
    }
  }

  const execution =
    dashboard?.execution || {};

  const coverageSummary =
    dashboard?.coverage?.requirements ||
    {};

  const totalJourneys =
    execution.total_journeys || 0;

  const passedJourneys =
    execution.passed_journeys || 0;

  const failedJourneys =
    execution.failed_journeys || 0;

  const healedSteps =
    execution.healed_steps || 0;

  const coveragePercentage =
    coverageSummary.coverage_percentage ||
    0;

  const totalBugs =
    dashboard?.bugs?.total_bugs ||
    bugs.length;

  const successRate =
    totalJourneys > 0
      ? Math.round(
          (passedJourneys /
            totalJourneys) *
            100
        )
      : 0;

  function renderPage() {
    switch (page) {
      case "requirements":
        return (
          <RequirementsPage
            requirements={
              requirements
            }
          />
        );

      case "journeys":
        return (
          <JourneysPage
            journeys={journeys}
          />
        );

      case "executions":
        return (
          <ExecutionsPage
            executions={executions}
          />
        );

      case "coverage":
        return (
          <CoveragePage
            coverage={coverage}
          />
        );

      case "bugs":
        return (
          <BugsPage
            bugs={bugs}
          />
        );

      case "healing":
        return (
          <HealingPage
            executions={executions}
          />
        );

      default:
        return (
          <DashboardPage
            requirements={
              requirements
            }
            journeys={journeys}
            executions={executions}
            totalJourneys={
              totalJourneys
            }
            passedJourneys={
              passedJourneys
            }
            failedJourneys={
              failedJourneys
            }
            healedSteps={
              healedSteps
            }
            coveragePercentage={
              coveragePercentage
            }
            totalBugs={totalBugs}
            successRate={successRate}
            executionStatus={
              executionStatus
            }
          />
        );
    }
  }

  return (
    <div className="app">

      <aside className="sidebar">

        <div className="brand">

          <div className="brand-logo">
            AI
          </div>

          <div>
            <div className="brand-title">
              Test Intelligence
            </div>

            <div className="brand-subtitle">
              AI TestOps Platform
            </div>
          </div>

        </div>

        <div className="nav-section-title">
          TEST INTELLIGENCE
        </div>

        <nav className="navigation">

          <NavItem
            icon="▦"
            label="Dashboard"
            active={
              page === "dashboard"
            }
            onClick={() =>
              setPage("dashboard")
            }
          />

          <NavItem
            icon="◈"
            label="Requirements"
            active={
              page ===
              "requirements"
            }
            onClick={() =>
              setPage("requirements")
            }
          />

          <NavItem
            icon="✓"
            label="Test Journeys"
            active={
              page === "journeys"
            }
            onClick={() =>
              setPage("journeys")
            }
          />

          <NavItem
            icon="▶"
            label="Executions"
            active={
              page === "executions"
            }
            onClick={() =>
              setPage("executions")
            }
          />

          <NavItem
            icon="◎"
            label="Coverage"
            active={
              page === "coverage"
            }
            onClick={() =>
              setPage("coverage")
            }
          />

          <div className="nav-section-title second">
            INTELLIGENCE
          </div>

          <NavItem
            icon="⚠"
            label="Bugs"
            active={
              page === "bugs"
            }
            onClick={() =>
              setPage("bugs")
            }
          />

          <NavItem
            icon="↻"
            label="Self-Healing"
            active={
              page === "healing"
            }
            onClick={() =>
              setPage("healing")
            }
          />

        </nav>

        <div className="sidebar-bottom">

          <div className="backend-status">

            <span className="status-dot" />

            <span>
              Backend Connected
            </span>

          </div>

          <span className="version">
            v1.0.0
          </span>

        </div>

      </aside>


      <main className="main">

        <header className="topbar">

          <div>

            <h1>
              {getPageTitle(page)}
            </h1>

            <p>
              {getPageDescription(
                page
              )}
            </p>

          </div>

          <div className="topbar-actions">

            <div className="connection-indicator">

              <span className="status-dot" />

              API Online

            </div>

            <button
              className={
                running
                  ? "run-button running"
                  : "run-button"
              }
              disabled={running}
              onClick={runTests}
            >
              {running
                ? "▶ Running..."
                : "▶ Run AI Tests"}
            </button>

            <button
              className="refresh-button"
              onClick={loadData}
            >
              ↻ Refresh
            </button>

          </div>

        </header>


        {/* ==================================================
            TARGET APPLICATION
            ================================================== */}

        <section className="target-panel">

          <div className="target-panel-header">

            <div>

              <h2>
                Target Application
              </h2>

              <p>
                Enter the application URL
                that AI Test Intelligence
                should explore and test.
              </p>

            </div>

            <span className="target-status">

              {targetSaved
                ? "✓ CONFIGURED"
                : "READY"}

            </span>

          </div>


          <div className="target-input-row">

            <div className="url-input-wrapper">

              <span className="url-prefix">
                URL
              </span>

              <input
                type="url"
                value={targetUrl}
                onChange={(event) => {
                  setTargetUrl(
                    event.target.value
                  );

                  setTargetSaved(false);
                }}
                onKeyDown={(event) => {

                  if (
                    event.key ===
                    "Enter"
                  ) {
                    saveTargetUrl();
                  }

                }}
                placeholder="https://your-application.com"
                className="target-url-input"
              />

            </div>

            <button
              className="analyze-button"
              onClick={
                saveTargetUrl
              }
              disabled={
                savingTarget ||
                !targetUrl.trim()
              }
            >
              {savingTarget
                ? "Generating Tests..."
                : "Configure Target"}
            </button>

          </div>

          {generationMessage && (
            <p className="target-generation-status">
              {generationMessage}
            </p>
          )}

        </section>


        {error && (

          <div className="error-banner">

            <span>
              ⚠
            </span>

            {error}

          </div>

        )}


        {running && (

          <div className="execution-banner">

            <div className="execution-spinner" />

            <div>

              <strong>
                AI test execution
                running
              </strong>

              <span>
                {
                  executionStatus.message
                }
              </span>

            </div>

          </div>

        )}


        {loading ? (

          <div className="loading-container">

            <div className="loader" />

            <span>
              Loading test
              intelligence...
            </span>

          </div>

        ) : (

          renderPage()

        )}

      </main>

    </div>
  );
}


/* ============================================================
   DASHBOARD
   ============================================================ */

function DashboardPage({
  totalJourneys,
  passedJourneys,
  failedJourneys,
  healedSteps,
  coveragePercentage,
  totalBugs,
  successRate,
  requirements,
  journeys,
  executions,
  executionStatus,
}: {
  requirements: Requirement[];
  journeys: Journey[];
  executions: ExecutionJourney[];
  totalJourneys: number;
  passedJourneys: number;
  failedJourneys: number;
  healedSteps: number;
  coveragePercentage: number;
  totalBugs: number;
  successRate: number;
  executionStatus: ExecutionStatus;
}) {
  return (
    <>
      <section className="kpi-grid">

        <KpiCard
          label="Total Journeys"
          value={totalJourneys}
          description="AI-generated workflows"
          icon="✓"
        />

        <KpiCard
          label="Passed"
          value={passedJourneys}
          description={`${failedJourneys} failed journeys`}
          icon="✓"
          variant="success"
        />

        <KpiCard
          label="Coverage"
          value={`${coveragePercentage}%`}
          description="Requirement automation"
          icon="◎"
          variant="blue"
        />

        <KpiCard
          label="Self-Healed"
          value={healedSteps}
          description="Recovered locator steps"
          icon="↻"
          variant="warning"
        />

        <KpiCard
          label="AI Bugs"
          value={totalBugs}
          description="Generated defect reports"
          icon="⚠"
          variant="danger"
        />

      </section>


      <section className="two-column">

        <Panel
          title="Execution Overview"
          subtitle="Latest automated journey execution"
          action={
            <span className="tag">
              PLAYWRIGHT
            </span>
          }
        >

          <div className="execution-overview">

            <div className="execution-stat">
              <span>Total</span>

              <strong>
                {totalJourneys}
              </strong>
            </div>

            <div className="execution-stat">
              <span>Passed</span>

              <strong className="text-success">
                {passedJourneys}
              </strong>
            </div>

            <div className="execution-stat">
              <span>Failed</span>

              <strong className="text-danger">
                {failedJourneys}
              </strong>
            </div>

            <div className="execution-stat">
              <span>Healed</span>

              <strong className="text-warning">
                {healedSteps}
              </strong>
            </div>

          </div>


          <div className="progress-section">

            <div className="progress-header">

              <span>
                Journey success rate
              </span>

              <strong>
                {successRate}%
              </strong>

            </div>

            <ProgressBar
              value={successRate}
            />

          </div>

        </Panel>


        <Panel
          title="Execution Engine"
          subtitle="Current Playwright execution state"
        >

          <div className="engine-status">

            <div className="engine-status-icon">
              {executionStatus.status ===
              "running"
                ? "▶"
                : "✓"}
            </div>

            <div>

              <strong>
                {executionStatus.status ===
                "running"
                  ? "Execution Running"
                  : "Ready"}
              </strong>

              <span>
                {executionStatus.message ||
                  "Ready to execute AI-generated journeys."}
              </span>

            </div>

          </div>


          <div className="engine-capabilities">

            <span>
              Playwright
            </span>

            <span>
              AI Journeys
            </span>

            <span>
              Self-Healing
            </span>

            <span>
              Evidence
            </span>

          </div>

        </Panel>

      </section>


      <Panel
        title="Test Inventory"
        subtitle="Current AI-generated automation"
      >

        <div className="intelligence-grid">

          <IntelligenceCard
            label="Requirements"
            value={
              requirements.length
            }
            icon="◈"
          />

          <IntelligenceCard
            label="AI Journeys"
            value={
              journeys.length
            }
            icon="✓"
          />

          <IntelligenceCard
            label="Executed Journeys"
            value={
              executions.length
            }
            icon="▶"
          />

          <IntelligenceCard
            label="Execution Steps"
            value={
              executions.reduce(
                (
                  total,
                  journey
                ) =>
                  total +
                  (
                    journey.total_steps ||
                    0
                  ),
                0
              )
            }
            icon="≡"
          />

        </div>

      </Panel>


      <Panel
        title="Recent Executions"
        subtitle="Latest AI-generated test journeys"
        action={
          <span className="count-badge">
            {executions.length}
          </span>
        }
      >

        <ExecutionTable
          executions={
            executions.slice(0, 5)
          }
        />

      </Panel>

    </>
  );
}


/* ============================================================
   REQUIREMENTS
   ============================================================ */

function RequirementsPage({
  requirements,
}: {
  requirements: Requirement[];
}) {
  return (
    <Panel
      title="Requirements"
      subtitle="AI-analyzed product requirements and acceptance criteria"
      action={
        <span className="count-badge">
          {requirements.length}
        </span>
      }
    >

      <div className="table-container">

        <table>

          <thead>

            <tr>
              <th>ID</th>
              <th>Requirement</th>
              <th>Type</th>
              <th>Priority</th>
              <th>Acceptance Criteria</th>
            </tr>

          </thead>

          <tbody>

            {requirements.map(
              (requirement) => (

                <tr
                  key={
                    requirement
                      .requirement_id
                  }
                >

                  <td>

                    <CodeBadge
                      value={
                        requirement
                          .requirement_id
                      }
                    />

                  </td>

                  <td>

                    <div className="table-title">
                      {requirement.title}
                    </div>

                    <div className="table-description">
                      {
                        requirement.description
                      }
                    </div>

                  </td>

                  <td>

                    <span className="type-badge">
                      {requirement.type}
                    </span>

                  </td>

                  <td>

                    <PriorityBadge
                      priority={
                        requirement.priority
                      }
                    />

                  </td>

                  <td>

                    <span className="criteria-count">

                      {
                        requirement
                          .acceptance_criteria
                          ?.length || 0
                      }{" "}
                      criteria

                    </span>

                  </td>

                </tr>

              )
            )}

          </tbody>

        </table>

      </div>

    </Panel>
  );
}


/* ============================================================
   JOURNEYS
   ============================================================ */

function JourneysPage({
  journeys,
}: {
  journeys: Journey[];
}) {
  return (
    <div className="journey-grid">

      {journeys.map(
        (
          journey,
          index
        ) => (

          <div
            className="journey-card"
            key={index}
          >

            <div className="journey-card-header">

              <span className="journey-number">

                {String(
                  index + 1
                ).padStart(2, "0")}

              </span>

              <PriorityBadge
                priority={
                  journey.priority
                }
              />

            </div>


            <h3>
              {journey.title}
            </h3>


            <p>
              {journey.description}
            </p>


            <div className="journey-meta">

              <span>
                {journey.type}
              </span>

              <span>
                {
                  journey.actions
                    ?.length || 0
                }{" "}
                steps
              </span>

            </div>


            <div className="expected-result">

              <span>
                EXPECTED RESULT
              </span>

              <p>
                {journey.expected_result}
              </p>

            </div>

          </div>

        )
      )}

    </div>
  );
}


/* ============================================================
   EXECUTIONS
   ============================================================ */

function ExecutionsPage({
  executions,
}: {
  executions: ExecutionJourney[];
}) {
  return (
    <Panel
      title="Execution Results"
      subtitle="Playwright journey execution and step-level evidence"
      action={
        <span className="count-badge">
          {executions.length}
        </span>
      }
    >

      <ExecutionTable
        executions={executions}
        showSteps
      />

    </Panel>
  );
}


/* ============================================================
   COVERAGE
   ============================================================ */

function CoveragePage({
  coverage,
}: {
  coverage: CoverageItem[];
}) {
  const full =
    coverage.filter(
      (item) =>
        item.coverage_level ===
        "FULL"
    ).length;

  const partial =
    coverage.filter(
      (item) =>
        item.coverage_level ===
        "PARTIAL"
    ).length;

  const none =
    coverage.filter(
      (item) =>
        item.coverage_level ===
        "NONE"
    ).length;

  const percentage =
    coverage.length
      ? Math.round(
          (full /
            coverage.length) *
            100
        )
      : 0;

  return (
    <>
      <section className="kpi-grid three">

        <KpiCard
          label="Coverage"
          value={`${percentage}%`}
          description="Fully covered requirements"
          icon="◎"
          variant="blue"
        />

        <KpiCard
          label="Full"
          value={full}
          description="Passing automation"
          icon="✓"
          variant="success"
        />

        <KpiCard
          label="Gaps"
          value={
            partial + none
          }
          description="Requirements needing attention"
          icon="⚠"
          variant="warning"
        />

      </section>


      <Panel
        title="Requirements Traceability"
        subtitle="Requirement → Journey → Execution"
      >

        <div className="table-container">

          <table>

            <thead>

              <tr>
                <th>Requirement</th>
                <th>Priority</th>
                <th>Coverage</th>
                <th>Matching Journeys</th>
                <th>Execution</th>
                <th>Recommendation</th>
              </tr>

            </thead>

            <tbody>

              {coverage.map(
                (item) => (

                  <tr
                    key={
                      item.requirement_id
                    }
                  >

                    <td>

                      <CodeBadge
                        value={
                          item.requirement_id
                        }
                      />

                      <div className="table-title">
                        {item.title}
                      </div>

                    </td>

                    <td>

                      <PriorityBadge
                        priority={
                          item.priority
                        }
                      />

                    </td>

                    <td>

                      <CoverageBadge
                        value={
                          item.coverage_level
                        }
                      />

                    </td>

                    <td>
                      {
                        item
                          .matching_journeys
                          ?.length || 0
                      }
                    </td>

                    <td>

                      {item
                        .passed_journeys
                        ?.length >
                        0 && (
                        <span className="text-success">
                          ✓ Passing
                        </span>
                      )}

                      {item
                        .failed_journeys
                        ?.length >
                        0 && (
                        <span className="text-danger">
                          ✕ Failed
                        </span>
                      )}

                      {item
                        .passed_journeys
                        ?.length ===
                        0 &&
                        item
                          .failed_journeys
                          ?.length ===
                          0 && (
                          <span className="muted">
                            Not executed
                          </span>
                        )}

                    </td>

                    <td>

                      <span className="recommendation">
                        {
                          item.recommendation
                        }
                      </span>

                    </td>

                  </tr>

                )
              )}

            </tbody>

          </table>

        </div>

      </Panel>
    </>
  );
}


/* ============================================================
   BUGS
   ============================================================ */

function BugsPage({
  bugs,
}: {
  bugs: Bug[];
}) {
  if (bugs.length === 0) {
    return (
      <EmptyState
        icon="✓"
        title="No AI-generated bugs"
        description="No application defects have been generated from the current execution evidence."
      />
    );
  }

  return (
    <Panel
      title="AI Bug Reports"
      subtitle="Defects generated from execution and failure evidence"
      action={
        <span className="count-badge">
          {bugs.length}
        </span>
      }
    >

      <div className="bug-list">

        {bugs.map(
          (bug) => (

            <div
              className="bug-card"
              key={bug.bug_id}
            >

              <div className="bug-header">

                <div>

                  <CodeBadge
                    value={
                      bug.bug_id
                    }
                  />

                  <h3>
                    {bug.title}
                  </h3>

                </div>

                <div className="bug-badges">

                  <SeverityBadge
                    value={
                      bug.severity
                    }
                  />

                  <PriorityBadge
                    priority={
                      bug.priority
                    }
                  />

                </div>

              </div>


              <p>
                {bug.summary}
              </p>


              <div className="bug-grid">

                <BugField
                  title="Expected"
                  value={
                    bug.expected_result
                  }
                />

                <BugField
                  title="Actual"
                  value={
                    bug.actual_result
                  }
                />

                <BugField
                  title="Root Cause"
                  value={
                    bug.root_cause
                  }
                />

                <BugField
                  title="Suggested Fix"
                  value={
                    bug.suggested_fix
                  }
                />

              </div>

            </div>

          )
        )}

      </div>

    </Panel>
  );
}


/* ============================================================
   SELF HEALING
   ============================================================ */

function HealingPage({
  executions,
}: {
  executions: ExecutionJourney[];
}) {
  const healedSteps =
    executions.flatMap(
      (journey) =>
        journey.steps?.filter(
          (step) =>
            step.healed === true
        ) || []
    );

  return (
    <>
      <section className="kpi-grid three">

        <KpiCard
          label="Healed Steps"
          value={
            healedSteps.length
          }
          description="Automatically recovered"
          icon="↻"
          variant="warning"
        />

        <KpiCard
          label="Healing Engine"
          value="ACTIVE"
          description="DOM candidate resolution"
          icon="◆"
          variant="success"
        />

        <KpiCard
          label="Retry"
          value="ENABLED"
          description="Automatic retry after failure"
          icon="▶"
          variant="blue"
        />

      </section>


      <Panel
        title="Self-Healing Activity"
        subtitle="Locator recovery performed during execution"
      >

        {healedSteps.length ===
        0 ? (

          <EmptyState
            icon="↻"
            title="No healing events"
            description="No locator recovery was required in the latest execution."
          />

        ) : (

          <div className="healing-list">

            {executions.map(
              (journey) =>
                journey.steps
                  ?.filter(
                    (step) =>
                      step.healed
                  )
                  .map(
                    (
                      step,
                      index
                    ) => (

                      <div
                        className="healing-card"
                        key={`${journey.journey_index}-${index}`}
                      >

                        <div className="healing-icon">
                          ↻
                        </div>

                        <div className="healing-content">

                          <strong>
                            {
                              journey.title
                            }
                          </strong>

                          <div className="healing-targets">

                            <span>
                              {
                                step.target
                              }
                            </span>

                            <span>
                              →
                            </span>

                            <span className="text-success">
                              {
                                step.locator_strategy
                              }
                            </span>

                          </div>

                          <small>
                            Action:{" "}
                            {
                              step.action
                            }
                          </small>

                        </div>

                        <span className="status-pill passed">
                          HEALED
                        </span>

                      </div>

                    )
                  )
            )}

          </div>

        )}

      </Panel>
    </>
  );
}


/* ============================================================
   EXECUTION TABLE
   ============================================================ */

function ExecutionTable({
  executions,
  showSteps = false,
}: {
  executions: ExecutionJourney[];
  showSteps?: boolean;
}) {
  return (
    <div className="table-container">

      <table>

        <thead>

          <tr>
            <th>Journey</th>
            <th>Status</th>
            <th>Steps</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Healed</th>
          </tr>

        </thead>

        <tbody>

          {executions.map(
            (execution) => (

              <tr
                key={
                  execution.journey_index
                }
              >

                <td>

                  <div className="table-title">
                    {
                      execution.title
                    }
                  </div>

                  {showSteps && (
                    <div className="step-list">

                      {execution.steps?.map(
                        (
                          step,
                          index
                        ) => (

                          <span
                            key={index}
                            className={
                              step.status ===
                              "PASSED"
                                ? "step passed"
                                : "step failed"
                            }
                          >

                            {index + 1}.{" "}

                            {
                              step.action
                            }

                            {step.healed
                              ? " ↻"
                              : ""}

                          </span>

                        )
                      )}

                    </div>
                  )}

                </td>

                <td>

                  <StatusBadge
                    status={
                      execution.status
                    }
                  />

                </td>

                <td>
                  {
                    execution.total_steps
                  }
                </td>

                <td className="text-success">
                  {
                    execution.passed_steps
                  }
                </td>

                <td className="text-danger">
                  {
                    execution.failed_steps
                  }
                </td>

                <td className="text-warning">
                  {
                    execution.healed_steps
                  }
                </td>

              </tr>

            )
          )}

        </tbody>

      </table>

    </div>
  );
}


/* ============================================================
   GENERIC COMPONENTS
   ============================================================ */

function Panel({
  title,
  subtitle,
  children,
  action,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="panel">

      <div className="panel-header">

        <div>

          <h2>
            {title}
          </h2>

          {subtitle && (
            <p>
              {subtitle}
            </p>
          )}

        </div>

        {action}

      </div>

      <div className="panel-content">
        {children}
      </div>

    </section>
  );
}


function KpiCard({
  label,
  value,
  description,
  icon,
  variant = "default",
}: {
  label: string;
  value: string | number;
  description: string;
  icon: string;
  variant?: string;
}) {
  return (
    <div className="kpi-card">

      <div
        className={`kpi-icon ${variant}`}
      >
        {icon}
      </div>

      <span className="kpi-label">
        {label}
      </span>

      <strong className="kpi-value">
        {value}
      </strong>

      <span className="kpi-description">
        {description}
      </span>

    </div>
  );
}


function IntelligenceCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: string;
}) {
  return (
    <div className="intelligence-card">

      <div className="intelligence-card-icon">
        {icon}
      </div>

      <div>

        <span>
          {label}
        </span>

        <strong>
          {value}
        </strong>

      </div>

    </div>
  );
}


function ProgressBar({
  value,
}: {
  value: number;
}) {
  return (
    <div className="progress-track">

      <div
        className="progress-value"
        style={{
          width: `${Math.min(
            100,
            Math.max(0, value)
          )}%`,
        }}
      />

    </div>
  );
}


function NavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: string;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={
        active
          ? "nav-item active"
          : "nav-item"
      }
      onClick={onClick}
    >

      <span className="nav-icon">
        {icon}
      </span>

      <span>
        {label}
      </span>

    </button>
  );
}


function CodeBadge({
  value,
}: {
  value: string;
}) {
  return (
    <span className="code-badge">
      {value}
    </span>
  );
}


function PriorityBadge({
  priority,
}: {
  priority: string;
}) {
  const value =
    priority || "Unknown";

  return (
    <span
      className={`priority-badge ${value
        .toLowerCase()
        .replace(
          /\s+/g,
          "-"
        )}`}
    >
      {value}
    </span>
  );
}


function CoverageBadge({
  value,
}: {
  value: string;
}) {
  return (
    <span
      className={`coverage-badge ${value.toLowerCase()}`}
    >
      {value}
    </span>
  );
}


function StatusBadge({
  status,
}: {
  status: string;
}) {
  const passed =
    status.toLowerCase() ===
    "passed";

  return (
    <span
      className={
        passed
          ? "status-pill passed"
          : "status-pill failed"
      }
    >
      {passed
        ? "PASSED"
        : "FAILED"}
    </span>
  );
}


function SeverityBadge({
  value,
}: {
  value: string;
}) {
  return (
    <span
      className={`severity-badge ${value
        .toLowerCase()
        .replace(
          /\s+/g,
          "-"
        )}`}
    >
      {value}
    </span>
  );
}


function BugField({
  title,
  value,
}: {
  title: string;
  value: string;
}) {
  return (
    <div className="bug-field">

      <span>
        {title}
      </span>

      <p>
        {value ||
          "Not available"}
      </p>

    </div>
  );
}


function EmptyState({
  icon,
  title,
  description,
}: {
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <div className="empty-state">

      <div className="empty-icon">
        {icon}
      </div>

      <h3>
        {title}
      </h3>

      <p>
        {description}
      </p>

    </div>
  );
}


/* ============================================================
   PAGE TITLES
   ============================================================ */

function getPageTitle(
  page: Page
): string {
  switch (page) {

    case "requirements":
      return "Requirements";

    case "journeys":
      return "AI Test Journeys";

    case "executions":
      return "Test Executions";

    case "coverage":
      return "Requirement Coverage";

    case "bugs":
      return "AI Bug Reports";

    case "healing":
      return "Self-Healing";

    default:
      return "Test Intelligence Dashboard";
  }
}


function getPageDescription(
  page: Page
): string {
  switch (page) {

    case "requirements":
      return "Requirement analysis and acceptance criteria.";

    case "journeys":
      return "AI-generated end-to-end workflows from the real application.";

    case "executions":
      return "Playwright execution results and step evidence.";

    case "coverage":
      return "Trace requirements through tests and execution.";

    case "bugs":
      return "AI-generated defects from execution evidence.";

    case "healing":
      return "Automatic locator recovery and retry intelligence.";

    default:
      return "AI-powered testing, execution, coverage and failure intelligence.";
  }
}


export default App;
