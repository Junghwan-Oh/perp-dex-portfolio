# Provenance

- Source project: Junghwan-Oh/2dex (private); source commit and full-file hashes are in `source-manifest.json`.
- `portfolio_bot/source_core.py`: exact `HedgeBot2DEX.executeHedgeCycle` method and `OrderResult` dataclass extracted from the referenced source. The host class is renamed `HedgeBotCore`, and only standard-library imports are retained. Live initialization, factories and adapters are excluded.
- `portfolio_bot/demo.py` and `tests/test_cycle.py`: newly prepared offline demonstration and tests; these are not represented as historical production code.
- The source project incorporates upstream work from https://github.com/your-quantguy/perp-dex-tools. Original copyright: Copyright (c) 2024 Binance Scalping Bot. The unchanged license is included.
- A new public repository should be initialized from these files only, without copying `.git` or publishing branches/tags from the private project.
