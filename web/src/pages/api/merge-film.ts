import { spawn } from "node:child_process";
import { PROJECT_ROOT, isValidFilm } from "../../lib/movie";

export const prerender = false;

export async function POST({ request }: { request: Request }) {
  let body: { film?: string };
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), { status: 400 });
  }
  const film = typeof body.film === "string" ? body.film.trim() : "";
  if (!film || !isValidFilm(film)) {
    return new Response(JSON.stringify({ error: `Unknown film: "${film}"` }), { status: 400 });
  }
  const command = `uv run python src/merge_film.py --film ${film}`;
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      const child = spawn("uv", ["run", "python", "src/merge_film.py", "--film", film], {
        cwd: PROJECT_ROOT,
        env: process.env,
        stdio: ["ignore", "pipe", "pipe"],
      });
      const push = (chunk: Buffer | string) => controller.enqueue(encoder.encode(chunk.toString()));
      push(`$ ${command}\n(cwd: ${PROJECT_ROOT})\n\n`);
      child.stdout.on("data", push);
      child.stderr.on("data", push);
      child.on("error", (error) => {
        push(`\n[error] ${error.message}\n[exit:127]\n`);
        controller.close();
      });
      child.on("close", (code) => {
        push(`\n[exit:${code ?? 0}]\n`);
        controller.close();
      });
      request.signal.addEventListener("abort", () => child.kill("SIGTERM"));
    },
  });
  return new Response(stream, {
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-cache", "X-Accel-Buffering": "no" },
  });
}
