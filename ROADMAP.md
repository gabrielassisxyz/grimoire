# Roadmap

What exists, what is missing, and what is deliberately out of scope. Background: [README](README.md), rules: [AGENTS.md](AGENTS.md).

## What exists today

- **The harness only.** `bin/ci` (ruff format, ruff lint, pytest, pip-audit, markdown soft-wrap, prose gate), the gitleaks and commit-message hooks with their installer, worktree isolation, and the matching GitHub Actions workflows.
- **The rules that cannot be retrofitted**, written before the first line of pipeline code: where game data may come from, what may be redistributed, and what the code must refuse to do. They are in AGENTS.md because a published history cannot be cleaned afterwards.

## Decisions still open

- **The pilot.** Which game, character, weapon and rune set, mode and difficulty, and which screen the first slice reads. Nothing downstream can be specified until this is chosen, because the ingestion path differs per game: packaged engine assets for one candidate, a community wiki and spreadsheet for the other.
- **How the state of a run is tracked.** Three candidates, in increasing cost and decreasing robustness: explicit confirmation of each choice through a local event log, visual inference with periodic resynchronisation from the stats panel, or instrumentation of the game. Explicit confirmation is the cheapest to build and the most reliable; instrumentation is fragile across patches and expands the security surface considerably.
- **What "best" means.** Scoring against a target build taken from a guide, or maximising a universal mathematical metric. The second requires modelling damage, procs, area, uptime, status effects, chains, summons and enemies, which is a later goal rather than a first cut.

## Missing, in rough order

1. **Source audit.** Compare the community sources against the installed build; produce a report of gaps and disagreements before trusting either.
2. **Versioned catalog.** Ids, aliases, effects, characters, weapons, runes and powers, each with provenance, build id and confidence.
3. **Structured extractor.** The multimodal model returns validated JSON constrained to known candidates. Region-based OCR and icon matching are deliberately *not* built first: the direct approach is measured against real screenshots, and OCR is introduced only where it demonstrably fails. Building it before measuring would be premature.
4. **Run state.** Initial snapshot plus an event log of choices, plus a resynchronisation path.
5. **Effect engine.** A small set of proven operations. No large speculative expression language.
6. **Ranker.** Guide-derived rules and synergies combined with the deltas the engine computes.
7. **Overlay surface.** Recommendation, confidence, deltas, and confirmation of the choice actually made.

## Not started, and blocked on something else

- **Depending on `ai-overlay-core`** for screen capture, the LLM client and proxy settings. The dependency is not declared while that package is unpublished: a lockfile pointing at an unpublished git source breaks every clone, CI included. Until then this repo has no runtime dependencies and no entrypoint.

## Deliberately out of scope

- **Circumventing protection of any kind.** No decryption of protected archives, no executable patching, no process injection, no memory reading. A protected source is a closed source.
- **Redistributing third-party content.** The tracked catalog holds normalized facts with provenance. Raw scrapes, verbatim prose, extracted assets, mapping files and save data stay out of the repository.
- **One repository per game.** The framework is game-agnostic with per-game packs.
- **A universal damage model** before a single pilot works end to end.
