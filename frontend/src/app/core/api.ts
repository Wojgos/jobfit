import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, InjectionToken, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  Application,
  ApplicationStatus,
  AskResponse,
  Cv,
  OfferDetail,
  OfferSummary,
} from './models';

/** Base URL of the API. Empty in the browser: the dev proxy or nginx forwards /api. */
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  factory: () => '',
});

@Injectable({ providedIn: 'root' })
export class JobfitApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  getCv(): Observable<Cv> {
    return this.http.get<Cv>(`${this.base}/api/cv`);
  }

  uploadCvFile(file: File): Observable<Cv> {
    const body = new FormData();
    body.append('file', file);
    return this.http.post<Cv>(`${this.base}/api/cv`, body);
  }

  uploadCvText(text: string): Observable<Cv> {
    return this.http.post<Cv>(`${this.base}/api/cv/text`, { text, filename: 'cv.txt' });
  }

  listOffers(): Observable<OfferSummary[]> {
    return this.http.get<OfferSummary[]>(`${this.base}/api/offers`);
  }

  getOffer(id: string): Observable<OfferDetail> {
    return this.http.get<OfferDetail>(`${this.base}/api/offers/${id}`);
  }

  createOffer(rawText: string, sourceUrl: string | null): Observable<OfferDetail> {
    return this.http.post<OfferDetail>(`${this.base}/api/offers`, {
      raw_text: rawText,
      source_url: sourceUrl || null,
    });
  }

  deleteOffer(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/api/offers/${id}`);
  }

  coverLetter(id: string, language: 'pl' | 'en'): Observable<{ text: string }> {
    return this.http.post<{ text: string }>(`${this.base}/api/offers/${id}/cover-letter`, {
      language,
    });
  }

  ask(id: string, question: string): Observable<AskResponse> {
    return this.http.post<AskResponse>(`${this.base}/api/offers/${id}/ask`, { question });
  }

  listApplications(): Observable<Application[]> {
    return this.http.get<Application[]>(`${this.base}/api/applications`);
  }

  updateApplication(
    id: string,
    patch: { status?: ApplicationStatus; notes?: string },
  ): Observable<Application> {
    return this.http.patch<Application>(`${this.base}/api/applications/${id}`, patch);
  }
}

/** Human-readable message from an API error (FastAPI puts it in `detail`). */
export function errorMessage(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    const detail = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return 'Invalid input: check the form fields.';
    if (error.status === 0) return 'Cannot reach the API. Is the backend running?';
    return `Request failed (${error.status}).`;
  }
  return 'Something went wrong.';
}
