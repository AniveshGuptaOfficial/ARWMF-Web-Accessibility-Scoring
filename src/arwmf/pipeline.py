"""End-to-end scoring: Capture -> five dimensions -> fused composite.

Each stage's outputs are recorded in the result dict so scoring runs are
auditable (per-dimension values, instance counts, and applied weights).
"""
from __future__ import annotations

import time
from pathlib import Path

from .capture import Capture
from .fusion import fuse
from .vision import dimension_contrast, dimension_layout, dimension_target_size


def _load_png(capture: Capture):
    import cv2

    if not capture.png_path or not Path(capture.png_path).exists():
        raise FileNotFoundError(f"screenshot missing: {capture.png_path}")
    img = cv2.imread(capture.png_path)
    if img is None:
        raise ValueError(f"unreadable screenshot: {capture.png_path}")
    return img


def _make_crop_fn(png_path: str):
    """crop_fn(rect) -> PIL image of the element region (for CLIP)."""
    import cv2
    from PIL import Image

    img = cv2.imread(png_path)
    if img is None:
        raise ValueError(f"unreadable screenshot: {png_path}")
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]

    def crop(rect: dict):
        x = max(0, int(rect.get("x", 0)))
        y = max(0, int(rect.get("y", 0)))
        x2 = min(w, int(rect.get("x", 0) + rect.get("w", 0)))
        y2 = min(h, int(rect.get("y", 0) + rect.get("h", 0)))
        if x2 <= x or y2 <= y:
            raise ValueError("empty crop region")
        return Image.fromarray(rgb[y:y2, x:x2])

    return crop


def score_capture(capture: Capture, *, use_clip: bool = True,
                  use_embeddings: bool = True, weights=None) -> dict:
    """Compute all dimension scores + composite for one capture.

    use_clip / use_embeddings allow cheap dry-runs (vision + heuristics only);
    NLP dimensions then still score via deterministic rules with the
    embedding-dependent parts degraded (recorded under 'degraded').
    """
    t0 = time.perf_counter()
    el = capture.elements
    degraded: list[str] = []

    # D1 contrast
    contrast = dimension_contrast(el.get("text_elements", []))
    # D2 target size
    target = dimension_target_size(el.get("interactive", []))
    # D3 layout (needs the screenshot)
    layout = dimension_layout(el.get("structure", {}), _load_png(capture))

    # D4 alt-text
    alt = None
    n_images_applicable = 0
    images = el.get("images", [])
    if images:
        from .nlp.alt_text import classify_alt

        applicable = [i for i in images if classify_alt(i) != "decorative"]
        n_images_applicable = len(applicable)
        if applicable:
            if use_clip:
                from .nlp.alt_text import ClipScorer, dimension_alt_text

                crop_fn = _make_crop_fn(capture.png_path)
                alt = dimension_alt_text(images, ClipScorer(), crop_fn)
            else:
                degraded.append("clip")
                # deterministic part only: missing/filename = 0, else neutral 40
                from .nlp.alt_text import classify_alt as _classify

                scores = [0.0 if _classify(i) in ("missing", "filename") else 40.0
                          for i in applicable]
                alt = sum(scores) / len(scores)

    # D5 link text
    link = None
    links = [l for l in el.get("links", []) if (l.get("text") or "").strip()]
    if links:
        from .nlp.link_text import dimension_link_text

        embedder = None
        if use_embeddings:
            try:
                from .nlp.link_text import ContextEmbedder

                embedder = ContextEmbedder()
            except Exception:
                degraded.append("embeddings")
        else:
            degraded.append("embeddings")
        link = dimension_link_text(links, embedder)

    dimension_scores = {
        "contrast": contrast,
        "target_size": target,
        "layout": layout,
        "alt_text": alt,
        "link_text": link,
    }
    fused = fuse(dimension_scores, weights)

    elapsed = time.perf_counter() - t0
    return {
        "url": capture.url,
        "viewport": capture.viewport_name,
        "composite": round(fused.composite, 1),
        "dimensions": {k: (None if v is None else round(v, 1))
                       for k, v in fused.dimensions.items()},
        "applied_weights": {k: round(v, 4) for k, v in fused.applied_weights.items()},
        "counts": {
            "text_elements": len(el.get("text_elements", [])),
            "interactive": len(el.get("interactive", [])),
            "images_applicable": n_images_applicable,
            "links": len(links),
            "n_elements": el.get("n_elements"),
        },
        "degraded": degraded,
        "seconds": round(elapsed, 3),
    }


def score_from_dir(capture_dir: Path, **kwargs) -> dict:
    capture = Capture.load(Path(capture_dir) / "capture.json")
    return score_capture(capture, **kwargs)
