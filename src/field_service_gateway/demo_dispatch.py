import asyncio
import argparse
import os

from .dispatch_service import DispatchRequest, WorkPhoto, publish_dispatch
from .infrai_dns import InfraiDnsClient


async def main(domain: str) -> None:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before running the dispatch demo")

    request = DispatchRequest(
        domain=domain,
        work_order_id="wo-1042",
        technician_id="tech-17",
        destination="completed.dispatch.internal",
        photos=[
            WorkPhoto(object_key="wo-1042/arrival.jpg", caption="Unit before repair"),
            WorkPhoto(object_key="wo-1042/result.jpg", caption="Unit running after repair"),
        ],
    )
    async with InfraiDnsClient(api_key) as client:
        result = await publish_dispatch(request, client)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish a sample dispatch DNS record")
    parser.add_argument("domain", help="DNS domain in your Infrai account")
    asyncio.run(main(parser.parse_args().domain))
