"""Declarative spec for the Lightning Trading Discord server.

Edit this file, then run `python provision.py` to apply it. Provisioning is
idempotent: roles and channels are matched by name, created when absent and
patched when they already exist.

Permission model
----------------
Access is a ladder. Each rung sees everything below it plus its own tier:

    @everyone  -> lobby + read-only signals preview
    Member     -> education, lounge, full signal feed
    Funded     -> the desk (live fills, positions, P&L)
    Analyst    -> may post into signal channels
    Head Trader-> moderation
    Founder    -> administrator

The scarcity is the point: a locked category that members can see but not
enter is what makes the tier above it feel worth reaching.
"""

# --- Discord permission bits -------------------------------------------------
# https://discord.com/developers/docs/topics/permissions

ADMINISTRATOR            = 1 << 3
MANAGE_CHANNELS          = 1 << 4
ADD_REACTIONS            = 1 << 6
KICK_MEMBERS             = 1 << 1
BAN_MEMBERS              = 1 << 2
VIEW_CHANNEL             = 1 << 10
SEND_MESSAGES            = 1 << 11
MANAGE_MESSAGES          = 1 << 13
EMBED_LINKS              = 1 << 14
ATTACH_FILES             = 1 << 15
READ_MESSAGE_HISTORY     = 1 << 16
MENTION_EVERYONE         = 1 << 17
CONNECT                  = 1 << 20
SPEAK                    = 1 << 21
MANAGE_NICKNAMES         = 1 << 27
MANAGE_ROLES             = 1 << 28
MANAGE_WEBHOOKS          = 1 << 29
USE_APPLICATION_COMMANDS = 1 << 31
CREATE_PUBLIC_THREADS    = 1 << 35
SEND_MESSAGES_IN_THREADS = 1 << 38

# Channel types
TEXT_CHANNEL   = 0
VOICE_CHANNEL  = 2
CATEGORY       = 4
FORUM_CHANNEL  = 15

# Handy bundles
READ_ONLY  = VIEW_CHANNEL | READ_MESSAGE_HISTORY | ADD_REACTIONS
CAN_TALK   = READ_ONLY | SEND_MESSAGES | EMBED_LINKS | ATTACH_FILES \
             | CREATE_PUBLIC_THREADS | SEND_MESSAGES_IN_THREADS \
             | USE_APPLICATION_COMMANDS


# --- Roles -------------------------------------------------------------------
# Ordered highest-authority first. Discord stacks roles bottom-up, so
# provision.py reverses this list when assigning positions.
#
# `hoist` shows the role as its own group in the member sidebar. Only the
# tiers worth displaying are hoisted -- a sidebar with eight headers looks
# cluttered, not exclusive.

ROLES = [
    {
        "name": "Founder",
        "color": 0xE8B923,          # gold
        "hoist": True,
        "mentionable": False,
        "permissions": ADMINISTRATOR,
    },
    {
        "name": "Head Trader",
        "color": 0xC9A227,          # antique gold
        "hoist": True,
        "mentionable": True,
        "permissions": (
            CAN_TALK | MANAGE_MESSAGES | MANAGE_NICKNAMES
            | KICK_MEMBERS | MENTION_EVERYONE
        ),
    },
    {
        "name": "Analyst",
        "color": 0x00B86B,          # emerald
        "hoist": True,
        "mentionable": True,
        "permissions": CAN_TALK | MENTION_EVERYONE,
    },
    {
        "name": "Funded",
        "color": 0x34D399,          # mint
        "hoist": True,
        "mentionable": False,
        "permissions": CAN_TALK,
    },
    {
        "name": "Member",
        "color": 0x64748B,          # slate
        "hoist": False,
        "mentionable": False,
        "permissions": CAN_TALK,
    },
]


# --- Channel tree ------------------------------------------------------------
# `overwrites` maps a role name (or "@everyone") to allow/deny bundles.
# A category's overwrites cascade to its channels unless a channel sets its
# own. Anything omitted inherits, which keeps this file readable.

TREE = [
    {
        "category": "▬▬▬  LIGHTNING  ▬▬▬",
        "overwrites": {
            "@everyone": {"allow": READ_ONLY, "deny": SEND_MESSAGES},
        },
        "channels": [
            {"name": "welcome",
             "topic": "Start here. What this desk is and how to move up."},
            {"name": "announcements",
             "topic": "Desk-wide news. Low volume, high signal."},
            {"name": "risk-disclosure",
             "topic": "Trading involves substantial risk of loss. "
                      "Nothing here is financial advice."},
        ],
    },
    {
        "category": "▬▬▬  SIGNALS  ▬▬▬",
        # Members read; only Analyst and above publish.
        "overwrites": {
            "@everyone":   {"allow": READ_ONLY, "deny": SEND_MESSAGES},
            "Analyst":     {"allow": CAN_TALK},
            "Head Trader": {"allow": CAN_TALK},
        },
        "channels": [
            {"name": "all-signals",
             "topic": "Every signal the engine publishes, unfiltered."},
            {"name": "eur-usd",     "topic": "EUR/USD setups and fills."},
            {"name": "gbp-usd",     "topic": "GBP/USD setups and fills."},
            {"name": "usd-jpy",     "topic": "USD/JPY setups and fills."},
            {"name": "performance",
             "topic": "Weekly win rate, expectancy, drawdown. Posted "
                      "automatically -- wins and losses both."},
        ],
    },
    {
        "category": "▬▬▬  THE DESK  ▬▬▬",
        # The locked tier. Visible in the sidebar but sealed, which is what
        # makes it worth climbing to. Flip the @everyone deny to include
        # VIEW_CHANNEL if you would rather hide it entirely.
        "overwrites": {
            "@everyone":   {"deny": VIEW_CHANNEL},
            "Funded":      {"allow": READ_ONLY},
            "Analyst":     {"allow": CAN_TALK},
            "Head Trader": {"allow": CAN_TALK},
        },
        "channels": [
            {"name": "live-fills",
             "topic": "Executions on the live OANDA account, posted by the bot."},
            {"name": "paper-fills",
             "topic": "Paper-account executions."},
            {"name": "open-positions",
             "topic": "Current exposure. Refreshed by the bot."},
            {"name": "daily-pnl",
             "topic": "End-of-session P&L summary."},
            {"name": "desk-floor", "type": VOICE_CHANNEL,
             "topic": "Voice. Open during London and New York sessions."},
        ],
    },
    {
        "category": "▬▬▬  EDUCATION  ▬▬▬",
        "overwrites": {
            "@everyone": {"deny": SEND_MESSAGES},
            "Member":    {"allow": CAN_TALK},
        },
        "channels": [
            {"name": "strategy",       "topic": "How the setups are built."},
            {"name": "chart-requests", "topic": "Ask for a pair to be reviewed."},
            {"name": "trade-journal",  "topic": "Post your own entries and exits."},
        ],
    },
    {
        "category": "▬▬▬  LOUNGE  ▬▬▬",
        "overwrites": {
            "@everyone": {"allow": CAN_TALK},
        },
        "channels": [
            {"name": "general",       "topic": "Off-topic welcome."},
            {"name": "wins",          "topic": "Post the screenshot."},
            {"name": "introductions", "topic": "Who you are and what you trade."},
        ],
    },
    {
        "category": "▬▬▬  OPS  ▬▬▬",
        # Staff only, hidden from everyone else.
        "overwrites": {
            "@everyone":   {"deny": VIEW_CHANNEL},
            "Head Trader": {"allow": CAN_TALK},
        },
        "channels": [
            {"name": "bot-logs",
             "topic": "Backend events from the Railway API."},
            {"name": "alerts",
             "topic": "Errors, disconnects, failed executions."},
            {"name": "staff-chat", "topic": "Private."},
        ],
    },
]


def role_names():
    return [r["name"] for r in ROLES]


def channel_count():
    return sum(len(c["channels"]) for c in TREE)
