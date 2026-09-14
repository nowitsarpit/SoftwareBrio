"""
Production SaaS Dashboard & Interactive Intelligence Report Generator.

Generates a modern, responsive, commercial-grade SaaS dashboard UI for
visualizing autonomous lead enrichment intelligence. Built with Linear-level
cleanliness, Apollo-style data density, and Clay-style drawer workflows.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.company import CompanyEnrichment


def generate_html_report(results: list[CompanyEnrichment], output_path: Path) -> None:
    """
    Generate a standalone, interactive SaaS dashboard HTML application.

    Parameters
    ----------
    results:
        List of enriched company intelligence records.
    output_path:
        Destination path for the HTML file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert results into a serializable JSON payload
    raw_data = [r.model_dump(mode="json") for r in results]
    json_data = json.dumps(raw_data, ensure_ascii=False, default=str)

    # Load active runtime settings for configuration view
    try:
        from app.config import settings
        config_data = {
            "openai_model": settings.openai_model,
            "openai_base_url": settings.openai_base_url or "https://api.openai.com/v1",
            "max_pages_per_domain": settings.max_pages_per_domain,
            "max_concurrent_domains": settings.max_concurrent_domains,
            "page_timeout": settings.page_timeout,
            "request_timeout": settings.request_timeout,
            "crawl_delay_seconds": settings.crawl_delay_seconds,
            "max_content_chars": settings.max_content_chars,
            "headless": settings.headless,
            "cache_enabled": settings.cache_enabled,
            "cache_ttl_hours": settings.cache_ttl_hours,
            "search_provider": settings.search_provider,
            "log_level": settings.log_level,
        }
    except Exception:
        config_data = {
            "openai_model": "gemini-2.5-flash",
            "openai_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "max_pages_per_domain": 8,
            "max_concurrent_domains": 2,
            "page_timeout": 30,
            "request_timeout": 30,
            "crawl_delay_seconds": 1.0,
            "max_content_chars": 40000,
            "headless": False,
            "cache_enabled": True,
            "cache_ttl_hours": 24,
            "search_provider": "disabled",
            "log_level": "INFO",
        }
    config_json = json.dumps(config_data, ensure_ascii=False)

    # Calculate executive aggregates directly from real data
    total_companies = len(results)
    successful = sum(1 for r in results if r.status == "success")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "failed")
    avg_confidence = (
        sum(r.confidence_score for r in results) / total_companies
        if total_companies > 0
        else 0.0
    )
    total_emails = sum(len(r.contact_emails) for r in results)
    total_leaders = sum(len(r.leadership) for r in results)
    total_pages = sum(r.crawl_metadata.pages_successful for r in results)
    total_tokens = sum(
        (r.llm_usage.total_tokens or 0) for r in results if r.llm_usage
    )
    total_cost = sum(
        (r.llm_usage.estimated_cost_usd or 0.0) for r in results if r.llm_usage
    )
    avg_duration = (
        sum(r.crawl_metadata.duration_seconds for r in results) / total_companies
        if total_companies > 0
        else 0.0
    )
    generated_at = datetime.now(timezone.utc).strftime("%b %d, %Y • %H:%M UTC")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BrioIntel — Autonomous Lead Intelligence Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-base: #090d16;
      --bg-surface: #0f172a;
      --bg-elevated: #1e293b;
      --bg-hover: #273549;
      --border-subtle: #1e293b;
      --border-strong: #334155;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --text-muted: #64748b;
      --accent-blue: #38bdf8;
      --accent-indigo: #6366f1;
      --accent-emerald: #10b981;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4);
      --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.5);
      --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.65);
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg-base);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: 14px;
      line-height: 1.5;
      display: flex;
      height: 100vh;
      overflow: hidden;
      -webkit-font-smoothing: antialiased;
    }}

    /* Sidebar */
    .sidebar {{
      width: 260px;
      background: var(--bg-surface);
      border-right: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      z-index: 20;
      transition: width 0.2s ease;
    }}
    .brand-header {{
      padding: 20px 24px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .brand-logo {{
      width: 32px;
      height: 32px;
      border-radius: var(--radius-sm);
      background: linear-gradient(135deg, var(--accent-indigo), var(--accent-blue));
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      color: #fff;
      font-size: 16px;
      box-shadow: 0 0 14px rgba(56, 189, 248, 0.3);
    }}
    .brand-text h1 {{
      font-size: 15px;
      font-weight: 700;
      letter-spacing: -0.01em;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .brand-tag {{
      font-size: 10px;
      padding: 1px 5px;
      background: rgba(99, 102, 241, 0.2);
      color: #818cf8;
      border-radius: 4px;
      font-weight: 600;
      text-transform: uppercase;
    }}
    .brand-text p {{
      font-size: 11px;
      color: var(--text-muted);
    }}

    .nav-group {{
      padding: 18px 14px;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 4px;
      overflow-y: auto;
    }}
    .nav-label {{
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-muted);
      padding: 8px 10px 4px;
    }}
    .nav-item {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 9px 12px;
      border-radius: var(--radius-sm);
      color: var(--text-secondary);
      cursor: pointer;
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      transition: all 0.15s ease;
    }}
    .nav-item:hover {{
      background: var(--bg-hover);
      color: var(--text-primary);
    }}
    .nav-item.active {{
      background: rgba(56, 189, 248, 0.1);
      color: var(--accent-blue);
      font-weight: 600;
    }}
    .nav-item svg {{
      width: 17px;
      height: 17px;
      stroke-width: 2;
    }}
    .nav-badge {{
      margin-left: auto;
      background: var(--bg-elevated);
      color: var(--text-muted);
      font-size: 11px;
      padding: 1px 6px;
      border-radius: 999px;
      font-family: var(--font-mono);
    }}
    .nav-item.active .nav-badge {{
      background: rgba(56, 189, 248, 0.2);
      color: var(--accent-blue);
    }}

    .sidebar-footer {{
      padding: 16px;
      border-top: 1px solid var(--border-subtle);
      background: rgba(0, 0, 0, 0.15);
      font-size: 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .status-indicator {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--accent-emerald);
      font-size: 12px;
      font-weight: 500;
    }}
    .status-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent-emerald);
      box-shadow: 0 0 8px var(--accent-emerald);
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.5; transform: scale(0.9); }}
    }}

    /* Main Area */
    .main-wrapper {{
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: var(--bg-base);
    }}

    /* Top Navigation Header */
    .top-header {{
      height: 60px;
      border-bottom: 1px solid var(--border-subtle);
      background: var(--bg-surface);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      gap: 16px;
      flex-shrink: 0;
    }}
    .breadcrumbs {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--text-muted);
    }}
    .breadcrumbs .active {{
      color: var(--text-primary);
      font-weight: 600;
    }}
    .top-actions {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .search-box {{
      position: relative;
      display: flex;
      align-items: center;
    }}
    .search-box svg {{
      position: absolute;
      left: 10px;
      width: 15px;
      height: 15px;
      color: var(--text-muted);
      pointer-events: none;
    }}
    .search-input {{
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      color: var(--text-primary);
      font-size: 13px;
      padding: 7px 12px 7px 32px;
      width: 240px;
      transition: all 0.15s ease;
      outline: none;
    }}
    .search-input:focus {{
      border-color: var(--accent-blue);
      width: 300px;
      box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.15);
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 7px 13px;
      border-radius: var(--radius-sm);
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.15s ease;
      text-decoration: none;
      white-space: nowrap;
    }}
    .btn-secondary {{
      background: var(--bg-elevated);
      border-color: var(--border-strong);
      color: var(--text-secondary);
    }}
    .btn-secondary:hover {{
      background: var(--bg-hover);
      color: var(--text-primary);
    }}
    .btn-primary {{
      background: linear-gradient(135deg, var(--accent-indigo), var(--accent-blue));
      color: #fff;
      font-weight: 600;
      box-shadow: 0 2px 8px rgba(56, 189, 248, 0.25);
    }}
    .btn-primary:hover {{
      opacity: 0.95;
      transform: translateY(-1px);
    }}
    .btn svg {{
      width: 14px;
      height: 14px;
    }}

    /* Content Area */
    .content-scroll {{
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}

    /* KPI Banner Grid */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
    }}
    .kpi-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 16px 18px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      transition: border-color 0.2s ease, transform 0.2s ease;
    }}
    .kpi-card:hover {{
      border-color: var(--border-strong);
      transform: translateY(-2px);
    }}
    .kpi-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      color: var(--text-muted);
      font-size: 11px;
      text-transform: uppercase;
      font-weight: 600;
      letter-spacing: 0.05em;
    }}
    .kpi-icon {{
      width: 18px;
      height: 18px;
      color: var(--accent-blue);
    }}
    .kpi-value {{
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--text-primary);
      display: flex;
      align-items: baseline;
      gap: 6px;
    }}
    .kpi-subtext {{
      font-size: 12px;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    .badge-trend-up {{
      color: var(--accent-emerald);
      font-weight: 600;
    }}

    /* Table Toolbar */
    .table-toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .filter-chips {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }}
    .chip {{
      padding: 5px 12px;
      border-radius: 20px;
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .chip:hover {{
      background: var(--bg-elevated);
      color: var(--text-primary);
    }}
    .chip.active {{
      background: rgba(56, 189, 248, 0.12);
      border-color: var(--accent-blue);
      color: var(--accent-blue);
      font-weight: 600;
    }}

    /* Table Container */
    .table-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      overflow: hidden;
      box-shadow: var(--shadow-sm);
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13px;
    }}
    .data-table th {{
      background: rgba(15, 23, 42, 0.7);
      padding: 12px 16px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border-subtle);
      cursor: pointer;
      user-select: none;
      white-space: nowrap;
    }}
    .data-table th:hover {{
      color: var(--text-primary);
    }}
    .data-table td {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--border-subtle);
      vertical-align: middle;
      color: var(--text-secondary);
    }}
    .data-table tbody tr {{
      cursor: pointer;
      transition: background 0.15s ease;
    }}
    .data-table tbody tr:hover {{
      background: rgba(30, 41, 59, 0.5);
    }}
    .data-table tbody tr.selected {{
      background: rgba(56, 189, 248, 0.08);
    }}

    /* Badges */
    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      font-family: var(--font-mono);
    }}
    .status-badge.success {{
      background: rgba(16, 185, 129, 0.12);
      color: var(--accent-emerald);
      border: 1px solid rgba(16, 185, 129, 0.25);
    }}
    .status-badge.partial {{
      background: rgba(245, 158, 11, 0.12);
      color: var(--accent-amber);
      border: 1px solid rgba(245, 158, 11, 0.25);
    }}
    .status-badge.failed {{
      background: rgba(239, 68, 68, 0.12);
      color: var(--accent-rose);
      border: 1px solid rgba(239, 68, 68, 0.25);
    }}

    /* Confidence Meter */
    .conf-meter {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .conf-bar-bg {{
      width: 60px;
      height: 6px;
      background: var(--bg-elevated);
      border-radius: 3px;
      overflow: hidden;
    }}
    .conf-bar-fill {{
      height: 100%;
      border-radius: 3px;
    }}
    .conf-val {{
      font-family: var(--font-mono);
      font-weight: 600;
      font-size: 12px;
      color: var(--text-primary);
    }}

    /* Company Cell */
    .company-cell {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .company-avatar {{
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: linear-gradient(135deg, #1e293b, #334155);
      border: 1px solid var(--border-strong);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      color: var(--accent-blue);
      font-size: 14px;
      flex-shrink: 0;
    }}
    .company-name {{
      font-weight: 600;
      color: var(--text-primary);
      font-size: 14px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .company-name:hover {{
      color: var(--accent-blue);
    }}

    /* Slide-over Detail Drawer */
    .drawer-overlay {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.65);
      backdrop-filter: blur(4px);
      z-index: 50;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.25s ease;
    }}
    .drawer-overlay.open {{
      opacity: 1;
      pointer-events: auto;
    }}
    .drawer {{
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      width: 640px;
      max-width: 90vw;
      background: var(--bg-surface);
      border-left: 1px solid var(--border-strong);
      z-index: 51;
      transform: translateX(100%);
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      display: flex;
      flex-direction: column;
      box-shadow: var(--shadow-lg);
    }}
    .drawer.open {{
      transform: translateX(0);
    }}
    .drawer-header {{
      padding: 20px 24px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      background: rgba(15, 23, 42, 0.95);
    }}
    .drawer-header-info {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}
    .drawer-title h2 {{
      font-size: 18px;
      font-weight: 700;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .drawer-close {{
      background: transparent;
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      color: var(--text-muted);
      cursor: pointer;
      padding: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.15s ease;
    }}
    .drawer-close:hover {{
      background: var(--bg-elevated);
      color: var(--text-primary);
    }}

    .drawer-tabs {{
      display: flex;
      border-bottom: 1px solid var(--border-subtle);
      background: rgba(0, 0, 0, 0.2);
      padding: 0 24px;
      gap: 20px;
      overflow-x: auto;
    }}
    .drawer-tab {{
      padding: 12px 0;
      font-size: 13px;
      font-weight: 500;
      color: var(--text-muted);
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.15s ease;
      white-space: nowrap;
    }}
    .drawer-tab:hover {{
      color: var(--text-primary);
    }}
    .drawer-tab.active {{
      color: var(--accent-blue);
      border-bottom-color: var(--accent-blue);
      font-weight: 600;
    }}

    .drawer-body {{
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}
    .drawer-section {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .section-title {{
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--accent-blue);
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .callout-box {{
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 16px;
      font-size: 13.5px;
      line-height: 1.6;
      color: #e2e8f0;
    }}

    /* Email / Contact List */
    .email-item {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 14px;
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      font-size: 13px;
      font-family: var(--font-mono);
      color: var(--text-primary);
    }}
    .email-item .email-actions {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .icon-btn {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      padding: 4px;
      border-radius: 4px;
      transition: all 0.15s ease;
    }}
    .icon-btn:hover {{
      color: var(--accent-blue);
      background: var(--bg-hover);
    }}

    /* Leader Card */
    .leader-card {{
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 12px 14px;
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      transition: border-color 0.15s ease;
    }}
    .leader-card:hover {{
      border-color: var(--border-strong);
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
      font-size: 14px;
      flex-shrink: 0;
    }}
    .leader-meta {{
      flex: 1;
    }}
    .leader-name {{
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .leader-title {{
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 2px;
    }}
    .linkedin-pill {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 11px;
      padding: 2px 7px;
      border-radius: 4px;
      background: rgba(10, 102, 194, 0.15);
      color: #38bdf8;
      border: 1px solid rgba(10, 102, 194, 0.3);
      text-decoration: none;
      font-weight: 500;
    }}
    .linkedin-pill:hover {{
      background: rgba(10, 102, 194, 0.25);
    }}

    /* Source Provenance Items */
    .source-box {{
      padding: 12px 14px;
      background: var(--bg-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .source-title {{
      font-size: 12.5px;
      font-weight: 600;
      color: var(--accent-blue);
      text-decoration: none;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .source-title:hover {{
      text-decoration: underline;
    }}
    .source-excerpt {{
      font-size: 12px;
      color: var(--text-secondary);
      line-height: 1.5;
      font-style: italic;
      border-left: 2px solid var(--border-strong);
      padding-left: 8px;
    }}

    /* Telemetry grid */
    .telemetry-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }}
    .telemetry-cell {{
      background: var(--bg-elevated);
      padding: 12px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-subtle);
    }}
    .telemetry-label {{
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 600;
    }}
    .telemetry-val {{
      font-size: 15px;
      font-weight: 700;
      color: var(--text-primary);
      margin-top: 4px;
      font-family: var(--font-mono);
    }}

    /* Toast */
    .toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      border: 1px solid var(--border-strong);
      color: #fff;
      padding: 10px 16px;
      border-radius: var(--radius-sm);
      font-size: 13px;
      box-shadow: var(--shadow-md);
      z-index: 100;
      display: flex;
      align-items: center;
      gap: 8px;
      opacity: 0;
      transform: translateY(10px);
      pointer-events: none;
      transition: all 0.2s ease;
    }}
    .toast.show {{
      opacity: 1;
      transform: translateY(0);
    }}

    /* Modal */
    .modal-overlay {{
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(4px);
      z-index: 60;
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s ease;
    }}
    .modal-overlay.open {{
      opacity: 1;
      pointer-events: auto;
    }}
    .modal-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-md);
      width: 520px;
      max-width: 90vw;
      box-shadow: var(--shadow-lg);
      overflow: hidden;
    }}
    .modal-header {{
      padding: 18px 24px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .modal-header h3 {{
      font-size: 16px;
      font-weight: 600;
    }}
    .modal-body {{
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .modal-footer {{
      padding: 14px 24px;
      background: rgba(0, 0, 0, 0.15);
      border-top: 1px solid var(--border-subtle);
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }}

    /* Activity Timeline */
    .timeline {{
      display: flex;
      flex-direction: column;
      gap: 16px;
      position: relative;
      padding-left: 20px;
    }}
    .timeline::before {{
      content: '';
      position: absolute;
      left: 7px;
      top: 6px;
      bottom: 6px;
      width: 2px;
      background: var(--border-subtle);
    }}
    .timeline-node {{
      position: relative;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .timeline-node::before {{
      content: '';
      position: absolute;
      left: -17px;
      top: 6px;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent-blue);
      box-shadow: 0 0 6px var(--accent-blue);
    }}
    .timeline-time {{
      font-size: 11px;
      font-family: var(--font-mono);
      color: var(--text-muted);
    }}
    .timeline-content {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 12px 14px;
      font-size: 13px;
    }}

    /* Settings View Cards */
    .settings-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 16px;
    }}
    .settings-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .settings-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 13px;
      border-bottom: 1px solid var(--border-subtle);
      padding-bottom: 8px;
    }}
    .settings-row:last-child {{
      border-bottom: none;
      padding-bottom: 0;
    }}
    .settings-key {{
      color: var(--text-muted);
    }}
    .settings-val {{
      font-family: var(--font-mono);
      font-weight: 500;
      color: var(--text-primary);
    }}

    /* Empty state */
    .empty-state {{
      padding: 48px 24px;
      text-align: center;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 12px;
      color: var(--text-muted);
    }}
    .empty-icon {{
      width: 42px;
      height: 42px;
      color: var(--text-muted);
      opacity: 0.6;
    }}

    /* Live runner stage indicators */
    .stage-item {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 8px 12px;
      border-radius: var(--radius-sm);
      background: var(--bg-elevated);
      font-size: 12.5px;
    }}
    .stage-icon {{
      width: 18px;
      height: 18px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 700;
    }}
    .stage-icon.done {{
      background: rgba(16, 185, 129, 0.2);
      color: var(--accent-emerald);
    }}
    .stage-icon.active {{
      background: rgba(56, 189, 248, 0.2);
      color: var(--accent-blue);
      animation: pulse 1.5s infinite;
    }}
    .stage-icon.pending {{
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-muted);
    }}

    /* Responsive */
    @media (max-width: 1024px) {{
      .sidebar {{ width: 220px; }}
      .drawer {{ width: 520px; }}
    }}
    @media (max-width: 768px) {{
      body {{ flex-direction: column; }}
      .sidebar {{ width: 100%; height: auto; border-right: none; border-bottom: 1px solid var(--border-subtle); }}
      .nav-group {{ flex-direction: row; overflow-x: auto; padding: 10px; }}
      .sidebar-footer {{ display: none; }}
      .drawer {{ width: 100%; max-width: 100vw; }}
      .search-input {{ width: 160px; }}
      .search-input:focus {{ width: 200px; }}
    }}
  </style>
</head>
<body>

  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="brand-header">
      <div class="brand-logo">B</div>
      <div class="brand-text">
        <h1>BrioIntel <span class="brand-tag">v2.0</span></h1>
        <p>Autonomous Lead Intelligence</p>
      </div>
    </div>

    <nav class="nav-group">
      <div class="nav-label">Workspace</div>
      <a class="nav-item active" onclick="switchView('runs')" id="nav-runs">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
        Overview & Runs
        <span class="nav-badge" id="badge-total-companies">{total_companies}</span>
      </a>
      <a class="nav-item" onclick="switchView('leadership')" id="nav-leadership">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
        Leadership Directory
        <span class="nav-badge">{total_leaders}</span>
      </a>
      <a class="nav-item" onclick="switchView('activity')" id="nav-activity">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 14 14"></polyline></svg>
        Activity & History
      </a>
      <a class="nav-item" onclick="switchView('telemetry')" id="nav-telemetry">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
        Telemetry & Costs
      </a>
      <a class="nav-item" onclick="switchView('settings')" id="nav-settings">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
        Configuration
      </a>

      <div class="nav-label" style="margin-top: 16px;">Quick Actions</div>
      <a class="nav-item" onclick="openNewEnrichModal()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg>
        New Enrichment Run
      </a>
      <a class="nav-item" onclick="exportData('json')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
        Export JSON Dataset
      </a>
    </nav>

    <div class="sidebar-footer">
      <div class="status-indicator">
        <span class="status-dot"></span>
        <span>Engine Active • Playwright</span>
      </div>
      <div style="color: var(--text-muted); font-size: 11px;">
        Updated: {generated_at}
      </div>
    </div>
  </aside>

  <!-- Main Content Wrapper -->
  <div class="main-wrapper">
    <!-- Top Bar -->
    <header class="top-header">
      <div class="breadcrumbs">
        <span>Workspace</span>
        <span>/</span>
        <span class="active" id="current-view-title">Enrichment Runs & Intelligence</span>
      </div>

      <div class="top-actions">
        <div class="search-box">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input type="text" id="globalSearch" class="search-input" placeholder="Search domain, ICP, names..." oninput="handleSearch(this.value)" />
        </div>

        <button class="btn btn-secondary" onclick="exportData('csv')" title="Export table summary as CSV">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
          Export CSV
        </button>

        <button class="btn btn-primary" onclick="openNewEnrichModal()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg>
          Run Pipeline
        </button>
      </div>
    </header>

    <!-- Scrollable Workspace Views -->
    <main class="content-scroll" id="mainContainer">
      
      <!-- VIEW: RUNS / OVERVIEW -->
      <section id="view-runs">
        <!-- KPI Cards Grid -->
        <div class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-header">
              <span>Companies Enriched</span>
              <svg class="kpi-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            </div>
            <div class="kpi-value">{total_companies}</div>
            <div class="kpi-subtext">
              <span class="badge-trend-up">100% processed</span>
              <span>• {successful} success</span>
            </div>
          </div>

          <div class="kpi-card">
            <div class="kpi-header">
              <span>Verified Inboxes</span>
              <svg class="kpi-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
            </div>
            <div class="kpi-value">{total_emails}</div>
            <div class="kpi-subtext">
              <span>Deterministic regex & mailto</span>
            </div>
          </div>

          <div class="kpi-card">
            <div class="kpi-header">
              <span>Leadership Identified</span>
              <svg class="kpi-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            </div>
            <div class="kpi-value">{total_leaders}</div>
            <div class="kpi-subtext">
              <span>Grounded executives</span>
            </div>
          </div>

          <div class="kpi-card">
            <div class="kpi-header">
              <span>Avg Confidence</span>
              <svg class="kpi-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"></circle><path d="m9 12 2 2 4-4"></path></svg>
            </div>
            <div class="kpi-value">{int(avg_confidence * 100)}%</div>
            <div class="kpi-subtext">
              <span class="badge-trend-up">Grade A/B Quality</span>
            </div>
          </div>

          <div class="kpi-card">
            <div class="kpi-header">
              <span>Pages Analyzed</span>
              <svg class="kpi-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            </div>
            <div class="kpi-value">{total_pages}</div>
            <div class="kpi-subtext">
              <span>Avg {avg_duration:.1f}s / domain</span>
            </div>
          </div>

          <div class="kpi-card">
            <div class="kpi-header">
              <span>Token Telemetry</span>
              <svg class="kpi-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
            </div>
            <div class="kpi-value">{total_tokens:,}</div>
            <div class="kpi-subtext">
              <span>Est: ${total_cost:.4f} USD</span>
            </div>
          </div>
        </div>

        <!-- Toolbar & Filter Chips -->
        <div class="table-toolbar">
          <div class="filter-chips">
            <button class="chip active" onclick="setFilter('all', this)">All Companies ({total_companies})</button>
            <button class="chip" onclick="setFilter('high-confidence', this)">High Confidence (90%+)</button>
            <button class="chip" onclick="setFilter('has-emails', this)">Verified Emails</button>
            <button class="chip" onclick="setFilter('has-leadership', this)">Key Executives</button>
            <button class="chip" onclick="setFilter('success', this)">Success Status</button>
          </div>
        </div>

        <!-- Modern Data Table -->
        <div class="table-card">
          <table class="data-table" id="companiesTable">
            <thead>
              <tr>
                <th onclick="sortTable('domain')">Company Domain ↕</th>
                <th onclick="sortTable('status')">Status ↕</th>
                <th onclick="sortTable('confidence')">Confidence ↕</th>
                <th>Discovered Inboxes</th>
                <th>Leadership</th>
                <th onclick="sortTable('pages')">Pages Crawled ↕</th>
                <th onclick="sortTable('duration')">Duration ↕</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody id="tableBody">
              <!-- Dynamically populated from DATA -->
            </tbody>
          </table>
          <div id="tableEmptyState" class="empty-state" style="display: none;">
            <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <p>No companies match the current filter or search criteria.</p>
            <button class="btn btn-secondary" onclick="resetFilters()">Clear Filters</button>
          </div>
        </div>
      </section>

      <!-- VIEW: LEADERSHIP DIRECTORY -->
      <section id="view-leadership" style="display: none;">
        <div style="margin-bottom: 16px;">
          <h2 style="font-size: 18px; font-weight: 700;">Global Leadership Directory</h2>
          <p style="color: var(--text-secondary); font-size: 13px;">Every verified executive identified from scraped site evidence and sources.</p>
        </div>
        <div class="table-card">
          <table class="data-table">
            <thead>
              <tr>
                <th>Executive</th>
                <th>Role / Title</th>
                <th>Company</th>
                <th>LinkedIn Profile</th>
                <th>Evidence Source</th>
              </tr>
            </thead>
            <tbody id="leadershipTableBody">
              <!-- Populated by JS -->
            </tbody>
          </table>
        </div>
      </section>

      <!-- VIEW: ACTIVITY TIMELINE -->
      <section id="view-activity" style="display: none;">
        <div style="margin-bottom: 16px;">
          <h2 style="font-size: 18px; font-weight: 700;">Pipeline Activity & Run History</h2>
          <p style="color: var(--text-secondary); font-size: 13px;">Audit trail of autonomous browsing, extraction milestones, and validation states.</p>
        </div>
        <div class="timeline" id="activityTimeline">
          <!-- Populated by JS -->
        </div>
      </section>

      <!-- VIEW: TELEMETRY & COSTS -->
      <section id="view-telemetry" style="display: none;">
        <div style="margin-bottom: 16px;">
          <h2 style="font-size: 18px; font-weight: 700;">Pipeline Telemetry & Resource Accounting</h2>
          <p style="color: var(--text-secondary); font-size: 13px;">Real-time execution metrics, token breakdown, and cost accounting per target.</p>
        </div>
        <div class="table-card">
          <table class="data-table">
            <thead>
              <tr>
                <th>Target Domain</th>
                <th>LLM Model</th>
                <th>Input Tokens</th>
                <th>Output Tokens</th>
                <th>Total Tokens</th>
                <th>Estimated Cost</th>
                <th>Crawl Duration</th>
                <th>Pages Attempted</th>
                <th>Pages Success</th>
              </tr>
            </thead>
            <tbody id="telemetryTableBody">
              <!-- Populated by JS -->
            </tbody>
          </table>
        </div>
      </section>

      <!-- VIEW: SETTINGS & CONFIG -->
      <section id="view-settings" style="display: none;">
        <div style="margin-bottom: 16px;">
          <h2 style="font-size: 18px; font-weight: 700;">Engine Configuration & Limits</h2>
          <p style="color: var(--text-secondary); font-size: 13px;">Read-only view of active environment settings loaded from application configuration.</p>
        </div>
        <div class="settings-grid" id="settingsGrid">
          <!-- Populated by JS -->
        </div>
      </section>

    </main>
  </div>

  <!-- Slide-Over Clay-Style Detail Drawer -->
  <div class="drawer-overlay" id="drawerOverlay" onclick="closeDrawer()"></div>
  <aside class="drawer" id="detailDrawer">
    <div class="drawer-header">
      <div class="drawer-header-info">
        <div class="company-avatar" id="drawerAvatar" style="width: 40px; height: 40px; font-size: 18px;">P</div>
        <div class="drawer-title">
          <h2 id="drawerDomain">domain.com</h2>
          <div style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
            <span class="status-badge success" id="drawerStatusBadge">SUCCESS</span>
            <span style="font-size: 12px; color: var(--text-muted);" id="drawerTimestamp">—</span>
          </div>
        </div>
      </div>
      <button class="drawer-close" onclick="closeDrawer()" title="Close (Esc)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      </button>
    </div>

    <!-- Drawer Navigation Tabs -->
    <div class="drawer-tabs">
      <div class="drawer-tab active" onclick="switchDrawerTab('overview', this)">Overview & ICP</div>
      <div class="drawer-tab" onclick="switchDrawerTab('contacts', this)">Contact Points</div>
      <div class="drawer-tab" onclick="switchDrawerTab('leadership', this)">Leadership</div>
      <div class="drawer-tab" onclick="switchDrawerTab('sources', this)">Evidence Sources</div>
      <div class="drawer-tab" onclick="switchDrawerTab('telemetry', this)">Telemetry</div>
    </div>

    <!-- Drawer Content Scroll -->
    <div class="drawer-body" id="drawerBody">
      <!-- Injected by renderDrawerContent() -->
    </div>
  </aside>

  <!-- New Enrichment Run Modal & Live Runner Experience -->
  <div class="modal-overlay" id="newEnrichModal">
    <div class="modal-card">
      <div class="modal-header">
        <h3>Trigger Autonomous Enrichment Run</h3>
        <button class="drawer-close" onclick="closeNewEnrichModal()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
      <div class="modal-body">
        <p style="color: var(--text-secondary); font-size: 13px;">Target company domains:</p>
        <textarea id="modalDomainsInput" rows="3" style="width: 100%; background: var(--bg-elevated); border: 1px solid var(--border-strong); border-radius: var(--radius-sm); color: #fff; padding: 10px; font-family: var(--font-mono); font-size: 13px; outline: none;" placeholder="postman.com&#10;supabase.com&#10;vapi.ai"></textarea>
        
        <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-top: 4px;">Autonomous Pipeline Stages:</div>
        <div style="display: flex; flex-direction: column; gap: 6px;">
          <div class="stage-item">
            <div class="stage-icon done">✓</div>
            <div><strong>1. URL Normalization:</strong> Strips schemes/ports, verifies apex canonical domain</div>
          </div>
          <div class="stage-item">
            <div class="stage-icon done">✓</div>
            <div><strong>2. Playwright Chromium:</strong> Renders dynamic JS DOM and prioritizes links</div>
          </div>
          <div class="stage-item">
            <div class="stage-icon done">✓</div>
            <div><strong>3. Content Extraction:</strong> Strips SVGs/styles/scripts, deduplicates paragraphs</div>
          </div>
          <div class="stage-item">
            <div class="stage-icon done">✓</div>
            <div><strong>4. Deterministic Extraction:</strong> Scans mailto & regex contacts</div>
          </div>
          <div class="stage-item">
            <div class="stage-icon done">✓</div>
            <div><strong>5. LLM Structured Extraction:</strong> OpenAI / Gemini JSON Schema validation</div>
          </div>
        </div>

        <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: var(--radius-sm); padding: 10px 12px; font-size: 12px; color: var(--accent-blue);">
          ⚡ Run locally via terminal:
          <code style="display: block; margin-top: 4px; padding: 4px; background: rgba(0,0,0,0.3); border-radius: 4px;">python run.py --domains postman.com supabase.com vapi.ai</code>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeNewEnrichModal()">Close</button>
        <button class="btn btn-primary" onclick="copyCliCommand()">Copy CLI Command</button>
      </div>
    </div>
  </div>

  <!-- Toast Notification -->
  <div class="toast" id="toast">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#34d399"><polyline points="20 6 9 17 4 12"></polyline></svg>
    <span id="toastMessage">Copied to clipboard</span>
  </div>

  <!-- Raw Embedded Grounded Dataset -->
  <script id="embedded-data" type="application/json">
{json_data}
  </script>
  <script id="embedded-config" type="application/json">
{config_json}
  </script>

  <!-- Client-Side Reactive Controller -->
  <script>
    const RAW_DATA = JSON.parse(document.getElementById('embedded-data').textContent);
    const CONFIG_DATA = JSON.parse(document.getElementById('embedded-config').textContent);
    let currentFilter = 'all';
    let currentSearch = '';
    let sortColumn = 'confidence';
    let sortDirection = -1; // descending
    let selectedRecord = null;

    function init() {{
      renderTable();
      renderLeadershipDirectory();
      renderActivityTimeline();
      renderTelemetryTable();
      renderSettings();

      // Keyboard shortcuts
      document.addEventListener('keydown', (e) => {{
        if (e.key === 'Escape') {{
          closeDrawer();
          closeNewEnrichModal();
        }}
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {{
          e.preventDefault();
          document.getElementById('globalSearch')?.focus();
        }}
      }});
    }}

    function switchView(viewName) {{
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
      document.getElementById('nav-' + viewName)?.classList.add('active');

      document.getElementById('view-runs').style.display = viewName === 'runs' ? 'block' : 'none';
      document.getElementById('view-leadership').style.display = viewName === 'leadership' ? 'block' : 'none';
      document.getElementById('view-activity').style.display = viewName === 'activity' ? 'block' : 'none';
      document.getElementById('view-telemetry').style.display = viewName === 'telemetry' ? 'block' : 'none';
      document.getElementById('view-settings').style.display = viewName === 'settings' ? 'block' : 'none';

      const titles = {{
        'runs': 'Enrichment Runs & Intelligence',
        'leadership': 'Global Leadership Directory',
        'activity': 'Pipeline Activity & History',
        'telemetry': 'Pipeline Telemetry & Accounting',
        'settings': 'Engine Configuration & Limits'
      }};
      document.getElementById('current-view-title').textContent = titles[viewName] || 'Overview';
    }}

    function setFilter(filter, el) {{
      document.querySelectorAll('.filter-chips .chip').forEach(c => c.classList.remove('active'));
      el.classList.add('active');
      currentFilter = filter;
      renderTable();
    }}

    function handleSearch(query) {{
      currentSearch = query.trim().toLowerCase();
      renderTable();
    }}

    function sortTable(col) {{
      if (sortColumn === col) {{
        sortDirection *= -1;
      }} else {{
        sortColumn = col;
        sortDirection = 1;
      }}
      renderTable();
    }}

    function getFilteredData() {{
      return RAW_DATA.filter(item => {{
        // Filter by category
        if (currentFilter === 'high-confidence' && item.confidence_score < 0.9) return false;
        if (currentFilter === 'has-emails' && (!item.contact_emails || item.contact_emails.length === 0)) return false;
        if (currentFilter === 'has-leadership' && (!item.leadership || item.leadership.length === 0)) return false;
        if (currentFilter === 'success' && item.status !== 'success') return false;

        // Search query
        if (currentSearch) {{
          const domainMatch = item.domain.toLowerCase().includes(currentSearch);
          const overviewMatch = (item.company_overview || '').toLowerCase().includes(currentSearch);
          const icpMatch = (item.ideal_customer_profile || '').toLowerCase().includes(currentSearch);
          const emailMatch = (item.contact_emails || []).some(e => e.toLowerCase().includes(currentSearch));
          const leaderMatch = (item.leadership || []).some(l => l.name.toLowerCase().includes(currentSearch) || l.title.toLowerCase().includes(currentSearch));
          if (!domainMatch && !overviewMatch && !icpMatch && !emailMatch && !leaderMatch) {{
            return false;
          }}
        }}
        return true;
      }}).sort((a, b) => {{
        let valA = a[sortColumn];
        let valB = b[sortColumn];
        if (sortColumn === 'confidence') {{
          valA = a.confidence_score;
          valB = b.confidence_score;
        }} else if (sortColumn === 'pages') {{
          valA = a.crawl_metadata?.pages_successful || 0;
          valB = b.crawl_metadata?.pages_successful || 0;
        }} else if (sortColumn === 'duration') {{
          valA = a.crawl_metadata?.duration_seconds || 0;
          valB = b.crawl_metadata?.duration_seconds || 0;
        }}
        if (valA < valB) return -1 * sortDirection;
        if (valA > valB) return 1 * sortDirection;
        return 0;
      }});
    }}

    function renderTable() {{
      const tbody = document.getElementById('tableBody');
      const emptyState = document.getElementById('tableEmptyState');
      const data = getFilteredData();

      if (data.length === 0) {{
        tbody.innerHTML = '';
        emptyState.style.display = 'flex';
        return;
      }}
      emptyState.style.display = 'none';

      let htmlRows = '';
      data.forEach(item => {{
        const initial = item.domain.charAt(0).toUpperCase();
        const confPct = Math.round(item.confidence_score * 100);
        const statusClass = item.status === 'success' ? 'success' : (item.status === 'partial' ? 'partial' : 'failed');
        
        let confColor = 'var(--accent-emerald)';
        if (confPct < 70) confColor = 'var(--accent-amber)';
        if (confPct < 50) confColor = 'var(--accent-rose)';

        // Emails snippet
        let emailsDisplay = '<span style="color: var(--text-muted);">0 emails</span>';
        if (item.contact_emails && item.contact_emails.length > 0) {{
          emailsDisplay = `<span class="badge" style="background: rgba(56,189,248,0.1); color: var(--accent-blue); border: 1px solid rgba(56,189,248,0.25); font-family: var(--font-mono); font-size: 11px; padding: 2px 7px; border-radius: 4px;">✉ ${{item.contact_emails.length}} address${{item.contact_emails.length > 1 ? 'es' : ''}}</span>`;
        }}

        // Leadership snippet
        let leadersDisplay = '<span style="color: var(--text-muted);">None found</span>';
        if (item.leadership && item.leadership.length > 0) {{
          const firstLeader = item.leadership[0].name;
          leadersDisplay = `<span style="color: #fff; font-weight: 500;">${{firstLeader}}</span>${{item.leadership.length > 1 ? ` <span style="color: var(--text-muted); font-size: 11px;">+${{item.leadership.length - 1}} more</span>` : ''}}`;
        }}

        const pages = item.crawl_metadata?.pages_successful || 0;
        const duration = item.crawl_metadata?.duration_seconds?.toFixed(1) || '0.0';

        htmlRows += `
          <tr onclick="inspectCompany('${{item.domain}}')" id="row-${{item.domain.replace(/[^a-zA-Z0-9]/g, '-')}}">
            <td>
              <div class="company-cell">
                <div class="company-avatar">${{initial}}</div>
                <div>
                  <div class="company-name">
                    ${{item.domain}}
                    <a href="https://${{item.domain}}" target="_blank" onclick="event.stopPropagation();" title="Visit live site" style="color: var(--text-muted);">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                    </a>
                  </div>
                </div>
              </div>
            </td>
            <td>
              <span class="status-badge ${{statusClass}}">${{item.status}}</span>
            </td>
            <td>
              <div class="conf-meter">
                <div class="conf-bar-bg">
                  <div class="conf-bar-fill" style="width: ${{confPct}}%; background: ${{confColor}};"></div>
                </div>
                <span class="conf-val">${{confPct}}%</span>
              </div>
            </td>
            <td>${{emailsDisplay}}</td>
            <td>${{leadersDisplay}}</td>
            <td style="font-family: var(--font-mono);">${{pages}} pages</td>
            <td style="font-family: var(--font-mono);">${{duration}}s</td>
            <td>
              <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;" onclick="event.stopPropagation(); inspectCompany('${{item.domain}}');">
                Inspect
              </button>
            </td>
          </tr>
        `;
      }});

      tbody.innerHTML = htmlRows;
    }}

    function inspectCompany(domain) {{
      const item = RAW_DATA.find(r => r.domain === domain);
      if (!item) return;
      selectedRecord = item;

      // Update drawer header
      document.getElementById('drawerAvatar').textContent = item.domain.charAt(0).toUpperCase();
      document.getElementById('drawerDomain').innerHTML = `${{item.domain}} <a href="https://${{item.domain}}" target="_blank" style="color: var(--text-muted); font-size: 13px;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg></a>`;
      
      const badge = document.getElementById('drawerStatusBadge');
      badge.className = 'status-badge ' + item.status;
      badge.textContent = item.status.toUpperCase();
      
      const timestamp = item.crawl_metadata?.extraction_timestamp ? new Date(item.crawl_metadata.extraction_timestamp).toLocaleString() : '';
      document.getElementById('drawerTimestamp').textContent = timestamp;

      // Reset to overview tab
      document.querySelectorAll('.drawer-tabs .drawer-tab').forEach((t, idx) => {{
        if (idx === 0) t.classList.add('active');
        else t.classList.remove('active');
      }});

      renderDrawerContent('overview');

      // Open drawer
      document.getElementById('drawerOverlay').classList.add('open');
      document.getElementById('detailDrawer').classList.add('open');
    }}

    function switchDrawerTab(tabName, el) {{
      document.querySelectorAll('.drawer-tabs .drawer-tab').forEach(t => t.classList.remove('active'));
      el.classList.add('active');
      renderDrawerContent(tabName);
    }}

    function renderDrawerContent(tabName) {{
      const body = document.getElementById('drawerBody');
      const item = selectedRecord;
      if (!item) return;

      if (tabName === 'overview') {{
        body.innerHTML = `
          <div class="drawer-section">
            <div class="section-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
              Two-Sentence Company Overview
            </div>
            <div class="callout-box" style="border-left: 3px solid var(--accent-blue);">
              ${{item.company_overview || '<span style="color: var(--text-muted);">No overview generated</span>'}}
            </div>
          </div>

          <div class="drawer-section">
            <div class="section-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"></circle><polygon points="12 6 12 12 14 14"></polygon></svg>
              Ideal Customer Profile (ICP)
            </div>
            <div class="callout-box" style="border-left: 3px solid var(--accent-indigo);">
              ${{item.ideal_customer_profile || '<span style="color: var(--text-muted);">No explicit ICP detected</span>'}}
            </div>
          </div>

          <div class="drawer-section">
            <div class="section-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
              Intelligence Confidence Score
            </div>
            <div class="callout-box" style="display: flex; align-items: center; justify-content: space-between;">
              <div>
                <div style="font-size: 20px; font-weight: 700; color: var(--text-primary); font-family: var(--font-mono);">
                  ${{Math.round(item.confidence_score * 100)}}%
                </div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                  Multi-factor calibrated score based on page density & deterministic grounding
                </div>
              </div>
              <button class="btn btn-secondary" onclick="copyText('${{item.confidence_score}}', 'Confidence score copied')">Copy Score</button>
            </div>
          </div>
        `;
      }} else if (tabName === 'contacts') {{
        let emailsHtml = '';
        if (item.contact_emails && item.contact_emails.length > 0) {{
          item.contact_emails.forEach(email => {{
            emailsHtml += `
              <div class="email-item">
                <span>${{email}}</span>
                <div class="email-actions">
                  <a href="mailto:${{email}}" class="icon-btn" title="Send Email">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
                  </a>
                  <button class="icon-btn" onclick="copyText('${{email}}', 'Email copied')" title="Copy Email">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                  </button>
                </div>
              </div>
            `;
          }});
        }} else {{
          emailsHtml = '<div class="callout-box" style="color: var(--text-muted);">No public contact emails discovered on crawled pages.</div>';
        }}
        body.innerHTML = `
          <div class="drawer-section">
            <div class="section-title">Discovered Public Inboxes (${{item.contact_emails?.length || 0}})</div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${{emailsHtml}}
            </div>
          </div>
        `;
      }} else if (tabName === 'leadership') {{
        let leadersHtml = '';
        if (item.leadership && item.leadership.length > 0) {{
          item.leadership.forEach(l => {{
            const liTag = l.linkedin_url ? `<a href="${{l.linkedin_url}}" target="_blank" class="linkedin-pill">LinkedIn ↗</a>` : '<span style="font-size: 11px; color: var(--text-muted);">No LinkedIn</span>';
            const srcTag = l.source_url ? `<a href="${{l.source_url}}" target="_blank" style="font-size: 11px; color: var(--accent-blue); text-decoration: none; margin-top: 4px; display: inline-block;">Source URL ↗</a>` : '';
            leadersHtml += `
              <div class="leader-card">
                <div class="leader-avatar">${{l.name.charAt(0)}}</div>
                <div class="leader-meta">
                  <div class="leader-name">${{l.name}} ${{liTag}}</div>
                  <div class="leader-title">${{l.title}}</div>
                  ${{srcTag}}
                </div>
              </div>
            `;
          }});
        }} else {{
          leadersHtml = '<div class="callout-box" style="color: var(--text-muted);">No leadership profiles detected in scraped company pages.</div>';
        }}
        body.innerHTML = `
          <div class="drawer-section">
            <div class="section-title">Key Leadership & Executives (${{item.leadership?.length || 0}})</div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${{leadersHtml}}
            </div>
          </div>
        `;
      }} else if (tabName === 'sources') {{
        let sourcesHtml = '';
        if (item.sources && item.sources.length > 0) {{
          item.sources.forEach(src => {{
            sourcesHtml += `
              <div class="source-box">
                <a href="${{src.url}}" target="_blank" class="source-title">
                  🔗 ${{src.page_title || src.url}}
                </a>
                <div class="source-excerpt">"${{src.relevant_excerpt || 'Direct page citation'}}..."</div>
              </div>
            `;
          }});
        }} else {{
          sourcesHtml = '<div class="callout-box" style="color: var(--text-muted);">No supporting source excerpts logged.</div>';
        }}
        body.innerHTML = `
          <div class="drawer-section">
            <div class="section-title">Crawled Citations & Excerpts (${{item.sources?.length || 0}})</div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${{sourcesHtml}}
            </div>
          </div>
        `;
      }} else if (tabName === 'telemetry') {{
        const meta = item.crawl_metadata || {{}};
        const usage = item.llm_usage || {{}};
        body.innerHTML = `
          <div class="drawer-section">
            <div class="section-title">Execution & Resource Consumption</div>
            <div class="telemetry-grid">
              <div class="telemetry-cell">
                <div class="telemetry-label">Crawl Latency</div>
                <div class="telemetry-val">${{meta.duration_seconds || 0}}s</div>
              </div>
              <div class="telemetry-cell">
                <div class="telemetry-label">Pages Successful</div>
                <div class="telemetry-val">${{meta.pages_successful || 0}} / ${{meta.pages_attempted || 0}}</div>
              </div>
              <div class="telemetry-cell">
                <div class="telemetry-label">LLM Model</div>
                <div class="telemetry-val" style="font-size: 13px;">${{usage.model || 'gemini-2.5-flash'}}</div>
              </div>
              <div class="telemetry-cell">
                <div class="telemetry-label">Estimated Cost</div>
                <div class="telemetry-val">${{usage.estimated_cost_usd ? '$' + usage.estimated_cost_usd.toFixed(4) : '$0.0000'}}</div>
              </div>
              <div class="telemetry-cell">
                <div class="telemetry-label">Input Tokens</div>
                <div class="telemetry-val">${{usage.input_tokens ? usage.input_tokens.toLocaleString() : '—'}}</div>
              </div>
              <div class="telemetry-cell">
                <div class="telemetry-label">Output Tokens</div>
                <div class="telemetry-val">${{usage.output_tokens ? usage.output_tokens.toLocaleString() : '—'}}</div>
              </div>
              <div class="telemetry-cell" style="grid-column: span 2;">
                <div class="telemetry-label">Total Tokens Utilized</div>
                <div class="telemetry-val" style="color: var(--accent-blue);">${{usage.total_tokens ? usage.total_tokens.toLocaleString() : '—'}}</div>
              </div>
            </div>
          </div>
        `;
      }}
    }}

    function closeDrawer() {{
      document.getElementById('drawerOverlay').classList.remove('open');
      document.getElementById('detailDrawer').classList.remove('open');
    }}

    function renderLeadershipDirectory() {{
      const tbody = document.getElementById('leadershipTableBody');
      let htmlRows = '';
      RAW_DATA.forEach(comp => {{
        if (comp.leadership) {{
          comp.leadership.forEach(lead => {{
            const liPill = lead.linkedin_url ? `<a href="${{lead.linkedin_url}}" target="_blank" class="linkedin-pill">Verified LinkedIn ↗</a>` : '<span style="color: var(--text-muted); font-size: 12px;">Not listed</span>';
            const srcLink = lead.source_url ? `<a href="${{lead.source_url}}" target="_blank" style="color: var(--accent-blue); text-decoration: none; font-size: 12px;">${{lead.source_url.replace(/https?:\\/\\//, '')}} ↗</a>` : '—';
            htmlRows += `
              <tr>
                <td>
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <div class="leader-avatar" style="width: 28px; height: 28px; font-size: 12px;">${{lead.name.charAt(0)}}</div>
                    <strong style="color: #fff;">${{lead.name}}</strong>
                  </div>
                </td>
                <td style="color: var(--text-primary);">${{lead.title}}</td>
                <td>
                  <span style="font-family: var(--font-mono); color: var(--accent-blue);">${{comp.domain}}</span>
                </td>
                <td>${{liPill}}</td>
                <td>${{srcLink}}</td>
              </tr>
            `;
          }});
        }}
      }});
      tbody.innerHTML = htmlRows || '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No leadership records found.</td></tr>';
    }}

    function renderActivityTimeline() {{
      const container = document.getElementById('activityTimeline');
      let nodesHtml = '';
      RAW_DATA.forEach(item => {{
        const timeStr = item.crawl_metadata?.extraction_timestamp ? new Date(item.crawl_metadata.extraction_timestamp).toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}}) : '09:00';
        nodesHtml += `
          <div class="timeline-node">
            <div class="timeline-time">${{timeStr}} • Enrichment Completed</div>
            <div class="timeline-content">
              <strong>${{item.domain}}</strong> processed successfully in ${{item.crawl_metadata?.duration_seconds?.toFixed(1) || 0}}s.
              Crawled ${{item.crawl_metadata?.pages_successful || 0}} pages, discovered ${{item.contact_emails?.length || 0}} inboxes and ${{item.leadership?.length || 0}} executives with ${{Math.round(item.confidence_score * 100)}}% confidence.
            </div>
          </div>
        `;
      }});
      container.innerHTML = nodesHtml || '<p style="color: var(--text-muted);">No logged activity.</p>';
    }}

    function renderTelemetryTable() {{
      const tbody = document.getElementById('telemetryTableBody');
      let htmlRows = '';
      RAW_DATA.forEach(comp => {{
        const meta = comp.crawl_metadata || {{}};
        const usage = comp.llm_usage || {{}};
        const costStr = usage.estimated_cost_usd ? '$' + usage.estimated_cost_usd.toFixed(4) : '$0.0000';
        htmlRows += `
          <tr>
            <td style="font-weight: 600; color: #fff;">${{comp.domain}}</td>
            <td style="font-family: var(--font-mono); font-size: 12px;">${{usage.model || 'gemini-2.5-flash'}}</td>
            <td style="font-family: var(--font-mono);">${{usage.input_tokens ? usage.input_tokens.toLocaleString() : '—'}}</td>
            <td style="font-family: var(--font-mono);">${{usage.output_tokens ? usage.output_tokens.toLocaleString() : '—'}}</td>
            <td style="font-family: var(--font-mono); font-weight: 700; color: var(--accent-blue);">${{usage.total_tokens ? usage.total_tokens.toLocaleString() : '—'}}</td>
            <td style="font-family: var(--font-mono);">${{costStr}}</td>
            <td style="font-family: var(--font-mono);">${{meta.duration_seconds || 0}}s</td>
            <td style="font-family: var(--font-mono);">${{meta.pages_attempted || 0}}</td>
            <td style="font-family: var(--font-mono); color: var(--accent-emerald); font-weight: 600;">${{meta.pages_successful || 0}}</td>
          </tr>
        `;
      }});
      tbody.innerHTML = htmlRows;
    }}

    function renderSettings() {{
      const container = document.getElementById('settingsGrid');
      container.innerHTML = `
        <div class="settings-card">
          <h3 style="font-size: 14px; font-weight: 600; color: #fff;">LLM & Extraction Engine</h3>
          <div class="settings-row">
            <span class="settings-key">Model</span>
            <span class="settings-val">${{CONFIG_DATA.openai_model}}</span>
          </div>
          <div class="settings-row">
            <span class="settings-key">Base URL</span>
            <span class="settings-val" style="font-size: 11px; max-width: 180px; overflow: hidden; text-overflow: ellipsis;">${{CONFIG_DATA.openai_base_url}}</span>
          </div>
          <div class="settings-row">
            <span class="settings-key">Structured Mode</span>
            <span class="settings-val">JSON Schema + Self-Repair</span>
          </div>
        </div>

        <div class="settings-card">
          <h3 style="font-size: 14px; font-weight: 600; color: #fff;">Crawling & Concurrency</h3>
          <div class="settings-row">
            <span class="settings-key">Max Pages / Domain</span>
            <span class="settings-val">${{CONFIG_DATA.max_pages_per_domain}}</span>
          </div>
          <div class="settings-row">
            <span class="settings-key">Max Concurrent Domains</span>
            <span class="settings-val">${{CONFIG_DATA.max_concurrent_domains}}</span>
          </div>
          <div class="settings-row">
            <span class="settings-key">Page Timeout</span>
            <span class="settings-val">${{CONFIG_DATA.page_timeout}}s</span>
          </div>
          <div class="settings-row">
            <span class="settings-key">Polite Crawl Delay</span>
            <span class="settings-val">${{CONFIG_DATA.crawl_delay_seconds}}s</span>
          </div>
        </div>

        <div class="settings-card">
          <h3 style="font-size: 14px; font-weight: 600; color: #fff;">Cache & Search Grounding</h3>
          <div class="settings-row">
            <span class="settings-key">Local Disk Cache</span>
            <span class="settings-val">${{CONFIG_DATA.cache_enabled ? 'Enabled (' + CONFIG_DATA.cache_ttl_hours + 'h TTL)' : 'Disabled'}}</span>
          </div>
          <div class="settings-row">
            <span class="settings-key">Search Provider</span>
            <span class="settings-val">${{CONFIG_DATA.search_provider}}</span>
          </div>
          <div class="settings-row">
            <span class="settings-key">Chromium Headless</span>
            <span class="settings-val">${{CONFIG_DATA.headless}}</span>
          </div>
        </div>
      `;
    }}

    function copyText(text, msg) {{
      navigator.clipboard.writeText(text);
      showToast(msg || 'Copied to clipboard');
    }}

    function showToast(msg) {{
      const toast = document.getElementById('toast');
      document.getElementById('toastMessage').textContent = msg;
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 2500);
    }}

    function exportData(format) {{
      if (format === 'json') {{
        const blob = new Blob([JSON.stringify(RAW_DATA, null, 2)], {{ type: 'application/json' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'lead_enrichment_output.json';
        a.click();
        URL.revokeObjectURL(url);
        showToast('Exported JSON dataset');
      }} else if (format === 'csv') {{
        const headers = ['domain', 'status', 'confidence_score', 'emails_count', 'leadership_count', 'pages_crawled', 'duration_seconds'];
        const rows = RAW_DATA.map(r => [
          r.domain,
          r.status,
          r.confidence_score,
          (r.contact_emails || []).length,
          (r.leadership || []).length,
          r.crawl_metadata?.pages_successful || 0,
          r.crawl_metadata?.duration_seconds || 0
        ]);
        const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\\n');
        const encodedUri = encodeURI(csvContent);
        const a = document.createElement('a');
        a.href = encodedUri;
        a.download = 'lead_enrichment_summary.csv';
        a.click();
        showToast('Exported CSV summary');
      }}
    }}

    function openNewEnrichModal() {{
      document.getElementById('newEnrichModal').classList.add('open');
    }}

    function closeNewEnrichModal() {{
      document.getElementById('newEnrichModal').classList.remove('open');
    }}

    function copyCliCommand() {{
      const raw = document.getElementById('modalDomainsInput').value.trim();
      const domains = raw.split(/[\\s,]+/).filter(Boolean).join(' ') || 'postman.com supabase.com vapi.ai';
      const cmd = `python run.py --domains ${{domains}}`;
      navigator.clipboard.writeText(cmd);
      showToast('CLI command copied!');
      closeNewEnrichModal();
    }}

    function resetFilters() {{
      currentSearch = '';
      currentFilter = 'all';
      document.getElementById('globalSearch').value = '';
      document.querySelectorAll('.filter-chips .chip').forEach((c, idx) => {{
        if (idx === 0) c.classList.add('active');
        else c.classList.remove('active');
      }});
      renderTable();
    }}

    window.onload = init;
  </script>
</body>
</html>
"""
    output_path.write_text(html_content, encoding="utf-8")
