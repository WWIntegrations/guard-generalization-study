# Guard Generalization Study

Use it when you need to check how often a frozen prompt-injection classifier flags harmless prompts, and to verify and re-read a saved study without rerunning any model.

## Quickstart

```sh
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -e .
python3 -B -m guardstudy verify --recorded-dir examples/recorded
python3 -B -m guardstudy report --recorded-dir examples/recorded
python3 -B -m guardstudy exposure --dataset examples/recorded/dataset.json --private-inventory examples/own-data/inventory.json
```

All three commands exit 0, run offline and print a short summary (add `--json` for machine output). `verify` prints:

```text
integrity: valid
study status: completed
files verified: 12
protocol digest: 20c562b88a2ee463
producer durability: not_evaluated (integrity only, not who ran it or when)
```

`report` prints the false-positive table below plus the limits. `exposure` is the own-data step: it compares private text (here `examples/own-data/private-sample.jsonl`, listed in `inventory.json`) with the public prompts and saves a hash-only receipt in a new `exposure-out` directory (`exposure-out-2` on the next run). Edit `inventory.json` to point at your own `.jsonl` file with `tekst` or `messages` rows. Its summary for the sample:

```text
exposure audit: coverage complete_declared_inventory
public prompts checked: 339
  clear_under_audit    256
  excluded_exact       1
  unknown_short        82
private sources read: 1, unreadable or empty: 0
```

Run the tests with `python3 -B -m unittest discover -v`. Running a new model needs the optional MLX setup and local weights (see below); only `fetch` uses the network.

A personal research project measuring how often a frozen prompt-injection classifier rejects benign prompts. The first study compares Qwen3-1.7B base with an existing LoRA v2 on NotInject, a public corpus of 339 benign prompts containing trigger words.

The completed frozen run shows substantial benign overblocking. In the prespecified primary cohort of 257 prompts, base incorrectly flagged 110 prompts (42.80%) and LoRA v2 flagged 96 (37.35%). The paired difference is -5.45 percentage points, with exact McNemar p = 0.10886. This does not establish a statistically resolved primary improvement. Even v2 incorrectly flags more than one in three benign primary prompts.

| Primary cohort, n = 257 | False positives | FPR | 95% Wilson interval |
| --- | ---: | ---: | --- |
| Base | 110 / 257 | 42.80% | 36.90% to 48.91% |
| LoRA v2 | 96 / 257 | 37.35% | 31.67% to 43.41% |

Across all 339 unique prompts, the descriptive result is 150 / 339 (44.25%) for base and 113 / 339 (33.33%) for v2; paired p = 0.00015757. That broader cohort includes 82 short prompts with unknown audit status. Its smaller p-value does not replace the primary result or establish general unseen-data performance.

Both variants produced all 339 expected predictions: 678 valid results, no missing or invalid rows, 100% coverage. The completed experiment used the frozen checkpoint, classifier and threshold; no tuning followed inspection of NotInject results. These false-positive levels do not justify automatic production blocking.

The harness preserves unsuccessful predictions, recomputes false-positive rates from saved outputs and distinguishes an intact bundle from a producer that confirmed filesystem durability. It is not a deployment guardrail or an evaluation of attack recall.

![Recorded experiment and interactive evidence viewer](docs/demo.gif)

[Watch the full recording](docs/showcase.mp4) or open the viewer locally:

```sh
python3 -B tools/serve.py
```

Visit `http://127.0.0.1:3415/docs/index.html`. The self-contained viewer exposes every public prompt, both saved predictions, cohort filters and exact-byte evidence downloads. It runs offline and does not perform model inference. The recording shows the real saved study, including an illustrative benign prompt rejected by both models.

![Study inputs, frozen inference and verified evidence](docs/architecture.svg)

See [verification](docs/verification.md), [media provenance](docs/media-provenance.md) and [visual design](docs/visual-design.md).

## Portable core

`verify` and `report` read the sealed real-run bundle in `examples/recorded` and reproduce saved metrics without model inference. `report --out report.md` also writes Markdown to a new file; that name is create-only, so use a fresh path each time. Commands that create a directory default to `<command>-out`, then `<command>-out-2` and so on.

The Python API `guardstudy.recorded.load_verified_bundle(path)` returns validated `manifest`, `report`, `dataset`, `predictions`, `exposure`, `protocol` and `raw_files`. Export the returned bytes, rather than re-reading the directory. Verification uses that same bounded snapshot and never imports MLX, PyArrow or Transformers.

## Acquire and prepare the study

Run from a checkout. Parquet import alone requires PyArrow 26.0.0. Fetch accepts only the four immutable files in the built-in source lock, including the original dataset card; HTTP credentials and proxy environment settings are not used.

```sh
python3 -B -m guardstudy fetch --out-dir acquisition
python3 -B -m guardstudy import --raw-dir acquisition/raw --out-dir imported
python3 -B -m guardstudy exposure --dataset imported/dataset.json --private-inventory /private/location/inventory.json --out-dir audit
python3 -B -m guardstudy model-lock --base-dir /local/model --adapter-dir /local/adapter --out-dir model-lock
python3 -B -m guardstudy freeze --dataset imported/dataset.json --exposure audit/exposure-receipt.json --model-lock model-lock/model-lock.json --out-dir frozen
```

The inventory is explicitly provided by the data owner. Each source has a neutral `source-001` style ID, a private JSONL path and kind `prepared_rows`, `source_inserts` or `translations`. Its `declared_complete` field describes the listed inventory, not every possible historical exposure. The public receipt contains whole-file hashes and aggregate counts, never private text, paths, row IDs or snippets. Without complete declared coverage, the primary cohort is empty and inconclusive; the descriptive cohort remains available.

`model-lock` performs CPU tokenization and hashes local artifacts. It does not execute model forwards. The base checkpoint, adapter, tokenizer files, classifier template, runtime versions and implementation files are bound before a study run. Any subsequent source change requires another freeze. The declared time is an operator statement, not a trusted timestamp.

## Optional local inference

The first configured backend is MLX on Apple Silicon, Python 3.12, MLX 0.32.4, MLX-LM 0.32.2, NumPy 2.5.4 and Transformers 5.20.2. There is no automatic provider fallback, download, training or threshold search. The base weights and the exact existing v2 adapter must already exist locally. Adapter weights are not distributed with this repository; full v2 inference reproduction therefore requires obtaining that artifact separately with appropriate rights.

```sh
python3 -B -m guardstudy run --protocol frozen/protocol.json --dataset imported/dataset.json --base-dir /local/model --adapter-dir /local/adapter --out-dir run
python3 -B -m guardstudy evaluate --protocol frozen/protocol.json --dataset imported/dataset.json --exposure audit/exposure-receipt.json --predictions-dir run --out-dir evaluated
python3 -B -m guardstudy seal --protocol frozen/protocol.json --dataset imported/dataset.json --exposure audit/exposure-receipt.json --predictions-dir run --out-dir recorded-new
```

Only `run` executes forwards. The worker uses one resident model, base then v2, with fixed buffering limits of 10 operations and 10 MB. Its two warmup prompts are original benign sentences, excluded from dataset metrics. Deadlines are 180 seconds for loading, 30 seconds per row and 3600 seconds for the entire run. The coordinator terminates only its own process groups. Timeouts and invalid outputs remain visible; selected failures are not retried.

`seal` belongs after independent review of the actual run. It rejects a fixture backend. Synthetic data exists only in unit tests, never as a successful example experiment.

## Limits

Python 3.11 or later on Linux or macOS; the offline validator has no third-party dependencies. The harness is not a deployment guardrail or an evaluation of attack recall, and these false-positive levels do not justify automatic production blocking.

- The measured quantity is benign false-positive rate, overall and by source group and category.
- Missing results remain in coverage and unconditional FPR bounds. They are never counted as CLEAN.
- Wilson intervals describe successfully evaluated samples under a Bernoulli assumption. NotInject is not a representative random sample of internet traffic.
- Recall, precision, AUROC, attack success rate and F1 are undefined for this benign-only study.
- Comparisons use common successful pairs and an exact McNemar calculation. Group membership can overlap; group denominators are not independent totals.
- The historical private Guard audit is separate evidence. Recomputing old predictions is not a fresh inference experiment.
- A valid hash bundle does not prove who ran it, when the protocol was frozen, whether timing measurements are truthful or whether an operator received filesystem sync acknowledgements.

See the [results and research scope](RESEARCH.md), [data card](DATA_CARD.md), [model card](MODEL_CARD.md), [design](docs/design.md) and [threat model](docs/threat-model.md). No salary, recruitment outcome, independent adoption or production safety is established by this repository.
