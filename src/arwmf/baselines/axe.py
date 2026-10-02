"""axe-core baseline: run in the captured page and map violations to 0-100.

Mapping (frozen, docs/02-accessibility-scoring-specification.md):
    penalty = Σ count(v) * weight(impact(v)),  weight = minor:1 moderate:2 serious:3 critical:4
    axe_score = 100 * max(0, 1 - penalty / (4 * max(N_elements, 50)))
"""
from __future__ import annotations

import json
from pathlib import Path

IMPACT_WEIGHT = {"minor": 1, "moderate": 2, "serious": 3, "critical": 4}
MIN_DENOM_ELEMENTS = 50

_AXE_PATH = Path(__file__).resolve().parents[3] / "node_modules" / "axe-core" / "axe.min.js"


def axe_score(violations: list[dict], n_elements: int) -> float:
    """Map axe violations to 0-100 using the frozen formula.

    violations: [{id, impact, nodes}] as returned by axe.run (or our runner).
    """
    penalty = 0.0
    for v in violations:
        impact = (v.get("impact") or "minor").lower()
        weight = IMPACT_WEIGHT.get(impact, 1)
        count = v.get("nodes_count", len(v.get("nodes", []) or []))
        penalty += count * weight
    denom = 4.0 * max(int(n_elements), MIN_DENOM_ELEMENTS)
    return 100.0 * max(0.0, 1.0 - penalty / denom)


def run_axe(url: str, timeout_ms: int = 60000) -> tuple[list[dict], int]:
    """Load url in Chromium, inject axe-core from node_modules, run it.

    Returns (violations, n_elements). Requires: playwright installed (bundled
    Chromium or a system channel via A11Y_BROWSER_CHANNEL / channel arg), and
    `npm install axe-core` done in the repo root.
    """
    import os

    from playwright.sync_api import sync_playwright

    channel = os.environ.get("A11Y_BROWSER_CHANNEL") or None
    if not _AXE_PATH.exists():
        raise FileNotFoundError(
            f"axe-core not found at {_AXE_PATH}; run `npm install axe-core`"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel=channel)
        try:
            page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                pass
            # inject axe via Runtime.evaluate: <script> injection is blocked by
            # strict page CSP (gov.uk, MDN, ...), evaluate bypasses it
            page.evaluate(_AXE_PATH.read_text(encoding="utf-8"))
            result = page.evaluate(
                """async () => {
                    const res = await axe.run(document, { resultTypes: ['violations'] });
                    return {
                        violations: res.violations.map(v => ({
                            id: v.id, impact: v.impact,
                            nodes_count: v.nodes.length,
                        })),
                        n_elements: document.querySelectorAll('body *').length,
                    };
                }"""
            )
        finally:
            browser.close()
    return result["violations"], int(result["n_elements"])


def run_axe_and_score(url: str) -> dict:
    violations, n = run_axe(url)
    return {
        "url": url,
        "axe_score": round(axe_score(violations, n), 1),
        "n_violations": len(violations),
        "n_elements": n,
        "violations": violations,
    }
