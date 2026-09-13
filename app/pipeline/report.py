"""
Interactive HTML report generator for lead enrichment results.

Produces a standalone, modern, responsive HTML dashboard that visualises
enriched leads, leadership profiles, confidence scores, source citations,
and pipeline cost/token telemetry.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.company import CompanyEnrichment


def generate_html_report(results: list[CompanyEnrichment], output_path: Path) -> None:
    """
    Generate a standalone HTML dashboard report from enrichment results.

    Parameters
    ----------
    results:
        List of enriched company records.
    output_path:
        Destination file path for the .html file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_companies = len(results)
    successful = sum(1 for r in results if r.status == "success")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "failed")
    avg_confidence = (
        sum(r.confidence_score for r in results) / total_companies
        if total_companies > 0
        else 0.0
    )
    total_tokens = sum(
        (r.llm_usage.total_tokens or 0) for r in results if r.llm_usage
    )
    total_cost = sum(
        (r.llm_usage.estimated_cost_usd or 0.0) for r in results if r.llm_usage
    )
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    cards_html = []
    for comp in results:
        status_color = (
            "#10b981" if comp.status == "success" else ("#f59e0b" if comp.status == "partial" else "#ef4444")
        )
        conf_pct = int(comp.confidence_score * 100)
        conf_grade = "A" if conf_pct >= 85 else ("B" if conf_pct >= 70 else ("C" if conf_pct >= 50 else "D"))

        # Emails HTML
        emails_html = ""
        if comp.contact_emails:
            for email in comp.contact_emails:
                safe_email = html.escape(email)
                emails_html += f'<span class="badge badge-email"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>{safe_email}</span> '
        else:
            emails_html = '<span class="text-muted">No public emails discovered</span>'

        # Leadership HTML
        leadership_html = ""
        if comp.leadership:
            for leader in comp.leadership:
                safe_name = html.escape(leader.name)
                safe_title = html.escape(leader.title)
                linkedin_tag = ""
                if leader.linkedin_url:
                    safe_url = html.escape(leader.linkedin_url)
                    linkedin_tag = f'<a href="{safe_url}" target="_blank" class="linkedin-link"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 10.9v8.37H9.2V10.9H6.46M7.83 6.6a1.64 1.64 0 0 0-1.66 1.66 1.65 1.65 0 0 0 1.66 1.65 1.64 1.64 0 0 0 1.65-1.65c0-.92-.74-1.66-1.65-1.66Z"/></svg>LinkedIn</a>'
                leadership_html += f'''
                <div class="leadership-card">
                    <div class="leader-avatar">{safe_name[:1]}</div>
                    <div class="leader-info">
                        <div class="leader-name">{safe_name} {linkedin_tag}</div>
                        <div class="leader-title">{safe_title}</div>
                    </div>
                </div>
                '''
        else:
            leadership_html = '<span class="text-muted">No leadership members identified</span>'

        # Sources HTML
        sources_html = ""
        if comp.sources:
            for src in comp.sources:
                safe_url = html.escape(src.url)
                safe_title = html.escape(src.page_title or src.url)
                safe_excerpt = html.escape(src.relevant_excerpt)
                sources_html += f'''
                <div class="source-item">
                    <a href="{safe_url}" target="_blank" class="source-link">🔗 {safe_title}</a>
                    <div class="source-excerpt">{safe_excerpt}</div>
                </div>
                '''
        else:
            sources_html = '<span class="text-muted">No source excerpts recorded</span>'

        # Telemetry stats
        pages_crawled = comp.crawl_metadata.pages_successful
        duration = comp.crawl_metadata.duration_seconds
        tokens_used = comp.llm_usage.total_tokens if comp.llm_usage and comp.llm_usage.total_tokens else 0
        cost_est = (
            f"${comp.llm_usage.estimated_cost_usd:.4f}"
            if comp.llm_usage and comp.llm_usage.estimated_cost_usd
            else "$0.0000"
        )

        cards_html.append(f'''
        <div class="company-card" data-domain="{html.escape(comp.domain)}">
            <div class="card-header">
                <div class="domain-title">
                    <h2>{html.escape(comp.domain)}</h2>
                    <span class="badge" style="background-color: {status_color}22; color: {status_color}; border: 1px solid {status_color};">
                        {comp.status.upper()}
                    </span>
                </div>
                <div class="confidence-gauge">
                    <div class="conf-badge conf-grade-{conf_grade}">
                        <span class="conf-grade">{conf_grade}</span>
                        <span class="conf-pct">{conf_pct}%</span>
                    </div>
                </div>
            </div>

            <div class="card-body">
                <div class="section-block">
                    <div class="section-title">Company Overview</div>
                    <p class="section-content">{html.escape(comp.company_overview or "No overview extracted.")}</p>
                </div>

                <div class="section-block">
                    <div class="section-title">Ideal Customer Profile (ICP)</div>
                    <p class="section-content">{html.escape(comp.ideal_customer_profile or "Not identified.")}</p>
                </div>

                <div class="section-block">
                    <div class="section-title">Discovered Contact Points</div>
                    <div class="badges-container">{emails_html}</div>
                </div>

                <div class="section-block">
                    <div class="section-title">Identified Leadership Team</div>
                    <div class="leadership-grid">{leadership_html}</div>
                </div>

                <details class="sources-details">
                    <summary class="sources-summary">Verified Sources & Evidence ({len(comp.sources)} pages)</summary>
                    <div class="sources-list">{sources_html}</div>
                </details>
            </div>

            <div class="card-footer">
                <div class="metric-chip">📄 Pages: <strong>{pages_crawled}</strong></div>
                <div class="metric-chip">⏱️ Duration: <strong>{duration}s</strong></div>
                <div class="metric-chip">🧠 Tokens: <strong>{tokens_used:,}</strong></div>
                <div class="metric-chip">💵 Est. Cost: <strong>{cost_est}</strong></div>
            </div>
        </div>
        ''')

    all_cards = "\n".join(cards_html)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autonomous Lead Enrichment Dashboard | SoftwareBrio</title>
    <style>
        :root {{
            --bg-body: #0b0f19;
            --bg-card: #131b2e;
            --bg-card-header: #1a243c;
            --border-color: #24304f;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-blue: #38bdf8;
            --accent-indigo: #6366f1;
            --badge-green: #10b981;
            --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-body);
            color: var(--text-primary);
            font-family: var(--font-sans);
            padding: 32px 24px;
            line-height: 1.5;
        }}
        .container {{ max-width: 1280px; margin: 0 auto; }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 32px;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header-title h1 {{
            font-size: 1.875rem;
            font-weight: 700;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header-title p {{ color: var(--text-secondary); font-size: 0.875rem; margin-top: 4px; }}
        .header-meta {{ text-align: right; color: var(--text-muted); font-size: 0.8125rem; }}

        /* KPI Banner */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}
        .kpi-label {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); }}
        .kpi-value {{ font-size: 1.75rem; font-weight: 700; margin-top: 6px; color: var(--text-primary); }}

        /* Company Cards */
        .cards-container {{ display: flex; flex-direction: column; gap: 24px; }}
        .company-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
            transition: border-color 0.2s ease;
        }}
        .company-card:hover {{ border-color: var(--accent-blue); }}
        .card-header {{
            background: var(--bg-card-header);
            padding: 18px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
        }}
        .domain-title {{ display: flex; align-items: center; gap: 14px; }}
        .domain-title h2 {{ font-size: 1.35rem; font-weight: 600; }}
        .badge {{
            font-size: 0.75rem;
            padding: 4px 10px;
            border-radius: 9999px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .badge-email {{ background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }}

        /* Confidence Gauge */
        .conf-badge {{
            display: flex;
            align-items: baseline;
            gap: 4px;
            padding: 6px 14px;
            border-radius: 8px;
            font-weight: 700;
        }}
        .conf-grade-A {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid #10b981; }}
        .conf-grade-B {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid #3b82f6; }}
        .conf-grade-C {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid #f59e0b; }}
        .conf-grade-D {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid #ef4444; }}
        .conf-grade {{ font-size: 1.15rem; }}
        .conf-pct {{ font-size: 0.8125rem; font-weight: 500; opacity: 0.85; }}

        .card-body {{ padding: 24px; display: flex; flex-direction: column; gap: 20px; }}
        .section-title {{ font-size: 0.8125rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent-blue); margin-bottom: 6px; }}
        .section-content {{ color: #cbd5e1; font-size: 0.9375rem; line-height: 1.6; }}

        /* Leadership */
        .leadership-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; margin-top: 8px; }}
        .leadership-card {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 12px 14px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .leader-avatar {{
            width: 38px;
            height: 38px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--accent-indigo), var(--accent-blue));
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            color: #fff;
            flex-shrink: 0;
        }}
        .leader-name {{ font-size: 0.9375rem; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
        .leader-title {{ font-size: 0.8125rem; color: var(--text-secondary); margin-top: 2px; }}
        .linkedin-link {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 0.75rem;
            color: #0077b5;
            text-decoration: none;
            background: rgba(0, 119, 181, 0.12);
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .linkedin-link:hover {{ text-decoration: underline; }}

        /* Sources */
        .sources-details {{
            border-top: 1px solid var(--border-color);
            padding-top: 14px;
            margin-top: 4px;
        }}
        .sources-summary {{
            cursor: pointer;
            font-size: 0.8125rem;
            color: var(--text-secondary);
            font-weight: 600;
        }}
        .sources-summary:hover {{ color: var(--accent-blue); }}
        .sources-list {{ margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }}
        .source-item {{
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 10px 14px;
        }}
        .source-link {{ color: var(--accent-blue); text-decoration: none; font-size: 0.875rem; font-weight: 500; }}
        .source-link:hover {{ text-decoration: underline; }}
        .source-excerpt {{ color: var(--text-secondary); font-size: 0.8125rem; margin-top: 4px; font-style: italic; }}

        /* Card Footer */
        .card-footer {{
            background: rgba(0, 0, 0, 0.25);
            border-top: 1px solid var(--border-color);
            padding: 12px 24px;
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            font-size: 0.8125rem;
            color: var(--text-secondary);
        }}
        .metric-chip {{ display: flex; align-items: center; gap: 4px; }}
        .metric-chip strong {{ color: var(--text-primary); }}

        /* Footer */
        footer {{
            margin-top: 48px;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8125rem;
            border-top: 1px solid var(--border-color);
            padding-top: 24px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-title">
                <h1>Autonomous Lead Intelligence Dashboard</h1>
                <p>AI Engineer Take-Home Evaluation | SoftwareBrio</p>
            </div>
            <div class="header-meta">
                Generated: <strong>{generated_at}</strong><br>
                Model: <strong>OpenAI Structured Extraction</strong>
            </div>
        </header>

        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Total Leads</div>
                <div class="kpi-value">{total_companies}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Successful</div>
                <div class="kpi-value" style="color: #10b981;">{successful}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Avg Confidence</div>
                <div class="kpi-value" style="color: #38bdf8;">{int(avg_confidence * 100)}%</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Total LLM Tokens</div>
                <div class="kpi-value">{total_tokens:,}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Total API Cost</div>
                <div class="kpi-value">${total_cost:.4f}</div>
            </div>
        </div>

        <div class="cards-container">
            {all_cards}
        </div>

        <footer>
            SoftwareBrio Autonomous Lead Enrichment Pipeline &bull; Production Architecture &bull; All Evidence Traceable to Public URLs
        </footer>
    </div>
</body>
</html>
"""

    with output_path.open("w", encoding="utf-8") as fh:
        fh.write(html_content)


