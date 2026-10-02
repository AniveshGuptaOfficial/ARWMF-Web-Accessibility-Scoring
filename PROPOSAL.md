# Adaptive Reliability-Weighted Multimodal Fusion for Offline Web Accessibility Scoring, Validated Against Multi-Rater Human Consensus

**Anivesh Gupta (23BCE0291) — BCSE397J Special Project, VIT Vellore**

## 1. Project title

Adaptive Reliability-Weighted Multimodal Fusion for Offline Web Accessibility Scoring, Validated Against Multi-Rater Human Consensus.

## 2. Abstract

Rule-based accessibility checkers such as Lighthouse and axe-core catch structural violations but cannot judge whether alt-text is meaningful or a layout is actually usable. Recent multimodal large language model (LLM) auditors close that judgment gap, but they depend on large, cloud-hosted models invoked per page, which is impractical for resource-constrained institutions auditing at scale. This project builds a lightweight, fully offline pipeline that fuses classical computer vision (contrast, target size, layout) with a small local embedding model (alt-text and link-text adequacy) into one composite accessibility score. Existing fusion designs, including the project's own earlier static formulation, assign each dimension a single fixed reliability weight for every page. This report extends that design to Adaptive Reliability-Weighted Multimodal Fusion (A-RWMF), where each dimension's weight is conditioned on the page's own content profile, on the premise that a detection module's reliability is not constant across page types — a text-heavy form and an image-dense marketing page do not stress the vision and NLP modules equally. The system is validated against a statistically grounded multi-rater consensus using intraclass correlation, both pooled and stratified by page type, to test whether adapting fusion weights to page context outperforms a single global weighting scheme.

## 3. Literature survey

Ten papers from 2024 to 2026 were reviewed for direct relevance to this project's scope: fused vision and NLP scoring, offline or lightweight deployment, and validation against human raters.

### 3.1 Multimodal accessibility auditors

Gu et al. propose AAA, an auditing framework built on GRASP, a graph-based multimodal sampling method, and MaC, a multimodal LLM copilot that supports human auditors through cross-modal reasoning. The system is effective but depends on a large model per page, and the authors themselves note that smaller fine-tuned models can serve as capable experts, which motivates the lightweight direction of this project.

Fernández-Navarro and Chicano automate accessibility remediation on both static websites and Angular single-page applications, fixing 80 percent of issues on public sites and 86 percent on Angular projects by editing the DOM directly through an LLM and generating image descriptions along the way. Their approach confirms that LLM-driven visual description works in practice, though again at the cost of a cloud model call per page.

### 3.2 Feasibility and reliability of LLM-based auditing

Van de Hoef et al. test a fine-tuned enterprise LLM against prior expert audits of two benchmark pages through a Chrome extension. The model localises problematic code with moderate success but performs weakly at assigning the correct WCAG criterion, and the authors conclude that probabilistic LLM output currently lacks the stability needed to support human auditors unsupervised. This result is a direct argument for reducing reliance on large-LLM judgment in the detection path rather than trying to stabilise it further.

Huang et al. present ACCESS, a benchmark and DOM-correction pipeline that uses prompt engineering with foundation models to fix accessibility violations, reporting a reduction of over 51 percent in violation counts. The work is strong on correction but does not address validation against human judgment.

### 3.3 Alt-text and semantic adequacy

Haque introduces AltIcon, which generates alt-text for UI icons during app development using two fine-tuned models, one text-only and one multimodal, rather than a general-purpose cloud LLM. The method pulls context from the DOM tree and in-icon text via OCR, and produces higher-quality output without needing a full screenshot. This is the closest existing precedent for a lightweight, locally-hosted alt-text scoring component.

Mähr and Twente generate alt-text for a heritage image collection using four vision-language models and validate the output with 21 human raters, using Friedman and Wilcoxon tests to check for significant differences between models. They find the models operationally useful but flag recurring factual errors, and argue for continued human-in-the-loop review. The rater-study design here is a direct template for validating a fused accessibility score against multiple humans rather than one.

### 3.4 Lightweight and on-device vision-language models

Baghel et al. evaluate SmolVLM2 variants at 500 million and 2.2 billion parameters for blind and low-vision description tasks, deploying both on a smartphone at FP32 and INT8 precision to measure real-world performance under mobile constraints. This is the strongest existing evidence that small, on-device vision-language models can support accessibility tasks, though the paper applies it to video description rather than web pages.

### 3.5 Statistical validation of subjective judgment

Kumar, Padath, and Wang benchmark PDF accessibility evaluation across seven criteria with expert-validated annotations, comparing five LLMs against rule-based checkers. GPT-4-Turbo reaches the highest accuracy at 0.85, but all models struggle on documents labelled Not Present or Cannot Tell, and the authors propose a hybrid approach combining automated checkers, LLM evaluation, and human assessment. Ground truth in this study still comes from a single expert panel rather than a formally validated multi-rater consensus.

Kuzikov et al. build a statistical framework for consensus-based reliability assessment among multiple LLM evaluators, using median aggregation and the intraclass correlation coefficient (ICC2k) to decide how much weight to give each rater's judgment. Applied to semantic similarity judgments across 17 models and roughly 14,000 samples, a reduced three-model core reaches an ICC2k of 0.955, only 2.2 percent below the full nine-model core, while cutting compute by 67 percent. Their method measures rater reliability to combine multiple raters into a single consensus; it treats that reliability as fixed once estimated, not as something that shifts with the item being judged, which is the gap this project's adaptive extension addresses. Sadallah and Encelle apply a related five-dimensional scoring framework to 66 multimodal STEM accessibility systems, achieving strong inter-rater agreement (ICC = 0.92) between two independent coders, with weights set by design rather than learned, and constant across all systems evaluated.

## 4. Objectives

1. Build a classical computer-vision module that detects contrast, target-size, and layout violations from page screenshots and computed styles without calling a cloud vision API. Contrast and target size are computed deterministically from WCAG formulas over element geometry; a small CNN classifier for layout remains an optional extension, attempted only if deterministic structural features prove insufficient against human layout ratings.
2. Build a lightweight, locally-hosted embedding model that scores alt-text and link-text semantic adequacy, extending the no-large-LLM approach used for UI icons to full web pages.
3. Implement static Reliability-Weighted Multimodal Fusion (RWMF), deriving each dimension's global weight from its measured agreement with human judgment.
4. Extend RWMF to Adaptive RWMF (A-RWMF), conditioning fusion weights on a lightweight page-context profile (image-to-text ratio, DOM depth, interactive-element count) so reliability is treated as page-dependent rather than fixed.
5. Construct a benchmark of independent human raters per page — floor of three, with the study protocol fixing five per page so ICC confidence intervals remain informative (docs/01) — stratified across at least two to three page-type buckets, and validate all fusion variants using median aggregation and the intraclass correlation coefficient (ICC2k), pooled and per bucket.
6. Compare naive equal-weight fusion, static RWMF, and A-RWMF against a rule-based checker and, where feasible, an LLM-based baseline, reporting accuracy, correlation, and compute cost for each.

## 5. Methodology

### 5.1 Vision pipeline

Page screenshots are captured across common viewport sizes (1280×800 desktop, 390×844 mobile). Foreground and background colours, font sizes, and bounding boxes are extracted per element from computed styles with ancestor-resolved effective backgrounds; WCAG contrast ratios and target-size checks are then computed deterministically from closed-form formulas (WCAG 1.4.3, 1.4.11, 2.5.8). Deterministic extraction is used in place of a learned detector because these criteria are defined over geometry, and a CNN would add training-data requirements and run-to-run variance without adding accuracy on a formula that can be evaluated exactly. The classical vision component also operates on the screenshot itself: Canny edge density provides a layout-clutter index, while heading hierarchy and landmark structure are read from the DOM. If deterministic structural features are shown to correlate poorly with human layout ratings during validation, a small CNN classifier over screenshot patches is the planned extension.

### 5.2 NLP pipeline

Alt-text and link-text are extracted from the DOM. Alt-text is scored by encoding the image region (cropped from the archived screenshot) and its alt-text string with a local, compact embedding model — a CLIP-family vision–language model under 200 M parameters running on CPU — and computing cosine similarity between the two, rather than issuing a per-page LLM call. Deterministic penalties score missing, filename-like, and generic-label alt text at zero before the similarity term applies. Link-text is scored with a lightweight vague-phrase check flagging labels such as 'click here', combined with a compact sentence-embedding comparison of the label against its surrounding context. Both models are downloaded once to a local cache; no page-time network call is made at any point, preserving the offline property.

### 5.3 Static fusion: Reliability-Weighted Multimodal Fusion (RWMF)

On a calibration subset of pages already rated by the human panel, for each accessibility dimension *d* (contrast, target size, layout, alt-text adequacy, link-text clarity), the project computes how well the automated score for *d* agrees with the human consensus for *d*, using the intraclass correlation coefficient — concretely ICC(A,1) between the system's dimension scores and the per-page median consensus for that dimension. That agreement becomes a single, global fusion weight:

    w_d = ICC_d / Σ_j ICC_j

and the composite score for a page is S = Σ_d w_d · s_d, where s_d is the module's raw score for dimension *d*. This is adapted from established confidence-weighted ensembling and inverse-variance weighting techniques, applied here to fuse detection modules for accessibility scoring rather than to combine raters or classifiers, which is the specific adaptation this project contributes at the static level.

Three implementation details are fixed here so the fit cannot be tuned after seeing held-out results:

- **Stability of ICC_d.** ICC is estimated from a small calibration set (roughly one third of a 40-page benchmark, stratified by bucket), so a single dimension's ICC can be noisy and can even be negative when a module performs worse than chance-level agreement. Raw ICCs are therefore floored at zero, smoothed toward a common prior, and renormalised: w_d = (max(ICC_d, 0) + λ) / Σ_j (max(ICC_j, 0) + λ), with λ = 0.1 as a fixed shrinkage constant. λ prevents any dimension from receiving exactly zero weight (which would discard a module's signal entirely) and prevents a noisy near-1 ICC on a small sample from dominating. If the sum of floored ICCs falls below 0.05 — meaning no module shows meaningful agreement with humans on the calibration set — the fit is declared uninformative and RWMF falls back to naive equal weights, which is reported as such rather than hidden.
- **Missing dimensions.** Pages with no applicable instances of a dimension (e.g., no images) drop that dimension and renormalise over the remaining weights, so pages remain comparable — the same rule the equal-weight baseline uses, applied identically to all variants.
- **Freeze discipline.** λ, the floor, the ICC estimator, and the calibration/validation split ratio are all declared before unblinding held-out scores. Any change is recorded in docs/04 with date and reason.

### 5.4 Adaptive fusion: Adaptive RWMF (A-RWMF)

The static weights above assume every page stresses each detection module equally, which is unlikely to hold in practice: a text-heavy form and an image-dense marketing page do not challenge the vision and NLP modules the same way. A-RWMF conditions each dimension's weight on a page-context profile x_p, a small set of cheaply computed features — the proportion of DOM nodes that are images, average text length per element, DOM depth, and interactive-element count — all of which are already collected during capture at effectively zero marginal cost:

    w_d(x_p) = softmax_d( ICC_d + β_d · x_p )

Here ICC_d is the same global reliability prior computed for RWMF, and β_d is a small set of coefficients fit on the calibration subset through constrained regression, capturing how each dimension's reliability shifts with page type. Two details keep this honest and within scope:

- **Negative and shifting priors.** Because ICC_d is floored at zero in RWMF, the same floor applies inside the softmax argument; otherwise a negative prior would systematically suppress a dimension regardless of the page context. The softmax temperature is fixed at 1.0; a temperature sweep is reported only as a sensitivity analysis, never used to pick the headline result.
- **Bucketed implementation for the semester.** Given the project's timeline, the initial implementation replaces continuous regression with two to three discrete page-type buckets (text-heavy, image-heavy, form-heavy), so β_d · x_p reduces to a lookup of per-bucket weights rather than a fitted regression. Bucket assignment is a deterministic first-match rule over thresholded profile features (image-node ratio, interactive-element ratio, mean text length), with thresholds set on calibration-page quantiles and frozen before unblinding. Per-bucket weights use the same floored, shrunk ICC formula computed within each bucket; any bucket with fewer than five calibration pages falls back to the global RWMF weights and is flagged, so a sparse bucket can never produce an unearned swing in weights. This preserves the core adaptive claim while keeping the implementation within scope for a single semester.

This design is a specific instance of dynamic classifier and ensemble selection, and of mixture-of-experts gating, both established paradigms in the ensemble learning literature (Ko, Sabourin, and Britto [11]); it is not proposed as a new gating mechanism in general. Its contribution is applying context-adaptive gating to multimodal accessibility scoring for the first time, and initialising the gate's prior from a statistically validated reliability signal, ICC, rather than learning it from an uninformed starting point, which most dynamic ensemble selection methods require substantially more labelled data to do.

### 5.5 Validation

A benchmark set of pages, stratified across the page-type buckets used in Section 5.4, is rated independently by human raters per page (three as a floor; the protocol fixes five), blind to any system output. Median aggregation produces the consensus label per dimension. The calibration subset and the held-out validation subset are kept separate: ICC_d and per-bucket weights are fit only on calibration pages (a stratified split of roughly one third of pages, with at least five pages per bucket required before any bucket-specific weight may be used), and the reported ICC2k figures come only from the held-out set, to avoid reporting a score inflated by fitting and testing on the same data. Because ICC estimates from small panels have wide confidence intervals, every point estimate is reported with its 95 percent confidence interval and a page-level bootstrap cross-check.

### 5.6 Comparative benchmarking

Four fusion variants are compared on the same held-out benchmark: naive equal-weight fusion (the current hand-set baseline), static RWMF, A-RWMF, and — as an external floor — a rule-based checker (axe-core) mapped to 0–100 by the frozen formula in docs/02, plus an LLM-based baseline where feasible. Results are reported both pooled across all pages and stratified by page-type bucket, on three measures: ICC(A,1) against consensus (agreement), Spearman ρ and mean absolute error (rank and calibration), and compute cost per page (wall-clock seconds and peak memory on the same machine; the fusion step itself is a four-feature lookup and is expected to cost microseconds, which is measured and reported rather than assumed).

The comparison between variants is pre-registered: static RWMF counts as an improvement over equal weights if its pooled MAE against consensus is lower with a 95 percent paired-bootstrap interval (resampling pages, 10,000 draws) excluding zero, and A-RWMF counts as adding value if it beats static RWMF on pooled MAE without losing pooled ICC, or matches pooled performance while winning in at least two of three buckets — the second criterion being exactly the pattern predicted by the page-dependence hypothesis: A-RWMF matches static RWMF on the pooled average but outperforms it within individual buckets, particularly on image-heavy or form-heavy pages where module reliability is expected to diverge most. Per-bucket tests are labelled exploratory and Holm–Bonferroni corrected. If A-RWMF fails both criteria, that is a reportable negative result — evidence that the page-context adaptation does not earn its complexity — not a failure of the study.

### 5.7 Threats to validity

- **Calibration-set size.** ICC_d is estimated from roughly a dozen pages; the shrinkage toward λ and the equal-weight fallback bound how much damage a noisy fit can do, but weights remain approximate and are reported with their bootstrap spread.
- **Bucket misclassification.** A page assigned to the wrong bucket receives the wrong weight table. Deterministic thresholds minimise discretion; misclassification rates are reported by hand-inspecting bucket assignments on the calibration set.
- **Consensus as a noisy target.** Human median scores carry rater noise and rater-population bias (the panel mixes trained and untrained raters by design). Panel ICC(A,k) is reported first; if the panel itself does not reach acceptable agreement (gate at 0.70, docs/01), system-versus-consensus figures are reported as inconclusive rather than as system failure.
- **Construct validity of the alt-text proxy.** CLIP similarity rewards topical overlap, not usefulness for a blind user; per-image error analysis of the worst system-versus-consensus disagreements is mined from raters' free-text notes.
- **Multiple comparisons.** Pooled results are confirmatory; bucket-level results are exploratory with Holm–Bonferroni correction, and no claim rests on a single uncorrected bucket comparison.
- **Ceiling effects.** Well-built pages cluster near the top of the scale, compressing variance and depressing ICC; the sampling frame deliberately includes a quality spread, and MAE is reported alongside ICC for this reason.

### 5.8 Compute measurement

Every variant shares the same capture, vision, and NLP front-end; only the weight assignment differs. Per-page cost is measured as median wall-clock seconds and peak RSS on one machine, with model load excluded from per-page time but reported once, and an offline verification run with the network disabled after initial model download.

## 6. Novelty

The project's novelty has three parts, ordered from broadest to most specific.

**First, combinatorial:** no reviewed system combines a lightweight, fully offline vision and NLP pipeline for web-page accessibility scoring with validation against a statistically grounded multi-rater consensus. The closest individual precedents each cover one piece of this: Haque's AltIcon is lightweight and fused but scoped to UI icons, not full pages; Baghel et al. deploy lightweight on-device vision-language models but for video description; Kuzikov et al. build the rigorous multi-rater reliability method but apply it to LLM-evaluator consensus, not to validating a system's output.

**Second, static RWMF (Section 5.3):** deriving fusion weights from each module's measured reliability against human judgment, rather than the fixed, hand-set weights used in the closest comparable framework, Sadallah and Encelle's five-dimensional scoring system. This is an adaptation of established confidence-weighted ensembling, not a new statistical technique, and is described as such rather than overclaimed.

**Third, adaptive A-RWMF (Section 5.4), the project's primary novelty claim:** conditioning fusion weights on page content rather than treating reliability as a fixed global constant. No reviewed system, including Kuzikov et al. and Sadallah and Encelle, models detection or rater reliability as a function of the item being judged; both treat it as a single fixed value once estimated. This is a specific, falsifiable claim, tested directly by the stratified benchmarking in Section 5.6: if A-RWMF fails to outperform static RWMF within individual page-type buckets, that is itself a reportable negative result, not a failure of the study.

Given the implementation timeline, static RWMF is the version the project commits to fully building and validating this semester. A-RWMF is proposed and specified in full here, with a scoped-down bucketed implementation attempted if time allows after static RWMF is validated; if not, it is reported as the project's primary direction for future work, built on a working, validated static baseline rather than left unsupported.

## 7. Implementation progress

The project is past the proposal stage: the offline scoring front-end is built and tested, while the reliability-weighted fusion layer specified in Sections 5.3–5.4 is not yet implemented. Concretely, the repository now contains a Python package (`arwmf`) with: the Playwright capture stage (screenshots plus per-element geometry, computed-style extraction, DOM structure and page-profile features); the three deterministic vision dimensions (contrast, target size, layout/clutter); the two NLP dimensions (CLIP-based alt-text similarity with deterministic penalties, link-text lexicon plus context embedding); a weighted five-dimension fusion stage with missing-dimension renormalisation; the statistics module (ICC(A,1) and ICC(A,k) with F-based and bootstrap confidence intervals, median consensus aggregation), validated against a published reference implementation's worked example; the axe-core baseline with the frozen 0–100 mapping; a CLI, a batch benchmark runner, and a correlation/compute report script. The suite currently stands at 40 passing tests, including an end-to-end run over accessibility fixtures that cleanly separates a well-built page (composite 94.1) from a deliberately inaccessible one (38.6).

Not yet built: the RWMF weight-fitting stage (objective 3), the bucketed A-RWMF stage (objective 4), any human benchmark data (objective 5), and the four-variant comparative benchmark (objective 6). This section will be updated at each review with what has actually been built, tested, or dropped.

## 8. Demonstration (demo)

A working demo exists: the CLI captures a page, emits per-dimension and composite scores, and computes ICC statistics over a ratings CSV; the axe-core baseline runs on the same pages for comparison. A demo of static RWMF (weight fit on a calibration split, weighted composites on held-out pages) follows once the human panel supplies calibration ratings. A demo of the bucketed A-RWMF variant will follow only if it is reached within the semester timeline.

## 9. Completion of the proposed implementation

Approximately 45 percent implemented as of this document: the full offline front-end (capture, vision, NLP, base fusion, statistics, baselines, CLI, batch tooling) exists with 40 passing tests, and no human benchmark data has been collected. The plan is to build and unit-test the RWMF fitting stage by the next review, run an initial calibration fit once early ratings arrive, then full multi-rater validation and stratified comparative benchmarking by the final review. The bucketed A-RWMF variant is attempted after static RWMF is validated, time permitting, and is otherwise reported as future work.

## 10. Identification of potential best projects by the review panel

This section is completed by the faculty review panel rather than by the student, and is left blank here for the panel's remarks and scoring at each review stage.

## References

[1] M. Gu, Z. Wang, S. Lai, Z. Gao, S. Zhou, and J. Bu, "Towards Scalable Web Accessibility Audit with MLLMs as Copilots," arXiv preprint, 2025.

[2] C. Fernández-Navarro and F. Chicano, "Automated LLM-Based Accessibility Remediation: From Conventional Websites to Angular Single-Page Applications," arXiv preprint, 2026.

[3] A. van de Hoef, K. Smit, S. Leewis, D. Castro, F. Hartman, J. Todorova, and N. Kuiper, "Evaluating the Feasibility of LLM-Based Automation of Manual WCAG Compliance Testing," Research in Progress, HU University of Applied Sciences Utrecht, 2025/2026.

[4] C. Huang, A. Ma, S. Vyasamudri, E. Puype, S. Kamal, J. Belza Garcia, S. Cheema, and M. Lutz, "ACCESS: Prompt Engineering for Automated Web Accessibility Violation Corrections," arXiv preprint, 2025.

[5] S. Haque, "Early Accessibility: Automating Alt-Text Generation for UI Icons During App Development," M.S. thesis, University of Texas at Arlington, 2025.

[6] M. Mähr and University of Twente, "Seeing History Unseen: Evaluating Vision-Language Models for WCAG-Compliant Alt-Text in Digital Heritage Collections," 2025/2026.

[7] S. S. Baghel, Y. P. S. Rathore, S. Jena, A. Pradhan, A. Shukla, P. Bhavsar, and P. Goyal, "Towards Blind and Low-Vision Accessibility of Lightweight VLMs and Custom LLM-Evals," IIT Mandi, 2025.

[8] A. Kumar, T. Padath, and L. L. Wang, "Benchmarking PDF Accessibility Evaluation: A Dataset and Framework for Assessing Automated and LLM-Based Approaches for Accessibility Testing," in Proc. ACM SIGACCESS Conf. Computers and Accessibility (ASSETS '25), 2025.

[9] B. O. Kuzikov, O. A. Shovkoplias, P. O. Tytov, S. R. Shovkoplias, O. V. Shutylieva, and O. V. Vlasenko, "A Statistical Framework for Consensus-Based Reliability Assessment in Large Language Model Evaluation Applied to Web Accessibility," Sumy State University, 2025.

[10] M. Sadallah and B. Encelle, "Beyond Additive Design: An Empirical Taxonomy of Multimodal STEM Accessibility Systems," in Proc. CHI Conference on Human Factors in Computing Systems Extended Abstracts (CHI EA '26), 2026.

[11] A. H. Ko, R. Sabourin, and A. S. Britto Jr., "From Dynamic Classifier Selection to Dynamic Ensemble Selection," Pattern Recognition, vol. 41, no. 8, pp. 1761–1774, 2008 — cited for the dynamic ensemble selection lineage underlying A-RWMF's gating mechanism.

> **Note to student:** references [1], [2], [4], [6], and [9] still need exact venue/DOI verification before final submission — "arXiv preprint" is a placeholder where the exact venue was not recorded in the survey.

**Companion documents:** `docs/01-rater-study-protocol.md` (rater design, power rationale, decision rules) · `docs/02-accessibility-scoring-specification.md` (frozen per-dimension formulas and axe mapping) · `docs/05-rwmf-arwmf-fusion-methodology.md` (full fitting procedure and pseudocode for Sections 5.3–5.4) · `docs/04-protocol-deviation-log.md` (where any post-freeze change must be recorded).
