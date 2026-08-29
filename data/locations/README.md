# Location dataset

`countries_regions.json` is a reduced, application-ready snapshot of the
[`dr5hn/countries-states-cities-database`](https://github.com/dr5hn/countries-states-cities-database)
dataset. It contains only the identifiers, names, ISO codes, and administrative
region types LumisPixel needs.

- Upstream revision: `b3b49250ff3906f6119e16c088c0053a2c972926`
- License: Open Database License (ODbL) 1.0
- Import: `python manage.py import_locations`
- Validation only: `python manage.py import_locations --dry-run`

The importer is transactional, idempotent, and does not delete records that are
missing from a later snapshot.
