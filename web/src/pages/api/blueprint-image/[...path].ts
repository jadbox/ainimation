import fs from "node:fs";
import path from "node:path";
import { BLUEPRINT_DIR } from "../../../lib/movie";

export const prerender = false;

export async function GET({ params }: { params: { path?: string } }) {
  const rel = params.path ?? "";
  const file = path.resolve(BLUEPRINT_DIR, rel);
  if (!file.startsWith(BLUEPRINT_DIR + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
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
