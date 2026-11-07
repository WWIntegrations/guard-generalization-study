# Design

The core is a Python package with no runtime dependencies for JSON verification, statistics and reporting. Optional Parquet parsing and MLX inference are isolated in child processes. The frontend consumes verified bytes and does not recompute study metrics.

## Artifact flow

`acquire -> dataset -> private exposure receipt -> model lock -> frozen protocol -> predictions -> report -> recorded manifest`

Each phase binds the preceding semantic digest. Dataset rows retain exact source text and their source partition; exact text hashes form unique clusters. The representative is the first source row in one, two, three order. A cluster can belong to more than one category or partition. Inference runs once per unique text and variant.

The frozen protocol records classifier text/template, tokenizer label sequences, threshold, source hashes, cohorts, resource limits and runtime pins. The worker checks current local files before loading. Only first-token ATTACK and CLEAN logits are compared. Probability is a numerically stable sigmoid of their difference. No generated answer is counted as a token throughput measurement.

## Failures and statistics

An expected prediction has status ok, invalid or not_attempted. A worker crash invalidates its current row and leaves later rows explicitly not attempted. The other variant may continue within the overall deadline. An overlength input is a deterministic row failure without truncation. A successful result is retained if the worker exits immediately afterward.

Reports expose expected count, attempts, valid results, invalid results, missing results, FP, CLEAN and coverage. FPR among successful results uses that denominator; unconditional bounds account for all missing outcomes. Paired results use only common valid rows. Latency uses arithmetic mean, interpolated median and nearest-rank p95, separately from model loading and warmup.

## Filesystem publication

Every destination is create-only. A temporary regular file is written fully in private staging outside the bundle on the same filesystem, then file-fsynced and linked to its final name without clobbering. The containing directory is fsynced. EEXIST remains an error even for identical bytes. Staging may remain after a crash and a second hardlink is allowed.

Artifacts are published before the manifest. The manifest link is the visibility commit point. A later directory fsync failure can leave a complete, readable bundle while the producer returns failure. No automatic rollback or deletion follows.

Computed study status, observed output state and producer durability acknowledgement are separate. Output observation can be absent, partial, complete or unknown. A permission or I/O read error is not absence. Offline verification reports current integrity and `producer_durability:not_evaluated`; it cannot recover the producer's past acknowledgements.

## Reproduction boundary

`load_verified_bundle` reads bounded raw bytes once, validates hashes and schemas, checks foreign keys and reconstructs the report. Returned `raw_files` are the same bytes that were verified and are suitable for exact downloads. The verifier does not import model or parser packages and does not need access to the private exposure inventory or adapter.

Hashes are integrity bindings, not signatures or proof of execution. The dataset-normalization derivation and runtime observations depend on the producer; the acquisition pipeline is separately reproducible from immutable public source bytes.
