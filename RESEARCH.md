# Research record

## Prespecified question

How often do a frozen Qwen3-1.7B base classifier and an existing LoRA v2 classify NotInject benign prompts as ATTACK? The threshold is 0.5, equivalently last-token ATTACK logit minus CLEAN logit greater than or equal to zero. No checkpoint selection, tuning, prompt search or threshold sweep is part of this study.

## Completed result: primary cohort first

The frozen run completed 678 valid predictions, 339 per variant, with no missing or invalid rows. The primary cohort contains 257 prompts whose declared audit status is clear; 82 short prompts remain excluded from this primary analysis. The retained protocol digest is `20c562b88a2ee46331fa9e7a3637fc04c849bdd5656be7ffb7a2d67f2bbdeca5`.

| Primary cohort | FP / valid | FPR | Wilson 95% interval | Coverage |
| --- | ---: | ---: | --- | ---: |
| Base | 110 / 257 | 42.80% | 36.90% to 48.91% | 100% |
| LoRA v2 | 96 / 257 | 37.35% | 31.67% to 43.41% | 100% |

The primary paired comparison has 40 prompts flagged only by base, 26 flagged only by v2, 70 flagged by both and 121 flagged by neither. The v2-minus-base FPR difference is -5.4475 percentage points. Two-sided exact McNemar p = 0.1088569644. This is an observed reduction, not a statistically resolved primary superiority claim. The remaining false-positive rate is high: v2 rejects 96 benign primary prompts.

## Descriptive cohort and interpretation

All 339 unique public prompts form a separate descriptive cohort, including the 82 exposure-unknown short prompts. Base flags 150 / 339 (44.25%; Wilson 95% interval 39.05% to 49.57%), and v2 flags 113 / 339 (33.33%; interval 28.53% to 38.51%). There are 65 base-only false positives, 28 v2-only, 85 common false positives and 161 common clean decisions. The paired difference is -10.9145 percentage points, with exact McNemar p = 0.0001575708.

The descriptive result must not substitute for the prespecified primary result. Among the 82 short prompts excluded from primary, the counts are 40 base false positives and 17 v2 false positives (25 flagged only by base, 2 only by v2), so they supply 23 of the 37-prompt net reduction in the descriptive cohort. "Short" means fewer than eight Unicode regex word tokens: 80 of the 82 contain Chinese text, where an unspaced run of characters counts as one word. As a result the primary cohort holds only 4 of the 84 `Multilingual` category prompts, and the larger descriptive difference mainly reflects v2's lower false-positive rate on Chinese prompts. The eligibility rule was not revised after seeing these results.

Every expected row completed, so observed FPR and missingness bounds coincide in this run. Wilson intervals remain conditional sampling calculations, not guarantees about arbitrary traffic. No attack recall, AUROC, precision, F1 or ASR can be measured on this benign-only corpus. No category-level significance claim is made without a prespecified multiplicity treatment.

The result demonstrates substantial overblocking under this classifier protocol, including after LoRA tuning. It does not support automatic production blocking. The experiment is retained as completed evidence; neither checkpoint selection nor threshold tuning was used to improve the reported outcome.

## Local forward timing

These are observations from the same sequential base-then-v2 run, not a randomized performance comparison. Forward timing includes scalar materialization and excludes tokenization, model loading and warmup.

| Cohort and variant | n | Mean, ms | Median, ms | p95, ms |
| --- | ---: | ---: | ---: | ---: |
| Primary base | 257 | 397.622 | 399.578 | 406.665 |
| Primary v2 | 257 | 418.817 | 422.355 | 431.808 |
| Descriptive base | 339 | 392.410 | 399.352 | 406.184 |
| Descriptive v2 | 339 | 414.028 | 421.854 | 430.293 |

Recorded runtime: Python 3.12.13, Darwin 25.1.0, arm64, MLX 0.32.4, MLX-LM 0.32.2, NumPy 2.5.4 and Transformers 5.20.2. Buffer limits were 10 operations and 10 MB. Load durations were approximately 740.240 ms for base and 594.226 ms for v2; each had two separate warmups. These are local runtime observations, not fresh proof of a particular chip model, cold-cache loading, causal speedup or cross-device portability.

## Source and observed acquisition

NotInject is published by Hao Li and Xiaogeng Liu with the InjecGuard research project. The original dataset card declares MIT and identifies every sample as benign. The pinned revision is `847ae76cf8fea5ed325429e569ae8cfef022d2e0`.

Sources: [dataset revision](https://huggingface.co/datasets/leolee99/NotInject/tree/847ae76cf8fea5ed325429e569ae8cfef022d2e0), [dataset card](https://huggingface.co/datasets/leolee99/NotInject/blob/847ae76cf8fea5ed325429e569ae8cfef022d2e0/README.md), [research paper](https://arxiv.org/abs/2410.22770).

The acquisition performed for this project downloaded exactly three Parquet files, 35,051 bytes in total, plus the 2,973-byte original card. All four SHA256 values matched the locked values. PyArrow 26.0.0 imported 113 records per partition, 339 total and 339 unique exact texts. The normalized dataset semantic digest is `200ee8388f9b2d4ca592fe677bb57a08287bd6a5813ec93bf5982a028db1cdd8`.

Source prompts are preserved exactly. Trigger words and category metadata are not classifier features. Apparent train/validation/test aliases are not additional samples.

## Models and licenses

The [MLX base card](https://huggingface.co/mlx-community/Qwen3-1.7B-4bit/tree/3b1b1768f8f8cf8351c712464f906e86c2b8269e) declares Apache-2.0 and links the upstream Qwen3-1.7B license. The MLX conversion and the upstream model are distinct artifacts; the study hashes the actual local converted weights and tokenizer files.

The existing v2 adapter has SHA256 `04d37a57a02a1a16310435218d833fe614480989fc7b6279b856d62cd7e7d4f5` and size 19,947,012 bytes. Its sanitized public loader configuration contains only LoRA type, layer count, rank, dropout and scale. The private original configuration is not copied. Adapter weights and private training data are not released. A public harness and materialized public-input predictions do not imply a license grant for those private artifacts.

The NotInject card and MIT notice concern the dataset. They do not license models, fonts, private training data or other repositories. Visual asset licenses are tracked separately by the frontend.

## Exposure analysis

The data owner supplies a bounded inventory of known prepared splits, evaluation inputs, source inserts and translations. Exact UTF-8 hashes, NFKC/casefold/whitespace hashes and overlapping word 8-grams are checked locally. A shingle intersection divided by the smaller set cardinality of at least 0.5 is excluded. Prompts with fewer than eight word tokens remain unknown, not clear. Word tokens are Unicode regex `\w+` matches, so text written without spaces, such as Chinese, usually falls in this group. Partial inventory coverage makes the primary cohort empty.

This method cannot establish that paraphrases, related attack families or pretraining contamination are absent. Base model pretraining exposure remains unknown. Known training sources are not relabeled as external holdouts.

## Evidence status

- Pinned public data acquisition and import: performed.
- CPU model artifact/tokenizer lock: prepared against the existing local cache. Nine loader files, 984,013,244 bytes, were also matched against immutable official repository metadata: SHA256 for LFS files and Git blob IDs for other files, then SHA256 of those verified bytes. No model weights were downloaded.
- Private exposure audit: 23 declared files/chunks, 93,413 prepared/source-fragment rows, 107,816,810 bytes. All declared inputs were readable. Of the public prompts, 257 were clear under this audit and 82 remain unknown because they are shorter than eight words. No exact, normalized or shingle exclusions were observed. Extracted chunk hashes identify derived inputs; the owner retains the original-to-extraction provenance privately. This does not cover an original production message store or base pretraining.
- Real smoke: one original benign prompt per variant completed before the benchmark; both were CLEAN. Smoke results are excluded from study metrics.
- Real benchmark: completed 678 / 678 valid predictions under the frozen protocol, with no tuning or missing outcomes.
- Read-only outcome review: all prediction IDs, text hashes, decisions and probabilities checked; independent counts, Wilson intervals, latency summaries and paired comparisons matched both cohorts and all 14 reported subgroup analyses. Runtime consistency and the exact run/freeze protocol bytes matched. Sealing is a separate publication operation.

The high false-positive result is retained. The result review rehashed eight small base-loader files and the v2 adapter; the large base weight file was not redundantly rehashed during that review. Its frozen hash and size were preserved, and the run performed its own binding checks before loading. Hash consistency is not independent authentication of execution or measurement truth.
