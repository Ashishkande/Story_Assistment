import { http } from "./client";
import type { LogResponse, Operation } from "../types";

export async function getLogs(storyId: string, limit = 100) {
  const { data } = await http.get<LogResponse>(`/api/stories/${storyId}/logs`, { params: { limit } });
  return data;
}

export async function startOperation(payload: {
  type: "plan" | "episode" | "demo";
  story_id?: string;
  premise?: string;
  episodes?: number;
}) {
  const { data } = await http.post<Operation>("/api/operations", payload);
  return data;
}

export async function getOperation(operationId: string) {
  const { data } = await http.get<Operation>(`/api/operations/${operationId}`);
  return data;
}

export async function waitForOperation(
  operationId: string,
  onUpdate?: (job: Operation) => void,
) {
  for (;;) {
    const job = await getOperation(operationId);
    onUpdate?.(job);
    if (job.status === "succeeded" || job.status === "failed") return job;
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
}
