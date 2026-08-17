export interface ConfirmModalOptions {
  title?: string;
  message: string;
  details?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "info" | "primary";
}

type Resolver = (confirmed: boolean) => void;

interface Elements {
  modal: HTMLDivElement;
  title: HTMLElement;
  message: HTMLElement;
  details: HTMLElement;
  iconContainer: HTMLElement;
  confirmBtn: HTMLButtonElement;
  cancelBtn: HTMLButtonElement;
  closeBtn: HTMLButtonElement;
}

let els: Elements | null = null;
let currentResolver: Resolver | null = null;

const ICONS = {
  danger: `<svg class="h-6 w-6 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>`,
  warning: `<svg class="h-6 w-6 text-amber-key" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>`,
  info: `<svg class="h-6 w-6 text-teal-shadow" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>`,
  primary: `<svg class="h-6 w-6 text-teal-shadow" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>`,
};

const BUTTON_CLASSES = {
  danger: "bg-rose-600/20 text-rose-300 ring-rose-500/50 hover:bg-rose-600/30 focus-visible:ring-rose-400",
  warning: "bg-amber-key/20 text-amber-soft ring-amber-key/40 hover:bg-amber-key/30 focus-visible:ring-amber-300",
  info: "bg-teal-shadow/20 text-teal-shadow ring-teal-shadow/40 hover:bg-teal-shadow/30 focus-visible:ring-teal-300",
  primary: "bg-teal-shadow/20 text-teal-shadow ring-teal-shadow/40 hover:bg-teal-shadow/30 focus-visible:ring-teal-300",
};

const ICON_BG_CLASSES = {
  danger: "bg-rose-500/10 ring-rose-500/20",
  warning: "bg-amber-key/10 ring-amber-key/20",
  info: "bg-teal-shadow/10 ring-teal-shadow/20",
  primary: "bg-teal-shadow/10 ring-teal-shadow/20",
};

function close(confirmed: boolean): void {
  if (!els) return;
  els.modal.classList.add("hidden");
  els.modal.classList.remove("flex");
  if (currentResolver) {
    const resolve = currentResolver;
    currentResolver = null;
    resolve(confirmed);
  }
}

function showModal(options: ConfirmModalOptions): void {
  if (!els) return;
  const variant = options.variant ?? "danger";

  els.title.textContent = options.title ?? "Are you sure?";
  els.message.textContent = options.message;

  if (options.details) {
    els.details.textContent = options.details;
    els.details.classList.remove("hidden");
  } else {
    els.details.textContent = "";
    els.details.classList.add("hidden");
  }

  els.iconContainer.innerHTML = ICONS[variant] ?? ICONS.danger;
  els.iconContainer.className = `flex h-12 w-12 shrink-0 items-center justify-center rounded-full ring-1 ${
    ICON_BG_CLASSES[variant] ?? ICON_BG_CLASSES.danger
  }`;

  els.confirmBtn.textContent = options.confirmLabel ?? "Confirm";
  els.cancelBtn.textContent = options.cancelLabel ?? "Cancel";

  // Reset button classes
  els.confirmBtn.className = `rounded-md px-4 py-2 text-xs font-semibold ring-1 transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 ${
    BUTTON_CLASSES[variant] ?? BUTTON_CLASSES.danger
  }`;

  els.modal.classList.remove("hidden");
  els.modal.classList.add("flex");

  // Focus cancel button by default to avoid accidental destructive confirmation
  els.cancelBtn.focus();
}

export function confirmModal(options: ConfirmModalOptions): Promise<boolean> {
  if (!els) {
    initConfirmModal();
  }
  if (!els) {
    return Promise.resolve(window.confirm(options.message));
  }

  if (currentResolver) {
    currentResolver(false);
    currentResolver = null;
  }

  return new Promise<boolean>((resolve) => {
    currentResolver = resolve;
    showModal(options);
  });
}

export function initConfirmModal(): void {
  const modal = document.getElementById("confirm-modal") as HTMLDivElement | null;
  const title = document.getElementById("confirm-modal-title");
  const message = document.getElementById("confirm-modal-message");
  const details = document.getElementById("confirm-modal-details");
  const iconContainer = document.getElementById("confirm-modal-icon");
  const confirmBtn = document.getElementById("confirm-modal-confirm-btn") as HTMLButtonElement | null;
  const cancelBtn = document.getElementById("confirm-modal-cancel-btn") as HTMLButtonElement | null;
  const closeBtn = document.getElementById("confirm-modal-close-x") as HTMLButtonElement | null;

  if (
    !modal || !title || !message || !details ||
    !iconContainer || !confirmBtn || !cancelBtn || !closeBtn
  ) {
    return;
  }

  els = { modal, title, message, details, iconContainer, confirmBtn, cancelBtn, closeBtn };

  confirmBtn.addEventListener("click", (e) => {
    e.preventDefault();
    close(true);
  });

  cancelBtn.addEventListener("click", (e) => {
    e.preventDefault();
    close(false);
  });

  closeBtn.addEventListener("click", (e) => {
    e.preventDefault();
    close(false);
  });

  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      close(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (els && !els.modal.classList.contains("hidden")) {
      if (event.key === "Escape") {
        event.preventDefault();
        close(false);
      }
    }
  });
}
