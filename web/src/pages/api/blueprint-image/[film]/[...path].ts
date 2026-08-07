import fs from "node:fs";
import path from "node:path";
import { blueprintsDir, isValidFilm } from "../../../../lib/movie";

export const prerender = false;

export async function GET({ params }: { params: { film?: string; path?: string } }) {
  const film = params.film ?? "";
  if (!isValidFilm(film)) {
    return new Response("Not found", { status: 404 });
  }
  const baseDir = blueprintsDir(film);
  const rel = params.path ?? "";
  const file = path.resolve(baseDir, rel);
  if (!file.startsWith(baseDir + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    return new Response("Not found", { status: 404 });
  }
  const data = fs.readFileSync(file);
  return new Response(data, {
    headers: {
      "Content-Type": "image/jpeg",
      "Cache-Control": "no-cache",
    },
  });
}
