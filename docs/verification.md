# Verification record

Verified locally on 2026-11-07. These observations establish the tested behavior, not independent provenance, production reliability or unseen-data generalization.

## Experiment and portable evidence

The frozen run completed 678 predictions: both variants evaluated all 339 public benign prompts, with zero invalid or missing rows. The prespecified primary cohort contains 257 prompts clear under the declared exposure audit. The other 82 prompts are too short for that audit and remain descriptive.

Primary false positives are 110/257 for base and 96/257 for LoRA v2. The paired difference is -5.45 percentage points, with exact McNemar p = 0.10886. This does not establish a statistically resolved primary improvement. The lower descriptive p-value does not replace that result. Attack recall and other single-class-inapplicable metrics remain null.

An independent arithmetic check recomputed counts, paired discordances, intervals and latency summaries from saved outputs. A separate code and result review checked all 678 predictions and both cohorts, including 14 subgroup summaries. Neither review reran inference or independently witnessed the protocol freeze.

The producer reported completed publication with filesystem durability acknowledged. The subsequent read-only verifier reported valid integrity for all 12 files, while correctly leaving producer durability unevaluated. Manifest SHA256: `702d9964128914beeee9390711033ce426ae33a003e46ba032be9ad38468e350`.

Fifty Python core tests passed locally on Python 3.14.6 in 5.032 seconds. A separate Python 3.12 run also passed all 50. Tests cover bounds, malformed and contradictory evidence, missing results, exposure matching, cohort accounting, model binding, deadlines and create-only publication. These use controlled fixtures; the published example bundle comes from actual MLX inference.

## Interface and local server

Twelve Node tests and six Python builder tests passed. The final build reproduces the recorded viewer byte for byte. HTML SHA256: `8ed458934d36b23d606c88d219e8f5b8666a7ad6f680d3804b1c2e788ec880c5`.

Chrome/Playwright completed 2,689 assertions across seven contexts: desktop 1440x900, mobile 390x844, small 320x740, tablet 768x1024, reduced motion, unavailable WebGL and unresolved font loading. The run checked all 339 exact prompt texts and prediction statuses on desktop, all cohort and subgroup summaries in every context, filters, focus, mobile menu, resize, pause and reduced motion. All 12 downloads were compared byte for byte with the validated snapshot in desktop and no-WebGL contexts, giving 24 checked exports. There were zero page errors, zero external runtime requests and no horizontal page overflow. Assertion counts include repeated viewports and state combinations, not independent experiments.

Earlier browser passes found real layout overflow from the decorative ring and an oversized rotated heading. A local mask now contains only the ring; the heading fits through responsive typography without clipping text. An early menu-focus failure was a test timing error: the native dialog close event had not yet run. The final harness waits for that event's focus result. These failures were retained during development; the figures above describe the complete final pass.

The local server returned the custom 404 for five denied paths, including a repository file, directory listing, dotfile path, traversal path and arbitrary missing page. Its 404 rendered without overflow at 1440, 390 and 320 pixels. Architecture SVG XML and browser rendering passed. Static review found no remaining high or medium priority issues in the reviewed code, viewer, documentation, server and CI scope; review alone is not a runtime test.

## Reproduction limits

Offline verification needs no model or third-party Python package. Repeating v2 inference also needs the exact separately held adapter, compatible Apple Silicon runtime and the locked model files. Hashes bind bytes, not an operator's identity, historical freeze time or timing truthfulness.

CI is configured for Python 3.11/3.14, Node 22, real-bundle verification and deterministic viewer rebuild. The actual CI result is available in the repository's Actions history. No hosting deployment or full pixel-identical visual certification is claimed. See [visual design](visual-design.md) and [media provenance](media-provenance.md).

Made by WW
