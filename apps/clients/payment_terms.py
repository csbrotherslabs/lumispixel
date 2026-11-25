from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from django.core.exceptions import ValidationError

def parse_payment_terms(data, currency):
    def amount(raw):
        value = Decimal(raw)
        if not value.is_finite() or value < 0 or value >= Decimal("10000000000") or value != value.quantize(Decimal(".01")):
            raise ValueError
        return value
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
        return "Payment terms not yet confirmed."
    currency = booking.payment_currency
    total = booking.booking_value
    deposit = booking.deposit_amount
    lines = [f"Total agreed service fee: {currency} {total:,.2f}."]
    if deposit:
        lines.append(f"Down payment: {currency} {deposit:,.2f}, due {booking.deposit_due_date:%B %d, %Y}.")
    else:
        lines.append("No down payment is required.")
    if total > deposit:
        lines.append(f"Remaining balance: {currency} {total-deposit:,.2f}, due {booking.balance_due_date:%B %d, %Y}.")
    return "\n".join(lines)
