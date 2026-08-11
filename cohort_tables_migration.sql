-- Run this once in the Supabase SQL Editor, BEFORE deploying the new backend
-- code that reads cohorts from the database instead of cohorts_config.json.
--
-- What this does:
--   1. Creates two new tables: "cohort" and "cohortmaterial".
--   2. Seeds them with the exact same 4 cohorts (and their materials) that
--      are currently in cohorts_config.json, so nothing changes for
--      existing learners/cohorts the moment this runs.
--
-- This does NOT touch any existing table. It is safe to run on the live
-- database -- it only adds two new, currently-unused tables. The app will
-- keep reading cohorts_config.json as normal until the new backend code is
-- deployed afterwards.

BEGIN;

CREATE TABLE cohort (
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    cohort_id       VARCHAR(100) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    materials_root  VARCHAR(1000) NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    description     VARCHAR(2000),
    project         VARCHAR(200),
    start_date      DATE,
    end_date        DATE,
    updated_at      TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (cohort_id)
);

CREATE TABLE cohortmaterial (
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    id          SERIAL PRIMARY KEY,
    cohort_id   VARCHAR(100) NOT NULL REFERENCES cohort (cohort_id),
    title       VARCHAR(300) NOT NULL,
    source      VARCHAR(1000) NOT NULL,
    type        VARCHAR(50) NOT NULL,
    CONSTRAINT uq_cohort_material_source UNIQUE (cohort_id, source)
);

CREATE INDEX ix_cohortmaterial_cohort_id ON cohortmaterial (cohort_id);

-- ### seed data, matching cohorts_config.json as committed today ###

INSERT INTO cohort (cohort_id, name, materials_root, enabled, description, project, start_date, end_date)
VALUES
    ('cohort-a', 'Cohort A', 'materials/cohort-a', true, NULL, NULL, NULL, NULL),
    ('cohort-b', 'Cohort B', 'materials/cohort-b', true, NULL, NULL, NULL, NULL),
    ('cohort-d', 'Cohort D', 'materials/cohort-d', true,
        'This is a new cohort with letter ''D''', 'AI system', '2026-08-07', '2026-08-31'),
    ('cohort-demo', 'Cohort Demo', 'materials/cohort-a', true,
        'Demo cohort for hamza/hend test accounts, mapped to Cohort A''s approved materials.',
        NULL, NULL, NULL);

INSERT INTO cohortmaterial (cohort_id, title, source, type)
VALUES
    ('cohort-a', 'Cohort A FAQ', 'faqs/faq.md', 'faq'),
    ('cohort-a', 'Cohort A Schedule', 'schedules/schedule.md', 'schedule'),
    ('cohort-a', 'Cohort A Getting Started', 'onboarding/getting-started.md', 'onboarding'),
    ('cohort-a', 'Cohort A Learner Handbook', 'docs/handbook.md', 'program_doc'),
    ('cohort-b', 'Cohort B FAQ', 'faqs/faq.md', 'faq'),
    ('cohort-b', 'Cohort B Schedule', 'schedules/schedule.md', 'schedule'),
    ('cohort-b', 'Cohort B Getting Started', 'onboarding/getting-started.md', 'onboarding'),
    ('cohort-b', 'Cohort B Learner Handbook', 'docs/handbook.md', 'program_doc'),
    ('cohort-d', 'AI Track rules', 'ai_track_rules.txt', 'program_doc'),
    ('cohort-d', 'Agent Project', 'ai_operations_support_agent_project_description.txt', 'program_doc'),
    ('cohort-demo', 'Cohort Demo FAQ', 'faqs/faq.md', 'faq'),
    ('cohort-demo', 'Cohort Demo Schedule', 'schedules/schedule.md', 'schedule'),
    ('cohort-demo', 'Cohort Demo Getting Started', 'onboarding/getting-started.md', 'onboarding'),
    ('cohort-demo', 'Cohort Demo Learner Handbook', 'docs/handbook.md', 'program_doc');

COMMIT;

-- After running this, verify with:
--   SELECT cohort_id, name, start_date, end_date FROM cohort ORDER BY cohort_id;
--   SELECT cohort_id, count(*) FROM cohortmaterial GROUP BY cohort_id ORDER BY cohort_id;
-- You should see the 4 cohorts above, with 4 materials each for
-- cohort-a/b/demo and 2 for cohort-d.
