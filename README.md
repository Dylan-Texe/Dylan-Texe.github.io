# Dylan

Personal site and X pin for [@Dylan_Texe](https://x.com/Dylan_Texe).

Published with GitHub Pages from this repository: [dylan-texe.github.io](https://dylan-texe.github.io/).

This is not the Tech Briefing product. That lives at [thetechbriefing.com](https://thetechbriefing.com).

## Pages

| Path | What it is |
| --- | --- |
| `/` | Pin. Name, one-line role, X, email, four products. |
| `/about/` | Short note. |
| `/archive/` | What this host used to be. |
| `/colophon/` | How the page is made. |

Work on the pin:

- [Tech Briefing](https://thetechbriefing.com) — live. Private intelligence. Morning desk briefing.
- [DocGlue](https://docglue.com) — live. Deal-pack and document workflow.
- [syntax.energy](https://syntax.energy) — lab. Satire energy utility.
- [Living System](https://project-x-living-system-taupe.vercel.app) — lab. Habitat for an escaped digital organism.

Living System has no custom domain on the Vercel project `project-x-living-system`. The link is that project's public production domain (`project-x-living-system-taupe.vercel.app`). Other `*.vercel.app` aliases on the project are deployment-protected.

Email on the pin is [syntax.energy@proton.me](mailto:syntax.energy@proton.me).

## Preview

No build step. The pin is static HTML and CSS.

```bash
make dev
# http://localhost:8080
```

`make dev` serves the files the way GitHub Pages does, including `404.html` for unknown paths.

`python3 scripts/build_site.py` refuses to run. It used to publish the Tech Briefing network console over `/`, which would replace this pin.

## Archive

`archive/network-console/` is a snapshot of that earlier console. It is not maintained and not linked from the pin. `robots.txt` asks crawlers to skip it.

`scripts/` and `data/` remain from that console. The scheduled RSS ingest no longer runs. The workflow can still be started by hand; it does not publish the site.
