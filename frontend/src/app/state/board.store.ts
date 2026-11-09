import { computed, inject } from '@angular/core';
import { tapResponse } from '@ngrx/operators';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';
import { setAllEntities, updateEntity, withEntities } from '@ngrx/signals/entities';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { firstValueFrom, pipe, switchMap, tap } from 'rxjs';

import { JobfitApi, errorMessage } from '../core/api';
import { APPLICATION_STATUSES, Application, ApplicationStatus } from '../core/models';

interface BoardState {
  loading: boolean;
  error: string | null;
}

export const BoardStore = signalStore(
  { providedIn: 'root' },
  withEntities<Application>(),
  withState<BoardState>({ loading: false, error: null }),
  withComputed(({ entities }) => ({
    /** One column per status, in board order. */
    columns: computed(() =>
      APPLICATION_STATUSES.map((status) => ({
        status,
        items: entities().filter((a) => a.status === status),
      })),
    ),
  })),
  withMethods((store, api = inject(JobfitApi)) => ({
    load: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap(() =>
          api.listApplications().pipe(
            tapResponse({
              next: (apps) => patchState(store, setAllEntities(apps), { loading: false }),
              error: (error) => patchState(store, { loading: false, error: errorMessage(error) }),
            }),
          ),
        ),
      ),
    ),

    /** Optimistic move: the card changes column at once and goes back if the API fails. */
    async move(id: string, status: ApplicationStatus): Promise<void> {
      const previous = store.entityMap()[id]?.status;
      if (!previous || previous === status) return;
      patchState(store, updateEntity({ id, changes: { status } }), { error: null });
      try {
        const saved = await firstValueFrom(api.updateApplication(id, { status }));
        patchState(store, updateEntity({ id, changes: saved }));
      } catch (error) {
        patchState(store, updateEntity({ id, changes: { status: previous } }), {
          error: errorMessage(error),
        });
      }
    },

    async saveNotes(id: string, notes: string): Promise<void> {
      try {
        const saved = await firstValueFrom(api.updateApplication(id, { notes }));
        patchState(store, updateEntity({ id, changes: saved }));
      } catch (error) {
        patchState(store, { error: errorMessage(error) });
      }
    },
  })),
);
