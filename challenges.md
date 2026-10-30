# Challenges and debugging notes

> Preparation note: These notes document AI-assisted work authorized by the repository organizer. Check the details against the final diff before using them in an evaluation submission.

## What was tricky

The starter mixed three concerns in `apply_order_event`: state transitions, event replay handling, and refund accounting. A replay looked harmless for payment status, but it duplicated the event ID; refund events could also add invalid amounts. That made it important to check the entire result, not only the visible order state.

## Evidence and root causes

Running the original `service.py` against the unchanged tests produced **62 failures and 150 passes**. The failures showed that event IDs were appended on every call, refund amounts were added without eligibility or bounds checks, and reconciliation could put a record with a different status into `matched`.

The refund amount inputs include values such as `True`, `0.5`, `None`, strings and amounts above the due. Python treats `bool` as a subclass of `int`, so checking only `isinstance(value, int)` would still accept `True`; the implementation explicitly excludes booleans.

## Resolution

The service now ignores missing IDs, unknown event types, and duplicate IDs; validates refund eligibility and outstanding balance; and marks a refund complete only when refunded equals due. Reconciliation evaluates amount and status separately. New tests cover malformed event types, missing IDs, late payment, invalid-refund retry, duplicate refunds, and malformed/duplicate reconciliation rows.

The post-change test run reported **218 passed**. The offline demo also completed and showed its fixture mismatches in the separate missing, amount, and status categories.

## Remaining limitations

The reconciliation API has no field for duplicate or malformed-row diagnostics, so invalid rows are ignored and the first duplicate order ID wins. There is no persistence, concurrency protection, or external payment integration; those would need separate design and tests in a production system.
