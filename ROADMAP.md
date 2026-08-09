# Roadmap

What exists, what is missing, and what is deliberately out of scope. Background: [README](README.md), rules: [AGENTS.md](AGENTS.md).

## What exists today

- **The harness only.** `bin/ci` (ruff format, ruff lint, pytest, pip-audit, markdown soft-wrap, prose gate), the gitleaks and commit-message hooks with their installer, worktree isolation, and the matching GitHub Actions workflows.
- **The rules that cannot be retrofitted**, written before the first line of pipeline code: where game data may come from, what may be redistributed, and what the code must refuse to do. They are in AGENTS.md because a published history cannot be cleaned afterwards.

## The pilot, settled

The first pack targets **Soulstone Survivors**, so the ingestion path is community sources with the installed build used for validation, not asset extraction.

- **Pilot build:** Barbarian, the Electric variant of a published character guide. Weapon `Tempest Battle Axes`; active skills `Thundering Slash`, `Thunder Clap`, `Lightning Beam`, `Power Conductor`, `Overcharged Blast`, `On Guard`; tenacity runes `Vulnerable Target`, `Critical Mastery`, `Vulnerable Exploit`, `Lord's Bane`; versatility runes `Skill Mastery: Electric`, `Weapon Expert`, `Skill Inclination: Electric`. Note that the character's native type is Slam, so the pilot deliberately exercises an off-type build, which is the case where a naive recommendation is most likely to be wrong.
- **First screen read:** the level-up power offer, and only that. Active skill choice and replacement come later. Each screen is a separate extraction contract, and adding the second before the first works doubles the failure surface without doubling what is learned.
- **What "best" means:** score against the target build taken from the guide, combined with the deltas the engine computes. A universal mathematical metric would require modelling damage, procs, area, uptime, status effects, chains, summons and enemies, and is a later goal rather than a first cut.
- **Run state:** visual inference with resynchronisation from the stats panel. Confirming every choice by hand is reliable but costs an interaction at every level-up, which is the wrong trade for a tool meant to reduce friction. The risk this accepts is that a missed or misread choice corrupts every later recommendation silently, so inference is paired with a divergence check: predicted stats are compared against the observed panel, and a mismatch beyond tolerance marks the state stale and refuses rather than continuing. That converts the silent failure into a loud one.

Still unset: the target mode and difficulty. This is not cosmetic, since debuff soft caps differ by an order of magnitude between normal enemies and titans or event bosses, which changes the arithmetic behind a recommendation.

## Missing, in rough order

1. **Source audit.** Compare the community sources against each other and against the installed build; produce a report of gaps and disagreements before trusting any of them. Licence position per source is settled here too, before ingestion rather than after.
2. **Versioned catalog.** Ids, aliases, effects, characters, weapons, runes and powers, each with provenance, build id and confidence.
3. **Pre-run advisor.** Read the local save for what the player has actually unlocked, then report what a target build requires and does not yet have, and which owned runes and weapons substitute. Deterministic end to end and free of any vision problem.
4. **Structured extractor.** The multimodal model returns validated JSON constrained to known candidates. Region-based OCR and icon matching are deliberately *not* built first: the direct approach is measured against real screenshots, and OCR is introduced only where it demonstrably fails. Building it before measuring would be premature. One constraint is already known: the shared capture path caps the image by *width*, which treats a tall window generously and a wide one harshly, so two players with different window geometry get very different effective resolution on the same interface. The cap belongs on the longest edge or on total pixels, and that has to be settled before fixtures are measured against each other.
5. **Run state.** Initial snapshot, inferred deltas, resynchronisation, and the divergence check that makes a stale state loud.
6. **Effect engine.** A small set of proven operations. No large speculative expression language.
7. **Ranker.** Guide-derived rules and synergies combined with the deltas the engine computes.
8. **Overlay surface.** Recommendation, confidence and deltas.

## Later, and gated on the engine rather than on effort

- **Build synthesis.** Composing a target build for a character, weapon and objective by searching the catalog, instead of scoring against a build copied from a guide. The gate is not ambition, it is the effect engine: ranking three offered powers against a *known* target is strictly easier than inventing the target, so a system that cannot do the first has no business attempting the second. Encoded guide builds are the calibration harness for the thing that would eventually replace them.
- **The validation this makes available**, written down now because it costs nothing today and is easy to forget: point the synthesiser at a character and weapon whose published build is already encoded, and see whether it reproduces that build. Agreement is evidence the engine models the game. Disagreement is informative either way, since it means the engine is wrong or the guide is, and finding out which is worth more than either answer alone.
- **The editorial layer generalises before it synthesises.** Guides share structure: which stats a crit build wants, how the synergy chains constrain type combinations, when survivability outranks damage. Extracting the rules the guides follow, rather than the builds they produce, is the intermediate step, and the sources that teach build construction are worth more here than any individual build.

## Not started, and blocked on something else

- **Depending on `ai-overlay-core`** for screen capture, the LLM client and proxy settings. The dependency is not declared while that package is unpublished: a lockfile pointing at an unpublished git source breaks every clone, CI included. Until then this repo has no runtime dependencies and no entrypoint.

## Deliberately out of scope

- **Circumventing protection of any kind.** No decryption of protected archives, no executable patching, no process injection, no memory reading. A protected source is a closed source. Reading the player's own save file from disk is a different thing and is in scope: it is their data, it is unprotected, and the tool only ever reads it.
- **Redistributing third-party content.** The tracked catalog holds normalized facts with provenance. Raw scrapes, verbatim prose, extracted assets, mapping files and save data stay out of the repository.
- **One repository per game.** The framework is game-agnostic with per-game packs.
- **A universal damage model** before a single pilot works end to end.
