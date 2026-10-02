# Calibration anchors — rating walkthrough (30 min, all raters)

Use the 3 calibration pages (`human_study/calibration_pages/`, NOT in the 40-page
benchmark). For each page: rate independently first (5 min), then compare in
group discussion (5 min per page).

## Slider mechanics
- 0–100 slider, integers. Use the full range; avoid clustering at 50.
- Anchor questions while rating:
  - Contrast: "Could I read every sentence on the first try?"
  - Target size: "Could I tap every control with a thumb, eyes closed to the layout?"
  - Layout: "Can I predict where the next section starts?"
  - Alt-text: "If I heard only the alt text, would I know what the image shows?"
  - Link text: "Out of context, would I know where each link goes?"
  - Overall: "Would I be comfortable using this page with a screen reader and a keyboard?"

## Worked examples (from prior audits — use for anchor alignment)

| Case | Dimension | Typical rating | Why |
|---|---|---|---|
| #aaa body text on white | contrast | 20–40 | ~2.3:1, fails 4.5:1 badly; readable but effortful |
| #777 small text on white | contrast | 70–85 | ~4.48:1, borderline; usable but marginal |
| 14×14 icon buttons, no labels | target size | 10–30 | fails 24×24 minimum badly |
| Inline text links in a paragraph | target size | 60–100 | WCAG exempts inline links; judge severity honestly |
| "click here" ×5, no landmarks | link text / layout | 0–25 | zero out-of-context information |
| Nav "Products", "Pricing", "Contact" | link text | 80–100 | self-explanatory labels |
| Hero image, filename alt `IMG_4471.jpg` | alt text | 0–10 | screen reader says the filename |
| Decorative icon marked alt="" + role=presentation | alt text | n/a | skip — do not penalise correct decorative handling |

## Reminders
- Rate **the capture in front of you**, not the site's reputation.
- You will not see automated scores; do not ask for them.
- Three pages will reappear later (intra-rater check) — rate them as new pages.
- Break after page 20. Stop if fatigued and report total session time.
