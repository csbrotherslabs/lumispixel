# Performance regression CI gate

LumisPixel's performance contracts are executable tests rather than review-only expectations.

Run the targeted gate with:

```bash
python manage.py test config.test_performance_gate --verbosity 2
```

## Protected contracts

The gate fails when:

- large client galleries stop materializing a bounded page of photos;
- pagination query counts grow with the number of photos;
- album/photo preparation introduces N+1 database queries;
- upload validation regresses to assumptions that require in-memory uploads instead of seekable or disk-backed files;
- gallery presentation stops requesting explicit preview/thumbnail delivery variants.

The complete Django suite still discovers the underlying test modules. The targeted gate exists so CI can run these high-value performance contracts as an explicit checkpoint.

## Adding performance-sensitive features

Changes to gallery rendering, dashboard gallery cards, albums, analytics, uploads, media delivery, or other high-volume paths should add a regression test when they introduce a new performance contract. Prefer deterministic assertions such as query counts, bounded materialization, page sizes, and stream/file behavior over wall-clock timing, which is noisy in shared CI runners.
