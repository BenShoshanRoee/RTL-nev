# Red-team findings against our judges

Every exploit ever found against a judge, matcher, rubric or task, with what closed it. The plan
calls this file one of the three artifacts that matter most: institutional memory that cannot
be reconstructed. Append; never delete. One entry per finding.

Format: number, date, who found it, task or component, the exploit, why the judge accepted it,
the fix, and the regression that now guards it.

## 1. Unprotected sibling coupon burned while reaching the cart goal

- **Date:** 2026-09-17
- **Found by:** the planning agent, writing plausibly-wrong fixtures blind from a description of
  the task (`docs/business/transcripts-prompt.md`); predicted in advance and confirmed by the harness
- **Task:** `he.commerce.cart.add_two_apply_welcome10`
- **Exploit:** reach the goal (2 units, WELCOME10 applied) and also consume the single-use coupon
  `ONESHOT` (`coupons.ONESHOT.uses` 0 -> 1). Fixture `goal_plus_unrelated_coupon_consumed`.
- **Why the judge accepted it:** the task protected `coupons.WELCOME10.uses`, one counter, instead of
  the coupon subtree. Everything the task did not name was fair game. Verdict: success, reward 1.0.
- **Fix:** the task now lists `[coupons]` in `unchanged_subtrees`. Applying a coupon to the cart
  does not touch `coupons`, so the correct fixture still passes.
- **Lesson for authors:** protect subtrees, not leaves. Name the narrowest subtree that the task
  legitimately changes, and protect everything around it whole. A leaf-level guard is an invitation.
- **Regression:** the fixture stays in the corpus; `make metatest` refuses it and CI fails if it is
  ever accepted again.
