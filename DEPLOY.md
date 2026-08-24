# Deploying to Vercel

You are deploying the **pre-built static site in `dist/`**. `build.py`, `data/` and
`style.css` are your source — they don't need to be served.

> **SEO note:** the pages carry self-referencing canonicals set from `baseUrl` in
> `data/site.json` (currently `https://jaaga-hyderabad.vercel.app`). The live URL MUST
> match `baseUrl`. If your Vercel URL ends up different, change `baseUrl`, run
> `python build.py`, and redeploy.

---

## Method A — Vercel CLI (no GitHub needed) — recommended to go live now

1. Install Node.js (https://nodejs.org), then the Vercel CLI:
   ```
   npm i -g vercel
   ```
2. Log in:
   ```
   vercel login
   ```
3. Deploy the built site:
   ```
   cd "C:\Users\adina\Desktop\Marketing Skill\jaaga-hyderabad-seo\dist"
   vercel --prod
   ```
   First run prompts — answer:
   - Set up and deploy? **Y**
   - Link to existing project? **N**
   - Project name? **jaaga-hyderabad**   ← sets the URL to jaaga-hyderabad.vercel.app
   - In which directory is your code? **./** (Enter)
   - Modify build settings? **N**
4. Confirm the printed URL is `https://jaaga-hyderabad.vercel.app`. If not, update
   `baseUrl` to the real URL, `python build.py`, and `vercel --prod` again.

### Redeploy after changes
```
cd "C:\Users\adina\Desktop\Marketing Skill\jaaga-hyderabad-seo"
python build.py
cd dist
vercel --prod
```

---

## Method B — GitHub → Vercel (optional; auto-deploy on every push)

Use this only if you want a repo + automatic deploys.

1. Create a repo on GitHub, then from the project root:
   ```
   git init
   git add .
   git commit -m "JaaGa Hyderabad static SEO site"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```
   (The committed `dist/` folder is what gets served — keep it committed.)
2. In Vercel: **Add New → Project → Import** the repo, then set:
   - **Framework Preset:** Other
   - **Build Command:** *(leave empty)*
   - **Output Directory:** `dist`
   - **Install Command:** *(leave empty)*
3. Deploy. Every future `git push` (after running `python build.py` and committing
   the updated `dist/`) redeploys automatically.

---

## Before pointing your real domain at it later
When ready to move to `hyderabad.jaaga.ai`:
1. Set `baseUrl` to `https://hyderabad.jaaga.ai`, run `python build.py`, redeploy.
2. In Vercel: Project → Settings → Domains → add `hyderabad.jaaga.ai`.
3. In your `jaaga.ai` DNS: add the CNAME record Vercel shows.
4. *Then* submit the sitemap in Google Search Console and start link-building.
