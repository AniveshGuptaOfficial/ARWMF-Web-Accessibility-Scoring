"""Playwright capture: full-page screenshots + per-element records + structure.

Output per (page, viewport) is a Capture object serialisable to JSON:
    capture.json   — element records, structure, meta
    capture.png    — full-page screenshot (used for clutter + CLIP crops)

Element extraction runs JS in the page: computed styles are resolved once,
effective background walks ancestors, so Python never re-implements cascade.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

VIEWPORTS = {"desktop": (1280, 800), "mobile": (390, 844)}

_EXTRACT_JS = r"""
() => {
  const INTERACTIVE = 'a[href], button, input, select, textarea, summary, ' +
    '[role="button"], [role="link"], [role="checkbox"], [role="radio"], ' +
    '[role="menuitem"], [role="tab"], [onclick], [tabindex]:not([tabindex="-1"])';
  const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'META', 'LINK',
    'HEAD', 'TEMPLATE', 'SVG', 'PATH']);

  function effectiveBg(el) {
    let node = el;
    while (node && node.nodeType === 1) {
      const cs = getComputedStyle(node);
      const bg = cs.backgroundColor;
      if (bg && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)') {
        const m = bg.match(/[\d.]+/g);
        if (m && (m.length < 4 || parseFloat(m[3]) > 0)) return bg;
      }
      node = node.parentElement;
    }
    return 'rgb(255, 255, 255)';
  }

  function rectOf(el) {
    const r = el.getBoundingClientRect();
    return { x: r.x + window.scrollX, y: r.y + window.scrollY,
             w: r.width, h: r.height };
  }

  function visible(el) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' ||
        cs.visibility === 'collapse' || parseFloat(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  const textEls = [], interactive = [], images = [], links = [];

  for (const el of document.querySelectorAll('body *')) {
    if (SKIP_TAGS.has(el.tagName)) continue;
    if (!visible(el)) continue;
    const rect = rectOf(el);
    if (rect.w <= 0 || rect.h <= 0) continue;

    // --- text-bearing leaf-ish elements for contrast
    const hasText = Array.from(el.childNodes)
      .some(n => n.nodeType === 3 && n.textContent.trim().length > 0);
    if (hasText) {
      const cs = getComputedStyle(el);
      const fw = parseInt(cs.fontWeight, 10) || 400;
      textEls.push({
        tag: el.tagName.toLowerCase(),
        text: el.textContent.trim().slice(0, 300),
        fg: cs.color,
        bg: effectiveBg(el),
        font_px: parseFloat(cs.fontSize),
        bold: fw >= 700,
        alpha: 1.0,
        visible: true,
        rect,
      });
    }

    // --- interactive elements
    if (el.matches(INTERACTIVE)) {
      const parentTag = el.parentElement ? el.parentElement.tagName : '';
      const inline = el.tagName === 'A' &&
        (parentTag === 'P' || parentTag === 'SPAN' || parentTag === 'EM' ||
         parentTag === 'STRONG' || parentTag === 'LI');
      interactive.push({
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role') || '',
        rect,
        visible: true,
        inline_exception: inline,
        text: (el.innerText || '').trim().slice(0, 200),
      });
    }

    // --- images
    if (el.tagName === 'IMG') {
      const alt = el.getAttribute('alt');
      images.push({
        src: (el.currentSrc || el.getAttribute('src') || '').slice(0, 500),
        alt: alt,  // null when attribute absent, '' when empty
        role: el.getAttribute('role') || '',
        aria_hidden: el.getAttribute('aria-hidden') === 'true',
        rect,
        area_px: rect.w * rect.h,
        visible: true,
      });
    }

    // --- links for link-text dimension (dedup by element later)
    if (el.tagName === 'A' && el.getAttribute('href')) {
      links.push({
        href: el.getAttribute('href') || '',
        text: (el.innerText || '').trim().slice(0, 300),
        context: (el.parentElement ? el.parentElement.innerText : '')
          .trim().slice(0, 1000),
        rect,
      });
    }
  }

  // --- structure
  const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'));
  const navLinks = document.querySelectorAll('nav a[href], header a[href]').length ||
    document.querySelectorAll('a[href]').length;
  const hasSkip = Array.from(document.querySelectorAll('a[href^="#"]'))
    .some(a => /skip|content/i.test(a.innerText || a.getAttribute('aria-label') || ''));
  const structure = {
    h1_count: document.querySelectorAll('h1').length,
    heading_levels: headings.filter(h => visible(h))
      .map(h => parseInt(h.tagName[1], 10)),
    has_main: !!document.querySelector('main, [role="main"]'),
    has_nav: !!document.querySelector('nav, [role="navigation"]'),
    nav_link_count: navLinks,
    has_skip_link: hasSkip,
    title: document.title || '',
    lang: document.documentElement.getAttribute('lang') || '',
  };

  return { text_elements: textEls, interactive, images, links, structure,
           n_elements: document.querySelectorAll('body *').length };
}
"""


@dataclass
class Capture:
    url: str
    viewport_name: str
    width: int
    height: int
    timestamp: float
    elements: dict
    png_path: str | None = None
    meta: dict = field(default_factory=dict)

    def save(self, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        path = out_dir / "capture.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "Capture":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**payload)


def capture_page(url: str, out_dir: Path, viewport: str = "desktop",
                 full_page: bool = True, timeout_ms: int = 60000,
                 wait_ms: int = 500, channel: str | None = None) -> Capture:
    """Open URL in headless Chromium, screenshot + extract element records.

    channel: optional system-browser channel ("chrome", "msedge") to use the
    installed browser instead of Playwright's bundled Chromium. Defaults to
    the A11Y_BROWSER_CHANNEL env var, then bundled Chromium.
    """
    from playwright.sync_api import sync_playwright

    import os

    channel = channel or os.environ.get("A11Y_BROWSER_CHANNEL") or None
    if viewport not in VIEWPORTS:
        raise ValueError(f"viewport must be one of {sorted(VIEWPORTS)}")
    w, h = VIEWPORTS[viewport]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel=channel)
        try:
            ctx = browser.new_context(viewport={"width": w, "height": h},
                                      device_scale_factor=1)
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                pass  # SPAs/heavy pages: proceed after domcontentloaded + wait
            page.wait_for_timeout(wait_ms)
            elements = page.evaluate(_EXTRACT_JS)
            png_path = out_dir / "capture.png"
            # explicit timeout: web-font wait on heavy sites (apple.com) can
            # exceed the 30s default before screenshot completes
            page.screenshot(path=str(png_path), full_page=full_page,
                            timeout=timeout_ms)
        finally:
            browser.close()

    capture = Capture(
        url=url,
        viewport_name=viewport,
        width=w,
        height=h,
        timestamp=time.time(),
        elements=elements,
        png_path=str(png_path),
        meta={"full_page": full_page},
    )
    capture.save(out_dir)
    return capture
