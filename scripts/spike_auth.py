"""Wegwerf-Spike: klärt vehicleState-Enum, Command-Payloads, Auth-Grant.

Klärt drei Fakten, bevor die echte Integration gebaut wird:
  1. authList-Antwortform + Geräte-Key (deviceSn vs deviceId)
  2. vehicleState-Strings je Mäher-Zustand + Command-Payload-Schema
  3. ob getAccessToken einen grant_type=password unterstützt (stiller Login)

Nutzung (Token/SN NICHT committen — nur als Env-Var):
  export NAVIMOW_TOKEN="<access_token aus App/offizieller Integration>"
  export NAVIMOW_SN="<Geraete-Seriennummer>"
  # optional für Auth-Test:
  export NAVIMOW_EMAIL="..."; export NAVIMOW_PW="..."

  python scripts/spike_auth.py authlist
  python scripts/spike_auth.py status
  python scripts/spike_auth.py command start    # | pause | dock
  python scripts/spike_auth.py login            # testet grant_type=password
"""

import asyncio
import os
import sys
import uuid

import aiohttp

BASE = "https://navimow-fra.ninebot.com"
CLIENT_ID = "homeassistant"
CLIENT_SECRET = "57056e15-722e-42be-bbaa-b0cbfb208a52"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['NAVIMOW_TOKEN']}",
        "requestId": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


async def _post(session, path, body):
    async with session.post(
        f"{BASE}{path}", json=body, headers=_headers()
    ) as r:
        text = await r.text()
        print(f"POST {path}  body={body}\n-> HTTP {r.status}\n{text}\n")
        return text


async def _get(session, path):
    async with session.get(f"{BASE}{path}", headers=_headers()) as r:
        text = await r.text()
        print(f"GET {path}\n-> HTTP {r.status}\n{text}\n")
        return text


async def main(action: str) -> None:
    async with aiohttp.ClientSession() as session:
        sn = os.environ.get("NAVIMOW_SN", "")
        if action == "authlist":
            await _get(session, "/openapi/smarthome/authList")
        elif action == "status":
            await _post(
                session, "/openapi/smarthome/getVehicleStatus", {"deviceSn": sn}
            )
        elif action == "command":
            cmd = sys.argv[2] if len(sys.argv) > 2 else "start"
            await _post(
                session,
                "/openapi/smarthome/sendCommands",
                {"deviceSn": sn, "command": cmd},
            )
        elif action == "login":
            body = {
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": os.environ.get("NAVIMOW_EMAIL", ""),
                "password": os.environ.get("NAVIMOW_PW", ""),
            }
            async with session.post(
                f"{BASE}/openapi/oauth/getAccessToken", json=body
            ) as r:
                print(f"login -> HTTP {r.status}\n{await r.text()}\n")
        else:
            print("unknown action — use: authlist | status | command | login")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "status"))
