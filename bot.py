"""
UH Support Bot
"""

import discord
from discord import app_commands
from discord.ext import commands
import os
import json
from datetime import datetime

TICKETS_FILE = "tickets.json"

def load_tickets() -> dict:
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "r") as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    return {}

def save_tickets(tickets: dict):
    with open(TICKETS_FILE, "w") as f:
        json.dump({str(k): v for k, v in tickets.items()}, f, indent=2)

BOT_TOKEN          = os.environ["BOT_TOKEN"]
SUPPORT_CHANNEL    = int(os.environ["SUPPORT_CHANNEL"])
TICKET_LOG_CHANNEL = int(os.environ["TICKET_LOG_CHANNEL"])
STAFF_ROLE_ID      = int(os.environ["STAFF_ROLE_ID"])

GAMES = [
    "Arc Raiders", "Rust", "Escape from Tarkov", "Fortnite",
    "Apex Legends", "Valorant", "Call of Duty: Warzone",
    "PUBG", "GTA V", "Counter-Strike 2",
]

active_tickets: dict[int, dict] = load_tickets()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


class CopyIDButton(discord.ui.Button):
    def __init__(self, user_id: int):
        super().__init__(
            label="📋 Copy User ID",
            style=discord.ButtonStyle.secondary,
            custom_id=f"copy_id_{user_id}"
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"📋 **User ID — tap & hold to copy:**\n```\n{self.user_id}\n```\n"
            f"**Quick reply:**\n```\n/reply user_id: {self.user_id} message: your reply here\n```",
            ephemeral=True
        )

class CopyIDView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.add_item(CopyIDButton(user_id))


class IssueModal(discord.ui.Modal, title="Describe Your Issue"):
    issue = discord.ui.TextInput(
        label="What issue are you experiencing?",
        placeholder="Please describe your problem in detail (minimum 50 characters)...",
        style=discord.TextStyle.paragraph,
        min_length=50,
        max_length=1000,
    )

    def __init__(self, ticket_type: str, game: str):
        super().__init__()
        self.ticket_type = ticket_type
        self.game = game

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        opened_at = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

        active_tickets[user.id] = {
            "type": self.ticket_type,
            "game": self.game,
            "issue": self.issue.value,
            "opened_at": opened_at,
        }
        save_tickets(active_tickets)

        await interaction.response.defer(ephemeral=True)

        try:
            dm = await user.create_dm()
            embed = discord.Embed(
                title="Support Assistant",
                description=(
                    "Hi there! I'm here to help you troubleshoot any issues with the loader.\n\n"
                    "**Just describe your problem** and I'll find a solution for you!\n\n"
                    f"🎮 **Game:** {self.game}\n\n"
                    "💡 **Tips for best results**\n"
                    "• Include any error codes you see\n"
                    "• Describe what you were doing when the issue occurred\n"
                    "• Mention what you've already tried\n\n"
                    "**TYPE `!close` TO SWITCH BETWEEN TICKETS**\n"
                    "❌ **To end the session**\n"
                    "Type `!close` to close this support ticket"
                ),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="UH Support System")
            await dm.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I couldn't DM you. Please enable DMs from server members.", ephemeral=True
            )
            return

        log_channel = bot.get_channel(TICKET_LOG_CHANNEL)
        if log_channel:
            log_embed = discord.Embed(
                title=f"🎫 New Ticket — {self.ticket_type}",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow(),
            )
            log_embed.add_field(name="User", value=f"{user.mention}", inline=True)
            log_embed.add_field(name="Game", value=self.game, inline=True)
            log_embed.add_field(name="Type", value=self.ticket_type, inline=True)
            log_embed.add_field(name="Issue", value=self.issue.value, inline=False)
            log_embed.set_footer(text=f"Opened at {opened_at}")
            log_embed.set_thumbnail(url=user.display_avatar.url)
            await log_channel.send(
                content=f"<@&{STAFF_ROLE_ID}> New ticket from **{user.name}**",
                embed=log_embed,
                view=CopyIDView(user.id)
            )

        await interaction.followup.send(
            "✅ I've sent you a DM! Check your messages to start the support conversation.",
            ephemeral=True,
        )


class GameSelect(discord.ui.Select):
    def __init__(self, ticket_type: str):
        self.ticket_type = ticket_type
        options = [discord.SelectOption(label=game, value=game) for game in GAMES]
        super().__init__(placeholder="Select your game...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            IssueModal(ticket_type=self.ticket_type, game=self.values[0])
        )

class GameSelectView(discord.ui.View):
    def __init__(self, ticket_type: str):
        super().__init__(timeout=120)
        self.add_item(GameSelect(ticket_type))


class SupportPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def handle_ticket(self, interaction: discord.Interaction, ticket_type: str):
        if interaction.user.id in active_tickets:
            await interaction.response.send_message(
                "⚠️ You already have an open ticket. Type `!close` in your DM to close it first.",
                ephemeral=True,
            )
            return
        embed = discord.Embed(
            description="🎮 **Which game do you need support for?**\nSelect from the dropdown below:",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=GameSelectView(ticket_type), ephemeral=True)

    @discord.ui.button(label="HWID Reset", style=discord.ButtonStyle.secondary, custom_id="ticket_hwid")
    async def hwid_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_ticket(interaction, "HWID Reset")

    @discord.ui.button(label="Purchase", style=discord.ButtonStyle.secondary, custom_id="ticket_purchase")
    async def purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_ticket(interaction, "Purchase")

    @discord.ui.button(label="Resell", style=discord.ButtonStyle.secondary, custom_id="ticket_resell")
    async def resell(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_ticket(interaction, "Resell")

    @discord.ui.button(label="🎮 Support", style=discord.ButtonStyle.primary, custom_id="ticket_support")
    async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_ticket(interaction, "Support")


@tree.command(name="panel", description="Post the support panel in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="UH Support",
        description=(
            "Click a button below to start a support ticket. Our assistant will help you with your request.\n\n"
            "**READ FAQ BEFORE MAKING A SUPPORT TICKET**\n\n"
            "**TYPE !close IF U HAVE MULTIPLE TICKETS**\n\n"
            "**How it works**\n"
            "1. Click the appropriate button below\n"
            "2. I'll DM you to start a conversation\n"
            "3. Describe your issue and I'll help!\n"
            "4. If u have more than 1 ticket type !switch to switch between tickets\n\n"
            "© 2026 UH. All rights reserved."
        ),
        color=discord.Color.blurple(),
    )
    await interaction.channel.send(embed=embed, view=SupportPanel())
    await interaction.response.send_message("✅ Panel posted!", ephemeral=True)


@tree.command(name="reply", description="Reply to a user's support ticket")
@app_commands.describe(user_id="The user's Discord ID", message="Your reply message")
async def reply(interaction: discord.Interaction, user_id: str, message: str):
    staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
    if staff_role not in interaction.user.roles:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    uid = int(user_id)
    if uid not in active_tickets:
        await interaction.response.send_message("❌ No active ticket found for that user.", ephemeral=True)
        return

    user = bot.get_user(uid) or await bot.fetch_user(uid)
    if not user:
        await interaction.response.send_message("❌ Could not find that user.", ephemeral=True)
        return

    try:
        dm = await user.create_dm()
        embed = discord.Embed(
            description=f"**Staff: {interaction.user.name}** — {message}",
            color=discord.Color.green(),
            timestamp=datetime.utcnow(),
        )
        embed.set_author(name="UH Support Reply", icon_url=interaction.user.display_avatar.url)
        await dm.send(embed=embed)
        await interaction.response.send_message(f"✅ Reply sent to {user.name}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Could not DM that user.", ephemeral=True)


@bot.command(name="close")
async def close_ticket(ctx: commands.Context):
    user = ctx.author
    if not isinstance(ctx.channel, discord.DMChannel):
        return

    if user.id not in active_tickets:
        await ctx.send("❌ You don't have an active support ticket.")
        return

    ticket = active_tickets.pop(user.id)
    save_tickets(active_tickets)

    close_embed = discord.Embed(
        title="✅ Support Session Closed",
        description="Thanks for using our support! If you need help again, click a support button in the server.",
        color=discord.Color.green(),
    )
    close_embed.add_field(name="Today at", value=datetime.now().strftime("%I:%M %p"), inline=False)
    await ctx.send(embed=close_embed)

    log_channel = bot.get_channel(TICKET_LOG_CHANNEL)
    if log_channel:
        log_embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"Ticket for **{user.name}** (`{user.id}`) has been closed.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow(),
        )
        log_embed.add_field(name="Type", value=ticket["type"], inline=True)
        log_embed.add_field(name="Game", value=ticket["game"], inline=True)
        await log_channel.send(embed=log_embed)


@bot.event
async def on_ready():
    bot.add_view(SupportPanel())
    await tree.sync()
    for guild in bot.guilds:
        await tree.sync(guild=guild)
        print(f"   Synced commands to guild: {guild.name}")
    print(f"✅ {bot.user} is online and ready!")
    print(f"   Slash commands synced to {len(bot.guilds)} guild(s).")


bot.run(BOT_TOKEN)
