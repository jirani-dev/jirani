# Agent Setup — Install and Use OpenCode

How to get a working OpenCode agent for the Jirani repo: install it, connect model access, understand what the repo configures, and see example usage. Prerequisite: the environment setup in `docs/onboarding.md` (uv, Docker, node/npm, graphify, pre-commit, gh) is done. The rules the agent operates under live in the `AGENTS.md` files; they win wherever this guide and they differ.

## 1. Install OpenCode

The project uses OpenCode **V2**; the npm package is `@opencode/cli` — the same one CI installs (`.github/workflows/ai-review.yml`). The older `opencode-ai` package is V1; don't use it.

```bash
npm install -g @opencode/cli      # or: curl -fsSL https://opencode.ai/v2/install | bash
                                  # or: brew install anomalyco/tap/opencode-v2
opencode --version
```

Windows: V2 does not support Windows package managers — download a standalone binary from the [V2 docs intro](https://opencode.ai/v2/docs/) or work in WSL.

## 2. Connect model access

The team admin gives you an OpenCode API key (Console account with the Go subscription). To connect it:

```bash
cd <repo-root> && opencode        # start the TUI in the repo root
```

then inside the TUI:

```text
/connect                            # select "OpenCode Go", paste your API key
```

Verify with `opencode auth list` (shows your saved account). Alternative for scripts and CI-style use: export `OPENCODE_API_KEY` — the same variable CI uses (`.github/workflows/ai-review.yml:21`).

You do not pick models — the repo pins them:

| What | Model | Pinned in |
|---|---|---|
| Main session (chat + edits) | `opencode-go/qwen3.8-max` | `.opencode/opencode.jsonc` |
| `executor` subagent (batched work) | `opencode-go/deepseek-v4-pro` | `.opencode/agents/executor.md` |
| `review` subagent (the gate) | `opencode/kimi-k3` | `.opencode/agents/review.md` |

The `opencode-go/` prefix routes through the OpenCode Go subscription; the `opencode/` prefix routes through OpenCode Console inference — one key from the admin covers both. Track usage and limits at [opencode.ai/console](https://opencode.ai/console).

## 3. First launch

Run `opencode` from the **repo root**. It picks up, with no action from you:

- `.opencode/opencode.jsonc` — the shared project config (models, MCP servers, permissions).
- The `AGENTS.md` files — root always; `backend/AGENTS.md` and `frontend/AGENTS.md` load as soon as the agent reads code in those folders.
- `.opencode/agents/`, `.opencode/commands/`, `.opencode/skills/` — the review/executor subagents, `/done`, and the vendored grill/domain-modeling skills.
- The **superpowers plugin** (pinned `v6.4.1` in `opencode.jsonc`) — first launch installs it in the background; this needs network. It generates `.opencode/node_modules/` and `.opencode/package.json`, both gitignored — never commit or hand-edit them.
- The MCP servers **context7** (library docs) and **gh_grep** (GitHub code search) — remote, preconfigured. If one asks for sign-in, run `/mcps` in the TUI and authenticate there.

## 4. What the project config does

`.opencode/opencode.jsonc` is shared and committed — it is the same on every machine.

| Piece | What it means for you |
|---|---|
| `permissions[]` | The enforced boundary behind the operating mode in `AGENTS.md`: edits to `backend/app/**` and `frontend/src/**` **ask you on every edit**; dependencies, packaging, migrations, and Docker files are **denied** (a human makes those changes); destructive git, `rm`, `psql`, and dependency installs **ask**. If the agent says a tool call was refused, that is this config working — it must not route around it. |
| `agents/review.md` | The one process gate: runs the Definitions of Done and audits the diff against the binding invariants, returns `VERDICT: DONE \| NOT DONE`. Read-only — it fixes nothing. |
| `agents/executor.md` | Implements one exhaustive task brief end to end on a cheaper model and reports files changed + DoD results. For large/batched work only — chat-sized edits stay in the main session. |
| `commands/done.md` | `/done` — dispatches the review gate on the uncommitted working tree. |
| `skills/` | Vendored skills: `grill-me`, `grilling`, `grill-with-docs`, `domain-modeling` (origin in `.opencode/skills/PROVENANCE.md`). |
| superpowers plugin | Process skills the agent loads on demand (brainstorming, TDD, systematic debugging, verification). Pinned — bumped deliberately, not automatically. |

The agent also follows the **graphify-first rule** from `AGENTS.md`: it queries the knowledge graph in `graphify-out/` before reading source files. `graphify-out/` is generated per clone (`graphify update .` in onboarding) and should be re-run after code changes.

## 5. Example usage

One full cycle, agent-assisted (mirrors "How work flows" in `docs/onboarding.md`):

```text
$ cd <repo-root> && opencode

> how does book upload validation work?
  The agent queries graphify first, then cites file:line answers.

> add an "overdue" flag to books, with tests
  It proposes edits to backend/app/** — you get a confirmation prompt on
  every edit: approve, reject, or ask for changes.

> @executor implement <task> per the brief: files X, Y; behavior Z; tests …
  Large or batched work goes to the executor subagent. The brief must be
  exhaustive — it stops rather than improvises.

> @review the overdue flag change
  The gate: DoD commands + invariant audit, one combined verdict.

> /done
  Same gate over everything uncommitted in the working tree.
```

Then: fix what the reviewer blocks, re-run it, and commit yourself (or approve the agent's `git commit` prompt) — the commit-msg hook enforces the format in `docs/CONTRIBUTING.md`. A change is done when `review` passes it locally and CI is green.

## 6. Overrides and troubleshooting

- **Personal config** goes in `~/.config/opencode/opencode.json`, which merges over the project file — never bend `.opencode/opencode.jsonc` to personal taste; it is shared and committed.
- **Terminal preferences** (theme, keybindings) live in `~/.config/opencode/cli.json`, or press `Ctrl+P` → **Open settings** in the TUI.
- **Config changes hot-reload** — no restart needed; `/reload` forces a full reload.
- **Agent behaves oddly / stuck:** `opencode service status`, then `opencode service restart` if unhealthy. Logs: `~/.local/share/opencode/log/opencode.log`.
- **Auth or model errors:** re-run `/connect`; `opencode auth list` shows what is connected. If `review` dispatches fail on `opencode/kimi-k3`, that model routes through Console inference — confirm your key is connected and talk to the admin.
- **Usage limit hit:** Go plans cap usage per model (5-hour/weekly/monthly); check [the console](https://opencode.ai/console). Free models still work; the admin can adjust the plan.
- **Anything else:** the [V2 troubleshooting guide](https://opencode.ai/v2/docs/troubleshooting/) and `docs/onboarding.md` § Troubleshooting.
