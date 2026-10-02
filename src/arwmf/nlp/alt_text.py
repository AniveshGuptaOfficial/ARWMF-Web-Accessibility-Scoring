"""Alt-text adequacy via CLIP image-text similarity (spec: D4).

Fully offline: the CLIP model is loaded from the local HuggingFace cache.
Constants (sigmoid midpoint/scale, generic-label penalty) are frozen in the
scoring spec; calibration-page refits must be logged as deviations.
"""
from __future__ import annotations

import re
from typing import Iterable

FILENAME_RE = re.compile(r"\.(jpe?g|png|gif|svg|webp|bmp)$", re.IGNORECASE)
GENERIC_LABELS = {"image", "picture", "photo", "icon", "logo", "graphic",
                  "screenshot", "img", "banner", "thumbnail"}

# logistic mapping constants (docs/02-accessibility-scoring-specification.md D4)
MIDPOINT = 0.24
SCALE = 0.04
GENERIC_PENALTY = 0.5
MIN_AREA_PX = 900.0

_MODEL_CACHE: dict = {}  # shared across ClipScorer instances (model load is expensive)


def _logistic(x: float) -> float:
    # numerically stable sigmoid
    if x >= 0:
        z = pow(2.718281828459045, -x)
        return 1.0 / (1.0 + z)
    z = pow(2.718281828459045, x)
    return z / (1.0 + z)


class ClipScorer:
    """Lazy-loaded CLIP (ViT-B/32) scorer for image-alt cosine similarity.

    The underlying model is cached at module level so scoring a batch of
    pages loads it once, not once per page.
    """

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32",
                 device: str | None = None):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._processor = None

    def _load(self):
        if self._model is None:
            key = ("clip", self.model_name)
            if key in _MODEL_CACHE:
                self._model, self._processor, self.device = _MODEL_CACHE[key]
                return self._model, self._processor
            import torch
            from transformers import CLIPModel, CLIPProcessor

            device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
            processor = CLIPProcessor.from_pretrained(self.model_name)
            model = CLIPModel.from_pretrained(self.model_name).to(device).eval()
            _MODEL_CACHE[key] = (model, processor, device)
            self._model, self._processor, self.device = model, processor, device
        return self._model, self._processor

    def similarity(self, image, alt_text: str) -> float:
        """Cosine similarity between the image embedding and alt-text embedding."""
        import torch

        model, processor = self._load()
        inputs = processor(text=[alt_text], images=image, return_tensors="pt",
                           padding=True, truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            out = model(**inputs)
        img = out.image_embeds[0] / out.image_embeds[0].norm(dim=-1, keepdim=True)
        txt = out.text_embeds[0] / out.text_embeds[0].norm(dim=-1, keepdim=True)
        return float((img * txt).sum())


def classify_alt(image_element: dict) -> str:
    """Route an image element: 'decorative' | 'missing' | 'filename' | 'score'."""
    alt = image_element.get("alt")  # None -> attribute absent
    if alt is None:
        if image_element.get("aria_hidden") or image_element.get("role") == "presentation":
            return "decorative"
        return "missing"
    alt = alt.strip()
    if alt == "":
        if image_element.get("role") == "presentation" or image_element.get("aria_hidden"):
            return "decorative"
        return "missing"  # empty alt on a non-presentational img is a failure
    src_name = (image_element.get("src") or "").split("?")[0].split("/")[-1]
    if FILENAME_RE.search(alt) or (src_name and alt.lower() == src_name.lower()):
        return "filename"
    return "score"


def generic_label_multiplier(alt_text: str) -> float:
    tokens = alt_text.lower().split()
    if 1 <= len(tokens) <= 3 and all(t.strip(".,") in GENERIC_LABELS for t in tokens):
        return GENERIC_PENALTY
    return 1.0


def image_alt_score(image_element: dict, scorer: ClipScorer, crop_fn) -> float | None:
    """Score one image element 0-100; None when decorative (excluded from mean).

    crop_fn(rect) -> PIL.Image for the element's screenshot crop.
    """
    kind = classify_alt(image_element)
    if kind == "decorative":
        return None
    if kind in ("missing", "filename"):
        return 0.0
    area = image_element.get("area_px")
    if area is not None and area < MIN_AREA_PX:
        return None  # too small to judge (tracking pixel)
    alt = image_element["alt"].strip()
    try:
        crop = crop_fn(image_element["rect"])
        cos = scorer.similarity(crop, alt)
    except Exception:
        return None  # unreadable crop -> exclude rather than silently zero
    score = 100.0 * _logistic((cos - MIDPOINT) / SCALE)
    return score * generic_label_multiplier(alt)


def dimension_alt_text(images: Iterable[dict], scorer: ClipScorer, crop_fn) -> float | None:
    """Mean over applicable images; None if no applicable images."""
    scores = [s for s in (image_alt_score(img, scorer, crop_fn) for img in images)
              if s is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)
