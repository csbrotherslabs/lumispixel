# Transactional email delivery contract

All new transactional email paths should call `queue_transactional_email` instead of sending SMTP inside a request.

- Supply a stable, event-specific `event_key` (for example `booking:<id>:created` or `support:<ticket>:reply:<comment>`).
- The outbox row is written in the caller's database transaction.
- Celery dispatch occurs only in `transaction.on_commit`.
- Broker failure leaves the row pending instead of failing the user request.
- SMTP failure leaves the row pending and Celery retries with bounded exponential backoff.
- A sent row is idempotent: duplicate task execution will not intentionally send it again.
- `python manage.py retry_transactional_email` can re-enqueue pending rows after an outage.

Do not use a generic event key for repeated events such as comments/replies; include the immutable event object's identifier.