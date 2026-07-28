# At-Risk Detector Job & Proactive Learner Nudges

Implements PRD F2.3-F2.5: a scheduled at-risk detector, an auditable
persisted risk state, deduplicated proactive nudges, a real in-chat
delivery channel, and an Ops-gated, cohort-scoped dashboard API.

## Files

| File | Responsibility |
| --- | --- |
| `app/schemas/signals.py` | **Fixed** — was a broken Week-1 draft (syntax errors, missing return). Now a working `compute_risk_signals`. |
| `app/atrisk/detector.py` | Pure threshold evaluation. No I/O. `resolve_thresholds` supports per-learner overrides. Carries `cohort_id` through from `LearnerProgress` into `DetectionResult`. |
| `app/atrisk/state.py` | SQLModel table `AtRiskStateRecord` + persistence/aggregate functions, all cohort-scopable via an optional `cohort_id` param — the auditable, shared risk contract. |
| `app/atrisk/nudges.py` | Abstract `NotificationSender` contract, dedup + rolling-window frequency-capped nudge building, delivery via the existing notification service. |
| `app/notifications/learner_chat_channel.py` | Real `NotificationSender` implementation: delivers a nudge as an assistant message appended into the learner's actual LangGraph chat session. |
| `app/api/v1/atrisk.py` | Ops-facing dashboard API (`/atrisk/summary`, `/atrisk/trend`, `/atrisk/learners`) — requires `get_current_ops_user` and a `cohort_id` query param on every endpoint. |
| `app/api/v1/auth.py` | `get_current_ops_user` — wraps `get_current_user`, 403s unless `User.is_ops`. |
| `app/models/user.py` | `User.is_ops` — the Ops/admin authorization flag. |
| `app/static/atrisk_dashboard.html` + `/dashboard` route in `app/main.py` | Standalone Ops dashboard UI: login, cohort filter, summary/trend/learner views. |
| `app/jobs/atrisk_job.py` | Orchestrates detect -> persist -> nudge as one idempotent job run. |
| `demo_learner_chat_nudge.py` | End-to-end demo against real learner accounts and real chat sessions (not fabricated ids) — proves the nudge appends to existing chat history rather than overwriting it. |
| `evals/atrisk_suite.py` | Labeled-dataset precision/recall/F1 report for the detector. |
| `tests/test_atrisk_detection.py` | Pytest coverage: detector, state idempotency + cohort scoping, nudge dedup + rolling-window boundary cases, Ops authorization, end-to-end job idempotency. |
| `alembic/versions/d4b7f2a91c3e_*.py` | Migration for the `atriskstaterecord` table. |
| `alembic/versions/e29c14a7d6f8_*.py` | Migration adding `cohort_id` to `atriskstaterecord` and `is_ops` to `user`. |

## Idempotency model

- **Detection** is a pure function of its inputs — running it twice on the
  same `LearnerProgress` always yields the same `AtRiskSignals`.
- **State persistence** upserts on `(learner_id, run_date)` — a DB-level
  unique constraint (`uq_atriskstaterecord_learner_rundate`) backs this, so
  even two concurrent job runs can't create duplicate rows for the same
  day (the loser of the insert race falls back to an update).
- **Nudge delivery** reuses the existing `dedup_key` + `tenacity` retry
  machinery in `app/notifications/service.py` / `app/scheduler/runner.py`.

## Nudge frequency cap: rolling window, not a calendar bucket

The frequency cap is a real rolling window: before building a nudge for a
learner, `app.atrisk.nudges._nudge_eligible` looks up that learner's most
recent `SENT` `AT_RISK_NUDGE` `NotificationRecord` and only allows a new
nudge once at least `frequency_days` (default 7) has actually elapsed
since it was sent. There is no calendar bucketing — "at least 7 days since
the last nudge" is enforced directly against real delivery history, not
approximated by a fixed-epoch bucket, so two nudges can never land closer
together than the configured window regardless of which calendar day they
fall on. See `test_send_at_risk_nudges_blocks_adjacent_day_nudge_within_frequency_window`
and `test_send_at_risk_nudges_allows_nudge_once_frequency_window_elapses`
in `tests/test_atrisk_detection.py` for the boundary regression coverage.

## Authorization and cohort scoping

`/atrisk/*` requires both an authenticated **and** Ops-authorized account
(`Depends(get_current_ops_user)`, 403 for `is_ops=False`) and a required
`cohort_id` query parameter. Every persisted `AtRiskStateRecord` carries
its `cohort_id` (sourced from `LearnerProgress.cohort_id` via
`DetectionResult`), and every read path — `get_aggregate`,
`get_aggregate_trend`, `get_at_risk_learner_ids`, and the "latest run
date" lookup they depend on — filters by it when provided. This keeps
one cohort's learners from appearing in another cohort's dashboard.

## In-chat nudge delivery

`LearnerChatChannel` (`app/notifications/learner_chat_channel.py`) is a
real `NotificationSender`: it resolves `learner_id -> session_id` (today,
via the only identity link the codebase has — `learner_id == str(User.id)`)
and appends the nudge as an assistant message into that learner's actual
LangGraph-backed chat session, via `LangGraphAgent.append_message` (a
read-modify-write that avoids clobbering `GraphState`'s un-reduced
`messages` list). `demo_learner_chat_nudge.py` runs the real
`run_at_risk_job` pipeline against real learner accounts and prints back
the full chat history, so you can see the nudge appended after a seeded
prior conversation rather than replacing it.

## What still needs wiring before this runs unattended in production

1. **A real `ProgressProvider`** — `app/jobs/atrisk_job.run_at_risk_job`
   takes a callable returning `list[LearnerProgress]`. Nothing in the
   codebase yet computes real learner progress (no progress-data
   model/service exists), so that's intentionally left pluggable rather
   than guessed at.
2. **A scheduler trigger** — `run_at_risk_job` is a plain, tested function;
   nothing registers it with a cron/Celery-beat/APScheduler mechanism yet
   (`app/scheduler/` currently only holds the notification-retry runner,
   not a job scheduler). Running `python -m app.jobs.atrisk_job` directly
   today evaluates an empty learner list by design, until (1) is wired up.

Everything else this doc used to list as outstanding — a real
`NotificationSender` and an Ops-facing API route — is implemented; see
the sections above.

## Running it

```bash
# Apply migrations
make migrate

# Run the detector precision eval
python -m evals.atrisk_suite

# Run the pytest suite (needs the project's Postgres, e.g. `make docker-up ENV=test`)
pytest tests/test_atrisk_detection.py -v

# Lint/typecheck
make check

# End-to-end demo: real learners, real chat sessions, real nudge delivery
python demo_learner_chat_nudge.py

# Ops dashboard (after `is_ops=True` is set on your account)
uvicorn app.main:app --reload --port 8000
# then open http://localhost:8000/dashboard
```
