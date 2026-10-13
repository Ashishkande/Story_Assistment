import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Trash2 } from "lucide-react";
import { deleteStory, getDashboard } from "../api/stories";
import { apiError } from "../api/client";
import type { DashboardData, Story } from "../types";
import { CreateStoryModal } from "../components/CreateStoryModal";
import { useToast } from "../hooks/useToast";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  Modal,
  StatusBadge,
  buttonClass,
  dangerButton,
  ghostButton,
} from "../components/ui";

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [storyToDelete, setStoryToDelete] = useState<Story | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { push } = useToast();

  function load() {
    setLoading(true);
    setError("");
    getDashboard()
      .then(setData)
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function confirmDeleteStory() {
    if (!storyToDelete) return;
    setDeleting(true);
    try {
      await deleteStory(storyToDelete.id);
      push("Story deleted successfully.");
      setStoryToDelete(null);
      load();
    } catch (err) {
      push(apiError(err), "error");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-amber-300">Dashboard</p>
          <h2 className="font-display text-4xl">The room is open.</h2>
        </div>
        <div className="flex gap-2">
          <button className={buttonClass} onClick={() => setCreating(true)}>Create Story</button>
          <Link className={ghostButton} to="/stories">View Stories</Link>
        </div>
      </header>

      {loading ? <LoadingBlock label="Loading dashboard..." /> : null}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {data && !loading ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ["Stories", data.total_stories],
              ["Generating", data.generating],
              ["Completed", data.completed],
              ["Episodes generated", data.episodes_generated],
            ].map(([label, value]) => (
              <article key={label} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
                <p className="text-xs uppercase tracking-wide text-zinc-400">{label}</p>
                <p className="font-display mt-2 text-3xl">{value}</p>
              </article>
            ))}
          </section>

          {data.total_stories === 0 ? (
            <EmptyState
              title="No stories yet."
              body="Create your first story from a one-line premise."
              action={<button className={buttonClass} onClick={() => setCreating(true)}>Create Story</button>}
            />
          ) : (
            <section className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
                <h3 className="mb-3 font-medium">Recent stories</h3>
                <ul className="space-y-3">
                  {data.recent_stories.map((story) => (
                    <li key={story.id} className="flex items-start justify-between gap-3 border-b border-zinc-800 pb-3 last:border-0">
                      <div>
                        <Link className="font-medium hover:text-amber-300" to={`/stories/${story.id}`}>
                          {story.title || "Untitled story"}
                        </Link>
                        <p className="text-sm text-zinc-400">{story.premise}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={story.status} />
                        <button
                          type="button"
                          title="Delete story"
                          onClick={() => setStoryToDelete(story)}
                          className="rounded p-1 text-zinc-500 transition hover:bg-rose-950/60 hover:text-rose-400"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
                <h3 className="mb-3 font-medium">Recent activity</h3>
                {data.recent_activity.length === 0 ? (
                  <p className="text-sm text-zinc-400">No agent runs yet.</p>
                ) : (
                  <ul className="space-y-2 text-sm">
                    {data.recent_activity.map((run) => (
                      <li key={run.id} className="flex justify-between gap-3">
                        <span>{run.agent} · {run.story_title || "Untitled"}</span>
                        <StatusBadge status={run.status} />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
          )}
        </>
      ) : null}
      {creating ? <CreateStoryModal onClose={() => { setCreating(false); load(); }} /> : null}

      {storyToDelete ? (
        <Modal title="Delete Story" onClose={() => !deleting && setStoryToDelete(null)}>
          <div className="space-y-4">
            <p className="text-sm text-zinc-300">
              Are you sure you want to delete <strong className="text-zinc-100">{storyToDelete.title || "this story"}</strong>?
            </p>
            <p className="rounded-lg border border-rose-900/50 bg-rose-950/30 p-3 text-xs text-rose-300">
              This will permanently delete the story and all associated data (episodes, plans, memory, and logs). This cannot be undone.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                className={ghostButton}
                disabled={deleting}
                onClick={() => setStoryToDelete(null)}
              >
                Cancel
              </button>
              <button
                className={dangerButton}
                disabled={deleting}
                onClick={confirmDeleteStory}
              >
                {deleting ? "Deleting..." : "Permanently Delete"}
              </button>
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
