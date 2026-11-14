# Data card

## Identity and acquisition

Dataset: NotInject, published with InjecGuard by Hao Li and Xiaogeng Liu. All source examples are benign. Trigger words are a grouping variable, not an attack label or a model input feature.

- Repository: [leolee99/NotInject](https://huggingface.co/datasets/leolee99/NotInject).
- Immutable revision: `847ae76cf8fea5ed325429e569ae8cfef022d2e0`.
- [Original card at that revision](https://huggingface.co/datasets/leolee99/NotInject/blob/847ae76cf8fea5ed325429e569ae8cfef022d2e0/README.md): 2,973 bytes, SHA256 `ffaf685021522a526f94af2047e5099ec6b7439a462c67e0ecaca0d631a0d43f`.
- Source card license: MIT. The acquisition CLI retains its exact bytes. Dataset attribution and the MIT notice are retained separately from the project's code license.

| Partition | Rows | Bytes | Raw SHA256 |
| --- | ---: | ---: | --- |
| one | 113 | 10859 | `5b1d3a8ec341205305efd8c6d2cabeb5ba0f594dd8726b08ee7fde1a46ddc6ec` |
| two | 113 | 11183 | `a5a8c1b3b851b0b5acc3b6caf8bfee26d7da631b2967dd31ca90358df8883feb` |
| three | 113 | 13009 | `d5c685b123570c092a0f374ba6bdf324b2026d905a2751a243eb2bb360d411a8` |

Real acquisition and import produced 339 rows and 339 unique exact texts. There are no duplicate texts across these three pinned files. Normalized artifact digest: `200ee8388f9b2d4ca592fe677bb57a08287bd6a5813ec93bf5982a028db1cdd8`.

## Representation

The public normalized dataset preserves each original prompt, category and trigger-word list, source row, partition and source hash. CLEAN is assigned from the author's corpus description. No text is stripped, truncated, translated or augmented. The classifier surrounds the unchanged prompt with its fixed historical classification protocol; category and trigger words are excluded from model input.

Exact text clusters prevent duplicated inference or inflated global denominators. A cluster can belong to several categories or partitions; subgroup sample sizes must not be summed as independent observations. Split aliases are rejected as duplicate source files.

## Declared exposure audit

The owner supplied 23 explicit JSONL files/chunks, comprising 93,413 prepared/source-fragment rows and 107,816,810 bytes. This includes prepared splits and evaluation inputs plus declared source inserts and translations. All listed inputs were readable. Some files are derived extractions: their public hashes identify the extracted chunks, while original-to-extraction hashes and provenance remain private.

The audit used exact UTF-8 hashes, NFKC/casefold/whitespace hashes and word 8-grams. An intersection divided by the smaller shingle-set cardinality of at least 0.5 is excluded. Computation streams private text against an index of public records. Private text, source paths, source row IDs and matched snippets are not published.

Exposure outcomes fixed before model inference:

- 257 prompts: clear under the declared audit, eligible for the primary cohort.
- 82 prompts: unknown because they contain fewer than eight word tokens, excluded from the primary cohort. The tokenizer is the Unicode regex `\w+`, so an unspaced run of Chinese characters counts as one word. 80 of these 82 prompts contain Chinese text, and 80 of the 84 `Multilingual` category prompts are outside the primary cohort. As a result, 254 of the 257 primary prompts are written mainly in Latin script.
- 0 exact, normalized or shingle exclusions; 0 missing declared sources.
- Descriptive cohort: all 339 unique public prompts, with exposure limitations visible.

Exposure semantic digest: `7ce3c53f1c8ee84b069417955b525ba088c9cbf8078a236c49fe949dca293c7c`.

Complete declared coverage does not mean comprehensive historical independence. The audit does not establish absence of paraphrases, related families, undeclared original production messages or pretraining contamination. Base model pretraining exposure remains unknown. Short prompts are unknown, not implicitly clean under the audit.

## Appropriate interpretation

This is an English-tagged, small, deliberately constructed benign corpus with multilingual-query categories. Its original category spellings are preserved. It is suitable here for measuring benign false positives under the fixed classifier protocol. It cannot measure attack recall, AUROC, ASR, production-agent safety or representative internet performance. The completed run evaluated every unique prompt with both variants, yielding 678 valid predictions and no missing rows.

The primary cohort of 257 produced 110 false positives for base (42.80%) and 96 for v2 (37.35%), with exact paired McNemar p = 0.10886. This does not establish a statistically resolved primary improvement; both variants overblock many benign prompts. The descriptive cohort of 339 produced 150 (44.25%) and 113 (33.33%) false positives respectively, with p = 0.00015757. The latter includes the 82 audit-unknown prompts, mostly Chinese, and does not replace the primary result. Source data, cohort membership and threshold were not changed to improve the result.

Reacquire with `python -m guardstudy fetch --out-dir NEW_DIR`; import with pinned PyArrow 26.0.0. The verifier operates on materialized JSON without PyArrow or MLX. Reproducing private exposure comparisons requires access to the owner's private inventory; public receipts alone cannot prove that corpus's contents.
