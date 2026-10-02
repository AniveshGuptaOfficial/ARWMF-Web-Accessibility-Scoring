# Multi-Rater Human Consensus Protocol — Web Accessibility Scoring Benchmark

Companion protocol to *A Lightweight Offline Multimodal Framework for Web Accessibility Scoring, Validated Against Multi-Rater Human Consensus*. This document fixes the study design **before** data collection so that the analysis plan cannot be tuned after seeing results.

## 1. Research questions

- **RQ1:** Does the fused automated score agree with multi-rater human consensus? (Primary: ICC(A,1) between system and consensus, plus ICC(A,1) of system entered as an additional rater in the full panel.)
- **RQ2:** How reliable is the human consensus itself? (ICC(A,k) of the rater panel — reported so RQ1 is interpretable; a system cannot out-agree a consensus that raters do not agree on.)
- **RQ3:** What is the compute-versus-correlation trade-off against axe-core and an LLM baseline? (Correlation with consensus × wall-clock seconds and peak MB per page.)

## 2. Sampling

### 2.1 Pages

- **N = 40 pages**, stratified across four categories (10 each): e-commerce, news/media, government/education, documentation/blogs.
- Selection: from the Tranco top-sites list filtered to categories, plus curated accessibility-relevant pages (deliberately include a spread from well-known accessible sites to known-poor ones — variance in the score range is required for ICC to be informative; a benchmark of only WCAG-compliant pages would compress variance and deflate ICC).
- Inclusion criteria: static content reachable without login; renders in Chromium; content images present on at least 30 pages (2–6 content images per page typical).
- Each page captured at one fixed desktop viewport (1280×800) for the primary benchmark; mobile (390×844) is a secondary analysis, doubling captures but not ratings.
- Pages are archived as HTML + PNG at capture time so ratings and automated scores refer to identical content even if live pages change.

### 2.2 Raters

- **5 raters per page, each page rated by all 5** (complete design — required for two-way ICC; ≥4 minimum, 5 chosen so ICC(A,k) CIs are usable).
- Panel composition: 3 raters with formal WCAG training (coursework or audit experience) + 2 raters drawn from a general technically-literate population without audit training. This mix is deliberate: the intended deployment context includes non-specialist auditors, and ICC over a mixed panel (treated as a random sample of the target user population) matches that use case. Subgroup agreement is reported as a secondary analysis.
- Screening: 10-minute WCAG-terminology screener (8 items, pass ≥ 6); all raters complete training below.
- Exclusion: screener failure, or intra-rater reliability check failure (3 duplicate pages embedded blind; excluded if any duplicate pair differs by > 15 points on the overall score).

### 2.3 Calibration / training

- All raters complete a 30-minute training session rating 3 calibration pages (not in the benchmark) with anchored rubric examples, followed by group discussion to align interpretation of anchors.
- After training, the 3 calibration pages are re-rated independently; Kendall's W across raters ≥ 0.6 required to proceed, otherwise one refresher round.

## 3. Rating instrument

Raters score the **archived screenshot + DOM snapshot** of each page (not the live page) on six 0–100 sliders with verbal anchors at 0 / 25 / 50 / 75 / 100 — the same five dimensions the system scores, plus one overall judgment:

| Dimension | 0 anchor | 50 anchor | 100 anchor |
|---|---|---|---|
| Contrast | Text largely unreadable | Readable with effort | Comfortable everywhere |
| Target size | Almost no tappable/hoverable target usable | Some targets awkward | All targets comfortably sized |
| Layout | Chaotic, no discernible structure | Usable but untidy | Clear, predictable hierarchy |
| Alt-text | Missing/meaningless on content images | Partially descriptive | Consistently meaningful |
| Link text | "Click here" everywhere | Mixed quality | Every link self-explanatory |
| **Overall** | Unusable | Frustrating but usable | Fully accessible |

- Instruction to raters: rate **what you see in this capture**, not inferred code quality or site reputation. Raters are blind to automated scores and to each other's ratings.
- Presentation order randomised per rater; each rating session ≤ 45 minutes with a break after 20 pages (fatigue control).
- Free-text note field per page (used for qualitative error analysis of worst system-vs-consensus disagreements).

## 4. Data schema

`human_study/ratings.csv` — one row per rater × page:

```
page_id, rater_id, contrast, target_size, layout, alt_text, link_text, overall, seconds, timestamp
```

- All scores 0–100, integer. Missing cells forbidden (interface enforces complete ratings; abort > 3 missing ratings triggers replacement rater for the affected pages only, re-rated in full).

`human_study/pages-manifest.csv` — manifest:

```
page_id, url, category, viewport, archived_html_path, archived_png_path, capture_date
```

## 5. Analysis plan (fixed in advance)

### 5.1 Consensus

Per Kuzikov et al.: consensus per dimension = **median across the 5 raters**; consensus overall = median of overall ratings (not the median of dimension medians — both are reported, the former is primary).

### 5.2 Reliability statistics

All ICCs: two-way random-effects, absolute agreement (McGraw & Wong ICC(A,·); "ICC2k" notation of Kuzikov et al. refers to ICC(A,k)).

1. **Panel reliability:** ICC(A,5) with 95% CI over the 6-dimension rater matrix.
2. **System-to-human:** system composite score entered as a 6th rater → ICC(A,1) of system vs. the other five, and separately Spearman ρ and MAE against the median consensus as secondary, distribution-free checks.
3. **Per-dimension ICCs** reported alongside the aggregate (exploratory; no multiple-comparison claims made).
4. Confidence intervals via the standard F-based method for point estimates, cross-checked with a 10,000-resample page-level bootstrap (pages are the resampling unit).

**Decision rules (pre-registered):**

- RQ1 positive if ICC(A,1) system-vs-consensus ≥ 0.50 **and** its 95% CI lower bound > 0.25 (conventional "moderate" floor), and ≥ the axe-core baseline ICC.
- Benchmark deemed inconclusive for RQ1 if panel ICC(A,5) < 0.70 (humans did not agree enough for the consensus to be a meaningful target) — result reported as inconclusive, not as system failure.
- RQ3 reported descriptively; no hypothesis test.

### 5.3 Compute measurement

Same machine, cold and warm runs reported separately: wall-clock seconds per page (median over benchmark), peak RSS in MB, model load time excluded from per-page time but reported once. Offline verification: all runs with network disabled after initial model download (verified by running capture/scoring with the interface disconnected).

## 6. Power / precision rationale

ICC point estimates stabilise around 30–50 targets for medium-effect values; with 40 pages × 5 raters the expected 95% CI half-width for ICC(A,1) ≈ 0.10–0.15 at true ICC ≈ 0.6 (F-based approximation), which is sufficient to separate "moderate" from "good" agreement and to compare system vs. axe-core (paired bootstrap on per-page absolute errors, N = 40, power ≈ 0.80 for d ≈ 0.45). If the pilot (first 10 pages) yields ICC(A,5) < 0.70, the fallback is to add up to 10 further pages and one additional rater on all pages before unblinding automated scores; this is the single permitted design change and it is recorded in the deviation log.

## 7. Ethics and consent

- Raters are volunteers recruited from the institution; written informed consent covering purpose, data use, right to withdraw without penalty, and anonymised publication of aggregated ratings.
- No personal data of raters beyond an anonymous rater ID is stored; the key mapping IDs to volunteers is kept separately and destroyed after grading.
- Pages are public web content; no login-walled or personal-content pages included.

## 8. Timeline

| Milestone | Content |
|---|---|
| Week 1 | Pilot 10 pages, calibration session, screener |
| Week 2 | Full rating of 40 pages × 5 raters |
| Week 3 | Automated scores unblinded, ICC analysis, baseline runs |
| Week 4 | Error analysis of worst disagreements, write-up |

Deviation log: any departure from sections 2–5 is appended here with date and reason before analysis.
