# Threat model

## Inputs and trust

Public dataset text is untrusted data. It is not executable HTML, shell input, tool instructions or code to import. Private exposure sources are read only from an explicit inventory. They are never copied into the public bundle. Model loading is local-only and rejects executable model code; the optional worker denies socket connection and DNS audit events.

The host, Python runtime, filesystem administrator and model libraries are trusted. This is process isolation and bounded input handling, not a hostile-code sandbox or a hardened defense against a privileged local adversary. Parquet child timeout is not a hard RSS limit.

## Acquisition

Only built-in immutable NotInject files can be requested through the CLI. Every redirect is HTTPS on port443, without user credentials. Public DNS answers are pinned to the socket address and checked against the connected peer, while TLS verifies the original hostname. Private, loopback, link-local and transition addresses are rejected. The fetch child enforces a whole-operation deadline, including DNS. Bytes are bounded and hashes and exact sizes are checked before parsing. Unsupported CDN behavior is an explicit failure; it does not enable a weaker fallback.

## Artifact integrity

JSON duplicate keys, nonfinite numbers, lone surrogates, excessive nesting and unexpected fields are rejected. Integers cannot be booleans. Public artifact reads reject symlinks and nonregular files and enforce byte limits. Bundle paths are relative POSIX paths with no traversal. Unexpected files are refused. Hash validation uses the same in-memory byte snapshot as report reconstruction.

Create-only publication never treats an existing destination as an implicit retry. A file or directory sync failure after manifest publication does not imply that the bundle is absent. Verification confirms current content and never invents producer durability or execution authenticity.

## ML and privacy

The coordinator launches only its own sequential worker processes and terminates only those process groups. Worker stderr is discarded rather than exported with local paths. Errors are closed codes. Private inventory paths and original configuration values do not belong in public runtime metadata. The worker receives only public source prompts and its fixed classifier protocol, never private training rows.

Exposure receipts contain neutral file identifiers, full-file hashes, counts and public row outcomes. Hashes are not a proof that unseen semantic families are absent. Missing source coverage never becomes a clear result. Base pretraining exposure remains unknown.

## Residual risks

A malicious operator can fabricate coherent predictions, timestamps, runtime measurements and receipts. Hashes do not authenticate those claims. Statistical uncertainty and the chosen benign corpus limit external validity. Public adapter distribution has a separate rights boundary. Hostile concurrent mutation of ancestor directories is outside the trusted local-workspace assumption. No claim of production agent safety, multi-host robustness, GPU portability or salary outcomes follows from this study.
