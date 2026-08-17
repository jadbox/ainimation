import { spawn } from "node:child_process";
import { PROJECT_ROOT, isValidFilm, isValidStoryName } from "../../lib/movie";

export const prerender = false;

export async function POST({ request }: { request: Request }) {
  let body: {
    film?: string;
    name?: string;
    parts?: number;
    type?: "start" | "end" | "both";
    ref?: string;
    force?: boolean;
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
  const parts = typeof body.parts === "number" ? body.parts : undefined;
  const keyframeType = body.type === "end" || body.type === "both" ? body.type : "start";
  const ref = typeof body.ref === "string" ? body.ref.trim() : "";
  const force = body.force === true;

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

  const args = ["run", "keyframes", "--film", film, "--scene", name];
  if (parts !== undefined && Number.isInteger(parts) && parts >= 0) {
    args.push("--parts", String(parts));
  }
  args.push("--type", keyframeType);
  if (ref) {
    args.push("--ref", ref);
  }
  if (force) {
    args.push("--force");
  }

  const command =
    `uv run keyframes --film ${film} --scene ${name}` +
    (parts !== undefined ? ` --parts ${parts}` : "") +
    ` --type ${keyframeType}` +
    (ref ? ` --ref ${ref}` : "") +
    (force ? " --force" : "");

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
