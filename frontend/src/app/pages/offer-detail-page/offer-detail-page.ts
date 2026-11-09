import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { RequirementMatch } from '../../core/models';
import { OfferDetailStore } from '../../state/offer-detail.store';
import { MATCH_LABELS, STATUS_LABELS, formatSalary } from '../../ui/labels';
import { ScoreBadge } from '../../ui/score-badge';

@Component({
  selector: 'app-offer-detail-page',
  imports: [ReactiveFormsModule, RouterLink, ScoreBadge],
  providers: [OfferDetailStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './offer-detail-page.html',
})
export class OfferDetailPage {
  /** Route parameter, bound by withComponentInputBinding(). */
  readonly id = input.required<string>();

  protected readonly store = inject(OfferDetailStore);
  protected readonly matchLabels = MATCH_LABELS;
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly question = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required, Validators.minLength(3)],
  });

  protected readonly analysis = computed(() => this.store.offer()?.analysis ?? null);
  protected readonly mustHaves = computed(() => this.byImportance('must'));
  protected readonly niceToHaves = computed(() => this.byImportance('nice'));
  protected readonly groups = computed(() => [
    { title: 'Must have', items: this.mustHaves() },
    { title: 'Nice to have', items: this.niceToHaves() },
  ]);
  protected readonly salary = computed(() => {
    const s = this.analysis()?.salary;
    return s ? formatSalary(s.monthly_min, s.monthly_max, s.currency) : null;
  });
  protected readonly asking = computed(() => this.store.chat().at(-1)?.answer === null);

  protected readonly suggestions = [
    'Which requirements am I missing and how could I close the gap?',
    'What should I highlight in the interview?',
    'How much is this per month?',
  ];

  constructor() {
    // rxMethod accepts a signal and reloads whenever the route id changes.
    this.store.load(this.id);
  }

  protected send(text = this.question.value): void {
    if (text.trim().length < 3 || this.asking()) return;
    this.store.ask(text.trim());
    this.question.reset();
  }

  protected async copyLetter(): Promise<void> {
    const letter = this.store.letter();
    if (letter) await navigator.clipboard.writeText(letter);
  }

  private byImportance(importance: 'must' | 'nice'): RequirementMatch[] {
    return this.analysis()?.matches.filter((m) => m.importance === importance) ?? [];
  }
}
