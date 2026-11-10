# SEO parity checklist: DocFX → doc-kitty (#6935)

Produced by WP02 (2026-11-10). Each DocFX rule in `scripts/docs/seo_verify.py` / `seo_postprocess.py` mapped to its doc-kitty / Starlight equivalent. The `render` surface of `scripts/docs/site_built_check.py` asserts description, self-canonical and `og:title`/`og:description`/`og:url` on every built page, and no literal GitHub alert marker.

| DocFX rule (source) | doc-kitty / Starlight equivalent | Status |
|---|---|---|
| V-06 description present (`seo_verify.py:290-293`) | Starlight `dist/utils/head.js` meta description; frontmatter gate requires `description`; `render` surface asserts non-empty | Parity |
| V-07 description is not the boilerplate (`seo_verify.py:294-302`, `seo_postprocess.py:22-31`) | None; Starlight falls back to the site description; required `description` lowers the risk | Gap (low): upstream issue requested |
| V-08 canonical equals page URL (`seo_verify.py:305-318`) | Starlight `head.js:14-40`; asserted by `render` | Parity |
| V-09 og:title/og:description match (`seo_verify.py:320-340`) | Starlight `head.js:68-83` from the same frontmatter; `render` asserts presence | Parity by construction |
| V-10 descriptions unique (`seo_verify.py:342-363`) | None | Gap: upstream issue requested |
| NFR-001 title present, not the site default (`seo_verify.py:281-287`) | Starlight `<title>{page} \| {site}`; frontmatter gate requires `title` | Parity by construction |
| I-09 redirect stubs noindex, not in sitemap (`seo_verify.py:366-379`) | Redirects are #6933 | Deferred to #6933 |
| C-B6 sitemap equals indexable set (`seo_verify.py:382-392`) | `@astrojs/sitemap` + doc-kitty `sitemapDraftFilter` + section `feeds`; `sitemap` surface asserts no unpublished route | Partial (completeness not asserted) |
| og:site_name/og:type/og:image/twitter:* (`seo_postprocess.py:299-308`) | Starlight `head.js`; doc-kitty `components/slots/HeadShare.astro` | Parity |
| JSON-LD breadcrumbs/kitty-specs (`seo_postprocess.py:134-250, 309`) | None | Dropped by ruling 3 (#6100) |
| noindex on non-indexable pages (`seo_postprocess.py:74-91, 316-319`) | doc-kitty `components/Head.astro` robots noindex on drafts; drafts not built | Parity |
| `write_sitemap` (`seo_postprocess.py:366`) | `@astrojs/sitemap` | Parity |
| `write_robots` / `write_cname` (`seo_postprocess.py:387-398`) | `site/public/robots.txt`, `site/public/CNAME` | Parity |
| Head injection | Starlight head + doc-kitty `Head` carrier; no `starlight.head` (doc-kitty #295) | Parity; #295 a constraint |

`seo_postprocess.py` / `seo_verify.py` stay until DocFX retirement (#6943, ADR D-13).
