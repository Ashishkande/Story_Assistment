export interface Story {
  id: string;
  title: string | null;
  premise: string;
  genre?: string | null;
  tone?: string | null;
  status: string;
  current_episode: number;
  total_planned: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface Arc {
  arc_number: number;
  title: string;
  episode_start: number;
  episode_end: number;
  summary: string;
  major_themes?: string[];
  turning_point?: string;
}

export interface EpisodePlan {
  episode_number: number;
  title: string;
  summary: string;
  planned_hook?: string;
  arc_number?: number;
  major_events?: string[];
  characters_involved?: string[];
}

export interface Plan {
  id: string;
  story_id: string;
  approved: boolean;
  version: number;
  world_rules: string[];
  major_turning_points: string[];
  planned_resolutions?: string[];
  arc_structure: Record<string, Arc>;
  episode_plans: EpisodePlan[];
}

export interface EpisodeSummary {
  episode_number: number;
  title: string | null;
  status: string;
  word_count?: number | null;
  critic_score?: number | null;
  is_stale?: boolean;
  revision_count?: number;
}

export interface CriticIssue {
  type?: string;
  severity?: string;
  description?: string;
}

export interface Episode {
  id: string;
  story_id: string;
  episode_number: number;
  title: string | null;
  content: string | null;
  summary: string | null;
  hook: string | null;
  status: string;
  word_count: number | null;
  revision_count: number;
  characters_present: string[];
  threads_opened: string[];
  threads_resolved: string[];
  critic_score: number | null;
  critic_issues: CriticIssue[];
  critic_passed: boolean | null;
  human_edited: boolean;
  rejection_reason: string | null;
  is_stale: boolean;
  stale_reason?: string | null;
}

export interface Character {
  name: string;
  role: string | null;
  status: string;
  current_state: string | null;
}

export interface WorldFact {
  category: string;
  key: string;
  value: string;
}

export interface OpenThread {
  title: string;
  description: string;
  importance: string;
}

export interface Memory {
  rolling_summary: string | null;
  characters: Character[];
  world_facts: WorldFact[];
  open_threads: OpenThread[];
  active_instructions: string[];
}

export interface FeedbackItem {
  id: string;
  episode: number | null;
  action: string;
  instruction: string | null;
  rejection_reason: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface AgentRun {
  id: string;
  episode_number: number | null;
  agent: string;
  status: string;
  input_tokens: number | null;
  output_tokens: number | null;
  cost: number | null;
  latency_ms: number | null;
  retry_count: number;
  created_at?: string;
  story_id?: string;
  story_title?: string | null;
}

export interface LogResponse {
  runs: AgentRun[];
  summary: {
    total_cost: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_tokens: number;
    total_runs: number;
    average_latency_ms: number;
  };
}

export interface DashboardData {
  total_stories: number;
  generating: number;
  completed: number;
  episodes_generated: number;
  recent_stories: Story[];
  recent_activity: AgentRun[];
}

export interface Operation {
  id: string;
  type: string;
  story_id: string | null;
  status: "queued" | "running" | "succeeded" | "failed";
  message: string;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface ResumePoint {
  last_approved_episode: number;
  next_episode: number;
  status: string;
  title: string | null;
}
