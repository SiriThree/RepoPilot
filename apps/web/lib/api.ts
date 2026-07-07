export type RunStep = {
  step_index: number;
  phase: string;
  tool_name: string;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown>;
  status: string;
};

export type CommandEvent = {
  command: string;
  risk_level: string;
  approval_status: string;
  exit_code: number | null;
  stdout_summary: string;
  stderr_summary: string;
  duration_ms: number;
};

export type AgentRun = {
  id: string;
  repo_path: string;
  task_input: string;
  base_ref: string;
  status: string;
  worktree_path: string;
  summary: string;
  created_at: string;
  finished_at: string | null;
  result: {
    summary: string;
    tests_passed: boolean;
    files_changed: string[];
    iterations: number;
    diff_text: string;
    diff_stats: {
      added_lines: number;
      removed_lines: number;
      hunks: number;
    };
    plan?: {
      task_type: string;
      suspected_files: string[];
      test_strategy: string[];
      reasoning_summary: string;
    };
    patch_proposal?: {
      path: string;
      old_snippet: string;
      new_snippet: string;
      reasoning_summary: string;
    } | null;
    patch_plan?: {
      patches: Array<{
        path: string;
        old_snippet: string;
        new_snippet: string;
        reasoning_summary: string;
      }>;
      reasoning_summary: string;
    } | null;
    approved_commands?: string[];
    pending_approval?: {
      command: string;
      command_key: string;
      risk_level: string;
      reason: string;
    } | null;
    failure_reason?: string | null;
    repo_url?: string | null;
    test_command?: string | null;
    setup_commands?: string[];
    test_patch?: string | null;
    issue_text?: string | null;
    issue_url?: string | null;
    ground_truth_pr?: string | null;
    ground_truth_commit?: string | null;
    profile: {
      file_count: number;
      languages: string[];
      has_pytest: boolean;
      top_level_dirs: string[];
    };
    initial_test: {
      passed: boolean;
      error_excerpt: string;
      duration_ms: number;
    };
    final_test: {
      passed: boolean;
      error_excerpt: string;
      duration_ms: number;
    };
  };
  steps: RunStep[];
  command_events: CommandEvent[];
};

export type EvaluationCaseResult = {
  name: string;
  run_id: string;
  repo_path: string;
  success: boolean;
  tests_passed: boolean;
  iterations: number;
  files_changed: string[];
  expected_changed_files: string[];
  failure_reason?: string | null;
  failed_phase?: string | null;
  failed_command?: string | null;
  failed_command_risk?: string | null;
  summary: string;
};

export type EvaluationRun = {
  id: string;
  name: string;
  status: string;
  case_count: number;
  passed_count: number;
  avg_iterations: number;
  created_at: string;
  result: {
    pass_rate: number;
    baseline_pass_rate?: number | null;
    pass_rate_delta?: number | null;
    high_risk_intercepted_count: number;
    unauthorized_file_modification_count: number;
    result_file?: string;
    failure_breakdown: Record<string, number>;
    failed_phase_breakdown: Record<string, number>;
    failed_command_breakdown: Record<string, number>;
    cases: EvaluationCaseResult[];
  };
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function createAgentRun(input: {
  repoPath?: string;
  repoUrl?: string;
  taskInput: string;
  baseRef?: string;
  testCommand?: string;
  setupCommands?: string[];
  testPatch?: string;
  issueText?: string;
  issueUrl?: string;
  groundTruthPr?: string;
  groundTruthCommit?: string;
}): Promise<AgentRun> {
  const response = await fetch(`${API_BASE_URL}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_path: input.repoPath ?? "",
      repo_url: input.repoUrl || null,
      task_input: input.taskInput,
      base_ref: input.baseRef ?? "HEAD",
      test_command: input.testCommand || null,
      setup_commands: input.setupCommands ?? [],
      test_patch: input.testPatch || null,
      issue_text: input.issueText || null,
      issue_url: input.issueUrl || null,
      ground_truth_pr: input.groundTruthPr || null,
      ground_truth_commit: input.groundTruthCommit || null
    }),
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Agent request failed: ${response.status}`);
  }

  return response.json();
}

export async function listAgentRuns(): Promise<AgentRun[]> {
  const response = await fetch(`${API_BASE_URL}/api/runs`, { cache: "no-store" });
  if (!response.ok) {
    return [];
  }
  return response.json();
}

export async function approveAgentRun(runId: string, commandKey: string): Promise<AgentRun> {
  const response = await fetch(`${API_BASE_URL}/api/runs/${runId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command_key: commandKey }),
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Approval request failed: ${response.status}`);
  }

  return response.json();
}

export async function createEvaluation(input: {
  name: string;
  casesPath?: string;
  runBaseline?: boolean;
  autoApproveHighRisk?: boolean;
  writeResultFile?: boolean;
  cases?: Array<{
    name: string;
    repo_path: string;
    task_input: string;
    base_ref?: string;
    expected_changed_files?: string[];
  }>;
}): Promise<EvaluationRun> {
  const response = await fetch(`${API_BASE_URL}/api/evals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: input.name,
      cases_path: input.casesPath,
      run_baseline: input.runBaseline ?? true,
      auto_approve_high_risk: input.autoApproveHighRisk ?? true,
      write_result_file: input.writeResultFile ?? true,
      cases: input.cases ?? []
    }),
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Evaluation request failed: ${response.status}`);
  }

  return response.json();
}

export async function listEvaluations(): Promise<EvaluationRun[]> {
  const response = await fetch(`${API_BASE_URL}/api/evals`, { cache: "no-store" });
  if (!response.ok) {
    return [];
  }
  return response.json();
}
