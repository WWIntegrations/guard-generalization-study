# System map: guard-generalization-study

Each diagram shows one real path through this repository. A highlighted box is a step that can reject its input; a vertical bar marks the boundary between zones.

[Back to the README](../README.md)

## Fetching the public corpus

The fetch command is the only step that uses the network. It can request only the files named in the built-in source lock, and every answer is checked before it is saved.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="system-map/fetch-source-lock-dark.svg">
  <img src="system-map/fetch-source-lock-light.svg" alt="The fetch command takes a file from the built-in source lock. The address must resolve to a public endpoint, the connection must be HTTPS to the same peer, and the bytes must match the locked size and SHA-256 before they are written." width="100%">
</picture>

Source: [`guardstudy/acquire.py`](../guardstudy/acquire.py), [`docs/threat-model.md`](../docs/threat-model.md), [`tests/test_acquire.py`](../tests/test_acquire.py)

## From raw files to a frozen protocol

Four commands turn the raw files into a protocol that binds the dataset, the private exposure audit and the exact model files. Each one writes into a new directory.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="system-map/prepare-and-freeze-dark.svg">
  <img src="system-map/prepare-and-freeze-light.svg" alt="The import command writes dataset.json. The exposure command reads the private inventory and writes a hash-only receipt. The model-lock command pins base and adapter files, and freeze binds all three into protocol.json." width="100%">
</picture>

Source: [`guardstudy/cli.py`](../guardstudy/cli.py), [`guardstudy/acquire.py`](../guardstudy/acquire.py), [`guardstudy/exposure.py`](../guardstudy/exposure.py), [`guardstudy/protocol.py`](../guardstudy/protocol.py)

## The only command that runs a model

The coordinator never imports MLX. It checks the frozen bindings, then supervises one worker process that scores every prompt with base and then LoRA v2, and keeps every row whatever happened.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="system-map/run-inference-dark.svg">
  <img src="system-map/run-inference-light.svg" alt="The run command checks the protocol against the dataset, local model files and runtime versions. A separate MLX worker scores each prompt under deadlines. Each expected row is saved as ok, invalid or not_attempted." width="100%">
</picture>

Source: [`guardstudy/runner.py`](../guardstudy/runner.py), [`guardstudy/worker_mlx.py`](../guardstudy/worker_mlx.py), [`guardstudy/protocol.py`](../guardstudy/protocol.py), [`tests/test_runner.py`](../tests/test_runner.py)

## What seal writes and in what order

Evaluate rebuilds the report from saved predictions. Seal does the same, refuses fixture output, writes every artifact as a new file and links the manifest last, so a visible manifest means a complete bundle.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="system-map/seal-bundle-layout-dark.svg">
  <img src="system-map/seal-bundle-layout-light.svg" alt="Saved predictions must cover every expected row and come from the real MLX backend. The report is rebuilt from them. Artifacts are written create-only and the manifest is linked last as the commit point." width="100%">
</picture>

Source: [`guardstudy/recorded.py`](../guardstudy/recorded.py), [`guardstudy/io.py`](../guardstudy/io.py), [`docs/design.md`](../docs/design.md), [`tests/test_recorded.py`](../tests/test_recorded.py)

## How a damaged bundle is rejected

Verify and report read the bundle once into memory and check that same snapshot. Any extra file, symlink, wrong hash or report that does not match the saved predictions stops with a closed error code and exit 2.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="system-map/verify-rejects-damage-dark.svg">
  <img src="system-map/verify-rejects-damage-light.svg" alt="The recorded directory is read once with size limits, refusing symlinks and unexpected files. Hashes, schemas and bindings are checked and the report is recomputed. Only then does the command print a summary, JSON or Markdown." width="100%">
</picture>

Source: [`guardstudy/recorded.py`](../guardstudy/recorded.py), [`guardstudy/io.py`](../guardstudy/io.py), [`guardstudy/cli.py`](../guardstudy/cli.py), [`tests/test_recorded.py`](../tests/test_recorded.py)

## Which file does which step

The package follows the artifact flow. cli.py dispatches the ten phase commands, io.py and schemas.py hold the strict JSON and create-only writes used by every step.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="system-map/module-map-dark.svg">
  <img src="system-map/module-map-light.svg" alt="acquire.py and exposure.py prepare the inputs. protocol.py and runner.py freeze and supervise the run. worker_mlx.py does the scoring. recorded.py and metrics.py build the report, seal and verify." width="100%">
</picture>

Source: [`guardstudy/cli.py`](../guardstudy/cli.py), [`guardstudy/io.py`](../guardstudy/io.py), [`guardstudy/schemas.py`](../guardstudy/schemas.py), [`guardstudy/metrics.py`](../guardstudy/metrics.py), [`guardstudy/summary.py`](../guardstudy/summary.py)

## How it is verified

Every push runs the Python tests on two versions, verifies the real recorded bundle and rebuilds the viewer to confirm it is byte for byte the published one.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="system-map/ci-checks-dark.svg">
  <img src="system-map/ci-checks-light.svg" alt="A push or pull request starts the contracts job, which runs unittest on Python 3.11 and 3.14 and then verifies examples/recorded. The interface job runs Node tests and compares a fresh viewer build with docs/index.html." width="100%">
</picture>

Source: [`.github/workflows/checks.yml`](../.github/workflows/checks.yml), [`docs/verification.md`](../docs/verification.md), [`tests/test_recorded.py`](../tests/test_recorded.py), [`showcase/test_build_assets.py`](../showcase/test_build_assets.py)
