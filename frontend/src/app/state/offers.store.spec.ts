import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { anOffer, setupHttp } from '../testing';
import { OffersStore } from './offers.store';

describe('OffersStore', () => {
  let store: InstanceType<typeof OffersStore>;
  let http: HttpTestingController;

  beforeEach(() => {
    http = setupHttp();
    store = TestBed.inject(OffersStore);
  });

  afterEach(() => http.verify());

  it('loads offers and averages the scores that exist', () => {
    store.loadAll();
    expect(store.loading()).toBe(true);
    http.expectOne('/api/offers').flush([anOffer('a', 80), anOffer('b', 61), anOffer('c', null)]);

    expect(store.loading()).toBe(false);
    expect(store.ids()).toEqual(['a', 'b', 'c']);
    expect(store.averageScore()).toBe(71);
  });

  it('adds an analysed offer on top and returns its id', async () => {
    const pending = store.analyze('Junior Python Developer, requirements: ...', null);
    expect(store.analyzing()).toBe(true);

    const request = http.expectOne('/api/offers');
    expect(request.request.body).toEqual({
      raw_text: 'Junior Python Developer, requirements: ...',
      source_url: null,
    });
    request.flush(anOffer('new', 90));

    expect(await pending).toBe('new');
    expect(store.ids()[0]).toBe('new');
    expect(store.analyzing()).toBe(false);
  });

  it('shows the API message when analysis is refused', async () => {
    const pending = store.analyze('text', null);
    http
      .expectOne('/api/offers')
      .flush(
        { detail: 'Upload your CV before analysing offers' },
        { status: 409, statusText: 'Conflict' },
      );

    expect(await pending).toBeNull();
    expect(store.error()).toBe('Upload your CV before analysing offers');
  });
});
