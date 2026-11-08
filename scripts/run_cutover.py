"""Run the routing cutover for one media-processing tenant."""

from provider_routing_service import ContentProviderRouting, TenantPlan, service_from_environment


def main() -> None:
    service: ContentProviderRouting = service_from_environment()
    plan = TenantPlan("studio-acme", "image", "incumbent-image-vendor")
    result = service.onboard(plan)
    print({"tenant": plan.tenant_id, "routing": result.get("data"), "rollback_vendor": "incumbent-image-vendor"})


if __name__ == "__main__":
    main()

