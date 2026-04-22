from __future__ import annotations

import json
from html import escape
from typing import Any


def _embed_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def build_dashboard_html(payload: dict[str, Any]) -> str:
    initial_payload = _embed_json(payload)
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AIOS News Ecosystem</title>
    <style>
      :root {{
        --bg: #f3eee7;
        --panel: rgba(255, 250, 244, 0.9);
        --panel-strong: rgba(255, 253, 248, 0.98);
        --line: rgba(39, 38, 35, 0.1);
        --ink: #20232d;
        --muted: #6b6f7e;
        --brand: #845631;
        --brand-soft: #ead8bf;
        --teal: #1f6b70;
        --rose: #7e3049;
        --danger: #9e3f31;
        --success: #285f3a;
        --shadow: 0 22px 60px rgba(55, 41, 23, 0.12);
        --radius: 28px;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        color: var(--ink);
        background:
          radial-gradient(circle at top right, rgba(170, 112, 62, 0.18), transparent 28%),
          radial-gradient(circle at left center, rgba(31, 107, 112, 0.12), transparent 24%),
          var(--bg);
        font-family: "Source Han Sans SC", "Noto Sans SC", "PingFang SC", sans-serif;
      }}
      .shell {{
        width: min(1320px, calc(100vw - 28px));
        margin: 18px auto 44px;
      }}
      .hero {{
        display: grid;
        grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.8fr);
        gap: 18px;
        padding: 30px;
        border-radius: 36px;
        background:
          linear-gradient(135deg, rgba(244, 226, 200, 0.96), rgba(235, 240, 246, 0.94)),
          var(--panel-strong);
        border: 1px solid rgba(255,255,255,0.5);
        box-shadow: var(--shadow);
      }}
      .eyebrow {{
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 8px 14px;
        border-radius: 999px;
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        background: rgba(255,255,255,0.68);
        border: 1px solid rgba(32, 35, 45, 0.08);
      }}
      h1 {{
        margin: 16px 0 10px;
        font-family: "Source Han Serif SC", "Noto Serif SC", serif;
        font-size: clamp(2.5rem, 4vw, 4.4rem);
        line-height: 0.98;
      }}
      .lede {{
        margin: 0;
        max-width: 720px;
        color: rgba(32, 35, 45, 0.78);
        font-size: 1.06rem;
        line-height: 1.8;
      }}
      .hero-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 26px;
      }}
      button, .button-link {{
        appearance: none;
        border: 0;
        cursor: pointer;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        min-height: 44px;
        padding: 0 18px;
        border-radius: 999px;
        font-size: 0.95rem;
        font-weight: 600;
      }}
      .button-primary {{
        color: white;
        background: linear-gradient(135deg, #8d5a2e, #5d4030);
        box-shadow: 0 14px 28px rgba(93, 64, 48, 0.2);
      }}
      .button-secondary {{
        color: var(--ink);
        background: rgba(255,255,255,0.72);
        border: 1px solid var(--line);
      }}
      .hero-panel {{
        padding: 22px;
        border-radius: 26px;
        background: rgba(255,255,255,0.7);
        border: 1px solid rgba(32, 35, 45, 0.08);
      }}
      .hero-panel h2 {{
        margin: 0 0 12px;
        font-size: 1.05rem;
      }}
      .score-pill {{
        display: inline-flex;
        align-items: baseline;
        gap: 10px;
        padding: 14px 16px;
        border-radius: 20px;
        background: rgba(132, 86, 49, 0.1);
      }}
      .score-pill strong {{
        font-size: 2rem;
        line-height: 1;
      }}
      .score-pill span {{
        color: var(--muted);
      }}
      .mini-list {{
        display: grid;
        gap: 10px;
        margin-top: 16px;
      }}
      .mini-item {{
        padding: 12px 14px;
        border-radius: 18px;
        background: rgba(255,255,255,0.78);
        border: 1px solid rgba(32, 35, 45, 0.08);
        color: var(--muted);
      }}
      .metrics {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin-top: 18px;
      }}
      .metric-card, .panel {{
        background: var(--panel);
        border-radius: var(--radius);
        border: 1px solid var(--line);
        box-shadow: var(--shadow);
      }}
      .metric-card {{
        padding: 20px 22px;
      }}
      .metric-label {{
        font-size: 0.82rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }}
      .metric-value {{
        margin-top: 8px;
        font-size: 2.1rem;
        font-weight: 700;
      }}
      .metric-footnote {{
        margin-top: 6px;
        color: var(--muted);
        font-size: 0.92rem;
      }}
      .grid {{
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 18px;
        margin-top: 18px;
      }}
      .panel {{
        padding: 24px;
      }}
      .panel h2 {{
        margin: 0;
        font-size: 1.35rem;
      }}
      .panel-head {{
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 18px;
      }}
      .subtle {{
        color: var(--muted);
        font-size: 0.95rem;
      }}
      .stage-list {{
        display: grid;
        gap: 12px;
      }}
      .stage-card {{
        padding: 16px 18px;
        border-radius: 22px;
        background: rgba(255,255,255,0.72);
        border: 1px solid rgba(32, 35, 45, 0.08);
      }}
      .stage-top {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }}
      .stage-order {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border-radius: 999px;
        background: rgba(132, 86, 49, 0.12);
        color: var(--brand);
        font-weight: 700;
      }}
      .stage-label {{
        font-weight: 700;
      }}
      .status-chip {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 7px 12px;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 700;
      }}
      .status-success {{ background: rgba(40, 95, 58, 0.12); color: var(--success); }}
      .status-running {{ background: rgba(31, 107, 112, 0.12); color: var(--teal); }}
      .status-pending {{ background: rgba(132, 86, 49, 0.12); color: var(--brand); }}
      .status-failed {{ background: rgba(158, 63, 49, 0.12); color: var(--danger); }}
      .status-partial {{ background: rgba(126, 48, 73, 0.12); color: var(--rose); }}
      .stage-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 10px;
        color: var(--muted);
        font-size: 0.92rem;
      }}
      .list-block {{
        display: grid;
        gap: 12px;
      }}
      .bullet-card {{
        padding: 14px 16px;
        border-radius: 20px;
        background: rgba(255,255,255,0.72);
        border: 1px solid rgba(32, 35, 45, 0.08);
      }}
      .bullet-card strong {{
        display: block;
        margin-bottom: 8px;
      }}
      .bullet-card ul {{
        margin: 0;
        padding-left: 18px;
        color: var(--muted);
        line-height: 1.7;
      }}
      .domain-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
      }}
      .domain-card {{
        padding: 18px;
        border-radius: 24px;
        background: rgba(255,255,255,0.72);
        border: 1px solid rgba(32, 35, 45, 0.08);
      }}
      .domain-card h3 {{
        margin: 0 0 8px;
        font-size: 1.08rem;
      }}
      .domain-desc {{
        color: var(--muted);
        font-size: 0.92rem;
        line-height: 1.6;
      }}
      .domain-strip {{
        margin-top: 14px;
        height: 8px;
        border-radius: 999px;
        background: rgba(32, 35, 45, 0.08);
        overflow: hidden;
      }}
      .domain-strip > span {{
        display: block;
        height: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, #7a5232, #1f6b70);
      }}
      .domain-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 12px;
        color: var(--muted);
        font-size: 0.9rem;
      }}
      .title-list {{
        margin-top: 12px;
        display: grid;
        gap: 8px;
      }}
      .title-pill {{
        padding: 10px 12px;
        border-radius: 16px;
        background: rgba(132, 86, 49, 0.08);
        font-size: 0.92rem;
      }}
      .report-grid {{
        display: grid;
        grid-template-columns: 0.95fr 1.05fr;
        gap: 18px;
      }}
      .report-card {{
        padding: 22px;
        border-radius: 26px;
        background:
          linear-gradient(180deg, rgba(245, 231, 208, 0.8), rgba(255,255,255,0.9)),
          var(--panel-strong);
        border: 1px solid rgba(32, 35, 45, 0.08);
      }}
      .report-title {{
        margin: 12px 0 8px;
        font-family: "Source Han Serif SC", "Noto Serif SC", serif;
        font-size: 2rem;
        line-height: 1.08;
      }}
      .report-overview {{
        color: var(--muted);
        line-height: 1.8;
      }}
      .highlight-list {{
        display: grid;
        gap: 12px;
      }}
      .highlight-item {{
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(255,255,255,0.74);
        border: 1px solid rgba(32, 35, 45, 0.08);
      }}
      .run-list {{
        display: grid;
        gap: 12px;
      }}
      .run-item {{
        padding: 16px 18px;
        border-radius: 20px;
        background: rgba(255,255,255,0.74);
        border: 1px solid rgba(32, 35, 45, 0.08);
      }}
      .run-id {{
        font-family: "JetBrains Mono", "Fira Code", monospace;
        font-size: 0.82rem;
        color: var(--muted);
      }}
      .artifact-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
      }}
      .artifact-card {{
        padding: 16px;
        border-radius: 20px;
        background: rgba(255,255,255,0.74);
        border: 1px solid rgba(32, 35, 45, 0.08);
      }}
      .artifact-card strong {{
        display: block;
        margin-bottom: 8px;
      }}
      .artifact-files {{
        margin-top: 10px;
        display: grid;
        gap: 6px;
        color: var(--muted);
        font-size: 0.84rem;
      }}
      .empty {{
        padding: 22px;
        border-radius: 22px;
        background: rgba(255,255,255,0.72);
        border: 1px dashed rgba(32, 35, 45, 0.14);
        color: var(--muted);
      }}
      @media (max-width: 1080px) {{
        .hero,
        .grid,
        .report-grid {{
          grid-template-columns: 1fr;
        }}
        .metrics,
        .domain-grid,
        .artifact-grid {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
      }}
      @media (max-width: 720px) {{
        .shell {{
          width: min(100vw - 16px, 100%);
          margin: 8px auto 24px;
        }}
        .hero,
        .panel {{
          padding: 18px;
        }}
        .metrics,
        .domain-grid,
        .artifact-grid {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="shell">
      <section class="hero">
        <div>
          <div class="eyebrow">AIOS Kernel Powered Newsroom</div>
          <h1>AIOS News Ecosystem</h1>
          <p class="lede">把热榜抓取、分类、检索、生成、审阅和日报制作收成一套可运行、可观察、可前端展示的 agent workflow。这个页面既是操作台，也是面试时最直观的系统快照。</p>
          <div class="hero-actions">
            <button class="button-primary" id="run-serial">运行一轮日报</button>
            <button class="button-secondary" id="refresh-dashboard">刷新状态</button>
            <a class="button-secondary button-link" href="/api/ecosystem/reports/latest/html" target="_blank" rel="noreferrer">打开最新日报</a>
          </div>
        </div>
        <aside class="hero-panel">
          <h2>系统评测</h2>
          <div id="hero-score"></div>
          <div class="mini-list" id="hero-bullets"></div>
        </aside>
      </section>

      <section class="metrics" id="metrics"></section>

      <section class="grid">
        <div class="panel">
          <div class="panel-head">
            <div>
              <h2>Workflow Timeline</h2>
              <div class="subtle">每个阶段的耗时、状态和产物数都会在这里汇总。</div>
            </div>
          </div>
          <div class="stage-list" id="stage-list"></div>
        </div>
        <div class="panel">
          <div class="panel-head">
            <div>
              <h2>质量判断</h2>
              <div class="subtle">把当前运行从“能跑”推进到“可讲、可演示、可继续做”。</div>
            </div>
          </div>
          <div class="list-block" id="evaluation-block"></div>
        </div>
      </section>

      <section class="panel" style="margin-top: 18px;">
        <div class="panel-head">
          <div>
            <h2>Domain Coverage</h2>
            <div class="subtle">看每个领域到底抓到了多少话题、生成了多少成稿、还缺哪一块。</div>
          </div>
        </div>
        <div class="domain-grid" id="domain-grid"></div>
      </section>

      <section class="grid">
        <div class="panel">
          <div class="panel-head">
            <div>
              <h2>Latest Brief</h2>
              <div class="subtle">最新日报的标题、总览和亮点入口。</div>
            </div>
          </div>
          <div class="report-grid" id="report-grid"></div>
        </div>
        <div class="panel">
          <div class="panel-head">
            <div>
              <h2>Recent Runs</h2>
              <div class="subtle">最近的运行记录，方便回放和比较。</div>
            </div>
          </div>
          <div class="run-list" id="run-list"></div>
        </div>
      </section>

      <section class="panel" style="margin-top: 18px;">
        <div class="panel-head">
          <div>
            <h2>Artifact Inventory</h2>
            <div class="subtle">把 intermediate 和 output 里的关键产物做成结构化盘点。</div>
          </div>
        </div>
        <div class="artifact-grid" id="artifact-grid"></div>
      </section>
    </div>

    <script>
      const INITIAL_PAYLOAD = {initial_payload};

      function escapeHtml(value) {{
        return String(value || "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");
      }}

      function fmtTime(value) {{
        if (!value) return "未记录";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString("zh-CN", {{ hour12: false }});
      }}

      function fmtDuration(value) {{
        if (value === null || value === undefined) return "未记录";
        return `${{Number(value).toFixed(2)}}s`;
      }}

      function statusClass(status) {{
        if (status === "success") return "status-success";
        if (status === "running") return "status-running";
        if (status === "failed") return "status-failed";
        if (status === "partial") return "status-partial";
        return "status-pending";
      }}

      function statusLabel(status) {{
        const mapping = {{
          success: "成功",
          running: "运行中",
          failed: "失败",
          partial: "部分完成",
          pending: "待执行",
          queued: "排队中",
        }};
        return mapping[status] || status || "未知";
      }}

      function renderMetrics(payload) {{
        const state = payload.latest_state || {{}};
        const latestMetrics = payload.latest_metrics || {{}};
        const quality = latestMetrics.quality || {{}};
        const coverage = state.coverage || {{}};
        const evaluation = state.evaluation || {{}};
        const run = (state.run || payload.latest_run || {{}});
        const cards = [
          {{
            label: "运行状态",
            value: statusLabel(run.status),
            footnote: `最近来源：${{run.source || "manual"}}`,
          }},
          {{
            label: "评测分数",
            value: evaluation.score ?? "--",
            footnote: evaluation.score_label || "暂无评测",
          }},
          {{
            label: "领域覆盖",
            value: `${{coverage.active_categories || 0}} / 6`,
            footnote: `就绪领域 ${{coverage.ready_categories || 0}} 个`,
          }},
          {{
            label: "日报成稿",
            value: coverage.total_articles ?? 0,
            footnote: `AIOS memory 辅助 ${{quality.memory_assisted_article_count || 0}} 篇`,
          }},
        ];
        document.getElementById("metrics").innerHTML = cards.map((card) => `
          <article class="metric-card">
            <div class="metric-label">${{escapeHtml(card.label)}}</div>
            <div class="metric-value">${{escapeHtml(card.value)}}</div>
            <div class="metric-footnote">${{escapeHtml(card.footnote)}}</div>
          </article>
        `).join("");
      }}

      function renderHero(payload) {{
        const evaluation = ((payload.latest_state || {{}}).evaluation) || {{}};
        document.getElementById("hero-score").innerHTML = `
          <div class="score-pill">
            <strong>${{escapeHtml(evaluation.score ?? "--")}}</strong>
            <span>${{escapeHtml(evaluation.score_label || "等待最新运行")}}</span>
          </div>
        `;

        const bullets = [
          ...(evaluation.strengths || []).slice(0, 2).map((item) => `<div class="mini-item">${{escapeHtml(item)}}</div>`),
          ...(evaluation.risks || []).slice(0, 1).map((item) => `<div class="mini-item">${{escapeHtml(item)}}</div>`),
        ];
        document.getElementById("hero-bullets").innerHTML = bullets.join("") || `<div class="mini-item">当前还没有足够的数据生成系统评测。</div>`;
      }}

      function renderStages(payload) {{
        const stages = ((payload.latest_state || {{}}).stage_flow) || [];
        const target = document.getElementById("stage-list");
        if (!stages.length) {{
          target.innerHTML = `<div class="empty">还没有阶段记录。你可以先运行一轮 workflow。</div>`;
          return;
        }}
        target.innerHTML = stages.map((item) => `
          <article class="stage-card">
            <div class="stage-top">
              <div style="display:flex; align-items:center; gap:12px;">
                <span class="stage-order">${{item.order}}</span>
                <div class="stage-label">${{escapeHtml(item.label)}}</div>
              </div>
              <span class="status-chip ${{statusClass(item.status)}}">${{escapeHtml(statusLabel(item.status))}}</span>
            </div>
            <div class="stage-meta">
              <span>耗时：${{escapeHtml(fmtDuration(item.duration))}}</span>
              <span>产物：${{escapeHtml(item.output_count ?? 0)}}</span>
              <span>领域成功：${{escapeHtml((item.domain_breakdown || {{}}).success_domains ?? 0)}}</span>
            </div>
            <div class="subtle" style="margin-top:10px;">${{escapeHtml(item.summary || "暂无摘要")}}</div>
          </article>
        `).join("");
      }}

      function renderEvaluation(payload) {{
        const evaluation = ((payload.latest_state || {{}}).evaluation) || {{}};
        const blocks = [
          ["亮点", evaluation.strengths || []],
          ["风险", evaluation.risks || []],
          ["下一步", evaluation.next_actions || []],
        ];
        document.getElementById("evaluation-block").innerHTML = blocks.map(([title, items]) => `
          <section class="bullet-card">
            <strong>${{escapeHtml(title)}}</strong>
            <ul>${{items.length ? items.map((item) => `<li>${{escapeHtml(item)}}</li>`).join("") : "<li>暂无</li>"}}</ul>
          </section>
        `).join("");
      }}

      function renderDomains(payload) {{
        const domains = ((payload.latest_state || {{}}).domains) || [];
        const target = document.getElementById("domain-grid");
        if (!domains.length) {{
          target.innerHTML = `<div class="empty">还没有领域覆盖信息。</div>`;
          return;
        }}
        target.innerHTML = domains.map((domain) => `
          <article class="domain-card">
            <div class="status-chip ${{statusClass(domain.status === "ready" ? "success" : domain.status === "partial" ? "partial" : "pending")}}">${{escapeHtml(domain.status === "ready" ? "已成稿" : domain.status === "partial" ? "部分完成" : "暂无内容")}}</div>
            <h3>${{escapeHtml(domain.name)}}</h3>
            <div class="domain-desc">${{escapeHtml(domain.description)}}</div>
            <div class="domain-strip"><span style="width:${{Math.max(domain.coverage_ratio || 0, 6)}}%"></span></div>
            <div class="domain-meta">
              <span>话题 ${{domain.topic_count || 0}}</span>
              <span>文章 ${{domain.article_count || 0}}</span>
              <span>信源 ${{domain.source_count || 0}}</span>
            </div>
            <div class="title-list">
              ${{(domain.titles || []).length ? domain.titles.map((title) => `<div class="title-pill">${{escapeHtml(title)}}</div>`).join("") : `<div class="title-pill">这个领域还没有成稿。</div>`}}
            </div>
          </article>
        `).join("");
      }}

      function renderReport(payload) {{
        const report = ((payload.latest_state || {{}}).report) || {{}};
        const metrics = report.metrics || {{}};
        const titles = report.highlight_titles || [];
        const target = document.getElementById("report-grid");
        if (!report.title && !titles.length) {{
          target.innerHTML = `<div class="empty">最新运行还没有产出可展示的日报。</div>`;
          return;
        }}
        target.innerHTML = `
          <article class="report-card">
            <div class="eyebrow">Latest Brief</div>
            <div class="report-title">${{escapeHtml(report.title || "今日新闻现场")}}</div>
            <div class="subtle">${{escapeHtml(report.subtitle || "等待新的摘要文案")}}</div>
            <p class="report-overview">${{escapeHtml(report.overview || "最新一次运行已经形成日报骨架，可以继续查看完整 HTML 页面。")}}</p>
            <div class="domain-meta">
              <span>文章数 ${{metrics.total_articles || 0}}</span>
              <span>栏目数 ${{metrics.active_sections || 0}}</span>
              <span>亮点数 ${{metrics.highlight_count || 0}}</span>
            </div>
            <div class="hero-actions" style="margin-top:18px;">
              <a class="button-primary button-link" href="/api/ecosystem/reports/latest/html" target="_blank" rel="noreferrer">查看完整日报</a>
              <a class="button-secondary button-link" href="/api/ecosystem/output/report/latest" target="_blank" rel="noreferrer">查看 JSON</a>
            </div>
          </article>
          <div class="highlight-list">
            ${{titles.length ? titles.map((title) => `<article class="highlight-item">${{escapeHtml(title)}}</article>`).join("") : `<div class="empty">还没有日报亮点。</div>`}}
          </div>
        `;
      }}

      function renderRuns(payload) {{
        const runs = payload.recent_runs || [];
        const target = document.getElementById("run-list");
        if (!runs.length) {{
          target.innerHTML = `<div class="empty">还没有历史运行记录。</div>`;
          return;
        }}
        target.innerHTML = runs.map((run) => `
          <article class="run-item">
            <div style="display:flex; justify-content:space-between; gap:12px; align-items:center;">
              <strong>${{escapeHtml(statusLabel(run.status))}}</strong>
              <span class="status-chip ${{statusClass(run.status)}}">${{escapeHtml(run.mode || "serial")}}</span>
            </div>
            <div class="run-id">${{escapeHtml(run.id || "")}}</div>
            <div class="subtle" style="margin-top:10px;">${{escapeHtml(run.message || "暂无摘要")}}</div>
            <div class="domain-meta">
              <span>创建：${{escapeHtml(fmtTime(run.created_at))}}</span>
              <span>结束：${{escapeHtml(fmtTime(run.finished_at))}}</span>
            </div>
          </article>
        `).join("");
      }}

      function renderArtifacts(payload) {{
        const artifacts = ((payload.latest_state || {{}}).artifacts) || {{}};
        const groups = [...(artifacts.intermediate || []), ...(artifacts.outputs || [])];
        const target = document.getElementById("artifact-grid");
        if (!groups.length) {{
          target.innerHTML = `<div class="empty">还没有产物盘点。</div>`;
          return;
        }}
        target.innerHTML = groups.map((group) => `
          <article class="artifact-card">
            <strong>${{escapeHtml(group.label)}}</strong>
            <div class="subtle">数量：${{escapeHtml(group.count ?? 0)}}</div>
            <div class="artifact-files">
              ${{(group.sample_files || []).length ? group.sample_files.map((file) => `<div>${{escapeHtml(file)}}</div>`).join("") : "<div>暂无文件</div>"}}
            </div>
          </article>
        `).join("");
      }}

      function render(payload) {{
        renderHero(payload);
        renderMetrics(payload);
        renderStages(payload);
        renderEvaluation(payload);
        renderDomains(payload);
        renderReport(payload);
        renderRuns(payload);
        renderArtifacts(payload);
      }}

      async function loadDashboard() {{
        const response = await fetch("/api/ecosystem/dashboard", {{ cache: "no-store" }});
        if (!response.ok) throw new Error(`dashboard load failed: ${{response.status}}`);
        return await response.json();
      }}

      async function refreshDashboard() {{
        try {{
          const payload = await loadDashboard();
          render(payload);
        }} catch (error) {{
          console.error(error);
        }}
      }}

      async function triggerRun(mode) {{
        const response = await fetch("/api/ecosystem/runs", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ mode, source: "dashboard" }}),
        }});
        const payload = await response.json();
        if (!response.ok) {{
          alert(payload.detail?.reason || payload.detail || payload.reason || "触发运行失败");
          return;
        }}
        await refreshDashboard();
      }}

      document.getElementById("refresh-dashboard").addEventListener("click", refreshDashboard);
      document.getElementById("run-serial").addEventListener("click", () => triggerRun("serial"));

      render(INITIAL_PAYLOAD);
      setInterval(refreshDashboard, 30000);
    </script>
  </body>
</html>"""
