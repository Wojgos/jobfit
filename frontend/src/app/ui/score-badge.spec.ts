import { TestBed } from '@angular/core/testing';

import { ScoreBadge, scoreTone } from './score-badge';

describe('scoreTone', () => {
  it.each([
    [100, 'good'],
    [75, 'good'],
    [74.9, 'fair'],
    [50, 'fair'],
    [49, 'poor'],
    [null, 'none'],
  ] as const)('%s -> %s', (score, tone) => {
    expect(scoreTone(score)).toBe(tone);
  });
});

describe('ScoreBadge', () => {
  it('renders a rounded percentage with an accessible label', async () => {
    const fixture = TestBed.createComponent(ScoreBadge);
    fixture.componentRef.setInput('score', 85.7);
    await fixture.whenStable();

    const badge = (fixture.nativeElement as HTMLElement).querySelector('span')!;
    expect(badge.textContent?.trim()).toBe('86%');
    expect(badge.getAttribute('aria-label')).toBe('Match score 85.7 percent');
    expect(badge.className).toContain('emerald');
  });

  it('renders a dash without a score', async () => {
    const fixture = TestBed.createComponent(ScoreBadge);
    fixture.componentRef.setInput('score', null);
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).textContent?.trim()).toBe('–');
  });
});
