"""CLI: capture, score, axe baseline, ICC analysis.

    python -m arwmf capture <url> --out page_captures/<id> [--viewport desktop|mobile]
    python -m arwmf score page_captures/<id> [--no-clip] [--no-embeddings] [-o scores.json]
    python -m arwmf axe <url>
    python -m arwmf icc human_study/ratings.csv [--dimension overall] [--bootstrap]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_capture(args) -> int:
    from .capture import capture_page

    cap = capture_page(args.url, Path(args.out), viewport=args.viewport)
    print(f"captured {args.url} -> {cap.png_path}")
    print(f"elements: {len(cap.elements.get('text_elements', []))} text, "
          f"{len(cap.elements.get('interactive', []))} interactive, "
          f"{len(cap.elements.get('images', []))} images, "
          f"{len(cap.elements.get('links', []))} links")
    return 0


def cmd_score(args) -> int:
    from .pipeline import score_from_dir

    result = score_from_dir(
        Path(args.capture),
        use_clip=not args.no_clip,
        use_embeddings=not args.no_embeddings,
    )
    text = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    print(text)
    return 0


def cmd_axe(args) -> int:
    from .baselines import run_axe_and_score

    result = run_axe_and_score(args.url)
    print(json.dumps(result, indent=2))
    return 0


def cmd_icc(args) -> int:
    import pandas as pd

    from .stats import icc_a1, icc_ak, median_consensus, ratings_to_matrix

    df = pd.read_csv(args.csv)
    matrix, pages, raters = ratings_to_matrix(df, args.dimension)
    a1 = icc_a1(matrix)
    ak = icc_ak(matrix)
    print(f"dimension: {args.dimension}  ({len(pages)} pages x {len(raters)} raters)")
    print(f"  {a1}")
    print(f"  {ak}")
    if args.bootstrap:
        from .stats import bootstrap_icc_ci

        lo, hi = bootstrap_icc_ci(matrix, m=1, n_boot=args.bootstrap, seed=0)
        print(f"  bootstrap ICC(A,1) 95% CI: [{lo:.3f}, {hi:.3f}]")
    if args.consensus:
        cons = median_consensus(df)
        cons.to_csv(args.consensus)
        print(f"wrote consensus -> {args.consensus}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="arwmf",
                                description="A-RWMF: offline multimodal web accessibility scoring")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("capture", help="screenshot + element extraction")
    c.add_argument("url")
    c.add_argument("--out", required=True)
    c.add_argument("--viewport", choices=["desktop", "mobile"], default="desktop")
    c.set_defaults(func=cmd_capture)

    s = sub.add_parser("score", help="score a capture directory")
    s.add_argument("capture")
    s.add_argument("-o", "--output")
    s.add_argument("--no-clip", action="store_true",
                   help="skip CLIP (deterministic alt-text rules only)")
    s.add_argument("--no-embeddings", action="store_true",
                   help="skip sentence embeddings for link text")
    s.set_defaults(func=cmd_score)

    a = sub.add_parser("axe", help="run axe-core baseline on a URL")
    a.add_argument("url")
    a.set_defaults(func=cmd_axe)

    i = sub.add_parser("icc", help="ICC analysis on a ratings CSV")
    i.add_argument("csv")
    i.add_argument("--dimension", default="overall",
                   choices=["contrast", "target_size", "layout", "alt_text",
                            "link_text", "overall"])
    i.add_argument("--bootstrap", type=int, default=0,
                   help="number of bootstrap resamples (0 = off)")
    i.add_argument("--consensus", help="write median consensus CSV here")
    i.set_defaults(func=cmd_icc)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
