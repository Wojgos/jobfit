import { computed, inject } from '@angular/core';
import { tapResponse } from '@ngrx/operators';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';
import {
  prependEntity,
  removeEntity,
  setAllEntities,
  withEntities,
} from '@ngrx/signals/entities';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { firstValueFrom, pipe, switchMap, tap } from 'rxjs';

import { JobfitApi, errorMessage } from '../core/api';
import { OfferDetail, OfferSummary } from '../core/models';

interface OffersState {
  loading: boolean;
  analyzing: boolean;
  error: string | null;
}

function toSummary(offer: OfferDetail): OfferSummary {
  const { id, title, company, score, status, created_at } = offer;
  return { id, title, company, score, status, created_at };
}

export const OffersStore = signalStore(
  { providedIn: 'root' },
  withEntities<OfferSummary>(),
  withState<OffersState>({ loading: false, analyzing: false, error: null }),
  withComputed(({ entities }) => ({
    averageScore: computed(() => {
      const scores = entities()
        .map((o) => o.score)
        .filter((s): s is number => s !== null);
      return scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;
    }),
  })),
  withMethods((store, api = inject(JobfitApi)) => ({
    loadAll: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap(() =>
          api.listOffers().pipe(
            tapResponse({
              next: (offers) => patchState(store, setAllEntities(offers), { loading: false }),
              error: (error) => patchState(store, { loading: false, error: errorMessage(error) }),
            }),
          ),
        ),
      ),
    ),

    /** Analyse a new offer; resolves to its id so the caller can navigate to it. */
    async analyze(rawText: string, sourceUrl: string | null): Promise<string | null> {
      patchState(store, { analyzing: true, error: null });
      try {
        const offer = await firstValueFrom(api.createOffer(rawText, sourceUrl));
        patchState(store, prependEntity(toSummary(offer)), { analyzing: false });
        return offer.id;
      } catch (error) {
        patchState(store, { analyzing: false, error: errorMessage(error) });
        return null;
      }
    },

    async remove(id: string): Promise<void> {
      try {
        await firstValueFrom(api.deleteOffer(id));
        patchState(store, removeEntity(id));
      } catch (error) {
        patchState(store, { error: errorMessage(error) });
      }
    },
  })),
);
