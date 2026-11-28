from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from django.core.exceptions import ValidationError

SUPPORTED_CURRENCIES = frozenset({"USD", "CAD", "GBP", "EUR", "AUD", "NZD", "CHF", "GHS", "NGN", "ZAR", "INR", "AED"})


def parse_payment_terms(data, currency):
    def amount(raw):
        value = Decimal(raw)
        if not value.is_finite() or value < 0 or value >= Decimal("10000000000") or value != value.quantize(Decimal(".01")):
            raise ValueError
        return value
    currency = data.get("payment_currency") or currency
    if currency not in SUPPORTED_CURRENCIES:
        raise ValidationError("Select a supported currency.")
    try:
        total = amount(data.get("price", ""))
        if total == 0 and data.get("complimentary") != "on":
            raise ValueError
        deposit = Decimal("0")
        if data.get("deposit_required") == "on":
            raw = amount(data.get("deposit_input", ""))
            if data.get("deposit_type") == "percentage":
                if raw > 100:
                    raise ValueError
                deposit = (total * raw / 100).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
            else:
                deposit = raw
            if not 0 < deposit <= total:
                raise ValueError
        deposit_due = date.fromisoformat(data.get("deposit_due_date", "")) if deposit else None
        balance_due = date.fromisoformat(data.get("balance_due_date", "")) if total > deposit else None
        if deposit_due and balance_due and deposit_due > balance_due:
            raise ValueError
    except (ValueError, ArithmeticError, TypeError):
        raise ValidationError("Enter an agreed fee, valid down payment and required payment dates. A zero fee requires complimentary confirmation.")
    return dict(booking_value=total, pricing_confirmed=True, payment_currency=currency, deposit_amount=deposit, deposit_due_date=deposit_due, balance_due_date=balance_due)

def payment_clause(booking):
    if not booking.pricing_confirmed:
        return "Payment terms have not yet been confirmed. This draft is not ready for signature."
    currency = booking.payment_currency
    total = Decimal(str(booking.booking_value))
    deposit = Decimal(str(booking.deposit_amount))
    def money(value):
        return f"{currency} {value:,.2f}"
    if total == 0:
        return "The photography session is complimentary. No service fee, down payment or remaining balance is payable."
    opening = f"The Client agrees to pay the Photographer a total service fee of {money(total)}."
    if not deposit:
        return f"{opening} No down payment is required. The full fee is payable on or before {booking.balance_due_date:%B %d, %Y}."
    advance = f"A down payment of {money(deposit)} is payable on or before {booking.deposit_due_date:%B %d, %Y} and will be credited toward the total service fee."
    if deposit == total:
        return f"{opening} {advance} No further service fee balance is payable."
    return f"{opening} {advance} The remaining balance of {money(total-deposit)} is payable on or before {booking.balance_due_date:%B %d, %Y}."

def payment_snapshot(booking):
    total = Decimal(str(booking.booking_value))
    deposit = Decimal(str(booking.deposit_amount))
    return {"pricing_confirmed": booking.pricing_confirmed, "currency": booking.payment_currency,
            "total": format(total, ".2f"), "deposit": format(deposit, ".2f"),
            "balance": format(total - deposit, ".2f"),
            "deposit_due": str(booking.deposit_due_date or ""), "balance_due": str(booking.balance_due_date or "")}

def validate_saved_payment_terms(booking):
    if not booking.pricing_confirmed or booking.payment_currency not in SUPPORTED_CURRENCIES:
        raise ValidationError("Save agreed pricing and payment terms before signing.")
    try:
        total, deposit = Decimal(str(booking.booking_value)), Decimal(str(booking.deposit_amount))
    except (ArithmeticError, ValueError, TypeError):
        raise ValidationError("The saved payment schedule is incomplete or invalid.")
    if not total.is_finite() or not deposit.is_finite():
        raise ValidationError("The saved payment schedule is incomplete or invalid.")
    if total < 0 or deposit < 0 or deposit > total or (deposit and not booking.deposit_due_date) or (total > deposit and not booking.balance_due_date):
        raise ValidationError("The saved payment schedule is incomplete or invalid.")
    if booking.deposit_due_date and booking.balance_due_date and booking.deposit_due_date > booking.balance_due_date:
        raise ValidationError("The down payment deadline must precede or equal the balance deadline.")
