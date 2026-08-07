import { spawn } from "node:child_process";
import { PROJECT_ROOT, isValidFilm, isValidStoryName, scriptgenCommand } from "../../lib/movie";

export const prerender = false;

export async function POST({ request }: { request: Request }) {
  let body: { film?: string; name?: string; force?: boolean };
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
  const force = Boolean(body.force);

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

  const args = ["run", "scriptgen", "--film", film, "--name", name];
  if (force) args.push("--force");

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      const child = spawn("uv", args, {
        cwd: PROJECT_ROOT,
        env: process.env,
        stdio: ["ignore", "pipe", "pipe"],
      });

      const push = (chunk: Buffer | string) =>
        controller.enqueue(encoder.encode(chunk.toString()));

      push(`$ ${scriptgenCommand(film, name, force)}\n`);
      push(`(cwd: ${PROJECT_ROOT})\n\n`);

      child.stdout.on("data", push);
      child.stderr.on("data", push);

      child.on("error", (err) => {
        push(`\n[error] ${err.message}\n[exit:127]\n`);
        controller.close();
      });

      child.on("close", (code) => {
        push(`\n[exit:${code ?? 0}]\n`);
        controller.close();
      });

      request.signal.addEventListener("abort", () => {
        child.kill("SIGTERM");
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
