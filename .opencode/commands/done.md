---
description: Gate a change — one dispatch runs the DoD commands + invariant audit and reports the verdict
---

Run the completion gate for the change referenced by `$ARGUMENTS`. If `$ARGUMENTS` is empty, gate the working tree as-is and say so.

## 1. Collect the review inputs (run once, reuse)

!`git status --short`
!`git diff`
!`git diff --cached`

## 2. Dispatch the gate

- **`review`** — self-contained prompt: "Gate the current uncommitted change. Changed files: <status output>. Diff: <git diff + git diff --cached outputs>. Run the full Definition of Done (scope mypy --strict to changed Python files under backend/; if none, run format/lint/full suite only) and audit the diff against the six invariants from AGENTS.md. Report in your standard REVIEW format."

The agent is read-only. Fix nothing during this step. Do not commit whatever it says.

## 3. Gate on the report

- **VERDICT: DONE** (all DoD commands pass; no NEW invariant violations outside the known debt table) → done.
- **VERDICT: NOT DONE / VIOLATION / FAIL / BLOCKED** → paste the failing output back to the user verbatim and stop. Do not loop more than 3 total attempts; on the 3rd failure, stop and ask for direction (AGENTS.md escalation).

Report: what was gated and the agent's verdict (one line).
