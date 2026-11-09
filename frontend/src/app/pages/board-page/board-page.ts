import { CdkDrag, CdkDragDrop, CdkDropList, CdkDropListGroup } from '@angular/cdk/drag-drop';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Application, ApplicationStatus } from '../../core/models';
import { BoardStore } from '../../state/board.store';
import { STATUS_LABELS } from '../../ui/labels';
import { ScoreBadge } from '../../ui/score-badge';

@Component({
  selector: 'app-board-page',
  imports: [CdkDropListGroup, CdkDropList, CdkDrag, RouterLink, ScoreBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './board-page.html',
})
export class BoardPage {
  protected readonly store = inject(BoardStore);
  protected readonly labels = STATUS_LABELS;

  constructor() {
    this.store.load();
  }

  protected drop(event: CdkDragDrop<ApplicationStatus, ApplicationStatus, Application>): void {
    if (event.previousContainer !== event.container) {
      void this.store.move(event.item.data.id, event.container.data);
    }
  }

  protected saveNotes(app: Application, event: Event): void {
    const notes = (event.target as HTMLTextAreaElement).value;
    if (notes !== app.notes) void this.store.saveNotes(app.id, notes);
  }
}
