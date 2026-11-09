import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type ScoreTone = 'good' | 'fair' | 'poor' | 'none';

export function scoreTone(score: number | null): ScoreTone {
  if (score === null) return 'none';
  if (score >= 75) return 'good';
  if (score >= 50) return 'fair';
  return 'poor';
}

const TONE_CLASSES: Record<ScoreTone, string> = {
  good: 'bg-emerald-100 text-emerald-800 ring-emerald-600/20',
  fair: 'bg-amber-100 text-amber-800 ring-amber-600/20',
  poor: 'bg-rose-100 text-rose-800 ring-rose-600/20',
  none: 'bg-slate-100 text-slate-600 ring-slate-500/20',
};

@Component({
  selector: 'app-score-badge',
  imports: [DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span
      class="inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-semibold tabular-nums ring-1 ring-inset"
      [class]="classes()"
      [attr.aria-label]="score() === null ? 'No score' : 'Match score ' + score() + ' percent'"
    >
      {{ score() === null ? '–' : (score() | number: '1.0-0') + '%' }}
    </span>
  `,
})
export class ScoreBadge {
  readonly score = input.required<number | null>();
  protected readonly classes = computed(() => TONE_CLASSES[scoreTone(this.score())]);
}
