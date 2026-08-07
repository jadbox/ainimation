# Animation Console (web)

A local Astro + Tailwind UI over the animation pipeline tools (`scriptgen`, `generate-blueprint`, `animator`). No authentication — intended to run on your machine alongside the Python pipeline.

## Features

- Scene table driven by the `story:` section of `../movie.yml`, with live script status from `../out/scripts/`.
- **Create scripts** button runs `uv run scriptgen --name <scene>` on the server and streams the output into a terminal panel.
- **View scripts** page renders all three 10-second segment scripts (`<scene>_part0..2.md`) with a sticky index.
- **Copy animator cmd** copies `uv run animator --scene <scene>` to the clipboard so you can run video generation yourself in a terminal.

## Running

```bash
cd web
npm install
npm run dev
```

Then open http://localhost:4321.

The server resolves the pipeline root by walking up from `web/` until it finds `movie.yml`. Override with `ANIMATION_ROOT=/path/to/animation npm run dev` if needed. `uv` must be on `PATH`, and the API keys required by `scriptgen` (`OPENROUTER_API_KEY`) must be set in the environment the dev server runs in.

## Production build

```bash
npm run build
node dist/server/entry.mjs            # default: http://localhost:4321
PORT=8080 HOST=127.0.0.1 node dist/server/entry.mjs
```

## Notes

- Scripts are only ever written by `scriptgen` (the UI shells out to it); the web server never writes to `out/scripts/` directly.
- Video generation is intentionally not triggered from the UI — copy the `animator` command and run it in your terminal.
