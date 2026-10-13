# Zenvora AI Website & Answer Engine Optimization (AEO) Audit Copilot

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![Framework](https://img.shields.io/badge/FastAPI-0.110%2B-green)
![License](https://img.shields.io/badge/license-MIT-blue)
![Precision](https://img.shields.io/badge/benchmark--precision-100%25-brightgreen)

Zenvora AI is a production-minded web application and AI copilot designed to audit public websites for technical SEO compliance and produce evidence-backed **Answer Engine Optimization (AEO)** recommendations.

Unlike traditional SEO tools that rely solely on keyword metrics, Zenvora evaluates web pages for generative AI search engines (Perplexity, ChatGPT Search, Google Gemini), optimizing for entity clarity, conversational Q&A readiness, and JSON-LD schema markup.

---

## 🏛️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Frontend Dashboard                            │
│           (Single-Page App: Vanilla JS + Zenvora CSS System)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST API
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Backend                              │
│                (App Entry, CORS, Security Router, Lifespan)            │
└────────┬──────────────────────────┬───────────────────────────┬────────┘
         │                          │                           │
         ▼                          ▼                           ▼
┌─────────────────┐       ┌──────────────────┐       ┌───────────────────┐
│ Security Layer  │       │ Crawler Engine   │       │ Technical Analyzer│
│ - SSRF Guard    │       │ - Robots.txt Check│      │ - HTML Parser     │
│ - DNS Rebinding │       │ - Async HTTPX    │       │ - 10 Rule Checks  │
│ - IP Blacklist  │       │ - Size/Timeout Cap│      │ - Score (0-100)   │
└─────────────────┘       └──────────────────┘       └─────────┬─────────┘
                                                               │
                                                               ▼
┌─────────────────┐                                  ┌───────────────────┐
│ SQLite DB       │◄───────── Async Repository ──────┤ AEO AI Copilot    │
│ - Audits Table  │           (SQLAlchemy 2.0)       │ - Schema Validator│
│ - Findings Table│                                  │ - OpenAI / Gemini │
└─────────────────┘                                  │ - Mock Fallback   │
                                                     └───────────────────┘
```

---

## ✨ Features

- **SSRF & Security Guardrails**: Pre-flight DNS resolution and IP blacklisting to prevent internal network scanning (blocking loopback `127.0.0.1`, private subnets `10.0.0.0/8`, `192.168.0.0/16`, and cloud metadata `169.254.169.254`).
- **Robots.txt & Rate Etiquette**: Automatically parses `robots.txt` using Python's `RobotFileParser` and enforces HTTP timeouts (10s) and body payload size caps (5MB).
- **Deterministic Technical Analyzer**: Evaluates 10 core technical and AEO checks (Title tag, Meta description, H1 uniqueness, Image alt attributes, Canonical URLs, Robots meta, Schema.org presence, AEO schema types like `FAQPage`/`Article`/`Product`, Thin content, and H2/H3 sub-headings).
- **LLM Provider Abstraction & Copilot**: Supports `OpenAI`, `Google Gemini`, and an offline `MockLLMProvider`. Includes automatic schema validation and fallback mechanisms if remote model APIs are unavailable or encounter rate limits.
- **Async Database Persistence**: Uses SQLAlchemy 2.0 with `aiosqlite` for full audit lifecycle storage, paginated history retrieval, and report deletion.
- **Zenvora UI Dashboard**: Single-page frontend adhering strictly to Zenvora's navy (`#0B192C`), teal (`#14B8A6`), and restrained gold (`#D4AF37`) color palette, featuring score ring gauges, tabbed findings view, Schema code block copier, and one-click JSON report export.
- **Ground-Truth Evaluation Harness**: Measures auditing accuracy (Precision, Recall, F1 Score) against benchmark website edge cases.

---

## 📁 Folder Structure

```
AEO_opt/
├── app/
│   ├── api/                     # REST API Router & Endpoints
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── audit.py     # Audit creation & fetching
│   │       │   ├── health.py    # Health check endpoint
│   │       │   ├── history.py   # Audit history listing
│   │       │   └── validate.py  # SSRF URL safety validator endpoint
│   │       └── router.py
│   ├── config.py                # Environment configuration (Pydantic BaseSettings)
│   ├── core/
│   │   ├── analyzer.py          # HTML parser & deterministic rule engine
│   │   ├── crawler.py           # Safe async fetcher & robots.txt parser
│   │   ├── security.py          # SSRF URL validator & DNS resolver
│   │   └── llm/                 # LLM Provider Abstraction & AEO Copilot
│   │       ├── base.py          # Abstract LLMProvider interface
│   │       ├── engine.py        # AEO engine & fallback orchestrator
│   │       ├── gemini_provider.py
│   │       ├── mock_provider.py # Offline mock provider
│   │       └── openai_provider.py
│   ├── db/                      # SQLAlchemy 2.0 Async Database Layer
│   │   ├── database.py
│   │   ├── models.py            # AuditRecord & FindingRecord ORM
│   │   └── repository.py        # Async CRUD operations
│   ├── main.py                  # FastAPI application entry point
│   └── schemas/                 # Pydantic validation schemas
│       ├── aeo.py
│       ├── audit.py
│       ├── crawler.py
│       └── technical.py
├── evals/                       # Ground Truth Benchmark Suite
│   ├── dataset.json             # Test site cases & expected findings
│   ├── fixtures/                # Synthetic HTML edge case files
│   └── run_eval.py              # Evaluation harness runner
├── frontend/                    # Single Page Web Application
│   ├── css/
│   │   └── styles.css           # Zenvora design system stylesheet
│   ├── js/
│   │   ├── api.js               # REST client library
│   │   └── app.js               # Dashboard UI logic
│   └── index.html               # Main dashboard HTML
├── tests/                       # Pytest Suite (24 unit & integration tests)
├── .env.example                 # Environment settings template
├── pytest.ini                   # Pytest configuration
├── requirements.txt             # Python dependencies
└── README.md                    # Project Documentation
```

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
- Python 3.10+
- Git

### 2. Setup Virtual Environment & Install Dependencies
```bash
# Clone or navigate to project workspace
cd c:\FutureIndia\Project\AEO_opt

# Create virtual environment (optional)
python -m venv venv
venv\Scripts\activate

# Install requirements
python -m pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` as needed:
```env
PROJECT_NAME="Zenvora AI Audit Copilot"
API_V1_STR="/api/v1"
DEBUG=True
DATABASE_URL="sqlite+aiosqlite:///./zenvora_audit.db"

# Select LLM Provider: 'mock', 'openai', or 'gemini'
LLM_PROVIDER="mock"
OPENAI_API_KEY=""
GEMINI_API_KEY=""
```

---

## 🏃 Running the Application

Start the local dev server using `uvicorn`:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser and navigate to:
- **Web Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)

---

## 🧪 Running Automated Tests

Run the complete test suite (24 unit & integration tests):

```bash
python -m pytest -v
```

---

## 📊 Running Benchmark Evaluation Harness

To test accuracy against the ground-truth benchmark dataset:

```bash
python evals/run_eval.py
```

Sample Evaluation Output:
```
================================================================================
OVERALL BENCHMARK EVALUATION METRICS
================================================================================
True Positives (TP) : 11
False Positives (FP): 0
False Negatives (FN): 0
PRECISION           : 100.00%
RECALL              : 100.00%
F1 SCORE            : 100.00%
================================================================================
```

---

## 🛡️ Security Architecture

1. **SSRF Guardrails**: Hostnames are resolved to IP addresses *before* making HTTP requests. Private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.1`, `::1`), and cloud metadata (`169.254.169.254`) are strictly blocked.
2. **Async DNS Resolution & Timeout Protection**: DNS resolution is performed non-blocking in an executor thread via `asyncio.get_running_loop().getaddrinfo()` with strict timeout enforcement (`5.0s`), protecting the event loop from denial-of-service and DNS hang attacks.
3. **Redirect Hop SSRF & DNS Rebinding Regression Protection**: Host IP validation is re-executed on every redirect target URL during crawling. Redirect attempts leading to internal IPs, localhost, or cloud metadata are aborted mid-flight and guarded by automated regression tests.
4. **Prompt Injection Protection**: Scraped HTML content is isolated as untrusted data inputs within structured JSON containers, preventing indirect prompt manipulation.
5. **Credential Isolation**: All API keys are loaded via `.env` / `Pydantic-Settings` and never logged.

---

## ⚠️ Limitations & Production Roadmap

1. **Single-Page Rendering**: The MVP crawler parses server-side HTML. For client-side JavaScript rendered Single-Page Applications (SPAs built with React/Vue/Angular), integrating a headless browser (Playwright or Chromium) is recommended for production.
2. **PostgreSQL Migration**: SQLite is used for MVP development. Migrating to PostgreSQL is seamless by changing `DATABASE_URL` to `postgresql+asyncpg://user:pass@host/dbname` and generating Alembic migrations.

---

## 📜 License

Distributed under the MIT License. Developed for Zenvora AI Website & AEO Audit Copilot.
