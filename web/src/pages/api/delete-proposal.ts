import { deleteProposalFiles, isValidFilm, isValidStoryName } from "../../lib/movie";

export const prerender = false;

export async function POST({ request }: { request: Request }) {
  let body: {
    film?: string;
    name?: string;
    part?: number;
    kind?: "start" | "end";
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
  const kind = body.kind === "end" ? "end" : body.kind === "start" ? "start" : null;
  const filename = typeof body.filename === "string" ? body.filename.trim() : undefined;

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

  if (!kind) {
    return new Response(
      JSON.stringify({ error: "Kind must be either 'start' or 'end'." }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  try {
    const deleted = deleteProposalFiles(film, name, part, kind, filename);
    return new Response(JSON.stringify({ success: true, deleted }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: (err as Error).message }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
}
