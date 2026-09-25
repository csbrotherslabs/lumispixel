# Generated for LumisPixel database integrity hardening.
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    dependencies = [("clients", "0023_contract_photographer_signature")]

    operations = [
        migrations.AddConstraint(model_name="clientinvoice", constraint=models.CheckConstraint(condition=Q(subtotal__gte=0), name="invoice_subtotal_nonnegative")),
        migrations.AddConstraint(model_name="clientinvoice", constraint=models.CheckConstraint(condition=Q(discount_total__gte=0), name="invoice_discount_nonnegative")),
        migrations.AddConstraint(model_name="clientinvoice", constraint=models.CheckConstraint(condition=Q(tax_total__gte=0), name="invoice_tax_nonnegative")),
        migrations.AddConstraint(model_name="clientinvoice", constraint=models.CheckConstraint(condition=Q(total__gte=0), name="invoice_total_nonnegative")),
        migrations.AddConstraint(model_name="clientinvoice", constraint=models.CheckConstraint(condition=Q(amount_paid__gte=0), name="invoice_paid_nonnegative")),
        migrations.AddConstraint(model_name="clientinvoice", constraint=models.CheckConstraint(condition=Q(amount_paid__lte=F("total")), name="invoice_paid_not_over_total")),
        migrations.AddConstraint(model_name="invoicelineitem", constraint=models.CheckConstraint(condition=Q(quantity__gt=0), name="invoice_line_quantity_positive")),
        migrations.AddConstraint(model_name="invoicelineitem", constraint=models.CheckConstraint(condition=Q(unit_price__gte=0), name="invoice_line_price_nonnegative")),
        migrations.AddConstraint(model_name="invoicelineitem", constraint=models.CheckConstraint(condition=Q(discount_percent__gte=0, discount_percent__lte=100), name="invoice_line_discount_percent_range")),
        migrations.AddConstraint(model_name="invoicelineitem", constraint=models.CheckConstraint(condition=Q(tax_percent__gte=0, tax_percent__lte=100), name="invoice_line_tax_percent_range")),
        migrations.AddConstraint(model_name="invoicelineitem", constraint=models.CheckConstraint(condition=Q(subtotal__gte=0), name="invoice_line_subtotal_nonnegative")),
        migrations.AddConstraint(model_name="invoicelineitem", constraint=models.CheckConstraint(condition=Q(total__gte=0), name="invoice_line_total_nonnegative")),
        migrations.AddConstraint(model_name="invoicepaymentschedule", constraint=models.CheckConstraint(condition=Q(amount__gt=0), name="invoice_schedule_amount_positive")),
        migrations.AddConstraint(model_name="invoicepayment", constraint=models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive")),
        migrations.AddConstraint(model_name="invoicepayment", constraint=models.CheckConstraint(condition=Q(processor_fee__gte=0), name="payment_fee_nonnegative")),
        migrations.AddConstraint(model_name="paymentrefund", constraint=models.CheckConstraint(condition=Q(amount__gt=0), name="refund_amount_positive")),
        migrations.AddConstraint(model_name="invoicecredit", constraint=models.CheckConstraint(condition=Q(amount__gt=0), name="credit_amount_positive")),
    ]
