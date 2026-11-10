"""
Arb Cannon: M&A Arbitrage brand assets (brand.py)

Inline SVG logo mark and sidebar lockup (mark + "M&A Arbitrage" wordmark) for
the light UI. Self-contained: no external assets; the wordmark uses the page's
Inter font. Drop BRAND_LOCKUP_HTML in place of the sidebar brand block and
append BRAND_CSS to the page <style>.
"""

# Mark only: two slanted strokes forming a stylized "M". Fills use currentColor
# so the mark can be recolored via CSS `color`; the white sheen on the lower
# diagonal is a translucent overlay and works on any ink color. viewBox is 2:1.
LOGO_MARK_SVG = r"""<svg class="arb-brand-mark" width="44" height="22" viewBox="0 0 166.8 83.3" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">
  <defs>
    <linearGradient id="arb-brand-sheen" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0.3" stop-color="#FFFFFF" stop-opacity="0"/>
      <stop offset="1" stop-color="#FFFFFF" stop-opacity="0.12"/>
    </linearGradient>
  </defs>
  <path fill="currentColor" d="M67.3 8.8H90.2L100.9 19.9L44.4 83.3H0Z"/>
  <path fill="currentColor" d="M134.8 0H166.8V83.3H135.7V39.5L97.8 83.3H61.3Z"/>
  <path fill="url(#arb-brand-sheen)" d="M134.8 0H135.7V39.5L97.8 83.3H61.3Z"/>
</svg>"""

# Styles for BRAND_LOCKUP_HTML. Padding matches the legacy `.brand` block so the
# lockup is a spacing-neutral swap; the lockup fits a 164px sidebar content box.
BRAND_CSS = r"""
    .arb-brand { --arb-brand-ink: #1F2226; display: flex; align-items: center; gap: 8px; padding: 2px 8px 22px; color: var(--arb-brand-ink); text-decoration: none; }
    .arb-brand-mark { width: 44px; height: 22px; flex: none; display: block; }
    .arb-brand-word { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-weight: 700; font-size: 15px; line-height: 1; letter-spacing: -0.3px; white-space: nowrap; color: var(--arb-brand-ink); }
"""

BRAND_LOCKUP_HTML = (
    r"""<div class="arb-brand" role="img" aria-label="M&amp;A Arbitrage">"""
    + LOGO_MARK_SVG
    + r"""<span class="arb-brand-word" aria-hidden="true">M&amp;A Arbitrage</span></div>"""
)
