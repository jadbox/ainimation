export interface CLIRunOptions {
  url: string;
  body: Record<string, unknown>;
  command: string;
}

interface Elements {
  modal: HTMLDivElement;
  title: HTMLElement;
  state: HTMLElement;
  log: HTMLPreElement;
  copy: HTMLButtonElement;
  run: HTMLButtonElement;
  cancel: HTMLButtonElement;
  rerun: HTMLButtonElement;
  close: HTMLButtonElement;
  home: HTMLButtonElement;
}

type Phase = "pending" | "running" | "finished";

let els: Elements | null = null;
let aborter: AbortController | null = null;
let lastRun: CLIRunOptions | null = null;
let phase: Phase = "pending";

function copyText(text: string, button: HTMLButtonElement): void {
  const restore = () => {
    window.setTimeout(() => {
      button.textContent = original;
      button.classList.remove("bg-teal-shadow/20");
    }, 1200);
  };
  const original = button.textContent ?? "";
  button.textContent = "copied!";
  button.classList.add("bg-teal-shadow/20");
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
  } else {
    fallbackCopy(text);
  }
  restore();
}

function fallbackCopy(text: string): void {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  ta.remove();
}

function applyPhase(): void {
  if (!els) return;
  const pending = phase === "pending";
  const running = phase === "running";
  els.copy.classList.toggle("hidden", running);
  els.run.classList.toggle("hidden", !pending);
  els.cancel.classList.toggle("hidden", !running);
  els.rerun.classList.toggle("hidden", phase !== "finished");
  els.close.classList.toggle("hidden", running);
}

function openModal(): void {
  if (!els) return;
  els.modal.classList.remove("hidden");
  els.modal.classList.add("flex");
}

function closeModal(): void {
  if (!els) return;
  els.modal.classList.add("hidden");
  els.modal.classList.remove("flex");
}

function showPending(options: CLIRunOptions): void {
  if (!els) return;
  phase = "pending";
  els.title.textContent = options.command;
  els.state.textContent = "ready";
  els.log.textContent = `$ ${options.command}\n\nPress "Run command" to execute in the browser, or copy it to run in your terminal.`;
  applyPhase();
}

async function run(options: CLIRunOptions): Promise<void> {
  if (!els) return;
  phase = "running";
  els.log.textContent = "";
  els.state.textContent = "starting…";
  applyPhase();
  aborter = new AbortController();
  let succeeded = false;
  try {
    const res = await fetch(options.url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(options.body),
      signal: aborter.signal,
    });
    if (!res.ok || !res.body) {
      const detail = await res.text().catch(() => "");
      els.log.textContent += `\n[http ${res.status}] ${detail}\n`;
      els.state.textContent = "failed";
      return;
    }
    els.state.textContent = "running…";
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      els.log.textContent += decoder.decode(value, { stream: true });
      els.log.scrollTop = els.log.scrollHeight;
      const exitMatch = els.log.textContent.match(/\[exit:(\d+)\]\s*$/);
      if (exitMatch) succeeded = exitMatch[1] === "0";
    }
    els.state.textContent = succeeded ? "done" : "failed";
  } catch (err) {
    if ((err as Error).name === "AbortError") {
      els.state.textContent = "cancelled";
    } else {
      els.log.textContent += `\n[error] ${(err as Error).message}\n`;
      els.state.textContent = "failed";
    }
  } finally {
    phase = "finished";
    applyPhase();
    if (succeeded) {
      setTimeout(() => location.reload(), 600);
    }
  }
}

export function openCLITerminal(options: CLIRunOptions): void {
  if (!els) return;
  lastRun = options;
  showPending(options);
  openModal();
}

export function initCLITerminal(): void {
  const modal = document.getElementById("cli-terminal") as HTMLDivElement | null;
  const title = document.getElementById("cli-terminal-title");
  const state = document.getElementById("cli-terminal-state");
  const log = document.getElementById("cli-terminal-log") as HTMLPreElement | null;
  const copy = document.getElementById("cli-terminal-copy") as HTMLButtonElement | null;
  const runBtn = document.getElementById("cli-terminal-run") as HTMLButtonElement | null;
  const cancel = document.getElementById("cli-terminal-cancel") as HTMLButtonElement | null;
  const rerun = document.getElementById("cli-terminal-rerun") as HTMLButtonElement | null;
  const close = document.getElementById("cli-terminal-close") as HTMLButtonElement | null;
  const home = document.getElementById("cli-terminal-home") as HTMLButtonElement | null;
  if (
    !modal || !title || !state || !log || !copy || !runBtn ||
    !cancel || !rerun || !close || !home
  ) {
    return;
  }

  els = { modal, title, state, log, copy, run: runBtn, cancel, rerun, close, home };

  copy.addEventListener("click", () => {
    if (lastRun) copyText(lastRun.command, copy);
  });
  runBtn.addEventListener("click", () => {
    if (lastRun && phase !== "running") void run(lastRun);
  });
  cancel.addEventListener("click", () => aborter?.abort());
  rerun.addEventListener("click", () => {
    if (lastRun && phase !== "running") void run(lastRun);
  });
  close.addEventListener("click", closeModal);
  home.addEventListener("click", () => {
    aborter?.abort();
    location.href = "/";
  });
  modal.addEventListener("click", (event) => {
    if (event.target === modal && phase !== "running") closeModal();
  });
}
