import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { startOperation, waitForOperation } from "../api/logs";
import { apiError } from "../api/client";
import { useToast } from "../hooks/useToast";
import { Field, buttonClass, inputClass } from "../components/ui";

const DEFAULT_PREMISE =
  "A delivery rider realizes every address on today's route belongs to someone who died in the same building.";

export function DemoPage() {
  const navigate = useNavigate();
  const { push } = useToast();
  const [premise, setPremise] = useState(DEFAULT_PREMISE);
  const [episodes, setEpisodes] = useState(15);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setMessage("Starting demo...");
    try {
      const job = await startOperation({ type: "demo", premise, episodes });
      const done = await waitForOperation(job.id, (update) => setMessage(update.message || "Agent is working..."));
      if (done.status === "failed") throw new Error(done.error || "Demo failed");
      const storyId = String(done.result?.story_id || "");
      push("Demo finished.");
      if (storyId) navigate(`/stories/${storyId}`);
    } catch (error) {
      push(apiError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-amber-300">Automated walkthrough</p>
        <h2 className="font-display text-4xl">Run the demo</h2>
        <p className="mt-2 text-sm text-zinc-400">
          Creates a story, generates the 200-episode plan, approves it, writes episodes, and records the two human interventions from the CLI demo.
        </p>
      </header>
      <Field label="Premise">
        <textarea className={`${inputClass} min-h-28`} value={premise} onChange={(event) => setPremise(event.target.value)} />
      </Field>
      <Field label="Episodes">
        <input className={inputClass} type="number" min={1} max={30} value={episodes} onChange={(event) => setEpisodes(Number(event.target.value))} />
      </Field>
      <button className={buttonClass} disabled={busy || premise.trim().length < 10} onClick={run}>
        {busy ? "Generating..." : "Run demo"}
      </button>
      {busy ? <p className="text-sm text-amber-200">Agent is working... {message}</p> : null}
    </div>
  );
}
