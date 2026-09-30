import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { approvePlan, getPlan } from "../api/plans";
import { apiError } from "../api/client";
import type { Arc, Plan } from "../types";
import { useToast } from "../hooks/useToast";
import { EmptyState, ErrorState, LoadingBlock, buttonClass } from "../components/ui";

function arcsOf(plan: Plan): Arc[] {
  return Object.values(plan.arc_structure || {}).sort((a, b) => a.arc_number - b.arc_number);
}

export function PlanPage() {
  const { storyId = "" } = useParams();
  const { push } = useToast();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [arcFilter, setArcFilter] = useState<number | "all">("all");
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    setError("");
    setMissing(false);
    getPlan(storyId)
      .then(setPlan)
      .catch((err) => {
        const message = apiError(err);
        if (message.toLowerCase().includes("not found")) setMissing(true);
        else setError(message);
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, [storyId]);

  const arcs = plan ? arcsOf(plan) : [];
  const episodes = useMemo(() => {
    if (!plan) return [];
    return plan.episode_plans.filter((episode) => arcFilter === "all" || episode.arc_number === arcFilter);
  }, [plan, arcFilter]);

  async function approve() {
    setBusy(true);
    try {
      await approvePlan(storyId);
      push("Plan approved.");
      load();
    } catch (err) {
      push(apiError(err), "error");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock label="Loading plan..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (missing || !plan) {
    return <EmptyState title="No plan yet." body="Generate the 200-episode plan from the story header. This can take a few minutes." />;
  }

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-2xl">Plan overview</h3>
            <p className="text-sm text-zinc-400">Version {plan.version}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`rounded-full px-3 py-1 text-xs ${plan.approved ? "bg-emerald-500/20 text-emerald-200" : "bg-amber-500/20 text-amber-100"}`}>
              {plan.approved ? "Approved" : "Draft"}
            </span>
            <button className={buttonClass} disabled={busy || plan.approved} onClick={approve}>
              {plan.approved ? "Approved" : busy ? "Approving..." : "Approve Plan"}
            </button>
          </div>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div>
            <h4 className="text-sm text-zinc-400">World rules</h4>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{(plan.world_rules || []).map((rule) => <li key={rule}>{rule}</li>)}</ul>
          </div>
          <div>
            <h4 className="text-sm text-zinc-400">Major turning points</h4>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{(plan.major_turning_points || []).map((point) => <li key={point}>{point}</li>)}</ul>
          </div>
        </div>
      </section>

      <section>
        <h3 className="mb-3 font-medium">Story arcs</h3>
        <div className="grid gap-3 md:grid-cols-2">
          {arcs.map((arc) => (
            <article key={arc.arc_number} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
              <p className="text-xs text-zinc-400">Arc {arc.arc_number}</p>
              <h4 className="font-display text-xl">{arc.title}</h4>
              <p className="text-xs text-zinc-500">Episodes {arc.episode_start}–{arc.episode_end}</p>
              <p className="mt-2 text-sm text-zinc-300">{arc.summary}</p>
            </article>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium">Episode plans</h3>
          <select
            className="rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
            value={arcFilter}
            onChange={(event) => setArcFilter(event.target.value === "all" ? "all" : Number(event.target.value))}
          >
            <option value="all">All arcs</option>
            {arcs.map((arc) => <option key={arc.arc_number} value={arc.arc_number}>Arc {arc.arc_number}</option>)}
          </select>
        </div>
        <div className="overflow-auto rounded-2xl border border-zinc-800">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="bg-zinc-900 text-zinc-400">
              <tr>
                <th className="px-3 py-2">#</th>
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Summary</th>
                <th className="px-3 py-2">Hook</th>
              </tr>
            </thead>
            <tbody>
              {episodes.map((episode) => (
                <tr key={episode.episode_number} className="border-t border-zinc-800">
                  <td className="px-3 py-2">{episode.episode_number}</td>
                  <td className="px-3 py-2">{episode.title}</td>
                  <td className="px-3 py-2 text-zinc-300">{episode.summary}</td>
                  <td className="px-3 py-2 text-zinc-400">{episode.planned_hook}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
