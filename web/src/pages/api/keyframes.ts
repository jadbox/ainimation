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
    refPrev?: string;
    refAfter?: string;
    refStart?: string;
    refEnd?: string;
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
  const refPrev =
    typeof body.refPrev === "string"
      ? body.refPrev.trim()
      : typeof body.refStart === "string"
        ? body.refStart.trim()
        : typeof body.ref === "string"
          ? body.ref.trim()
          : "";
  const refAfter =
    typeof body.refAfter === "string"
      ? body.refAfter.trim()
      : typeof body.refEnd === "string"
        ? body.refEnd.trim()
        : "";

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
  if (refPrev) {
    args.push("--ref-prev", refPrev);
  }
  if (refAfter) {
    args.push("--ref-after", refAfter);
  }

  const command =
    `uv run keyframes --film ${film} --scene ${name}` +
    (parts !== undefined ? ` --parts ${parts}` : "") +
    ` --type ${keyframeType}` +
    (refPrev ? ` --ref-prev ${refPrev}` : "") +
    (refAfter ? ` --ref-after ${refAfter}` : "");

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
