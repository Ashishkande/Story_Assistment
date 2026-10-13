import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Trash2 } from "lucide-react";
import { deleteStory, listStories } from "../api/stories";
import { apiError } from "../api/client";
import type { Story } from "../types";
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

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString();
}

export function StoriesPage() {
  const [stories, setStories] = useState<Story[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [storyToDelete, setStoryToDelete] = useState<Story | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { push } = useToast();

  function load() {
    setLoading(true);
    setError("");
    listStories()
      .then(setStories)
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function confirmDeleteStory() {
    if (!storyToDelete) return;
    setDeleting(true);
    try {
      await deleteStory(storyToDelete.id);
      setStories((prev) => prev.filter((s) => s.id !== storyToDelete.id));
      push("Story deleted successfully.");
      setStoryToDelete(null);
    } catch (err) {
      push(apiError(err), "error");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-5">
      <header className="flex items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-amber-300">Library</p>
          <h2 className="font-display text-4xl">Stories</h2>
        </div>
        <button className={buttonClass} onClick={() => setCreating(true)}>Create Story</button>
      </header>
      {loading ? <LoadingBlock label="Loading stories..." /> : null}
      {error ? <ErrorState message={error} onRetry={load} /> : null}
      {!loading && !error && stories.length === 0 ? (
        <EmptyState title="No stories yet." body="Create your first story." action={<button className={buttonClass} onClick={() => setCreating(true)}>Create Story</button>} />
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        {stories.map((story) => (
          <article key={story.id} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-display text-2xl">{story.title || "Untitled"}</h3>
              <StatusBadge status={story.status} />
            </div>
            <p className="mt-2 text-sm text-zinc-400">{story.premise}</p>
            <dl className="mt-4 grid grid-cols-3 gap-2 text-xs text-zinc-400">
              <div><dt>Episode</dt><dd className="text-sm text-zinc-100">{story.current_episode} / {story.total_planned || 200}</dd></div>
              <div><dt>Created</dt><dd className="text-sm text-zinc-100">{formatDate(story.created_at)}</dd></div>
              <div><dt>Status</dt><dd className="text-sm text-zinc-100">{story.status.replaceAll("_", " ")}</dd></div>
            </dl>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-zinc-800/80 pt-3 text-sm">
              <div className="flex flex-wrap gap-3">
                <Link className="font-medium text-amber-300 hover:underline" to={`/stories/${story.id}`}>Open</Link>
                <Link className="text-zinc-300 hover:text-white" to={`/stories/${story.id}/plan`}>Plan</Link>
                <Link className="text-zinc-300 hover:text-white" to={`/stories/${story.id}/episodes`}>Generate</Link>
                <Link className="text-zinc-300 hover:text-white" to={`/stories/${story.id}/memory`}>Memory</Link>
                <Link className="text-zinc-300 hover:text-white" to={`/stories/${story.id}/logs`}>Logs</Link>
              </div>
              <button
                type="button"
                title="Delete story"
                onClick={() => setStoryToDelete(story)}
                className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-400 transition hover:bg-rose-950/50 hover:text-rose-300"
              >
                <Trash2 size={13} />
                Delete
              </button>
            </div>
          </article>
        ))}
      </div>
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
