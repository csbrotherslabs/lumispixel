# Static asset deployment contract

LumisPixel builds static assets with WhiteNoise's `CompressedManifestStaticFilesStorage`.

## Release requirements

1. Run `python manage.py collectstatic --noinput --clear` from the exact application commit being released.
2. Treat any `collectstatic` failure as a failed release. Do not start or promote the web release with a partial or stale `STATIC_ROOT`.
3. Ship the generated `staticfiles.json`, hashed assets, and compressed variants with the same release as the Django templates and Python code that reference them.
4. Do not share or reuse a mutable `STATIC_ROOT` between different application releases.
5. Production must not override `DJANGO_STATICFILES_STORAGE`; the only accepted production backend is `whitenoise.storage.CompressedManifestStaticFilesStorage`.

Hashed asset URLs are content-addressed, so WhiteNoise may send long-lived immutable cache headers for them. Non-hashed static URLs keep a short cache lifetime.

CI runs a clean production-style `collectstatic` and the static deployment contract tests before a pull request can be merged.
