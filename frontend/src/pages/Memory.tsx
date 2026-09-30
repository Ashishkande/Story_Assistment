import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getMemory } from "../api/memory";
import { apiError } from "../api/client";
import type { Memory } from "../types";
import { EmptyState, ErrorState, ImportanceBadge, LoadingBlock } from "../components/ui";

export function MemoryPage() {
  const { storyId = "" } = useParams();
  const [memory, setMemory] = useState<Memory | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    setError("");
    getMemory(storyId)
      .then(setMemory)
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(load, [storyId]);

  if (loading) return <LoadingBlock label="Loading memory..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!memory) return <EmptyState title="No memory yet." body="Memory is written after the first approved episode." />;

  const empty = !memory.rolling_summary && memory.characters.length === 0 && memory.world_facts.length === 0;

  return (
    <div className="space-y-4">
      {empty ? <EmptyState title="Memory is still empty." body="Approve an episode to update the rolling summary, characters, facts, and threads." /> : null}
      <section className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
        <h3 className="font-display text-2xl">Rolling summary</h3>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-zinc-200">{memory.rolling_summary || "No summary yet."}</p>
      </section>
      <section className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
        <h3 className="mb-3 font-medium">Characters</h3>
        <table className="w-full text-left text-sm">
          <thead className="text-zinc-400"><tr><th>Name</th><th>Role</th><th>Status</th><th>Current state</th></tr></thead>
          <tbody>
            {memory.characters.map((character) => (
              <tr key={character.name} className="border-t border-zinc-800">
                <td className="py-2">{character.name}</td>
                <td>{character.role}</td>
                <td>{character.status}</td>
                <td>{character.current_state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
        <h3 className="mb-3 font-medium">World facts</h3>
        <table className="w-full text-left text-sm">
          <thead className="text-zinc-400"><tr><th>Category</th><th>Key</th><th>Value</th></tr></thead>
          <tbody>
            {memory.world_facts.map((fact) => (
              <tr key={`${fact.category}-${fact.key}`} className="border-t border-zinc-800">
                <td className="py-2">{fact.category}</td>
                <td>{fact.key}</td>
                <td>{fact.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section>
        <h3 className="mb-3 font-medium">Open threads</h3>
        <div className="grid gap-3 md:grid-cols-2">
          {memory.open_threads.map((thread) => (
            <article key={thread.title} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
              <ImportanceBadge importance={thread.importance || "medium"} />
              <h4 className="mt-2 font-medium">{thread.title}</h4>
              <p className="text-sm text-zinc-300">{thread.description}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
        <h3 className="font-medium">Active human instructions</h3>
        {memory.active_instructions.length === 0 ? <p className="mt-2 text-sm text-zinc-400">None.</p> : (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {memory.active_instructions.map((instruction) => <li key={instruction}>{instruction}</li>)}
          </ul>
        )}
      </section>
    </div>
  );
}
