import type { LeadDetailResponse } from '../types/lead';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export interface PitcherModeResponse {
  lead_id: string;
  subject_line: string;
  email_body: string;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export function fetchLeads(): Promise<LeadDetailResponse[]> {
  return requestJson<LeadDetailResponse[]>('/api/leads/');
}

export function fetchPitcherMode(id: string): Promise<PitcherModeResponse> {
  return requestJson<PitcherModeResponse>(`/api/leads/${id}/verdict`, {
    method: 'POST',
  });
}

export function ingestLead(companyName: string): Promise<LeadDetailResponse> {
  return requestJson<LeadDetailResponse>('/api/leads/ingest', {
    method: 'POST',
    body: JSON.stringify({ company_name: companyName }),
  });
}

export function deleteLead(id: string): Promise<{ status: string; id: string }> {
  return requestJson<{ status: string; id: string }>(`/api/leads/${id}`, {
    method: 'DELETE',
  });
}

export interface PipelineStatusResponse {
  last_run_time: string;
  lead_count_processed: number;
  status: string;
  errors_encountered: boolean;
}

export function fetchPipelineStatus(): Promise<PipelineStatusResponse> {
  return requestJson<PipelineStatusResponse>('/api/pipeline/status');
}

export function runPipeline(): Promise<any> {
  return requestJson<any>('/api/pipeline/run-test', {
    method: 'POST',
  });
}


export interface IntentConfig {
  active_niche?: string;
  news_queries: string[];
  serper_queries: string[];
  jobspy_search_term: string;
  news_signals_query_template?: string;
  exa_query?: string;
  extraction_keywords: string[];
  social_triggers: string[];
  social_topics: string[];
  min_employees?: number;
  max_employees?: number;
  min_arr?: string;
  max_arr?: string;
  target_industries?: string[];
  decision_maker_titles?: string[];
}

export interface AIICPResponse {
  min_employees: number;
  max_employees: number;
  min_arr?: string;
  max_arr?: string;
  target_industries: string[];
  jobspy_search_term: string;
  exa_query: string;
  extraction_keywords: string[];
  social_triggers: string[];
  social_topics: string[];
  news_queries: string[];
  serper_queries: string[];
  summary_explanation: string;
}

export function fetchIntents(): Promise<IntentConfig> {
  return requestJson<IntentConfig>('/api/settings/intents');
}

export function updateIntents(config: IntentConfig): Promise<IntentConfig> {
  return requestJson<IntentConfig>('/api/settings/intents', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

export function generateICPWithAI(prompt: string): Promise<AIICPResponse> {
  return requestJson<AIICPResponse>('/api/settings/ai-icp-assistant', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });
}


export async function triggerSocialSweep(): Promise<{ status: string; fetched_count: number; saved_new: number; last_fetched_at?: string }> {
  return requestJson<{ status: string; fetched_count: number; saved_new: number; last_fetched_at?: string }>('/api/social-posts/fetch', {
    method: 'POST',
  });
}

import type { SocialPost } from '../types/lead';

export function fetchSocialPosts(platform?: string, keyword?: string): Promise<SocialPost[]> {
  const params = new URLSearchParams();
  if (platform && platform !== 'All') params.append('platform', platform);
  if (keyword) params.append('keyword', keyword);
  const q = params.toString() ? `?${params.toString()}` : '';
  return requestJson<SocialPost[]>(`/api/social-posts/${q}`);
}

export function deleteSocialPost(id: string): Promise<{ status: string }> {
  return requestJson<{ status: string }>(`/api/social-posts/${id}`, {
    method: 'DELETE',
  });
}

export function fetchLatestATSJobs(): Promise<{ status: string; jobs: any[]; run_time?: string; general_summary?: string }> {
  return requestJson<{ status: string; jobs: any[]; run_time?: string; general_summary?: string }>('/api/ats-jobs/latest');
}

export function triggerATSJobsFetch(): Promise<{ status: string; jobs: any[]; run_time?: string; general_summary?: string }> {
  return requestJson<{ status: string; jobs: any[]; run_time?: string; general_summary?: string }>('/api/ats-jobs/fetch', {
    method: 'POST',
  });
}

export function deleteATSJob(id: string): Promise<{ status: string }> {
  return requestJson<{ status: string }>(`/api/ats-jobs/${id}`, {
    method: 'DELETE',
  });
}
