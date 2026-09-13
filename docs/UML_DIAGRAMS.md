# SoftwareBrio — Comprehensive UML Diagrams Specification

This document provides a full suite of **Unified Modeling Language (UML)** specifications for the Autonomous Lead Enrichment Pipeline. All diagrams are rendered using standard Mermaid UML syntax supported directly by GitHub markdown.

---

## Table of Contents
1. [Component Diagram (System Architecture)](#1-component-diagram-system-architecture)
2. [Class Diagram (Core Domain & Pipeline Classes)](#2-class-diagram-core-domain--pipeline-classes)
3. [Sequence Diagram (End-to-End Execution Flow)](#3-sequence-diagram-end-to-end-execution-flow)
4. [Activity Diagram (Crawler & Enrichment Logic)](#4-activity-diagram-crawler--enrichment-logic)
5. [State Machine Diagram (Lead Processing Lifecycle)](#5-state-machine-diagram-lead-processing-lifecycle)
6. [Deployment Diagram (Runtime Environment & External Sinks)](#6-deployment-diagram-runtime-environment--external-sinks)

---

## 1. Component Diagram (System Architecture)

Illustrates the modular subsystems, interfaces, and dependencies across the application.

```mermaid
graph TB
    subgraph "CLI & Entrypoint Layer"
        CLI["app.main (CLI Entrypoint)"]
        Config["app.config (Settings / Pydantic)"]
    end

    subgraph "Pipeline Orchestration Layer"
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
        RetryUtil["app.resilience.retry (with_retry / Backoff)"]
        DiskCache["app.utils.cache (DiskCache)"]
        Logger["app.utils.logging (Rich Console & File Logger)"]
    end

    subgraph "Data Model Layer"
        Models["app.models.company (CompanyIntelligence & Sub-models)"]
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

## 2. Class Diagram (Core Domain & Pipeline Classes)

Details the object-oriented structure, attributes, methods, and relationships.

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

    EnrichmentPipeline ..> RawPageBundle : produces / consumes
    EnrichmentPipeline ..> CompanyIntelligence : returns
    EnrichmentPipeline --> Crawler : delegates crawling
    EnrichmentPipeline --> LLMExtractor : delegates extraction
    EnrichmentPipeline --> ConfidenceScorer : calculates score
```

---

## 3. Sequence Diagram (End-to-End Execution Flow)

Depicts message exchanges and chronological invocations across components.

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
            Cache-->>Pipeline: Cached CompanyIntelligence
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

            opt Critical Fields Missing (e.g., funding/founding)
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
    Out-->>User: Output files saved (data/output.json)
```

---

## 4. Activity Diagram (Crawler & Enrichment Logic)

Illustrates the step-by-step branching, error-handling, and decision logic.

```mermaid
flowchart TD
    Start([Start Domain Pipeline]) --> CheckCache{In Disk Cache?}
    CheckCache -- Yes --> ReturnCache[Load Cached Intelligence]
    ReturnCache --> Finish([Yield Lead Result])

    CheckCache -- No --> Normalize[Normalize Domain & Build Root URL]
    Normalize --> FetchHome[Attempt Fast HTTP GET]
    
    FetchHome --> HomeSuccess{HTTP 200 & Non-Empty?}
    HomeSuccess -- Yes --> ParseHome[Extract Links & Meta Content]
    HomeSuccess -- No --> LaunchBrowser[Launch Headless Chromium]
    LaunchBrowser --> BrowserRender[Wait for NetworkIdle & Render DOM]
    BrowserRender --> ParseHome

    ParseHome --> RankLinks[Rank Links by Keyword Score: about, pricing, product, contact]
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

## 5. State Machine Diagram (Lead Processing Lifecycle)

Tracks the operational state transitions of a domain target during processing.

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

## 6. Deployment Diagram (Runtime Environment & External Sinks)

Shows the deployment topology, runtime processes, storage targets, and external third-party APIs.

```mermaid
graph TB
    subgraph Host["Host Environment (Developer / Docker / CI)"]
        subgraph PythonRuntime["Python 3.11+ Virtual Environment"]
            MainProc["Python Process (app.main)"]
            Engine["Enrichment Engine (Async IO / Threads)"]
            Inst["Instructor + Pydantic v2"]
            BS4["BeautifulSoup4 + Cleaners"]
        end

        subgraph HeadlessBrowserNode["Playwright Subsystem"]
            Chromium["Chromium Headless Instance"]
        end

        subgraph LocalFileSystem["Local File System"]
            InputFile[("data/input.json")]
            OutputFile[("data/output.json")]
            CSVFile[("data/output.csv")]
            CacheDir[("cache/ Directory (JSON Files)")]
            LogFile[("logs/enrichment.log")]
        end
    end

    subgraph ExternalWeb["Target Web Ecosystem"]
        Target1["Company 1 (e.g. postman.com)"]
        Target2["Company 2 (e.g. supabase.com)"]
        Target3["Company 3 (e.g. vapi.ai)"]
    end

    subgraph CloudAPIs["External SaaS & AI Providers"]
        OpenAIAPI["OpenAI API (GPT-4o-mini / GPT-4o)"]
        PerplexityAPI["Perplexity AI API (Sonar Search)"]
    end

    MainProc --> InputFile
    MainProc --> Engine
    Engine --> Chromium
    Engine --> BS4
    Engine --> Inst
    
    Engine -->|HTTP GET| Target1
    Chromium -->|Render JS / DOM| Target2
    Engine -->|HTTP GET| Target3
    
    Inst -->|REST HTTPS / TLS| OpenAIAPI
    Engine -->|Search Fallback HTTPS| PerplexityAPI

    Engine --> CacheDir
    Engine --> LogFile
    Engine --> OutputFile
    Engine --> CSVFile
```
