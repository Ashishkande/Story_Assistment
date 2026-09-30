import type { ReactNode } from "react";

export function StatusBadge({ status }: { status: string }) {
  const key = status.toLowerCase();
  const tone =
    key === "approved" || key === "completed" || key === "success"
      ? "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30"
      : key === "rejected" || key === "failed"
        ? "bg-rose-500/15 text-rose-300 ring-rose-400/30"
        : key === "human_review" || key === "plan_pending_review"
          ? "bg-amber-500/15 text-amber-200 ring-amber-400/30"
          : key === "generating" || key === "planning" || key === "active" || key === "running"
            ? "bg-sky-500/15 text-sky-200 ring-sky-400/30"
            : "bg-zinc-500/15 text-zinc-300 ring-zinc-400/30";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${tone}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function ImportanceBadge({ importance }: { importance: string }) {
  const key = importance.toLowerCase();
  const tone =
    key === "critical"
      ? "bg-rose-500/20 text-rose-200"
      : key === "high"
        ? "bg-amber-500/20 text-amber-100"
        : key === "low"
          ? "bg-zinc-500/20 text-zinc-300"
          : "bg-sky-500/20 text-sky-100";
  return <span className={`rounded-full px-2 py-0.5 text-xs uppercase ${tone}`}>{importance}</span>;
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-zinc-700 px-6 py-16 text-center">
      <h2 className="font-display text-2xl text-zinc-100">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-zinc-400">{body}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-2xl border border-rose-500/30 bg-rose-950/40 px-6 py-10 text-center">
      <h2 className="font-display text-xl text-rose-100">Something went wrong.</h2>
      <p className="mt-2 text-sm text-rose-200/80">{message}</p>
      {onRetry ? (
        <button className="mt-4 rounded-lg bg-rose-100 px-3 py-1.5 text-sm font-medium text-rose-950" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="space-y-3" aria-busy="true">
      <p className="text-sm text-zinc-400">{label}</p>
      <div className="h-24 animate-pulse rounded-xl bg-zinc-800/80" />
      <div className="h-24 animate-pulse rounded-xl bg-zinc-800/60" />
    </div>
  );
}

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-xl overflow-auto rounded-2xl border border-zinc-700 bg-zinc-900 p-5 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-xl">{title}</h2>
          <button className="text-sm text-zinc-400" onClick={onClose}>Close</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-zinc-300">{label}</span>
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-amber-400";

export const buttonClass =
  "rounded-lg bg-amber-400 px-3 py-2 text-sm font-semibold text-zinc-950 disabled:cursor-not-allowed disabled:opacity-50";

export const ghostButton =
  "rounded-lg border border-zinc-700 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-800 disabled:opacity-50";
