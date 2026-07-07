"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { MetricCard } from "@/components/MetricCard";
import { AgentRun, approveAgentRun, createAgentRun, listAgentRuns } from "@/lib/api";

const defaultRepoPath = "D:\\repos\\example-python-service";
const defaultTask = "Fix the failing boundary check so zero raises ValueError and update tests if needed.";

function prettyJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

export default function DashboardPage() {
  const [repoPath, setRepoPath] = useState(defaultRepoPath);
  const [repoUrl, setRepoUrl] = useState("");
  const [baseRef, setBaseRef] = useState("HEAD");
  const [testCommand, setTestCommand] = useState("python -m pytest -q");
  const [issueUrl, setIssueUrl] = useState("");
  const [issueText, setIssueText] = useState("");
  const [groundTruthPr, setGroundTruthPr] = useState("");
  const [groundTruthCommit, setGroundTruthCommit] = useState("");
  const [taskInput, setTaskInput] = useState(defaultTask);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  async function refreshRuns() {
    const nextRuns = await listAgentRuns();
    setRuns(nextRuns);
    if (!run && nextRuns.length > 0) {
      setRun(nextRuns[0]);
    }
  }

  function submit() {
    setError("");
    startTransition(async () => {
      try {
        const nextRun = await createAgentRun({
          repoPath,
          repoUrl,
          taskInput,
          baseRef,
          testCommand,
          issueText,
          issueUrl,
          groundTruthPr,
          groundTruthCommit
        });
        setRun(nextRun);
        await refreshRuns();
      } catch {
        setError("后端暂时不可用，或仓库路径不是有效的本地 Git 仓库。请确认 FastAPI 已在 8000 端口启动。");
      }
    });
  }

  function approvePendingCommand() {
    if (!run?.result.pending_approval) {
      return;
    }
    setError("");
    startTransition(async () => {
      try {
        const nextRun = await approveAgentRun(run.id, run.result.pending_approval!.command_key);
        setRun(nextRun);
        await refreshRuns();
      } catch {
        setError("审批后重新执行失败，请检查后端日志。");
      }
    });
  }

  const testsPassed = run?.result.tests_passed ? "Passed" : run ? "Failed" : "Idle";
  const changedFiles = run?.result.files_changed.length ? run.result.files_changed.length.toString() : "0";
  const iterations = run?.result.iterations?.toString() ?? "-";
  const commands = run?.command_events.length?.toString() ?? "0";

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">RepoPilot Console</div>
        <nav className="nav">
          <Link href="/dashboard">运行台</Link>
          <Link href="/eval">评测台</Link>
        </nav>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow">Controlled Code Repair Agent</div>
          <h1>让代码修复 Agent 受控、可读、可批准。</h1>
          <p>
            RepoPilot 将自然语言修复任务转成可执行的 patch-test-repair 工作流。
            这一页重点展示规划结果、多文件 patch plan、高风险命令审批和最终 diff。
          </p>
        </div>

        <div className="agent-console">
          <label className="field-label" htmlFor="repo-path">
            Repository Path
          </label>
          <input id="repo-path" value={repoPath} onChange={(event) => setRepoPath(event.target.value)} />
          <label className="field-label" htmlFor="repo-url">
            Repository URL
          </label>
          <input id="repo-url" value={repoUrl} onChange={(event) => setRepoUrl(event.target.value)} />
          <label className="field-label" htmlFor="base-ref">
            Base Ref
          </label>
          <input id="base-ref" value={baseRef} onChange={(event) => setBaseRef(event.target.value)} />
          <label className="field-label" htmlFor="test-command">
            Test Command
          </label>
          <input id="test-command" value={testCommand} onChange={(event) => setTestCommand(event.target.value)} />
          <label className="field-label" htmlFor="issue-url">
            Issue URL
          </label>
          <input id="issue-url" value={issueUrl} onChange={(event) => setIssueUrl(event.target.value)} />
          <label className="field-label" htmlFor="task-input">
            Task Input
          </label>
          <textarea id="task-input" value={taskInput} onChange={(event) => setTaskInput(event.target.value)} />
          <label className="field-label" htmlFor="issue-text">
            Issue Text
          </label>
          <textarea id="issue-text" value={issueText} onChange={(event) => setIssueText(event.target.value)} />
          <label className="field-label" htmlFor="ground-truth-pr">
            Ground Truth PR
          </label>
          <input id="ground-truth-pr" value={groundTruthPr} onChange={(event) => setGroundTruthPr(event.target.value)} />
          <label className="field-label" htmlFor="ground-truth-commit">
            Ground Truth Commit
          </label>
          <input
            id="ground-truth-commit"
            value={groundTruthCommit}
            onChange={(event) => setGroundTruthCommit(event.target.value)}
          />
          <button onClick={submit} disabled={isPending}>
            {isPending ? "RepoPilot 正在执行..." : "启动一次受控修复"}
          </button>
          <button className="secondary-button" onClick={() => void refreshRuns()} disabled={isPending}>
            刷新最近运行
          </button>
          {error ? <p className="empty">{error}</p> : null}
        </div>
      </section>

      <section className="grid">
        <MetricCard label="测试状态" value={testsPassed} hint="最终测试结果" />
        <MetricCard label="修改文件" value={changedFiles} hint="final diff touched files" />
        <MetricCard label="修复轮数" value={iterations} hint="patch-test-repair loops" />
        <MetricCard label="命令事件" value={commands} hint="recorded command trace" />
      </section>

      <section className="content">
        <article className="panel">
          <h2>运行摘要</h2>
          <p>{run?.summary ?? "提交一个本地 Git 仓库和修复任务后，这里会显示最终执行摘要。"}</p>
          <ul className="recommendations">
            <li>任务内容：{run?.task_input ?? "等待输入任务"}</li>
            <li>仓库路径：{run?.repo_path ?? "等待输入仓库路径"}</li>
            <li>仓库 URL：{run?.result.repo_url ?? "-"}</li>
            <li>Base Ref：{run?.base_ref ?? "HEAD"}</li>
            <li>测试命令：{run?.result.test_command ?? "python -m pytest -q"}</li>
            <li>Issue URL：{run?.result.issue_url ?? "-"}</li>
            <li>Ground Truth：{run?.result.ground_truth_pr ?? run?.result.ground_truth_commit ?? "-"}</li>
            <li>工作树：{run?.worktree_path ?? "任务运行后生成独立 worktree"}</li>
            <li>运行状态：{run?.status ?? "idle"}</li>
            <li>失败原因：{run?.result.failure_reason ?? "-"}</li>
          </ul>
          {run?.result.diff_stats ? (
            <div className="pill-row">
              <span className="pill">+{run.result.diff_stats.added_lines} 行新增</span>
              <span className="pill">-{run.result.diff_stats.removed_lines} 行删除</span>
              <span className="pill">{run.result.diff_stats.hunks} 个 diff hunk</span>
            </div>
          ) : null}
          {run?.result.pending_approval ? (
            <div className="approval-card">
              <strong>待审批高风险命令</strong>
              <p>{run.result.pending_approval.command}</p>
              <p>{run.result.pending_approval.reason}</p>
              <button className="approve-button" onClick={approvePendingCommand} disabled={isPending}>
                批准并继续执行
              </button>
            </div>
          ) : null}
        </article>

        <article className="panel">
          <h2>规划结果</h2>
          <ul className="recommendations">
            <li>任务类型：{run?.result.plan?.task_type ?? "等待 planner 输出"}</li>
            <li>候选文件：{run?.result.plan?.suspected_files.join(", ") || "-"}</li>
            <li>测试策略：{run?.result.plan?.test_strategy.join(", ") || "-"}</li>
            <li>规划说明：{run?.result.plan?.reasoning_summary || "-"}</li>
          </ul>
        </article>

        <article className="panel">
          <h2>多文件 Patch Plan</h2>
          <ol className="steps">
            {run?.result.patch_plan?.patches?.length ? (
              run.result.patch_plan.patches.map((patch, index) => (
                <li key={`${patch.path}-${index}`}>
                  <strong>{patch.path}</strong>
                  <p>{patch.reasoning_summary}</p>
                  <code>
                    {patch.old_snippet}
                    {" -> "}
                    {patch.new_snippet}
                  </code>
                </li>
              ))
            ) : (
              <li>当前运行没有生成多文件 patch plan。</li>
            )}
          </ol>
        </article>

        <article className="panel">
          <h2>补丁提案概览</h2>
          <ul className="recommendations">
            <li>目标文件：{run?.result.patch_proposal?.path ?? "等待 patch 提案"}</li>
            <li>旧片段：{run?.result.patch_proposal?.old_snippet ?? "-"}</li>
            <li>新片段：{run?.result.patch_proposal?.new_snippet ?? "-"}</li>
            <li>修改理由：{run?.result.patch_proposal?.reasoning_summary ?? "-"}</li>
          </ul>
        </article>

        <article className="panel">
          <h2>测试观察</h2>
          <ul className="recommendations">
            <li>首次测试：{run?.result.initial_test.passed ? "通过" : "失败"}</li>
            <li>首次摘录：{run?.result.initial_test.error_excerpt || "等待首次测试输出"}</li>
            <li>最终测试：{run?.result.final_test.passed ? "通过" : "失败"}</li>
            <li>最终摘录：{run?.result.final_test.error_excerpt || "等待最终测试输出"}</li>
          </ul>
        </article>

        <article className="panel">
          <h2>执行轨迹</h2>
          <ol className="steps">
            {run?.steps.length ? (
              run.steps.map((step) => (
                <li key={`${step.step_index}-${step.tool_name}`}>
                  <strong>
                    Step {step.step_index}: {step.phase} / {step.tool_name}
                  </strong>
                  <p>状态：{step.status}</p>
                  <div className="log-block">{prettyJson(step.output_json)}</div>
                </li>
              ))
            ) : (
              <li>等待 RepoPilot 产生 trace。</li>
            )}
          </ol>
        </article>

        <article className="panel">
          <h2>命令日志</h2>
          <ol className="steps">
            {run?.command_events.length ? (
              run.command_events.map((event, index) => (
                <li key={`${event.command}-${index}`}>
                  <strong>{event.command}</strong>
                  <p>
                    风险等级：{event.risk_level} · 审批状态：{event.approval_status} · 退出码：
                    {event.exit_code ?? "-"} · 耗时：{event.duration_ms} ms
                  </p>
                  <div className="log-block">{event.stderr_summary || event.stdout_summary || "No output captured."}</div>
                </li>
              ))
            ) : (
              <li>等待受控命令执行。</li>
            )}
          </ol>
        </article>

        <article className="panel">
          <h2>最终 Diff</h2>
          {run?.result.diff_text ? (
            <div className="diff-block">{run.result.diff_text}</div>
          ) : (
            <p className="empty">任务完成后，这里会显示完整 diff。</p>
          )}
        </article>

        <article className="panel">
          <h2>最近运行</h2>
          <ol className="steps">
            {runs.length ? (
              runs.map((item) => (
                <li key={item.id}>
                  <strong>{item.status.toUpperCase()}</strong>
                  <p>{item.task_input}</p>
                  <code>{item.repo_path}</code>
                </li>
              ))
            ) : (
              <li>还没有运行记录。</li>
            )}
          </ol>
        </article>
      </section>
    </main>
  );
}
