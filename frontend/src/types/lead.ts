export type SignalType =
  | 'funding_round'
  | 'sdr_hiring'
  | 'growth_news'
  | 'upmarket_pivot'
  | string;

export type LeadTier = 'High' | 'Medium' | 'Low';
export type ICPFit = 'Strong' | 'Partial' | 'Poor';
export type LeadBadge = 'new_today' | 'score_up' | 'score_down' | 'signal_added' | 'filtered';

export interface ExtractedSignal {
  signal_type: SignalType;
  verbatim_quote: string;
  quote_validated: boolean;
  similarity_score: number;
  source_url?: string;
  recency_label: string;
  event_date?: string;
  score_contribution: number;
}

export interface DNSAuditObjective {
  spf: string;
  dkim: string;
  dmarc: string;
  issues: string[];
  provider?: string;
}

export interface IntentConfig {
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

export type EmailDeliverabilityStatus =
  | 'DELIVERABLE'
  | 'HIGH_PROBABILITY'
  | 'CATCH_ALL'
  | 'INVALID';

export interface SocialPost {
  id: string;
  platform: 'reddit' | 'yelp' | 'x' | 'facebook' | 'instagram' | 'linkedin' | string;
  author_name: string;
  author_handle: string;
  content: string;
  post_url: string;
  keyword_matched: string;
  company_name?: string;
  summary?: string | null;
  published_at: string;
}

export interface Contact {
  name: string;
  title: string;
  email: string;
  confidence: string;
  source?: string;
  linkedin_url?: string;
  department?: string;
  phone?: string;
  status?: EmailDeliverabilityStatus;
}

export interface ConfidenceEvaluation {
  label: string;
  color: string;
  verified: number;
  total: number;
}

export interface SignalTagModel {
  tag: string;
  category: string;
  color_theme: string;
}

export interface LeadDetailResponse {
  id: string;
  company_name: string;
  domain: string;
  industry: string;
  company_segment?: string | null;
  employee_count: number | null;
  funding_stage: string | null;
  intent_score: number;
  intent_classification?: 'HOT' | 'WARM' | 'SKIP' | null;
  one_line_reason?: string | null;
  location_mentioned?: string | null;
  budget_mentioned?: string | null;
  urgency_indicators?: string[];
  competitor_mentioned?: string | null;
  icp_score?: number;
  signal_freshness: number;
  tier: LeadTier;
  icp_fit: ICPFit;
  confidence: ConfidenceEvaluation;
  why_now: string;
  signal_tags?: SignalTagModel[];
  badge: LeadBadge | null;
  social_segment?: string | null;
  meta_ads_active?: boolean;
  meta_ads_count?: number;
  bio_url?: string | null;
  signals: ExtractedSignal[];
  ai_verdict: string;
  dns_audit: DNSAuditObjective;
  contacts?: Contact[];
  company_linkedin_id?: string | null;
  annual_revenue?: string | null;
  company_insights?: any; // Replace with proper type if available
  job_openings?: any; // Replace with proper type if available
  last_updated: string;
}
