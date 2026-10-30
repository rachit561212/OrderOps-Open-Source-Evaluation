# Testing record

## Environment and commands

- Python: 3.14
- The initial service edits predated this baseline run, so the committed starter `service.py` was temporarily restored to measure the original behavior and then the working version was restored.
- Baseline command against the original `service.py`: `.venv/bin/python -m pytest -q`
- Baseline result: **62 failed, 150 passed** (212 total).
- Post-change command: `.venv/bin/python -m pytest -q`
- Post-change result: **218 passed**.
- Demo command: `.venv/bin/python -m main` — completed successfully and printed missing-record, amount-mismatch, and status-mismatch findings for the synthetic fixtures.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test / evidence |
|---|---|---|---|---|
| 1 | Replay an already processed payment event | Event ID appears once; no second application | Passed | `test_payment_event_replay_idempotent` |
| 2 | Refund a placed unpaid order | No refund is recorded | Passed | `test_refund_eligibility_matrix`; `test_refund_requires_eligible_order` |
| 3 | Refund with zero, negative, fractional, boolean, string, missing, or over-due amount | Ignore invalid refund without changing totals | Passed | `test_invalid_refund_amounts_are_ignored`; `test_refund_must_be_positive`; `test_refund_cannot_exceed_amount_due` |
| 4 | Two valid partial refunds sum to more than due | Reject the second refund; refunded total never exceeds due | Passed | `test_refunds_cannot_exceed_due` |
| 5 | Payment confirmation arrives after cancellation | Mark payment paid and set full order total as due | Passed | `test_late_payment_after_cancellation_sets_refund_due` |
| 6 | Refund event is replayed | Apply the same refund once | Passed | `test_duplicate_refund_event_is_applied_only_once` |
| 7 | Refund amount is invalid, then corrected using the same event ID | Ignore first attempt; accept corrected retry | Passed | `test_invalid_refund_does_not_consume_event_id` |
| 8 | Provider record differs in amount and status; rows also include malformed/duplicate IDs | Report both mismatches; ignore malformed row and retain first duplicate | Passed | `test_reconciliation_reports_both_mismatch_types_and_ignores_bad_rows` |
| 9 | Event has no ID or has a non-string event type | Leave order unchanged without raising | Passed | `test_missing_event_id_is_ignored`; `test_unhashable_event_type_is_ignored` |

## Regression coverage added

Added tests for delayed payment after cancellation, missing IDs, unhashable event types, corrected refund retries, duplicate refund replays, and reconciliation with both mismatch types plus malformed/duplicate rows. Existing tests cover the broader transition matrix and refund boundaries.

## Remaining limitations

The reconciliation report has no category for malformed or duplicate rows, so they are ignored and the first duplicate ID is retained. Tests are local and use only synthetic records; no external payment service or concurrent execution is modeled.
