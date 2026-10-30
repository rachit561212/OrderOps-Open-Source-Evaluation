import pytest
from models import new_order
from service import apply_order_event, reconcile_orders


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


@pytest.mark.parametrize("status,kind,expected", [
    ("PLACED","restaurant_accepted","ACCEPTED"),
    ("ACCEPTED","restaurant_accepted","ACCEPTED"),
    ("REJECTED","restaurant_accepted","REJECTED"),
    ("CANCELLED","restaurant_accepted","CANCELLED"),
    ("OUT_FOR_DELIVERY","restaurant_accepted","OUT_FOR_DELIVERY"),
    ("DELIVERED","restaurant_accepted","DELIVERED"),
    ("PLACED","restaurant_rejected","REJECTED"),
    ("ACCEPTED","restaurant_rejected","ACCEPTED"),
    ("REJECTED","restaurant_rejected","REJECTED"),
    ("CANCELLED","restaurant_rejected","CANCELLED"),
    ("OUT_FOR_DELIVERY","restaurant_rejected","OUT_FOR_DELIVERY"),
    ("DELIVERED","restaurant_rejected","DELIVERED"),
    ("PLACED","cancel_requested","CANCELLED"),
    ("ACCEPTED","cancel_requested","CANCELLED"),
    ("REJECTED","cancel_requested","REJECTED"),
    ("CANCELLED","cancel_requested","CANCELLED"),
    ("OUT_FOR_DELIVERY","cancel_requested","OUT_FOR_DELIVERY"),
    ("DELIVERED","cancel_requested","DELIVERED"),
    ("PLACED","dispatch_started","PLACED"),
    ("ACCEPTED","dispatch_started","OUT_FOR_DELIVERY"),
    ("OUT_FOR_DELIVERY","dispatch_started","OUT_FOR_DELIVERY"),
    ("DELIVERED","dispatch_started","DELIVERED"),
    ("PLACED","order_delivered","PLACED"),
    ("ACCEPTED","order_delivered","ACCEPTED"),
    ("OUT_FOR_DELIVERY","order_delivered","DELIVERED"),
    ("CANCELLED","order_delivered","CANCELLED"),
])
def test_order_state_transition_matrix(status, kind, expected):
    order = new_order("O", 5000, status)
    result = apply_order_event(order, ev("E", kind))
    assert result["status"] == expected


@pytest.mark.parametrize("event_id", [f"EV-{i:03}" for i in range(20)])
def test_payment_event_replay_idempotent(event_id):
    order = new_order("O", 5000)
    event = ev(event_id, "payment_confirmed")
    once = apply_order_event(order, event)
    twice = apply_order_event(once, event)
    assert twice["payment_status"] == "PAID"
    assert twice["processed_event_ids"] == [event_id]


@pytest.mark.parametrize("amount", [1, 10, 100, 500, 999, 1000, 1500, 2500, 4999, 5000])
def test_valid_partial_and_full_refunds(amount):
    order = new_order("O", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)
    result = apply_order_event(order, ev("R", "refund_processed", amount_paise=amount))
    assert result["refunded_paise"] == amount
    assert result["payment_status"] == ("REFUNDED" if amount == 5000 else "PAID")


@pytest.mark.parametrize("amount", [0, -1, -10, 0.5, True, None, "10", [], {}, 5001, 6000, 10000, -5000, 2.2, False])
def test_invalid_refund_amounts_are_ignored(amount):
    order = new_order("O", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)
    result = apply_order_event(order, ev("R", "refund_processed", amount_paise=amount))
    assert result["refunded_paise"] == 0
    assert result["payment_status"] == "PAID"


@pytest.mark.parametrize("status,payment_status,due", [
    ("PLACED","UNPAID",0), ("PLACED","PAID",0),
    ("ACCEPTED","PAID",0), ("OUT_FOR_DELIVERY","PAID",0),
    ("DELIVERED","PAID",0), ("REJECTED","UNPAID",0),
    ("CANCELLED","UNPAID",0), ("REJECTED","PAID",5000),
    ("CANCELLED","PAID",5000), ("REJECTED","REFUNDED",5000),
    ("CANCELLED","REFUNDED",5000), ("FAILED","PAID",5000),
])
def test_refund_eligibility_matrix(status, payment_status, due):
    order = new_order("O", 5000, status)
    order.update(payment_status=payment_status, refund_due_paise=due)
    result = apply_order_event(order, ev("R", "refund_processed", amount_paise=1000))
    if status in ("REJECTED","CANCELLED") and payment_status == "PAID" and due > 0:
        assert result["refunded_paise"] == 1000
    else:
        assert result["refunded_paise"] == 0


@pytest.mark.parametrize("first,second", [
    (1,1),(100,200),(1000,1000),(2500,2500),(4999,1),
    (3000,2000),(4000,2000),(4900,100),(2000,3500),(1000,4500),
    (4500,500),(2500,2501),(1234,4321),(3333,1667),(1,5000),
    (5000,1),(999,4001),(4001,999),(250,4750),(2750,2250),
])
def test_refunds_cannot_exceed_due(first, second):
    order = new_order("O", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)
    one = apply_order_event(order, ev("R1", "refund_processed", amount_paise=first))
    two = apply_order_event(one, ev("R2", "refund_processed", amount_paise=second))
    expected = first + second if first + second <= 5000 else first
    assert two["refunded_paise"] == expected
    assert two["refunded_paise"] <= 5000


@pytest.mark.parametrize("left,right", [
    ("PLACED","PLACED"),("PLACED","ACCEPTED"),("PLACED","CANCELLED"),
    ("ACCEPTED","ACCEPTED"),("ACCEPTED","DELIVERED"),("REJECTED","CANCELLED"),
    ("CANCELLED","CANCELLED"),("OUT_FOR_DELIVERY","DELIVERED"),("DELIVERED","DELIVERED"),
    ("FAILED","PENDING"),("REFUNDED","PAID"),("PAID","PAID"),
])
def test_reconciliation_status_mismatch_matrix(left, right):
    report = reconcile_orders(
        [{"order_id":"O","amount_paise":5000,"status":left}],
        [{"order_id":"O","amount_paise":5000,"status":right}],
    )
    if left == right:
        assert report["matched"] == ["O"]
        assert report["status_mismatches"] == []
    else:
        assert report["matched"] == []
        assert report["status_mismatches"] == ["O"]


@pytest.mark.parametrize("a,b", [
    (1,2),(2,1),(99,100),(100,99),(999,1000),(1000,999),
    (4999,5000),(5000,4999),(10000,10001),(10001,10000),
    (45900,45000),(89900,89901),(129900,0),(0,129900),(25,250),
    (250,25),(10,5000),(5000,10),(12345,54321),(700,701),
])
def test_reconciliation_amount_mismatch_matrix(a, b):
    report = reconcile_orders(
        [{"order_id":"O","amount_paise":a,"status":"PLACED"}],
        [{"order_id":"O","amount_paise":b,"status":"PLACED"}],
    )
    assert report["amount_mismatches"] == ["O"]
    assert report["matched"] == []


@pytest.mark.parametrize("oid", [f"INT-{i:02}" for i in range(15)])
def test_internal_only_order_is_reported(oid):
    report = reconcile_orders([{"order_id":oid,"amount_paise":1,"status":"PLACED"}], [])
    assert report["missing_from_provider"] == [oid]


@pytest.mark.parametrize("oid", [f"PROV-{i:02}" for i in range(15)])
def test_provider_only_order_is_reported(oid):
    report = reconcile_orders([], [{"order_id":oid,"amount_paise":1,"status":"PLACED"}])
    assert report["missing_from_internal"] == [oid]


@pytest.mark.parametrize("n", range(1, 11))
def test_reconciliation_results_are_deterministic(n):
    ids = [f"O-{i:02}" for i in range(n)]
    rows = [{"order_id":oid,"amount_paise":100,"status":"PLACED"} for oid in reversed(ids)]
    report = reconcile_orders(rows, rows)
    assert report["matched"] == sorted(ids)


@pytest.mark.parametrize("kind", ["", "unknown", "refund", None, 1, "PAYMENT_CONFIRMED", "chargeback", "cancel", "delivery", "refund_processed_v2"])
def test_unknown_event_does_not_mutate_order_state(kind):
    order = new_order("O", 5000)
    result = apply_order_event(order, ev("E", kind, amount_paise=3000))
    assert result["status"] == "PLACED"
    assert result["refunded_paise"] == 0


@pytest.mark.parametrize("total", [1, 10, 100, 500, 1000, 2500, 5000, 9999, 10000, 99999])
def test_refund_due_uses_full_order_total_on_paid_rejection(total):
    order = new_order("O", total)
    order["payment_status"] = "PAID"
    result = apply_order_event(order, ev("E", "restaurant_rejected"))
    assert result["refund_due_paise"] == total
    assert result["status"] == "REJECTED"


@pytest.mark.parametrize("kind", ["restaurant_accepted","restaurant_rejected","cancel_requested","dispatch_started","order_delivered"])
def test_input_order_is_not_mutated(kind):
    initial = "OUT_FOR_DELIVERY" if kind == "order_delivered" else "PLACED"
    order = new_order("O", 1000, initial)
    before = dict(order)
    apply_order_event(order, ev("E", kind))
    assert order == before


def test_late_payment_after_cancellation_sets_refund_due():
    order = new_order("O", 2500, "CANCELLED")
    result = apply_order_event(order, ev("PAY", "payment_confirmed"))
    assert result["payment_status"] == "PAID"
    assert result["refund_due_paise"] == 2500


def test_missing_event_id_is_ignored():
    order = new_order("O", 2500)
    result = apply_order_event(order, {"type": "payment_confirmed"})
    assert result == order


def test_unhashable_event_type_is_ignored():
    order = new_order("O", 2500)
    result = apply_order_event(order, ev("E", ["payment_confirmed"]))
    assert result == order


def test_invalid_refund_does_not_consume_event_id():
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    invalid = apply_order_event(order, ev("R", "refund_processed", amount_paise=-1))
    corrected = apply_order_event(invalid, ev("R", "refund_processed", amount_paise=1000))
    assert corrected["refunded_paise"] == 1000
    assert corrected["payment_status"] == "REFUNDED"


def test_duplicate_refund_event_is_applied_only_once():
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    refund = ev("R", "refund_processed", amount_paise=400)
    once = apply_order_event(order, refund)
    replayed = apply_order_event(once, refund)
    assert replayed["refunded_paise"] == 400
    assert replayed["processed_event_ids"] == ["R"]


def test_reconciliation_reports_both_mismatch_types_and_ignores_bad_rows():
    report = reconcile_orders(
        [None, {"order_id": "O", "amount_paise": 100, "status": "PLACED"}],
        [
            {"order_id": "O", "amount_paise": 90, "status": "CANCELLED"},
            {"order_id": "O", "amount_paise": 1, "status": "DELIVERED"},
            {"order_id": None, "amount_paise": 0, "status": "UNKNOWN"},
        ],
    )
    assert report["amount_mismatches"] == ["O"]
    assert report["status_mismatches"] == ["O"]
    assert report["matched"] == []
