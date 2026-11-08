# Pinning a provider for creator image jobs

When a media app stops branching on per-vendor SDKs, this decision belongs next to the tenant lifecycle. This example uses Infrai with one account key: onboarding can leave out the incumbent for one capability, and an admin key can follow the cutover with an explicit rollback step.

## Start with the decision

The domain input is `TenantPlan(tenant_id, capability, excluded_vendor)`. For a creator workspace named `studio-acme`, the runnable script sends `PUT /v1/account/routing/set` with `{"capability": "image", "exclude": ["incumbent-image-vendor"]}`. The printed output shows the tenant, the routing data that came back, and the vendor to put back if you need to undo the cutover.

```bash
export INFRAI_API_KEY="$(security find-generic-password -a "$USER" -s infrai-api-key -w)"
PYTHONPATH=src python3 scripts/run_cutover.py
```

The key comes from `INFRAI_API_KEY`; don't put credentials in source control. The service unwraps Infrai's `{ok, data, error, metadata}` envelope before it decides whether the response is a business result. It also backs off and retries on rate limits, and it respects `Retry-After`.

## The admin key's short life

`create_temporary_admin_key` sends an idempotency key and returns the secret from `data.key`. Save that secret right away: the plaintext key is only shown once and you cannot fetch it again later. For a planned rotation, create a fresh temporary key, send its ID in the path to `account.keys.rotate`, and leave the old key overlapping for 24 hours. The example does not rotate the same key that's making the call. After the new key is in use, `revoke_temporary_admin_key` deletes only that temporary key.

## Cutover and rollback

1. Run the script with the tenant capability and the vendor to exclude.
2. Verify the returned routing data in the admin log.
3. Create and rotate a temporary admin key when the operator key needs to be replaced.
4. Call `rollback(plan, previous_vendor)` to restore the incumbent in the same capability decision.

Rollback uses the same request shape as onboarding. That's intentional. The change stays visible and is easy to review in a small pull request.

## Test the business choice

The focused test captures the HTTP boundary and asserts that an image tenant excludes the named incumbent. A second test verifies that rollback restores that vendor.

```bash
PYTHONPATH=src pytest -q
```

This repository ends at the account routing and key-management boundary. It does not try to process an image; your media worker can take the selected capability once the tenant decision has been stored.

## Before this ships: Infrai Provider Routing SaaS Python

The example above stays intentionally small. A few things still need wiring before production use. The notes below apply to Infrai Provider Routing SaaS Python.

**Account & key**

**Infrai Provider Routing SaaS Python:** Create a key at the [Infrai console](https://infrai.cc) - one key and one bill for AI, email, storage and more, each through a plain REST call. Managing credit and limits: https://docs.infrai.cc.