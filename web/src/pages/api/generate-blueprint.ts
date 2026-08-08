import { spawn } from "node:child_process";
import {
  PROJECT_ROOT,
  blueprintCommand,
  isValidCharacter,
  isValidFilm,
  isValidSceneSlug,
} from "../../lib/movie";

export const prerender = false;

export async function POST({ request }: { request: Request }) {
  let body: { film?: string; character?: string; scene?: string; new?: boolean };
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const film = typeof body.film === "string" ? body.film.trim() : "";
  const character = typeof body.character === "string" ? body.character.trim() : "";
  const scene = typeof body.scene === "string" ? body.scene.trim() : "";
  const fresh = body.new === true;

  if (!film || !isValidFilm(film)) {
    return new Response(JSON.stringify({ error: `Unknown film: "${film}"` }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  let args: string[];
  let command: string;
  if (character && isValidCharacter(film, character)) {
    args = ["run", "generate-blueprint", "--film", film, "--character", character];
    command = blueprintCommand(film, { character }, fresh);
  } else if (scene && isValidSceneSlug(film, scene)) {
    args = ["run", "generate-blueprint", "--film", film, "--scene", scene];
    command = blueprintCommand(film, { scene }, fresh);
  } else {
    return new Response(
      JSON.stringify({ error: `Unknown blueprint subject: "${character || scene}"` }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }
  if (fresh) {
    args.push("--new");
  }

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
