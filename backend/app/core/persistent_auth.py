"""Explicitly opted-in, owner-bound access until logout/revocation.

The sentinel is storage-only, not a real event date. Browser cookies roll within
the browser's 400-day cap; the OAuth wire TTL stays within signed 32-bit limits.
"""
UNTIL_REVOKED_EPOCH = 253370736000  # 9999-01-01 UTC; safe in Asia/Shanghai.
COOKIE_MAX_AGE = 400 * 86400
OAUTH_MAX_AGE = 2147483647
