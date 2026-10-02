# Scoring Specification (v1.0 — fixed before benchmark unblinding)

All dimension scores are 0–100. The composite is a weighted mean over applicable dimensions.

## Weights (a priori, sensitivity-analysed later)

| Dimension | Weight |
|---|---|
| Contrast | 0.25 |
| Target size | 0.15 |
| Layout | 0.20 |
| Alt-text | 0.25 |
| Link text | 0.15 |

If a dimension has no applicable instances on a page (no images → no alt-text instances), its weight is dropped and remaining weights renormalised to sum to 1. Pages with zero applicable instances of *all* dimensions are excluded from the benchmark.

## D1 — Contrast (WCAG 1.4.3 / 1.4.11)

For each visible text element *e* with resolved foreground colour and effective background (ancestor-resolved):

- Required ratio: **4.5:1** normal text; **3:1** large text (≥ 24 px, or ≥ 18.66 px bold) and non-text UI components (WCAG 1.4.11) against their adjacent background.
- Element score: `clip(ratio / required, 0, 1) × 100` — partial credit for approaching but not meeting the threshold.
- Dimension score: mean over elements, weighted by `sqrt(area)` so large hero/headline text dominates the judgment, consistent with how raters experience a page. (Implementation note: weight = sqrt(width × height) of the text node's bounding box, clipped to [1, max_w × max_h].)

## D2 — Target size (WCAG 2.5.8, minimum conformance level)

For each interactive element (link, button, form control, `role=button`/`link`, `[tabindex]` ≥ 0):

- Element score: `min(w/24, 1) × min(h/24, 1) × 100`.
- Inline links inside a paragraph of text are exempt per WCAG 2.5.8 exception (inline) and excluded from the denominator.
- Dimension score: mean over applicable elements.

## D3 — Layout

Two sub-scores, equally weighted:

- **Structure (DOM):** starts at 100; penalties: no `<h1>` (−20), multiple `<h1>` (−10 each beyond the first, cap −30), skipped heading levels (−15), missing `main` landmark (−15), missing `nav` when nav links exist (−15), no skip-link with > 20 nav links (−10), clipped at 0.
- **Clutter (vision):** Canny edge-density `d` over the full-page screenshot. Score = `clip((d_max − d) / (d_max − d_min), 0, 1) × 100` with `d_min = 0.02`, `d_max = 0.20` (calibrated on the 10-page pilot; constants frozen before unblinding — changes require a logged deviation).
- Dimension score = 0.5 × structure + 0.5 × clutter.

## D4 — Alt-text adequacy (CLIP image–text similarity)

Applicable instances: images with rendered area ≥ 900 px² (i.e., content images; tiny tracking pixels excluded).

Per instance:

1. Missing `alt` attribute → **0**.
2. `alt=""` with `role="presentation"`/`aria-hidden` → decorative, excluded from denominator.
3. Filename-like alt (`/\\.(jpe?g|png|gif|svg)$/i` or matching the `src` basename) → **0**.
4. Otherwise: crop the element's region from the archived PNG, embed crop + alt with CLIP (ViT-B/32, local), cosine similarity `c`. CLIP cosine for genuinely matching image–caption pairs centres ≈ 0.25–0.35; map with a logistic: `raw = 100 × σ((c − 0.24) / 0.04)` where σ is the logistic function. Constants to be re-fitted **on the calibration pages only** if pilot residuals show systematic bias; any change is logged before unblinding.
5. Generic-label penalty: alt consisting only of interface words (`image, picture, photo, icon, logo, graphic, screenshot`) with ≤ 3 tokens → multiply by 0.5.

Dimension score = mean over applicable instances. **Warning flagged in the spec:** CLIP similarity is an imperfect proxy for human alt-text judgments (it rewards topical overlap, not usefulness for a blind user). Expected ICC contribution is the main empirical risk of the project; per-image human ratings in the study would detect this, and the free-text notes are mined for qualitative failure modes.

## D5 — Link-text adequacy

Applicable instances: links with non-empty rendered text.

1. Vague-label lexicon hit (`click here, here, more, read more, link, more info, learn more, this, this link, details, continue, read more`, exact or ≤ 1 extra token) → **0**.
2. Pure-URL or image-only-without-alt link text → **0**.
3. Otherwise: MiniLM-L6 sentence embedding of link text vs. its enclosing block's text (minus the link itself); cosine `c` mapped by `clip((c − c₀)/(0.55 − c₀), 0, 1) × 100` with `c₀ = 0.05`. Multiply by 0.6 if the label is a single generic verb from the lexicon used non-exactly (partial penalty).
4. Single-token labels that are meaningful nouns (contain a content word not in lexicon) score by rule 3 alone.

Dimension score = mean over applicable instances.

## Composite

```
composite = Σ (w_i × d_i) / Σ w_i   over applicable dimensions i,  d_i ∈ [0,100]
```

Reported to 1 decimal. Composite is the quantity correlated against human median consensus.

## Baseline mapping — axe-core → 0–100

axe-core emits violations with `impact ∈ {minor, moderate, serious, critical}`. Mapping (fixed):

```
penalty = Σ_violations  count(v) × weight(impact(v)),  weight = {minor:1, moderate:2, serious:3, critical:4}
axe_score = 100 × max(0, 1 − penalty / (4 × N_elements))
```

`N_elements` = count of elements in the accessibility-relevant set (same set the vision pipeline scores, i.e., text + interactive elements, min 50 to avoid denominator instability). Rationale: normalises for page size so a violation-dense small page and a large page are comparable; frozen before unblinding.

## Compute measurement

- Per page: wall-clock seconds (median over benchmark), peak RSS MB (tracemalloc + RSS), model load excluded but reported once.
- Offline check: run with network disabled after model download.
