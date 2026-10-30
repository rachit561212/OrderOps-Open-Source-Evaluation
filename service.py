"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    out=deepcopy(order)
    if not isinstance(order, dict) or not isinstance(event, dict):
        return out
    event_id=event.get("event_id")
    kind=event.get("type")
    known_events={"payment_confirmed", "restaurant_accepted", "restaurant_rejected",
                  "cancel_requested", "dispatch_started", "order_delivered", "refund_processed"}
    if not isinstance(event_id, str) or not event_id.strip() or not isinstance(kind, str) or kind not in known_events:
        return out
    processed=out.setdefault("processed_event_ids", [])
    if not isinstance(processed, list):
        processed=[]
        out["processed_event_ids"]=processed
    if event_id in processed:
        return out
    out.setdefault("payment_status","UNPAID")
    out.setdefault("refund_due_paise",0)
    out.setdefault("refunded_paise",0)
    out.setdefault("processed_event_ids",[])

    # Deliberate starter defects: duplicate and invalid refund events are not
    # fully protected, and some transitions need tighter validation.
    if kind=="payment_confirmed":
        out["payment_status"]="PAID"
    elif kind=="restaurant_accepted" and out.get("status")=="PLACED":
        out["status"]="ACCEPTED"
    elif kind=="restaurant_rejected" and out.get("status")=="PLACED":
        out["status"]="REJECTED"
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    elif kind=="cancel_requested" and out.get("status") in ("PLACED","ACCEPTED"):
        out["status"]="CANCELLED"
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    elif kind=="dispatch_started" and out.get("status")=="ACCEPTED":
        out["status"]="OUT_FOR_DELIVERY"
    elif kind=="order_delivered" and out.get("status")=="OUT_FOR_DELIVERY":
        out["status"]="DELIVERED"
    elif kind=="refund_processed":
        # Bug to find: validate eligibility, positive amount and maximum refund.
        out["refunded_paise"] += event.get("amount_paise",0)
        if out["refunded_paise"] >= out.get("refund_due_paise",0):
            out["payment_status"]="REFUNDED"

    processed.append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left={r.get("order_id"):r for r in internal}
    right={r.get("order_id"):r for r in provider}
    report={"matched":[],"missing_from_provider":[],"missing_from_internal":[],
            "amount_mismatches":[],"status_mismatches":[]}
    for key in sorted(set(left)|set(right),key=lambda x:str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a,b=left[key],right[key]
            if a.get("amount_paise") != b.get("amount_paise"):
                report["amount_mismatches"].append(key)
            # Deliberate starter defect: mismatched statuses may be called matched.
            else:
                report["matched"].append(key)
    return report
