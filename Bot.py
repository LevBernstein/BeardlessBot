"""Beardless Bot"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from random import choice, randint
from sys import stdout
from time import time
from typing import Final

import aiofiles
import nextcord
from dotenv import dotenv_values
from nextcord.ext import commands
from nextcord.utils import get

import brawl
import bucks
import logs
import misc

with Path("README.MD").open() as rd:
	__version__ = " ".join(rd.read().split(" ")[3:6])

# This dictionary is for keeping track of pings in the lfs channels.
sparPings: dict[int, dict[str, int]] = {}

# This array stores the active instances of blackjack.
games: list[bucks.BlackjackGame] = []

# Replace OWNER_ID with your Discord user id
OWNER_ID: Final[int] = 196354892208537600
EGG_GUILD_ID: Final[int] = 442403231864324119
SPAR_COOLDOWN: Final[int] = 7200

bot = commands.Bot(
	command_prefix="!",
	case_insensitive=True,
	help_command=misc.BBHelpCommand(),
	intents=nextcord.Intents.all(),
	chunk_guilds_at_startup=False,
	owner_id=OWNER_ID
)


@bot.event
async def on_ready() -> None:
	"""
	Startup method. Fires whenever the Bot connects to the Gateway.

	on_ready handles setting the Bot's status and avatar; if the Bot is
	launched many times within a short period, you may be rate limited,
	triggering an HTTPException.

	The method also initializes sparPings to enable a 2-hour cooldown for the
	spar command, and chunks all guilds (caches them) to speed up operations.
	This also allows you to get a good idea of how many unique users are in
	all guilds in which Beardless Bot operates.
	"""
	logging.info("Beardless Bot %s online!", __version__)

	status = nextcord.Game(name="try !blackjack and !flip")
	try:
		await bot.change_presence(activity=status)
		logging.info("Status updated!")
		assert bot.user is not None
		async with aiofiles.open("resources/images/prof.png", "rb") as f:
			await bot.user.edit(avatar=await f.read())
	except nextcord.HTTPException:
		logging.exception("Failed to update avatar or status!")
	except FileNotFoundError:
		logging.exception(
			"Avatar file not found! Check your directory structure."
		)
	else:
		logging.info("Avatar updated!")

	try:
		members = set(bot.guilds[0].members)
	except IndexError:
		logging.exception("Bot is in no servers! Add it to a server.")
	else:
		for guild in bot.guilds:
			# Do this first so all servers can spar immediately
			sparPings[guild.id] = dict.fromkeys(brawl.regions, 0)
		logging.info("Zeroed sparpings! Sparring is now possible.")
		logging.info("Chunking guilds, collecting analytics...")
		for guild in bot.guilds:
			members = members.union(set(guild.members))
			await guild.chunk()

		logging.info(
			"Chunking complete! Beardless Bot serves"
			" %i unique members across %i servers.",
			len(members),
			len(bot.guilds)
		)


@bot.event
async def on_guild_join(guild: nextcord.Guild) -> None:
	logging.info("Just joined %s!", guild.name)

	if guild.me.guild_permissions.administrator:
		role = get(guild.roles, name="Beardless Bot")
		assert role is not None
		for channel in guild.text_channels:
			try:
				await channel.send(embed=misc.onJoin(guild, role))
			except nextcord.DiscordException:
				logging.exception("Failed to send onJoin msg!")
			else:
				logging.info("Sent join message in %s.", channel.name)
				break
		logging.info("Beardless Bot is now in %i servers.", len(bot.guilds))
		sparPings[guild.id] = dict.fromkeys(brawl.regions, 0)
	else:
		logging.warning("Not given admin perms in %s.", guild.name)
		for channel in guild.text_channels:
			try:
				await channel.send(embed=misc.noPerms)
			except nextcord.DiscordException:
				logging.exception("Failed to send noPerms msg!")
			else:
				logging.info("Sent no perms msg in %s.", channel.name)
				break
		await guild.leave()
		logging.info("Left %s.", guild.name)


# Event logging


@bot.event
async def on_message_delete(msg: nextcord.Message) -> nextcord.Embed | None:
	if (
		msg.guild
		and (
			msg.channel.name != "bb-log"  # type: ignore[union-attr]
			or msg.content
		)
		and (channel := misc.getLogChannel(msg.guild))
	):
		emb = logs.logDeleteMsg(msg)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_bulk_message_delete(
	msgList: list[nextcord.Message]
) -> nextcord.Embed | None:
	assert msgList[0].guild is not None
	if channel := misc.getLogChannel(msgList[0].guild):
		emb = logs.logPurge(msgList[0], msgList)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_message_edit(
	before: nextcord.Message, after: nextcord.Message
) -> nextcord.Embed | None:
	if after.guild and (before.content != after.content):
		assert isinstance(
			after.channel, nextcord.TextChannel | nextcord.Thread
		)
		if misc.scamCheck(after.content):
			logging.info(
				"Possible nitro scam detected in %s/%i",
				after.guild.name,
				after.guild.id
			)
			if not (role := get(after.guild.roles, name="Muted")):
				role = await misc.createMutedRole(after.guild)
			# TODO: after migrating from MockUser to MockMember,
			# add assert not isinstance(after.author, nextcord.User)
			# and remove below type ignore
			await after.author.add_roles(role)  # type: ignore[union-attr]
			for channel in after.guild.text_channels:
				if channel.name in {"infractions", "bb-log"}:
					await channel.send(
						misc.scamReport.format(
							after.author.mention,
							after.channel.mention,
							after.content
						)
					)
			await after.channel.send(misc.scamDelete)
			await after.author.send(misc.scamDM.format(after.guild))
			await after.delete()
		if logChannel := misc.getLogChannel(after.guild):
			emb = logs.logEditMsg(before, after)
			await logChannel.send(embed=emb)
			return emb
	return None


@bot.event
async def on_reaction_clear(
	msg: nextcord.Message, reactions: list[nextcord.Reaction]
) -> nextcord.Embed | None:
	assert msg.guild is not None
	if channel := misc.getLogChannel(msg.guild):
		emb = logs.logClearReacts(msg, reactions)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_guild_channel_delete(
	ch: nextcord.abc.GuildChannel
) -> nextcord.Embed | None:
	if channel := misc.getLogChannel(ch.guild):
		emb = logs.logDeleteChannel(ch)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_guild_channel_create(
	ch: nextcord.abc.GuildChannel
) -> nextcord.Embed | None:
	if channel := misc.getLogChannel(ch.guild):
		emb = logs.logCreateChannel(ch)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_member_join(member: nextcord.Member) -> nextcord.Embed | None:
	if channel := misc.getLogChannel(member.guild):
		emb = logs.logMemberJoin(member)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_member_remove(member: nextcord.Member) -> nextcord.Embed | None:
	if channel := misc.getLogChannel(member.guild):
		emb = logs.logMemberRemove(member)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_member_update(
	before: nextcord.Member, after: nextcord.Member
) -> nextcord.Embed | None:
	if channel := misc.getLogChannel(before.guild):
		emb = None
		if before.nick != after.nick:
			emb = logs.logMemberNickChange(before, after)
		elif before.roles != after.roles:
			emb = logs.logMemberRolesChange(before, after)
		if emb:
			await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_member_ban(
	guild: nextcord.Guild, member: nextcord.Member
) -> nextcord.Embed | None:
	if channel := misc.getLogChannel(guild):
		emb = logs.logBan(member)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_member_unban(
	guild: nextcord.Guild, member: nextcord.Member
) -> nextcord.Embed | None:
	if channel := misc.getLogChannel(guild):
		emb = logs.logUnban(member)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_thread_join(thread: nextcord.Thread) -> nextcord.Embed | None:
	if thread.me:
		return None
	await thread.join()
	if channel := misc.getLogChannel(thread.guild):
		emb = logs.logCreateThread(thread)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_thread_delete(thread: nextcord.Thread) -> nextcord.Embed | None:
	if channel := misc.getLogChannel(thread.guild):
		emb = logs.logDeleteThread(thread)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_thread_update(
	before: nextcord.Thread, after: nextcord.Thread
) -> nextcord.Embed | None:
	if channel := misc.getLogChannel(after.guild):
		emb = None
		# TODO: log Thread.locked/unlocked
		if before.archived and not after.archived:
			emb = logs.logThreadUnarchived(after)
		elif after.archived and not before.archived:
			emb = logs.logThreadArchived(after)
		if emb:
			await channel.send(embed=emb)
		return emb
	return None


# Commands:


@bot.command(name="flip")  # type: ignore[arg-type]
async def cmdFlip(ctx: misc.botContext, bet: str = "10") -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if bucks.activeGame(games, ctx.author):
		report = bucks.finMsg.format(ctx.author.mention)
	else:
		report = bucks.flip(ctx.author, bet.lower())
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Coin Flip", report))
	return 1


@bot.command(name="blackjack", aliases=("bj",))  # type: ignore[arg-type]
async def cmdBlackjack(ctx: misc.botContext, bet: str = "10") -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if bucks.activeGame(games, ctx.author):
		report = bucks.finMsg.format(ctx.author.mention)
	else:
		report, game = bucks.blackjack(ctx.author, bet)
		if game:
			games.append(game)
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Blackjack", report))
	return 1


@bot.command(name="deal", aliases=("hit",))  # type: ignore[arg-type]
async def cmdDeal(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if "," in ctx.author.name:
		report = bucks.commaWarn.format(ctx.author.mention)
	else:
		report = bucks.noGameMsg.format(ctx.author.mention)
		if game := bucks.activeGame(games, ctx.author):
			report = game.deal()
			if game.checkBust() or game.perfect():
				game.checkBust()
				bucks.writeMoney(
					ctx.author, game.bet, writing=True, adding=True
				)
				games.remove(game)
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Blackjack", report))
	return 1


@bot.command(name="stay", aliases=("stand",))  # type: ignore[arg-type]
async def cmdStay(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if "," in ctx.author.name:
		report = bucks.commaWarn.format(ctx.author.mention)
	else:
		report = bucks.noGameMsg.format(ctx.author.mention)
		if game := bucks.activeGame(games, ctx.author):
			result = game.stay()
			report = game.message
			if result and game.bet:
				written, bonus = bucks.writeMoney(
					ctx.author, game.bet, writing=True, adding=True
				)
				if written == -1:
					assert isinstance(bonus, str)
					report = bonus
			games.remove(game)
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Blackjack", report))
	return 1


@bot.command(name="av", aliases=("avatar",))  # type: ignore[arg-type]
async def cmdAv(ctx: misc.botContext, *, target: str = "") -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	avTarget: nextcord.Member | nextcord.User | str
	if ctx.message.mentions:
		avTarget = ctx.message.mentions[0]
	elif target:
		avTarget = target
	else:
		avTarget = ctx.author
	await ctx.send(embed=misc.av(avTarget, ctx.message))
	return 1


@bot.command(name="info")  # type: ignore[arg-type]
async def cmdInfo(ctx: misc.botContext, *, target: str = "") -> int:
	if not ctx.guild:
		return 0
	if misc.ctxCreatedThread(ctx):
		return -1
	infoTarget: nextcord.Member | str
	if ctx.message.mentions:
		assert isinstance(ctx.message.mentions[0], nextcord.Member)
		infoTarget = ctx.message.mentions[0]
	elif target:
		infoTarget = target
	else:
		assert isinstance(ctx.author, nextcord.Member)
		infoTarget = ctx.author
	await ctx.send(embed=misc.info(infoTarget, ctx.message))
	return 1


@bot.command(name="balance", aliases=("bal",))  # type: ignore[arg-type]
async def cmdBalance(ctx: misc.botContext, *, target: str = "") -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	balTarget: nextcord.Member | nextcord.User | str
	if ctx.message.mentions:
		balTarget = ctx.message.mentions[0]
	elif target:
		balTarget = target
	else:
		balTarget = ctx.author
	await ctx.send(embed=bucks.balance(balTarget, ctx.message))
	return 1


@bot.command(  # type: ignore[arg-type]
	name="leaderboard", aliases=("leaderboards", "lb")
)
async def cmdLeaderboard(ctx: misc.botContext, *, target: str = "") -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	lbTarget: nextcord.Member | nextcord.User | str
	if ctx.message.mentions:
		lbTarget = ctx.message.mentions[0]
	elif target:
		lbTarget = target
	else:
		lbTarget = ctx.author
	await ctx.send(embed=bucks.leaderboard(lbTarget, ctx.message))
	return 1


@bot.command(name="dice")  # type: ignore[arg-type]
async def cmdDice(ctx: misc.botContext) -> int | nextcord.Embed:
	if misc.ctxCreatedThread(ctx):
		return -1
	emb = misc.bbEmbed("Beardless Bot Dice", misc.diceMsg)
	await ctx.send(embed=emb)
	return emb


@bot.command(name="reset")  # type: ignore[arg-type]
async def cmdReset(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=bucks.reset(ctx.author))
	return 1


@bot.command(name="register")  # type: ignore[arg-type]
async def cmdRegister(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=bucks.register(ctx.author))
	return 1


@bot.command(name="bucks")  # type: ignore[arg-type]
async def cmdBucks(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=misc.bbEmbed("BeardlessBucks", bucks.buckMsg))
	return 1


@bot.command(name="hello", aliases=("hi",))  # type: ignore[arg-type]
async def cmdHello(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(choice(misc.greetings))
	return 1


@bot.command(name="source")  # type: ignore[arg-type]
async def cmdSource(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	source = (
		"Most facts taken from [this website]"
		"(https://www.thefactsite.com/1000-interesting-facts/)."
	)
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Fun Facts", source))
	return 1


@bot.command(name="add", aliases=("join", "invite"))  # type: ignore[arg-type]
async def cmdAdd(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=misc.inviteMsg)
	return 1


@bot.command(name="rohan")  # type: ignore[arg-type]
async def cmdRohan(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(file=nextcord.File("resources/images/cute.png"))
	return 1


@bot.command(name="random")  # type: ignore[arg-type]
async def cmdRandomBrawl(
	ctx: misc.botContext, ranType: str = "None"
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	emb = await brawl.randomBrawl(ranType.lower(), brawlKey)
	await ctx.send(embed=emb)
	return 1


@bot.command(name="fact")  # type: ignore[arg-type]
async def cmdFact(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(
		embed=misc.bbEmbed(
			f"Beardless Bot Fun Fact #{randint(1, 111111111)}", misc.fact()
		)
	)
	return 1


@bot.command(  # type: ignore[arg-type]
	name="animals", aliases=("animal", "pets")
)
async def cmdAnimals(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=misc.animals)
	return 1


@bot.command(name="define")  # type: ignore[arg-type]
async def cmdDefine(ctx: misc.botContext, *, words: str = "") -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	try:
		emb = await misc.define(words)
		await ctx.send(embed=emb)
	except Exception as e:
		await ctx.send(
			"The API I use to get definitions is experiencing server outages"
			" and performance issues. Please be patient."
		)
		misc.logException(e, ctx)
		return 0
	return 1


@bot.command(name="ping")  # type: ignore[arg-type]
async def cmdPing(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	assert bot.user is not None
	emb = misc.bbEmbed(
		"Pinged", f"Beardless Bot's latency is {int(1000 * bot.latency)} ms."
	).set_thumbnail(url=misc.fetchAvatar(bot.user))
	await ctx.send(embed=emb)
	return 1


@bot.command(name="roll")  # type: ignore[arg-type]
async def cmdRoll(
	ctx: misc.botContext, dice: str = "None"
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=misc.rollReport(dice, ctx.author))
	return 1


@bot.command(  # type: ignore[arg-type]
	name="dog", aliases=(*misc.animalList, "moose")
)
async def cmdAnimal(
	ctx: misc.botContext, breed: str | None = None
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	assert ctx.invoked_with is not None
	species = ctx.invoked_with.lower()
	if breed:
		breed = breed.lower()
	if "moose" in {species, breed}:
		try:
			moose = await misc.animal("moose", "moose")
		except Exception as e:
			misc.logException(e, ctx)
			await ctx.send(
				embed=misc.bbEmbed(
					"Something's gone wrong with the Moose API!",
					"Please inform my creator and he'll see what's going on."
				)
			)
			return 0
		emb = misc.bbEmbed("Random Moose").set_image(url=moose)
		await ctx.send(embed=emb)
		return 1
	if species == "dog":
		try:
			dogUrl = await misc.animal("dog", breed)
		except Exception as e:
			logging.exception("%s %s", species, breed)
			misc.logException(e, ctx)
			await ctx.send(
				embed=misc.bbEmbed(
					"Something's gone wrong with the Dog API!",
					"Please inform my creator and he'll see what's going on."
				)
			)
			return 0
		if dogUrl.startswith(("Dog breeds: ", "Breed not found")):
			await ctx.send(dogUrl)
			return int(dogUrl.startswith("Dog breeds: "))
		dogBreed = "Hound" if "hound" in dogUrl else dogUrl.split("/")[-2]
		emb = misc.bbEmbed(
			"Random " + dogBreed.title()
		).set_image(url=dogUrl)
		await ctx.send(embed=emb)
		return 1
	emb = misc.bbEmbed("Random " + species.title())
	try:
		url = await misc.animal(species)
		emb.set_image(url=url)
	except Exception as e:
		logging.exception("%s %s", species, breed)
		misc.logException(e, ctx)
		await ctx.send(
			embed=misc.bbEmbed(
				"Something's gone wrong!",
				"Please inform my creator and he'll see what's going on."
			)
		)
		return 0
	await ctx.send(embed=emb)
	return 1


# Server-only commands (not usable in DMs):


@bot.command(name="mute")  # type: ignore[arg-type]
async def cmdMute(
	ctx: misc.botContext,
	target: str | None = None,
	duration: str | None = None,
	*,
	additional: str = ""
) -> int:
	if not ctx.guild:
		return 0
	if misc.ctxCreatedThread(ctx):
		return -1
	if not (
		ctx  # type: ignore[union-attr]
		.author
		.guild_permissions
		.manage_messages
	):
		await ctx.send(misc.naughty.format(ctx.author.mention))
		return 0
	if not target:
		await ctx.send(f"Please specify a target, {ctx.author.mention}.")
		return 0
	# TODO: switch to converter in arg
	converter = commands.MemberConverter()
	try:
		muteTarget = await converter.convert(ctx, target)
	except commands.MemberNotFound as e:
		misc.logException(e, ctx)
		await ctx.send(
			embed=misc.bbEmbed(
				"Beardless Bot Mute",
				"Invalid target! Target must be a mention or user ID."
				f"\nSpecific error: {e}"
			)
		)
		return 0
	# If user tries to mute BB:
	if bot.user is not None and muteTarget.id == bot.user.id:
		await ctx.send("I am too powerful to be muted. Stop trying.")
		return 0
	if not (role := get(ctx.guild.roles, name="Muted")):
		role = await misc.createMutedRole(ctx.guild)
	mTime = mString = None
	if duration:
		duration = duration.lower()
		times = (
			("day", 86400.0),
			("hour", 3600.0),
			("minute", 60.0),
			("second", 1.0)
		)

		# prossesing duration here makes life easier
		lastNumeric = 0
		for c in duration:
			if not c.isnumeric():
				break
			lastNumeric += 1

		if lastNumeric == 0:
			# treat duration as mute reason
			additional = duration + " " + additional
			duration = None
		else:
			unit = duration[lastNumeric:]
			unitIsValid = False
			for mPair in times:
				# Check for first char, whole word, plural
				if unit in {mPair[0][0], mPair[0], mPair[0] + "s"}:
					unitIsValid = True
					duration = duration[:lastNumeric]  # the numeric part
					mTime = float(duration) * mPair[1]
					mString = " " + mPair[0] + ("" if duration == "1" else "s")
					break
			if not unitIsValid:
				# treat duration as mute reason
				additional = duration + " " + additional
				duration = None

	try:
		await muteTarget.add_roles(role)
	except nextcord.DiscordException as e:
		misc.logException(e, ctx)
		await ctx.send(misc.hierarchyMsg)
		return 0
	report = "Muted " + muteTarget.mention
	addendum = (
		" for " + duration + mString + "."  # type: ignore[operator]
	) if None not in {duration, mString} else "."
	emb = misc.bbEmbed("Beardless Bot Mute", report + addendum).set_author(
		name=ctx.author, icon_url=misc.fetchAvatar(ctx.author)
	)
	if additional:
		emb.add_field(name="Mute Reason:", value=additional, inline=False)
	await ctx.send(embed=emb)
	if channel := misc.getLogChannel(ctx.guild):
		await channel.send(
			embed=logs.logMute(
				muteTarget,
				ctx.message,
				duration,
				mString,
				mTime
			)
		)
	if mTime:
		# Autounmute
		logging.info(
			"Muted %s/%i%s Muter: %s/%i. Guild: %s",
			muteTarget.name,
			muteTarget.id,
			addendum,
			ctx.author.name,
			ctx.author.id,
			ctx.guild.name
		)
		await asyncio.sleep(mTime)
		await muteTarget.remove_roles(role)
		logging.info(
			"Autounmuted %s after waiting%s", muteTarget.name, addendum
		)
		if channel := misc.getLogChannel(ctx.guild):
			await channel.send(
				embed=logs.logUnmute(
					muteTarget,
					ctx.author  # type: ignore[arg-type]
				)
			)
	return 1


@bot.command(name="unmute")  # type: ignore[arg-type]
async def cmdUnmute(
	ctx: misc.botContext, target: str | None = None
) -> int:
	if not ctx.guild:
		return 0
	if misc.ctxCreatedThread(ctx):
		return -1
	report = misc.naughty.format(ctx.author.mention)
	if (
		ctx  # type: ignore[union-attr]
		.author
		.guild_permissions
		.manage_messages
	):
		if not (role := get(ctx.guild.roles, name="Muted")):
			report = "Error! Muted role does not exist! Can't unmute!"
		elif target:
			converter = commands.MemberConverter()
			try:
				mutedMember = await converter.convert(ctx, target)
				await mutedMember.remove_roles(role)
			except commands.MemberNotFound as e:
				misc.logException(e, ctx)
				report = "Invalid target! Target must be a mention or user ID."
			except nextcord.DiscordException as e:
				misc.logException(e, ctx)
				report = misc.hierarchyMsg
			else:
				report = f"Unmuted {mutedMember.mention}."
				if channel := misc.getLogChannel(ctx.guild):
					await channel.send(
						embed=logs.logUnmute(
							mutedMember,
							ctx.author  # type: ignore[arg-type]
						)
					)
		else:
			report = f"Invalid target, {ctx.author.mention}."
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Unmute", report))
	return 1


@bot.command(name="purge")  # type: ignore[arg-type]
async def cmdPurge(
	ctx: misc.botContext, num: str | None = None
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.guild:
		if (
			ctx  # type: ignore[union-attr]
			.author
			.guild_permissions
			.manage_messages
		):
			if num is None or not num.isnumeric() or ((mNum := int(num)) < 0):
				emb = misc.bbEmbed(
					"Beardless Bot Purge", "Invalid message number!"
				)
				await ctx.send(embed=emb)
				return 0
			await ctx.channel.purge(  # type: ignore[union-attr]
				limit=mNum + 1, check=lambda msg: not msg.pinned
			)
			return 1
		desc = misc.naughty.format(ctx.author.mention)
		await ctx.send(embed=misc.bbEmbed("Beardless Bot Purge", desc))
	return 0


@bot.command(name="buy")  # type: ignore[arg-type]
async def cmdBuy(
	ctx: misc.botContext, color: str = "none"
) -> int:
	if not ctx.guild:
		return 0
	if misc.ctxCreatedThread(ctx):
		return -1
	report = "Invalid color. Choose blue, red, orange, or pink, {}."
	color = color.lower()
	colors = {
		"blue": 0x3C9EFD,
		"pink": 0xD300FF,
		"orange": 0xFAAA24,
		"red": 0xF5123D
	}
	if color in colors:
		if not (role := get(ctx.guild.roles, name="special " + color)):
			report = "That color role does not exist in this server, {}."
		elif role in ctx.author.roles:  # type: ignore[union-attr]
			report = "You already have this special color, {}."
		else:
			if not role.color.value:
				await role.edit(colour=nextcord.Colour(colors[color]))
			report = (
				"Not enough BeardlessBucks. You need"
				" 50000 to buy a special color, {}."
			)
			result, bonus = bucks.writeMoney(
				ctx.author, -50000, writing=True, adding=True
			)
			if result == 1:
				report = (
					f"Color {role.mention}"
					" purchased successfully, {}!"
				)
				await ctx.author.add_roles(role)  # type: ignore[union-attr]
			if result == -1:
				assert isinstance(bonus, str)
				report = bonus
			if result == 2:
				report = bucks.newUserMsg
	await ctx.send(
		embed=misc.bbEmbed(
			"Beardless Bot Special Colors",
			report.format(ctx.author.mention)
		)
	)
	return 1


@bot.command(  # type: ignore[arg-type]
	name="pins", aliases=("sparpins", "howtospar")
)
async def cmdPins(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.guild:
		if ctx.channel.name == "looking-for-spar":  # type: ignore[union-attr]
			await ctx.send(embed=misc.sparPins)
			return 1
		await ctx.send(
			embed=misc.bbEmbed(
				"Try using !spar in the looking-for-spar channel."
			).add_field(
				name="To spar someone from your region:",
				value=misc.sparDesc,
				inline=False
			)
		)
	return 0


@bot.command(name="spar")  # type: ignore[arg-type]
async def cmdSpar(
	ctx: misc.botContext, region: str | None = None, *, additional: str = ""
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not ctx.guild:
		return 0
	author = ctx.author.mention
	if ctx.channel.name != "looking-for-spar":  # type: ignore[union-attr]
		await ctx.send(f"Please only use !spar in looking-for-spar, {author}.")
		return 0
	if not region:
		await ctx.send(embed=misc.sparPins)
		return 0
	report = brawl.badRegion.format(author)
	tooRecent: int | None = None
	role: nextcord.Role | None = None
	if (region := region.lower()) in {"usw", "use"}:
		region = region[:2] + "-" + region[2]
	for guild, pings in sparPings.items():
		if guild == ctx.guild.id:
			for key, value in pings.items():
				if key == region:
					if not (role := get(ctx.guild.roles, name=key.upper())):
						role = await ctx.guild.create_role(
							name=key.upper(), mentionable=False
						)
					if time() - value > SPAR_COOLDOWN:
						pings[key] = int(time())
						report = f"{role.mention} come spar {author}"
					else:
						tooRecent = value
					break
			break
	if role and tooRecent:
		hours, seconds = divmod(
			SPAR_COOLDOWN - (int(time()) - tooRecent), 3600
		)
		minutes, seconds = divmod(seconds, 60)
		report = brawl.pingMsg(author, hours, minutes, seconds)
	await ctx.send(report)
	if additional and role and not tooRecent:
		await ctx.send(
			f"Additional info: \"{additional}\"".replace("@", "")
		)
	return 1


# Commands requiring a Brawlhalla API key:


@bot.command(name="brawl")  # type: ignore[arg-type]
async def cmdBrawl(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if brawlKey:
		await ctx.send(embed=brawl.brawlCommands())
		return 1
	return 0


@bot.command(name="brawlclaim")  # type: ignore[arg-type]
async def cmdBrawlclaim(
	ctx: misc.botContext, profUrl: str = "None"
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not brawlKey:
		return 0
	brawlId: int | None
	if profUrl.isnumeric():
		brawlId = int(profUrl)
	else:
		brawlId = await brawl.getBrawlId(brawlKey, profUrl)
	if brawlId is not None:
		try:
			brawl.claimProfile(ctx.author.id, brawlId)
		except Exception as e:
			misc.logException(e, ctx)
			report = brawl.reqLimit
		else:
			report = "Profile claimed."
	else:
		report = "Invalid profile URL/Brawlhalla ID! " + brawl.badClaim
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Rank", report)
	)
	return 1


@bot.command(name="brawlrank")  # type: ignore[arg-type]
async def cmdBrawlrank(
	ctx: misc.botContext, *, target: str = ""
) -> int | None:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not (brawlKey and ctx.guild):
		return 0
	# TODO: write valid target method; no need for this copy paste
	# have it return target, report

	rankTarget: misc.targetTypes = (
		ctx.message.mentions[0]
		if ctx.message.mentions
		else target or ctx.author
	)
	if isinstance(rankTarget, str):
		report = "Invalid target!"
		rankTarget = misc.memSearch(ctx.message, rankTarget)
	if rankTarget:
		try:
			emb = await brawl.getRank(
				rankTarget,  # type: ignore[arg-type]
				brawlKey
			)
			await ctx.send(embed=emb)
		except Exception as e:
			misc.logException(e, ctx)
			report = brawl.reqLimit
		else:
			return None
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Rank", report)
	)
	return 1


@bot.command(name="brawlstats")  # type: ignore[arg-type]
async def cmdBrawlstats(ctx: misc.botContext, *, target: str = "") -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not (brawlKey and ctx.guild):
		return 0
	statsTarget: misc.targetTypes = (
		ctx.message.mentions[0]
		if ctx.message.mentions
		else target or ctx.author
	)
	if isinstance(statsTarget, str):
		report = "Invalid target!"
		statsTarget = misc.memSearch(ctx.message, statsTarget)
	if statsTarget:
		try:
			emb = await brawl.getStats(
				statsTarget,  # type: ignore[arg-type]
				brawlKey
			)
			await ctx.send(embed=emb)
		except Exception as e:
			misc.logException(e, ctx)
			report = brawl.reqLimit
		else:
			return 1
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Stats", report)
	)
	return 0


@bot.command(name="brawlclan")  # type: ignore[arg-type]
async def cmdBrawlclan(
	ctx: misc.botContext, *, target: str = ""
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not (brawlKey and ctx.guild):
		return 0
	clanTarget: misc.targetTypes = (
		ctx.message.mentions[0]
		if ctx.message.mentions
		else target or ctx.author
	)
	if isinstance(clanTarget, str):
		report = "Invalid target!"
		clanTarget = misc.memSearch(ctx.message, clanTarget)
	if clanTarget:
		try:
			emb = await brawl.getClan(
				clanTarget,  # type: ignore[arg-type]
				brawlKey
			)
			await ctx.send(embed=emb)
		except Exception as e:
			misc.logException(e, ctx)
			report = brawl.reqLimit
		else:
			return 1
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Clan", report)
	)
	return 0


@bot.command(name="brawllegend")  # type: ignore[arg-type]
async def cmdBrawllegend(
	ctx: misc.botContext, legend: str | None = None
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not brawlKey:
		return 0
	report = (
		"Invalid legend! Please do !brawllegend followed by a legend name."
	)
	if legend:
		try:
			emb = await brawl.legendInfo(brawlKey, legend.lower())
		except Exception as e:
			misc.logException(e, ctx)
			report = brawl.reqLimit
		else:
			if emb:
				await ctx.send(embed=emb)
				return 1
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Legend Info", report)
	)
	return 0


# Server-specific commands:


@bot.command(name="tweet", aliases=("eggtweet",))  # type: ignore[arg-type]
async def cmdTweet(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.guild and ctx.guild.id == EGG_GUILD_ID:
		emb = misc.bbEmbed(
			"eggsoup(@eggsouptv)", misc.formattedTweet(misc.tweet()), 0x1DA1F2
		).set_thumbnail(url=misc.tweetThumb)
		await ctx.send(embed=emb)
		return 1
	return 0


@bot.command(name="reddit")  # type: ignore[arg-type]
async def cmdReddit(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.guild and ctx.guild.id == EGG_GUILD_ID:
		await ctx.send(embed=misc.redditEmb)
		return 1
	return 0


@bot.command(name="guide")  # type: ignore[arg-type]
async def cmdGuide(ctx: misc.botContext) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.guild and ctx.guild.id == EGG_GUILD_ID:
		await ctx.send(
			embed=misc.bbEmbed(
				"The Eggsoup Improvement Guide",
				"https://www.youtube.com/watch?v=nH0TOoJIU80"
			)
		)
		return 1
	return 0


@bot.command(  # type: ignore[arg-type]
	name="search", aliases=("google", "lmgtfy")
)
async def cmdSearch(
	ctx: misc.botContext, *, arg: str = ""
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=misc.search(arg))
	return 1


@bot.listen()
async def on_command_error(
	ctx: misc.botContext, e: commands.errors.CommandError
) -> int:
	if isinstance(e, commands.CommandNotFound):
		return 0
	if isinstance(e, commands.ArgumentParsingError):
		await ctx.send(
			embed=misc.bbEmbed(
				"Careful with quotation marks!",
				"Error: Either put everything in quotes or nothing."
			)
		)
	misc.logException(e, ctx)
	return 1


@bot.listen("on_message")
async def handleMessages(message: nextcord.Message) -> int:
	if message.author.bot or not message.guild:
		return -1

	if misc.scamCheck(message.content.lower()):
		logging.info(
			"Possible nitro scam detected in %s/%i",
			message.guild.name,
			message.guild.id
		)
		author = message.author
		if not (role := get(message.guild.roles, name="Muted")):
			role = await misc.createMutedRole(message.guild)
		await author.add_roles(role)  # type: ignore[union-attr]
		for channel in message.guild.text_channels:
			if channel.name in {"infractions", "bb-log"}:
				await channel.send(
					misc.scamReport.format(
						author.mention,
						message.channel.mention,  # type: ignore[union-attr]
						message.content
					)
				)
		await message.channel.send(misc.scamDelete)
		await author.send(misc.scamDM.format(message.guild))
		await message.delete()
		return -1

	return 1


if __name__ == "__main__":
	logging.basicConfig(
		format="%(asctime)s: %(levelname)s: %(message)s",
		datefmt="%m/%d %H:%M:%S",
		level=logging.INFO,
		force=True,
		handlers=[
			logging.FileHandler(
				datetime.now().strftime("resources/logs/%Y-%m-%d-%H-%M-%S.log")
			),
			logging.StreamHandler(stdout)
		]
	)

	logging.getLogger("httpx").setLevel(logging.WARNING)

	env = dotenv_values(".env")

	try:
		brawlKey = env["BRAWLKEY"]
	except KeyError:
		brawlKey = None
		logging.warning(
			"No Brawlhalla API key. Brawlhalla-specific"
			" commands will not be active."
		)

	try:
		bot.run(env["DISCORDTOKEN"])
	except KeyError:
		logging.exception(
			"Fatal error! DISCORDTOKEN environment variable has not"
			" been defined. See: README.MD's installation section."
		)
	except nextcord.DiscordException:
		logging.exception("Encountered DiscordException!")
