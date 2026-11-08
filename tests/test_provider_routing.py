from provider_routing_service import ContentProviderRouting, TenantPlan


class RecordingClient:
    def __init__(self):
        self.calls = []

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        return {"ok": True, "data": {"routing": body}}


def test_content_tenant_excludes_incumbent_for_image_jobs():
    client = RecordingClient()
    service = ContentProviderRouting(client)

    service.onboard(TenantPlan("creator-42", "image", "incumbent-image-vendor"))

    assert client.calls == [
        ("PUT", "/v1/account/routing/set", {"capability": "image", "exclude": ["incumbent-image-vendor"]})
    ]


def test_rollback_restores_the_previous_vendor():
    client = RecordingClient()
    service = ContentProviderRouting(client)

    service.rollback(TenantPlan("creator-42", "image", "new-image-vendor"), "incumbent-image-vendor")

    assert client.calls[0][2] == {"capability": "image", "exclude": ["incumbent-image-vendor"]}
