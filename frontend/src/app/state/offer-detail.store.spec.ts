import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { anOffer, setupHttp } from '../testing';
import { OfferDetailStore } from './offer-detail.store';

describe('OfferDetailStore', () => {
  let store: InstanceType<typeof OfferDetailStore>;
  let http: HttpTestingController;

  beforeEach(() => {
    http = setupHttp(OfferDetailStore);
    store = TestBed.inject(OfferDetailStore);
    store.load('o1');
    http.expectOne('/api/offers/o1').flush(anOffer('o1', 75));
  });

  afterEach(() => http.verify());

  it('shows the question at once and fills in the answer with the tool trace', () => {
    store.ask('Do I know Docker?');
    expect(store.chat()).toEqual([{ question: 'Do I know Docker?', answer: null, steps: [] }]);

    http.expectOne('/api/offers/o1/ask').flush({
      answer: 'Yes, in two projects.',
      steps: [{ tool: 'search_cv', args: { query: 'Docker' }, result_preview: '{...}' }],
    });

    const [turn] = store.chat();
    expect(turn.answer).toBe('Yes, in two projects.');
    expect(turn.steps.map((s) => s.tool)).toEqual(['search_cv']);
  });

  it('ignores a second question while the first is being answered', () => {
    store.ask('First?');
    store.ask('Second?');
    http.expectOne('/api/offers/o1/ask').flush({ answer: 'One', steps: [] });

    expect(store.chat().map((t) => t.question)).toEqual(['First?']);
  });

  it('turns an API error into an answer instead of leaving the chat hanging', () => {
    store.ask('Anything?');
    http
      .expectOne('/api/offers/o1/ask')
      .flush({ detail: 'LLM quota exceeded' }, { status: 429, statusText: 'Too Many' });

    expect(store.chat()[0].answer).toContain('LLM quota exceeded');
  });

  it('writes a cover letter in the chosen language', () => {
    store.writeLetter('en');
    const request = http.expectOne('/api/offers/o1/cover-letter');
    expect(request.request.body).toEqual({ language: 'en' });
    request.flush({ text: 'Dear Hiring Team' });

    expect(store.letter()).toBe('Dear Hiring Team');
    expect(store.letterLoading()).toBe(false);
  });
});
