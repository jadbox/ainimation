import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { load as loadYaml } from "js-yaml";

export interface Character {
  name: string;
  species: string;
  identity: string;
  appearance: string;
  voice: string;
  avoid: string;
}

export interface SceneLocation {
  name: string;
  slug: string;
  logline: string;
  backgrounds: Array<{
    key: string;
    description: string;
    lighting: string;
    mood: string;
  }>;
}

export interface StoryScene {
  name: string;
  title: string;
  scene: string;
  characters: string[];
  emotions: string[];
  actions: string[];
  looks: string[];
}

export interface MovieConfig {
  movie: {
    title: string;
    headline: string;
    style: string;
    camera_rules: string;
    hard_direction_rules: string[];
  };
  characters: Character[];
  scenes: SceneLocation[];
  story: StoryScene[];
}

function findProjectRoot(): string {
  if (process.env.ANIMATION_ROOT)
    return path.resolve(process.env.ANIMATION_ROOT);
  let dir = import.meta.dirname;
  for (let i = 0; i < 8; i++) {
    if (fs.existsSync(path.join(dir, "films"))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return path.resolve(import.meta.dirname, "..", "..", "..");
}

export const PROJECT_ROOT = findProjectRoot();
export const FILMS_DIR = path.join(PROJECT_ROOT, "films");

export function listFilms(): string[] {
  if (!fs.existsSync(FILMS_DIR)) return [];
  return fs
    .readdirSync(FILMS_DIR, { withFileTypes: true })
    .filter(
      (e) =>
        e.isDirectory() &&
        fs.existsSync(path.join(FILMS_DIR, e.name, "movie.yml")),
    )
    .map((e) => e.name)
    .sort();
}

export function isValidFilm(film: string): boolean {
  return listFilms().includes(film);
}

export function defaultFilm(): string {
  const films = listFilms();
  const env = process.env.FILM;
  if (env && films.includes(env)) return env;
  return films[0] ?? "";
}

export function requireFilm(film: string): string {
  if (!isValidFilm(film)) {
    throw new Error(
      `Unknown film "${film}". Available films: ${listFilms().join(", ")}`,
    );
  }
  return film;
}

export function filmRoot(film: string): string {
  return path.join(FILMS_DIR, requireFilm(film));
}

export function movieYmlPath(film: string): string {
  return path.join(filmRoot(film), "movie.yml");
}

export function scriptsDir(film: string): string {
  return path.join(filmRoot(film), "out", "scripts");
}

export function blueprintsDir(film: string): string {
  return path.join(filmRoot(film), "out", "blueprint");
}

export function animationsDir(film: string): string {
  return path.join(filmRoot(film), "out", "animations");
}

const cache = new Map<string, { mtimeMs: number; config: MovieConfig }>();

export function loadMovie(film: string): MovieConfig {
  const file = movieYmlPath(film);
  const stat = fs.statSync(file);
  const cached = cache.get(film);
  if (cached && cached.mtimeMs === stat.mtimeMs) return cached.config;
  const config = loadYaml(fs.readFileSync(file, "utf8")) as MovieConfig;
  cache.set(film, { mtimeMs: stat.mtimeMs, config });
  return config;
}

export function scriptPath(film: string, name: string, part: number): string {
  return path.join(scriptsDir(film), `${name}_part${part}.md`);
}

export function scriptStatus(film: string, name: string): boolean[] {
  const parts = scriptPartIndices(film, name);
  return parts.map((part) => fs.existsSync(scriptPath(film, name, part)));
}

export function scriptPartIndices(film: string, name: string): number[] {
  const dir = scriptsDir(film);
  if (!fs.existsSync(dir)) return [0, 1, 2];
  const pattern = new RegExp(
    `^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}_part(\\d+)\\.md$`,
    "i",
  );
  const parts = fs
    .readdirSync(dir)
    .map((file) => file.match(pattern))
    .filter((match): match is RegExpMatchArray => match !== null)
    .map((match) => Number(match[1]))
    .sort((a, b) => a - b);
  return parts.length > 0 ? parts : [0, 1, 2];
}

export function readScript(
  film: string,
  name: string,
  part: number,
): string | null {
  const file = scriptPath(film, name, part);
  if (!fs.existsSync(file)) return null;
  return fs.readFileSync(file, "utf8");
}

export function animatorCommand(film: string, name: string): string {
  return `uv run animator --film ${film} --scene ${name}`;
}

export function scriptgenCommand(
  film: string,
  name: string,
  force = false,
  parts = 3,
): string {
  return `uv run scriptgen --film ${film} --name ${name} --parts ${parts}${force ? " --force" : ""}`;
}

export function isValidStoryName(film: string, name: string): boolean {
  return loadMovie(film).story.some((s) => s.name === name);
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function subjectBlueprintDir(film: string, subject: string): string {
  return path.join(blueprintsDir(film), slugify(subject));
}

export function backgroundBlueprintDir(
  film: string,
  sceneSlug: string,
  bgKey: string,
): string {
  return path.join(blueprintsDir(film), slugify(sceneSlug), slugify(bgKey));
}

export interface BlueprintInfo {
  attempts: string[];
  latest: string | null;
  style: string | null;
}

export function blueprintInfo(dir: string): BlueprintInfo {
  const empty: BlueprintInfo = { attempts: [], latest: null, style: null };
  if (!fs.existsSync(dir)) return empty;
  const files = fs.readdirSync(dir);
  const attempts = files.filter((f) => /^attempt-\d+\.jpg$/.test(f)).sort();
  const style = files.find((f) => f.endsWith("-style.jpg")) ?? null;
  return {
    attempts,
    latest: attempts.length > 0 ? attempts[attempts.length - 1] : null,
    style,
  };
}

function extractFrame(
  clipPath: string,
  destination: string,
  first: boolean,
): boolean {
  const args = ["-y"];
  if (!first) args.push("-sseof", "-0.1");
  args.push("-i", clipPath, "-frames:v", "1", "-q:v", "2", destination);
  const result = spawnSync("ffmpeg", args, { encoding: "utf8" });
  return result.status === 0 && fs.existsSync(destination);
}

export function resolveSceneFrame(
  film: string,
  sceneName: string,
  part: number,
  kind: "start" | "end",
): string | null {
  const dir = path.join(animationsDir(film), sceneName);
  if (!fs.existsSync(dir)) return null;
  const named = `part-${part}-${kind}.jpg`;
  const namedPath = path.join(dir, named);
  if (fs.existsSync(namedPath))
    return `films/${film}/out/animations/${sceneName}/${named}`;
  if (kind === "end") {
    const legacy = path.join(dir, `part-${part}.jpg`);
    if (fs.existsSync(legacy))
      return `films/${film}/out/animations/${sceneName}/part-${part}.jpg`;
  }
  const clip = path.join(dir, `part-${part}.mp4`);
  if (fs.existsSync(clip) && extractFrame(clip, namedPath, kind === "start")) {
    return `films/${film}/out/animations/${sceneName}/${named}`;
  }
  return null;
}

function dirHasBlueprintImages(dir: string): boolean {
  const info = blueprintInfo(dir);
  return info.latest !== null || info.style !== null;
}

export function hasBlueprint(film: string, subject: string): boolean {
  const dir = subjectBlueprintDir(film, subject);
  if (!fs.existsSync(dir)) return false;
  if (dirHasBlueprintImages(dir)) return true;
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .some((e) => dirHasBlueprintImages(path.join(dir, e.name)));
}

export function isValidCharacter(film: string, name: string): boolean {
  return loadMovie(film).characters.some((c) => c.name === name);
}

export function isValidSceneSlug(film: string, slug: string): boolean {
  return loadMovie(film).scenes.some((s) => s.slug === slug);
}

export function blueprintCommand(
  film: string,
  target: { character?: string; scene?: string },
): string {
  return target.character
    ? `uv run generate-blueprint --film ${film} --character "${target.character}"`
    : `uv run generate-blueprint --film ${film} --scene ${target.scene}`;
}

export function hasAnimation(film: string, name: string): boolean {
  return fs.existsSync(path.join(animationsDir(film), name, "full.mp4"));
}

export interface FilmVideo {
  file: string;
  thumb: string;
}

export function filmVideo(film: string): FilmVideo | null {
  const dir = animationsDir(film);
  const file = "film.mp4";
  const thumb = "film-thumb.jpg";
  return fs.existsSync(path.join(dir, file)) &&
    fs.existsSync(path.join(dir, thumb))
    ? { file, thumb }
    : null;
}

export interface SegmentVideo {
  part: number;
  video: string;
  thumb: string | null;
  startThumb: string | null;
  endThumb: string | null;
}

export interface SceneVideos {
  full: { thumb: string | null } | null;
  segments: SegmentVideo[];
}

function pickThumb(files: Set<string>, base: string): string | null {
  if (files.has(`${base}-end.jpg`)) return `${base}-end.jpg`;
  if (files.has(`${base}.jpg`)) return `${base}.jpg`;
  return null;
}

export function sceneVideos(film: string, name: string): SceneVideos {
  const dir = path.join(animationsDir(film), name);
  const empty: SceneVideos = { full: null, segments: [] };
  if (!fs.existsSync(dir)) return empty;
  const files = new Set(fs.readdirSync(dir));
  const segments: SegmentVideo[] = [];
  for (const file of files) {
    const match = file.match(/^part-(\d+)\.mp4$/);
    if (match) {
      const base = `part-${match[1]}`;
      segments.push({
        part: Number(match[1]),
        video: file,
        thumb: pickThumb(files, base),
        startThumb: files.has(`${base}-start.jpg`) ? `${base}-start.jpg` : null,
        endThumb: files.has(`${base}-end.jpg`) ? `${base}-end.jpg` : null,
      });
    }
  }
  segments.sort((a, b) => a.part - b.part);
  const full = files.has("full.mp4")
    ? { thumb: pickThumb(files, "part-0") }
    : null;
  return { full, segments };
}

export function animationFileUrl(
  film: string,
  name: string,
  file: string,
): string {
  return `/api/animation/${film}/${name}/${file}`;
}

export function filmAnimationFileUrl(film: string, file: string): string {
  return `/api/animation/${film}/${file}`;
}

export function blueprintImageUrl(
  film: string,
  relDir: string,
  file: string,
): string {
  return `/api/blueprint-image/${film}/${relDir}/${file}`;
}
