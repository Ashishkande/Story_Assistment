import { http } from "./client";
import type { DashboardData, ResumePoint, Story } from "../types";

export async function listStories() {
  const { data } = await http.get<Story[]>("/api/stories");
  return data;
}

export async function getStory(storyId: string) {
  const { data } = await http.get<Story>(`/api/stories/${storyId}`);
  return data;
}

export async function createStory(premise: string) {
  const { data } = await http.post<{ id: string; premise: string; status: string }>("/api/stories", { premise });
  return data;
}

export async function getDashboard() {
  const { data } = await http.get<DashboardData>("/api/dashboard");
  return data;
}

export async function resumeStory(storyId: string) {
  const { data } = await http.post<ResumePoint>(`/api/stories/${storyId}/resume`);
  return data;
}

export async function reconcileStory(storyId: string, fromEpisode: number) {
  const { data } = await http.post(`/api/stories/${storyId}/reconcile`, { from_episode: fromEpisode });
  return data;
}
