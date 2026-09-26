import contextvars
import logging
import re
import uuid


_request_id = contextvars.ContextVar("request_id", default="-")
_SENSITIVE = re.compile(
    r"(?i)(authorization|cookie|password|passwd|secret|token|api[_-]?key|access[_-]?key)"
    r"(\s*[=:]\s*)([^\s,;]+)"
)


def redact(value):
    if value is None:
        return value
    return _SENSITIVE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", str(value))


class SensitiveDataFilter(logging.Filter):
    """Attach correlation data and redact common secret assignments."""

    def filter(self, record):
        record.request_id = getattr(record, "request_id", None) or _request_id.get()
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
        record.msg = redact(rendered)
        record.args = ()
        return True


class RequestIDMiddleware:
    header_name = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.META.get(self.header_name, "").strip()
        request_id = supplied[:128] if supplied else uuid.uuid4().hex
        token = _request_id.set(request_id)
        request.request_id = request_id
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            _request_id.reset(token)
