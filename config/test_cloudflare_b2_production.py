from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


class CloudflareB2ProductionContractTests(SimpleTestCase):
    def test_production_worker_is_separate_and_prefix_isolated(self):
        config = (ROOT / "cloudflare/media-worker/wrangler.jsonc").read_text(encoding="utf-8")
        self.assertIn('"name": "lumispixel-media-dev"', config)
        self.assertIn('"name": "lumispixel-media-prod"', config)
        self.assertIn('"B2_ALLOWED_PREFIX": "private/dev/"', config)
        self.assertIn('"B2_ALLOWED_PREFIX": "private/prod/"', config)

    def test_production_deployment_is_explicit_and_gated(self):
        workflow = (ROOT / ".github/workflows/deploy-cloudflare-media-production.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("environment: production", workflow)
        self.assertIn("wrangler deploy --env production", workflow)
        self.assertIn("npm ci", workflow)

    def test_worker_fails_closed_and_does_not_cache_origin_failures(self):
        worker = (ROOT / "cloudflare/media-worker/src/index.js").read_text(encoding="utf-8")
        self.assertIn('return textResponse("Media origin unavailable", 502)', worker)
        self.assertIn("originResponse.status === 200", worker)
        self.assertIn("if (!authorization.ok) return authorization.response", worker)
        self.assertIn("objectKey.startsWith(allowedPrefix)", worker)
