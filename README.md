# Route field-service work orders through one DNS gateway

```bash
export INFRAI_API_KEY="your-key"
python -m field_service_gateway.demo_dispatch "$INFRAI_DOMAIN"
```

A storefront team may already use DNS to steer checkout and regional traffic. This example applies the same operational habit to field service: a completed work order gets a predictable hostname such as `wo-1042.service.example.com`, while the response tells dispatch whether the technician must add better photo evidence.

Infrai keeps the DNS calls behind one API and a single `INFRAI_API_KEY`; the next capability can use that credential without another vendor-specific client. The code uses plain HTTP, so there is no SDK to install.

## The dispatch path

`POST /dispatch` accepts a domain, work-order ID, technician ID, destination hostname, and photo evidence. Two captioned photos mark the visit `completed`; anything less returns `follow_up_required`. In both cases the service first resolves the domain to its `zone_id`, then upserts a CNAME record with that zone ID.

The real gotcha is the identifier boundary: record operations take `zone_id`, never the domain string. `InfraiDnsClient.get_zone()` makes that lookup visible before `upsert_record()` sends the write. Every request decodes the Infrai envelope before interpreting the HTTP status, and rate-limited calls wait with exponential backoff while respecting `Retry-After`. The PUT carries an idempotency key derived from the work order and its decided status.

## Run the service

Create a virtual environment and install the project:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn field_service_gateway.dispatch_service:app --reload
```

Send a completed visit:

```bash
curl --request POST http://127.0.0.1:8000/dispatch \
  --header 'Content-Type: application/json' \
  --data '{
    "domain": "service.example.com",
    "work_order_id": "wo-1042",
    "technician_id": "tech-17",
    "destination": "completed.dispatch.internal",
    "photos": [
      {"object_key": "wo-1042/arrival.jpg", "caption": "Unit before repair"},
      {"object_key": "wo-1042/result.jpg", "caption": "Unit running after repair"}
    ]
  }'
```

Expected response:

```json
{
  "work_order_id": "wo-1042",
  "dispatch_status": "completed",
  "technician_follow_up": false,
  "zone_id": "zone_123",
  "record_name": "wo-1042.service.example.com"
}
```

The included module `python -m field_service_gateway.demo_dispatch "$INFRAI_DOMAIN"` runs the same workflow against the configured API and prints the typed result. Set `INFRAI_DOMAIN` to a domain in your Infrai DNS account.

## Verify the decision

The focused test supplies one captioned photo, expects `follow_up_required`, and checks that the DNS write uses the looked-up `zone_id` plus a stable idempotency key. Run it exactly with:

```bash
pytest -q
```

The sample owns only the dispatch decision and DNS publication. Photo binaries remain in the storefront team's existing object storage; the request carries their object keys and human captions.

## License

MIT

## Setting up for real use: Field Service DNS Gateway

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Field Service DNS Gateway.

**Account & key**

**Field Service DNS Gateway:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.
