import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createStory } from "../api/stories";
import { apiError } from "../api/client";
import { useToast } from "../hooks/useToast";
import { Field, Modal, buttonClass, inputClass } from "./ui";

const SAMPLE =
  "A delivery rider realizes every address on today's route belongs to someone who died in the same building.";

export function CreateStoryModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const { push } = useToast();
  const [premise, setPremise] = useState(SAMPLE);
  const [busy, setBusy] = useState(false);
  const [createdId, setCreatedId] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    try {
      const story = await createStory(premise.trim());
      setCreatedId(story.id);
      push("Story created successfully.");
    } catch (error) {
      push(apiError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Create New Story" onClose={onClose}>
      {createdId ? (
        <div className="space-y-4">
          <p className="text-sm text-emerald-300">Story created successfully.</p>
          <p className="break-all text-sm text-zinc-300">Story ID: {createdId}</p>
          <button className={buttonClass} onClick={() => navigate(`/stories/${createdId}`)}>
            Open workspace
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <Field label="Premise">
            <textarea className={`${inputClass} min-h-28`} value={premise} onChange={(event) => setPremise(event.target.value)} />
          </Field>
          <button className={buttonClass} disabled={busy || premise.trim().length < 10} onClick={submit}>
            {busy ? "Creating..." : "Create Story"}
          </button>
        </div>
      )}
    </Modal>
  );
}
