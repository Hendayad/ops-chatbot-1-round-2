"""Tests for multi-cohort isolation and cohort configuration (M10 / F3.4)."""

import json
import os
import shutil
import tempfile

import pytest

from app.cohorts.config import CohortConfigLoader
from app.cohorts.scope import (
    cohort_of,
    find_leaked_items,
    is_same_cohort,
    normalize_cohort,
    scope_by_cohort,
    validate_cohort_access,
)


class _Chunk:
    """Minimal stand-in for a retrieved chunk, which carries cohort as an attribute."""

    def __init__(self, cohort: str) -> None:
        self.cohort = cohort


# --- normalize_cohort ---


@pytest.mark.parametrize(
    "value,expected",
    [("cohort-a", "cohort-a"), ("  cohort-a  ", "cohort-a"), ("", ""), ("   ", ""), (None, "")],
)
def test_normalize_cohort(value, expected):
    """Whitespace is stripped and every empty form collapses to an empty string."""
    assert normalize_cohort(value) == expected


# --- is_same_cohort ---


def test_is_same_cohort_matches_identical_cohorts():
    assert is_same_cohort("cohort-a", "cohort-a") is True


def test_is_same_cohort_ignores_surrounding_whitespace():
    assert is_same_cohort("  cohort-a ", "cohort-a") is True


def test_is_same_cohort_rejects_different_cohorts():
    assert is_same_cohort("cohort-a", "cohort-b") is False


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_is_same_cohort_rejects_empty_on_either_side(empty):
    """Fail closed: an absent cohort must never match anything."""
    assert is_same_cohort(empty, "cohort-a") is False
    assert is_same_cohort("cohort-a", empty) is False


# --- cohort_of ---


def test_cohort_of_reads_top_level_cohort_key():
    assert cohort_of({"cohort": "cohort-a"}) == "cohort-a"


def test_cohort_of_reads_cohort_id_key():
    assert cohort_of({"cohort_id": "cohort-a"}) == "cohort-a"


def test_cohort_of_reads_nested_metadata():
    assert cohort_of({"metadata": {"cohort": "cohort-a"}}) == "cohort-a"
    assert cohort_of({"metadata": {"cohort_id": "cohort-b"}}) == "cohort-b"


def test_cohort_of_reads_object_attribute():
    assert cohort_of(_Chunk("cohort-a")) == "cohort-a"


def test_cohort_of_returns_empty_when_absent():
    assert cohort_of({"id": 1}) == ""
    assert cohort_of({"metadata": {}}) == ""


# --- scope_by_cohort ---


def test_scope_by_cohort_keeps_only_matching_documents():
    docs = [
        {"id": 1, "cohort": "cohort-a"},
        {"id": 2, "cohort": "cohort-b"},
        {"id": 3, "metadata": {"cohort": "cohort-a"}},
    ]
    result = scope_by_cohort(docs, "cohort-a")

    assert [doc["id"] for doc in result] == [1, 3]


def test_scope_by_cohort_excludes_unscoped_documents():
    """A document with no cohort belongs to nobody and must be dropped."""
    docs = [{"id": 1, "cohort": "cohort-a"}, {"id": 2}]
    result = scope_by_cohort(docs, "cohort-a")

    assert [doc["id"] for doc in result] == [1]


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_scope_by_cohort_returns_nothing_for_missing_cohort(missing):
    """The critical leak guard: no cohort means no results, never all results."""
    docs = [{"id": 1, "cohort": "cohort-a"}, {"id": 2, "cohort": "cohort-b"}]

    assert scope_by_cohort(docs, missing) == []


def test_scope_by_cohort_works_on_chunk_objects():
    chunks = [_Chunk("cohort-a"), _Chunk("cohort-b")]
    result = scope_by_cohort(chunks, "cohort-a")

    assert len(result) == 1
    assert result[0].cohort == "cohort-a"


# --- find_leaked_items ---


def test_find_leaked_items_reports_foreign_documents():
    docs = [{"id": 1, "cohort": "cohort-a"}, {"id": 2, "cohort": "cohort-b"}]
    leaked = find_leaked_items(docs, "cohort-a")

    assert [doc["id"] for doc in leaked] == [2]


def test_find_leaked_items_empty_when_all_scoped():
    docs = [{"id": 1, "cohort": "cohort-a"}]

    assert find_leaked_items(docs, "cohort-a") == []


# --- validate_cohort_access ---


def test_validate_cohort_access_allows_same_cohort():
    assert validate_cohort_access("cohort-a", "cohort-a") is True


def test_validate_cohort_access_denies_cross_cohort():
    assert validate_cohort_access("cohort-a", "cohort-b") is False


@pytest.mark.parametrize("empty", [None, ""])
def test_validate_cohort_access_denies_missing_user_cohort(empty):
    assert validate_cohort_access(empty, "cohort-a") is False


# --- CohortConfigLoader ---


@pytest.fixture
def temp_dir():
    """Yield a private temporary directory and remove it afterwards.

    Uses tempfile rather than pytest's tmp_path fixture because this Windows
    environment denies access to pytest's own temporary root.
    """
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def config_file(temp_dir):
    """Write a two-cohort configuration file and return its path."""
    path = os.path.join(temp_dir, "cohorts_config.json")
    with open(path, "w", encoding="utf-8") as config:
        json.dump(
            {
                "cohort-a": {"name": "July 2026", "materials_root": "materials/cohort-a"},
                "cohort-b": {"name": "Sept 2026", "materials_root": ""},
            },
            config,
        )
    return path


def test_list_cohorts_returns_configured_cohorts(config_file):
    loader = CohortConfigLoader(config_file)

    assert loader.list_cohorts() == ["cohort-a", "cohort-b"]


def test_load_cohort_config_returns_entry(config_file):
    loader = CohortConfigLoader(config_file)
    config = loader.load_cohort_config("cohort-a")

    assert config["cohort_id"] == "cohort-a"
    assert config["name"] == "July 2026"
    assert config["materials_root"] == "materials/cohort-a"


def test_load_cohort_config_returns_empty_template_for_unknown_cohort(config_file):
    loader = CohortConfigLoader(config_file)
    config = loader.load_cohort_config("cohort-zzz")

    assert config == {"cohort_id": "cohort-zzz", "name": "", "materials_root": ""}


def test_is_known_cohort(config_file):
    loader = CohortConfigLoader(config_file)

    assert loader.is_known_cohort("cohort-a") is True
    assert loader.is_known_cohort("cohort-zzz") is False
    assert loader.is_known_cohort("") is False


def test_missing_config_file_is_treated_as_no_cohorts(temp_dir):
    """A missing file must not raise - it means nothing is configured yet."""
    loader = CohortConfigLoader(os.path.join(temp_dir, "does_not_exist.json"))

    assert loader.list_cohorts() == []
    assert loader.is_known_cohort("cohort-a") is False


def test_malformed_config_file_is_treated_as_no_cohorts(temp_dir):
    """Invalid JSON must degrade safely instead of crashing the application."""
    path = os.path.join(temp_dir, "broken.json")
    with open(path, "w", encoding="utf-8") as broken:
        broken.write("{not valid json")
    loader = CohortConfigLoader(path)

    assert loader.list_cohorts() == []


# --- The isolation evaluation must run in CI, not only by hand ---


def test_isolation_eval_covers_the_real_retrieval_and_answer_paths():
    """The eval is a deliverable, so a regression in it must fail the suite."""
    from evals.cohort_isolation import run_evaluation

    reports = run_evaluation()
    failed = [report["case"] for report in reports if not report["passed"]]

    assert not failed, f"cross-cohort leakage detected in: {failed}"
    # Guard against the eval silently shrinking back to pure-function cases.
    covered = {report["case"] for report in reports}
    assert any(case.startswith("retriever_") for case in covered)
    assert any(case.startswith("answer_node_") for case in covered)


def test_adversarial_cohort_leakage_suite_passes():
    """Run the adversarial leakage suite to verify cross-cohort queries are blocked."""
    from evals.adversarial_cohort_leakage import run_adversarial_suite

    report = run_adversarial_suite()
    assert report["failed_cases"] == 0
    assert report["isolation_success_rate"] == 100.0


# --- Config-driven gating: which cohorts may be served at all ---


def test_any_cohort_is_servable_when_nothing_is_configured(monkeypatch):
    """An empty config means single-cohort mode, not "refuse everything"."""
    from app.cohorts import config as config_module

    monkeypatch.setattr(config_module.cohort_config, "config_path", "does_not_exist.json")

    assert config_module.cohort_gating_enabled() is False
    assert config_module.is_servable_cohort("cohort-a") is True


def test_unknown_cohort_is_refused_once_cohorts_are_configured(monkeypatch, config_file):
    from app.cohorts import config as config_module

    monkeypatch.setattr(config_module.cohort_config, "config_path", config_file)

    assert config_module.cohort_gating_enabled() is True
    assert config_module.is_servable_cohort("cohort-a") is True
    assert config_module.is_servable_cohort("cohort-zzz") is False


def test_empty_cohort_is_never_servable(monkeypatch, config_file):
    from app.cohorts import config as config_module

    monkeypatch.setattr(config_module.cohort_config, "config_path", config_file)

    assert config_module.is_servable_cohort(None) is False
    assert config_module.is_servable_cohort("") is False


def test_answer_node_refuses_a_cohort_that_is_not_configured(monkeypatch, config_file):
    """The config gate must run before retrieval, not after."""
    import asyncio

    from app.cohorts import config as config_module
    from app.graph.nodes.answer import generate_grounded_answer

    monkeypatch.setattr(config_module.cohort_config, "config_path", config_file)

    outcome = asyncio.run(generate_grounded_answer("when is the deadline", cohort="cohort-zzz"))

    assert outcome.grounded is False
    assert outcome.escalation_reason == "unknown_cohort"


def test_a_new_cohort_needs_only_a_config_entry(temp_dir):
    """F3.4 target: launching a cohort is config + materials, with no code change."""
    path = os.path.join(temp_dir, "cohorts.json")
    with open(path, "w", encoding="utf-8") as config:
        json.dump({"cohort-a": {"name": "A", "materials_root": "materials/a"}}, config)
    loader = CohortConfigLoader(path)
    assert loader.list_cohorts() == ["cohort-a"]

    with open(path, "w", encoding="utf-8") as config:
        json.dump(
            {
                "cohort-a": {"name": "A", "materials_root": "materials/a"},
                "cohort-c": {"name": "C", "materials_root": "materials/c"},
            },
            config,
        )

    # Same loader instance, no restart: the file is re-read on every call.
    assert loader.list_cohorts() == ["cohort-a", "cohort-c"]
    assert loader.load_cohort_config("cohort-c")["materials_root"] == "materials/c"
