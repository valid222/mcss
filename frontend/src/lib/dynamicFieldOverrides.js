import { NIGERIA_STATE_OPTIONS, lgaOptionsForState } from './nigeriaStatesLgas.js';
import { bankOptions } from './banks.js';

const ACCOUNT_TYPE_OPTIONS = [
  { value: 'Savings', label: 'Savings' },
  { value: 'Current', label: 'Current' },
];

// Bank/payout fields HR fills in while preparing payroll, not something a
// staff member entering their own bank details should ever see or need —
// see finance.services.BANK_CUSTOM_FIELD_KEYS on the backend for the full
// set account_number/account_type/sort_code feed into on the payout sheet.
export const STAFF_HIDDEN_BANK_KEYS = ['payment_reference', 'beneficiary_code', 'is_cashcard'];

/** A `getValue(key)` accessor for a dynamic custom-fields array whose
 * values are keyed by field_id (StaffOnboarding, DynamicProfileFields,
 * UserManagementPage all work this way) — resolves a sibling field's
 * current value by its `key` slug instead of the caller needing to know
 * its field_id. */
export function valueGetterByKey(fields, valuesByFieldId) {
  const fieldIdByKey = Object.fromEntries(fields.map((f) => [f.key, f.field_id]));
  return (key) => valuesByFieldId[fieldIdByKey[key]];
}

/** One field definition (must carry `.key`), swapped for a smarter control
 * than its own stored field_type when it's one of a handful of well-known
 * "staff" custom-field keys — without changing what's actually stored or
 * exported:
 *  - sort_code -> a bank-name dropdown (the value stored is still the
 *    bank's CBN sort code; staff never see or type the code itself)
 *  - account_type -> a Savings/Current dropdown
 *  - state -> every Nigerian state
 *  - lga -> every LGA in whichever state is currently selected
 * Every other field passes through unchanged. `getValue(key)` resolves a
 * sibling field's current value (used by `lga` to filter against `state`).
 * See apps.admissions.paystack.list_banks (the bank list's source) and
 * nigeriaStatesLgas.js (the state/LGA dataset). */
export function overrideDynamicField(field, getValue, { banks } = {}) {
  switch (field.key) {
    case 'sort_code':
      return { ...field, type: 'select', label: field.label || 'Bank', options: bankOptions(banks) };
    case 'account_type':
      return { ...field, type: 'select', options: ACCOUNT_TYPE_OPTIONS };
    case 'state':
      return { ...field, type: 'select', options: NIGERIA_STATE_OPTIONS };
    case 'lga':
      return { ...field, type: 'select', options: lgaOptionsForState(getValue('state')) };
    default:
      return field;
  }
}

/** overrideDynamicField applied across a whole fields array at once —
 * the common case every call site actually wants. */
export function overrideDynamicFields(fields, valuesByFieldId, { banks } = {}) {
  const getValue = valueGetterByKey(fields, valuesByFieldId);
  return fields.map((f) => overrideDynamicField(f, getValue, { banks }));
}

/** Best-effort "full name" from Biodata first/middle/last-name custom
 * field answers, or null if they're blank (the Super Admin hasn't added
 * those fields yet, or the applicant hasn't filled them in) — lets a form
 * derive the legacy hardcoded full_name payload key from the new dynamic
 * Biodata fields instead of asking for a name twice. */
export function deriveFullName(getValue) {
  const parts = [getValue('first_name'), getValue('middle_name'), getValue('last_name')].filter(Boolean);
  return parts.length ? parts.join(' ') : null;
}
