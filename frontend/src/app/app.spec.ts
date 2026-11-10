import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';
import { setupHttp } from './testing';

describe('App', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    http = setupHttp(provideRouter([]));
  });

  afterEach(() => http.verify());

  async function render(demoMode: boolean): Promise<HTMLElement> {
    const fixture = TestBed.createComponent(App);
    http.expectOne('/api/meta').flush({ demo_mode: demoMode, llm_provider: 'fake' });
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('renders the main navigation', async () => {
    const element = await render(false);
    const links = [...element.querySelectorAll('nav ul a')];
    expect(links.map((a) => a.textContent?.trim())).toEqual(['Offers', 'Board', 'My CV']);
    expect(element.querySelector('[role="status"]')).toBeNull();
  });

  it('shows a banner in the public demo', async () => {
    const element = await render(true);
    expect(element.querySelector('[role="status"]')?.textContent).toContain('Public demo');
  });
});
