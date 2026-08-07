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
    adaptation: string;
    style: string;
    style_summary: string;
    camera_rules: string;
    hard_direction_rules: string[];
  };
  characters: Character[];
  scenes: SceneLocation[];
  story: StoryScene[];
}

function findProjectRoot(): string {
  if (process.env.ANIMATION_ROOT) return path.resolve(process.env.ANIMATION_ROOT);
  let dir = import.meta.dirname;
  for (let i = 0; i < 8; i++) {
    if (fs.existsSync(path.join(dir, "movie.yml"))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return path.resolve(import.meta.dirname, "..", "..", "..");
}

export const PROJECT_ROOT = findProjectRoot();

export const MOVIE_YML = path.join(PROJECT_ROOT, "movie.yml");
export const SCRIPTS_DIR = path.join(PROJECT_ROOT, "out", "scripts");
export const BLUEPRINT_DIR = path.join(PROJECT_ROOT, "out", "blueprint");
export const ANIMATIONS_DIR = path.join(PROJECT_ROOT, "out", "animations");

let cache: { mtimeMs: number; config: MovieConfig } | null = null;

export function loadMovie(): MovieConfig {
  const stat = fs.statSync(MOVIE_YML);
  if (cache && cache.mtimeMs === stat.mtimeMs) return cache.config;
  const config = loadYaml(fs.readFileSync(MOVIE_YML, "utf8")) as MovieConfig;
  cache = { mtimeMs: stat.mtimeMs, config };
  return config;
}

export function scriptPath(name: string, part: number): string {
  return path.join(SCRIPTS_DIR, `${name}_part${part}.md`);
}

export function scriptStatus(name: string): boolean[] {
  return [0, 1, 2].map((part) => fs.existsSync(scriptPath(name, part)));
}

export function readScript(name: string, part: number): string | null {
  const file = scriptPath(name, part);
  if (!fs.existsSync(file)) return null;
  return fs.readFileSync(file, "utf8");
}

export function animatorCommand(name: string): string {
  return `uv run animator --scene ${name}`;
}

export function scriptgenCommand(name: string, force = false): string {
  return `uv run scriptgen --name ${name}${force ? " --force" : ""}`;
}

export function isValidStoryName(name: string): boolean {
  return loadMovie().story.some((s) => s.name === name);
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function blueprintDir(subject: string): string {
  return path.join(BLUEPRINT_DIR, slugify(subject));
}

export function backgroundBlueprintDir(sceneSlug: string, bgKey: string): string {
  return path.join(BLUEPRINT_DIR, slugify(sceneSlug), slugify(bgKey));
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
  return { attempts, latest: attempts.length > 0 ? attempts[attempts.length - 1] : null, style };
}

function dirHasBlueprintImages(dir: string): boolean {
  const info = blueprintInfo(dir);
  return info.latest !== null || info.style !== null;
}

export function hasBlueprint(subject: string): boolean {
  const dir = blueprintDir(subject);
  if (!fs.existsSync(dir)) return false;
  if (dirHasBlueprintImages(dir)) return true;
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .some((e) => dirHasBlueprintImages(path.join(dir, e.name)));
}

export function isValidCharacter(name: string): boolean {
  return loadMovie().characters.some((c) => c.name === name);
}

export function isValidSceneSlug(slug: string): boolean {
  return loadMovie().scenes.some((s) => s.slug === slug);
}

export function blueprintCommand(target: { character?: string; scene?: string }): string {
  return target.character
    ? `uv run generate-blueprint --character "${target.character}"`
    : `uv run generate-blueprint --scene ${target.scene}`;
}

export function hasAnimation(name: string): boolean {
  return fs.existsSync(path.join(ANIMATIONS_DIR, name, "full.mp4"));
}
