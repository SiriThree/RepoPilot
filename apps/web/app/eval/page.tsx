"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { MetricCard } from "@/components/MetricCard";
import { EvaluationRun, createEvaluation, listEvaluations } from "@/lib/api";

const defaultCasesPath = "D:\\找实习\\insight-agent-studio\\benchmark\\cases\\sample_cases.json";

function renderBreakdownMap(items: Record<string, number>) {
  const entries = Object.entries(items);
  if (entries.length === 0) {
    return <li>当前没有可展示的失败聚合结果。</li>;
  }

  return entries
    .sort((left, right) => right[1] - left[1])
    .map(([key, count]) => (
      <li key={key}>
        <strong>{key}</strong>
        <p>出现次数：{count}</p>
      </li>
    ));
}

export default function EvalPage() {
  const [casesPath, setCasesPath] = useState(defaultCasesPath);
  const [evaluation, setEvaluation] = useState<EvaluationRun | null>(null);
  const [history, setHistory] = useState<EvaluationRun[]>([]);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  async function refreshHistory() {
    const nextHistory = await listEvaluations();
    setHistory(nextHistory);
    if (!evaluation && nextHistory.length > 0) {
      setEvaluation(nextHistory[0]);
    }
  }

  function submit() {
    setError("");
    startTransition(async () => {
      try {
        const nextEvaluation = await createEvaluation({
          name: "RepoPilot Sample Benchmark",
          casesPath
        });
        setEvaluation(nextEvaluation);
        await refreshHistory();
      } catch {
        setError("评测启动失败。请确认 case 文件路径存在，并且后端已经启动。");
      }
    });
  }

  const passRate = evaluation ? `${(evaluation.result.pass_rate * 100).toFixed(1)}%` : "-";
  const baselinePassRate =
    evaluation?.result.baseline_pass_rate !== undefined && evaluation.result.baseline_pass_rate !== null
      ? `${(evaluation.result.baseline_pass_rate * 100).toFixed(1)}%`
      : "-";
  const passRateDelta =
    evaluation?.result.pass_rate_delta !== undefined && evaluation.result.pass_rate_delta !== null
      ? `+${(evaluation.result.pass_rate_delta * 100).toFixed(1)} pts`
      : "-";
  const passedCount = evaluation?.passed_count?.toString() ?? "0";
  const caseCount = evaluation?.case_count?.toString() ?? "0";
  const avgIterations = evaluation?.avg_iterations?.toString() ?? "-";
  const highRiskCount = evaluation?.result.high_risk_intercepted_count?.toString() ?? "0";
  const unauthorizedCount = evaluation?.result.unauthorized_file_modification_count?.toString() ?? "0";

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">RepoPilot Eval Lab</div>
        <nav className="nav">
          <Link href="/dashboard">运行台</Link>
          <Link href="/eval">评测台</Link>
        </nav>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow">Benchmark and Bad Cases</div>
          <h1>让 Agent 的优化建立在坏例分析上。</h1>
          <p>
            这一页用于批量运行 benchmark case，并按失败原因、失败阶段和最后命令进行聚合，
            帮我们判断问题究竟出在规划、补丁生成、测试环境还是执行约束上。
          </p>
        </div>

        <div className="agent-console">
          <label className="field-label" htmlFor="cases-path">
            Benchmark Case File
          </label>
          <input id="cases-path" value={casesPath} onChange={(event) => setCasesPath(event.target.value)} />
          <button onClick={submit} disabled={isPending}>
            {isPending ? "评测执行中..." : "运行一次 Benchmark"}
          </button>
          <button className="secondary-button" onClick={() => void refreshHistory()} disabled={isPending}>
            刷新评测历史
          </button>
          {error ? <p className="empty">{error}</p> : null}
        </div>
      </section>

      <section className="grid">
        <MetricCard label="通过率" value={passRate} hint="passed_count / case_count" />
        <MetricCard label="Baseline" value={baselinePassRate} hint="single-shot pass rate" />
        <MetricCard label="提升幅度" value={passRateDelta} hint="RepoPilot - baseline" />
        <MetricCard label="高风险拦截" value={highRiskCount} hint="pending high-risk commands" />
      </section>

      <section className="content">
        <article className="panel">
          <h2>本次评测摘要</h2>
          <ul className="recommendations">
            <li>名称：{evaluation?.name ?? "等待启动评测"}</li>
            <li>状态：{evaluation?.status ?? "idle"}</li>
            <li>通过率：{passRate}</li>
            <li>Baseline 通过率：{baselinePassRate}</li>
            <li>提升幅度：{passRateDelta}</li>
            <li>通过 Case：{passedCount} / {caseCount}</li>
            <li>平均修复轮数：{avgIterations}</li>
            <li>高风险命令拦截：{highRiskCount}</li>
            <li>越权文件修改：{unauthorizedCount}</li>
            <li>结果文件：{evaluation?.result.result_file ?? "-"}</li>
          </ul>
        </article>

        <article className="panel">
          <h2>失败原因分布</h2>
          <ol className="steps">{renderBreakdownMap(evaluation?.result.failure_breakdown ?? {})}</ol>
        </article>

        <article className="panel">
          <h2>失败阶段分布</h2>
          <ol className="steps">{renderBreakdownMap(evaluation?.result.failed_phase_breakdown ?? {})}</ol>
        </article>

        <article className="panel">
          <h2>失败命令分布</h2>
          <ol className="steps">{renderBreakdownMap(evaluation?.result.failed_command_breakdown ?? {})}</ol>
        </article>

        <article className="panel">
          <h2>Case 结果</h2>
          <ol className="steps">
            {evaluation?.result.cases.length ? (
              evaluation.result.cases.map((item) => (
                <li key={item.run_id}>
                  <strong>{item.name}</strong>
                  <p>
                    Success: {item.success ? "Yes" : "No"} · Tests: {item.tests_passed ? "Passed" : "Failed"} ·
                    Iterations: {item.iterations}
                  </p>
                  <p>
                    Failure: {item.failure_reason ?? "-"} · Phase: {item.failed_phase ?? "-"} · Risk:{" "}
                    {item.failed_command_risk ?? "-"}
                  </p>
                  <code>{item.failed_command ?? item.summary}</code>
                </li>
              ))
            ) : (
              <li>等待 benchmark 结果。</li>
            )}
          </ol>
        </article>

        <article className="panel">
          <h2>评测历史</h2>
          <ol className="steps">
            {history.length ? (
              history.map((item) => (
                <li key={item.id}>
                  <strong>{item.name}</strong>
                  <p>
                    Cases: {item.case_count} · Passed: {item.passed_count} · Avg iterations: {item.avg_iterations}
                  </p>
                  <code>{item.created_at}</code>
                </li>
              ))
            ) : (
              <li>还没有评测记录。</li>
            )}
          </ol>
        </article>
      </section>
    </main>
  );
}
