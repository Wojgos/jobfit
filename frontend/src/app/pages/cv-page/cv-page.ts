import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';

import { CvStore } from '../../state/cv.store';
import { MetaStore } from '../../state/meta.store';

@Component({
  selector: 'app-cv-page',
  imports: [ReactiveFormsModule, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './cv-page.html',
})
export class CvPage {
  protected readonly store = inject(CvStore);
  protected readonly meta = inject(MetaStore);
  protected readonly text = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required, Validators.minLength(50)],
  });

  constructor() {
    this.store.load();
  }

  protected onFile(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) this.store.uploadFile(file);
  }

  protected submitText(): void {
    if (this.text.valid) this.store.uploadText(this.text.value);
  }
}
