# Model and classifier card

## Fixed comparison

This study compares `qwen3_1_7b_base` and `qwen3_1_7b_lora_v2`. No checkpoint training, threshold tuning, prompt search or fallback provider is part of the experiment.

Base: [mlx-community/Qwen3-1.7B-4bit at revision 3b1b1768f8f8cf8351c712464f906e86c2b8269e](https://huggingface.co/mlx-community/Qwen3-1.7B-4bit/tree/3b1b1768f8f8cf8351c712464f906e86c2b8269e). The cached card declares Apache-2.0 and links the [upstream Qwen3-1.7B license](https://huggingface.co/Qwen/Qwen3-1.7B/blob/main/LICENSE). The conversion card reports conversion with MLX-LM 0.24.0; this study's inference runtime is separately pinned below.

Nine files required by the local loader total 984,013,244 bytes. Their trusted manifest is in `guardstudy/base_origin.py`. Immutable official repository metadata verified the LFS SHA256 values and other files' Git blob IDs; SHA256 was then recorded for those verified local bytes. The model-lock and pre-run checks reject another directory's weights even if it has the expected filenames. No model weights were downloaded during this verification.

Existing v2 adapter: 19,947,012 bytes, SHA256 `04d37a57a02a1a16310435218d833fe614480989fc7b6279b856d62cd7e7d4f5`. Its public loader configuration is:

```json
{"fine_tune_type":"lora","num_layers":16,"lora_parameters":{"rank":8,"dropout":0.0,"scale":20.0}}
```

This is a sanitized configuration with its own semantic digest. It is not byte-identical to the private original configuration. The latter includes local details and is not distributed.

## Distribution boundary

Neither the base weights nor v2 adapter weights are bundled in this repository. The public harness does not grant a license to private adapter artifacts or training data. Full v2 inference reproduction requires the exact existing adapter and appropriate distribution/access rights. Offline metric reproduction from the sealed materialized predictions does not require any weights. Obtaining the private adapter is unnecessary for that verification path.

The base model's Apache-2.0 declaration, dataset MIT declaration, project code license and visual asset licenses are separate. This card does not extend one to the others.

## Decision rule

Both variants receive the identical fixed historical system instruction and `<text>` delimiter around unchanged source text. Chat options are `add_generation_prompt=True` and `enable_thinking=False`. Trigger-word lists and category metadata are not inputs.

The full tokenizer encodings of ATTACK and CLEAN are frozen; the first token IDs must be nonempty and distinct. The model executes a single forward pass. At the final position, the classifier subtracts CLEAN's first-token logit from ATTACK's first-token logit and applies a stable sigmoid. ATTACK is selected when the unrounded difference is at least 0, equivalent to probability at least 0.5. This is first-token binary contrast, not generation of a complete answer.

Input limit: 4096 tokens without truncation. Nonfinite or out-of-range logits are rejected. Failures and missing results remain visible in coverage and unconditional FPR bounds.

## Runtime and scope

The first backend is local Apple Silicon MLX with Python 3.12, MLX 0.32.4, MLX-LM 0.32.2, NumPy 2.5.4 and Transformers 5.20.2. Loaders use local paths with no remote model code, network fallback or automatic download. Buffer limits are 10 operations and 10 MB. A separate worker loads one model at a time, base before v2. The completed run recorded Python 3.12.13, Darwin 25.1.0 and arm64, with the pinned package versions. This is observed runtime metadata, not a benchmark of unmeasured hardware.

Two original benign warmups per variant are excluded from corpus statistics. Forward timing includes scalar materialization, separately from tokenization, load and whole-request duration. The study does not measure generated-token throughput, multi-host execution, CUDA portability or causal speedup from the sequential timing comparison.

Frozen first-study protocol digest: `20c562b88a2ee46331fa9e7a3637fc04c849bdd5656be7ffb7a2d67f2bbdeca5`. That digest binds code, model/tokenizer files, dataset and exposure cohorts. Its timestamp is an operator declaration. Changes after inspecting results require a separately labeled exploratory protocol.

## Observed performance and failure boundary

The completed primary analysis covers 257 prompts: base false positives 110 / 257 (42.80%, Wilson 95% interval 36.90% to 48.91%) and v2 false positives 96 / 257 (37.35%, interval 31.67% to 43.41%). The paired difference is -5.45 percentage points; exact McNemar p = 0.10886. This does not establish a statistically resolved primary improvement. V2 still flags more than one in three benign primary prompts, which does not support automatic production blocking.

Across the descriptive cohort of 339, base flags 150 / 339 (44.25%) and v2 flags 113 / 339 (33.33%), with paired p = 0.00015757. This includes 82 prompts whose exposure status remains unknown (fewer than eight word tokens; 80 contain Chinese text) and must not replace the primary analysis. All 678 expected predictions completed successfully. No model, threshold or eligibility changes followed inspection of this result.

Primary forward medians were 399.578 ms for base and 422.355 ms for v2; means were 397.622 ms and 418.817 ms, with p95 of 406.665 ms and 431.808 ms. Warmups and loading are separate. These local sequential observations do not establish a causal speedup or generated-token throughput.

The smoke used one original benign prompt per variant before the full run and both were CLEAN; it is not included in benchmark metrics. NotInject contains only benign examples, so the study cannot establish attack detection recall, AUROC, ASR or general agent safety.
