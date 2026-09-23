# Vendored skills — provenance

## grill-me, grilling, grill-with-docs, domain-modeling

- **Source:** https://github.com/LinnetCodes/grill-me (MIT, © 2026 LinnetCodes)
- **Upstream origin:** adapted from Matt Pocock's MIT-licensed `mattpocock/skills`
- **Vendored:** 2026-09-22, copied from the plugin's git fetch cache into
  `.opencode/skills/` (this directory).
- **Why vendored, not installed as a plugin:** LinnetCodes/grill-me ships a V1
  plugin entrypoint (`.opencode/plugins/grill-me.js`) that OpenCode v2.0.14
  rejects with `PluginModule.LoadError: Plugin must export a default definition
  with an id and an effect or setup function (Missing key at ["default"])`.
  This is the documented "V1 plugins do not run in V2" breaking change
  (https://opencode.ai/v2/docs/migrate-v1). The skills themselves are plain
  Markdown, which OpenCode discovers natively from `.opencode/skills/` with no
  plugin — so vendoring sidesteps the broken entrypoint entirely.
- **License:** MIT — see `LICENSE` in this directory.

### What each does

| Skill | Purpose |
|---|---|
| `grill-me` | Entry point; delegates to `grilling`. `disable-model-invocation: true` — user invokes it explicitly. |
| `grilling` | The engine: relentless one-question-at-a-time interview to stress-test a plan/design before building. Looks up facts in the codebase; puts decisions to the user. |
| `grill-with-docs` | `grilling` plus living docs — writes ADRs and a glossary as decisions crystallise. |
| `domain-modeling` | Builds/sharpens the project's ubiquitous language; records architectural decisions. Used by `grill-with-docs`. |

### Updating

Re-fetch from upstream and re-copy the `skills/*` directories here:

```sh
git clone --depth 1 https://github.com/LinnetCodes/grill-me.git /tmp/grill-me
cp -R /tmp/grill-me/skills/{grill-me,grilling,grill-with-docs,domain-modeling} .opencode/skills/
cp /tmp/grill-me/LICENSE .opencode/skills/LICENSE
```

If upstream ever ships a V2-compatible plugin entrypoint, the plugin form can
replace this vendored copy.

## systematic-debugging

NOT vendored here — provided by the `superpowers` plugin
(`superpowers@git+https://github.com/obra/superpowers.git#v6.4.1`), already in
`opencode.jsonc`. Available as `systematic-debugging`; auto-invoked before
proposing fixes to any bug, test failure, or unexpected behaviour.
