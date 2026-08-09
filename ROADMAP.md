# Roadmap

What exists, what is missing, and what is deliberately out of scope. Background: [README](README.md), rules: [AGENTS.md](AGENTS.md).

## What exists today

- **The harness only.** `bin/ci` (ruff format, ruff lint, pytest, pip-audit, markdown soft-wrap, prose gate), the gitleaks and commit-message hooks with their installer, worktree isolation, and the matching GitHub Actions workflows.
- **The rules that cannot be retrofitted**, written before the first line of pipeline code: where game data may come from, what may be redistributed, and what the code must refuse to do. They are in AGENTS.md because a published history cannot be cleaned afterwards.

## The pilot, settled

The first pack targets **Soulstone Survivors**, so the ingestion path is community sources with the installed build used for validation, not asset extraction.

- **Pilot build:** Barbarian, the Electric variant of a published character guide. Weapon `Tempest Battle Axes`; active skills `Thundering Slash`, `Thunder Clap`, `Lightning Beam`, `Power Conductor`, `Overcharged Blast`, `On Guard`; tenacity runes `Vulnerable Target`, `Critical Mastery`, `Vulnerable Exploit`, `Lord's Bane`; versatility runes `Skill Mastery: Electric`, `Weapon Expert`, `Skill Inclination: Electric`. The character screen states five available skill types for this character, Electric among them, so the pilot is an on-type build rather than the off-type case an earlier reading of the community spreadsheet suggested. That reading came from two lists aligned by column position, which give the *primary* type and not the set of available ones; the difference matters, and the lesson generalises past this one fact. A layout inference from a spreadsheet is a hypothesis, and the game's own screens are the authority.
- **First screen read:** the level-up power offer, and only that. Active skill choice and replacement come later. Each screen is a separate extraction contract, and adding the second before the first works doubles the failure surface without doubling what is learned.
- **What "best" means:** score against the target build taken from the guide, combined with the deltas the engine computes. A universal mathematical metric would require modelling damage, procs, area, uptime, status effects, chains, summons and enemies, and is a later goal rather than a first cut.
- **Run state:** visual inference with resynchronisation from the stats panel. Confirming every choice by hand is reliable but costs an interaction at every level-up, which is the wrong trade for a tool meant to reduce friction. The risk this accepts is that a missed or misread choice corrupts every later recommendation silently, so inference is paired with a divergence check: predicted stats are compared against the observed panel, and a mismatch beyond tolerance marks the state stale and refuses rather than continuing. That converts the silent failure into a loud one.

- **Target difficulty:** a standard map at the curse intensity the player already runs, around the high twenties, on a fixed and recorded curse set. Objective is completing the run. Not a Dungeon of Despair, which carries a separate threat axis and would add a second difficulty variable to control; not a titan hunt or an endless mode, the first because titans and event bosses use a debuff soft cap an order of magnitude lower than normal enemies and the first engine should model one cap regime, the second because a mode with no terminal state gives no clean answer to whether a recommendation helped.

The reasoning behind that number, since it is the kind of choice that looks arbitrary later. Difficulty here has to satisfy three things at once and they pull against each other. It must be high enough that a wrong choice is visibly wrong, because where every build clears there is nothing for a ranker to prove. It must be low enough to keep runs at a few minutes, because validation needs many runs and the community reports single runs stretching past an hour once curse intensity passes the mid thirties. And it must be where the player actually plays, or every fixture is calibrating the tool for a situation it will never see. The commonly cited sweet spot in the low-to-mid thirties optimises prestige gained per unit of difficulty, which is a farming objective and not this one; going higher buys longer runs and, by the account of the community's most cited source, no additional reward.

**Record the curse set, not only the intensity.** Different curses apply different pressures, so two runs that both report the same total are not the same experiment, and the better power choice can differ between them. An intensity number alone makes those runs look identical in the data while being incomparable in fact, which is how a dataset gets quietly poisoned.

## Missing, in rough order

1. **Source audit.** Compare the community sources against each other and against the installed build; produce a report of gaps and disagreements before trusting any of them. Licence position per source is settled here too, before ingestion rather than after.
2. **Versioned catalog.** Ids, aliases, effects, characters, weapons, runes and powers, each with provenance, build id and confidence.
3. **Pre-run advisor.** Read the local save for what the player has actually unlocked, then report what a target build requires and does not yet have, and which owned runes and weapons substitute. Deterministic end to end and free of any vision problem.
4. **Structured extractor.** The multimodal model returns validated JSON constrained to known candidates. Region-based OCR and icon matching are deliberately *not* built first: the direct approach is measured against real screenshots, and OCR is introduced only where it demonstrably fails. Building it before measuring would be premature. One constraint is already known: the shared capture path caps the image by *width*, which treats a tall window generously and a wide one harshly, so two players with different window geometry get very different effective resolution on the same interface. The cap belongs on the longest edge or on total pixels, and that has to be settled before fixtures are measured against each other.
5. **Run state.** Initial snapshot, inferred deltas, resynchronisation, and the divergence check that makes a stale state loud. What the interface actually offers is now known, and it changes the design (see below).

### What the interface gives us, observed rather than assumed

Read off real frames of a real run. These are the facts the run-state design rests on, and they are load-bearing enough to state before any code exists.

- **A level-up card shows the current value and the value after taking it**, as `+12% ▸ +16%`. That single detail does two jobs at once. It is ground truth to check the effect engine against, since the game states the result the engine is trying to predict. And it is a free partial resynchronisation at every level-up, for whichever stats the offer happens to touch, with no pause and no question asked. Drift in those stats is therefore detectable within a level or two rather than accumulating until someone thinks to check.
- **The full stats panel appears only on pause and on the end-of-run screen**, not during play and not on the level-up screen. A complete resynchronisation therefore costs an interaction, while a partial one is free. That asymmetry is the whole reason the previous point matters.
- **Rarity is written as text on the card**, not conveyed by colour alone. A whole class of colour and icon matching is unnecessary for the first cut.
- **The build version is printed in the corner of every frame.** Fixtures self-document the version they came from, which is exactly what the catalog's staleness checks need and would otherwise have to be recorded by hand.
- The level-up cards are drawn semi-transparent over live gameplay, so damage numbers and enemies pass behind and through the text. That is the extractor's hard case, and it is the normal case rather than an edge one.
- **The character screen carries the whole pre-run input in one frame**: the character's flat bonuses, its unique skills, the set of skill types available to it, the equipped divine legacy with its modifiers, the weapon row with the selection marked, the owned and locked characters, and the material counts. The pre-run advisor's first version can therefore be checked against a single capture, before any save file is parsed.

**Where a fact comes from decides how far it is trusted.** The community spreadsheet is the fastest source and it is not the authority; the game's own screens are. One claim in this document was wrong for exactly that reason, taken from column alignment in a spreadsheet tab and contradicted by the character screen. The catalog's evidence classes already encode this, and the source audit should treat a spreadsheet-derived record as provisional until a screen or an asset agrees with it.
6. **Effect engine.** A small set of proven operations. No large speculative expression language.
7. **Ranker.** Guide-derived rules and synergies combined with the deltas the engine computes. The decision is wider than the offer, see below.

### The offer is not the decision space

Scoring the three cards on screen and naming the best one solves a smaller problem than the one the player actually has. The screen also carries reroll, banish and lock, each with a count, and an offered active skill can replace one taken earlier as a placeholder. So the choices at a level-up include at least: take one of the offered options, reroll the whole offer, banish an option so it stops appearing in later offers, lock an option to keep it available for a later level, and replace an earlier filler with the real thing now that it has appeared.

Three consequences, and none of them are cosmetic.

- **Those counters are finite, so spending one is an economic decision rather than a tactical one.** A reroll spent on a mediocre offer at level eight is a reroll unavailable at level thirty, when the pool is thinner and the stakes are higher. Ranking cannot answer "reroll or take the least bad option" without a notion of what the remaining rerolls are worth.
- **Banish changes the distribution of every later offer, which is the only lever that does.** Removing a power from the pool raises the odds of everything else, so its value is not the value of avoiding one bad card, it is the value of a better pool for the rest of the run. That is a probability question, and it is the one place where the arithmetic has to look forward rather than at the current state.
- **Lock and replace exist because the right option and the right moment do not always coincide.** Two strong options in one offer is a case for locking one; taking a filler active skill early and swapping it when the intended one appears is a normal line of play, not a mistake being corrected.

**The tool operates none of these.** It does not press reroll and it does not choose what to banish on the player's behalf. What it needs is to know they exist, to read how many of each remain, and to include them as candidate actions when it says what it would do. The counts are on screen at every level-up, so this costs nothing to read and would cost a redesign to add later.
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
