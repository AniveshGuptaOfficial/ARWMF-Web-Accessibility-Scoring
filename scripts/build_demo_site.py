"""Build the static Vercel demo site from recorded benchmark results.

Reads page_captures/run1/<id>/{score.json, axe.json, capture.png} plus the page
manifest, compresses each screenshot to JPEG, and emits:

    site/data/demo-results.json     — recorded REAL results for the demo front-end
    site/assets/<id>.jpg            — full-page screenshots ("full screenshot" link)

The hosted demo (site/app.js) replays these recorded results client-side with
animated phases; live scoring always runs locally via `python webapp/server.py`.

Usage:
    python scripts/build_demo_site.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "page_captures" / "run1"
SITE = ROOT / "site"
ASSETS = SITE / "assets"
DATA = SITE / "data"
QUALITY = 78

# friendly chip labels for the demo UI (fallback: manifest url host)
LABELS = {
    "p01": "vtrade",
    "p02": "example.com",
    "p03": "Wikipedia",
    "p04": "gov.uk",
    "p05": "BBC",
    "p06": "Apple",
    "p07": "MDN",
    "p08": "Hacker News",
}


def main() -> int:
    manifest_path = ROOT / "human_study" / "pages-manifest.csv"
    manifest = {r["page_id"]: r for r in csv.DictReader(manifest_path.open(encoding="utf-8"))}
    ASSETS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    pages, missing = [], []
    for pid, row in sorted(manifest.items()):
        pdir = RUN / pid
        score_p, axe_p, png_p = pdir / "score.json", pdir / "axe.json", pdir / "capture.png"
        if not (score_p.exists() and axe_p.exists() and png_p.exists()):
            missing.append(pid)
            continue
        score = json.loads(score_p.read_text(encoding="utf-8"))
        axe = json.loads(axe_p.read_text(encoding="utf-8"))

        jpg = ASSETS / f"{pid}.jpg"
        with Image.open(png_p) as im:
            im.convert("RGB").save(jpg, "JPEG", quality=QUALITY, optimize=True)

        pages.append({
            "id": pid,
            "label": LABELS.get(pid, row["url"]),
            "url": row["url"],
            "category": row.get("category", ""),
            "score": score,
            "axe": axe,
            "screenshot": f"assets/{pid}.jpg",
        })
        print(f"  {pid}  {LABELS.get(pid, row['url']):<14} composite={score['composite']:>5}  "
              f"axe={axe['axe_score']:>5}  violations={axe['n_violations']}  "
              f"jpg={jpg.stat().st_size / 1024:.0f} KB")

    out = {
        "source": "A-RWMF benchmark run1 — 8 pages, desktop viewport, recorded 2026-09",
        "note": ("Pre-recorded REAL results produced by the A-RWMF pipeline "
                 "(Playwright capture -> five dimensions -> weighted fusion -> axe-core). "
                 "This static demo replays them client-side. Live scoring runs locally: "
                 "python webapp/server.py"),
        "pages": pages,
    }
    (DATA / "demo-results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    total_mb = sum(f.stat().st_size for f in ASSETS.glob("*.jpg")) / (1024 * 1024)
    print(f"\nwrote {len(pages)} pages -> site/data/demo-results.json "
          f"(assets: {total_mb:.1f} MB JPEG)")
    if missing:
        print(f"skipped (missing recorded files): {missing}")
    return 0 if pages else 1


if __name__ == "__main__":
    sys.exit(main())
