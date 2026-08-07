# Discord server provisioning

Builds out the Lightning Trading Discord — roles, categories, channels and
per-channel permissions — from a single declarative file, plus the brand
assets to dress it.

```
discord/
├── blueprint.py      the spec: roles, channel tree, permission overwrites
├── provision.py      applies the spec to a live guild (idempotent)
├── render_icons.py   SVG -> PNG at the sizes Discord accepts
└── brand/
    ├── *.svg         source artwork, edit these
    └── png/          build output, regenerate with render_icons.py
```

## Setup

**1. Finish the bot application** at
<https://discord.com/developers/applications> — give it a name, then
**Bot → Reset Token**.

**2. Put the token in the environment. Never in a file, never in chat.**

```bash
export DISCORD_BOT_TOKEN='...'      # from the Bot tab, shown once
export DISCORD_GUILD_ID='...'       # right-click server → Copy Server ID
```

**3. Invite the bot** with Manage Channels, Manage Roles and Manage Webhooks:

```
https://discord.com/oauth2/authorize?client_id=1535432465844273293&scope=bot%20applications.commands&permissions=805432336
```

**4. Drag the bot's role to the top** of Server Settings → Roles. Discord
will not let a bot create or edit any role positioned above its own, so
provisioning fails partway through if you skip this.

## Run it

```bash
pip install requests
python provision.py --dry-run     # print the plan, send nothing
python provision.py               # apply
python provision.py --icons       # apply and upload the server icon
```

Re-running is safe. Roles and channels are matched by name — missing ones
get created, existing ones get patched back into line with the blueprint.
Nothing is ever deleted. Rename something in `blueprint.py` and you get a
new channel next to the old one; removing the stale one is deliberately a
manual decision.

## The permission ladder

Each tier inherits everything below it. The point of the design is that
`THE DESK` sits visible in the sidebar and locked — a members-only category
nobody can see does not motivate anyone to reach it.

| Category      | @everyone | Member | Funded | Analyst | Head Trader |
|---------------|-----------|--------|--------|---------|-------------|
| LIGHTNING     | read      | read   | read   | read    | post        |
| SIGNALS       | read      | read   | read   | post    | post        |
| THE DESK      | —         | —      | read   | post    | post        |
| EDUCATION     | read      | post   | post   | post    | post        |
| LOUNGE        | post      | post   | post   | post    | post        |
| OPS           | hidden    | hidden | hidden | hidden  | post        |

`Founder` holds Administrator and bypasses the table entirely.

To hide `THE DESK` completely instead of teasing it, the category's
`@everyone` rule already denies `VIEW_CHANNEL` — it is the `Funded` allow
that opens it back up. Drop the `Funded` entry and it disappears for
everyone below Analyst.

## Brand assets

Discord **rejects SVG on every upload surface** — app icon, server icon,
custom emoji, role icon. It takes PNG, GIF, JPG and WEBP only. So the SVGs
here are the editable source and `render_icons.py` produces the raster
Discord will actually accept.

```bash
pip install cairosvg
python render_icons.py
```

| Output | Size | Where it goes |
|---|---|---|
| `app-icon-1024.png` | 1024² | Developer portal → General Information. Manual upload; the API has no endpoint for it. |
| `server-icon-512.png` | 512² | `provision.py --icons`, or Server Settings by hand. |
| `emoji-*.png` | 128² | Server Settings → Emoji. Max 256 KB each; the renderer warns if one runs over. |

Palette: obsidian `#111721`, gold `#E8B923`, emerald `#00B86B`, mint
`#34D399`, slate `#64748B`. Role colors in `blueprint.py` are drawn from
the same set, so the member sidebar matches the icon.

Channel names are plain text — Discord allows unicode but not images, so
the section dividers are `▬` runs rather than embedded graphics.

## Notes

- Category names starting with `▬` sort oddly against alphabetical
  channels. Order is set by drag in the client, or by `PATCH
  /guilds/{id}/channels` with explicit positions.
- `provision.py` honours Discord's 429 back-off and retries six times.
- The bot cannot create the guild itself, only modify one it has joined.
