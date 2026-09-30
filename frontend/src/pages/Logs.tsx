import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getLogs } from "../api/logs";
import { apiError } from "../api/client";
import type { LogResponse } from "../types";
import { EmptyState, ErrorState, LoadingBlock, StatusBadge } from "../components/ui";

export function LogsPage() {
  const { storyId = "" } = useParams();
  const [data, setData] = useState<LogResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    getLogs(storyId)
      .then(setData)
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(load, [storyId]);

  if (loading) return <LoadingBlock label="Loading logs..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data || data.runs.length === 0) return <EmptyState title="No logs yet." body="Agent runs appear here after planning or episode generation." />;

  const cards = [
    ["Total cost", `$${data.summary.total_cost.toFixed(4)}`],
    ["Total tokens", data.summary.total_tokens.toLocaleString()],
    ["Total runs", String(data.summary.total_runs)],
    ["Average latency", `${data.summary.average_latency_ms} ms`],
  ];

  return (
    <div className="space-y-4">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(([label, value]) => (
          <article key={label} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
            <p className="text-xs uppercase text-zinc-400">{label}</p>
            <p className="font-display mt-1 text-2xl">{value}</p>
          </article>
        ))}
      </section>
      <div className="overflow-auto rounded-2xl border border-zinc-800">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-zinc-900 text-zinc-400">
            <tr>
              {["Episode", "Agent", "Status", "Input", "Output", "Cost", "Latency", "Retries"].map((heading) => (
                <th key={heading} className="px-3 py-2 font-medium">{heading}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.runs.map((run) => (
              <tr key={run.id} className="border-t border-zinc-800">
                <td className="px-3 py-2">{run.episode_number ?? "—"}</td>
                <td className="px-3 py-2">{run.agent}</td>
                <td className="px-3 py-2"><StatusBadge status={run.status} /></td>
                <td className="px-3 py-2">{run.input_tokens ?? 0}</td>
                <td className="px-3 py-2">{run.output_tokens ?? 0}</td>
                <td className="px-3 py-2">${(run.cost ?? 0).toFixed(4)}</td>
                <td className="px-3 py-2">{run.latency_ms ?? "—"}</td>
                <td className="px-3 py-2">{run.retry_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
