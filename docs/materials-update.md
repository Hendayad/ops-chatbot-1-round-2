# Materials Update Guide

## Purpose

This document explains how to update the knowledge base used by OpsAgent AI.

---

## Step 1

Collect the latest source materials.

Examples:

- PDFs
- Policies
- Internal documentation
- Course guides

---

## Step 2

Place the files in the ingestion folder.

(Reference the existing ingestion process from M01.)

---

## Step 3

Run the ingestion pipeline.

Example

make ingest

(or the command already used by the project)

---

## Step 4

Verify ingestion completed successfully.

Check:

- Console output
- Database
- Knowledge search

---

## Step 5

Restart the backend if required.

---

## Verification

Ask the chatbot a question that only exists in the newly added document.

If it answers correctly the ingestion succeeded.

---

## Best Practices

- Never modify the database manually.
- Keep source documents version controlled.
- Re-run ingestion whenever documents change.