"""Release the ORM connection only at a safe inference boundary."""
from django.db import connections


def release_inference_connection(using="default"):
    connection = connections[using]
    # Eager tasks and tests may run inside a caller-owned transaction.
    # Never close a connection with an open transaction or disabled autocommit.
    if connection.connection is not None and not connection.in_atomic_block and connection.get_autocommit():
        connection.close()
