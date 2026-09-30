import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listStories } from "../api/stories";
import { apiError } from "../api/client";
import type { Story } from "../types";
import { CreateStoryModal } from "../components/CreateStoryModal";
import { EmptyState, ErrorState, LoadingBlock, StatusBadge, buttonClass } from "../components/ui";

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString();
}

export function StoriesPage() {
  const [stories, setStories] = useState<Story[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  function load() {
    setLoading(true);
    setError("");
    listStories()
      .then(setStories)
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

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
            <div className="mt-4 flex flex-wrap gap-2 text-sm">
              <Link className="text-amber-300" to={`/stories/${story.id}`}>Open</Link>
              <Link to={`/stories/${story.id}/plan`}>Plan</Link>
              <Link to={`/stories/${story.id}/episodes`}>Generate</Link>
              <Link to={`/stories/${story.id}/memory`}>Memory</Link>
              <Link to={`/stories/${story.id}/logs`}>Logs</Link>
            </div>
          </article>
        ))}
      </div>
      {creating ? <CreateStoryModal onClose={() => { setCreating(false); load(); }} /> : null}
    </div>
  );
}
