import hashlib
import hmac
import logging

import requests
from django.core.cache import cache

from apps.settings_app.models import SystemSetting

logger = logging.getLogger(__name__)

BASE_URL = "https://api.paystack.co"
_BANKS_CACHE_KEY = "paystack:banks:ngn"
_BANKS_CACHE_TTL = 86400  # a day — bank codes change rarely; avoids hitting Paystack from every public form load


def _secret_key():
    setting = SystemSetting.objects.filter(key="payments.paystack.secret_key").first()
    return setting.get_decrypted_value() if setting else None


def is_configured():
    return bool(_secret_key())


def initialize_transaction(email, amount_naira, reference, callback_url):
    """Calls Paystack's real "Initialize Transaction" API. Returns the
    response dict (has "authorization_url"/"access_code"/"reference") or
    None if Paystack isn't configured or the call fails — callers fall back
    to manual/offline payment instructions in that case."""
    secret_key = _secret_key()
    if not secret_key:
        return None
    try:
        resp = requests.post(
            f"{BASE_URL}/transaction/initialize",
            headers={"Authorization": f"Bearer {secret_key}"},
            json={
                "email": email,
                "amount": int(amount_naira * 100),  # Paystack amounts are in kobo, not Naira
                "reference": reference,
                "callback_url": callback_url,
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("status"):
            logger.warning("Paystack initialize returned status=false: %s", payload.get("message"))
            return None
        return payload["data"]
    except requests.RequestException:
        logger.exception("Paystack initialize_transaction request failed.")
        return None


def verify_transaction(reference):
    """Calls Paystack's "Verify Transaction" API — used as the required
    second check after webhook signature verification, per Paystack's own
    guidance, so a validly-signed-but-stale/forged event body can't be
    trusted on its own."""
    secret_key = _secret_key()
    if not secret_key:
        return None
    try:
        resp = requests.get(
            f"{BASE_URL}/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {secret_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("status"):
            return None
        return payload["data"]
    except requests.RequestException:
        logger.exception("Paystack verify_transaction request failed.")
        return None


def list_banks():
    """Every Nigerian bank Paystack knows about — the shared source of truth
    for the payout sheet's "CBN Sort code" column, since Paystack's own
    `code` field for each bank *is* the standard NIP/CBN institution code.
    Staff pick a bank by name; the code that actually lands in the export
    is resolved from this list, never typed by hand. Cached because this is
    reachable from the public, unauthenticated Staff Registration form."""
    cached = cache.get(_BANKS_CACHE_KEY)
    if cached is not None:
        return cached
    secret_key = _secret_key()
    if not secret_key:
        return []
    try:
        resp = requests.get(
            f"{BASE_URL}/bank",
            headers={"Authorization": f"Bearer {secret_key}"},
            params={"currency": "NGN", "country": "nigeria", "perPage": 200},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("status"):
            return []
    except requests.RequestException:
        logger.exception("Paystack list_banks request failed.")
        return []

    banks = sorted(
        (
            {"name": b["name"], "code": b["code"]}
            for b in payload.get("data", [])
            if b.get("code") and b.get("active", True)
        ),
        key=lambda b: b["name"],
    )
    cache.set(_BANKS_CACHE_KEY, banks, _BANKS_CACHE_TTL)
    return banks


def verify_signature(raw_body, signature_header):
    """Paystack webhook contract: x-paystack-signature is HMAC-SHA512 of the
    raw request body, keyed with the secret key. Must be computed over the
    exact raw bytes, not a re-serialized version, and compared in constant
    time."""
    secret_key = _secret_key()
    if not secret_key or not signature_header:
        return False
    expected = hmac.new(secret_key.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature_header)
