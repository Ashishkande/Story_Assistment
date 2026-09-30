import { http } from "./client";
import type { Episode, EpisodeSummary } from "../types";

export async function listEpisodes(storyId: string) {
  const { data } = await http.get<EpisodeSummary[]>(`/api/stories/${storyId}/episodes`);
  return data;
}

export async function getEpisode(storyId: string, episodeNumber: number) {
  const { data } = await http.get<Episode>(`/api/stories/${storyId}/episodes/${episodeNumber}`);
  return data;
}

export async function approveEpisode(storyId: string, episodeNumber: number) {
  const { data } = await http.post(`/api/stories/${storyId}/episodes/${episodeNumber}/approve`);
  return data;
}

export async function editEpisode(storyId: string, episodeNumber: number, content: string, editNotes: string) {
  const { data } = await http.put(`/api/stories/${storyId}/episodes/${episodeNumber}`, {
    content,
    edit_notes: editNotes,
  });
  return data;
}

export async function rejectEpisode(storyId: string, episodeNumber: number, reason: string) {
  const { data } = await http.post(`/api/stories/${storyId}/episodes/${episodeNumber}/reject`, { reason });
  return data;
}
