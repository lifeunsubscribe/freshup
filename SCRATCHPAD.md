# Sharkrite Scratchpad

## Encountered Issues (Needs Triage)

- **2026-03-18** | `tests/routers/test_auth.py:test_register_password_exactly_128_characters` | test-failure | Password validation test expects 128-char passwords to be accepted but hash_password rejects passwords >72 bytes | Affects: User registration with long passwords | Fix: Either update test to expect 422 validation error or update password validation to truncate/reject at Pydantic level before hashing | Done: Test passes or validation is consistent across all layers
