"""Public API of the state-diff judge (contract version in JUDGE_CONTRACT_VERSION)."""

from rtlenv.judge.core import JUDGE_CONTRACT_VERSION, Rollout, judge
from rtlenv.judge.matchers import KINDS, MatcherSpecError, MatchResult, parse, strict_equal
from rtlenv.judge.progress import ProgressResult, compute_progress, replay
from rtlenv.judge.reward import DEFAULT_WEIGHTS, RewardConfigError, compute_reward, validate_weights
from rtlenv.judge.verdict import FIELDS, Verdict

__all__ = [
    "FIELDS",
    "JUDGE_CONTRACT_VERSION",
    "KINDS",
    "MatchResult",
    "MatcherSpecError",
    "ProgressResult",
    "RewardConfigError",
    "Rollout",
    "DEFAULT_WEIGHTS",
    "compute_progress",
    "compute_reward",
    "replay",
    "validate_weights",
    "Verdict",
    "judge",
    "parse",
    "strict_equal",
]
