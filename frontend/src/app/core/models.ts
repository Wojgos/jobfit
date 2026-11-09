// Mirrors the backend schemas in backend/app/schemas.

export type Importance = 'must' | 'nice';
export type MatchStatus = 'met' | 'partial' | 'missing';
export type ApplicationStatus = 'to_apply' | 'applied' | 'interview' | 'offer' | 'rejected';

export const APPLICATION_STATUSES: readonly ApplicationStatus[] = [
  'to_apply',
  'applied',
  'interview',
  'offer',
  'rejected',
];

export interface Cv {
  id: string;
  filename: string;
  chunks: number;
  created_at: string;
}

export interface Requirement {
  name: string;
  category: string;
  importance: Importance;
}

export interface OfferExtraction {
  title: string;
  company: string | null;
  seniority: 'intern' | 'junior' | 'mid' | 'senior' | 'unknown';
  work_mode: 'remote' | 'hybrid' | 'onsite' | 'unknown';
  requirements: Requirement[];
}

export interface RequirementMatch {
  name: string;
  importance: Importance;
  status: MatchStatus;
  evidence: string;
  comment: string;
}

export interface NormalizedSalary {
  monthly_min: number | null;
  monthly_max: number | null;
  currency: string;
  contract: 'b2b' | 'uop' | 'other' | 'unknown';
  basis: string;
}

export interface Analysis {
  score: number;
  summary: string;
  extraction: OfferExtraction;
  matches: RequirementMatch[];
  salary: NormalizedSalary | null;
}

export interface OfferSummary {
  id: string;
  title: string;
  company: string | null;
  score: number | null;
  status: ApplicationStatus | null;
  created_at: string;
}

export interface OfferDetail extends OfferSummary {
  source_url: string | null;
  raw_text: string;
  analysis: Analysis | null;
  application_id: string | null;
}

export interface ToolTrace {
  tool: string;
  args: Record<string, unknown>;
  result_preview: string;
}

export interface AskResponse {
  answer: string;
  steps: ToolTrace[];
}

export interface Application {
  id: string;
  offer_id: string;
  title: string;
  company: string | null;
  score: number | null;
  status: ApplicationStatus;
  notes: string;
  updated_at: string;
}
