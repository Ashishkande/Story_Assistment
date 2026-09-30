import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { approveEpisode, editEpisode, getEpisode, listEpisodes, rejectEpisode } from "../api/episodes";
import { addFeedback } from "../api/memory";
import { reconcileStory } from "../api/stories";
import { apiError } from "../api/client";
import type { Episode, EpisodeSummary } from "../types";
import { useToast } from "../hooks/useToast";
import { EmptyState, ErrorState, Field, LoadingBlock, Modal, StatusBadge, buttonClass, ghostButton, inputClass } from "../components/ui";

export function EpisodesPage() {
  const { storyId = "" } = useParams();
  const { push } = useToast();
  const [items, setItems] = useState<EpisodeSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingEpisode, setLoadingEpisode] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"edit" | "reject" | "feedback" | null>(null);
  const [content, setContent] = useState("");
  const [notes, setNotes] = useState("");
  const [reason, setReason] = useState("");
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);

  function loadList(prefer?: number) {
    setLoadingList(true);
    setError("");
    listEpisodes(storyId)
      .then((rows) => {
        setItems(rows);
        const next = prefer ?? selected ?? rows.at(-1)?.episode_number ?? null;
        setSelected(next);
      })
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoadingList(false));
  }

  useEffect(() => {
    loadList();
    // story changes should reload the sidebar
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storyId]);

  useEffect(() => {
    if (!selected) {
      setEpisode(null);
      return;
    }
    setLoadingEpisode(true);
    getEpisode(storyId, selected)
      .then((row) => {
        setEpisode(row);
        setContent(row.content || "");
      })
      .catch((err) => push(apiError(err), "error"))
      .finally(() => setLoadingEpisode(false));
  }, [storyId, selected]);

  async function act(work: () => Promise<unknown>, success: string) {
    setBusy(true);
    try {
      await work();
      push(success);
      setMode(null);
      loadList(selected ?? undefined);
      if (selected) {
        const fresh = await getEpisode(storyId, selected);
        setEpisode(fresh);
        setContent(fresh.content || "");
      }
    } catch (err) {
      push(apiError(err), "error");
    } finally {
      setBusy(false);
    }
  }

  if (loadingList) return <LoadingBlock label="Loading episodes..." />;
  if (error) return <ErrorState message={error} onRetry={() => loadList()} />;
  if (items.length === 0) {
    return <EmptyState title="No episodes yet." body="Approve the plan, then generate the next episode from the header." />;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
      <aside className="max-h-[70vh] space-y-1 overflow-auto rounded-2xl border border-zinc-800 bg-zinc-900 p-2">
        {items.map((item) => (
          <button
            key={item.episode_number}
            className={`flex w-full items-center justify-between rounded-lg px-2 py-2 text-left text-sm ${
              selected === item.episode_number ? "bg-amber-400 text-zinc-950" : "hover:bg-zinc-800"
            }`}
            onClick={() => setSelected(item.episode_number)}
          >
            <span>Episode {item.episode_number}</span>
            {item.is_stale ? <span className="text-[10px] uppercase">Stale</span> : null}
          </button>
        ))}
      </aside>

      {loadingEpisode || !episode ? (
        <LoadingBlock label="Loading episode..." />
      ) : (
        <article className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase text-zinc-400">Episode {episode.episode_number}</p>
              <h3 className="font-display text-3xl">{episode.title || "Untitled episode"}</h3>
            </div>
            <StatusBadge status={episode.is_stale ? "stale" : episode.status} />
          </div>
          <dl className="mt-4 grid grid-cols-3 gap-3 text-sm">
            <div><dt className="text-zinc-400">Critic score</dt><dd>{episode.critic_score ?? "N/A"}</dd></div>
            <div><dt className="text-zinc-400">Word count</dt><dd>{episode.word_count ?? "—"}</dd></div>
            <div><dt className="text-zinc-400">Revisions</dt><dd>{episode.revision_count}</dd></div>
          </dl>
          {episode.is_stale ? <p className="mt-3 text-sm text-amber-200">Stale: {episode.stale_reason}</p> : null}
          <div className="prose-reading mt-6 max-w-2xl whitespace-pre-wrap font-display text-lg leading-8 text-zinc-100">
            {episode.content}
          </div>
          <div className="mt-6 grid gap-3 text-sm md:grid-cols-3">
            <div>
              <h4 className="text-zinc-400">Characters</h4>
              <p>{(episode.characters_present || []).join(", ") || "—"}</p>
            </div>
            <div>
              <h4 className="text-zinc-400">Threads opened</h4>
              <p>{(episode.threads_opened || []).join(", ") || "—"}</p>
            </div>
            <div>
              <h4 className="text-zinc-400">Threads resolved</h4>
              <p>{(episode.threads_resolved || []).join(", ") || "—"}</p>
            </div>
          </div>
          <section className="mt-6">
            <h4 className="text-sm text-zinc-400">Critic issues</h4>
            {(episode.critic_issues || []).length === 0 ? <p className="text-sm">None recorded.</p> : (
              <ul className="mt-2 space-y-2 text-sm">
                {episode.critic_issues.map((issue, index) => (
                  <li key={index} className="rounded-lg bg-zinc-950 px-3 py-2">
                    <span className="uppercase text-rose-200">{issue.severity || "note"}</span> {issue.type}: {issue.description}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <div className="mt-6 flex flex-wrap gap-2">
            <button className={buttonClass} disabled={busy} onClick={() => act(() => approveEpisode(storyId, episode.episode_number), "Episode approved.")}>Approve</button>
            <button className={ghostButton} onClick={() => setMode("edit")}>Edit</button>
            <button className={ghostButton} onClick={() => setMode("reject")}>Reject</button>
            <button className={ghostButton} onClick={() => setMode("feedback")}>Give Feedback</button>
            <button
              className={ghostButton}
              disabled={busy}
              onClick={() =>
                act(
                  () => reconcileStory(storyId, episode.episode_number),
                  "Later episodes marked stale. Generate next to rewrite them in order.",
                )
              }
            >
              Reconcile later episodes
            </button>
          </div>
        </article>
      )}

      {mode === "edit" && episode ? (
        <Modal title="Edit episode" onClose={() => setMode(null)}>
          <div className="space-y-3">
            <Field label="Episode content">
              <textarea className={`${inputClass} min-h-64 font-display`} value={content} onChange={(event) => setContent(event.target.value)} />
            </Field>
            <Field label="Edit notes">
              <input className={inputClass} value={notes} onChange={(event) => setNotes(event.target.value)} />
            </Field>
            <button
              className={buttonClass}
              disabled={busy}
              onClick={() => act(() => editEpisode(storyId, episode.episode_number, content, notes), "Episode saved.")}
            >
              Save & Approve
            </button>
          </div>
        </Modal>
      ) : null}

      {mode === "reject" && episode ? (
        <Modal title="Reject episode" onClose={() => setMode(null)}>
          <div className="space-y-3">
            <Field label="Rejection reason">
              <textarea className={`${inputClass} min-h-24`} value={reason} onChange={(event) => setReason(event.target.value)} />
            </Field>
            <button
              className={buttonClass}
              disabled={busy || !reason.trim()}
              onClick={() => act(() => rejectEpisode(storyId, episode.episode_number, reason.trim()), "Episode rejected.")}
            >
              Reject Episode
            </button>
          </div>
        </Modal>
      ) : null}

      {mode === "feedback" && episode ? (
        <Modal title="Persistent instruction" onClose={() => setMode(null)}>
          <div className="space-y-3">
            <Field label="Persistent instruction">
              <textarea className={`${inputClass} min-h-28`} value={instruction} onChange={(event) => setInstruction(event.target.value)} />
            </Field>
            <p className="text-xs text-zinc-400">This instruction will affect future episodes.</p>
            <button
              className={buttonClass}
              disabled={busy || instruction.trim().length < 5}
              onClick={() => act(() => addFeedback(storyId, episode.episode_number, instruction.trim()), "Instruction saved.")}
            >
              Save Instruction
            </button>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
