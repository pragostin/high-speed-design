# High-Speed Design — Knowledge Base

A personal, searchable library of study notes on high-speed IC design: TIAs,
drivers, equalization (CTLE), inductive peaking / T-coils, RF & transmission-line
theory, noise, PAM4 signaling, and layout/EM. Built around **public material only**
(papers, textbooks) — no confidential or work-internal content.

Each note is a self-contained **card**: a Markdown file with a small frontmatter
header (title, topics, keywords, date). The site renders the cards newest-first,
with full-text search and topic-chip filtering. No build framework, no backend —
just static files. Math via KaTeX, diagrams via Mermaid.

---

## How it works

```
high-speed-design/
├── cards/                  ← the knowledge base — one .md file per note
├── material/              ← raw papers / book chapters / data (local only, git-ignored)
├── site/                  ← the deployable static site
│   ├── index.html         ← the app (search, chips, card rendering)
│   ├── cards.json         ← generated index (metadata + body of every card)
│   └── assets/lib/        ← vendored KaTeX / Mermaid / marked (regenerated, git-ignored)
├── scripts/
│   ├── build_index.py     ← scans cards/ → writes site/cards.json
│   └── fetch-libs.sh      ← downloads the frontend libraries into assets/lib/
└── vercel.json            ← Vercel build config
```

The site reads `cards.json`. You never edit `cards.json` by hand — it is
regenerated from the `cards/` folder by `build_index.py`.

---

## Adding a new note (the everyday workflow)

1. (Optional) Drop the source paper / chapter into `material/`.
2. Create a new file in `cards/`, named `YYYY-MM-DD-short-slug.md`.
3. Give it frontmatter, then write the body in Markdown:

   ```markdown
   ---
   title: CTLE Zero/Pole Placement for 56 GHz Equalization
   topics: [CTLE, BW Compensation, RF Theory]
   keywords: [continuous-time linear equalizer, source degeneration, peaking, zero]
   date: 2026-06-01
   material: [material/ctle-paper-2023.pdf]
   summary: One-line description shown on the card before you expand it.
   ---

   ## Background
   Prose with inline math like $f_z = 1/(2\pi R_s C_s)$ ...

   $$ H(s) = \frac{...}{...} $$       ← display math

   ```mermaid
   graph LR
     A["Input"] --> B["CTLE"] --> C["Slicer"]
   ```
   ```

4. Regenerate the index:

   ```bash
   python3 scripts/build_index.py
   ```

5. Refresh the browser. The new card appears at the top.

### Frontmatter fields

| field      | purpose                                                            |
|------------|--------------------------------------------------------------------|
| `title`    | card heading                                                       |
| `topics`   | big reusable buckets → become the filter chips. A card can have several (a card is allowed to be both `TIA` and `Driver`). |
| `keywords` | finer free-text terms; searchable, shown as `#tags`                |
| `date`     | `YYYY-MM-DD`; controls newest-first ordering                       |
| `summary`  | one line shown on the collapsed card                               |
| `material` | optional list of source files (paths under `material/`)            |

**Topics vs keywords:** topics are the few stable categories you filter by;
keywords are everything else. Both feed the search box, so you can always just
type `group delay` and find every card that mentions it, regardless of topic.

### Mermaid label tip

Wrap node labels in quotes if they contain commas, parentheses, or symbols:
`A["Shunt-feedback TIA (R_F, A)"]`. Unquoted labels with punctuation can render
garbled.

---

## Running it locally

The site must be served over HTTP (opening `index.html` via `file://` breaks
`fetch()` of `cards.json`). From the project root:

```bash
# first time only — pull down KaTeX / Mermaid / marked
bash scripts/fetch-libs.sh

# build the index
python3 scripts/build_index.py

# serve
cd site && python3 -m http.server 8000
# open http://localhost:8000
```

---

## Publishing to Vercel

This deploys like gym-tracker. `vercel.json` tells Vercel to fetch the libraries
and build the index at deploy time, then serve the `site/` folder.

```bash
# from the project root, first time:
npm i -g vercel        # if not already installed
vercel                 # link + deploy a preview
vercel --prod          # promote to production
```

On every `git push` (once linked to the repo), Vercel re-runs the build and
redeploys automatically.

> The build needs both `bash` and `python3`, which the default Vercel build
> image provides. If Python isn't found, set the project's Node/runtime image to
> one that includes Python 3, or pre-generate `cards.json` locally and commit it
> (then simplify `buildCommand` to just `bash scripts/fetch-libs.sh`).

### Password protection — two ways

**A. Built-in (recommended, zero code).**
In the Vercel dashboard: **Project → Settings → Deployment Protection →
Password Protection → Enable**, set a password, save. The whole site is then
gated at Vercel's edge. This is the cleanest option and what to use day-to-day.
(Availability depends on your Vercel plan.)

**B. Serverless gate (the learning exercise).**
If you want to understand the mechanism, the idea is:

- Add an `api/` serverless function that receives a submitted password,
  compares it to an environment variable (e.g. `SITE_PASSWORD`), and on success
  sets a signed cookie.
- A second function (or Vercel Middleware, `middleware.js` at the root) checks
  that cookie on every request and redirects to a small login page if it's
  missing.
- The password lives in a Vercel **Environment Variable**, never in the repo.

This is more moving parts than option A but teaches you how edge auth, cookies,
and environment variables fit together. Ask and we can build it step by step.

---

## Notes on scope & safety

- **Public material only.** Keep anything confidential or work-internal out of
  `cards/`. The `material/` folder is git-ignored so raw PDFs never get pushed.
- The whole thing is dependency-light on purpose: if a library ever breaks,
  re-run `fetch-libs.sh` to re-vendor known-good versions.
