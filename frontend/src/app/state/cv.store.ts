import { inject } from '@angular/core';
import { tapResponse } from '@ngrx/operators';
import { patchState, signalStore, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable, exhaustMap, pipe, switchMap, tap } from 'rxjs';

import { JobfitApi, errorMessage } from '../core/api';
import { Cv } from '../core/models';

interface CvState {
  cv: Cv | null;
  loaded: boolean;
  saving: boolean;
  error: string | null;
}

export const CvStore = signalStore(
  { providedIn: 'root' },
  withState<CvState>({ cv: null, loaded: false, saving: false, error: null }),
  withMethods((store, api = inject(JobfitApi)) => {
    const save = rxMethod<() => Observable<Cv>>(
      pipe(
        tap(() => patchState(store, { saving: true, error: null })),
        exhaustMap((request) =>
          request().pipe(
            tapResponse({
              next: (cv) => patchState(store, { cv, saving: false }),
              error: (error) => patchState(store, { saving: false, error: errorMessage(error) }),
            }),
          ),
        ),
      ),
    );
    return {
      load: rxMethod<void>(
        pipe(
          switchMap(() =>
            api.getCv().pipe(
              tapResponse({
                next: (cv) => patchState(store, { cv, loaded: true }),
                // 404 simply means no CV yet.
                error: (error) =>
                  patchState(store, {
                    loaded: true,
                    error:
                      error instanceof HttpErrorResponse && error.status === 404
                        ? null
                        : errorMessage(error),
                  }),
              }),
            ),
          ),
        ),
      ),
      uploadFile: (file: File) => save(() => api.uploadCvFile(file)),
      uploadText: (text: string) => save(() => api.uploadCvText(text)),
    };
  }),
);
