import { http } from "./client";
import type { FeedbackItem, Memory } from "../types";

export async function getMemory(storyId: string) {
  const { data } = await http.get<Memory>(`/api/stories/${storyId}/memory`);
  return data;
}

export async function listFeedback(storyId: string) {
  const { data } = await http.get<FeedbackItem[]>(`/api/stories/${storyId}/feedback`);
  return data;
}

export async function addFeedback(storyId: string, episode: number, instruction: string) {
  const { data } = await http.post(`/api/stories/${storyId}/feedback`, { episode, instruction });
  return data;
}
