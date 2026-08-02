# Operations Runbook

## Purpose

This runbook provides operational procedures for maintaining the OpsAgent AI platform.

---

# Starting the Platform

Backend

uv run uvicorn app.main:app --reload

Frontend

streamlit run frontend/app.py

---

# Docker

Start services

docker compose up

Stop services

docker compose down

---

# Database

Apply migrations

alembic upgrade head

Create migration

alembic revision --autogenerate -m "message"

---

# Common Problems

## Backend won't start

Check

- Environment variables
- Database connection
- Docker

---

## Frontend cannot connect

Verify

BACKEND_URL

Backend is running

---

## Login fails

Check

JWT configuration

Database

User account

---

## Escalation tickets missing

Verify

Escalation service

Database table

API endpoint

---

## Reminders missing

Verify

ReminderEvent table

Scheduler

Notification preferences

---

## Knowledge search returns nothing

Run ingestion again.

---

## Logs

Application logs are written to:

logs/

(assuming this is correct)

---

## Health Checks

Verify:

Backend responds

/api/v1/health

Database reachable

Frontend loads

Authentication works

---

## Backup

Back up:

PostgreSQL database

Knowledge documents

Configuration files
