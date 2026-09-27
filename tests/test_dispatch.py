import asyncio

from field_service_gateway.dispatch_service import (
    DispatchRequest,
    DispatchStatus,
    WorkPhoto,
    publish_dispatch,
)


class RecordingDnsClient:
    def __init__(self) -> None:
        self.write: dict[str, str] = {}

    async def get_zone(self, domain: str) -> str:
        assert domain == "service.example.com"
        return "zone_field_7"

    async def upsert_record(self, **values: str) -> dict[str, str]:
        self.write = values
        return {"record_id": "record_42"}


def test_one_photo_requests_follow_up_and_publishes_by_zone_id() -> None:
    client = RecordingDnsClient()
    request = DispatchRequest(
        domain="service.example.com",
        work_order_id="wo-1042",
        technician_id="tech-17",
        destination="review.dispatch.internal",
        photos=[WorkPhoto(object_key="wo-1042/arrival.jpg", caption="Unit on arrival")],
    )

    result = asyncio.run(publish_dispatch(request, client))

    assert result.dispatch_status is DispatchStatus.FOLLOW_UP_REQUIRED
    assert result.technician_follow_up is True
    assert client.write == {
        "zone_id": "zone_field_7",
        "name": "wo-1042.service.example.com",
        "content": "review.dispatch.internal",
        "idempotency_key": "dispatch:wo-1042:follow_up_required",
    }
