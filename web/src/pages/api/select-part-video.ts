import fs from "node:fs";
import path from "node:path";
import {
  animationsDir,
  composeSceneVideo,
  isValidFilm,
  isValidStoryName,
  loadSceneSelections,
  saveSceneSelections,
} from "../../lib/movie";

export const prerender = false;

export async function POST({ request }: { request: Request }) {
  let body: {
    film?: string;
    name?: string;
    part?: number;
    filename?: string;
  };
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const film = typeof body.film === "string" ? body.film.trim() : "";
  const name = typeof body.name === "string" ? body.name.trim() : "";
  const part = typeof body.part === "number" ? body.part : Number.NaN;
  const filename = typeof body.filename === "string" ? body.filename.trim() : "";

  if (!film || !isValidFilm(film)) {
    return new Response(JSON.stringify({ error: `Unknown film: "${film}"` }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (!name || !isValidStoryName(film, name)) {
    return new Response(
      JSON.stringify({ error: `Unknown story scene name: "${name}"` }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!Number.isInteger(part) || part < 0) {
    return new Response(
      JSON.stringify({ error: "Part must be a non-negative integer." }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!filename) {
    return new Response(
      JSON.stringify({ error: "Filename is required." }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const sceneDir = path.join(animationsDir(film), name);
  const targetFile = path.join(sceneDir, filename);

  if (!fs.existsSync(targetFile)) {
    return new Response(
      JSON.stringify({ error: `Target video file does not exist: "${filename}"` }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    );
  }

  try {
    const selections = loadSceneSelections(film, name);
    selections[part] = filename;
    saveSceneSelections(film, name, selections);

    const result = await composeSceneVideo(film, name);

    return new Response(
      JSON.stringify({
        success: true,
        fullVideo: "full.mp4",
        selections,
        output: result.output,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: (err as Error).message }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
}
