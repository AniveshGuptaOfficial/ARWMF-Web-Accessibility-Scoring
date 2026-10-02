"""Batch capture + score + axe over the pages manifest (human_study/pages-manifest.csv).

    python scripts/run_benchmark_captures.py --manifest human_study/pages-manifest.csv \
        --out human_study/run1 [--no-clip] [--no-embeddings] [--skip-axe]

Emits per page: <out>/<page_id>/capture.{json,png}, score.json, axe.json
and a summary scores_system.csv / scores_axe.csv at <out>/.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arwmf.capture import capture_page  # noqa: E402
from arwmf.pipeline import score_capture  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--viewport", default="desktop", choices=["desktop", "mobile"])
    ap.add_argument("--no-clip", action="store_true")
    ap.add_argument("--no-embeddings", action="store_true")
    ap.add_argument("--skip-axe", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = list(csv.DictReader(Path(args.manifest).open(encoding="utf-8")))
    if not manifest:
        raise SystemExit("empty manifest")

    system_rows, axe_rows, failures = [], [], []
    t_all = time.perf_counter()

    for row in manifest:
        page_id, url = row["page_id"], row["url"]
        pdir = out / page_id
        print(f"[{page_id}] {url}")
        try:
            cap = capture_page(url, pdir, viewport=args.viewport)
            score = score_capture(cap, use_clip=not args.no_clip,
                                  use_embeddings=not args.no_embeddings)
            (pdir / "score.json").write_text(json.dumps(score, indent=2),
                                             encoding="utf-8")
            system_rows.append({"page_id": page_id, "composite": score["composite"],
                                "seconds": score["seconds"],
                                **{f"dim_{k}": v for k, v in score["dimensions"].items()}})
        except Exception as exc:
            failures.append((page_id, repr(exc)))
            traceback.print_exc()
            continue

        if not args.skip_axe:
            try:
                from arwmf.baselines import run_axe_and_score

                axe = run_axe_and_score(url)
                (pdir / "axe.json").write_text(json.dumps(axe, indent=2),
                                               encoding="utf-8")
                axe_rows.append({"page_id": page_id, "axe_score": axe["axe_score"],
                                 "n_violations": axe["n_violations"]})
            except Exception as exc:
                failures.append((page_id, f"axe: {exc!r}"))
                traceback.print_exc()

    def write_csv(path: Path, rows: list[dict]) -> None:
        if not rows:
            return
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    write_csv(out / "scores_system.csv", system_rows)
    write_csv(out / "scores_axe.csv", axe_rows)

    total = time.perf_counter() - t_all
    print(f"\ndone: {len(system_rows)} scored, {len(axe_rows)} axe, "
          f"{len(failures)} failed, {total:.1f}s total")
    for pid, err in failures:
        print(f"  FAIL {pid}: {err}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
