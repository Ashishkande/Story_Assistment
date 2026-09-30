import { http } from "./client";
import type { Plan } from "../types";

export async function getPlan(storyId: string) {
  const { data } = await http.get<Plan>(`/api/stories/${storyId}/plan`);
  return data;
}

export async function approvePlan(storyId: string) {
  const { data } = await http.post(`/api/stories/${storyId}/plan/approve`);
  return data;
}
