"""At-risk signal computation: pure threshold evaluation of a LearnerProgress snapshot (PRD F2.3).

Deliberately free of I/O and side effects -- app.atrisk.detector calls this
once per learner and wraps the result in a DetectionResult. Being a pure
function of (progress, thresholds) is what lets the detector (and the
scheduled job built on top of it) be re-run safely: the same inputs always
produce the same signals.

This evaluates against the shared app.schemas.progress.LearnerProgress
contract (owned by the platform team, not this slice) -- specifically its
computed properties (progress_ratio, days_inactive, average_feedback_score)
rather than raw stored fields, since those properties already encode the
"no signal yet" cases (no tasks assigned, never active, no feedback left)
that this module must not misread as risk signals.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.progress import LearnerProgress


class AtRiskSignals(BaseModel):
    """Individual risk indicators for one learner, plus the aggregate verdict."""

    missed_deadlines: bool
    inactive: bool
    low_progress: bool
    low_feedback: bool

    score: int
    at_risk: bool


class RiskThresholds(BaseModel):
    """Configurable thresholds a learner's progress is evaluated against.

    Field names/scales match the shared LearnerProgress computed properties:
    inactivity_days against days_inactive (float days), minimum_progress_ratio
    against progress_ratio (0-1 scale, not percent), minimum_feedback_score
    against average_feedback_score (0-5 scale).
    """

    missed_deadlines: int = 2
    inactivity_days: float = 7
    minimum_progress_ratio: float = 0.5
    minimum_feedback_score: float = 3


def compute_risk_signals(
    progress: LearnerProgress,
    thresholds: RiskThresholds,
) -> AtRiskSignals:
    """Evaluate one learner's progress snapshot against the given thresholds.

    Each indicator is independent; `score` is how many tripped (0-4), and
    `at_risk` is True as soon as any one of them trips.

    A learner with no recorded activity yet (`days_inactive is None`) and a
    learner who hasn't left feedback yet (`average_feedback_score is None`)
    are never penalized for those signals -- consistent with how
    LearnerProgress itself treats "no data yet" as no signal, not as a bad
    score, this function does the same rather than defaulting an unknown to
    the worst case.

    Args:
        progress: The learner's progress snapshot to evaluate.
        thresholds: The thresholds to evaluate it against.

    Returns:
        AtRiskSignals with each indicator plus the aggregate score/verdict.
    """
    missed = progress.missed_deadlines >= thresholds.missed_deadlines
    inactive = progress.days_inactive is not None and progress.days_inactive >= thresholds.inactivity_days
    low_progress = progress.progress_ratio < thresholds.minimum_progress_ratio
    low_feedback = (
        progress.average_feedback_score is not None
        and progress.average_feedback_score < thresholds.minimum_feedback_score
    )

    score = sum([missed, inactive, low_progress, low_feedback])
    at_risk = score > 0

    return AtRiskSignals(
        missed_deadlines=missed,
        inactive=inactive,
        low_progress=low_progress,
        low_feedback=low_feedback,
        score=score,
        at_risk=at_risk,
    )
