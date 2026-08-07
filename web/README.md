# Animation Console (web)

A local Astro + Tailwind UI over the animation pipeline tools (`scriptgen`, `generate-blueprint`, `animator`). No authentication — intended to run on your machine alongside the Python pipeline.

## Features

- Multi-film support: each film lives in `../films/<slug>/` (its own `movie.yml` and `out/` assets). The app routes by film (`/<film>`, `/<film>/scene/...`) and `/` redirects to the default film. When more than one film exists, a film switcher appears in the header; the header title always reflects the selected film's `movie.yml` title.
- Scene table driven by the `story:` section of the film's `movie.yml`, with live script status from `films/<film>/out/scripts/`.
- **Create scripts** button runs `uv run scriptgen --film <film> --name <scene>` on the server and streams the output into a terminal panel.
- **View scripts** page renders all three 10-second segment scripts (`<scene>_part0..2.md`) with a sticky index.
- **Copy animator cmd** copies `uv run animator --film <film> --scene <scene>` to the clipboard so you can run video generation yourself in a terminal.

## Running

From the project root:

```bash
./start_web.sh
```

Or manually:

```bash
cd web
npm install
npm run dev
```

Then open http://localhost:4321.

The server resolves the pipeline root by walking up from `web/` until it finds the `films/` directory. Override with `ANIMATION_ROOT=/path/to/animation npm run dev` if needed. The default film is the first folder under `films/` that has a `movie.yml` (override with `FILM=<slug>`). `uv` must be on `PATH`, and the API keys required by `scriptgen` (`OPENROUTER_API_KEY`) must be set in the environment the dev server runs in.

## Production build

```bash
npm run build
node dist/server/entry.mjs            # default: http://localhost:4321
PORT=8080 HOST=127.0.0.1 node dist/server/entry.mjs
```

## Notes

- Scripts are only ever written by `scriptgen` (the UI shells out to it); the web server never writes to `films/<film>/out/scripts/` directly.
- Video generation is intentionally not triggered from the UI — copy the `animator` command and run it in your terminal.
