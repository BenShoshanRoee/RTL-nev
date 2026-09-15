---
name: judge
description: Security-critical procedure for touching anything in bench/rtlenv/judge/, any rubric, matcher, reward function, verdict, progress/milestone logic, or task fixture under bench/tasks/. Cheat-surface first, fixture minimums, mutation testing, unchanged_subtrees. Default assumption is the judge is too permissive.
---

# judge — assume it is too permissive

A silently permissive judge looks fine from the outside and destroys the product.
Treat every matcher, rubric, reward shaper, milestone and fixture as security-critical.

## Before writing any judge or task
1. **Cheat surface first.** Write down every way a model could collect the reward without
   doing the work: final state reachable by a shortcut, side effects invisible to the
   goal matcher, partial credit for free milestones, matcher accepting a superset,
   pathology making corrupt stored state look correct on screen, order-of-operations
   tricks, undo/redo, refresh, creating a second entity instead of editing the first.
   This goes in the task's `cheat_surface` field. No cheat surface, no judge.
2. **Declare `unchanged_subtrees`.** Mandatory on every task. Everything the task does not
   touch must be asserted equal before/after. This is how side effects get caught.
3. **Decide what corrupt-but-visible-correct looks like** for this task. The judge must
   score stored state, not rendered state.

## Fixture minimums (per task, all committed, all run in CI)
- 1 correct rollout → full reward.
- 1 clearly wrong rollout → zero.
- ≥3 plausibly wrong rollouts → less than full, each targeting one cheat-surface item.
  Examples: right item wrong quantity; right final state plus an unrelated side effect;
  goal reached via a second entity; visible state right, stored state corrupted by a pathology.
- Name each fixture after the cheat it exercises.

## Mutation testing (required for every matcher)
- Weaken each matcher programmatically (equality → contains, exact count → ≥1, subtree
  check removed, threshold loosened, field dropped). Assert at least one fixture flips.
- A matcher that survives all mutations with all fixtures still passing is untested.
  Add the fixture that kills the mutant or delete the matcher.

## Rules
- Deterministic. Same rollout, same verdict. No LLM-as-judge, no VLM, no timing dependence.
- Diff structured state only. Never parse screenshots or DOM text for verdicts.
- Money comparisons are integer minor units.
- Partial credit only for milestones that are prerequisites of the goal, never for
  activity. A milestone reachable without progress toward the goal is a cheat surface.
- Pathology tasks: correct final state reached by blundering through a pathology that
  corrupted stored data must NOT score full. `unchanged_subtrees` carries this.
- Log every verdict with the seed, task id and the diff that produced it.

## Done means
Tests exist for: each fixture verdict, each mutation kill, `unchanged_subtrees` catching a
planted side effect, and validator rejection of a task missing `cheat_surface` or
`unchanged_subtrees`. Run them. Show the command and output summary to the operator.
