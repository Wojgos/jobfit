import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'offers' },
  {
    path: 'offers',
    title: 'Offers · JobFit',
    loadComponent: () => import('./pages/offers-page/offers-page').then((m) => m.OffersPage),
  },
  {
    path: 'offers/:id',
    title: 'Offer · JobFit',
    loadComponent: () =>
      import('./pages/offer-detail-page/offer-detail-page').then((m) => m.OfferDetailPage),
  },
  {
    path: 'board',
    title: 'Board · JobFit',
    loadComponent: () => import('./pages/board-page/board-page').then((m) => m.BoardPage),
  },
  {
    path: 'cv',
    title: 'My CV · JobFit',
    loadComponent: () => import('./pages/cv-page/cv-page').then((m) => m.CvPage),
  },
  { path: '**', redirectTo: 'offers' },
];
