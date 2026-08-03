# Materials Update Instructions

## Purpose

This document explains how administrators update the Knowledge Base (KB) by adding, modifying, re-ingesting, and retiring learning materials. The ingestion process is designed to be **re-runnable**, allowing approved content to be safely reprocessed without rebuilding the entire system.

---

## Intended Audience

This guide is intended for Operations Administrators responsible for maintaining the Knowledge Base after deployment.

It assumes the administrator has access to:

- the project repository
- the configured materials directory
- the Knowledge Base administration API
- application logs

# Overview

The Ops Chatbot Knowledge Base stores information used by the chatbot to answer learner questions.

Administrators maintain the Knowledge Base by:

- adding approved source documents
- updating existing materials
- re-ingesting updated content
- onboarding new cohorts
- retiring obsolete materials

The system automatically loads approved materials, converts them into normalized `RawMaterial` objects, and stores them in the knowledge base.

---

# Update Workflow

Every Knowledge Base update follows the same operational workflow:

1. Prepare or modify source documents.
2. Validate document formatting.
3. Place the documents in the appropriate directory.
4. Execute the ingestion process.
5. Verify successful ingestion.
6. Test chatbot responses.
7. Monitor logs for ingestion errors.

This workflow minimizes the risk of inconsistent or outdated chatbot responses.

# Supported Material Types

Materials are organized by category.

| Directory | Source Type |
|------------|-------------|
| `faqs/` | FAQ |
| `schedules/` | Schedule |
| `onboarding/` | Onboarding Material |
| `docs/` | Program Documentation |

The loader determines the material type from the directory in which the file is located.

---

# Directory Structure

Each cohort should have a materials directory with the following structure:

```
materials/
│
├── faqs/
├── schedules/
├── onboarding/
└── docs/
```

Example:

```
materials/
│
├── faqs/
│   ├── common_questions.json
│   └── grading.md
│
├── schedules/
│   └── schedule.json
│
├── onboarding/
│   └── welcome.md
│
└── docs/
    ├── handbook.md
    └── policies.txt
```

---

# Supported File Formats

The loader accepts the following file types.

## FAQ

- JSON
- Markdown
- Text

Examples:

```
questions.json
faq.md
faq.txt
```

---
# File Requirements

Before ingestion, ensure that every source document:

- uses UTF-8 encoding
- contains readable text
- is free of binary data
- has a supported file extension
- contains approved operational content
- follows the organization's documentation standards

Large files should be reviewed to ensure they remain within operational limits.

## Schedules

- JSON
- Markdown
- Text

---

## Onboarding

- Markdown
- Text

---

## Program Documentation

- Markdown
- Text

---

Unsupported file types are ignored during ingestion.

---

# JSON Format

## FAQ JSON

FAQ JSON should contain a list of question and answer objects.

Example:

```json
[
    {
        "question": "How do I reset my password?",
        "answer": "Use the password reset page."
    },
    {
        "question": "Where are lectures uploaded?",
        "answer": "All lectures are available on the portal."
    }
]
```

The loader converts each item into readable text before ingestion.

---

## Schedule JSON

Schedules should be stored as a list of objects.

Example:

```json
[
    {
        "week": 1,
        "topic": "Introduction",
        "date": "2026-08-10"
    },
    {
        "week": 2,
        "topic": "Databases",
        "date": "2026-08-17"
    }
]
```

Each object is flattened into readable text during processing.

---

# Updating Existing Materials

When updating existing documentation:

1. Locate the original source file.
2. Modify only the approved source document.
3. Preserve existing filenames whenever possible.
4. Save the updated file.
5. Validate formatting.
6. Run the ingestion process.
7. Verify the updated material appears in the Knowledge Base.
8. Confirm the chatbot returns the updated information.

The original source files remain the authoritative version of all Knowledge Base content.

# Adding New Materials

To add new content:

1. Determine the appropriate material category.
2. Save the file using a descriptive filename.
3. Place the file in the correct directory.
4. Verify the file format is supported.
5. Confirm UTF-8 encoding.
6. Execute the ingestion process.
7. Verify successful ingestion.
8. Test chatbot responses using questions related to the new content.

# Re-Ingesting Materials

Administrators can reload approved materials using the Knowledge Base administration API.

```
POST /api/v1/kb/reingest
```

The request submits a collection of normalized `RawMaterial` objects for ingestion.

Successful ingestion returns statistics describing the processed materials.

---
# Duplicate Prevention

The ingestion process is designed to be safely re-runnable.

Re-running ingestion:

- updates modified documents
- processes newly added documents
- ignores duplicate content when appropriate
- does not require rebuilding the database

Administrators should always use the ingestion API rather than manually modifying indexed data.

# Onboarding a New Cohort

To initialize the Knowledge Base for a new cohort:

```
POST /api/v1/kb/cohorts/{cohort_id}/onboard
```

During onboarding the system:

1. Loads the cohort configuration.
2. Reads the configured materials directory.
3. Loads every approved document.
4. Assigns the cohort identifier to every material.
5. Ingests all materials into the Knowledge Base.

If the cohort configuration is invalid or no approved materials exist, onboarding fails with an error.

---

# Listing Current Materials

To review all currently indexed materials:

```
GET /api/v1/kb/materials
```

Verify:

- titles
- source paths
- cohort assignments
- expected document count

This endpoint should be used after every ingestion operation.

---

# Post-Ingestion Verification

After every update:

- confirm all expected materials are listed
- verify document counts
- confirm updated schedules appear correctly
- verify chatbot responses using representative questions
- check application logs for ingestion warnings or errors

Do not consider an update complete until these verification steps succeed.

# Retiring Materials

Materials that are no longer valid should be retired instead of manually removing records.

```
POST /api/v1/kb/retire/{material_id}
```

Retired materials are removed from the active knowledge base while preserving operational traceability.

---

# Removing Source Files

After a material has been retired:

- remove or archive the original source file if it is no longer required
- document the reason for retirement
- verify the chatbot no longer references the retired content

# Re-runnable Ingestion

The ingestion workflow is designed to support repeated execution.

Administrators may safely re-run ingestion after:

- correcting document content
- adding new files
- updating schedules
- revising FAQs
- onboarding additional cohorts

Re-running ingestion ensures the Knowledge Base reflects the latest approved content without requiring a complete system rebuild.

---

# Validation Checklist

Before ingestion:

- Materials are stored in the correct directory.
- Files use supported formats.
- JSON files are valid.
- Files are not empty.
- Cohort configuration is correct.

After ingestion:

- Materials appear in the materials list.
- Updated content is searchable.
- Chat responses reflect the latest information.
- No ingestion errors are recorded in the application logs.

---

# Operational Validation

Administrators should verify that:

- onboarding completes successfully
- ingestion statistics match expectations
- no duplicate documents appear
- no retired documents remain searchable
- the chatbot references the latest approved content

# Common Issues

## No Materials Found

Possible causes:

- incorrect materials directory
- empty directory
- unsupported file types

Resolution:

- verify the configured `materials_root`
- ensure approved files exist
- retry onboarding

---

## Invalid JSON

Symptoms:

- ingestion skips the file
- warning messages appear in logs

Resolution:

- validate JSON syntax
- correct formatting
- re-run ingestion

---

## Unsupported File Type

Unsupported extensions are skipped automatically.

Convert the file to one of the supported formats before ingestion.

---

## Empty File

Empty documents are ignored.

Add content before attempting another ingestion.

---
## Partial Ingestion

Symptoms:

- only some materials appear
- ingestion completes with warnings

Resolution:

- review ingestion logs
- verify every document uses a supported format
- correct invalid files
- rerun ingestion

## Duplicate Content

Symptoms:

- repeated chatbot responses
- duplicate search results

Resolution:

- verify duplicate source files do not exist
- retire obsolete materials
- rerun ingestion

## Cohort Onboarding Failure

Possible causes:

- invalid cohort configuration
- missing materials directory
- unreadable files

Resolution:

- verify cohort configuration
- confirm directory structure
- rerun onboarding

# Best Practices

- Maintain one source of truth for every document.
- Store only approved operational materials.
- Use descriptive filenames.
- Validate JSON before ingestion.
- Review ingestion logs after every update.
- Verify chatbot responses after every ingestion.
- Retire outdated materials instead of leaving obsolete information available.
- Keep schedules synchronized with official program information.
- Archive obsolete source documents when appropriate.
- Perform regular audits of the Knowledge Base.

# Related Documentation

For additional operational procedures, refer to:

- `docs/admin_guide.md`
- `docs/runbook.md`