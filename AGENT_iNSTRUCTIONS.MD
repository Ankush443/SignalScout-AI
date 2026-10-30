# SignalScout AI — Complete Build Instructions for CLI Agent

## 1. Project Objective

You are working on **SignalScout AI**, an AI-powered business opportunity intelligence platform.

The goal is to help founders, startups and small businesses discover companies showing meaningful business signals, such as:

1. Companies announcing new funding.
2. Companies hiring multiple AI engineers or expanding their AI teams.

The platform should collect company-related signals, normalize and classify them, assess the reliability of their sources, identify relevant business opportunities, and present useful results through a simple dashboard.

**Your responsibility is to inspect the existing repository, fix current issues, complete the remaining implementation, test everything, and prepare the project for submission today.**

Do not start from scratch. Preserve working code and build upon the existing implementation.

---

# 2. Important Working Instructions

Follow these instructions throughout development.

### Repository handling

- First inspect the entire repository and understand its current architecture.
- Read existing Python files, tests, JSON data, configuration files and documentation.
- Identify what is already implemented before writing new code.
- Do not unnecessarily rewrite working modules.
- Preserve existing functionality and improve it incrementally.
- Use the existing project structure where practical.
- Do not create duplicate modules or unnecessary abstractions.
- Do not delete existing tests just to make the test suite pass.
- Do not replace meaningful functionality with hardcoded demonstration outputs.

### Development approach

- Prioritize a working end-to-end MVP over sophisticated architecture.
- Keep the implementation modular and maintainable.
- Use clear function names, type hints where appropriate and useful docstrings.
- Handle missing fields, invalid inputs, network errors and malformed records.
- Avoid unnecessary dependencies.
- Prefer free and publicly accessible data sources.
- Never introduce an API integration that requires an unavailable API key without providing a working fallback.
- Do not fabricate company information, funding announcements, job listings, source URLs or verification results.
- Clearly distinguish sample data from live collected data.

### Time constraint

The project must be ready for submission today.

Prioritize tasks in this order:

1. Fix existing failures.
2. Complete the core backend pipeline.
3. Build a working interface.
4. Add meaningful tests.
5. Prepare documentation and demo instructions.
6. Polish the interface only after everything works.

If a feature cannot be completed reliably within the available time, implement a clearly documented fallback rather than leaving the entire application broken.

---

# 3. Existing Project Context

The project currently has the following known structure:

```text
SignalScout AI/
│
├── data/
│   └── sample_companies.json
│
├── src/
│   ├── __init__.py
│   ├── signal_detector.py
│   └── source_reliability.py
│
├── tests/
│   ├── test_signal_detector.py
│   └── test_source_reliability.py
│
└── ...
```

The actual repository may contain additional files. Inspect them before making architectural decisions.

### Existing implemented functionality

The project already has some of the following:

- Signal classification into funding and hiring.
- Signal type normalization using lowercase and whitespace stripping.
- Input validation.
- Handling of invalid signal records.
- Deduplication using `signal_id`.
- Source reliability assessment.
- Enrichment of detected signals with a `source_reliability` field.
- Unit tests for signal detection and source reliability.

Existing module locations:

```python
from src.signal_detector import detect_signals
from src.source_reliability import assess_source
```

Keep imports consistent with the actual package structure.

---

# 4. Immediate Task: Fix the Four Failing Tests

The latest test execution was:

```bash
python -m unittest discover -s tests -v
```

Result:

```text
Ran 19 tests

15 tests passed
4 tests failed
```

All four failures have the same underlying cause.

The signal detector now enriches every returned signal with:

```python
"source_reliability": "missing_source"
```

However, four existing tests compare entire dictionaries against their original input dictionaries. Their expected values do not contain this newly added field.

### Failing tests

1. `test_both_signals_types_are_classigied_correctly`
2. `test_different_signal_ids_are_preserved`
3. `test_duplicate_signal_ids_are_removed`
4. `test_signal_without_ids_are_preserved`

### Required fix

Inspect `tests/test_signal_detector.py`.

Update the assertions so that they test the actual behavior rather than comparing outdated full dictionaries.

Examples of suitable assertions:

```python
self.assertEqual(len(result["funding"]), 1)

self.assertEqual(
    result["funding"][0]["signal_id"],
    "F001"
)

self.assertEqual(
    result["funding"][0]["source_reliability"],
    "missing_source"
)
```

For signals without IDs, verify that both records remain present and their relevant identifying fields are preserved.

For different IDs, verify that both IDs remain present.

For funding and hiring classification, verify:

- Funding records appear only in `result["funding"]`.
- Hiring records appear only in `result["hiring"]`.
- Source reliability enrichment is present.

**Do not remove source reliability enrichment to make the tests pass.**

After fixing the assertions, run:

```bash
python -m unittest discover -s tests -v
```

All existing tests must pass before proceeding.

Also run:

```bash
python -m compileall src tests
```

Resolve any syntax or import errors.

---

# 5. Core Backend Requirements

Complete the backend as a modular pipeline.

The intended flow is:

```text
Data Sources
     |
     v
Data Ingestion
     |
     v
Signal Normalization
     |
     v
Signal Detection
     |
     v
Deduplication
     |
     v
Source Reliability Assessment
     |
     v
Company Matching
     |
     v
Opportunity Evaluation
     |
     v
API / Dashboard
```

Do not combine all these responsibilities into one large Python file.

## 5.1 Signal Data Schema

Establish a consistent normalized signal format.

A signal should support fields such as:

```json
{
  "signal_id": "FUNDING001",
  "company_name": "NovaAI Technologies",
  "signal_type": "funding",
  "title": "NovaAI Technologies announces a funding round",
  "description": "The company announced a new investment round.",
  "amount": "$12 million",
  "detected_at": "2026-10-30",
  "source_name": "Example News Source",
  "source_url": "https://example.com/article",
  "source_published_at": "2026-10-29",
  "verification_status": "unverified"
}
```

This is an illustrative schema, not a real announcement.

Requirements:

- Support funding and hiring signals.
- Preserve original source information.
- Handle missing optional fields.
- Normalize company names and signal types.
- Use ISO-formatted dates where possible.
- Never invent missing information.
- Keep source URLs attached to their corresponding signals.

If the existing project uses different field names, migrate carefully without breaking existing functionality.

## 5.2 Signal Detection

Improve the existing `signal_detector.py`.

It must:

- Identify funding signals.
- Identify hiring signals.
- Normalize signal types.
- Validate input structures.
- Skip malformed individual records where appropriate.
- Reject invalid company structures.
- Handle empty or missing signal lists.
- Deduplicate records with identical usable `signal_id` values.
- Preserve records without IDs.
- Enrich detected records with source reliability information.

Keep the detector independently testable.

Do not load sample JSON or start network requests when this module is imported.

## 5.3 Source Reliability

Improve `source_reliability.py`.

Use transparent reliability states such as:

| Status | Meaning |
|---|---|
| `missing_source` | No source URL was provided |
| `invalid_source_url` | The URL is malformed or uses an unsupported scheme |
| `unverified` | A usable URL exists but the claim has not been independently checked |
| `verified` | The claim has passed an explicit trusted verification process |

Important:

- Having a URL does not mean that the information is verified.
- Do not trust arbitrary incoming `verification_status` fields.
- Verification should be assigned by trusted application logic, not by raw external data.
- A valid URL does not prove that the source is reputable or the claim is true.
- If real verification cannot be implemented today, keep signals as `unverified`.
- Display uncertainty clearly in the interface.

If possible, preserve the current `assess_source()` interface to avoid breaking other modules.

---

# 6. Cross-Source Duplicate Detection

The current implementation only removes duplicate signals with identical `signal_id` values.

This is insufficient for real-world data.

The same funding announcement may appear on multiple websites with different IDs.

Implement a second-stage duplicate detection mechanism.

Compare signals using:

1. Normalized company names.
2. Normalized announcement titles.
3. Publication dates.
4. Signal types.
5. Source evidence.

For example:

```text
Source A:
NovaAI raises $12 million in Series A
ID: SOURCE_A_123

Source B:
NovaAI Technologies secures $12M Series A funding
ID: SOURCE_B_987
```

These may represent the same underlying announcement.

Requirements:

- Normalize whitespace and capitalization.
- Handle common company suffixes where reasonable.
- Normalize title text.
- Compare publication dates with a reasonable tolerance.
- Use a conservative similarity threshold.
- Avoid merging unrelated announcements.
- Preserve all supporting source URLs when duplicate records are merged.
- Preserve the original signal data and explain why records were grouped.
- Keep this functionality separately testable.

Do not rely solely on identical titles or identical dates.

If full semantic matching is too expensive or unreliable, implement a conservative rule-based approach first.

---

# 7. Data Ingestion Layer

Create a dedicated ingestion layer.

Suggested structure:

```text
src/
├── ingestion/
│   ├── __init__.py
│   ├── base.py
│   ├── rss_ingestion.py
│   └── normalizer.py
```

Adapt this to the current repository rather than forcing an unnecessary restructure.

### Requirements

The ingestion layer should:

- Collect publicly accessible information.
- Extract title, description, source URL, publication date and source name.
- Convert incoming records into the normalized signal schema.
- Handle malformed feeds and missing fields.
- Handle network timeouts and unavailable sources.
- Avoid crashing the entire application when one source fails.
- Prevent repeated ingestion of the same records.
- Keep source attribution.

### Data source strategy

Start with one practical source type, preferably publicly accessible RSS feeds or another accessible structured source.

Do not assume that a website has a working RSS feed. Inspect and test the source before integrating it.

If no dependable live source is available:

- Implement the ingestion interface.
- Include a small local fixture dataset.
- Clearly label fixture data as sample data.
- Keep the application functional without internet access.
- Document how to configure additional sources later.

Do not build a fragile scraper for multiple websites simply to claim broad coverage.

### Signal extraction

The first version should identify:

**Funding signals**
- Funding announcement.
- Seed round.
- Series A/B/C.
- Venture capital investment.
- Company fundraising.

**Hiring signals**
- AI engineer.
- Machine learning engineer.
- Applied AI engineer.
- Generative AI engineer.
- LLM engineer.
- AI research engineer.

Use explainable keyword/rule-based classification initially.

Do not introduce a machine-learning model unless it adds real value and can be completed and tested today.

---

# 8. Company Matching

Create a company matching module.

Its purpose is to identify companies that are relevant to the selected business opportunity.

For the MVP, support configurable matching criteria.

Examples:

- Companies hiring multiple AI engineers.
- Companies that recently raised funding.
- Companies showing both funding and hiring signals.

The module should:

- Normalize company names.
- Group signals belonging to the same company.
- Combine multiple signals for one company.
- Identify companies showing multiple relevant signals.
- Avoid duplicate company entries.
- Return structured results.
- Preserve references to supporting signals.

Example output:

```json
{
  "company": "DataBridge AI",
  "funding_signals": 1,
  "hiring_signals": 2,
  "opportunity_tags": [
    "recent_funding",
    "ai_team_expansion"
  ]
}
```

This is a sample output structure, not a real company finding.

---

# 9. Opportunity Evaluation and Ranking

Create an opportunity evaluation module.

The platform should not merely list signals. It should help users understand which companies may represent stronger business opportunities.

Implement a transparent rule-based scoring system.

Suggested factors:

| Factor | Suggested weight |
|---|---:|
| Recent funding announcement | 30 |
| Multiple AI-related hiring signals | 30 |
| Presence of both funding and hiring signals | 25 |
| Source quality / evidence availability | 15 |
| **Total** | **100** |

These weights are initial defaults and can be adjusted.

Requirements:

- Scores must be calculated from actual available signal data.
- Missing data must not automatically receive maximum points.
- Avoid treating a URL as proof of claim accuracy.
- Include a breakdown explaining how each score was calculated.
- Include the signals supporting each opportunity.
- Allow sorting by score and recency.
- Make scoring rules easy to modify.

Example:

```json
{
  "company": "DataBridge AI",
  "opportunity_score": 82,
  "reasons": [
    "Recent funding signal detected",
    "Multiple AI-related hiring signals detected"
  ],
  "evidence_count": 3
}
```

Do not present this sample as a real result.

**Important:** The score is an opportunity-priority heuristic, not a probability that a company will buy a product or service.

---

# 10. API Development

Inspect the existing backend before selecting a framework.

If FastAPI is already used, continue with it.

Otherwise, use FastAPI for a lightweight API if no existing framework makes that unnecessary.

Suggested endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /` | API health and project information |
| `GET /health` | Health check |
| `GET /companies` | List detected companies |
| `GET /signals` | List normalized signals |
| `GET /opportunities` | List ranked opportunities |
| `GET /companies/{company_name}` | Company details and supporting signals |
| `POST /ingest` | Trigger ingestion, if safe and practical |

Requirements:

- Return valid JSON.
- Validate request parameters.
- Handle empty results.
- Return meaningful HTTP status codes.
- Avoid exposing internal exceptions.
- Keep API logic separate from detection and scoring logic.
- Add basic filtering for signal type, company and recency where practical.

Do not expose a public ingestion endpoint that can be abused to fetch arbitrary URLs.

If live ingestion is not available, the endpoints must still work against the sample dataset.

---

# 11. Frontend / Dashboard

Inspect the existing frontend before creating another one.

If there is no usable frontend, build a clean and functional dashboard.

Preferred stack if starting fresh:

- React
- Vite
- TypeScript
- Tailwind CSS, if already configured or practical
- Existing FastAPI backend

Do not spend excessive time on design animations.

### Dashboard requirements

The interface should include:

**A. Overview**

Show:

- Total companies tracked.
- Total funding signals.
- Total hiring signals.
- Total opportunities identified.

**B. Opportunity feed**

Display ranked companies with:

- Company name.
- Opportunity score.
- Funding information, if available.
- AI hiring information, if available.
- Number of supporting signals.
- Latest signal date.
- Source reliability status.

**C. Filters**

Support:

- Funding.
- Hiring.
- Both signals.
- Minimum opportunity score.
- Search by company name.

**D. Company details**

Show:

- Company overview.
- Detected signals.
- Signal descriptions.
- Source URLs.
- Source names.
- Dates.
- Reliability status.
- Opportunity score breakdown.

**E. User feedback**

Include:

- Loading state.
- Empty state.
- Error state.
- Refresh action.

### Visual direction

Use a professional SaaS intelligence dashboard.

Design guidance:

- Clean, modern layout.
- Clear information hierarchy.
- Professional typography.
- Neutral background.
- Consistent spacing.
- Simple cards and tables.
- Good desktop responsiveness.
- Avoid excessive gradients and decorative animations.

The interface should communicate that SignalScout AI is a business intelligence tool, not a generic analytics dashboard.

---

# 12. Data and Sample Dataset

Inspect `data/sample_companies.json`.

Improve it if needed.

Include realistic test scenarios covering:

- Company with only funding signals.
- Company with only hiring signals.
- Company with both signal types.
- Company with multiple hiring records.
- Company with multiple funding records.
- Duplicate signal IDs.
- Similar announcements with different source IDs.
- Missing source URLs.
- Invalid URLs.
- Missing optional fields.
- Different date formats, if the normalizer supports them.

Keep malformed input tests in unit tests rather than making the primary sample dataset unusable.

Do not present fabricated sample companies as live discoveries.

Use clearly identified synthetic/demo records where appropriate.

---

# 13. Testing Requirements

Testing is mandatory.

Use the existing `unittest` setup unless the repository already uses another test framework.

Add or improve tests for:

### Signal detection

- Funding classification.
- Hiring classification.
- Case normalization.
- Whitespace normalization.
- Empty signals.
- Missing signals.
- Invalid company input.
- Invalid signal list.
- Malformed signal records.
- Duplicate signal IDs.
- Different signal IDs.
- Records without IDs.
- Source reliability enrichment.

### Source reliability

- Missing source URL.
- Blank source URL.
- Invalid URL.
- Unsupported URL scheme.
- Valid but unverified URL.
- Explicit trusted verification behavior.
- Non-dictionary input.

### Ingestion

- Valid source records.
- Missing fields.
- Malformed records.
- Invalid publication dates.
- Duplicate records.
- Network failure.
- Empty feed.

### Cross-source deduplication

- Same signal ID.
- Same announcement with different IDs.
- Same company but different announcements.
- Similar titles but different companies.
- Same company with different signal types.
- Missing dates.
- Multiple supporting URLs retained.

### Company matching and ranking

- Company grouping.
- Multiple signals for one company.
- Correct opportunity tags.
- Score calculation.
- Missing evidence.
- Ranking order.
- Score explanation.

### API

- Health endpoint.
- Empty response.
- Company listing.
- Signal listing.
- Opportunity listing.
- Invalid filters.
- Unknown company.

Use mocks for external requests. Tests must not depend on live websites or internet access.

Run:

```bash
python -m unittest discover -s tests -v
```

Also run the frontend build if a frontend exists:

```bash
npm run build
```

Fix all errors.

---

# 14. Project Documentation

Prepare a comprehensive `README.md`.

It should include:

1. Project title and introduction.
2. Problem statement.
3. What SignalScout AI does.
4. Target users.
5. Key features.
6. How the pipeline works.
7. Architecture diagram.
8. Technology stack.
9. Project structure.
10. Installation instructions.
11. Environment configuration.
12. How to run the backend.
13. How to run the frontend.
14. How to execute tests.
15. Sample data explanation.
16. Signal reliability explanation.
17. Opportunity scoring explanation.
18. Limitations.
19. Future improvements.
20. Screenshots section, if screenshots are available.

### README accuracy

Do not claim:

- Production-grade monitoring if only sample data is supported.
- Real-time discovery if ingestion is manual or fixture-based.
- Verified announcements when they have not been checked.
- AI-powered predictions if the system uses rules.
- Actual commercial intent based only on funding or hiring signals.

Clearly explain what is implemented and what remains a future enhancement.

---

# 15. Architecture Diagram

Include an architecture diagram in the README using Mermaid.

The diagram should represent:

```text
External Sources / Sample Data
             |
             v
       Data Ingestion
             |
             v
      Data Normalization
             |
             v
       Signal Detection
             |
             v
    Duplicate Detection
             |
             v
   Source Reliability Check
             |
             v
       Company Matching
             |
             v
    Opportunity Evaluation
             |
             v
        FastAPI Backend
             |
             v
       React Dashboard
```

Adjust the diagram to match the implementation.

---

# 16. Configuration and Setup

Provide a working `.env.example` if environment variables are needed.

Requirements:

- Never commit API keys or secrets.
- Add `.env` to `.gitignore`.
- Document optional API credentials.
- Provide sensible defaults.
- Ensure the application can run in demo mode without external API keys.
- Include all required dependencies in the relevant dependency file.

Provide exact Windows setup instructions in the README.

For example:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

Run the backend using the actual configured application entry point.

Do not document commands that have not been tested.

---

# 17. Demo Readiness

Prepare the project so that someone can run it and understand its functionality quickly.

The demo should demonstrate:

1. Application startup.
2. Sample or live data loading.
3. Funding signal detection.
4. Hiring signal detection.
5. Source reliability labels.
6. Duplicate detection.
7. Company grouping.
8. Opportunity ranking.
9. Opening a company detail view.
10. Viewing source evidence.

The demo must work without requiring paid API credentials.

If live ingestion is available, demonstrate it separately from sample mode.

Clearly label sample data in the dashboard.

---

# 18. Performance and Code Quality

Keep the project simple but reliable.

Requirements:

- Avoid unnecessary repeated processing.
- Avoid blocking the application during external requests.
- Set network timeouts.
- Handle exceptions at appropriate boundaries.
- Avoid global mutable state.
- Avoid hardcoded local file paths.
- Use `pathlib` for file paths.
- Keep business logic independent of API routes.
- Avoid unnecessary dependencies.
- Keep configuration separate from application logic.
- Add basic logging where useful.

Do not introduce a database unless the existing project already uses one or persistence is genuinely necessary for the MVP.

A JSON-backed demo implementation is acceptable if it is reliable and clearly documented.

---

# 19. Suggested Final Project Structure

Use this as a reference, not a requirement to restructure everything:

```text
SignalScout AI/
│
├── data/
│   └── sample_companies.json
│
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── signal_detector.py
│   ├── source_reliability.py
│   ├── normalizer.py
│   ├── deduplicator.py
│   ├── company_matcher.py
│   ├── opportunity_scorer.py
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── rss_ingestion.py
│   │
│   └── api/
│       ├── __init__.py
│       └── routes.py
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── ...
│
├── tests/
│   ├── test_signal_detector.py
│   ├── test_source_reliability.py
│   ├── test_normalizer.py
│   ├── test_deduplicator.py
│   ├── test_company_matcher.py
│   ├── test_opportunity_scorer.py
│   └── test_api.py
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

# 20. Final Acceptance Criteria

The project is considered ready only when the following conditions are met.

## Backend

- [ ] Existing four test failures are fixed.
- [ ] Existing tests continue to cover original behavior.
- [ ] Signal detection works.
- [ ] Funding and hiring signals are normalized.
- [ ] Duplicate detection works.
- [ ] Cross-source duplicate handling is implemented.
- [ ] Source reliability is transparent.
- [ ] Company matching works.
- [ ] Opportunity scoring works.
- [ ] API endpoints return correct data.
- [ ] Sample mode works without internet access.

## Frontend

- [ ] Dashboard starts successfully.
- [ ] Dashboard retrieves data from the backend.
- [ ] Overview metrics are correct.
- [ ] Opportunity feed works.
- [ ] Filters work.
- [ ] Company detail view works.
- [ ] Evidence URLs are accessible as links.
- [ ] Loading, empty and error states work.
- [ ] Sample records are visibly identified.

## Quality

- [ ] All backend tests pass.
- [ ] Python compilation succeeds.
- [ ] Frontend production build succeeds.
- [ ] No exposed secrets.
- [ ] No broken imports.
- [ ] No unnecessary duplicate modules.
- [ ] README contains tested setup instructions.
- [ ] Architecture diagram reflects the real implementation.

## Submission

- [ ] Project starts using documented commands.
- [ ] Demo can run without paid API credentials.
- [ ] README explains limitations honestly.
- [ ] No fabricated live-data claims.
- [ ] Final implementation summary is prepared.

---

# 21. Required Final Report From the Agent

After implementation, provide a concise but detailed report containing:

### A. What was implemented

List every completed feature.

### B. Existing issues fixed

Explain the four original test failures and how they were resolved.

### C. New files

List every new file and its purpose.

### D. Modified files

List every modified file and the reason for modification.

### E. Test results

Include the actual output or summary of:

```bash
python -m unittest discover -s tests -v
```

And the frontend build, if applicable.

Do not claim tests passed unless you actually ran them.

### F. Run instructions

Provide the exact commands to start the backend and frontend on Windows.

### G. Limitations

List any features that are incomplete, mocked, sample-only or dependent on external services.

### H. Submission checklist

Confirm which acceptance criteria are complete and which remain incomplete.

---

# 22. Final Priority Instruction

**Build a complete, working and honest MVP—not a collection of unfinished features.**

If time becomes limited, prioritize:

1. Reliable signal detection and source handling.
2. Company matching and opportunity scoring.
3. A working API and dashboard.
4. Comprehensive tests.
5. Clear README and demo instructions.

Do not spend hours integrating multiple unreliable external sources.

A working sample-data pipeline with a clean architecture, transparent evidence handling, tested scoring logic and a functional dashboard is preferable to a supposedly real-time platform that does not work.

Begin by auditing the existing repository and fixing the four failing tests. Then proceed incrementally, testing after each major module.

Do not stop after writing a plan. Implement, run, debug and verify the application.
