"""Beardless Bot events, commands, listeners, and main."""

import asyncio
import logging
import random
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from time import time
from typing import Final

import aiofiles
import dotenv
import nextcord
from httpx import RequestError
from nextcord.ext import commands
from nextcord.utils import get

import brawl
import bucks
import logs
import misc

with Path("README.MD").open("r", encoding="UTF-8") as readme:
	__version__ = " ".join(readme.read().split(" ")[3:6])

logger = logging.getLogger(__name__)

# This dictionary is for keeping track of pings in the lfs channels.
# TODO: use on_close() to make wait times persist through restarts
# https://github.com/LevBernstein/BeardlessBot/issues/44
SparPings: dict[int, dict[str, int]] = {}

# This array stores the active instances of blackjack.
BlackjackGames: list[bucks.BlackjackGame] = []

# Replace OwnerId with your Discord user id
OwnerId: Final[int] = 196354892208537600
EggGuildId: Final[int] = 442403231864324119
SparCooldown: Final[int] = 7200

BeardlessBot = commands.Bot(
	command_prefix="!",
	case_insensitive=True,
	help_command=misc.BbHelpCommand(),
	intents=nextcord.Intents.all(),
	chunk_guilds_at_startup=False,
	owner_id=OwnerId,
	activity=nextcord.CustomActivity(name="Try !blackjack and !flip"),
)

BrawlKey: str | None = None

RoleColors = {
	"blue": 0x3C9EFD, "pink": 0xD300FF, "orange": 0xFAAA24, "red": 0xF5123D,
}


# Setup:


@BeardlessBot.event
async def on_ready() -> None:
	"""
	Startup method. Fires whenever the Bot connects to the Gateway.

	on_ready handles setting the Bot's avatar; if the Bot is launched
	many times within a short period, you may be rate limited,
	triggering an HTTPException.

	The method also initializes sparPings to enable a 2-hour cooldown for the
	spar command, and chunks all guilds (caches them) to speed up operations.
	This also allows you to get a good idea of how many unique users are in
	all guilds in which Beardless Bot operates.
	"""
	logger.info("Beardless Bot %s online!", __version__)

	assert BeardlessBot.user is not None
	try:
		async with aiofiles.open("resources/images/prof.png", "rb") as f:
			await BeardlessBot.user.edit(avatar=await f.read())
	except nextcord.HTTPException:
		logger.exception("Failed to update avatar!")
	except FileNotFoundError:
		logger.exception(
			"Avatar file not found! Check your directory structure.",
		)
	else:
		logger.info("Avatar updated!")

	try:
		members = set(BeardlessBot.guilds[0].members)
	except IndexError:
		logger.exception("Bot is in no servers! Add it to a server.")
	else:
		for guild in BeardlessBot.guilds:
			# Do this first so all servers can spar immediately
			SparPings[guild.id] = dict.fromkeys(brawl.Regions, 0)
		logger.info("Zeroed sparpings! Sparring is now possible.")
		logger.info("Chunking guilds, collecting analytics...")
		for guild in BeardlessBot.guilds:
			members = members.union(set(guild.members))
			await guild.chunk()

		logger.info(
			"Chunking complete! Beardless Bot serves"
			" %i unique members across %i servers.",
			len(members),
			len(BeardlessBot.guilds),
		)


@BeardlessBot.event
async def on_guild_join(guild: nextcord.Guild) -> None:
	logger.info("Just joined %s!", guild.name)

	if guild.me.guild_permissions.administrator:
		role = get(guild.roles, name="Beardless Bot")
		assert role is not None
		for channel in guild.text_channels:
			try:
				await channel.send(embed=misc.on_join(guild, role))
			except nextcord.DiscordException:
				logger.exception("Failed to send onJoin msg!")
			else:
				logger.info("Sent join message in %s.", channel.name)
				break
		logger.info(
			"Beardless Bot is now in %i servers.", len(BeardlessBot.guilds),
		)
		SparPings[guild.id] = dict.fromkeys(brawl.Regions, 0)
	else:
		logger.warning("Not given admin perms in %s.", guild.name)
		for channel in guild.text_channels:
			try:
				await channel.send(embed=misc.NoPermsEmbed)
			except nextcord.DiscordException:
				logger.exception("Failed to send noPerms msg!")
			else:
				logger.info("Sent no perms msg in %s.", channel.name)
				break
		await guild.leave()
		logger.info("Left %s.", guild.name)


# Event logging:


@BeardlessBot.event
async def on_message_delete(
	message: nextcord.Message,
) -> nextcord.Embed | None:
	emb = None
	if (
		message.guild
		and ((
			hasattr(message.channel, "name")
			and message.channel.name != misc.LogChannelName
		) or message.content)
		and (channel := misc.get_log_channel(message.guild))
	):
		emb = logs.log_delete_msg(message)
		await channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_bulk_message_delete(
	messages: Sequence[nextcord.Message],
) -> nextcord.Embed | None:
	emb = None
	assert messages[0].guild is not None
	if channel := misc.get_log_channel(messages[0].guild):
		emb = logs.log_purge(messages[0], messages)
		await channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_message_edit(
	before: nextcord.Message, after: nextcord.Message,
) -> nextcord.Embed | None:
	emb = None
	if after.guild and (before.content != after.content):
		if misc.scam_check(after.content):
			await misc.delete_scam_and_notify(after)
		if log_channel := misc.get_log_channel(after.guild):
			emb = logs.log_edit_msg(before, after)
			await log_channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_reaction_clear(
	message: nextcord.Message, reactions: list[nextcord.Reaction],
) -> nextcord.Embed | None:
	assert message.guild is not None
	emb = None
	if channel := misc.get_log_channel(message.guild):
		emb = logs.log_clear_reacts(message, reactions)
		await channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_guild_channel_delete(
	channel: nextcord.abc.GuildChannel,
) -> nextcord.Embed | None:
	emb = None
	if log_channel := misc.get_log_channel(channel.guild):
		emb = logs.log_delete_channel(channel)
		await log_channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_guild_channel_create(
	channel: nextcord.abc.GuildChannel,
) -> nextcord.Embed | None:
	emb = None
	if log_channel := misc.get_log_channel(channel.guild):
		emb = logs.log_create_channel(channel)
		await log_channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_member_join(member: nextcord.Member) -> nextcord.Embed | None:
	emb = None
	if channel := misc.get_log_channel(member.guild):
		emb = logs.log_member_join(member)
		await channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_member_remove(member: nextcord.Member) -> nextcord.Embed | None:
	emb = None
	if channel := misc.get_log_channel(member.guild):
		emb = logs.log_member_remove(member)
		await channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_member_update(
	before: nextcord.Member, after: nextcord.Member,
) -> nextcord.Embed | None:
	emb = None
	if channel := misc.get_log_channel(before.guild):
		if before.nick != after.nick:
			emb = logs.log_member_nick_change(before, after)
		elif before.roles != after.roles:
			emb = logs.log_member_roles_change(before, after)
		if emb:
			await channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_member_ban(
	guild: nextcord.Guild, member: nextcord.Member,
) -> nextcord.Embed | None:
	emb = None
	if channel := misc.get_log_channel(guild):
		emb = logs.log_ban(member)
		await channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_member_unban(
	guild: nextcord.Guild, member: nextcord.Member,
) -> nextcord.Embed | None:
	emb = None
	if channel := misc.get_log_channel(guild):
		emb = logs.log_unban(member)
		await channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_thread_join(thread: nextcord.Thread) -> nextcord.Embed | None:
	emb = None
	if not thread.me:
		await thread.join()
		if channel := misc.get_log_channel(thread.guild):
			emb = logs.log_create_thread(thread)
			await channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_thread_delete(thread: nextcord.Thread) -> nextcord.Embed | None:
	emb = None
	if channel := misc.get_log_channel(thread.guild):
		emb = logs.log_delete_thread(thread)
		await channel.send(embed=emb)
	return emb


@BeardlessBot.event
async def on_thread_update(
	before: nextcord.Thread, after: nextcord.Thread,
) -> nextcord.Embed | None:
	emb = None
	if channel := misc.get_log_channel(after.guild):
		# TODO: log Thread.locked/unlocked
		# https://github.com/LevBernstein/BeardlessBot/issues/45
		if before.archived and not after.archived:
			emb = logs.log_thread_unarchived(after)
		elif after.archived and not before.archived:
			emb = logs.log_thread_archived(after)
		if emb:
			await channel.send(embed=emb)
	return emb


# Commands:


@BeardlessBot.command(name="flip")  # type: ignore[arg-type]
async def cmd_flip(ctx: misc.BotContext, bet: str = "10") -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	report = (
		bucks.FinMsg.format(ctx.author.mention)
		if bucks.active_game(BlackjackGames, ctx.author)
		else bucks.flip(ctx.author, bet.lower())
	)
	await ctx.send(embed=misc.bb_embed("Beardless Bot Coin Flip", report))
	return 1


@BeardlessBot.command(  # type: ignore[arg-type]
	name="blackjack", aliases=("bj",),
)
async def cmd_blackjack(ctx: misc.BotContext, bet: str = "10") -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	if bucks.active_game(BlackjackGames, ctx.author):
		report = bucks.FinMsg.format(ctx.author.mention)
	else:
		report, game = bucks.blackjack(ctx.author, bet)
		if game:
			BlackjackGames.append(game)
	await ctx.send(embed=misc.bb_embed("Beardless Bot Blackjack", report))
	return 1


@BeardlessBot.command(name="deal", aliases=("hit",))  # type: ignore[arg-type]
async def cmd_deal(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	if "," in ctx.author.name:
		report = bucks.CommaWarn.format(ctx.author.mention)
	else:
		report = bucks.NoGameMsg.format(ctx.author.mention)
		if game := bucks.active_game(BlackjackGames, ctx.author):
			report = game.deal()
			if game.check_bust() or game.perfect():
				game.check_bust()
				bucks.write_money(
					ctx.author, game.bet, writing=True, adding=True,
				)
				BlackjackGames.remove(game)
	await ctx.send(embed=misc.bb_embed("Beardless Bot Blackjack", report))
	return 1


@BeardlessBot.command(  # type: ignore[arg-type]
	name="stay", aliases=("stand",),
)
async def cmd_stay(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	if "," in ctx.author.name:
		report = bucks.CommaWarn.format(ctx.author.mention)
	else:
		report = bucks.NoGameMsg.format(ctx.author.mention)
		if game := bucks.active_game(BlackjackGames, ctx.author):
			result = game.stay()
			report = game.message
			if result and game.bet:
				written, bonus = bucks.write_money(
					ctx.author, game.bet, writing=True, adding=True,
				)
				if written == bucks.MoneyFlags.CommaInUsername:
					assert isinstance(bonus, str)
					report = bonus
			BlackjackGames.remove(game)
	await ctx.send(embed=misc.bb_embed("Beardless Bot Blackjack", report))
	return 1


@BeardlessBot.command(name="av", aliases=("avatar",))  # type: ignore[arg-type]
async def cmd_av(ctx: misc.BotContext, *, target: str = "") -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(embed=misc.avatar(
		misc.get_target(ctx, target), ctx.message,
	))
	return 1


@BeardlessBot.command(name="info")  # type: ignore[arg-type]
async def cmd_info(ctx: misc.BotContext, *, target: str = "") -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild:
		return -1
	info_target: nextcord.Member | str
	if ctx.message.mentions:
		assert isinstance(ctx.message.mentions[0], nextcord.Member)
		info_target = ctx.message.mentions[0]
	elif target:
		info_target = target
	else:
		assert isinstance(ctx.author, nextcord.Member)
		info_target = ctx.author
	await ctx.send(embed=misc.info(info_target, ctx.message))
	return 1


@BeardlessBot.command(  # type: ignore[arg-type]
	name="balance", aliases=("bal",),
)
async def cmd_balance(ctx: misc.BotContext, *, target: str = "") -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(
		embed=bucks.balance(misc.get_target(ctx, target), ctx.message),
	)
	return 1


@BeardlessBot.command(  # type: ignore[arg-type]
	name="leaderboard", aliases=("leaderboards", "lb"),
)
async def cmd_leaderboard(ctx: misc.BotContext, *, target: str = "") -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(
		embed=bucks.leaderboard(misc.get_target(ctx, target), ctx.message),
	)
	return 1


@BeardlessBot.command(name="dice")  # type: ignore[arg-type]
async def cmd_dice(ctx: misc.BotContext) -> int | nextcord.Embed:
	if misc.ctx_created_thread(ctx):
		return -1
	description = (
		f"Welcome to Beardless Bot dice, {ctx.author.mention}! Enter !roll"
		" [count]d[number][+/-][modifier] to roll [count] [number]-sided"
		" dice and add or subtract a modifier. For example: !d8+3, or"
		" !4d100-17, or !d6."
	)
	emb = misc.bb_embed("Beardless Bot Dice", description)
	await ctx.send(embed=emb)
	return emb


@BeardlessBot.command(name="reset")  # type: ignore[arg-type]
async def cmd_reset(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(embed=bucks.reset(ctx.author))
	return 1


@BeardlessBot.command(name="register")  # type: ignore[arg-type]
async def cmd_register(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(embed=bucks.register(ctx.author))
	return 1


@BeardlessBot.command(name="bucks")  # type: ignore[arg-type]
async def cmd_bucks(ctx: misc.BotContext) -> int | nextcord.Embed:
	if misc.ctx_created_thread(ctx):
		return -1
	description = (
		"BeardlessBucks are this bot's special currency."
		" You can earn them by playing games. First, do"
		" !register to get yourself started with a balance."
	)
	emb = misc.bb_embed("BeardlessBucks", description)
	await ctx.send(embed=emb)
	return emb


@BeardlessBot.command(name="hello", aliases=("hi",))  # type: ignore[arg-type]
async def cmd_hello(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(random.choice(misc.Greetings))
	return 1


@BeardlessBot.command(name="source")  # type: ignore[arg-type]
async def cmd_source(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	source = (
		"Most facts taken from [this website]"
		"(https://www.thefactsite.com/1000-interesting-facts/)."
	)
	await ctx.send(embed=misc.bb_embed("Beardless Bot Fun Facts", source))
	return 1


@BeardlessBot.command(  # type: ignore[arg-type]
	name="add", aliases=("join", "invite"),
)
async def cmd_add(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(embed=misc.Invite_Embed)
	return 1


@BeardlessBot.command(name="rohan")  # type: ignore[arg-type]
async def cmd_rohan(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(file=nextcord.File("resources/images/cute.png"))
	return 1


@BeardlessBot.command(name="random")  # type: ignore[arg-type]
async def cmd_random_brawl(
	ctx: misc.BotContext, ran_type: str = "None",
) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	emb = await brawl.random_brawl(ran_type.lower(), BrawlKey)
	await ctx.send(embed=emb)
	return 1


@BeardlessBot.command(name="fact")  # type: ignore[arg-type]
async def cmd_fact(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(embed=misc.bb_embed(
		f"Beardless Bot Fun Fact #{random.randint(1, 111111111)}", misc.fact(),
	))
	return 1


@BeardlessBot.command(  # type: ignore[arg-type]
	name="animals", aliases=("animal", "pets"),
)
async def cmd_animals(ctx: misc.BotContext) -> int:
	"""
	Send an embed listing all the valid animal commands.

	Args:
		ctx (misc.BotContext): The context in which the command was invoked

	Returns:
		int: -1 if the message was a thread creation; 1 otherwise.

	"""
	if misc.ctx_created_thread(ctx):
		return -1
	emb = misc.bb_embed("Animal Photo Commands:").add_field(
		name="!dog",
		value=(
			"Can also do !dog breeds to see breeds you"
			" can get pictures of with !dog [breed]"
		),
		inline=False,
	)
	for animal_name in misc.AnimalList:
		emb.add_field(name="!" + animal_name, value="_ _")
	await ctx.send(embed=emb)
	return 1


@BeardlessBot.command(name="define")  # type: ignore[arg-type]
async def cmd_define(ctx: misc.BotContext, *, words: str = "") -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	emb = await misc.define(words)
	await ctx.send(embed=emb)
	return 1


@BeardlessBot.command(name="ping")  # type: ignore[arg-type]
async def cmd_ping(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx) or BeardlessBot.user is None:
		return -1
	emb = misc.bb_embed(
		"Pinged",
		f"Beardless Bot's latency is {int(1000 * BeardlessBot.latency)} ms.",
	).set_thumbnail(url=misc.fetch_avatar(BeardlessBot.user))
	await ctx.send(embed=emb)
	return 1


@BeardlessBot.command(name="roll")  # type: ignore[arg-type]
async def cmd_roll(
	ctx: misc.BotContext, dice: str = "None",
) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(embed=misc.roll_report(dice, ctx.author))
	return 1


@BeardlessBot.command(name="dog", aliases=("moose",))  # type: ignore[arg-type]
async def cmd_dog(ctx: misc.BotContext, *, breed: str = "") -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	assert ctx.invoked_with is not None
	try:
		url = await misc.get_dog(
			breed.lower() if ctx.invoked_with.lower() != "moose" else "moose",
		)
	except (misc.AnimalException, ValueError, KeyError) as e:
		logger.exception("Failed getting dog breed: %s", breed)
		misc.log_exception(e, ctx)
		await ctx.send(embed=misc.bb_embed(
			"Something's gone wrong with the Dog API!",
			"Please inform my creator and he'll see what's going on.",
		))
		return 0
	if url.startswith(("Dog breeds: ", "Breed not found")):
		await ctx.send(url)
		return int(url.startswith("Dog breeds: "))
	dog_breed = "Hound" if "hound" in url else url.split("/")[-2]
	emb = misc.bb_embed(
		"Random " + dog_breed.replace("main", "moose").title(),
	).set_image(url=url)
	await ctx.send(embed=emb)
	return 1


@BeardlessBot.command(  # type: ignore[arg-type]
	name="bunny", aliases=misc.AnimalList,
)
async def cmd_animal(ctx: misc.BotContext, *, breed: str = "") -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	assert ctx.invoked_with is not None
	species = ctx.invoked_with.lower()
	try:
		url = await misc.get_animal(species)
	except (misc.AnimalException, ValueError, KeyError) as e:
		logger.exception("%s %s", species, breed)
		misc.log_exception(e, ctx)
		await ctx.send(embed=misc.bb_embed(
			"Something's gone wrong!",
			"Please inform my creator and he'll see what's going on.",
		))
		return 0
	await ctx.send(
		embed=misc.bb_embed("Random " + species.title()).set_image(url=url),
	)
	return 1


# Server-only commands (not usable in DMs):


@BeardlessBot.command(name="mute")  # type: ignore[arg-type]
async def cmd_mute(
	ctx: misc.BotContext,
	target: str | None = None,
	duration: str | None = None,
	*,
	additional: str = "",
) -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild:
		return -1
	if not (mute_target := await misc.process_mute_target(
		ctx, target, BeardlessBot,
	)):
		return 0
	role = await misc.create_muted_role(ctx.guild)
	duration, reason, mute_time = misc.process_mute_duration(
		duration, additional,
	)
	try:
		await mute_target.add_roles(role)
	except nextcord.Forbidden as e:
		misc.log_exception(e, ctx)
		await ctx.send(misc.HierarchyMsg)
		return 0
	addendum = (" for " + duration + ".") if duration is not None else "."
	emb = misc.bb_embed(
		"Beardless Bot Mute", "Muted " + mute_target.mention + addendum,
	).set_author(name=ctx.author, icon_url=misc.fetch_avatar(ctx.author))
	if reason:
		emb.add_field(name="Mute Reason:", value=reason, inline=False)
	await ctx.send(embed=emb)
	if channel := misc.get_log_channel(ctx.guild):
		await channel.send(embed=logs.log_mute(
			mute_target, ctx.message, duration,
		))
	if mute_time:
		# autounmute(mute_target, ctx, mute_time, role, addendum)
		# TODO: use on_close() to make mute times persist through restarts
		# https://github.com/LevBernstein/BeardlessBot/issues/44
		# Autounmute
		logger.info(
			"Muted %s/%i%s Muter: %s/%i. Guild: %s",
			mute_target.name,
			mute_target.id,
			addendum,
			ctx.author.name,
			ctx.author.id,
			ctx.guild.name,
		)
		await asyncio.sleep(mute_time)
		await mute_target.remove_roles(role)
		logger.info(
			"Autounmuted %s after waiting%s", mute_target.name, addendum,
		)
		if channel := misc.get_log_channel(ctx.guild):
			assert isinstance(ctx.author, nextcord.Member)
			await channel.send(embed=logs.log_unmute(mute_target, ctx.author))
	return 1


@BeardlessBot.command(name="unmute")  # type: ignore[arg-type]
async def cmd_unmute(
	ctx: misc.BotContext, target: str | None = None,
) -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild:
		return -1
	report = misc.Naughty.format(ctx.author.mention)
	assert isinstance(ctx.author, nextcord.Member)
	if ctx.author.guild_permissions.manage_messages:
		if not (role := get(ctx.guild.roles, name="Muted")):
			report = "Error! Muted role does not exist! Can't unmute!"
		elif target:
			converter = commands.MemberConverter()
			try:
				muted_member = await converter.convert(ctx, target)
			except commands.MemberNotFound as e:
				misc.log_exception(e, ctx)
				report = "Invalid target! Target must be a mention or user ID."
			else:
				try:
					await muted_member.remove_roles(role)
				except nextcord.Forbidden as e:
					misc.log_exception(e, ctx)
					report = misc.HierarchyMsg
				else:
					report = f"Unmuted {muted_member.mention}."
					if channel := misc.get_log_channel(ctx.guild):
						await channel.send(
							embed=logs.log_unmute(muted_member, ctx.author),
						)
		else:
			report = f"Invalid target, {ctx.author.mention}."
	await ctx.send(embed=misc.bb_embed("Beardless Bot Unmute", report))
	return 1


@BeardlessBot.command(name="purge")  # type: ignore[arg-type]
async def cmd_purge(
	ctx: misc.BotContext, num: str | None = None,
) -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild:
		return -1
	assert hasattr(ctx.author, "guild_permissions")
	if ctx.author.guild_permissions.manage_messages:
		if num is None or not num.isnumeric() or ((limit := int(num)) < 0):
			await ctx.send(embed=misc.bb_embed(
				"Beardless Bot Purge", "Invalid message number!",
			))
			return 0
		assert isinstance(
			ctx.channel,
			nextcord.TextChannel | nextcord.VoiceChannel | nextcord.Thread,
		)
		await ctx.channel.purge(
			limit=limit + 1, check=lambda msg: not msg.pinned,
		)
		return 1
	await ctx.send(embed=misc.bb_embed(
		"Beardless Bot Purge", misc.Naughty.format(ctx.author.mention),
	))
	return 0


@BeardlessBot.command(name="buy")  # type: ignore[arg-type]
async def cmd_buy(
	ctx: misc.BotContext, color: str = "none",
) -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild:
		return -1
	assert isinstance(ctx.author, nextcord.Member)
	report = "Invalid color. Choose blue, red, orange, or pink, {}."
	if (color := color.lower()) in RoleColors:
		if not (role := get(ctx.guild.roles, name="special " + color)):
			report = "That color role does not exist in this server, {}."
		elif role in ctx.author.roles:
			report = "You already have this special color, {}."
		else:
			if not role.color.value:
				await role.edit(colour=nextcord.Colour(RoleColors[color]))
			result, bonus = bucks.write_money(
				ctx.author, -50000, writing=True, adding=True,
			)
			if result == bucks.MoneyFlags.BalanceChanged:
				report = (
					"Color " + role.mention + " purchased successfully, {}!"
				)
				await ctx.author.add_roles(role)
			elif result == bucks.MoneyFlags.CommaInUsername:
				assert isinstance(bonus, str)
				report = bonus
			elif result == bucks.MoneyFlags.Registered:
				report = bucks.NewUserMsg
			else:
				report = (
					"Not enough BeardlessBucks. You need"
					" 50000 to buy a special color, {}."
				)
	await ctx.send(embed=misc.bb_embed(
		"Beardless Bot Special Colors", report.format(ctx.author.mention),
	))
	return 1


@BeardlessBot.command(  # type: ignore[arg-type]
	name="pins", aliases=("sparpins", "howtospar"),
)
async def cmd_pins(ctx: misc.BotContext) -> int:
	if (
		misc.ctx_created_thread(ctx)
		or not ctx.guild
		or not hasattr(ctx.channel, "name")
	):
		return -1
	if await misc.check_for_spar_channel(ctx):
		return 1
	await ctx.send(
		embed=misc.bb_embed(
			f"Try using !spar in the {misc.SparChannelName} channel.",
		).add_field(
			name="To spar someone from your region:",
			value=misc.SparDesc,
			inline=False,
		),
	)
	return 0


@BeardlessBot.command(name="spar")  # type: ignore[arg-type]
async def cmd_spar(
	ctx: misc.BotContext, region: str | None = None, *, additional: str = "",
) -> int:
	if (
		misc.ctx_created_thread(ctx)
		or not ctx.guild
		or not hasattr(ctx.channel, "name")
	):
		return -1
	author = ctx.author.mention
	if ctx.channel.name != misc.SparChannelName:
		await ctx.send(
			f"Please only use !spar in {misc.SparChannelName}, {author}.",
		)
		return 0
	if not region:
		await misc.check_for_spar_channel(ctx)
		return 0
	report = brawl.BadRegion.format(author)
	too_recent: int | None = None
	role: nextcord.Role | None = None
	if (region := region.lower()) in {"usw", "use"}:
		region = region[:2] + "-" + region[2]
	if (
		(pings := SparPings.get(ctx.guild.id)) is not None
		and (value := pings.get(region)) is not None
	):
		if not (role := get(ctx.guild.roles, name=region.upper())):
			role = await ctx.guild.create_role(
				name=region.upper(), mentionable=False, reason="Sparring Role",
			)
		if time() - value > SparCooldown:
			pings[region] = int(time())
			report = f"{role.mention} come spar {author}"
		else:
			too_recent = value
	if role and too_recent:
		hours, seconds = divmod(
			SparCooldown - (int(time()) - too_recent), 3600,
		)
		minutes, seconds = divmod(seconds, 60)
		report = brawl.ping_msg(author, hours, minutes, seconds)
	await ctx.send(report)
	if additional and role and not too_recent:
		await ctx.send(f"Additional info: \"{additional}\"".replace("@", ""))
	return 1


# Commands requiring a Brawlhalla API key:


@BeardlessBot.command(name="brawl")  # type: ignore[arg-type]
async def cmd_brawl(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	if BrawlKey:
		await ctx.send(embed=brawl.brawl_commands())
		return 1
	return 0


@BeardlessBot.command(name="brawlclaim")  # type: ignore[arg-type]
async def cmd_brawlclaim(ctx: misc.BotContext, url_or_id: str = "None") -> int:
	if misc.ctx_created_thread(ctx) or not BrawlKey:
		return -1
	brawl_id = (
		int(url_or_id)
		if url_or_id.isnumeric()
		else await brawl.get_brawl_id(BrawlKey, url_or_id)
	)
	if brawl_id is not None:
		brawl.claim_profile(ctx.author.id, brawl_id)
		report = "Profile claimed."
	else:
		report = "Invalid profile URL/Brawlhalla ID! " + brawl.BadClaim
	await ctx.send(embed=misc.bb_embed(
		"Beardless Bot Brawlhalla Rank", report,
	))
	return 1


@BeardlessBot.command(name="brawlrank")  # type: ignore[arg-type]
async def cmd_brawlrank(ctx: misc.BotContext, *, target: str = "") -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild or not BrawlKey:
		return -1
	# TODO: write valid target method; no need for this copy paste
	# have it return target, report
	rank_target: misc.TargetTypes | None = misc.get_target(ctx, target)
	report = "Invalid target!"
	if isinstance(rank_target, str):
		rank_target = misc.member_search(ctx.message, rank_target)
	if rank_target:
		try:
			emb = await brawl.get_rank(rank_target, BrawlKey)
		except RequestError as e:
			misc.log_exception(e, ctx)
			report = brawl.RequestLimit
		else:
			await ctx.send(embed=emb)
			return 1
	await ctx.send(embed=misc.bb_embed(
		"Beardless Bot Brawlhalla Rank", report,
	))
	return 0


@BeardlessBot.command(name="brawlstats")  # type: ignore[arg-type]
async def cmd_brawlstats(ctx: misc.BotContext, *, target: str = "") -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild or not BrawlKey:
		return -1
	stats_target: misc.TargetTypes | None = misc.get_target(ctx, target)
	report = "Invalid target!"
	if isinstance(stats_target, str):
		stats_target = misc.member_search(ctx.message, stats_target)
	if stats_target:
		try:
			emb = await brawl.get_stats(stats_target, BrawlKey)
		except RequestError as e:
			misc.log_exception(e, ctx)
			report = brawl.RequestLimit
		else:
			await ctx.send(embed=emb)
			return 1
	await ctx.send(embed=misc.bb_embed(
		"Beardless Bot Brawlhalla Stats", report,
	))
	return 0


@BeardlessBot.command(name="brawlclan")  # type: ignore[arg-type]
async def cmd_brawlclan(ctx: misc.BotContext, *, target: str = "") -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild or not BrawlKey:
		return -1
	clan_target: misc.TargetTypes | None = misc.get_target(ctx, target)
	report = "Invalid target!"
	if isinstance(clan_target, str):
		clan_target = misc.member_search(ctx.message, clan_target)
	if clan_target:
		try:
			emb = await brawl.get_clan(clan_target, BrawlKey)
		except RequestError as e:
			misc.log_exception(e, ctx)
			report = brawl.RequestLimit
		else:
			await ctx.send(embed=emb)
			return 1
	await ctx.send(embed=misc.bb_embed(
		"Beardless Bot Brawlhalla Clan", report,
	))
	return 0


@BeardlessBot.command(name="brawllegend")  # type: ignore[arg-type]
async def cmd_brawllegend(ctx: misc.BotContext, legend: str = "") -> int:
	if misc.ctx_created_thread(ctx) or not BrawlKey:
		return -1
	report = (
		"Invalid legend! Please do !brawllegend followed by a legend name."
	)
	if legend:
		try:
			emb = await brawl.legend_info(BrawlKey, legend.lower())
		except RequestError as e:
			misc.log_exception(e, ctx)
			report = brawl.RequestLimit
		else:
			if emb is not None:
				await ctx.send(embed=emb)
				return 1
	await ctx.send(embed=misc.bb_embed(
		"Beardless Bot Brawlhalla Legend Info", report,
	))
	return 0


# Server-specific commands:


@BeardlessBot.command(  # type: ignore[arg-type]
	name="tweet", aliases=("eggtweet",),
)
async def cmd_tweet(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild:
		return -1
	if ctx.guild.id == EggGuildId:
		emb = misc.bb_embed(
			"eggsoup(@eggsouptv)", misc.format_tweet(misc.tweet()), 0x1DA1F2,
		).set_thumbnail(url=(
			"https://pbs.twimg.com/profile_images/13"
			"97696436393836546/NgpD6O57_400x400.jpg"
		))
		await ctx.send(embed=emb)
		return 1
	return 0


@BeardlessBot.command(name="reddit")  # type: ignore[arg-type]
async def cmd_reddit(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild:
		return -1
	if ctx.guild.id == EggGuildId:
		await ctx.send(embed=misc.EggRedditEmbed)
		return 1
	return 0


@BeardlessBot.command(name="guide")  # type: ignore[arg-type]
async def cmd_guide(ctx: misc.BotContext) -> int:
	if misc.ctx_created_thread(ctx) or not ctx.guild:
		return -1
	if ctx.guild.id == EggGuildId:
		await ctx.send(embed=misc.bb_embed(
			"The Eggsoup Improvement Guide",
			"https://www.youtube.com/watch?v=nH0TOoJIU80",
		))
		return 1
	return 0


@BeardlessBot.command(  # type: ignore[arg-type]
	name="search", aliases=("google", "lmgtfy"),
)
async def cmd_search(ctx: misc.BotContext, *, searchterm: str = "") -> int:
	if misc.ctx_created_thread(ctx):
		return -1
	await ctx.send(embed=misc.search(searchterm))
	return 1


# Listeners:


@BeardlessBot.listen()
async def on_command_error(
	ctx: misc.BotContext, e: commands.errors.CommandError,
) -> int:
	"""
	Nextcord command error handler.

	Handle any instances of CommandError that are thrown without taking down
	the whole bot. Two special cases exist here:
		1. CommandNotFound. If someone tries to use a command that does not
		exist, that may be because they are using another bot. Don't do
		anything in that case.
		2. ArgumentParsingError. This is mainly caused by people using unclosed
		quotes--single or double--in the arguments to a command. In that case,
		warn them to be careful with quotation marks.
	No matter what subclass of CommandError it is, log the Exception with the
	misc.logException method.

	Args:
		ctx (misc.botContext): The context in which the command threw an
			Exception
		e (commands.errors.CommandError): The Exception that was thrown

	Returns:
		int: 0 if the Exception was CommandNotFound; otherwise, 0.

	"""
	if isinstance(e, commands.CommandNotFound):
		return 0
	if isinstance(e, commands.ArgumentParsingError):
		await ctx.send(embed=misc.bb_embed(
			"Careful with quotation marks!",
			"Error: Either put everything in quotes or nothing.",
		))
	misc.log_exception(e, ctx)
	return 1


@BeardlessBot.listen("on_message")
async def handle_messages(message: nextcord.Message) -> int:
	"""
	Process messages from users for possible scams.

	Basically just a wrapper to call scamCheck on every message sent in
	a server by a non-bot user.

	Args:
		message (nextcord.Message): The message to process

	Returns:
		int: 0 if the message is from a bot or not sent in a server; -1 if
			the message is flagged as a possible scam; 1 otherwise.

	"""
	if message.author.bot or not message.guild:
		return 0

	if misc.scam_check(message.content):
		await misc.delete_scam_and_notify(message)
		return -1

	return 1


# Main:


def launch() -> None:
	"""
	Launch Beardless Bot.

	Pulls in the Brawlhalla API key and Discord token from .env. BB will still
	run without a Brawlhalla API key, but not having a Discord token is fatal.

	Note that commands.Bot.run() is blocking; you can't include any method
	calls after that if you actually want them to fire.
	"""
	env = dotenv.dotenv_values(".env")
	global BrawlKey  # noqa: PLW0603
	try:
		BrawlKey = env["BRAWLKEY"]
	except KeyError:
		BrawlKey = None
		logger.warning(
			"No Brawlhalla API key. Brawlhalla-specific"
			" commands will not be active.",
		)

	try:
		BeardlessBot.run(env["DISCORDTOKEN"])
	except KeyError:
		logger.exception(
			"Fatal error! DISCORDTOKEN environment variable has not"
			" been defined. See: README.MD's installation section.",
		)
	except nextcord.DiscordException:
		logger.exception("Encountered DiscordException!")


if __name__ == "__main__":  # pragma: no cover
	# Pipe logs to stdout and logs folder
	logging.basicConfig(
		format="%(asctime)s: %(levelname)s: %(message)s",
		datefmt="%m/%d %H:%M:%S",
		level=logging.INFO,
		force=True,
		handlers=[
			logging.FileHandler(datetime.now(misc.TimeZone).strftime(
				"resources/logs/%Y-%m-%d-%H-%M-%S.log",
			)), logging.StreamHandler(sys.stdout),
		],
	)

	# HTTPX tends to flood logs with INFO-level calls; set it to >= WARNING
	logging.getLogger("httpx").setLevel(logging.WARNING)

	launch()
