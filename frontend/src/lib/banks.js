import { api } from './api.js';

// Shared, memoized Nigerian bank list — every "pick your bank" dropdown
// (Staff Registration, self-service profile, admin staff editor,
// Non-Academic Staff Pay) fetches through here instead of hitting
// /finance/banks itself, so a page with several of these fields (or several
// mounts across a session) only ever fetches it once. `code` is each bank's
// CBN sort code — see backend apps.admissions.paystack.list_banks.
let cached = null;
let inFlight = null;

export function getBanks() {
  if (cached) return Promise.resolve(cached);
  if (inFlight) return inFlight;
  inFlight = api
    .get('/finance/banks', { auth: false })
    .then((banks) => {
      cached = Array.isArray(banks) ? banks : [];
      return cached;
    })
    .catch(() => [])
    .finally(() => {
      inFlight = null;
    });
  return inFlight;
}

export function bankOptions(banks) {
  return (banks || []).map((b) => ({ value: b.code, label: b.name }));
}
