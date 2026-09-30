import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { getStory, resumeStory } from "../api/stories";
import { apiError } from "../api/client";
import { startOperation, waitForOperation } from "../api/logs";
import type { Story } from "../types";
import { useToast } from "../hooks/useToast";
import { ErrorState, LoadingBlock, StatusBadge, buttonClass, ghostButton } from "../components/ui";

const tabs = [
  ["", "Overview"],
  ["plan", "Plan"],
  ["episodes", "Episodes"],
  ["memory", "Memory"],
  ["feedback", "Feedback"],
  ["logs", "Logs"],
] as const;

export function StoryLayout() {
  const { storyId = "" } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();
  const [story, setStory] = useState<Story | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState("");
  const [jobKind, setJobKind] = useState<"plan" | "episode" | null>(null);

  function load() {
    setLoading(true);
    getStory(storyId)
      .then(setStory)
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(load, [storyId]);

  async function run(type: "plan" | "episode", message: string) {
    setJobKind(type);
    setWorking(message);
    try {
      const job = await startOperation({ type, story_id: storyId });
      const done = await waitForOperation(job.id, (update) => setWorking(update.message || message));
      if (done.status === "failed") throw new Error(done.error || "Generation failed");
      push(type === "plan" ? "Plan generated." : "Episode ready for review.");
      load();
      navigate(type === "plan" ? `/stories/${storyId}/plan` : `/stories/${storyId}/episodes`);
    } catch (err) {
      push(apiError(err), "error");
    } finally {
      setWorking("");
      setJobKind(null);
    }
  }

  async function resume() {
    try {
      const point = await resumeStory(storyId);
      push(`Next episode is ${point.next_episode}. Last approved: ${point.last_approved_episode}.`);
      navigate(`/stories/${storyId}/episodes`);
    } catch (err) {
      push(apiError(err), "error");
    }
  }

  if (loading) return <LoadingBlock label="Loading story..." />;
  if (error || !story) return <ErrorState message={error || "Story not found"} onRetry={load} />;

  return (
    <div className="space-y-5">
      <header className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-amber-300">{story.genre || "Serial"}</p>
            <h2 className="font-display text-4xl">{story.title || "Untitled story"}</h2>
            <p className="mt-2 max-w-3xl text-sm text-zinc-400">{story.premise}</p>
          </div>
          <StatusBadge status={story.status} />
        </div>
        <p className="mt-4 text-sm text-zinc-300">
          Episode {story.current_episode} / {story.total_planned || 200}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button className={buttonClass} disabled={!!working} onClick={() => run("episode", "Generating episode...")}>
            {jobKind === "episode" ? working : "Generate Next Episode"}
          </button>
          <button className={ghostButton} disabled={!!working} onClick={resume}>Resume</button>
          <button className={ghostButton} disabled={!!working} onClick={() => run("plan", "Generating 200-episode plan...")}>
            {jobKind === "plan" ? working : "Generate Plan"}
          </button>
        </div>
        {working ? <p className="mt-3 text-sm text-amber-200">Agent is working... {working}</p> : null}
      </header>
      <nav className="flex flex-wrap gap-2">
        {tabs.map(([path, label]) => (
          <NavLink
            key={label}
            end={path === ""}
            to={path ? `/stories/${storyId}/${path}` : `/stories/${storyId}`}
            className={({ isActive }) =>
              `rounded-full px-3 py-1 text-sm ${isActive ? "bg-zinc-100 text-zinc-950" : "bg-zinc-800 text-zinc-300"}`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet context={{ story, reloadStory: load }} />
    </div>
  );
}
