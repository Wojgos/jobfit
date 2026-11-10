import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { CvStore } from '../../state/cv.store';
import { MetaStore } from '../../state/meta.store';
import { OffersStore } from '../../state/offers.store';
import { STATUS_LABELS } from '../../ui/labels';
import { ScoreBadge } from '../../ui/score-badge';

@Component({
  selector: 'app-offers-page',
  imports: [ReactiveFormsModule, RouterLink, DatePipe, ScoreBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './offers-page.html',
})
export class OffersPage {
  protected readonly offers = inject(OffersStore);
  protected readonly cv = inject(CvStore);
  protected readonly meta = inject(MetaStore);
  private readonly router = inject(Router);
  protected readonly statusLabels = STATUS_LABELS;

  protected readonly form = new FormGroup({
    rawText: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(80)],
    }),
    sourceUrl: new FormControl('', { nonNullable: true }),
  });

  constructor() {
    this.offers.loadAll();
    this.cv.load();
  }

  protected async analyze(): Promise<void> {
    if (this.form.invalid) return;
    const { rawText, sourceUrl } = this.form.getRawValue();
    const id = await this.offers.analyze(rawText, sourceUrl || null);
    if (id) {
      this.form.reset();
      await this.router.navigate(['/offers', id]);
    }
  }
}
