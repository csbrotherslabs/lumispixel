import base64
import io

import qrcode
from django import template
from django.utils.safestring import mark_safe
from qrcode.image.svg import SvgPathImage

register = template.Library()


def _qr_code(value):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(value)
    qr.make(fit=True)
    return qr


def qr_png_data_uri(value):
    if not value:
        return ""
    buffer = io.BytesIO()
    _qr_code(value).make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def qr_svg_data_uri(value):
    if not value:
        return ""
    buffer = io.BytesIO()
    _qr_code(value).make_image(image_factory=SvgPathImage).save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


@register.simple_tag
def gallery_qr_png(value):
    return mark_safe(qr_png_data_uri(value))


@register.simple_tag
def gallery_qr_svg(value):
    return mark_safe(qr_svg_data_uri(value))
