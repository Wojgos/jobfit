import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { MetaStore } from './state/meta.store';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
})
export class App {
  protected readonly meta = inject(MetaStore);
  protected readonly links = [
    { path: '/offers', label: 'Offers' },
    { path: '/board', label: 'Board' },
    { path: '/cv', label: 'My CV' },
  ];
}
