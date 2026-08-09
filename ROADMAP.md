# Roadmap

What exists, what is missing, and what is deliberately out of scope. Background: [README](README.md), rules: [AGENTS.md](AGENTS.md).

## What exists today

- **The harness.** `bin/ci` (ruff format, ruff lint, pytest, pip-audit, markdown soft-wrap, prose gate), the gitleaks and commit-message hooks with their installer, worktree isolation, and the matching GitHub Actions workflows.
- **The rules that cannot be retrofitted**, written before the first line of pipeline code: where game data may come from, what may be redistributed, and what the code must refuse to do. They are in AGENTS.md because a published history cannot be cleaned afterwards.
- **A save reader.** It resolves each domain to its latest written slot, reads the primitives, and decodes the skill tree into records. It refuses a payload that does not fit the layout rather than returning part of one.
- **A target build and the catalog it refers to.** The pilot build is stored as identifiers, and the catalog joins those to the names the game displays. Both are partial and say which parts are missing.

Nothing reads a screen yet, and there is no entrypoint. Nothing here is a running tool.

## The pilot, settled

The first pack targets **Soulstone Survivors**, so the ingestion path is community sources with the installed build used for validation, not asset extraction.

- **Pilot build:** Barbarian, the Electric variant of a published character guide. Weapon `Tempest Battle Axes`; active skills `Thundering Slash`, `Thunder Clap`, `Lightning Beam`, `Power Conductor`, `Overcharged Blast`, `On Guard`; tenacity runes `Vulnerable Target`, `Critical Mastery`, `Vulnerable Exploit`, `Lord's Bane`; versatility runes `Skill Mastery: Electric`, `Weapon Expert`, `Skill Inclination: Electric`. The character screen states five available skill types for this character, Electric among them, so the pilot is an on-type build rather than the off-type case an earlier reading of the community spreadsheet suggested. That reading came from two lists aligned by column position, which give the *primary* type and not the set of available ones; the difference matters, and the lesson generalises past this one fact. A layout inference from a spreadsheet is a hypothesis, and the game's own screens are the authority.
- **First screen read:** the level-up power offer, and only that. Active skill choice and replacement come later. Each screen is a separate extraction contract, and adding the second before the first works doubles the failure surface without doubling what is learned.
- **What "best" means:** score against the target build taken from the guide, combined with the deltas the engine computes. A universal mathematical metric would require modelling damage, procs, area, uptime, status effects, chains, summons and enemies, and is a later goal rather than a first cut.
- **Run state:** visual inference with resynchronisation from the stats panel. Confirming every choice by hand is reliable but costs an interaction at every level-up, which is the wrong trade for a tool meant to reduce friction. The risk this accepts is that a missed or misread choice corrupts every later recommendation silently, so inference is paired with a divergence check: predicted stats are compared against the observed panel, and a mismatch beyond tolerance marks the state stale and refuses rather than continuing. That converts the silent failure into a loud one.

- **Target difficulty:** a standard map at the curse intensity the player already runs, around the high twenties, on a fixed and recorded curse set. Objective is completing the run. Not a Dungeon of Despair, which carries a separate threat axis and would add a second difficulty variable to control; not a titan hunt or an endless mode, the first because titans and event bosses use a debuff soft cap an order of magnitude lower than normal enemies and the first engine should model one cap regime, the second because a mode with no terminal state gives no clean answer to whether a recommendation helped.

**Rewards do scale with difficulty, contrary to what an earlier note here claimed.** The selection screen states the bonuses explicitly next to the curse list, and at the settings in use they are large: a percentage uplift in the soft currency well into three figures, a larger one on progression, and flat uplifts on two mineral tiers. A community remark that higher difficulty pays nothing extra was taken at face value and written down; the screen contradicts it. It was probably true of the extreme top end and was generalised too far, by the community first and then by this document. It does not change the pilot difficulty, which was chosen on iteration speed rather than on reward, but a reader would have drawn the wrong conclusion from the old wording.

**First result of the source audit, obtained early and worth stating.** The community wiki's table for the highest curse tier matches the game screen exactly: the same six modifiers, in the same order, with the same point values. So on this table the source that reports an older version is nonetheless correct, which is the outcome the version field exists to let you distinguish from the opposite one. Stale is a reason to check, not a reason to discard.

The reasoning behind that number, since it is the kind of choice that looks arbitrary later. Difficulty here has to satisfy three things at once and they pull against each other. It must be high enough that a wrong choice is visibly wrong, because where every build clears there is nothing for a ranker to prove. It must be low enough to keep runs at a few minutes, because validation needs many runs and the community reports single runs stretching past an hour once curse intensity passes the mid thirties. And it must be where the player actually plays, or every fixture is calibrating the tool for a situation it will never see. The commonly cited sweet spot in the low-to-mid thirties optimises prestige gained per unit of difficulty, which is a farming objective and not this one; going higher buys longer runs and, by the account of the community's most cited source, no additional reward.

**Record the curse set, not only the intensity.** Different curses apply different pressures, so two runs that both report the same total are not the same experiment, and the better power choice can differ between them. An intensity number alone makes those runs look identical in the data while being incomparable in fact, which is how a dataset gets quietly poisoned.

## Missing, in rough order

1. **Source audit.** Compare the community sources against each other and against the installed build; produce a report of gaps and disagreements before trusting any of them. Licence position per source is settled here too, before ingestion rather than after. It has begun, and its first result is below.

#### The pilot's own guide is already stale, in the way that is hardest to see

Checking the published build against the release notes for the installed version found two changes that matter, and both of them are invisible to any structural check.

- A rune the build depends on for critical hit chance had that value doubled. The guide states the old number in prose, gives it as the reason for taking the rune, and is now wrong about the magnitude while remaining right about the choice.
- The skill the build uses to apply its central status effect now applies four stacks where it applied one. The whole build is organised around stacking that effect so two other skills scale off it, so this is not a marginal adjustment to a minor component; it is a fourfold change to the loop the build exists to run.

**Every identifier in that guide still resolves.** Referential integrity, which is the strong mechanical check, passes completely: no weapon, rune, skill or power has been renamed or removed. A tool relying on it alone would report the build as healthy while recommending against numbers that are off by a factor of two and a factor of four. This is exactly the semantic case that only release notes can catch, found on the first cross-check and on the pilot itself rather than on some hypothetical later build.

It also settles what the video transcripts are for. They are auto-generated captions, noisy enough that names arrive mangled, so they are useless as a source of values. What they carry is *what changed and why*, which is the same role the release notes play: a trigger and a diagnostic, never an input to the catalog.
2. **Versioned catalog.** Ids, aliases, effects, characters, weapons, runes and powers, each with provenance, build id and confidence. The alias half exists for the pilot; the rest does not.

#### The alias layer, and why it could not be a naming convention

The two vocabularies are joined by records rather than by a rule, and the reason is that a rule would nearly work. `RuneCriticalMastery` is "Critical Mastery" and `RuneStartWeaponSkill` is "Weapon Expert", so any transformation confident enough to handle the first is wrong about the second, and it is wrong quietly, in the direction of a plausible answer. There is no fuzzy matching and no nearest match anywhere in the resolver: a name either has a record or the lookup fails naming the name and the file that would fix it.

Evidence classes are not interchangeable here and the records say which one they rest on. A pair read off a tooltip is the game stating both vocabularies in one frame. A pair joined through an effect description is an inference: a spreadsheet gives a name and an effect, the save gives an identifier describing the same effect, and the two are matched on that description. The second is sound where the effect is distinctive and it is still weaker than being told, so it carries lower confidence and is worth upgrading whenever a capture of that tooltip turns up.

A record carries a list of evidence rather than one entry, because the pairs worth trusting most are the ones two unrelated readings agree on, and a schema holding a single class can only record the second one in a comment where nothing can weigh it. The loader enforces what each class owes: a community source without its URL and retrieval date is refused at load time rather than described as required in a document, since a provenance rule nothing checks is one the tree drifts away from quietly.

**One gap in that taxonomy is known and open.** None of the four classes describes reading the player's own save, which is the mechanism behind the weapon anchor and behind the save side of every effect join in the pack. Those readings are currently stated in prose in the file headers, so the strongest evidence here is the part a reader cannot get at mechanically. Either a fifth class covers it or the joins stay half recorded.

**The pilot's weapon resolved on an anchor rather than on the arrangement.** The blacksmith screen names one weapon at a time and shows five in a row, which gives an ordering but not the identifiers. What settles it is a reading from somewhere else entirely: the character screen had the fourth weapon selected and named it, and the save's equipped-weapon domain gives that character's weapon as the fourth identifier. Two readings that share no mechanism agree on one position, so the row order is the identifier order, and the other four follow from it.

**Two of the pilot build's seven runes are still unresolved, and they are recorded as absent rather than approximated.** One of them is worse than a gap: the guide asks for Skill Inclination and the save's presets hold Affinity, which the spreadsheet shows to be a different rune with a different unlock condition and a different effect. An identifier that is present, related and wrong is exactly what a resolver built on resemblance would have accepted.
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

### What the save turned out to hold

Found by scanning identifiers across every domain, before any record layout was decoded.

- **The curse vocabulary is in the save, with canonical ids and levels.** `mapprogression` carries entries such as `HealingDampening-01` through `-05`, `EmpoweredElites-01` through `-05`, `EliteFrequency`, `ExplosiveGoblins`, `MeteorOnDeath`, `EmpoweredBosses`, `ResilientBosses`, `PillarsOfProtection`, 44 distinct in total. So the identifier list for curses needs no external source at all; only their effects do. What that domain records is progression per map rather than which curses a given run had enabled, so it names the vocabulary without pinning any particular run.
- **Match history records the composition of runs already played.** `gamestatsmatchhistory` holds skill and rune identifiers per match, including exactly the pilot build's parts: `LightningBeam`, `PowerConductor`, `OverchargedBlast`, `OnGuard`, `PiercingShout`, `RuneAffinityElectric`, `RuneCriticalMastery`, `RuneExtraCritChance`, `RuneExtraCritDamageAgainstDazed`. Past runs are therefore a dataset rather than a memory, and decoding that one record layout is worth more than decoding any other.

#### The ten files a domain has are a rotation, and the unsuffixed one is rarely current

Each domain is written as `playerProfile-0-<domain>.savgs` alongside `-1` through `-9`, which reads like a current file with nine backups and is not. The game writes the ten in a ring, so the newest state is in whichever name it happened to reach last, and the unsuffixed one is simply position zero.

The evidence is a domain caught mid-rotation. Ordering `unlockedweapons` by modification time gives 31 unlocked weapons, 31, then **31 under the unsuffixed name**, then 32, 33, 34, 35, 35, 36, and **37 under `-7`**: one clean monotone sequence with the unsuffixed file sitting in the middle of it, a day and a half behind. Read that file and the player owns two weapons for the pilot character; read the newest and they own all five, which is what the character screen shows.

Two consequences worth stating separately, because the first is a bug anyone would write and the second changes what the reader can promise.

- **A reading of the save is a reading per domain, never per directory.** Domains are written only when they change, so on one real profile the newest slot differed for almost every domain: nine distinct rotation numbers across twenty-three domains, with exactly one landing on zero. Any code that opens the unsuffixed name is reporting the player's progression as it stood at an arbitrary earlier moment, and nothing about the answer looks wrong.
- **Which slot is latest is decided by a counter inside the payload, not by the file's timestamp.** The integer every domain writes just after its format tag counts how many times that domain has been written: read one domain across all ten slots and the values are ten consecutive integers, 20 to 29 for unlocked weapons, 504 to 513 for the skill tree. It was nearly mistaken for a schema version, which it resembles in every way except the one that matters.

That distinction is worth more than a tidier implementation. A timestamp is metadata and does not survive a copy, a restore from backup, or a move between machines, none of which change the save; a counter written by the game inside the file survives all of them. It also makes the two orderings checkable against each other, and on all twenty-three domains of one profile they picked the same slot, which is the kind of agreement between unrelated mechanisms that turns a plausible reading into a settled one.

#### The skill tree carries the run's finite counters, which were expected to cost a screen read

The first domain decoded as records rather than scanned for identifiers. It holds 148 nodes, each with the level invested in it: account-wide ones named plainly, and per-character ones named `<Character>_T<tier>N<node>`.

Two of its contents change earlier decisions.

- **`Rerolls`, `Banish`, `Lock`, `DashCount` and `DeathGuards` are in there.** Those are the finite counters that make a level-up an economic decision rather than a tactical one, and the plan had them arriving from the screen at every offer. Their starting values are in the save instead, with no vision problem and no ambiguity. The screen is still needed for what remains of each during a run, but the run no longer starts from an unknown.
- **`SkillTreeRunicPower` is what bounds a rune preset**, so whether a target build is even loadable is decidable before the run. A build is not only a set of runes the player owns, it is a set that fits a budget, and a build encoded without its cost cannot be checked against that budget at all.

**The reader refuses a payload that leaves bytes over.** That check is the whole reason to trust the layout: a record layout wrong by one field consumes the stream just as willingly and returns records that are simply the wrong ones. The leftover count is the only symptom such an error has, so it is fatal rather than logged. On the profile this was settled against, 148 records read and nothing remained.

### Three constraints the difficulty modifiers made concrete

Reading the community wiki's page on the mode settled several things at once, and each one generalises past curses.

- **Internal identifiers are not display names, and the gap is not cosmetic.** The save calls a curse `HealingDampening`; the interface calls it "Lifeless Void". Likewise `ExplosiveGoblins` against "Reckless Goblins", `EmpoweredElites` against "Captains of the Void", `EliteFrequency` against "Unholy Reinforcements". Every source therefore speaks one of two vocabularies, and a catalog record needs both plus the mapping between them, or a rule written from a guide will never resolve against a save. This is what the alias field is for and it is required from the first record, not added when it hurts.
- **The community source is already behind the installed build.** That page's own navigation reports a version three minor releases older than the one installed. Nothing about it is obviously wrong, which is the point: staleness here does not announce itself, so a record's version is not bookkeeping, it is the only thing separating a current fact from a plausible one.
- **The objective has cliff edges, which changes what a good recommendation is.** Finishing under thirteen minutes opens one mode and under fifteen opens another. A run is therefore not scored on a smooth "did it clear" axis, and near those boundaries the value of a power that raises clear speed jumps discontinuously. Any scoring that treats time as a smooth preference will be wrong in exactly the situations the player cares most about.

The page states CC-BY-SA, which matches the assumption the licence position was written against: facts and numbers normalize freely, prose is never copied.

Fetching it is unreliable rather than impossible. A direct fetch is refused with 402 and the scraper failed on one occasion and succeeded on another, apparently depending on the network path out. So the wiki is usable but cannot be depended on, and anything load-bearing that lives only there should be captured from a screen instead, which the source ordering above prefers anyway.

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
