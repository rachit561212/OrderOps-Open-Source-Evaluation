# Order flow notes

The sequence below uses a synthetic order worth 5,000 paise. Each event has a distinct ID.

| Step | Event | Expected state | Observed state |
|---|---|---|---|
| 1 | Start with `new_order("O-1", 5000)` | `PLACED`, `UNPAID`, due 0, refunded 0 | Same |
| 2 | `payment_confirmed` | `PLACED`, `PAID`, due 0, refunded 0 | Same |
| 3 | `restaurant_accepted` | `ACCEPTED`, `PAID`, due 0, refunded 0 | Same |
| 4 | `cancel_requested` before dispatch | `CANCELLED`, `PAID`, due 5,000, refunded 0 | Same |
| 5 | `refund_processed` for 2,000 paise | `CANCELLED`, `PAID`, due 5,000, refunded 2,000 | Same; partial refund remains `PAID` |
| 6 | `refund_processed` for 3,000 paise | `CANCELLED`, `REFUNDED`, due 5,000, refunded 5,000 | Same; full due has been refunded |

## Edge cases checked

1. **Cancellation after dispatch:** an order in `OUT_FOR_DELIVERY` stays in that state when cancellation is requested (`test_order_state_transition_matrix`).
2. **Duplicate refund notification:** replaying the same refund event ID does not add the refund twice (`test_duplicate_refund_event_is_applied_only_once`).
3. **Late payment after cancellation:** payment confirmation sets the paid order's full valid total as refund due (`test_late_payment_after_cancellation_sets_refund_due`).

## Assumptions and limitations

- Cancellation is allowed from `PLACED` and `ACCEPTED`; dispatch and delivery transitions require the expected preceding state.
- A rejected or cancelled paid order is refundable up to its full order total. Partial refunds remain distinct from full completion.
- Refund and total amounts are integer paise. This in-memory service does not model payment-provider delays beyond the late payment event, persistence, or concurrent updates.
- Reconciliation ignores malformed rows and keeps the first record for duplicate order IDs because its current return shape has no anomaly bucket.
