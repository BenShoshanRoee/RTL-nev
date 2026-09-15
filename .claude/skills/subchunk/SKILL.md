---
name: subchunk
description: Outer loop for starting ANY sub-chunk from rtl-implementation-plan.md. Use whenever the operator says "start X.Y.Z", "next sub-chunk", "continue the plan", or names a sub-chunk. Reads progress.md, greps only the relevant plan section, tests first, verifies, updates progress.md, stops.
---

# subchunk — the outer loop

Runs on every sub-chunk. `verify` always runs at step 7. `judge`, `rtl`, `provenance`,
`determinism` are triggered by the file paths you are about to touch, not by the
sub-chunk's name. Check paths at step 3.

## Procedure
1. **State.** Read `progress.md`. Confirm the current sub-chunk id. If a previous sub-chunk
   is "In progress", finish or explicitly re-scope it before starting a new one.
2. **Spec.** Locate the section, read only it:
   `rg -n "Sub-chunk X.Y.Z" docs/plan/rtl-implementation-plan.md` then `sed -n START,ENDp` up to the
   next `#### Sub-chunk`. Do not read neighbouring sections unless a Dependency points there.
3. **Restate** to the operator in ≤15 lines: Objective, Files (exact paths), Test Criteria as
   a checklist, Dependencies (confirm each is in `progress.md` Completed), Manual Steps.
   List which of `judge` / `rtl` / `provenance` / `determinism` apply and why.
   If more than ~5 files: list the plan and WAIT for confirmation.
4. **Check the plan.** If a criterion is unverifiable, a dependency is missing, or the order
   is wrong: say so, propose the fix, wait. Never deviate silently.
5. **Failing tests first.** Write the tests that encode every Test Criterion. Run them.
   Show the operator they fail (summarised, with the command).
6. **Implement** to make them pass. Touch only the declared Files. Ask before adding a
   dependency (licence allowlist) or touching anything else.
7. **Run `verify`.** Every plan criterion becomes a runnable command with expected output.
   Run each. Record actual output. Anything that needs the operator's key, GPU, or judgement
   is a MANUAL step, stated explicitly.
8. **Update `progress.md`** (end only): move the sub-chunk to Completed with the exact
   verification commands; set the next sub-chunk as Current; append Decisions, Deviations,
   Known debt as applicable; list Manual steps under Blocked.
9. **Report and stop.** Files touched with line counts, the verification commands to run,
   what failure would look like, what is needed for the next sub-chunk. Do not start it.

## Never
- Read the plan in full. Read progress.md at the start only, never rewrite it there.
- Say "should work". Paste large outputs. Start the next sub-chunk in the same session.
