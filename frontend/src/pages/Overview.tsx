import { Link, useOutletContext, useParams } from "react-router-dom";
import type { Story } from "../types";

export function OverviewPage() {
  const { storyId } = useParams();
  const { story } = useOutletContext<{ story: Story }>();
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {[
        ["Status", story.status.replaceAll("_", " ")],
        ["Tone", story.tone || "Not set"],
        ["Progress", `${story.current_episode} / ${story.total_planned || 200}`],
      ].map(([label, value]) => (
        <article key={label} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
          <p className="text-xs uppercase text-zinc-400">{label}</p>
          <p className="mt-2 text-lg">{value}</p>
        </article>
      ))}
      <article className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4 md:col-span-3">
        <h3 className="font-medium">Continue</h3>
        <p className="mt-1 text-sm text-zinc-400">
          Generate a plan, approve it, then review each episode before the next one is written.
        </p>
        <div className="mt-3 flex gap-4 text-sm text-amber-300">
          <Link to={`/stories/${storyId}/plan`}>View plan</Link>
          <Link to={`/stories/${storyId}/episodes`}>Review episodes</Link>
          <Link to={`/stories/${storyId}/memory`}>Open memory</Link>
        </div>
      </article>
    </div>
  );
}
