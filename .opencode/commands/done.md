---
description: Gate a change or plan task — one dispatch runs the DoD commands + invariant audit; tick the box only if it passes
---

Run the completion gate for the change or task referenced by `$ARGUMENTS` (e.g. `/done Task 8`, `/done 12`, or `/done the auth fix`), then tick the plan box only if the gate passes. If `$ARGUMENTS` is empty and the change doesn't obviously map to a plan task, say so and gate the working tree as-is.

## 1. Resolve the task box (skip if not a plan task)

```
grep -rn "### Task\|## Task" docs/superpowers/plans/ | grep -i "$ARGUMENTS"
```

- Exactly one match → proceed.
- Zero matches → no plan task involved; gate the working tree directly.
- Multiple matches, or the box is already ticked → say so and stop. Do not guess. (A bare number can be ambiguous across plan files — the grep tells you.)

## 2. Collect the review inputs (run once, reuse)

!`git status --short`
!`git diff`
!`git diff --cached`

## 3. Dispatch the gate

- **`review`** — self-contained prompt: "Gate the current uncommitted change. Changed files: <status output>. Diff: <git diff + git diff --cached outputs>. Run the full Definition of Done (scope mypy --strict to changed Python files under backend/; if none, run format/lint/full suite only) and audit the diff against the six invariants from AGENTS.md. Report in your standard REVIEW format."

The agent is read-only. Fix nothing during this step. Do not commit whatever it says.

## 4. Gate on the report

- **VERDICT: DONE** (all DoD commands pass; no NEW invariant violations outside the known debt table) → step 5.
- **VERDICT: NOT DONE / VIOLATION / FAIL / BLOCKED** → **do not tick.** Paste the failing output back to the user verbatim and stop. Do not loop more than 3 total attempts; on the 3rd failure, stop and ask for direction (AGENTS.md escalation).

## 5. Tick + commit (plan tasks only)

- Flip the task's `- [ ]` to `- [x]` in the plan file under `docs/superpowers/plans/` (`docs/**` is writable).
- Per AGENTS.md "Tick the plan box in the same commit": if the task produced uncommitted code changes, stage the plan file with them and commit together. If nothing is staged, commit the tick alone as `chore: tick <task>`.

Report: what was gated, the agent's verdict (one line), whether the box was ticked, and the commit hash if one was made.
