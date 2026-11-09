import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { anApplication, setupHttp } from '../testing';
import { BoardStore } from './board.store';

describe('BoardStore', () => {
  let store: InstanceType<typeof BoardStore>;
  let http: HttpTestingController;

  beforeEach(() => {
    http = setupHttp();
    store = TestBed.inject(BoardStore);
    store.load();
    http
      .expectOne('/api/applications')
      .flush([anApplication('1', 'to_apply'), anApplication('2', 'applied')]);
  });

  afterEach(() => http.verify());

  it('groups applications into columns in board order', () => {
    const columns = store.columns();
    expect(columns.map((c) => c.status)).toEqual([
      'to_apply',
      'applied',
      'interview',
      'offer',
      'rejected',
    ]);
    expect(columns[0].items.map((a) => a.id)).toEqual(['1']);
    expect(columns[1].items.map((a) => a.id)).toEqual(['2']);
  });

  it('moves a card at once and keeps it there when the API confirms', async () => {
    const done = store.move('1', 'interview');
    expect(store.entityMap()['1'].status).toBe('interview');

    const request = http.expectOne('/api/applications/1');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ status: 'interview' });
    request.flush(anApplication('1', 'interview'));
    await done;

    expect(store.entityMap()['1'].status).toBe('interview');
    expect(store.error()).toBeNull();
  });

  it('moves the card back when the API fails', async () => {
    const done = store.move('1', 'offer');
    http
      .expectOne('/api/applications/1')
      .flush({ detail: 'Database unavailable' }, { status: 503, statusText: 'Unavailable' });
    await done;

    expect(store.entityMap()['1'].status).toBe('to_apply');
    expect(store.error()).toBe('Database unavailable');
  });

  it('ignores a drop into the same column', async () => {
    await store.move('2', 'applied');
    http.expectNone('/api/applications/2');
  });
});
