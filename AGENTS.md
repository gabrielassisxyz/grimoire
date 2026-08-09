# grimoire: Agent Briefing

> Read before every interaction. Living spec: short, imperative. On every gotcha or decision, append one line here.

> **What it is:** a summoned overlay that advises on a choice offered mid-run in a roguelike game. The pipeline is screenshot, structured extraction of the offered options, resolution to catalog ids, the known state of the run, deterministic simulation of the known effects, ranking, and only then an LLM that explains the ranking. The model never produces the numbers.

> **Calibration:** Tier 2 · Phase: work. External stakes are contained (local-only, no hosted service), but the repo redistributes normalized facts derived from third-party sources, which is a real exposure; personal stakes are high, since this is a public tool meant to grow into a game-agnostic framework. **Review gate:** standard. One independent opinion over the whole branch diff, exactly once, pre-push. No per-commit reviews.

## Stack & Commands

- **Stack:** Python (uv-managed, `.python-version` = 3.13). No runtime dependencies yet. `ai-overlay-core` (screen capture, LLM client, proxy settings) is the intended dependency and is deliberately not declared: it is unpublished, and a lockfile pointing at an unpublished git source breaks every clone and every CI run. See [ROADMAP.md](ROADMAP.md).
- **Setup:** `uv sync`, then `bin/install-hooks` (once per clone, so the gitleaks and attribution hooks are active).
- **Test:** `uv run pytest`.
- **All CI checks:** `bin/ci` (ruff format, ruff lint, pytest, pip-audit, markdown soft-wrap, prose gate). This is the exact script GitHub Actions runs.
- **Entrypoint:** none yet. There is no `python -m grimoire` to run until the first pipeline stage exists; do not write one into this file before it works.

## Scope (current)

- **Current scope:** nothing is implemented. The repo carries its harness and the rules that must hold from the first commit, chiefly the data-provenance ones, because those are the constraints that cannot be retrofitted onto a published history.
- The target is a **game-agnostic framework with per-game packs**, not one repo per game. That is a present need and not speculation: two games are already in play with incompatible ingestion paths, one whose data comes from packaged engine assets and one whose data comes from a community wiki and spreadsheet. The catalog layer is pluggable from the start for that reason alone.
- The first implemented pack is deliberately narrow: one character, one weapon and rune set, one objective, one screen. Breadth comes after that slice proves the whole chain end to end. The pilot is pinned in [ROADMAP.md](ROADMAP.md); do not widen it there without a present need.
- **Two surfaces, not one.** Before a run, read the player's own save for what is unlocked and report what a target build still needs. During a run, read the offered choice from the screen and rank it. They share the catalog and nothing else: the first has no vision problem and no time pressure, the second has both.
- Don't expand beyond it without a present need. If a change drifts past it, STOP and flag it.

<!-- BEGIN universal-principles v3 -->
## Working principles

- **The human defines the WHAT; the agent decides the HOW.** Don't wait for line-by-line dictation. Plan first for non-trivial tasks: show the plan + to-do list, wait for approval.
- **Think before coding — don't assume, don't hide confusion.** State assumptions explicitly; if multiple interpretations exist, present them — don't pick silently. If a simpler approach exists, say so and push back. If a task is impossible under the stated constraints, or info is missing, say so — don't guess. (For trivial tasks, use judgment; this is bias, not ritual.)
- **Surgical changes — touch only what you must.** Every changed line traces to the task. Don't "improve" adjacent code, reformat, or refactor what isn't broken; match existing style even if you'd do it differently. Flag unrelated dead code — don't delete it. Remove only the imports / variables / functions your own change orphaned.
- **Chesterton's Fence — find the problem before undoing the decision.** A config, a flag, a workaround that looks arbitrary is a **fence**: someone put it there, probably to fix something that is invisible to you *because the fence is working*. You arrive with no history, so absence of a visible reason is evidence of your ignorance, not of its uselessness. When your fresh measurement contradicts what the human vaguely remembers ("I changed this once, because of some problem"), **your measurement is the suspect first** — it may be measuring the case that *isn't* failing. Go find the original problem, then decide. *(A CIFS share was benchmarked with a big sequential `dd`, looked fast, and the local-disk download dir was "fixed" away — while the actual failure was random writes: par2, unrar, torrent piece-writes. Two wrong commits.)*
- **Goal-driven execution — define the success check, then loop to it.** Turn the task into something verifiable before coding: "add validation" → write tests for invalid inputs, then pass them; "fix the bug" → write a failing repro test, then pass it; "refactor X" → tests green before and after. For multi-step work, state a brief plan with a verify step each.
- **"Flaky" is not a diagnosis — test in the environment the thing actually runs in.** A component that fails *consistently* under automation is being **mis-invoked**, not being unreliable; "it works when I run it by hand" is not evidence that it works. The shell you test in has a TTY, a `$HOME`, an `ssh-agent`, an interactive stdin — the systemd unit, the CI job and the scripted harness have none of those, so a passing manual run can be testing a different program. Reproduce it *there* (start the unit, `env -u SSH_AUTH_SOCK`, `</dev/null`, `--dry-run` to print the real command line) before accepting "unstable" as a cause. **When a fix doesn't change the symptom, stop fixing and go look at what is actually being executed.** *(An interactive-mode flag with no TTY made one harness fail every review panel for weeks, written off as "flaky"; it was the wrong flag.)*
- **KISS — don't solve a problem you don't have yet.** Simplicity isn't "write less code"; it's not building for a need that doesn't exist. Let structure emerge from the code.
- **YAGNI & flat.** No preventive abstractions, no single-use interfaces. Interfaces for real boundaries only. Architecture is *extracted* once a pattern proves itself in real use — never designed up front for a user who doesn't exist yet. Need pulls architecture.
- **Order: make it work → make it right → make it fast** (Kent Beck), in that order. Most over-engineering is doing "right"/"fast" before a working thing exists to justify it.
- **Flag scope creep — a standing duty, not a suggestion.** When a solo tool starts being framed as a public / multi-user / multi-tenant / plugin-system / configurable-N-backends platform before a real, present need exists, STOP and ask: "Is this needed now?" Justify future-proofing against a need that exists *today*.
- **No silent decisions (comprehension debt).** Never make a silent architectural or design call — state it and record the rationale, so the reasoning is recoverable later.
- **Real decisions are presented in the chat, in isolation — never via popup.** When a design/architecture/scope/trade-off decision arises, surface it on its own: the options, what each means, pros/cons/trade-offs, and a recommendation — then decide together. Don't bury it mid-text or bundle it with other topics, and don't compress it into a quick-pick widget (e.g. AskUserQuestion) — the widget skips the reasoning and overlays the explanation. Widgets are for trivial short-answer picks only.
- **Long answers are written to be scanned, not read twice.** For recaps, status reports, batch reviews, plans, and any comparison of options: lead with the outcome in one line, then break the body into bullets and **bold** the load-bearing terms. Options are always a list — one bullet per option, the recommended one marked — never a paragraph the reader has to parse to find the choices. Reserve unbroken prose for short arguments; a wall of paragraphs costs more in re-reading than the structure would have cost in words.

## Git: branches, commits, PRs, comments

- **Ask the repo for its default branch; never assume one.** Repos differ — `master` and `main` are both common, often in the same person's account — and a wrong guess sends a PR to a branch that does not exist, or, worse, has you "fixing" a URL that was right all along. `git symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||'`, or `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`. Never commit directly to it: branch, then PR.
- **A new repo starts on `main`.** That is the preferred name, and `init.defaultBranch` is set to it, so `git init` produces it without anyone choosing. It settles new repos only: an existing one keeps the branch it has, because renaming breaks open PRs, CI filters, deploy hooks and every permalink into the tree, and buys nothing. The rule above still governs everything already in existence — ask, never assume.
- **Branches** — Conventional Branch (conventionalbranch.org): `<type>/<kebab-description>`, types `feature/`, `bugfix/`, `hotfix/`, `chore/`, `release/`, `docs/`.
- **Commits** — Conventional Commits (conventionalcommits.org): `<type>(scope): <description>`, types `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `style`. Breaking change → `!` after the type or a `BREAKING CHANGE:` footer.
- **Atomic commits** — one logical change per commit, each independently green and revertible. Never `git add .` blind; split unrelated changes.
- **Always work in your own worktree — mandatory, not conditional.** Parallel sessions are opened freely and nothing signals their existence to you, so a "check whether another session is here first" step can never be reliable — the honest answer is always "maybe". The only collision-proof arrangement is structural: keep the main working tree on the default branch as a clean reference and **never work in it** — before your first write (commit, branch, rebase, stash; read-only exploration is exempt), create your own worktree and do everything there: `git worktree add ../<repo>-<task> -b <your-branch> <origin>/<default-branch>`. Do this **whether or not** you believe another agent is running — that belief is exactly what you cannot verify. Report which worktree/branch you used; remove it once merged. Only the human can see all the open sessions.
- **Pull requests** — describe **what + why**. *What*: a 1–3 line summary. *Why* (the bulk): decisions, trade-offs, rejected alternatives. The diff shows the what; the PR explains why.
- **Comments** — always **WHY, not WHAT**: explain intent, never restate the obvious mechanics. Keep existing comments; they carry intent.

## Code style (baseline)

- Functions: 4–40 lines, one thing each (SRP). Files: under ~500 lines, split by responsibility.
- Names specific and unique — avoid `data`, `handler`, `Manager`, `util`.
- Explicit types. Early returns over nested ifs; max ~2 levels of indentation.
- Inject dependencies; wrap third-party libs behind a thin interface this project owns.
- No duplication — but don't extract *too early*. Tolerate duplication while the pattern is still forming; extract the abstraction *from* proven, repeated code, never ahead of it.
- **Refactoring is not automatic.** After a large feature, list refactoring candidates (files > ~500 lines, duplicated logic, long functions, hardcoded config) and ask before pruning — the human decides, the tests are the safety net. Consolidate when the thing works and the seams are obvious, not before.
<!-- END universal-principles v3 -->

## Data and provenance

The rules that cannot be retrofitted. Publication does not clean a history: a blob reachable from `refs/pull/*` survives any rewrite, so a source that should never have been committed cannot be uncommitted. Every rule below applies from the first commit.

- **Three classes of evidence, and every catalog record names its own.** `game_asset` (read from a packaged install: asset path plus build id), `community_source` (wiki, spreadsheet, guide: URL plus retrieval date plus the game version it describes), `measured` (a controlled in-game experiment: the procedure, the before state, the after state). Each record also carries a `confidence`. A record with no evidence is not a record.
- **Never tracked, under any circumstances:** raw scrape output, verbatim third-party prose, extracted game assets, packaged archives, decryption keys, `.usmap` mapping files, and save-game blobs. They are derived from the reader's own licensed install or from someone else's copyrighted text, and shipping them here redistributes the publisher's content. They live in `local/` or an ignored cache. The `.gitignore` already refuses the common extensions; that is a backstop, not permission to try.
- **What ships is normalized facts, never the source.** A guide becomes structured rules; it never becomes a quoted post. A spreadsheet becomes typed records with provenance; it never becomes a copy of the sheet.
- **A source's license is verified before its data enters the tracked catalog**, not after. A source whose license does not permit a normalized redistribution stays out, and the gap is recorded as a gap.
- **No circumvention.** If an archive is encrypted and the publisher has not made the key available, that source is closed. Do not add code that decrypts protected content, patches the executable, injects into the game process, or reads its memory. This is a hard boundary and not a trade-off to weigh against convenience. Parsing the player's own save file from disk is not circumvention and is allowed: it is unprotected local data belonging to whoever runs the tool, and the tool only ever reads it. The parsed contents are still never tracked.
- **The catalog is versioned against the game build.** A patch means re-extract, structural diff, and revalidate the measurements the diff touched. A record whose build id is older than the installed game is stale, and stale is a state the code must be able to report.
- **Patch notes are a trigger and a diagnostic, never a source.** They are the publisher's prose describing deltas rather than state, so nothing is ever ingested from them and they are not tracked. Their two uses are: a new build id means re-ingest and diff, and when the diff reports a changed record they explain whether the change invalidates a strategy or only moves a number. That second use is the only handle on a patch that rewrites a mechanic without touching any name or value a build refers to directly.

## Architectural principles

- **The LLM explains; it never computes.** Every number that reaches the user comes from the catalog or from the effect engine. A model that is asked to do arithmetic will do it, plausibly and wrongly, and that failure is invisible in the output.
- **Fail loud, never silent.** A missing catalog id, an unresolvable option, or a stale build halts the recommendation and surfaces a greppable marker naming both the missing thing and the catalog entry that would fix it. Never a silent fallback, never a nearest match accepted without a score.
- **Below the confidence threshold, refuse.** The correct output is a refusal that names what could not be read, not a hedged guess. A tool that guesses when it cannot see is worse than no tool, because it is trusted at exactly the moment it is wrong.
- **A build is a set of catalog references, never a list of names.** Every weapon, rune, skill and power in an encoded build is a catalog id, stored with the game build it was verified against. This is what makes staleness decidable instead of a matter of opinion: a reference that stops resolving is a broken build, reported with the exact id, and a referenced record that changed between game versions is a targeted warning rather than a blanket one. A build stored as loose strings can never be checked against anything, and the check cannot be added later without re-encoding every build.
- **The effect engine implements only proven formulas.** An operation whose ordering, cap, or rounding is not established by an asset or by a measurement is recorded as unknown and excluded from the ranking. It is not approximated to keep a number on the screen.

## Tests (TDD)

- Every feature is born with a test; every bugfix with a regression test.
- **Hermetic by default.** Tests must not touch the network, a real game install, a real screenshot, or a real model. Screenshots are committed fixtures, cropped to the game only; vision and LLM calls go through named fakes, never inline stubs.
- Every formula in the effect engine has a test derived from a recorded measurement, and the test carries that measurement's provenance. A formula whose test cannot cite its evidence is a guess with a green check next to it.
- Tests run with ONE command (`uv run pytest`), no manual setup and no credential. If it cannot run headless, it is wrong.
- Before saying "done", run `bin/ci` and show the result.

## Small releases

- Every commit on `main` passes `bin/ci` and is runnable. No broken commit fixed by the next one. Branch off `main`, PR back; the conventions are in the principles block above.
- Closed work is committed before switching tasks; flag it if it has not been.

## Security (habit, not a phase)

- Screenshots capture whatever is on screen. Never log image bytes or write them outside a path the user controls, and downscale before sending anything to a model.
- No API key is embedded here. Credentials resolve from the environment or from the local proxy, never from a tracked file.
- Dependency CVEs are caught by `pip-audit` in `bin/ci` and in CI.
- When touching user input, the network, the filesystem, or a parser fed by third-party data, flag the risk and propose the guard.

## Prose

- No em-dash. Use a comma, a colon, a semicolon or a full stop. `bin/ci` checks this across the whole tree, so it applies to Markdown, source comments, config and workflow files alike, and the `commit-msg` hook applies it to commit messages.
- Bold marks structure (a bullet lead-in, a table header), never emphasis mid-sentence. Same for italics: a term being introduced, not a word being stressed.
- No process narration anywhere a stranger can read it: no task ids, no phase names, no review rounds, no mention of who or what reviewed a diff, no reference to a session or a conversation. Commit and PR text describe the problem and the change, never how the work was organised.
- No audience in the text. A README says what the software does, not who is going to read it.
- Comment density is low by default: the non-obvious only, the why and not the what. Long reasoning belongs in a document under `docs/`, not in a header comment.

## Git and secrets

- Before any commit, show `git status` and `git diff --cached`; confirm no secret and no third-party blob is staged. The gitleaks pre-commit hook is the deterministic backstop; this habit is the probabilistic one. Run `bin/install-hooks` once per clone so the hook is active.
- Real secrets stay out of git. Only `*.env.example` with fake values is committed.

## Post-implementation checklist (run before "done")

1. Commits small and well-described.
2. Refactoring candidates listed (if the change was large).
3. Security risks flagged (if you touched screenshots, the network, the filesystem, or a third-party parser).
4. Provenance checked (if you touched the catalog): every new record carries evidence and confidence, and no raw source was tracked.
5. This spec updated if behavior, setup, or release flow changed, and any hurdle it gained is classified rather than just appended.

## Common hurdles

| hurdle | class | gate |
|---|---|---|
| The prose gate scans the whole tree, not a diff. An em-dash in a code comment, a YAML key or a shell script fails CI exactly like one in a doc. | ci | `bin/ci` |
| `scripts/md-unwrap.py` takes a repo path, not a file, and `--write` refuses a dirty tree without `--allow-dirty`. Pointing it at a single file silently does nothing. | tripwire | `bin/ci` (`--check`) |
| The same script only reads files git already tracks, so on an unstaged tree it reports soft-wrapped no matter what the files contain. Stage first, then check. | tripwire | `bin/ci` (`--check`) |
| Its `--write` mode skips a repo whose history looks third-party, and a repo with zero commits has no authors to match, so the first run on a new checkout self-skips. `--include-forks` overrides it. `--check` never applies that heuristic. | tripwire | none, `--check` is unaffected |
| Harness files vendored from the shared source must stay byte-identical AND keep their executable bit. A copy installed at 644 reports as wrong. | ci | the shared harness checker, outside this repo |
| `ai-overlay-core` is not a dependency yet, so screen capture and the LLM client do not exist here. Do not write an import for them before the dependency is declared. | prose | none yet |
| `bin/worktree` falls back to `master` when `refs/remotes/origin/HEAD` is missing, and a repository created with `git init` plus `remote add` never has that ref. The default branch here is `main`, so run `git remote set-head origin -a` once or every new worktree branches off a ref that does not exist. | tripwire | none, the fallback is silent |

**A hurdle promoted to a gate is deleted from this table, not duplicated.** The gate is the instruction; a line here restating it only dilutes the ones still unguarded.
