# grimoire

A summoned overlay that advises on a choice offered mid-run in a roguelike game: which power to take at level-up, which weapon to keep, which branch of a skill tree to walk.

The point is what does *not* happen. A multimodal model asked to look at a screenshot and recommend a perk has to recognise the interface, remember the build, interpret the wording, infer hidden rules and do arithmetic, all at once. One misread label or one invented rule and the whole recommendation is wrong, confidently and invisibly. So the model is not asked to do that.

```
screenshot
  -> structured extraction of the offered options
  -> resolution to catalog ids
  -> the known state of the run
  -> deterministic simulation of the known effects
  -> ranking
  -> the model explains the ranking
```

The numbers come from a versioned catalog and a deterministic effect engine. The model is the last stage and it only puts the result into words, handles the subjective part of a preference, and says why one option beat another. Below a confidence threshold it refuses instead of guessing.

## Status

Nothing is implemented. The repository currently carries its engineering harness and the rules that have to hold from the first commit, chiefly the ones about where game data may come from and what may be redistributed. See [ROADMAP.md](ROADMAP.md) for what exists, what is missing, and what is deliberately out of scope.

## Design constraints

- **Game-agnostic, with per-game packs.** Two games are already in scope with incompatible ingestion paths: one whose data lives in packaged engine assets, one whose data lives in a community wiki and spreadsheet. The catalog layer is pluggable for that reason.
- **Every catalog record carries its evidence.** Read from a game asset, taken from a community source, or established by a controlled in-game measurement, plus a confidence and the game build it describes.
- **Normalized facts only.** Raw scrapes, verbatim third-party prose, extracted assets, decryption keys and save files are never committed. They are derived from a licensed local install or from someone else's copyrighted text.
- **No circumvention.** If a source is protected, it is closed. There is no code here that decrypts protected content, patches an executable, or reads another process's memory.

## Development

```sh
uv sync             # create the environment
bin/install-hooks   # once per clone: gitleaks and commit-message gates
bin/ci              # the exact checks CI runs
```

## License

MIT. See [LICENSE](LICENSE).
