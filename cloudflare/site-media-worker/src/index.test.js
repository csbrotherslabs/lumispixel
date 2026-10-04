import assert from "node:assert/strict";
import test from "node:test";
import { allowedSiteKey } from "./index.js";

test("only site image namespaces in the selected environment are public", () => {
  assert.equal(allowedSiteKey("site/prod/client-profiles/avatar.png", "site/prod/"), true);
  assert.equal(allowedSiteKey("site/prod/photographer_websites/2/hero/image.webp", "site/prod/"), true);
  for (const key of [
    "site/dev/client-profiles/avatar.png", "private/prod/galleries/1/image.jpg",
    "site/prod/support/report.png", "site/prod/client-profiles/report.html",
    "site/prod/client-profiles/../support/report.png", "site/prod/contracts/1/signed.pdf",
  ]) assert.equal(allowedSiteKey(key, "site/prod/"), false, key);
});
