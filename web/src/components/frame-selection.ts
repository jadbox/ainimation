/**
 * frame-selection.ts
 * 
 * Client-side state manager and event coordinator for scene frame selections,
 * localStorage persistence, video/proposal deletions, and video generation triggers.
 */
import { openCLITerminal } from "./cli-terminal";
import { confirmModal } from "./confirm-modal";

export interface PartFrameState {
  frameStart: string;
  frameEnd: string;
}

// In-memory state cache mapped by part index: part -> { frameStart, frameEnd }
const partFrameState = new Map<number, PartFrameState>();

/**
 * Return the unique localStorage key scoped to the film, scene, and part.
 */
export function getFrameStorageKey(film: string, scene: string, part: number): string {
  return `selected_reference_frames:${film}:${scene}:${part}`;
}

/**
 * Load the saved frame state from localStorage for a given part.
 */
export function loadSavedFrameState(
  film: string,
  scene: string,
  part: number,
): PartFrameState {
  try {
    const raw = localStorage.getItem(getFrameStorageKey(film, scene, part));
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        frameStart: typeof parsed?.frameStart === "string" ? parsed.frameStart : "",
        frameEnd: typeof parsed?.frameEnd === "string" ? parsed.frameEnd : "",
      };
    }
  } catch (e) {
    console.warn("Failed to load saved frame state from localStorage", e);
  }
  return { frameStart: "", frameEnd: "" };
}

/**
 * Save the frame state to localStorage for a given part (or remove if empty).
 */
export function saveFrameState(
  film: string,
  scene: string,
  part: number,
  state: PartFrameState,
): void {
  try {
    const key = getFrameStorageKey(film, scene, part);
    if (!state.frameStart && !state.frameEnd) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, JSON.stringify(state));
    }
  } catch (e) {
    console.warn("Failed to save frame state to localStorage", e);
  }
}

/**
 * Retrieve the active in-memory frame state for a given part.
 */
export function getPartFrameState(part: number): PartFrameState {
  return partFrameState.get(part) ?? { frameStart: "", frameEnd: "" };
}

/**
 * Update the visual selection state styling for an individual frame tile.
 */
export function updateTileUI(tile: HTMLElement, isSelected: boolean): void {
  if (isSelected) {
    tile.classList.add(
      "selected",
      "border-2",
      "border-emerald-500",
      "bg-emerald-950/20",
      "ring-2",
      "ring-emerald-500/40",
      "text-emerald-300",
    );
    tile.classList.remove("border-line", "bg-panel/70");
    const badge = tile.querySelector(".selected-badge");
    if (badge) badge.classList.remove("hidden");
    const btn = tile.querySelector<HTMLButtonElement>("[data-toggle-selection]");
    if (btn) btn.textContent = "Deselect";
  } else {
    tile.classList.remove(
      "selected",
      "border-2",
      "border-emerald-500",
      "bg-emerald-950/20",
      "ring-2",
      "ring-emerald-500/40",
      "text-emerald-300",
    );
    tile.classList.add("border", "border-line", "bg-panel/70");
    const badge = tile.querySelector(".selected-badge");
    if (badge) badge.classList.add("hidden");
    const btn = tile.querySelector<HTMLButtonElement>("[data-toggle-selection]");
    if (btn) btn.textContent = "Select frame";
  }
}

/**
 * Toggle the selection of a tile within its frame selector group,
 * update the state map, and persist to localStorage.
 */
export function toggleTileSelection(
  container: HTMLElement,
  film: string,
  scene: string,
  part: number,
  kind: "start" | "end",
  value: string,
): boolean {
  const parentSelector = container.closest<HTMLElement>("[data-frame-selector]");
  if (!parentSelector) return false;

  const allTiles = parentSelector.querySelectorAll<HTMLElement>("[data-tile-container]");
  const isSelected = container.classList.contains("selected");
  const state = partFrameState.get(part) || { frameStart: "", frameEnd: "" };

  // Deselect all tiles in this frame selector group
  allTiles.forEach((t) => updateTileUI(t, false));

  let nowSelected = false;
  if (isSelected) {
    if (kind === "start") state.frameStart = "";
    else state.frameEnd = "";
  } else {
    updateTileUI(container, true);
    if (kind === "start") state.frameStart = value;
    else state.frameEnd = value;
    nowSelected = true;
  }

  partFrameState.set(part, state);
  saveFrameState(film, scene, part, state);
  return nowSelected;
}

/**
 * Initialize all frame selector groups on the page with their saved localStorage selections.
 */
export function initFrameSelectors(film: string, scene: string): void {
  document.querySelectorAll<HTMLElement>("[data-frame-selector]").forEach((selectorContainer) => {
    const part = Number(selectorContainer.dataset.part);
    const kind = selectorContainer.dataset.frameSelector as "start" | "end";

    if (!partFrameState.has(part)) {
      partFrameState.set(part, loadSavedFrameState(film, scene, part));
    }

    const state = partFrameState.get(part)!;
    const targetVal = kind === "start" ? state.frameStart : state.frameEnd;
    let targetFound = false;

    const tiles = selectorContainer.querySelectorAll<HTMLElement>("[data-tile-container]");
    tiles.forEach((tile) => {
      const val = tile.dataset.value ?? "";
      if (targetVal && val === targetVal) {
        updateTileUI(tile, true);
        targetFound = true;
      }

      const toggleBtn = tile.querySelector<HTMLButtonElement>("[data-toggle-selection]");
      toggleBtn?.addEventListener("click", () => {
        toggleTileSelection(tile, film, scene, part, kind, val);
      });
    });

    // Clean up stale reference if the selected file was deleted
    if (targetVal && !targetFound) {
      if (kind === "start") state.frameStart = "";
      else state.frameEnd = "";
      saveFrameState(film, scene, part, state);
    }
  });
}

/**
 * Handle confirmation and deletion for keyframe proposals.
 */
export async function performDeleteProposal(
  film: string,
  name: string,
  part: number,
  kind: "start" | "end",
  filename?: string,
): Promise<void> {
  const confirmed = await confirmModal({
    title: "Delete Keyframe Proposal",
    message: filename
      ? `Are you sure you want to delete proposal "${filename}"?`
      : `Are you sure you want to delete the ${kind} proposal image and prompt for Part ${part}?`,
    details: "This will permanently remove the proposal image, its prompt file, and its execution metadata.",
    confirmLabel: "Delete Proposal",
    variant: "danger",
  });
  if (!confirmed) {
    return;
  }
  try {
    const res = await fetch("/api/delete-proposal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ film, name, part, kind, filename }),
    });
    if (res.ok) {
      const state = partFrameState.get(part);
      if (state) {
        if (kind === "start" && (filename ? state.frameStart.includes(filename) : true)) {
          state.frameStart = "";
        }
        if (kind === "end" && (filename ? state.frameEnd.includes(filename) : true)) {
          state.frameEnd = "";
        }
        saveFrameState(film, name, part, state);
      }
      location.reload();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(`Failed to delete proposal: ${err.error || res.statusText}`);
    }
  } catch (err) {
    alert(`Failed to delete proposal: ${(err as Error).message}`);
  }
}

/**
 * Handle confirmation and deletion for rendered video clips.
 */
export async function performDeleteVideo(
  film: string,
  name: string,
  part: number,
  filename?: string,
): Promise<void> {
  const confirmed = await confirmModal({
    title: "Delete Generated Video",
    message: filename
      ? `Are you sure you want to delete "${filename}"?`
      : `Are you sure you want to delete all video clips for Part ${part}?`,
    details: "This will remove the video clip, extracted start/end frame thumbnails, prompt metadata, and execution logs.",
    confirmLabel: "Delete Video",
    variant: "danger",
  });
  if (!confirmed) {
    return;
  }
  try {
    const res = await fetch("/api/delete-video", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ film, name, part, filename }),
    });
    if (res.ok) {
      location.reload();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(`Failed to delete video: ${err.error || res.statusText}`);
    }
  } catch (err) {
    alert(`Failed to delete video: ${(err as Error).message}`);
  }
}

/**
 * Initialize proposal and video deletion button event listeners.
 */
export function initDeleteHandlers(): void {
  document.querySelectorAll<HTMLButtonElement>("[data-delete-proposal]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const film = btn.dataset.film!;
      const name = btn.dataset.name!;
      const part = Number(btn.dataset.part);
      const kind = btn.dataset.kind as "start" | "end";
      const filename = btn.dataset.filename;
      void performDeleteProposal(film, name, part, kind, filename);
    });
  });

  document.querySelectorAll<HTMLButtonElement>("[data-delete-video]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const film = btn.dataset.film!;
      const name = btn.dataset.name!;
      const part = Number(btn.dataset.part);
      const filename = btn.dataset.filename;
      void performDeleteVideo(film, name, part, filename);
    });
  });
}

/**
 * Default duration in seconds for video generation.
 */
export const DEFAULT_VIDEO_DURATION = 5;

/**
 * Return the unique localStorage key for duration scoped to the film, scene, and part.
 */
export function getDurationStorageKey(film: string, scene: string, part: number): string {
  return `selected_video_duration:${film}:${scene}:${part}`;
}

/**
 * Load the saved duration from localStorage for a given part.
 */
export function loadSavedDuration(
  film: string,
  scene: string,
  part: number,
  fallback = DEFAULT_VIDEO_DURATION,
): number {
  try {
    const raw = localStorage.getItem(getDurationStorageKey(film, scene, part));
    if (raw) {
      const parsed = parseInt(raw, 10);
      if (!Number.isNaN(parsed) && parsed >= 1 && parsed <= 15) {
        return parsed;
      }
    }
  } catch (e) {
    console.warn("Failed to load saved duration from localStorage", e);
  }
  return fallback;
}

/**
 * Save the duration to localStorage for a given part.
 */
export function saveDuration(
  film: string,
  scene: string,
  part: number,
  duration: number,
): void {
  try {
    const key = getDurationStorageKey(film, scene, part);
    localStorage.setItem(key, String(duration));
  } catch (e) {
    console.warn("Failed to save duration to localStorage", e);
  }
}

/**
 * Initialize duration selectors for all parts from saved localStorage values.
 */
export function initDurationSelectors(film: string, scene: string): void {
  document.querySelectorAll<HTMLSelectElement>("[data-duration-select]").forEach((select) => {
    const container = select.closest<HTMLElement>("[data-generate-details]");
    const partAttr = container?.dataset.part ?? select.dataset.part;
    if (partAttr === undefined) return;
    const part = Number(partAttr);
    if (Number.isNaN(part)) return;

    const savedDuration = loadSavedDuration(film, scene, part);
    select.value = String(savedDuration);

    select.addEventListener("change", () => {
      const val = parseInt(select.value, 10);
      if (!Number.isNaN(val) && val >= 1 && val <= 15) {
        saveDuration(film, scene, part, val);
      }
    });
  });
}

/**
 * Default model selection ("provider:model" spec).
 */
export const DEFAULT_VIDEO_MODEL_SELECTION = "minimax:MiniMax-H3";

/**
 * Return the unique localStorage key for the model selection scoped to the film, scene, and part.
 */
export function getModelStorageKey(film: string, scene: string, part: number): string {
  return `selected_video_model:${film}:${scene}:${part}`;
}

/**
 * Load the saved model selection from localStorage for a given part.
 */
export function loadSavedModel(
  film: string,
  scene: string,
  part: number,
  fallback = DEFAULT_VIDEO_MODEL_SELECTION,
): string {
  try {
    const raw = localStorage.getItem(getModelStorageKey(film, scene, part));
    if (raw && raw.includes(":")) {
      return raw;
    }
  } catch (e) {
    console.warn("Failed to load saved model from localStorage", e);
  }
  return fallback;
}

/**
 * Save the model selection to localStorage for a given part.
 */
export function saveModel(
  film: string,
  scene: string,
  part: number,
  selection: string,
): void {
  try {
    const key = getModelStorageKey(film, scene, part);
    localStorage.setItem(key, selection);
  } catch (e) {
    console.warn("Failed to save model to localStorage", e);
  }
}

/**
 * Initialize model selectors for all parts from saved localStorage values.
 */
export function initModelSelectors(film: string, scene: string): void {
  document.querySelectorAll<HTMLSelectElement>("[data-model-select]").forEach((select) => {
    const container = select.closest<HTMLElement>("[data-generate-details]");
    const partAttr = container?.dataset.part ?? select.dataset.part;
    if (partAttr === undefined) return;
    const part = Number(partAttr);
    if (Number.isNaN(part)) return;

    const savedModel = loadSavedModel(film, scene, part);
    if (select.querySelector(`option[value="${CSS.escape(savedModel)}"]`)) {
      select.value = savedModel;
    }

    select.addEventListener("change", () => {
      if (select.value.includes(":")) {
        saveModel(film, scene, part, select.value);
      }
    });
  });
}

/**
 * Initialize GENERATE video buttons per scene part with active frame selections, duration, and model.
 */
export function initGeneratePartHandlers(): void {
  document.querySelectorAll<HTMLButtonElement>("[data-generate-part]").forEach((button) => {
    button.addEventListener("click", () => {
      const film = button.dataset.film!;
      const name = button.dataset.name!;
      const part = Number(button.dataset.part);
      const state = getPartFrameState(part);

      const durationSelect = button
        .closest("[data-generate-details]")
        ?.querySelector<HTMLSelectElement>("[data-duration-select]");
      const duration = durationSelect
        ? parseInt(durationSelect.value, 10) || loadSavedDuration(film, name, part)
        : loadSavedDuration(film, name, part);

      saveDuration(film, name, part, duration);

      const modelSelect = button
        .closest("[data-generate-details]")
        ?.querySelector<HTMLSelectElement>("[data-model-select]");
      const model = modelSelect?.value || loadSavedModel(film, name, part);
      saveModel(film, name, part, model);

      // Close the dropdown popup
      const details = button.closest<HTMLDetailsElement>("details");
      if (details) {
        details.removeAttribute("open");
      }

      const command = [
        `uv run animator --film ${film} --scene ${name} --parts ${part} --duration ${duration}`,
        model ? `--model ${model}` : "",
        state.frameStart ? `--frame_start ${state.frameStart}` : "",
        state.frameEnd ? `--frame_end ${state.frameEnd}` : "",
      ]
        .filter(Boolean)
        .join(" ");

      openCLITerminal({
        url: "/api/animator",
        body: {
          film,
          name,
          parts: part,
          duration,
          model,
          frameStart: state.frameStart,
          frameEnd: state.frameEnd,
        },
        command,
      });
    });
  });

  // Close details dropdown when clicking outside
  document.addEventListener("click", (event) => {
    const target = event.target as HTMLElement;
    if (!target.closest("[data-generate-details]")) {
      document.querySelectorAll<HTMLDetailsElement>("[data-generate-details][open]").forEach((el) => {
        el.removeAttribute("open");
      });
    }
  });
}
