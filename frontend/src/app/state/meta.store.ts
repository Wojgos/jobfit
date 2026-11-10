import { HttpClient } from '@angular/common/http';
import { inject } from '@angular/core';
import { patchState, signalStore, withHooks, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { EMPTY, catchError, pipe, switchMap, tap } from 'rxjs';

import { API_BASE_URL } from '../core/api';

interface MetaState {
  demoMode: boolean;
  llmProvider: string | null;
}

/** Deployment info from /api/meta; loads once when the store is first injected. */
export const MetaStore = signalStore(
  { providedIn: 'root' },
  withState<MetaState>({ demoMode: false, llmProvider: null }),
  withMethods((store, http = inject(HttpClient), base = inject(API_BASE_URL)) => ({
    load: rxMethod<void>(
      pipe(
        switchMap(() =>
          http.get<{ demo_mode: boolean; llm_provider: string }>(`${base}/api/meta`).pipe(
            tap((meta) =>
              patchState(store, { demoMode: meta.demo_mode, llmProvider: meta.llm_provider }),
            ),
            catchError(() => EMPTY), // not fatal: the app works as a normal instance
          ),
        ),
      ),
    ),
  })),
  withHooks({ onInit: (store) => store.load() }),
);
