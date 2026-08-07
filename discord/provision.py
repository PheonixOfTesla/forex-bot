"""Apply blueprint.py to a live Discord guild.

    export DISCORD_BOT_TOKEN=...        # never commit this
    export DISCORD_GUILD_ID=...

    python provision.py --dry-run       # show the plan, touch nothing
    python provision.py                 # apply it
    python provision.py --icons         # also upload app/server icons

Safe to re-run. Roles and channels are matched by name: missing ones are
created, existing ones are patched to match the blueprint. Nothing is ever
deleted -- if you rename something in the blueprint you will get a new
channel alongside the old one, and removing the stale one is a manual call
on purpose.
"""

import argparse
import base64
import os
import sys
import time
from pathlib import Path

import requests

import blueprint as bp

API = "https://discord.com/api/v10"
BRAND_DIR = Path(__file__).parent / "brand" / "png"


class DiscordError(RuntimeError):
    pass


class Client:
    def __init__(self, token, guild_id, dry_run=False):
        self.guild = guild_id
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bot {token}",
            "User-Agent": "LightningTrading/1.0 (+https://github.com/PheonixOfTesla/forex-bot)",
        })

    def request(self, method, path, **kw):
        """One call, with Discord's 429 back-off honoured."""
        url = f"{API}{path}"
        for attempt in range(6):
            resp = self.session.request(method, url, timeout=30, **kw)

            if resp.status_code == 429:
                wait = resp.json().get("retry_after", 1.0)
                print(f"    rate limited, waiting {wait:.1f}s")
                time.sleep(wait + 0.1)
                continue

            if resp.status_code >= 400:
                raise DiscordError(
                    f"{method} {path} -> {resp.status_code}: {resp.text[:300]}"
                )

            # 204 No Content has no body to decode.
            return resp.json() if resp.content else {}

        raise DiscordError(f"{method} {path}: still rate limited after 6 tries")

    # -- reads ---------------------------------------------------------------

    def guild_info(self):
        return self.request("GET", f"/guilds/{self.guild}")

    def roles(self):
        return self.request("GET", f"/guilds/{self.guild}/roles")

    def channels(self):
        return self.request("GET", f"/guilds/{self.guild}/channels")

    # -- writes --------------------------------------------------------------

    def create_role(self, payload):
        return self.request("POST", f"/guilds/{self.guild}/roles", json=payload)

    def patch_role(self, role_id, payload):
        return self.request("PATCH", f"/guilds/{self.guild}/roles/{role_id}",
                            json=payload)

    def create_channel(self, payload):
        return self.request("POST", f"/guilds/{self.guild}/channels", json=payload)

    def patch_channel(self, channel_id, payload):
        return self.request("PATCH", f"/channels/{channel_id}", json=payload)

    def patch_guild(self, payload):
        return self.request("PATCH", f"/guilds/{self.guild}", json=payload)


def data_uri(path):
    """Discord wants images as base64 data URIs, not multipart uploads."""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def build_overwrites(spec, role_ids, everyone_id):
    """Translate blueprint overwrites into Discord's wire format."""
    out = []
    for role_name, rule in (spec or {}).items():
        if role_name == "@everyone":
            target = everyone_id
        else:
            target = role_ids.get(role_name)
            if target is None:
                print(f"    ! no role {role_name!r}, skipping its overwrite")
                continue
        out.append({
            "id": str(target),
            "type": 0,                          # 0 = role, 1 = member
            "allow": str(rule.get("allow", 0)),
            "deny": str(rule.get("deny", 0)),
        })
    return out


def sync_roles(client):
    """Create or update every blueprint role. Returns {name: id}."""
    print("\nRoles")
    existing = {r["name"]: r for r in client.roles()}
    everyone_id = next(r["id"] for r in client.roles()
                       if r["name"] == "@everyone")
    ids = {}

    for spec in bp.ROLES:
        payload = {
            "name": spec["name"],
            "permissions": str(spec["permissions"]),
            "color": spec["color"],
            "hoist": spec["hoist"],
            "mentionable": spec["mentionable"],
        }
        current = existing.get(spec["name"])

        if current:
            print(f"  = {spec['name']:<12} exists, patching")
            if not client.dry_run:
                client.patch_role(current["id"], payload)
            ids[spec["name"]] = current["id"]
        else:
            print(f"  + {spec['name']:<12} creating  #{spec['color']:06X}")
            if client.dry_run:
                ids[spec["name"]] = f"<new:{spec['name']}>"
            else:
                ids[spec["name"]] = client.create_role(payload)["id"]

    return ids, everyone_id


def sync_channels(client, role_ids, everyone_id):
    """Create or update categories and their channels."""
    print("\nChannels")
    existing = {(c["name"], c["type"]): c for c in client.channels()}
    created = 0

    for group in bp.TREE:
        cat_name = group["category"]
        cat_overwrites = build_overwrites(
            group.get("overwrites"), role_ids, everyone_id
        )

        current = existing.get((cat_name, bp.CATEGORY))
        if current:
            print(f"\n  = {cat_name}")
            cat_id = current["id"]
            if not client.dry_run:
                client.patch_channel(
                    cat_id, {"permission_overwrites": cat_overwrites}
                )
        else:
            print(f"\n  + {cat_name}")
            if client.dry_run:
                cat_id = f"<new:{cat_name}>"
            else:
                cat_id = client.create_channel({
                    "name": cat_name,
                    "type": bp.CATEGORY,
                    "permission_overwrites": cat_overwrites,
                })["id"]
                created += 1

        for ch in group["channels"]:
            ch_type = ch.get("type", bp.TEXT_CHANNEL)
            payload = {
                "name": ch["name"],
                "type": ch_type,
                "parent_id": cat_id,
            }
            # Voice channels reject `topic`.
            if ch_type != bp.VOICE_CHANNEL and ch.get("topic"):
                payload["topic"] = ch["topic"]
            # A channel-level override replaces the inherited category rules.
            if "overwrites" in ch:
                payload["permission_overwrites"] = build_overwrites(
                    ch["overwrites"], role_ids, everyone_id
                )

            found = existing.get((ch["name"], ch_type))
            if found:
                print(f"      = #{ch['name']}")
                if not client.dry_run:
                    client.patch_channel(
                        found["id"],
                        {k: v for k, v in payload.items() if k != "type"},
                    )
            else:
                print(f"      + #{ch['name']}")
                if not client.dry_run:
                    client.create_channel(payload)
                    created += 1

    return created


def upload_icons(client):
    """Push the rendered server icon, if render_icons.py has been run."""
    print("\nIcons")
    icon = BRAND_DIR / "server-icon-512.png"
    if not icon.exists():
        print(f"  ! {icon} not found -- run `python render_icons.py` first")
        return
    print(f"  + server icon from {icon.name}")
    if not client.dry_run:
        client.patch_guild({"icon": data_uri(icon)})
    print("  i app icon must be uploaded by hand at "
          "discord.com/developers -- the API has no endpoint for it")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan without calling Discord")
    parser.add_argument("--icons", action="store_true",
                        help="also upload the server icon")
    args = parser.parse_args()

    token = os.environ.get("DISCORD_BOT_TOKEN")
    guild = os.environ.get("DISCORD_GUILD_ID")

    if not args.dry_run:
        missing = [n for n, v in
                   (("DISCORD_BOT_TOKEN", token), ("DISCORD_GUILD_ID", guild))
                   if not v]
        if missing:
            sys.exit(f"error: set {' and '.join(missing)} in the environment")

    client = Client(token or "", guild or "0", dry_run=args.dry_run)

    if args.dry_run:
        print("DRY RUN -- no requests will be sent\n")
        print(f"Plan: {len(bp.ROLES)} roles, {len(bp.TREE)} categories, "
              f"{bp.channel_count()} channels")
        role_ids = {r["name"]: f"<new:{r['name']}>" for r in bp.ROLES}
        for group in bp.TREE:
            print(f"\n  + {group['category']}")
            for ch in group["channels"]:
                kind = "voice" if ch.get("type") == bp.VOICE_CHANNEL else "text"
                print(f"      + #{ch['name']:<18} ({kind})")
        return

    info = client.guild_info()
    print(f"Guild: {info['name']} ({guild})")

    role_ids, everyone_id = sync_roles(client)
    created = sync_channels(client, role_ids, everyone_id)

    if args.icons:
        upload_icons(client)

    print(f"\nDone. {created} channels created, "
          f"{len(bp.ROLES)} roles in sync.")
    print("Next: drag Lightning Trading's own role above Member in "
          "Server Settings so it can manage the tiers below it.")


if __name__ == "__main__":
    main()
