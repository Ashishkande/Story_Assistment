import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { addFeedback, listFeedback } from "../api/memory";
import { apiError } from "../api/client";
import type { FeedbackItem } from "../types";
import { useToast } from "../hooks/useToast";
import { EmptyState, ErrorState, Field, LoadingBlock, StatusBadge, buttonClass, inputClass } from "../components/ui";

export function FeedbackPage() {
  const { storyId = "" } = useParams();
  const { push } = useToast();
  const [rows, setRows] = useState<FeedbackItem[]>([]);
  const [episode, setEpisode] = useState(1);
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    listFeedback(storyId)
      .then(setRows)
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(load, [storyId]);

  async function save() {
    setBusy(true);
    try {
      await addFeedback(storyId, episode, instruction.trim());
      setInstruction("");
      push("Instruction saved. It will affect later episodes.");
      load();
    } catch (err) {
      push(apiError(err), "error");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock label="Loading feedback..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <form className="space-y-3 rounded-2xl border border-zinc-800 bg-zinc-900 p-4" onSubmit={(event) => { event.preventDefault(); save(); }}>
        <h3 className="font-display text-2xl">Persistent instruction</h3>
        <Field label="After episode">
          <input className={inputClass} type="number" min={0} value={episode} onChange={(event) => setEpisode(Number(event.target.value))} />
        </Field>
        <Field label="Instruction">
          <textarea className={`${inputClass} min-h-32`} value={instruction} onChange={(event) => setInstruction(event.target.value)} />
        </Field>
        <p className="text-xs text-zinc-400">This instruction will affect future episodes.</p>
        <button className={buttonClass} disabled={busy || instruction.trim().length < 5} type="submit">Save Instruction</button>
      </form>
      <section className="space-y-3">
        {rows.length === 0 ? <EmptyState title="No instructions yet." body="Feedback stored here stays active for every episode after the one you choose." /> : null}
        {rows.map((row) => (
          <article key={row.id} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs text-zinc-400">After episode {row.episode ?? "—"}</p>
              <StatusBadge status={row.is_active ? "active" : row.action} />
            </div>
            <p className="mt-2 text-sm">{row.instruction || row.rejection_reason || row.action}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
