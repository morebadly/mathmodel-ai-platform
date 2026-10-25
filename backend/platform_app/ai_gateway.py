"""One bounded HTTP request; deadline includes connect, headers and body reads."""
import asyncio
import json
import httpx
from django.conf import settings

TOTAL_SECONDS = 90
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


async def _request(body):
    async with httpx.AsyncClient(timeout=TOTAL_SECONDS, follow_redirects=False) as client:
        async with client.stream('POST', settings.AI_BASE_URL + '/chat/completions', headers={'Authorization': 'Bearer ' + settings.AI_API_KEY}, json=body) as response:
            response.raise_for_status()
            data=bytearray()
            async for chunk in response.aiter_bytes():
                if len(data)+len(chunk)>MAX_RESPONSE_BYTES:
                    raise ValueError('Model response exceeds platform limit')
                data.extend(chunk)
            return json.loads(data)


def request_completion(body):
    async def bounded():
        try:
            return await asyncio.wait_for(_request(body), timeout=TOTAL_SECONDS)
        except asyncio.TimeoutError as exc:
            raise httpx.ReadTimeout('Model total deadline exceeded') from exc
    return asyncio.run(bounded())
