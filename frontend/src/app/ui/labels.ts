import { ApplicationStatus, MatchStatus } from '../core/models';

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  to_apply: 'To apply',
  applied: 'Applied',
  interview: 'Interview',
  offer: 'Offer',
  rejected: 'Rejected',
};

export const MATCH_LABELS: Record<MatchStatus, { label: string; classes: string }> = {
  met: { label: 'Met', classes: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20' },
  partial: { label: 'Partial', classes: 'bg-amber-50 text-amber-700 ring-amber-600/20' },
  missing: { label: 'Missing', classes: 'bg-rose-50 text-rose-700 ring-rose-600/20' },
};

export function formatSalary(min: number | null, max: number | null, currency: string): string {
  // Polish style with a non-breaking space, also for four-digit amounts ("8 000", "12 000").
  const fmt = (n: number) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  if (min !== null && max !== null) return `${fmt(min)} – ${fmt(max)} ${currency}`;
  if (max !== null) return `up to ${fmt(max)} ${currency}`;
  if (min !== null) return `from ${fmt(min)} ${currency}`;
  return '—';
}
