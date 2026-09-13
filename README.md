# Autonomous Lead Enrichment Pipeline

> **Production-grade, modular Python pipeline that autonomously crawls company websites, extracts structured business intelligence using an LLM, validates data with strict Pydantic schemas, and outputs clean lead intelligence.** Built for the AI Engineer Intern take-home assignment with zero hardcoded company rules.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-e92063.svg?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-45ba4b.svg?logo=playwright&logoColor=white)](https://playwright.dev/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991.svg?logo=openai&logoColor=white)](https://platform.openai.com/)
[![Tests](https://img.shields.io/badge/Tests-94%20Passing-brightgreen.svg)]()
[![Code Style](https://img.shields.io/badge/Code%20Style-Black%20%2F%20Ruff-000000.svg)]()

---

## Table of Contents

1. [Assignment Requirements & Fulfillment Matrix](#1-assignment-requirements--fulfillment-matrix)
2. [System Architecture & UML Diagrams](#2-system-architecture--uml-diagrams)
   - [2.1 Component Diagram](#21-component-diagram-system-architecture)
   - [2.2 Class Diagram](#22-class-diagram-domain-model--pipeline)
   - [2.3 Sequence Diagram](#23-sequence-diagram-end-to-end-flow)
   - [2.4 Activity Diagram](#24-activity-diagram-crawling--extraction-logic)
   - [2.5 State Machine Diagram](#25-state-machine-diagram-lead-processing-lifecycle)
   - [2.6 Deployment Diagram](#26-deployment-diagram-runtime--infrastructure)
3. [Key Engineering Highlights](#3-key-engineering-highlights)
4. [Project Structure](#4-project-structure)
5. [Installation & Setup](#5-installation--setup)
6. [CLI Usage](#6-cli-usage)
7. [Input & Output Specification](#7-input--output-specification)
8. [Confidence Scoring & Lead Grading](#8-confidence-scoring--lead-grading)
9. [Testing & Quality Assurance](#9-testing--quality-assurance)
10. [Loom Demo Script (2–3 Minute Guide)](#10-loom-demo-script-23-minute-guide)
11. [Responsible Crawling & Safety Policies](#11-responsible-crawling--safety-policies)

---

## 1. Assignment Requirements & Fulfillment Matrix

| Assignment Requirement | Implementation Detail | Status |
|---|---|:---:|
| **Autonomous Domain Navigation** | Accepts domain list (`postman.com`, `supabase.com`, `vapi.ai`, or arbitrary domains), resolves root URLs, and auto-discovers relevant paths. | ✅ **Satisfied** |
| **Hybrid Crawling Architecture** | Fast `httpx` HTTP retrieval with automatic fallback to headless **Playwright Chromium** for JavaScript SPAs / Cloudflare bot blocks. | ✅ **Satisfied** |
| **Heuristic Page Prioritization** | Scores and ranks internal links (e.g. `/about`, `/pricing`, `/products`, `/contact`) to fetch high-value pages first within a bounded budget. | ✅ **Satisfied** |
| **Content Cleaning & Deduplication** | Strips scripts, SVGs, styles, navbars, footers, cookie banners, and removes cross-page duplicate paragraphs using exact hashing. | ✅ **Satisfied** |
| **Deterministic Contact Extraction** | Scans raw HTML/text using RFC-compliant regex for emails, phone numbers, and social links (LinkedIn, X/Twitter, GitHub, YouTube). | ✅ **Satisfied** |
| **Structured LLM Extraction** | OpenAI `gpt-4o-mini` / `gpt-4o` using Pydantic schema validation with automatic JSON repair loop for schema self-correction. | ✅ **Satisfied** |
| **External Search Grounding** | Optional Perplexity AI integration (`sonar` search) to enrich missing funding, founders, or headquarters with cited web evidence. | ✅ **Satisfied** |
| **Calibrated Confidence Scoring** | Multi-factor objective score (0.0 to 1.0) based on page coverage, deterministic evidence, and field completeness with letter grades (A–D). | ✅ **Satisfied** |
| **JSON & CSV Output** | Formats final structured intelligence to `data/output.json` with metadata, evidence links, and execution metrics. | ✅ **Satisfied** |
| **Comprehensive Test Suite** | **94 unit tests** covering URL normalization, discovery, regex parsing, content dedup, models, and pipeline logic. | ✅ **Satisfied** |

---

## 2. System Architecture & UML Diagrams

### 2.1 Component Diagram (System Architecture)

```mermaid
graph TB
    subgraph "CLI & Config Layer"
        CLI["app.main (CLI Interface)"]
        Config["app.config (Pydantic Settings)"]
    end

    subgraph "Pipeline Orchestration"
        Pipeline["app.pipeline.enrichment (EnrichmentPipeline)"]
        Scorer["app.pipeline.confidence (ConfidenceScorer)"]
        OutWriter["app.pipeline.output (OutputWriter)"]
    end

    subgraph "Web Discovery & Crawling Subsystem"
        Crawler["app.crawler.crawler (Crawler)"]
        Discovery["app.crawler.discovery (PageDiscovery)"]
        URLUtils["app.crawler.url_utils (URL Normalizer / Filters)"]
        BrowserMgr["app.browser.browser_manager (PlaywrightBrowserManager)"]
    end

    subgraph "Extraction & Parsing Subsystem"
        ContentExt["app.extraction.content (ContentExtractor)"]
        ContactExt["app.extraction.contacts (ContactExtractor)"]
        LinkExt["app.extraction.links (LinkExtractor)"]
    end

    subgraph "Intelligence & LLM Subsystem"
        LLMExt["app.llm.extractor (LLMExtractor / Instructor)"]
        SearchEng["app.llm.search (PerplexitySearchEngine)"]
    end

    subgraph "Resilience & Utility Subsystem"
        RetryUtil["app.resilience.retry (Exponential Backoff)"]
        DiskCache["app.utils.cache (DiskCache)"]
        Logger["app.utils.logging (Rich Console Logger)"]
    end

    subgraph "Data Models"
        Models["app.models.company (CompanyIntelligence & Submodels)"]
    end

    CLI --> Config
    CLI --> Pipeline
    Pipeline --> Crawler
    Pipeline --> LLMExt
    Pipeline --> Scorer
    Pipeline --> OutWriter
    Crawler --> BrowserMgr
    Crawler --> Discovery
    Crawler --> URLUtils
    Crawler --> DiskCache
    Crawler --> RetryUtil
    Pipeline --> ContentExt
    Pipeline --> ContactExt
    Discovery --> LinkExt
    LLMExt --> Models
    LLMExt --> SearchEng
    Pipeline --> Logger
    OutWriter --> Models
```

---

### 2.2 Class Diagram (Domain Model & Pipeline)

```mermaid
classDiagram
    direction TB

    class CompanyIntelligence {
        +str company_name
        +str domain
        +str website_url
        +str summary
        +str what_they_do
        +str category
        +List~str~ tags
        +List~str~ target_audience
        +List~str~ value_propositions
        +List~str~ products_services
        +str pricing_model
        +FundingInfo funding
        +FoundingInfo founding
        +List~KeyPerson~ key_people
        +ContactInfo contacts
        +LeadScore lead_scoring
        +List~PageEvidence~ evidence_pages
        +float confidence_score
        +str extraction_timestamp
        +dict to_clean_dict()
    }

    class FundingInfo {
        +str stage
        +str total_raised
        +str last_round_date
        +List~str~ known_investors
        +str source_evidence
    }

    class FoundingInfo {
        +int year
        +List~str~ founders
        +str headquarters
    }

    class KeyPerson {
        +str name
        +str title
        +str linkedin_url
    }

    class ContactInfo {
        +List~str~ emails
        +List~str~ phone_numbers
        +dict social_links
    }

    class LeadScore {
        +int score
        +str grade
        +List~str~ positive_signals
        +List~str~ risk_signals
        +str reasoning
    }

    class PageEvidence {
        +str url
        +str page_type
        +str retrieved_at
        +int content_length
    }

    class RawPageBundle {
        +str domain
        +str homepage_url
        +List~CrawledPage~ pages
        +List~str~ discovered_emails
        +List~str~ discovered_phones
        +dict social_links
        +int total_text_length
        +str combined_evidence()
    }

    class EnrichmentPipeline {
        -Settings settings
        -Crawler crawler
        -LLMExtractor extractor
        -PerplexitySearchEngine search_engine
        -ConfidenceScorer scorer
        +enrich_domain(domain: str) CompanyIntelligence
        +enrich_all(domains: List~str~) List~CompanyIntelligence~
        -_fallback_search(domain: str, raw_bundle: RawPageBundle) str
    }

    class Crawler {
        -Settings settings
        -PlaywrightBrowserManager browser_mgr
        -DiskCache cache
        +crawl_domain(domain: str) RawPageBundle
        +fetch_page(url: str, use_browser: bool) str
        -_fetch_http(url: str) str
        -_fetch_browser(url: str) str
    }

    class LLMExtractor {
        -Settings settings
        -OpenAI client
        +extract(domain: str, evidence: str) CompanyIntelligence
        -_repair_json(raw_text: str, err: Exception) CompanyIntelligence
    }

    class ConfidenceScorer {
        +calculate(data: CompanyIntelligence, evidence: RawPageBundle) float
    }

    CompanyIntelligence "1" *-- "1" FundingInfo
    CompanyIntelligence "1" *-- "1" FoundingInfo
    CompanyIntelligence "1" *-- "*" KeyPerson
    CompanyIntelligence "1" *-- "1" ContactInfo
    CompanyIntelligence "1" *-- "1" LeadScore
    CompanyIntelligence "1" *-- "*" PageEvidence

    EnrichmentPipeline ..> RawPageBundle : creates & transforms
    EnrichmentPipeline ..> CompanyIntelligence : produces
    EnrichmentPipeline --> Crawler : orchestrates
    EnrichmentPipeline --> LLMExtractor : invokes
    EnrichmentPipeline --> ConfidenceScorer : calculates score
```

---

### 2.3 Sequence Diagram (End-to-End Flow)

```mermaid
sequenceDiagram
    autonumber
    actor User as User / CLI
    participant Pipeline as EnrichmentPipeline
    participant Cache as DiskCache
    participant Crawler as Crawler Subsystem
    participant Browser as Playwright Browser
    participant Extractor as Content/Contact Extractor
    participant LLM as LLM Extractor (OpenAI)
    participant Search as Perplexity Fallback
    participant Scorer as ConfidenceScorer
    participant Out as OutputWriter

    User->>Pipeline: run(domains=["postman.com", ...])
    loop For Each Domain
        Pipeline->>Cache: check_cached_enrichment(domain)
        alt Cache Hit
            Cache-->>Pipeline: Return Cached CompanyIntelligence
        else Cache Miss
            Pipeline->>Crawler: crawl_domain(domain)
            Crawler->>Crawler: Fetch Homepage (HTTP GET)
            alt HTTP 403 / JS Challenge / Empty DOM
                Crawler->>Browser: fetch_page_rendered(url)
                Browser-->>Crawler: Rendered HTML DOM
            end
            Crawler->>Extractor: discover_links(html)
            Extractor-->>Crawler: candidate_urls (prioritized)
            
            loop Crawl Top Pages (e.g. /pricing, /about)
                Crawler->>Crawler: Fetch page content
                Crawler->>Extractor: clean_and_extract_text(html)
                Extractor-->>Crawler: Clean Markdown & Contacts
            end
            Crawler-->>Pipeline: RawPageBundle(pages, contacts)

            Pipeline->>LLM: extract(domain, raw_evidence)
            activate LLM
            LLM->>LLM: Call OpenAI with Pydantic Schema
            alt Parsing Error / Schema Mismatch
                LLM->>LLM: Self-Correction Prompt Loop
            end
            LLM-->>Pipeline: CompanyIntelligence
            deactivate LLM

            opt Missing Critical Fields (e.g., funding/founding)
                Pipeline->>Search: search_missing_facts(domain, query)
                Search-->>Pipeline: Grounded Evidence Snippets
                Pipeline->>LLM: merge_evidence_update(company, snippets)
                LLM-->>Pipeline: Refined CompanyIntelligence
            end

            Pipeline->>Scorer: calculate(intelligence, raw_bundle)
            Scorer-->>Pipeline: confidence_score (0.0 - 1.0)
            Pipeline->>Cache: save(domain, intelligence)
        end
    end

    Pipeline->>Out: write_json(output_path, results)
    Pipeline->>Out: write_csv(output_path, results)
    Out-->>User: Outputs saved to data/output.json
```

---

### 2.4 Activity Diagram (Crawling & Extraction Logic)

```mermaid
flowchart TD
    Start([Start Domain Pipeline]) --> CheckCache{In Disk Cache?}
    CheckCache -- Yes --> ReturnCache[Load Cached Intelligence]
    ReturnCache --> Finish([Yield Lead Result])

    CheckCache -- No --> Normalize[Normalize Domain & Build Root URL]
    Normalize --> FetchHome[Attempt Fast HTTP GET]
    
    FetchHome --> HomeSuccess{HTTP 200 & Valid HTML?}
    HomeSuccess -- Yes --> ParseHome[Extract Links & Meta Content]
    HomeSuccess -- No --> LaunchBrowser[Launch Headless Chromium]
    LaunchBrowser --> BrowserRender[Wait for NetworkIdle & Render DOM]
    BrowserRender --> ParseHome

    ParseHome --> RankLinks[Rank Links by Keyword Weight: about, pricing, product, contact]
    RankLinks --> SelectTop[Select Top N Candidate URLs]
    
    subgraph CrawlLoop [Prioritized Crawl Loop]
        SelectTop --> CrawlNext[Fetch Next Prioritized URL]
        CrawlNext --> ExtractText[Extract Clean Text + Deduplicate Paragraphs]
        ExtractText --> ExtractContacts[Regex Extract: Emails, Phones, Socials]
        ExtractContacts --> MorePages{More URLs in Queue?}
        MorePages -- Yes --> CrawlNext
        MorePages -- No --> AssembleBundle[Assemble RawPageBundle]
    end

    AssembleBundle --> CallLLM[Execute LLM Extraction with Pydantic Constraints]
    CallLLM --> ValidateSchema{Pydantic Validation Passed?}
    ValidateSchema -- No --> RetryLLM[Retry LLM with Error Context]
    RetryLLM --> ValidateSchema
    ValidateSchema -- Yes --> CheckCoverage{Key Info Present?}

    CheckCoverage -- Missing Crucial Info --> PerplexitySearch[Query Web Search Fallback]
    PerplexitySearch --> EnrichMissing[Patch Missing Fields via LLM]
    EnrichMissing --> ComputeScore
    CheckCoverage -- Sufficient Info --> ComputeScore[Compute Weighted Confidence Score]

    ComputeScore --> GradeLead[Calculate Lead Score & Grade: A/B/C/D]
    GradeLead --> SaveDiskCache[Save to Disk Cache]
    SaveDiskCache --> Finish
```

---

### 2.5 State Machine Diagram (Lead Processing Lifecycle)

```mermaid
stateDiagram-v2
    [*] --> Discovered: Domain Queued

    Discovered --> CrawlingHomepage: Start Crawl
    
    state CrawlingHomepage {
        [*] --> FastHTTP
        FastHTTP --> HeadlessBrowser: On 403 / Cloudflare / Blank
        HeadlessBrowser --> HomepageSuccess: Rendered HTML
        FastHTTP --> HomepageSuccess: Valid 200 OK
    }

    CrawlingHomepage --> PageDiscovery: Extract Internal Links
    PageDiscovery --> CrawlingSubpages: Priority Queue Built
    
    state CrawlingSubpages {
        [*] --> FetchingSubpage
        FetchingSubpage --> ContentExtraction: HTML Received
        ContentExtraction --> Deduplication: Clean Boilerplate
        Deduplication --> RegexContacts: Harvest Emails/Socials
        RegexContacts --> FetchingSubpage: Next URL
        RegexContacts --> EvidenceComplete: Queue Exhausted
    }

    CrawlingSubpages --> LLMExtracting: Bundle Assembled
    
    state LLMExtracting {
        [*] --> PromptEngineered
        PromptEngineered --> StructuredOutput: OpenAI API
        StructuredOutput --> SchemaValidated: Pydantic Pass
        StructuredOutput --> SelfRepair: Validation Error
        SelfRepair --> SchemaValidated: Fixed
    }

    LLMExtracting --> SearchGrounding: Incomplete Fields (Funding/Year)
    SearchGrounding --> Scoring: External Facts Integrated
    LLMExtracting --> Scoring: Sufficient Evidence

    Scoring --> Completed: Confidence & Grade Calculated
    Completed --> Cached: Persisted to Cache
    Cached --> [*]: Emitted to Output

    CrawlingHomepage --> Failed: Unreachable / DNS Error
    CrawlingSubpages --> Failed: All Pages Timed Out
    Failed --> [*]: Failure Recorded in Output
```

---

### 2.6 Deployment Diagram (Runtime & Infrastructure)

```mermaid
graph TB
    subgraph Host["Host Machine (Windows / Linux / Docker)"]
        subgraph PythonRuntime["Python 3.11+ Runtime"]
            MainProc["CLI Runner (app.main)"]
            Engine["Enrichment Engine (Async IO / ThreadPool)"]
            Inst["Pydantic v2 + OpenAI SDK"]
            BS4["BeautifulSoup4 + Parsers"]
        end

        subgraph HeadlessBrowserNode["Playwright Subsystem"]
            Chromium["Chromium Headless Instance"]
        end

        subgraph LocalFileSystem["Local File System"]
            InputFile[("data/input.json")]
            OutputFile[("data/output.json")]
            CSVFile[("data/output.csv")]
            CacheDir[("cache/ (SHA-256 JSON Responses)")]
            LogFile[("logs/enrichment.log")]
        end
    end

    subgraph ExternalWeb["Target Company Websites"]
        Target1["postman.com"]
        Target2["supabase.com"]
        Target3["vapi.ai"]
        TargetN["Arbitrary Domain..."]
    end

    subgraph CloudAPIs["External SaaS & AI Providers"]
        OpenAIAPI["OpenAI API (GPT-4o-mini / GPT-4o)"]
        PerplexityAPI["Perplexity AI API (Sonar Search Grounding)"]
    end

    MainProc --> InputFile
    MainProc --> Engine
    Engine --> Chromium
    Engine --> BS4
    Engine --> Inst
    
    Engine -->|Fast HTTP GET| Target1
    Chromium -->|JS DOM Rendering| Target2
    Engine -->|Fast HTTP GET| Target3
    Engine -->|Fast HTTP GET| TargetN
    
    Inst -->|Structured JSON / TLS| OpenAIAPI
    Engine -->|Search Grounding / TLS| PerplexityAPI

    Engine --> CacheDir
    Engine --> LogFile
    Engine --> OutputFile
    Engine --> CSVFile
```

---

## 3. Key Engineering Highlights

### 1. Zero Hardcoded Company Heuristics
The pipeline contains **zero domain-specific hardcoded parsing rules** for Postman, Supabase, or Vapi. Everything is driven by generalized heuristic scorers and LLM semantic extraction.

### 2. Dual-Engine Crawler (HTTP + Playwright Headless Browser)
- Starts with lightweight, fast `httpx` GET requests (~200ms).
- Automatically escalates to **Playwright Chromium** when encountering status `403 Forbidden`, Cloudflare challenges, SPA root divs `<div id="root"></div>`, or low-content DOMs (< 500 characters).

### 3. Heuristic Link Scoring & Prioritization
Discovered links are prioritized using semantic path keywords:
- **Priority Tier 1 (Score: 85–100)**: `/about`, `/company`, `/team`, `/pricing`, `/plans`
- **Priority Tier 2 (Score: 60–80)**: `/product`, `/features`, `/solutions`, `/contact`
- **Ignored / Filtered**: Auth pages (`/login`, `/signup`), media assets (`.png`, `.pdf`), localized duplicates (`/fr/`, `/es/`).

### 4. Cross-Page Paragraph Deduplication
Common boilerplates (cookie notices, header navigation, footers, terms) that repeat across multiple pages are hashed and deduplicated, keeping LLM prompts concise and focused on unique content.

### 5. Deterministic Regex Contact Harvesting
Emails, phone numbers, and social links (LinkedIn, X, GitHub, YouTube) are extracted deterministically from HTML and text prior to the LLM step, preventing LLM hallucination of contact info.

### 6. Pydantic v2 Schema Enforcement & Self-Correction
Outputs are strictly validated using Pydantic v2. If the LLM generates an invalid payload, the error feedback is automatically reflected back into a self-repair prompt loop (up to 3 retries).

### 7. Optional Search Grounding (Perplexity API)
When critical corporate fields (e.g. founding year, funding stage, total raised) cannot be found on public website pages, the pipeline can query Perplexity's Sonar search engine for verified citations.

---

## 4. Project Structure

```
d:\SoftwareBrio\
├── app/
│   ├── config.py                  # Pydantic-settings environment configuration
│   ├── main.py                    # CLI entrypoint (Rich terminal formatting)
│   ├── browser/
│   │   └── browser_manager.py     # Playwright Chromium manager (lifecycle & stealth)
│   ├── crawler/
│   │   ├── crawler.py             # Dual HTTP/Browser crawler with retries & cache
│   │   ├── discovery.py           # Internal link discovery and priority ranking
│   │   └── url_utils.py           # Domain validation, normalization, and path filtering
│   ├── extraction/
│   │   ├── contacts.py            # Regex extractor for emails, phones, social links
│   │   ├── content.py             # BeautifulSoup text cleaner & paragraph dedup
│   │   └── links.py               # Anchor tag extractor & internal link resolver
│   ├── llm/
│   │   ├── extractor.py           # OpenAI structured output extraction & JSON repair
│   │   └── search.py              # Perplexity API web search fallback client
│   ├── models/
│   │   └── company.py             # Pydantic v2 schemas for all intelligence entities
│   ├── pipeline/
│   │   ├── confidence.py          # Calibrated confidence & lead score calculator
│   │   ├── enrichment.py          # Master domain orchestration pipeline
│   │   └── output.py              # Multi-format output writer (JSON, CSV, console)
│   ├── resilience/
│   │   └── retry.py               # Exponential backoff decorator with jitter
│   └── utils/
│       ├── cache.py               # SHA-256 persistent disk response cache
│       ├── hashing.py             # Text fingerprinting utilities
│       └── logging.py             # Rich console logger with file rotation
├── data/
│   ├── input.json                 # Input company domain list
│   └── output.json                # Generated lead intelligence output
├── tests/
│   ├── conftest.py                # Pytest fixtures and mock responses
│   ├── test_contacts.py           # Tests for regex email/phone/social extraction
│   ├── test_content.py            # Tests for HTML cleaning & paragraph dedup
│   ├── test_discovery.py          # Tests for heuristic link scoring & discovery
│   ├── test_models.py             # Tests for Pydantic schema validation & serialization
│   ├── test_pipeline.py           # Tests for pipeline orchestration & mock LLM calls
│   └── test_url_utils.py          # Tests for domain parsing and URL filtering
├── .env.example                   # Environment variable template
├── .gitignore                     # Git ignore rules for secrets, cache, and venv
├── pyproject.toml                 # Project packaging and tool configuration
├── README.md                      # Consolidated project documentation and UML models
└── requirements.txt               # Pinned Python package dependencies
```

---

## 5. Installation & Setup

### Prerequisites
- **Python 3.11+** installed
- **Git** installed

### 1. Clone the Repository
```powershell
git clone https://github.com/nowitsarpit/SoftwareBrio.git
cd SoftwareBrio
```

### 2. Create and Activate Virtual Environment
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Install Playwright Browsers
```powershell
playwright install chromium
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env` and insert your OpenAI API key:
```powershell
Copy-Item .env.example .env
```

Edit `.env`:
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Optional: Perplexity API for web search grounding
PERPLEXITY_API_KEY=pplx-...

# Pipeline Settings
MAX_PAGES_PER_DOMAIN=5
CRAWL_DELAY_SECONDS=1.0
USE_BROWSER_FALLBACK=true
ENABLE_CACHE=true
```

---

## 6. CLI Usage

### Basic Run (Default `data/input.json`)
```powershell
python -m app.main
```

### Specify Input & Output Paths
```powershell
python -m app.main --input data/input.json --output data/output.json --format both
```

### Enrich a Single Domain Ad-Hoc
```powershell
python -m app.main --domain postman.com
```

### Available CLI Flags
| Flag | Description | Default |
|---|---|---|
| `--input`, `-i` | Path to JSON input file containing domain list | `data/input.json` |
| `--output`, `-o` | Destination path for output JSON/CSV | `data/output.json` |
| `--domain`, `-d` | Process a single domain directly from the command line | `None` |
| `--format`, `-f` | Output format: `json`, `csv`, or `both` | `both` |
| `--concurrency`, `-c` | Number of concurrent domains to enrich | `1` |
| `--no-cache` | Bypass local disk cache and force live crawling | `False` |
| `--model`, `-m` | Override OpenAI model (`gpt-4o-mini`, `gpt-4o`) | `gpt-4o-mini` |
| `--verbose`, `-v` | Enable detailed debug logging | `False` |

---

## 7. Input & Output Specification

### Input Format (`data/input.json`)
```json
[
  "postman.com",
  "supabase.com",
  "vapi.ai"
]
```

### Output Format Sample (`data/output.json`)
```json
[
  {
    "company_name": "Supabase",
    "domain": "supabase.com",
    "website_url": "https://supabase.com",
    "summary": "Supabase is an open source Firebase alternative providing a Postgres database, authentication, instant APIs, edge functions, and real-time subscriptions.",
    "what_they_do": "Builds scalable backend infrastructure tools centered around Postgres for software developers and enterprise teams.",
    "category": "Developer Tools & Cloud Infrastructure",
    "tags": ["Postgres", "Database", "Authentication", "Open Source", "Serverless"],
    "target_audience": ["Full-Stack Developers", "Software Engineers", "Startups", "Enterprise Engineering Teams"],
    "value_propositions": [
      "Dedicated PostgreSQL database without manual configuration",
      "Auto-generated instant REST and GraphQL APIs",
      "Built-in user authentication with Row-Level Security"
    ],
    "products_services": ["Postgres Database", "Auth", "Storage", "Edge Functions", "Realtime"],
    "pricing_model": "Freemium with Usage-Based and Enterprise Tiers",
    "funding": {
      "stage": "Series B",
      "total_raised": "$116M",
      "last_round_date": "2022",
      "known_investors": ["Y Combinator", "Coatue", "Felicis Ventures"],
      "source_evidence": "Extracted from verified company press and about pages."
    },
    "founding": {
      "year": 2020,
      "founders": ["Paul Copplestone", "Ant Wilson"],
      "headquarters": "Singapore / Remote"
    },
    "key_people": [
      {
        "name": "Paul Copplestone",
        "title": "Co-founder & CEO",
        "linkedin_url": "https://linkedin.com/in/paulcopplestone"
      }
    ],
    "contacts": {
      "emails": ["support@supabase.com", "press@supabase.com"],
      "phone_numbers": [],
      "social_links": {
        "twitter": "https://twitter.com/supabase",
        "github": "https://github.com/supabase",
        "linkedin": "https://linkedin.com/company/supabase"
      }
    },
    "lead_scoring": {
      "score": 92,
      "grade": "A",
      "positive_signals": ["Clear pricing tiers", "High technical audience match", "Active hiring and enterprise plan"],
      "risk_signals": [],
      "reasoning": "High value B2B developer tool with self-serve model and transparent pricing."
    },
    "evidence_pages": [
      {
        "url": "https://supabase.com",
        "page_type": "homepage",
        "retrieved_at": "2026-09-13T10:30:00Z",
        "content_length": 14200
      },
      {
        "url": "https://supabase.com/pricing",
        "page_type": "pricing",
        "retrieved_at": "2026-09-13T10:30:03Z",
        "content_length": 8900
      }
    ],
    "confidence_score": 0.94,
    "extraction_timestamp": "2026-09-13T10:30:08Z"
  }
]
```

---

## 8. Confidence Scoring & Lead Grading

The confidence score ($0.0 - 1.0$) is calculated via an objective, weighted multi-factor rubric:

$$\text{Confidence Score} = \sum (\text{Weight}_i \times \text{Factor}_i)$$

| Factor | Weight | Evaluation Criteria |
|---|:---:|---|
| **Page Coverage** | 25% | Ratio of target pages successfully crawled (homepage, about, pricing, products). |
| **Evidence Volume** | 20% | Quality and length of cleaned text content retrieved (> 5,000 characters). |
| **Deterministic Contacts** | 20% | Verification of discovered public emails, telephone numbers, and social links. |
| **Field Completeness** | 20% | Absence of null / unknown fields across key people, funding, and ICP attributes. |
| **Source Grounding** | 15% | Percentage of factual statements linked directly to crawled evidence pages. |

### Lead Scoring Grades
- **Grade A (Score 85–100)**: Excellent fit — High intent, verified contact info, strong technical adoption signals.
- **Grade B (Score 70–84)**: Good fit — Complete overview, transparent pricing, minor missing leadership data.
- **Grade C (Score 50–69)**: Moderate fit — Incomplete information, ambiguous pricing, low contact discovery.
- **Grade D (Score < 50)**: Poor fit / Inconclusive — Low content extracted, protected/blocked domain.

---

## 9. Testing & Quality Assurance

The test suite contains **94 unit tests** executed using `pytest`. Tests run in isolated environments using mocked HTTP responses and mock LLM calls.

### Run All Tests
```powershell
pytest tests/ -v
```

### Test Coverage Breakdown
- `tests/test_url_utils.py`: Domain sanitization, path normalization, deduplication, and exclusion rules.
- `tests/test_discovery.py`: Anchor link parsing, internal URL scoring, and priority queue ordering.
- `tests/test_content.py`: HTML stripping, boilerplate filtering, and cross-page paragraph deduplication.
- `tests/test_contacts.py`: Regex extraction for complex email formats, telephone variations, and social profile handles.
- `tests/test_models.py`: Pydantic validation checks, field constraints, defaults, and JSON serialization.
- `tests/test_pipeline.py`: Full end-to-end pipeline orchestration, caching mechanisms, and error recovery.

---

## 10. Loom Demo Script (2–3 Minute Guide)

Use this structured outline for recording your assignment submission video:

```
[0:00 - 0:30] Introduction & Problem
- State name and project purpose: Autonomous Lead Enrichment Pipeline.
- Highlight the core challenge: Extracting grounded B2B company intelligence without 
  hardcoded scrapers or brittle heuristics.

[0:30 - 1:15] Architecture Walkthrough
- Point to the Mermaid Component & Sequence diagrams in README.md.
- Explain the Hybrid Crawler: Fast HTTP with automatic Playwright Chromium fallback.
- Explain Heuristic Page Prioritization: Smart scoring of /about, /pricing, and /team links.
- Highlight Deterministic Contact Extraction: Regex harvesting before the LLM step.

[1:15 - 2:00] Live Execution & Terminal Demo
- Run the pipeline: python -m app.main --input data/input.json
- Show the Rich console output displaying live domain progress, discovered links, 
  and token cost tracking.
- Open data/output.json: Show structured fields (ICP, pricing model, key people, 
  confidence scores, and source evidence URLs).

[2:00 - 2:30] Resilience, Testing & Wrap-Up
- Run pytest tests/ -v (demonstrate 94/94 passing tests in < 1 second).
- Mention safety features: Polite crawl delays, local disk caching, exponential retries.
- Conclude: Production-grade, maintainable architecture ready for deployment.
```

---

## 11. Responsible Crawling & Safety Policies

To ensure responsible, legal, and ethical interaction with target websites:

1. **Polite Crawl Delays**: Enforces a configurable delay between consecutive requests to the same host (`CRAWL_DELAY_SECONDS=1.0`).
2. **Strict Concurrency Limits**: Limits simultaneous requests per host to prevent denial-of-service issues.
3. **No Auth/CAPTCHA Bypass**: Does not attempt to crack CAPTCHAs, bypass paywalls, or circumvent authentication guards.
4. **No External Traversal**: Restricts crawling strictly to the target company's primary domain and subdomains.
5. **No JavaScript Execution of Scraped Payloads**: Safely sanitizes all scraped text and disables script execution.
6. **Local Disk Caching**: Caches raw HTTP/browser responses using SHA-256 keys to avoid redundant bandwidth consumption.