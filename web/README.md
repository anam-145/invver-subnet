# web

A static page that walks through the pipeline: retrieval, generation, and the exploit trace.

No build step, no backend, no environment variables. Three files.

---

## Run locally

```bash
python -m http.server 8080
# → http://localhost:8080/?lang=en
```

or `npx serve .`. Opening `index.html` via `file://` also works — there are no fetches.

## Language

`KO / EN` toggle at top right, also settable by URL:

```
http://localhost:8080/?lang=en
```

## Layout

```
index.html          structure + i18n keys
assets/styles.css   design tokens and layout
assets/app.js       i18n · stage 1 static analyzer · exploit trace
```

Stage 1 genuinely runs in the browser — paste any Solidity into the textarea and the signal extraction and property ranking recompute. Press **Fix the CEI order** and the violation disappears while reentrancy drops from 7 to 4.

Stages 2 and 3 are labelled as not yet run, because they have not been. Do not fill them with fabricated output; see the note at the bottom of this file.

---

## Deploying

Every path is relative, so a subdirectory works as well as a subdomain. Only `index.html` and `assets/` need to be uploaded — not this README.

### Static host (Cloudflare Pages, Vercel, Netlify, GitHub Pages)

No build command. Output directory `web`.

### Nginx

```nginx
server {
    listen 80;
    server_name demo.example.com;
    root /var/www/invariant-subnet;
    index index.html;

    location / { try_files $uri $uri/ =404; }
    location /assets/ { expires 7d; add_header Cache-Control "public"; }
}
```

### Caddy (automatic HTTPS)

```
demo.example.com {
    root * /var/www/invariant-subnet
    file_server
}
```

### Upload

```bash
scp -r index.html assets user@host:/var/www/invariant-subnet/
```

Create the directory and fix ownership first — `scp` will not create nested directories, and web roots are usually owned by root.

---

## Design tokens

| Role | Value |
|---|---|
| Primary | `#3182F6` |
| Background | `#F9FAFB` |
| Text | `#4E5968` |
| Title | `#191F28` |
| Border | `#E5E8EB` |
| Secondary text | `#8B95A1` |
| Fill | `#F2F4F6` |
| Danger | `#F04452` |
| Success | `#00A661` |

Typeface is **Pretendard Variable** (dynamic subset, jsDelivr CDN) — the only external reference on the page.

### Self-hosting the font

To remove that dependency:

```bash
mkdir -p assets/fonts
curl -L -o assets/fonts/PretendardVariable.woff2 \
  https://github.com/orioncactus/pretendard/raw/main/packages/pretendard/dist/web/variable/woff2/PretendardVariable.woff2
```

Delete the CDN `<link>` from `index.html` and add to the top of `assets/styles.css`:

```css
@font-face {
  font-family: "Pretendard Variable";
  font-weight: 45 920;
  font-style: normal;
  font-display: swap;
  src: url("./fonts/PretendardVariable.woff2") format("woff2-variations");
}
```

`assets/fonts/` is gitignored at the repository root — remove that line if you vendor the font.

---

## Editing

- **Copy** — the `I18N` object in `assets/app.js`. Change `ko` and `en` together.
- **Evidence table** — `EVIDENCE` in the same file.
- **Limitations** — `LIMITS` in the same file.
- **Reference property corpus** — `PROPERTIES`. Keep in sync with [`../generator/src/reference_db.json`](../generator/src/reference_db.json).
- **Static analyzer** — `extractSignals` / `detectCEI`. This is a port of [`../generator/src/retrieve.mjs`](../generator/src/retrieve.mjs). **Do not change one without the other.**

### After stages 2 and 3 have actually been run

The page currently marks them **not yet run**, honestly. Once they have been executed from `generator/`:

1. Replace the warning text in `I18N.*.s2.warn` and `s3.warn` with the measured result.
2. Change the `.state pending` class to `.state live` in `index.html`.
3. Flip the last two rows of `EVIDENCE` from `no` to `ok`.
4. Add the generated invariants to the stage 2 section.

**Do not fill in results that were not produced.** A technical conversation surfaces it immediately.
