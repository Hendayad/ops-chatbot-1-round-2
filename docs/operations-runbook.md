# Operational Runbook

## Purpose

This runbook provides operational procedures for monitoring, troubleshooting, and recovering the Ops Chatbot platform. It is intended for Operations personnel responsible for maintaining service availability and resolving production issues.

---
## Intended Audience

This runbook is intended for Operations Administrators responsible for maintaining production availability of the Ops Chatbot platform.

It provides operational procedures for incident response, troubleshooting, recovery, and post-incident validation.

# System Components

The platform consists of the following services:

- FastAPI Backend
- PostgreSQL Database
- Streamlit Frontend
- Knowledge Base
- Scheduler
- Notification Service
- Ticket Escalation Service
- Prometheus
- Grafana

---
# Service Dependencies

The platform components depend on each other as follows:

- Streamlit depends on the FastAPI backend.
- FastAPI depends on PostgreSQL.
- Knowledge Base services depend on the database and ingestion pipeline.
- Scheduler depends on the backend and notification services.
- Prometheus collects metrics from backend services.
- Grafana visualizes metrics collected by Prometheus.

Failures in lower-level services may affect higher-level components.

# Daily Health Checks

Perform the following checks at the beginning of each day.

## API

Verify the API is reachable.

```
http://localhost:8000/docs
```

Expected Result:

- API responds successfully.
- Swagger documentation loads.
- Endpoints return expected responses.

---

## Database

Confirm:

- database is reachable
- migrations are current
- connection errors are absent

---

## Knowledge Base

Verify:

- materials are available
- onboarding completed successfully
- recent updates are visible
- no ingestion failures appear in logs

---

## Scheduler

Check that scheduled jobs continue to execute.

Expected indicators:

- reminder jobs complete
- notifications continue sending
- scheduler logs show successful execution

---

## Monitoring

Review Grafana dashboards.

Verify:

- CPU usage
- memory usage
- API latency
- request volume
- error rate
- database health

Investigate unusual trends immediately.

---
# Health Check Frequency

Recommended operational schedule:

| Check | Frequency |
|--------|-----------|
| API availability | Every day |
| Database connectivity | Every day |
| Scheduler health | Every day |
| Notification delivery | Every day |
| Dashboard review | Every day |
| Knowledge Base verification | After every update |
| Database migrations | Before deployments |

# Common Failure Modes

---

## API Returns HTTP 500

### Symptoms

- frontend cannot load data
- API requests fail
- internal server errors appear in logs

### Possible Causes

- application exception
- invalid database data
- missing migrations
- dependency failure

### Investigation

1. Review backend logs.
2. Identify the failing endpoint.
3. Read the exception traceback.
4. Verify database connectivity.

### Resolution

- Correct invalid database records.
- Restart the API if necessary.
- Apply pending migrations.
- Redeploy if configuration changed.

---

## Database Connection Failure

### Symptoms

- application startup failure
- database timeout
- connection refused
- authentication errors

### Investigation

Verify:

- PostgreSQL is running.
- connection settings are correct.
- credentials are valid.
- network connectivity exists.

### Resolution

Restart database services.

If using Docker:

```bash
make docker-up
```

If migrations are pending:

```bash
make migrate
```

---

## Migration Failure

### Symptoms

- startup errors
- missing tables
- schema mismatch
- SQL exceptions

### Investigation

Review migration history.

```bash
make migrate-history
```

Verify current revision.

---

### Resolution

Apply migrations.

```bash
make migrate
```

If necessary, roll back the previous migration.

```bash
make migrate-downgrade
```

Only perform rollback during approved maintenance windows.

---

## Knowledge Base Ingestion Failure

### Symptoms

- onboarding fails
- materials missing
- chatbot cannot answer newly added questions

### Possible Causes

- missing materials directory
- invalid JSON
- unsupported file format
- empty files
- invalid cohort configuration

### Investigation

Verify:

- materials exist
- directory structure is correct
- JSON is valid
- files are not empty
- cohort configuration is correct

---

### Resolution

Correct the source files.

Re-run onboarding.

```
POST /api/v1/kb/cohorts/{cohort_id}/onboard
```

Or perform another ingestion.

```
POST /api/v1/kb/reingest
```

Verify the results.

```
GET /api/v1/kb/materials
```

---

## Cohort Onboarding Failure

### Symptoms

- onboarding endpoint returns an error
- no materials appear

### Investigation

Check:

- cohort exists
- materials_root is configured
- directory exists
- approved materials are present

### Resolution

Correct the configuration or materials.

Retry onboarding.

---

## Notification Failure

### Symptoms

- reminders not delivered
- notifications missing

### Investigation

Verify:

- scheduler is running
- notification records are created
- notification preferences are correct

### Resolution

Restart scheduler if necessary.

Review application logs for notification failures.

---

## Scheduler Failure

### Symptoms

- reminder jobs stop executing
- recurring tasks no longer run

### Investigation

Review scheduler logs.

Look for:

- failed jobs
- uncaught exceptions
- repeated retries

### Resolution

Restart the application.

Verify scheduled jobs resume successfully.

---
## Ticket Escalation Failure

### Symptoms

- learner receives escalation message
- no ticket appears in the Operations queue
- escalation service errors appear in logs

### Investigation

Verify:

- escalation service is running
- ticket database is reachable
- ticket creation logs contain no errors

### Resolution

Restart affected services if necessary.

Review ticket service logs and retry the escalation if appropriate.



## Authentication Failure

### Symptoms

- HTTP 401
- HTTP 403
- login failures
- invalid token messages

### Investigation

Verify:

- JWT configuration
- user credentials
- token expiration
- user permissions

### Resolution

Authenticate again.

Replace expired tokens.

Verify role assignments.

---

## Slow API Responses

### Symptoms

- high latency
- frontend timeout
- delayed chatbot responses

### Investigation

Review:

- database performance
- API logs
- CPU utilization
- memory usage

Determine whether delays originate from:

- database queries
- knowledge retrieval
- LLM processing
- external services

### Resolution

Restart affected services if required.

Investigate long-running queries or repeated retries.

---

## Monitoring Service Failure

### Symptoms

- Grafana dashboards unavailable
- Prometheus metrics missing

### Investigation

Verify:

- Prometheus is running
- Grafana is running
- metrics endpoint responds

### Resolution

Restart the monitoring stack:

```bash
make stack-up
```

# Log Review

Important log categories include:

- application startup
- authentication
- scheduler execution
- knowledge ingestion
- notification delivery
- ticket escalation
- database operations
- API request failures

Administrators should review logs:

- after deployments
- after configuration changes
- after production incidents
- whenever error rates increase

Repeated warnings should be investigated before they become service outages.

# Incident Response Workflow

For every production incident:

1. Identify affected services.
2. Review application logs.
3. Determine the root cause.
4. Apply corrective actions.
5. Verify service recovery.
6. Record the incident.
7. Monitor the system for recurring issues.

# Recovery Checklist

After resolving any incident verify:

- backend is running
- database is available
- API documentation loads
- authentication succeeds
- knowledge base is accessible
- scheduler resumes
- notifications are delivered
- dashboards show healthy status
- application logs contain no recurring critical errors
- chatbot responses are correct
- ticket escalation functions correctly
- monitoring metrics return to normal
- no failed scheduler jobs remain queued

---

# Escalation Procedure

Escalate incidents when:

- service outage exceeds operational limits
- database recovery fails
- repeated ingestion failures occur
- migrations cannot be completed
- authentication remains unavailable
- production data integrity is at risk

Provide the following information:

- incident start time
- affected services
- observed symptoms
- relevant log messages
- troubleshooting performed
- current system status

---

# Useful Operational Commands

## Start Development Server

```bash
make dev
```

---

## Start API and Database

```bash
make docker-up
```

---

## Start Full Monitoring Stack

```bash
make stack-up
```

---

## View Logs

```bash
make docker-logs
```

---

## View Complete Stack Logs

```bash
make stack-logs
```

---

## Apply Database Migrations

```bash
make migrate
```

---

## Run Migrations in Docker

```bash
make docker-migrate
```

---

## Run Repository Checks

```bash
make check
```

---

# Operational Best Practices

- Monitor dashboards throughout the day.
- Review application logs regularly.
- Investigate recurring warnings promptly.
- Apply migrations before deploying application updates.
- Verify Knowledge Base updates after every ingestion.
- Keep source materials organized by cohort.
- Validate new materials before onboarding.
- Record every production incident.
- Verify system health after every deployment.
- Back up the database before major maintenance.
- Avoid manual database modifications unless absolutely necessary.

# Related Documentation

For additional operational procedures, refer to:

- `docs/admin_guide.md`
- `docs/materials_update.md`