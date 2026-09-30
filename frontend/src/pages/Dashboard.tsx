import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getDashboard } from "../api/stories";
import { apiError } from "../api/client";
import type { DashboardData } from "../types";
import { CreateStoryModal } from "../components/CreateStoryModal";
import { EmptyState, ErrorState, LoadingBlock, StatusBadge, buttonClass, ghostButton } from "../components/ui";

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  function load() {
    setLoading(true);
    setError("");
    getDashboard()
      .then(setData)
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

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
                      <StatusBadge status={story.status} />
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
      {creating ? <CreateStoryModal onClose={() => setCreating(false)} /> : null}
    </div>
  );
}
