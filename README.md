# tuppennywell.com

The one-page website for Tuppenny Well Ltd. Plain HTML and one small stylesheet: no framework, no build step, no JavaScript, no cookies and no tracking.

The site is hosted on GitHub Pages. Pushing to `main` publishes it.

## What is in this repo

| File | What it is |
|---|---|
| `index.html` | The whole page, including the logo seal (inlined near the bottom). |
| `styles.css` | All styling, light and dark mode. Colours are in section 1 only. |
| `favicon.svg`, `favicon.ico`, `apple-touch-icon.png` | Browser tab and home-screen icons. |
| `og-image.png` | The preview card shown when the link is shared (1200 x 630). |
| `CNAME` | Tells GitHub Pages the site's domain. **Do not edit or delete.** |
| `.nojekyll` | Tells GitHub Pages to serve the files as they are. |
| `tests/`, `scripts/` | Automated checks (see [Checks](#checks)). |
| `.github/workflows/` | The two workflows: `ci` and `live-site-check`. |

The icons and preview image are generated from the logo artwork in the [`logo-design`](https://github.com/Tuppenny-Well-Ltd/logo-design) repo. To change them, regenerate them there and copy the four files from its `assets/web/` folder to the top level of this repo.

## Editing the page

1. Create a branch, edit `index.html` or `styles.css`, and look at the result locally:

   ```bash
   python3 -m http.server 8000
   ```

   Then open <http://localhost:8000>.

2. Run the checks before you push:

   ```bash
   python3 -m unittest discover -s tests
   ```

3. Push the branch and open a pull request. The `ci` workflow runs the same tests plus the W3C HTML validator. Merge when it is green.

Things worth knowing:

- **Placeholders:** search `index.html` for `[` to find text still to fill in. The testimonial section is switched off by the word `hidden` on its `<section>` line. Delete that word once the quote is real. The tests fail if a `[PLACEHOLDER]` is visible.
- **No JavaScript, no outside resources.** The tests fail if the page adds a `<script>` or loads fonts, images or styles from another site. This protects the "no tracking, no cookie banner" promise. If you really want one, change the test in the same pull request.
- **Colours:** the tests check text contrast against the accessibility minimum (4.5:1) in both light and dark mode, so a low-contrast colour change will fail.
- **The seal:** the logo is inlined in `index.html` so it follows light and dark mode. The comment above it explains how to replace it.
- **Footer details** (company number, registered office, VAT number) must match Companies House. Update them if any of them change.

## Deploying

Merging to `main` publishes the site automatically. GitHub runs a workflow called **pages build and deployment**, and the change is normally live within a minute or two. Watch it under the repo's **Actions** tab.

If a change does not appear, hard-refresh the browser (Ctrl+Shift+R) before assuming something is wrong, because browsers cache aggressively, tab icons especially.

## Rolling back

Every change is a commit, so any change can be undone:

1. Open the pull request that caused the problem and click **Revert** at the bottom. GitHub creates a new pull request that undoes it.
2. Merge that pull request. The site redeploys the previous version.

From the command line, `git revert <commit>` does the same, and then you push it through a pull request.

**Emergency off switch:** the repo's **Settings**, then **Pages**, then **Unpublish site**, which takes the site down until you publish it again. Use it only if something must not be public right now.

## Hosting and DNS

Everything below is set up and working. This section is here so you can understand it and repair it.

- **Domain:** registered at Namecheap. DNS is also at Namecheap (Domain List, **Manage**, **Advanced DNS**). Nameservers are Namecheap's own and have not been moved.
- **Website:** GitHub Pages, serving the `main` branch from the repo root. **Enforce HTTPS** is on. GitHub issues and renews the certificate itself.
- **Email:** Proton Mail, on a custom domain. `hello@tuppennywell.com` is delivered to Proton.

These DNS records exist. Do not delete any of them without knowing what it does.

| Purpose | Type | Host | Value |
|---|---|---|---|
| Website (IPv4) | A, four records | `@` | `185.199.108.153`, `.109.153`, `.110.153`, `.111.153` |
| Website (IPv6) | AAAA, four records | `@` | `2606:50c0:8000::153`, `8001::153`, `8002::153`, `8003::153` |
| `www` redirects to the main address | CNAME | `www` | `tuppenny-well-ltd.github.io.` |
| GitHub domain verification | TXT | `_github-pages-challenge-Tuppenny-Well-Ltd` | (a code GitHub gave us) |
| Email delivery | MX, two records | `@` | `mail.protonmail.ch` (10), `mailsec.protonmail.ch` (20) |
| Email authentication | TXT and CNAME | `@`, `_dmarc`, three `protonmail*._domainkey` | Proton's SPF, DMARC and DKIM records |
| Proton domain verification | TXT | `@` | `protonmail-verification=...` |

The GitHub IP addresses come from GitHub's documentation, "Managing a custom domain for your GitHub Pages site". If the site ever stops resolving, check them against that page.

**Before changing any DNS:** take a screenshot of the Advanced DNS page. Never touch the email records or the Mail Settings dropdown (it must stay on **Custom MX**) as part of a website change.

## Renewals

- **Domain:** `tuppennywell.com` is registered for a year at a time and renews every March. Namecheap's **Auto-Renew** should be on (Domain List, **Manage**, **Auto-Renew**). Check the exact expiry date in Namecheap, and check that auto-renew is on and the payment card is current, a month or two beforehand.
- **Namecheap account email:** use an address that is **not** on `tuppennywell.com`. If the domain lapsed, mail to it would stop working, and so would the reminders.
- **If the domain lapses,** the site and email both stop. Renew it in Namecheap as soon as possible. Namecheap usually allows a short grace period after expiry, sometimes at extra cost.
- **HTTPS certificate:** renewed by GitHub, with nothing to do. The weekly check warns if it is within 10 days of expiring.

## Checks

| Check | When it runs | What it does |
|---|---|---|
| `ci` | Every pull request and push to `main` | Page tests (head tags, icons, preview image, no scripts, no outside loads, alt text, contrast, no visible placeholders) and the HTML validator. |
| `live-site-check` | Every Monday, and on demand | Checks the real site over the internet: the page loads over HTTPS, `http://` and `www` redirect correctly, the preview image is served, and the certificate is not about to expire. |

If the weekly check fails, GitHub emails whoever last edited the workflow file. To run it by hand: **Actions**, then **live-site-check**, then **Run workflow**.

**Caution:** GitHub switches scheduled workflows off after 60 days with no activity in the repo. It sends a notice, but it is easy to miss. If the repo has been quiet for a couple of months, check that the weekly check is still enabled, or run it manually.

## When something is wrong

Start by finding out what is actually broken. These commands show what the world sees:

```bash
dig +short A tuppennywell.com; dig +short AAAA tuppennywell.com; dig +short CNAME www.tuppennywell.com
```

```bash
curl -sI https://tuppennywell.com | head -5
```

```bash
dig +short MX tuppennywell.com
```

| Symptom | Likely cause and fix |
|---|---|
| Site shows an old version | Browser cache; hard-refresh. Check the latest **pages build and deployment** run succeeded. |
| `dig` shows no web addresses | A DNS record was removed or changed. Compare with the table above and restore it in Namecheap. |
| `dig` is blank here but works elsewhere | A stale cache on your own network. Ask Namecheap's server directly: add `@dns1.registrar-servers.com` to the `dig` command. |
| Certificate warning | Usually the DNS records are wrong, or the domain was changed in Pages. Check **Settings**, then **Pages**, shows "DNS check successful". As a last resort, remove the custom domain there, save, add it again and wait. Do not do this casually: it restarts certificate issuance. |
| `www` does not redirect | The `www` CNAME is missing or wrong. |
| Email stops arriving | The MX records or Mail Settings changed. Restore them, and check Proton's **Domain names** page shows all green. |
| GitHub Pages is down for a long time | The site content is entirely in this repo, so it can be served from another static host (Cloudflare Pages or Netlify) in about 15 minutes. Create the project from this repo, point the same A, AAAA and `www` records at it, and keep the email records unchanged. |

## Where things live

- **Code and content:** <https://github.com/Tuppenny-Well-Ltd/website>
- **Logo and icon source:** <https://github.com/Tuppenny-Well-Ltd/logo-design>
- **Domain and DNS:** Namecheap
- **Email:** Proton Mail (Settings, then **Domain names**)
- **Hosting settings:** the repo's **Settings**, then **Pages**

© 2026 Tuppenny Well Ltd. All rights reserved.
