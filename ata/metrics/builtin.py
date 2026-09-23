"""Built-in metrics, registered into the default registry on import.

The six original aggregate metrics are thin wrappers around the pure functions in
``core`` (so their logic and output shape are unchanged). ``LatencyMetric`` and
``TurnErrorRateMetric`` demonstrate the hook API: they accumulate per-turn state
in ``on_turn`` and emit it in ``compute``.
"""

from __future__ import annotations

from pydantic import BaseModel

from ata.metrics.base import Metric, MetricContext
from ata.metrics.core import (
    compute_boundary_adherence,
    compute_constraint_violations,
    compute_conversation_efficiency,
    compute_recovery_behavior,
    compute_task_completion,
    compute_verification_rate,
)
from ata.metrics.registry import register
from ata.models.suite import Scenario
from ata.models.transcript import Turn

# ── The six aggregate metrics (wrap the existing pure functions) ──────────────

@register
class TaskCompletion(Metric):
    name = "task_completion"
    description = "Fraction of positive scenarios the agent completed."

    def compute(self, ctx: MetricContext):
        return compute_task_completion(ctx.scenarios, ctx.verdicts)


@register
class BoundaryAdherence(Metric):
    name = "boundary_adherence"
    description = "Fraction of negative scenarios the agent correctly refused."

    def compute(self, ctx: MetricContext):
        return compute_boundary_adherence(ctx.scenarios, ctx.verdicts)


@register
class VerificationRate(Metric):
    name = "verification_rate"
    description = "Fraction of probe-verified successes that held on re-check."

    def compute(self, ctx: MetricContext):
        return compute_verification_rate(ctx.scenarios, ctx.verdicts)


@register
class ConstraintViolations(Metric):
    name = "constraint_violations"
    description = "Per-constraint violation rate, most-violated first."

    def compute(self, ctx: MetricContext):
        return compute_constraint_violations(ctx.scenarios, ctx.verdicts)


@register
class RecoveryBehavior(Metric):
    name = "recovery_behavior"
    description = "Quality breakdown of correct refusals (clean vs. confused/error/leak)."

    def compute(self, ctx: MetricContext):
        return compute_recovery_behavior(ctx.scenarios, ctx.verdicts)


@register
class ConversationEfficiency(Metric):
    name = "conversation_efficiency"
    description = "Average turns to completion / to refusal."

    def compute(self, ctx: MetricContext):
        return compute_conversation_efficiency(ctx.scenarios, ctx.verdicts, ctx.transcripts)


# ── Hook-based metrics ────────────────────────────────────────────────────────

def _percentile(sorted_values: list[int], p: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    k = (len(sorted_values) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    if lo == hi:
        return float(sorted_values[lo])
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


class LatencyResult(BaseModel):
    turns: int
    avg_ms: float | None
    min_ms: int | None
    max_ms: int | None
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None


@register
class LatencyMetric(Metric):
    name = "latency"
    description = "Agent response latency across all non-error turns (ms)."

    def __init__(self) -> None:
        self._samples: list[int] = []

    def on_turn(self, ctx: MetricContext, scenario: Scenario, turn: Turn, index: int) -> None:
        if turn.error is None:
            self._samples.append(turn.latency_ms)

    def compute(self, ctx: MetricContext) -> LatencyResult:
        s = sorted(self._samples)
        n = len(s)
        return LatencyResult(
            turns=n,
            avg_ms=sum(s) / n if n else None,
            min_ms=s[0] if n else None,
            max_ms=s[-1] if n else None,
            p50_ms=_percentile(s, 50),
            p95_ms=_percentile(s, 95),
            p99_ms=_percentile(s, 99),
        )


class TurnErrorRateResult(BaseModel):
    total_turns: int
    error_turns: int
    rate: float


@register
class TurnErrorRateMetric(Metric):
    name = "turn_error_rate"
    description = "Fraction of turns that returned an adapter/transport error."

    def __init__(self) -> None:
        self._total = 0
        self._errors = 0

    def on_turn(self, ctx: MetricContext, scenario: Scenario, turn: Turn, index: int) -> None:
        self._total += 1
        if turn.error is not None:
            self._errors += 1

    def compute(self, ctx: MetricContext) -> TurnErrorRateResult:
        return TurnErrorRateResult(
            total_turns=self._total,
            error_turns=self._errors,
            rate=self._errors / self._total if self._total else 0.0,
        )


# ── Voice metric (thin proof; template for the thick voice metrics) ───────────

class TimeToFirstAudioResult(BaseModel):
    turns: int
    avg_ms: float | None
    p50_ms: float | None
    p95_ms: float | None


@register
class TimeToFirstAudioMetric(Metric):
    """How long after the user speaks the agent starts talking back.

    Reads ``turn.voice.time_to_first_audio_ms``, recorded by voice adapters. On a
    text run no turn carries ``voice``, so this reports zero samples. This is the
    first metric to consume ``VoiceMeta`` and the template for the rest (barge-in,
    talk-over, silence recovery) — each a new @register'd metric, no engine change.
    """

    name = "time_to_first_audio"
    description = "Agent time-to-first-audio across voice turns (ms)."

    def __init__(self) -> None:
        self._samples: list[int] = []

    def on_turn(self, ctx: MetricContext, scenario: Scenario, turn: Turn, index: int) -> None:
        if turn.error is None and turn.voice and turn.voice.time_to_first_audio_ms is not None:
            self._samples.append(turn.voice.time_to_first_audio_ms)

    def compute(self, ctx: MetricContext) -> TimeToFirstAudioResult:
        s = sorted(self._samples)
        n = len(s)
        return TimeToFirstAudioResult(
            turns=n,
            avg_ms=sum(s) / n if n else None,
            p50_ms=_percentile(s, 50),
            p95_ms=_percentile(s, 95),
        )
