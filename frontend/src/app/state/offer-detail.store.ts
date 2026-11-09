import { inject } from '@angular/core';
import { tapResponse } from '@ngrx/operators';
import { patchState, signalStore, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { exhaustMap, pipe, switchMap, tap } from 'rxjs';

import { JobfitApi, errorMessage } from '../core/api';
import { OfferDetail, ToolTrace } from '../core/models';

export interface ChatTurn {
  question: string;
  answer: string | null; // null while the assistant is working
  steps: ToolTrace[];
}

interface OfferDetailState {
  offer: OfferDetail | null;
  loading: boolean;
  error: string | null;
  letter: string | null;
  letterLoading: boolean;
  chat: ChatTurn[];
}

/** Per-page store: provided by the offer detail component, so it resets on navigation. */
export const OfferDetailStore = signalStore(
  withState<OfferDetailState>({
    offer: null,
    loading: false,
    error: null,
    letter: null,
    letterLoading: false,
    chat: [],
  }),
  withMethods((store, api = inject(JobfitApi)) => {
    const answerLastQuestion = (answer: string, steps: ToolTrace[]) =>
      patchState(store, ({ chat }) => ({
        chat: chat.map((turn, i) => (i === chat.length - 1 ? { ...turn, answer, steps } : turn)),
      }));

    return {
      load: rxMethod<string>(
        pipe(
          tap(() => patchState(store, { loading: true, error: null })),
          switchMap((id) =>
            api.getOffer(id).pipe(
              tapResponse({
                next: (offer) => patchState(store, { offer, loading: false }),
                error: (error) =>
                  patchState(store, { loading: false, error: errorMessage(error) }),
              }),
            ),
          ),
        ),
      ),

      writeLetter: rxMethod<'pl' | 'en'>(
        pipe(
          tap(() => patchState(store, { letterLoading: true })),
          exhaustMap((language) =>
            api.coverLetter(store.offer()!.id, language).pipe(
              tapResponse({
                next: ({ text }) => patchState(store, { letter: text, letterLoading: false }),
                error: (error) =>
                  patchState(store, { letterLoading: false, error: errorMessage(error) }),
              }),
            ),
          ),
        ),
      ),

      ask: rxMethod<string>(
        // exhaustMap: a question asked while another is being answered is ignored.
        exhaustMap((question) => {
          patchState(store, ({ chat }) => ({
            chat: [...chat, { question, answer: null, steps: [] }],
          }));
          return api.ask(store.offer()!.id, question).pipe(
            tapResponse({
              next: ({ answer, steps }) => answerLastQuestion(answer, steps),
              error: (error) => answerLastQuestion(`⚠ ${errorMessage(error)}`, []),
            }),
          );
        }),
      ),
    };
  }),
);
