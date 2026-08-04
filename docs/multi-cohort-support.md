# M10: Multi-Cohort Support & No Answer Leakage — Technical & Operational Documentation

**Module**: M10 — Multi-Cohort Support (Config-Driven Cohorts, No Answer Leakage)  
**Sprint**: Sprint 4  
**Status**: Production Ready  
**Primary Seams**: `app/cohorts/`, `app/ingestion/`, `app/kb/`, `app/retrieval/`, `app/graph/nodes/answer.py`, `evals/`

---

## 1. Executive Overview

The Ops Chatbot relies on the cohort as the **primary unit of data and retrieval isolation**. Learners assigned to Cohort A must only receive evidence, schedules, FAQs, and materials explicitly belonging to Cohort A.

M10 enforces strict cross-cohort isolation at the **storage, retrieval, and application graph layers**, preventing cross-cohort answer leakage in practice. Additionally, launching a new cohort is **100% configuration-driven**: adding a cohort entry and placing approved source materials allows instant onboarding without modifying application code or re-indexing existing cohorts.

---

## 2. Technical Architecture & Multi-Layer Isolation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. Storage & Ingestion Layer                                                │
│    - Database table 'knowledge_chunks' has indexed 'cohort' column.          │
│    - RawMaterial loaded from materials/<cohort>/ is stamped with cohort metadata.│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. Scoping Rules Engine (app/cohorts/scope.py)                              │
│    - Central source of truth for cohort normalization and comparison.        │
│    - Fail-closed: empty or missing cohort returns empty results (no leak). │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. Retrieval Scoping Layer (app/retrieval/retriever.py)                     │
│    - SQL-level vector search: WHERE cohort = :cohort                         │
│    - Defense-in-depth: scope_by_cohort() filtering in memory.              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. LangGraph Answer Node Layer (app/graph/nodes/answer.py)                  │
│    - resolve_cohort(): resolves cohort from state / RunnableConfig          │
│    - is_servable_cohort(): verifies cohort exists in cohorts_config.json     │
│    - _deduplicate_and_scope_chunks(): scopes chunks before prompting LLM   │
│    - _citations_are_valid(): rejects LLM answers citing foreign chunks       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Data Layer & Database Schema (`app/kb/store.py`)
Stored vector chunks reside in the PostgreSQL/pgvector `knowledge_chunks` table:
```sql
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,
    cohort TEXT NOT NULL,         -- Mandatory cohort scope identifier
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_cohort ON knowledge_chunks (cohort);
```

### 2.2 Shared Scoping Rules (`app/cohorts/scope.py`)
All layers import their matching rules from `app.cohorts.scope` to guarantee consistent isolation semantics:
- `normalize_cohort(cohort)`: Strips whitespace, maps `None` or blank values to `""`.
- `is_same_cohort(c1, c2)`: Returns `True` only when both parameters are non-empty and identical.
- `cohort_of(item)`: Extracts cohort from object attributes (`item.cohort`), top-level dictionary keys (`item["cohort"]`), or nested metadata (`item["metadata"]["cohort"]`).
- `scope_by_cohort(items, cohort)`: Keeps only items owned by `cohort`. Returns `[]` if `cohort` is empty.
- `find_leaked_items(items, cohort)`: Returns foreign items not owned by `cohort` (used by evals).

### 2.3 Retrieval Layer Isolation (`app/retrieval/retriever.py`)
`KnowledgeRetriever` implements dual-level defense-in-depth isolation:
1. **SQL Filter**: Vector search executes `WHERE cohort = :cohort AND embedding IS NOT NULL`.
2. **In-Memory Scoping**: Results pass through `scope_by_cohort(accepted, normalized_cohort)` before returning to the application node.

### 2.4 Application Node Isolation (`app/graph/nodes/answer.py`)
The LangGraph `grounded_answer` node enforces fail-closed isolation:
1. Resolves learner cohort using `resolve_cohort(state, config)`.
2. Checks configuration gating via `is_servable_cohort(cohort)`. Returns honest refusal `unknown_cohort` if unconfigured.
3. Scopes retrieved chunks via `_deduplicate_and_scope_chunks(chunks, cohort=cohort)`.
4. Verifies LLM citations via `_citations_are_valid(response, citation_map, cohort=cohort)`. Any foreign cohort citation forces an honest refusal (`invalid_citations`).

---

## 3. Configuration-Driven Cohort Onboarding

Launching a new cohort requires **only** configuration entries and source materials. **No code changes or re-indexing of existing cohorts are required.**

### 3.1 Cohort Configuration Specification (`cohorts_config.json`)
The configuration file path is set via `COHORTS_CONFIG_PATH` (defaults to `cohorts_config.json`).

```json
{
  "july-2026": {
    "name": "July 2026 Program Cohort",
    "materials_root": "materials/july-2026"
  },
  "sept-2026": {
    "name": "September 2026 Program Cohort",
    "materials_root": "materials/sept-2026"
  }
}
```

### 3.2 Step-by-Step Onboarding Walkthrough

#### Step 1: Add Cohort Entry
Open `cohorts_config.json` and add the new cohort definition:
```json
"fall-2026": {
  "name": "Fall 2026 Cohort",
  "materials_root": "materials/fall-2026"
}
```

#### Step 2: Populate Approved Source Materials
Create the directory structure under `materials_root`:
```
materials/fall-2026/
├── faqs/
│   └── onboarding_faq.json
├── schedules/
│   └── program_schedule.json
├── onboarding/
│   └── welcome_guide.md
└── docs/
    └── curriculum_expectations.md
```

#### Step 3: Trigger Onboarding API
Call the authenticated admin onboarding endpoint:
```http
POST /api/v1/kb/cohorts/fall-2026/onboard
Authorization: Bearer <ADMIN_JWT_TOKEN>
```

**Response**:
```json
{
  "sources_seen": 4,
  "sources_ingested": 4,
  "sources_skipped": 0,
  "chunks_written": 18
}
```

Every material loaded from `materials/fall-2026/` is automatically stamped with `cohort: "fall-2026"`. Existing cohorts remain unaffected.

## 4. Running the Evaluation Suite from a Fresh Checkout

Follow these step-by-step instructions to run the full evaluation suite and generate reports starting from a clean repository clone:

### Step 1: Clone Repository & Setup Environment
```powershell
git clone https://github.com/MoHatemTC/ops-chatbot-1-round-2.git
cd ops-chatbot-1-round-2

# Initialize Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # On Windows (or source .venv/bin/activate on Linux/macOS)

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Set Test Environment Variables
```powershell
$env:APP_ENV="test"
$env:OPENAI_API_KEY="test-key"
```

### Step 3: Run the Structural Cohort Isolation Suite
Verifies structural scoping rules, leaky repository filtering, answer node citation validation, and config gating:
```powershell
python -m evals.cohort_isolation
```
**Expected Output**:
```text
[PASS] scope_rules_cohort-a - isolation_score=1.00
[PASS] scope_rules_cohort-b - isolation_score=1.00
[PASS] scope_rules_missing_cohort_None - isolation_score=1.00
[PASS] scope_rules_missing_cohort_'' - isolation_score=1.00
[PASS] scope_rules_missing_cohort_'   ' - isolation_score=1.00
[PASS] scope_rules_validate_access - isolation_score=1.00
[PASS] retriever_drops_foreign_chunks_cohort-a - isolation_score=1.00
[PASS] retriever_drops_foreign_chunks_cohort-b - isolation_score=1.00
[PASS] retriever_refuses_empty_cohort - isolation_score=1.00
[PASS] answer_node_scopes_chunks - isolation_score=1.00
[PASS] answer_node_rejects_foreign_citations - isolation_score=1.00
[PASS] answer_node_refuses_without_cohort - isolation_score=1.00
[PASS] config_gate_refuses_unconfigured_cohort - isolation_score=1.00

All 13 isolation cases passed - no cross-cohort leakage.
```

### Step 4: Run the Adversarial Cross-Cohort Leakage Suite
Queries Cohort A using context, secrets, deadlines, and policies exclusive to Cohort B, asserting zero leakage and logging detailed error states if any case fails:
```powershell
python -m evals.adversarial_cohort_leakage
```
**Expected Output**:
```text
[PASS] ADV-01 - Cross-Cohort Deadline Leakage Attempt (Cohort: cohort-a)
[PASS] ADV-02 - Cross-Cohort Exclusive Policy Leakage Attempt (Cohort: cohort-a)
[PASS] ADV-03 - Cross-Cohort Secret Passcode Leakage Attempt (Cohort: cohort-a)
[PASS] ADV-04 - System Override Prompt Injection Leakage Attempt (Cohort: cohort-a)
[PASS] ADV-05 - Unscoped Missing Cohort Request (Cohort: (empty))
[PASS] ADV-06 - Unconfigured Cohort Access Request (Cohort: cohort-unconfigured-999)
[PASS] ADV-07 - Legitimate Cohort A Control Case (Cohort: cohort-a)

Final Summary: 7/7 Passed (100.0% Isolation Score, 0% Leakage)
Report files generated under: evals/reports
```

### Step 5: Run Automated Pytest Suite
```powershell
pytest tests/test_cohort_scope.py
```
*(41/41 test cases pass in under 2 seconds).*

### Step 6: Inspect Evaluation Output Reports
Report outputs are saved automatically under `evals/reports/`:
- **Markdown Report**: `evals/reports/adversarial_cohort_leakage_report.md`
- **JSON Metrics Report**: `evals/reports/adversarial_cohort_leakage_report.json`

---

## 5. Summary of Files

| File Path | Description |
|---|---|
| [app/cohorts/scope.py](file:///d:/LLM/sprint/ops-chatbot-1-round-2/app/cohorts/scope.py) | Central isolation rules (`is_same_cohort`, `scope_by_cohort`) |
| [app/cohorts/config.py](file:///d:/LLM/sprint/ops-chatbot-1-round-2/app/cohorts/config.py) | `CohortConfigLoader` & servable cohort gating (`is_servable_cohort`) |
| [app/ingestion/loader.py](file:///d:/LLM/sprint/ops-chatbot-1-round-2/app/ingestion/loader.py) | `load_materials()` stamping cohort metadata on raw materials |
| [app/kb/store.py](file:///d:/LLM/sprint/ops-chatbot-1-round-2/app/kb/store.py) | `KBStore` & `PgVectorChunkRepository` persistence |
| [app/retrieval/retriever.py](file:///d:/LLM/sprint/ops-chatbot-1-round-2/app/retrieval/retriever.py) | `KnowledgeRetriever` SQL filter & defense-in-depth scoping |
| [app/graph/nodes/answer.py](file:///d:/LLM/sprint/ops-chatbot-1-round-2/app/graph/nodes/answer.py) | `grounded_answer` node cohort resolution & citation validation |
| [app/kb/admin_api.py](file:///d:/LLM/sprint/ops-chatbot-1-round-2/app/kb/admin_api.py) | Config-driven onboarding endpoint `POST /api/v1/kb/cohorts/{cohort_id}/onboard` |
| [cohorts_config.example.json](file:///d:/LLM/sprint/ops-chatbot-1-round-2/cohorts_config.example.json) | Example cohort configuration JSON file |
| [evals/cohort_isolation.py](file:///d:/LLM/sprint/ops-chatbot-1-round-2/evals/cohort_isolation.py) | Structural isolation evaluation suite (13 cases) |
| [evals/adversarial_cohort_leakage.py](file:///d:/LLM/sprint/ops-chatbot-1-round-2/evals/adversarial_cohort_leakage.py) | Adversarial cross-cohort leakage evaluation suite (7 cases) |
| [tests/test_cohort_scope.py](file:///d:/LLM/sprint/ops-chatbot-1-round-2/tests/test_cohort_scope.py) | Unit and integration test suite (41 cases) |
