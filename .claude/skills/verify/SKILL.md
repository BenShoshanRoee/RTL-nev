---
name: verify
description: Use at the end of every sub-chunk and whenever writing acceptance criteria or verification steps. Turns each plan criterion into a runnable command with expected output and a description of what failure looks like. The operator never reads code; they run commands.
---

# verify — verification is the deliverable

The operator does not read TypeScript and does not review diffs. If correctness can only
be judged by reading code, the sub-chunk is structured wrong. Restructure it.

## Procedure
1. List every Test Criterion from the sub-chunk's plan section, verbatim.
2. For each, write ONE command the operator can paste. Prefer `make`, `pnpm test`,
   `uv run pytest`, `rg`. No multi-step recipes; wrap them in a script under `tools/` or a
   Makefile target if needed.
3. For each command state:
   - **Expected output** (exact line, count, or exit code)
   - **What failure looks like** (the message they would see)
   - **What it proves** (one sentence)
4. Run every command yourself first. Paste only a short summary of actual output. If actual
   differs from expected, the sub-chunk is not done.
5. Include a **negative check** wherever the criterion is a gate: break it deliberately
   (add `Math.random()`, drop `unchanged_subtrees`, add a physical CSS property, add an
   unlisted content file) and show the gate fails with a named error. Then revert.
6. Anything needing the operator's API key, GPU, spend, or human judgement: list under
   **MANUAL** with the exact command and what to look for. Never claim it passed.
7. Add the commands to `progress.md` "Verified by" once the operator has run them.

## Output format to the operator
```
## Verification for X.Y.Z
| # | Criterion | Command | Expected | Failure looks like |
|---|---|---|---|---|
...
MANUAL:
- 🔧 <step>: <command or action>; look for <signal>
```

## Never
- "Tests pass" without the command. "Should work." Asking the operator to read a file.
- A criterion with no command. A command you did not run.
