# Optimizations and trade-offs

> Preparation note: The organizer authorized AI assistance for this repository task. No performance improvement is claimed without a benchmark.

## Objective

The main need was safer and easier-to-follow event processing. The starter already handled small in-memory lists; there was no measured performance problem to justify a more complex design.

## Changes made

- Kept the service synchronous and in memory, with direct transition conditions and a small integer-amount helper. This makes the state rules visible without adding a framework.
- Built order-ID indexes once before reconciliation, then sorted the combined IDs. This avoids rescanning every row for every order and gives repeatable report ordering.
- Added input checks at the event and reconciliation boundaries so malformed values do not crash the flow or affect totals.

The full visible suite passed after the changes (**218 passed**). No timing or memory benchmark was run, so no speedup is claimed.

## Trade-offs and next steps

Keeping the first duplicate reconciliation row is simple and deterministic, but it hides later duplicates because the current report schema cannot describe them. A follow-up could add a duplicate/malformed-record section and test its semantics. For high-volume or concurrent use, persistent event storage and atomic refund updates would be necessary; that is beyond this offline starter.
