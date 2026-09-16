"""Public API of the state-diff judge (contract version in JUDGE_CONTRACT_VERSION)."""

from rtlenv.judge.core import JUDGE_CONTRACT_VERSION, Rollout, judge
from rtlenv.judge.matchers import KINDS, MatcherSpecError, MatchResult, parse, strict_equal
from rtlenv.judge.verdict import FIELDS, Verdict

__all__ = [
    "FIELDS",
    "JUDGE_CONTRACT_VERSION",
    "KINDS",
    "MatchResult",
    "MatcherSpecError",
    "Rollout",
    "Verdict",
    "judge",
    "parse",
    "strict_equal",
]
