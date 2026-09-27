from __future__ import annotations

import os
from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai_dns import InfraiDnsClient, InfraiError


class DispatchStatus(str, Enum):
    COMPLETED = "completed"
    FOLLOW_UP_REQUIRED = "follow_up_required"


class WorkPhoto(BaseModel):
    object_key: str = Field(min_length=1)
    caption: str = Field(min_length=1)


class DispatchRequest(BaseModel):
    domain: str = Field(min_length=1)
    work_order_id: str = Field(pattern=r"^[a-z0-9-]+$")
    technician_id: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    photos: list[WorkPhoto]


class DispatchResult(BaseModel):
    work_order_id: str
    dispatch_status: DispatchStatus
    technician_follow_up: bool
    zone_id: str
    record_name: str


def decide_dispatch(photos: list[WorkPhoto]) -> DispatchStatus:
    return (
        DispatchStatus.COMPLETED
        if len(photos) >= 2 and all(photo.caption.strip() for photo in photos)
        else DispatchStatus.FOLLOW_UP_REQUIRED
    )


def dns_client() -> InfraiDnsClient:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    return InfraiDnsClient(api_key)


app = FastAPI(title="Field-service DNS dispatch")


@app.post("/dispatch", response_model=DispatchResult)
async def publish_dispatch(
    request: DispatchRequest,
    client: InfraiDnsClient = Depends(dns_client),
) -> DispatchResult:
    status = decide_dispatch(request.photos)
    record_name = f"{request.work_order_id}.{request.domain}"
    try:
        zone_id = await client.get_zone(request.domain)
        await client.upsert_record(
            zone_id=zone_id,
            name=record_name,
            content=request.destination,
            idempotency_key=f"dispatch:{request.work_order_id}:{status.value}",
        )
    except InfraiError as exc:
        caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=caller_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return DispatchResult(
        work_order_id=request.work_order_id,
        dispatch_status=status,
        technician_follow_up=status is DispatchStatus.FOLLOW_UP_REQUIRED,
        zone_id=zone_id,
        record_name=record_name,
    )
