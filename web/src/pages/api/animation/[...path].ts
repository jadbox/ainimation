import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import { ANIMATIONS_DIR } from "../../../lib/movie";

export const prerender = false;

const MIME: Record<string, string> = {
  ".mp4": "video/mp4",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
};

export async function GET({
  params,
  request,
}: {
  params: { path?: string };
  request: Request;
}) {
  const rel = params.path ?? "";
  const file = path.resolve(ANIMATIONS_DIR, rel);
  if (
    !file.startsWith(ANIMATIONS_DIR + path.sep) ||
    !fs.existsSync(file) ||
    !fs.statSync(file).isFile()
  ) {
    return new Response("Not found", { status: 404 });
  }

  const type = MIME[path.extname(file).toLowerCase()] ?? "application/octet-stream";
  const stat = fs.statSync(file);
  const range = request.headers.get("range");

  if (range) {
    const match = range.match(/bytes=(\d*)-(\d*)/);
    let start = 0;
    let end = stat.size - 1;
    if (match) {
      if (match[1]) start = parseInt(match[1], 10);
      if (match[2]) end = parseInt(match[2], 10);
    }
    if (Number.isNaN(start) || Number.isNaN(end) || start > end || start >= stat.size) {
      return new Response("Range Not Satisfiable", {
        status: 416,
        headers: { "Content-Range": `bytes */${stat.size}` },
      });
    }
    if (end >= stat.size) end = stat.size - 1;
    const nodeStream = fs.createReadStream(file, { start, end });
    return new Response(Readable.toWeb(nodeStream) as ReadableStream, {
      status: 206,
      headers: {
        "Content-Type": type,
        "Accept-Ranges": "bytes",
        "Content-Range": `bytes ${start}-${end}/${stat.size}`,
        "Content-Length": String(end - start + 1),
        "Cache-Control": "no-cache",
      },
    });
  }

  const nodeStream = fs.createReadStream(file);
  return new Response(Readable.toWeb(nodeStream) as ReadableStream, {
    headers: {
      "Content-Type": type,
      "Accept-Ranges": "bytes",
      "Content-Length": String(stat.size),
      "Cache-Control": "no-cache",
    },
  });
}
