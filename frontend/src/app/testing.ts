import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Provider } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { Application, ApplicationStatus, OfferDetail } from './core/models';

export function setupHttp(...providers: Provider[]): HttpTestingController {
  TestBed.configureTestingModule({
    providers: [provideHttpClient(), provideHttpClientTesting(), ...providers],
  });
  return TestBed.inject(HttpTestingController);
}

export function anApplication(id: string, status: ApplicationStatus): Application {
  return {
    id,
    offer_id: `offer-${id}`,
    title: `Offer ${id}`,
    company: null,
    score: 80,
    status,
    notes: '',
    updated_at: '2026-11-09T10:00:00Z',
  };
}

export function anOffer(id: string, score: number | null): OfferDetail {
  return {
    id,
    title: `Junior Developer ${id}`,
    company: 'Example',
    score,
    status: 'to_apply',
    created_at: '2026-11-09T10:00:00Z',
    source_url: null,
    raw_text: 'Junior Python Developer...',
    application_id: `app-${id}`,
    analysis: null,
  };
}
