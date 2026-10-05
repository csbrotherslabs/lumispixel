# Inbox event delivery

These events use the existing Notification table, /notifications/ page, navbar unread badge and latest-15 drawer. Delivery does not mark a notification read. It does not send additional email.

| Source | Events and recipients |
| --- | --- |
| Gallery invitations | Existing gallery sharing notification to an invited registered client |
| Gallery analytics | Favorites, comments, photo/gallery downloads and purchases to the gallery owner; self activity excluded |
| Gallery activity | Completed upload batches and completed AI processing to the owner |
| Bookings/consultations | Creation, status changes and rescheduling to the owner and explicitly linked client account |
| Contracts | Sent, signed and voided to owner and linked client |
| Invoices/payments | Invoice sent/voided, payment completed/failed/canceled to owner and linked client |
| CRM | New leads and due follow-ups/tasks to the photographer |
| Teams | Sent/resent invitations to registered invitees; accepted/declined/revoked events to the studio owner |
| Accounts/billing | Password changes to the account; subscription status changes to the owner |
| Support | Public staff replies and ticket status changes to requester; internal comments never sent |
| Uploads | Persisted failed photo processing and stopped multipart uploads to owner |
| Internal operations | Existing staff ticket, approval and system health notifications remain connected |

Hourly reminders: confirmed sessions in the next 24 hours; unpaid sent/partially-paid invoices overdue in the photographer's time zone (respect reminders_enabled); unsigned contracts at least 3 days after sending; due lead follow-ups and open tasks; published/delivered galleries expiring in 3 days (owner and active registered invitees); numeric plan storage at 90% or full (daily maximum per threshold/allowance). Unlimited/custom allowances are excluded. Upload error scan catches bulk updates within the last 24 hours.

NotificationEventReceipt has a unique recipient/event key and survives notification dismissal. This prevents repeat scans or event retries from recreating dismissed notifications. Writes share the originating transaction, so a rolled-back event leaves no notification. Client deliveries use Client.user and require the client and workflow object to belong to the same photographer; email guesses do not link private booking or billing records.

## Run

Run `python manage.py migrate` before exercising these workflows. Instant events are handled in-process. Run a Celery worker and Celery beat for the hourly `apps.notifications.tasks.scan_notification_reminders` task. Restart both after deployment. For local testing or a cron alternative, use `python manage.py scan_notification_reminders`. Existing pending email delivery behavior is unchanged.

The application does not yet implement gallery access requests, contract decline events, or suspicious/new-device sign-in detection. There is no truthful source to connect for these events until their workflows exist. External clients without a LumisPixel account cannot receive an in-app inbox notification; existing email delivery remains responsible for their communications.

Notification hooks observe ordinary model saves and persisted gallery/team audit events. New bulk writes must emit an audit event or use the scan path explicitly; Django does not send post_save for QuerySet.update/bulk_create.
