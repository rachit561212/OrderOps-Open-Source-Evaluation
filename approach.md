# Approach and implementation notes

> Preparation note: The organizer authorized AI assistance for this repository task. These notes describe the changes and checks completed here; review them before using them in an evaluation submission.

## Baseline

- Runtime: Python 3.14. The `python` command is not installed in this environment, so commands used `.venv/bin/python`.
- The initial service edits had already been made when this requested baseline was run. To measure the true starter state, the committed `service.py` was temporarily restored for the test run, then the working version was restored.
- Baseline command on the original committed `service.py`: `.venv/bin/python -m pytest -q`.
- Baseline result: **62 failed, 150 passed** (212 total). The most frequent failure was replaying a processed event; other groups covered refund eligibility and limits, plus reconciliation status mismatches.
- The baseline demo ran and exposed the fixture mismatches; the starter's status comparison did not report `ORD-102`'s status difference.

## Code path reviewed

`main.py` calls `reconcile_orders` using synthetic records from `fixtures.py`. `apply_order_event` handles order/payment state changes and tracks processed event IDs; `reconcile_orders` compares internal and provider rows by order ID. The acceptance tests exercise transitions, refund bounds, event replays, and reconciliation cases.

## Changes made

- Added event ID and event type checks, and ignored replays of previously processed IDs.
- Kept the existing valid order transitions and protected cancellation after dispatch.
- Restricted refunds to paid cancelled/rejected orders. Refund inputs must be positive integer paise and fit within the outstanding due. Partial refunds remain `PAID`; the full refund changes payment status to `REFUNDED`.
- Accounted for a payment confirmation arriving after cancellation or rejection by setting the valid order total as refund due.
- Reported amount and status mismatches independently. Reconciliation ignores malformed rows, keeps the first row for duplicate IDs, and returns IDs in sorted order.
- Added regression cases for late payment, missing IDs, malformed event types, corrected refund retries, duplicate refund events, and rows with both amount and status mismatches.

## Verification

After the changes, `.venv/bin/python -m pytest -q` reported **218 passed**. `.venv/bin/python -m main` completed and reported the expected fixture discrepancies: `ORD-103` missing from provider, `ORD-104` missing internally, amount mismatches for `ORD-101` and `ORD-102`, and a status mismatch for `ORD-102`.

## Assumptions and limitations

Refunds apply only to cancelled or rejected paid orders. Only the first record for a duplicate order ID is reconciled; the report format has no duplicate-record category. The implementation is an in-memory example, not a durable event store or payment-provider integration.
