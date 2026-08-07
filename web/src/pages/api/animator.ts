import { spawn } from "node:child_process";
import { PROJECT_ROOT, isValidFilm, isValidStoryName } from "../../lib/movie";

export const prerender = false;

export async function POST({ request }: { request: Request }) {
  let body: { film?: string; name?: string; parts?: number; frameStart?: string; frameEnd?: string };
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
  const parts = typeof body.parts === "number" ? body.parts : Number.NaN;
  const frameStart = typeof body.frameStart === "string" ? body.frameStart.trim() : "";
  const frameEnd = typeof body.frameEnd === "string" ? body.frameEnd.trim() : "";

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
  if (!Number.isInteger(parts) || parts < 0) {
    return new Response(
      JSON.stringify({ error: "Parts must be a non-negative integer." }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const args = ["run", "animator", "--film", film, "--scene", name, "--parts", String(parts)];
  if (frameStart) args.push("--frame_start", frameStart);
  if (frameEnd) args.push("--frame_end", frameEnd);

  const command = `uv run animator --film ${film} --scene ${name} --parts ${parts}` +
    (frameStart ? ` --frame_start ${frameStart}` : "") +
    (frameEnd ? ` --frame_end ${frameEnd}` : "");

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

      push(`$ ${command}\n`);
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
