"""Beardless Bot"""
with open("README.MD") as f:
	__version__ = " ".join(f.read().split(" ")[3:6])

import asyncio
import logging
from datetime import datetime
from random import choice, randint
from sys import stdout
from time import time
from typing import Dict, Final, List, Optional, Union, no_type_check

import aiofiles
import nextcord
from dotenv import dotenv_values
from nextcord.ext import commands
from nextcord.utils import get

import brawl
import bucks
import logs
import misc

# This dictionary is for keeping track of pings in the lfs channels.
sparPings: Dict[int, Dict[str, int]] = {}

# This array stores the active instances of blackjack.
games: List[bucks.BlackjackGame] = []

# Replace OWNER_ID with your Discord user id
OWNER_ID: Final[int] = 196354892208537600

bot = commands.Bot(
	command_prefix="!",
	case_insensitive=True,
	help_command=misc.bbHelpCommand(command_attrs={"aliases": ["commands"]}),
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
	logging.info(f"Beardless Bot {__version__} online!")

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

	# Initialize ping waiting time to 0 for each server, get server size:
	global sparPings
	logging.info("Chunking and collecting analytics...")
	try:
		members = set(bot.guilds[0].members)
	except IndexError:
		logging.exception("Bot is in no servers! Add it to a server.")
	else:
		for guild in bot.guilds:
			sparPings[guild.id] = {r: 0 for r in brawl.regions}
			members = members.union(set(guild.members))
			await guild.chunk()

		logging.info(
			f"Done! Beardless Bot serves {len(members)} unique"
			f" members across {len(bot.guilds)} servers."
		)


@bot.event
async def on_guild_join(guild: nextcord.Guild) -> None:
	logging.info(f"Just joined {guild.name}!")

	if guild.me.guild_permissions.administrator:
		role = get(guild.roles, name="Beardless Bot")
		assert role is not None
		for channel in guild.text_channels:
			try:
				await channel.send(embed=misc.onJoin(guild, role))
			except nextcord.DiscordException as e:
				logging.exception(e)
			else:
				logging.info(f"Sent join message in {channel.name}.")
				break
		logging.info(f"Beardless Bot is now in {len(bot.guilds)} servers.")
		global sparPings
		sparPings[guild.id] = {r: 0 for r in brawl.regions}
	else:
		logging.warning(f"Not given admin perms in {guild.name}.")
		for channel in guild.text_channels:
			try:
				await channel.send(embed=misc.noPerms)
			except nextcord.DiscordException as e:
				logging.exception(e)
			else:
				logging.info(f"Sent no perms msg in {channel.name}.")
				break
		await guild.leave()
		logging.info(f"Left {guild.name}.")


# Event logging


@bot.event
async def on_message_delete(msg: nextcord.Message) -> Optional[nextcord.Embed]:
	if msg.guild and (
		msg.channel.name != "bb-log" or msg.content  # type: ignore
	):
		if channel := misc.getLogChannel(msg.guild):
			emb = logs.logDeleteMsg(msg)
			await channel.send(embed=emb)
			return emb
	return None


@bot.event
async def on_bulk_message_delete(
	msgList: List[nextcord.Message]
) -> Optional[nextcord.Embed]:
	assert msgList[0].guild is not None
	if channel := misc.getLogChannel(msgList[0].guild):
		emb = logs.logPurge(msgList[0], msgList)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_message_edit(
	before: nextcord.Message, after: nextcord.Message
) -> Union[int, nextcord.Embed, None]:
	if after.guild and (before.content != after.content):
		assert isinstance(
			after.channel, (nextcord.TextChannel, nextcord.Thread)
		)
		if misc.scamCheck(after.content):
			logging.info("Possible nitro scam detected in " + str(after.guild))
			if not (role := get(after.guild.roles, name="Muted")):
				role = await misc.createMutedRole(after.guild)
			await after.author.add_roles(role)  # type: ignore
			for channel in after.guild.text_channels:
				if channel.name in ("infractions", "bb-log"):
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
	msg: nextcord.Message, reactions: List[nextcord.Reaction]
) -> Optional[nextcord.Embed]:
	assert msg.guild is not None
	if channel := misc.getLogChannel(msg.guild):
		emb = logs.logClearReacts(msg, reactions)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_guild_channel_delete(
	ch: nextcord.abc.GuildChannel
) -> Optional[nextcord.Embed]:
	if channel := misc.getLogChannel(ch.guild):
		emb = logs.logDeleteChannel(ch)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_guild_channel_create(
	ch: nextcord.abc.GuildChannel
) -> Optional[nextcord.Embed]:
	if channel := misc.getLogChannel(ch.guild):
		emb = logs.logCreateChannel(ch)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_member_join(member: nextcord.Member) -> Optional[nextcord.Embed]:
	if channel := misc.getLogChannel(member.guild):
		emb = logs.logMemberJoin(member)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_member_remove(
	member: nextcord.Member
) -> Optional[nextcord.Embed]:
	if channel := misc.getLogChannel(member.guild):
		emb = logs.logMemberRemove(member)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_member_update(
	before: nextcord.Member, after: nextcord.Member
) -> Optional[nextcord.Embed]:
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
) -> Optional[nextcord.Embed]:
	if channel := misc.getLogChannel(guild):
		emb = logs.logBan(member)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_member_unban(
	guild: nextcord.Guild, member: nextcord.Member
) -> Optional[nextcord.Embed]:
	if channel := misc.getLogChannel(guild):
		emb = logs.logUnban(member)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_thread_join(thread: nextcord.Thread) -> Optional[nextcord.Embed]:
	if thread.me:
		return None
	await thread.join()
	if channel := misc.getLogChannel(thread.guild):
		emb = logs.logCreateThread(thread)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_thread_delete(
	thread: nextcord.Thread
) -> Optional[nextcord.Embed]:
	if channel := misc.getLogChannel(thread.guild):
		emb = logs.logDeleteThread(thread)
		await channel.send(embed=emb)
		return emb
	return None


@bot.event
async def on_thread_update(
	before: nextcord.Thread, after: nextcord.Thread
) -> Optional[nextcord.Embed]:
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


@bot.command(name="flip")  # type: ignore
async def cmdFlip(ctx: commands.Context, bet: str = "10", *args) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if bucks.activeGame(games, ctx.author):
		report = bucks.finMsg.format(ctx.author.mention)
	else:
		report = bucks.flip(ctx.author, bet.lower())
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Coin Flip", report))
	return 1


@bot.command(name="blackjack", aliases=("bj",))  # type: ignore
async def cmdBlackjack(ctx: commands.Context, bet="10", *args) -> int:
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


@bot.command(name="deal", aliases=("hit",))  # type: ignore
async def cmdDeal(ctx: commands.Context, *args) -> int:
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
				bucks.writeMoney(ctx.author, game.bet, True, True)
				games.remove(game)
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Blackjack", report))
	return 1


@bot.command(name="stay", aliases=("stand",))  # type: ignore
async def cmdStay(ctx: commands.Context) -> int:
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
					ctx.author, game.bet, True, True
				)
				if written == -1:
					assert isinstance(bonus, str)
					report = bonus
			games.remove(game)
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Blackjack", report))
	return 1


@no_type_check
@bot.command(name="av", aliases=("avatar",))
async def cmdAv(ctx: commands.Context, *target) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	elif target:
		target = " ".join(target)
	else:
		target = ctx.author
	await ctx.send(embed=misc.av(target, ctx.message))
	return 1


@no_type_check
@bot.command(name="info")
async def cmdInfo(ctx: commands.Context, *target) -> int:
	if not ctx.guild:
		return 0
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	elif target:
		target = " ".join(target)
	else:
		target = ctx.author
	await ctx.send(embed=misc.info(target, ctx.message))
	return 1


@no_type_check
@bot.command(name="balance", aliases=("bal",))
async def cmdBalance(ctx: commands.Context, *target) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	elif target:
		target = " ".join(target)
	else:
		target = ctx.author
	await ctx.send(embed=bucks.balance(target, ctx.message))
	return 1


@no_type_check
@bot.command(name="leaderboard", aliases=("leaderboards", "lb"))
async def cmdLeaderboard(
	ctx: commands.Context, *target
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	elif target:
		target = " ".join(target)
	else:
		target = ctx.author
	await ctx.send(embed=bucks.leaderboard(target, ctx.message))
	return 1


@bot.command(name="dice")  # type: ignore
async def cmdDice(ctx: commands.Context) -> Union[int, nextcord.Embed]:
	if misc.ctxCreatedThread(ctx):
		return -1
	emb = misc.bbEmbed("Beardless Bot Dice", misc.diceMsg)
	await ctx.send(embed=emb)
	return emb


@bot.command(name="reset")  # type: ignore
async def cmdReset(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=bucks.reset(ctx.author))
	return 1


@bot.command(name="register")  # type: ignore
async def cmdRegister(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=bucks.register(ctx.author))
	return 1


@bot.command(name="bucks")  # type: ignore
async def cmdBucks(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=misc.bbEmbed("BeardlessBucks", bucks.buckMsg))
	return 1


@bot.command(name="hello", aliases=("hi",))  # type: ignore
async def cmdHello(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(choice(misc.greetings))
	return 1


@bot.command(name="source")  # type: ignore
async def cmdSource(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	source = (
		"Most facts taken from [this website]"
		"(https://www.thefactsite.com/1000-interesting-facts/)."
	)
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Fun Facts", source))
	return 1


@bot.command(name="add", aliases=("join", "invite"))  # type: ignore
async def cmdAdd(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=misc.inviteMsg)
	return 1


@bot.command(name="rohan")  # type: ignore
async def cmdRohan(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(file=nextcord.File("resources/images/cute.png"))
	return 1


@bot.command(name="random")  # type: ignore
async def cmdRandomBrawl(
	ctx: commands.Context, ranType: str = "None", *args
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=brawl.randomBrawl(ranType.lower(), brawlKey))
	return 1


@bot.command(name="fact")  # type: ignore
async def cmdFact(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(
		embed=misc.bbEmbed(
			f"Beardless Bot Fun Fact #{randint(1, 111111111)}", misc.fact()
		)
	)
	return 1


@bot.command(name="animals", aliases=("animal", "pets"))  # type: ignore
async def cmdAnimals(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=misc.animals)
	return 1


@bot.command(name="define")  # type: ignore
async def cmdDefine(ctx: commands.Context, *words) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	try:
		await ctx.send(embed=misc.define(" ".join(words)))
	except Exception as e:
		await ctx.send(
			"The API I use to get definitions is experiencing server outages"
			" and performance issues. Please be patient."
		)
		misc.logException(e, ctx)
		return 0
	return 1


@bot.command(name="ping")  # type: ignore
async def cmdPing(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	assert bot.user is not None
	emb = misc.bbEmbed(
		"Pinged", f"Beardless Bot's latency is {int(1000 * bot.latency)} ms."
	).set_thumbnail(url=misc.fetchAvatar(bot.user))
	await ctx.send(embed=emb)
	return 1


@bot.command(name="roll")  # type: ignore
async def cmdRoll(ctx: commands.Context, dice: str = "None", *args) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=misc.rollReport(dice, ctx.author))
	return 1


@bot.command(name="dog", aliases=misc.animalList + ("moose",))  # type: ignore
async def cmdAnimal(
	ctx: commands.Context, breed: Optional[str] = None, *args
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	assert ctx.invoked_with is not None
	species = ctx.invoked_with.lower()
	if breed:
		breed = breed.lower()
	if "moose" in (species, breed):
		try:
			moose = misc.animal("moose", "moose")
		except Exception as e:
			misc.logException(e, ctx)
			emb = misc.bbEmbed(
				"Something's gone wrong with the Moose API!",
				"Please inform my creator and he'll see what's going on."
			)
		else:
			emb = misc.bbEmbed("Random Moose").set_image(url=moose)
		await ctx.send(embed=emb)
		return 0
	if species == "dog":
		try:
			dogUrl = misc.animal("dog", breed)
		except Exception as e:
			logging.exception(f"{species} {breed} {e}")
			emb = misc.bbEmbed(
				"Something's gone wrong with the Dog API!",
				"Please inform my creator and he'll see what's going on."
			)
		else:
			if any(dogUrl.startswith(s) for s in ("Breed", "Dog")):
				await ctx.send(dogUrl)
				return 1
			dogBreed = "Hound" if "hound" in dogUrl else dogUrl.split("/")[-2]
			emb = misc.bbEmbed(
				"Random " + dogBreed.title()
			).set_image(url=dogUrl)
		await ctx.send(embed=emb)
		return 1
	titlemod = " Animal" if species == "zoo" else ""
	emb = misc.bbEmbed("Random " + species.title() + titlemod)
	try:
		emb.set_image(url=misc.animal(species))
	except Exception as e:
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


@no_type_check
@bot.command(name="mute")
async def cmdMute(
	ctx: commands.Context,
	target: Optional[str] = None,
	duration: Optional[str] = None,
	*args
) -> int:
	if not ctx.guild:
		return 0
	if misc.ctxCreatedThread(ctx):
		return -1
	if not ctx.author.guild_permissions.manage_messages:
		await ctx.send(misc.naughty.format(ctx.author.mention))
		return 0
	if not target:
		await ctx.send(f"Please specify a target, {ctx.author.mention}.")
		return 0
	# TODO: switch to converter in arg
	converter = commands.MemberConverter()
	try:
		target = await converter.convert(ctx, target)
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
	if target.id == bot.user.id:  # If user tries to mute BB:
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
			args = (duration,) + args
			duration = None
		else:
			unit = duration[lastNumeric:]
			unitIsValid = False
			for mPair in times:
				if (
					unit == mPair[0][0]        # first character
					or unit == mPair[0]        # whole word
					or unit == mPair[0] + "s"  # plural
				):
					unitIsValid = True
					duration = duration[:lastNumeric]  # the numeric part
					mTime = float(duration) * mPair[1]
					mString = " " + mPair[0] + ("" if duration == "1" else "s")
					break
			if not unitIsValid:
				# treat duration as mute reason
				args = (duration,) + args
				duration = None

	try:
		await target.add_roles(role)
	except nextcord.DiscordException as e:
		misc.logException(e, ctx)
		await ctx.send(misc.hierarchyMsg)
		return 0
	report = "Muted " + target.mention
	report += (" for " + duration + mString + ".") if mTime else "."
	emb = misc.bbEmbed("Beardless Bot Mute", report).set_author(
		name=ctx.author, icon_url=misc.fetchAvatar(ctx.author)
	)
	if args:
		emb.add_field(
			name="Mute Reason:", value=" ".join(args), inline=False
		)
	await ctx.send(embed=emb)
	if channel := misc.getLogChannel(ctx.guild):
		await channel.send(
			embed=logs.logMute(
				target,
				ctx.message,
				duration,
				mString,
				mTime
			)
		)
	if mTime:
		# Autounmute
		logging.info(f"Muted {target} for {mTime} in {ctx.guild.name}")
		await asyncio.sleep(mTime)
		await target.remove_roles(role)
		logging.info("Autounmuted " + target.name)
		if channel := misc.getLogChannel(ctx.guild):
			await channel.send(
				embed=logs.logUnmute(target, ctx.author)
			)
	return 1


@no_type_check
@bot.command(name="unmute")
async def cmdUnmute(
	ctx: commands.Context, target: Optional[str] = None, *args
) -> int:
	if not ctx.guild:
		return 0
	if misc.ctxCreatedThread(ctx):
		return -1
	report = misc.naughty.format(ctx.author.mention)
	if ctx.author.guild_permissions.manage_messages:
		# TODO: add a check for Muted role existing
		if target:
			converter = commands.MemberConverter()
			try:
				target = await converter.convert(ctx, target)
				await target.remove_roles(get(ctx.guild.roles, name="Muted"))
			except commands.MemberNotFound as e:
				misc.logException(e, ctx)
				report = "Invalid target! Target must be a mention or user ID."
				return 0
			except nextcord.DiscordException as e:
				misc.logException(e, ctx)
				report = misc.hierarchyMsg
			else:
				report = f"Unmuted {target.mention}."
				if channel := misc.getLogChannel(ctx.guild):
					await channel.send(
						embed=logs.logUnmute(target, ctx.author)
					)
		else:
			report = f"Invalid target, {ctx.author.mention}."
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Unmute", report))
	return 1


@bot.command(name="purge")  # type: ignore
async def cmdPurge(
	ctx: commands.Context, num: Optional[str] = None, *args
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.guild:
		if ctx.author.guild_permissions.manage_messages:  # type: ignore
			try:
				if (mNum := int(num)) < 0:  # type: ignore
					raise ValueError
			except (TypeError, ValueError):
				emb = misc.bbEmbed(
					"Beardless Bot Purge", "Invalid message number!"
				)
				await ctx.send(embed=emb)
				return 0
			await ctx.channel.purge(  # type: ignore
				limit=mNum + 1, check=lambda msg: not msg.pinned
			)
			return 1
		desc = misc.naughty.format(ctx.author.mention)
		await ctx.send(embed=misc.bbEmbed("Beardless Bot Purge", desc))
	return 0


@bot.command(name="buy")  # type: ignore
async def cmdBuy(ctx: commands.Context, color: str = "none", *args) -> int:
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
		elif role in ctx.author.roles:  # type: ignore
			report = "You already have this special color, {}."
		else:
			if not role.color.value:
				await role.edit(colour=nextcord.Colour(colors[color]))
			report = (
				"Not enough BeardlessBucks. You need"
				" 50000 to buy a special color, {}."
			)
			result, bonus = bucks.writeMoney(ctx.author, -50000, True, True)
			if result == 1:
				report = (
					f"Color {role.mention}"
					" purchased successfully, {}!"
				)
				await ctx.author.add_roles(role)  # type: ignore
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


@bot.command(name="pins", aliases=("sparpins", "howtospar"))  # type: ignore
async def cmdPins(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.guild:
		if ctx.channel.name == "looking-for-spar":  # type: ignore
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


@bot.command(name="spar")  # type: ignore
async def cmdSpar(
	ctx: commands.Context, region: Optional[str] = None, *args
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not ctx.guild:
		return 0
	author = ctx.author.mention
	if ctx.channel.name != "looking-for-spar":  # type: ignore
		await ctx.send(f"Please only use !spar in looking-for-spar, {author}.")
		return 0
	if not region:
		await ctx.send(embed=misc.sparPins)
		return 0
	report = brawl.badRegion.format(author)
	tooRecent = role = None
	global sparPings
	if (region := region.lower()) in ("usw", "use"):
		region = region[:2] + "-" + region[2]
	for guild, pings in sparPings.items():
		if guild == ctx.guild.id:
			for key, value in pings.items():
				if key == region:
					if not (role := get(ctx.guild.roles, name=key.upper())):
						role = await ctx.guild.create_role(
							name=key.upper(), mentionable=False
						)
					if time() - value > 7200:
						pings[key] = int(time())
						report = f"{role.mention} come spar {author}"
					else:
						tooRecent = value
					break
			break
	if role and tooRecent:
		hours, seconds = divmod(7200 - (int(time()) - tooRecent), 3600)
		minutes, seconds = divmod(seconds, 60)
		report = brawl.pingMsg(author, hours, minutes, seconds)
	await ctx.send(report)
	if args and role and not tooRecent:
		await ctx.send(
			f"Additional info: \"{' '.join(args)}\"".replace("@", "")
		)
	return 1


# Commands requiring a Brawlhalla API key:


@bot.command(name="brawl")  # type: ignore
async def cmdBrawl(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if brawlKey:
		await ctx.send(embed=brawl.brawlCommands())
		return 1
	return 0


@bot.command(name="brawlclaim")  # type: ignore
async def cmdBrawlclaim(
	ctx: commands.Context, profUrl: str = "None", *args
) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not brawlKey:
		return 0
	if profUrl.isnumeric():
		brawlId = int(profUrl)
	else:
		brawlId = brawl.getBrawlId(brawlKey, profUrl)  # type: ignore
	if brawlId is not None:
		try:
			brawl.claimProfile(ctx.author.id, brawlId)
		except Exception as e:
			misc.logException(e, ctx)
			report = brawl.reqLimit
		else:
			report = "Profile claimed."
	else:
		report = "Invalid profile URL/Brawlhalla ID! " if profUrl else ""
		report += brawl.badClaim
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Rank", report)
	)
	return 1


@bot.command(name="brawlrank")  # type: ignore
async def cmdBrawlrank(ctx: commands.Context, *target) -> Optional[int]:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not (brawlKey and ctx.guild):
		return 0
	# TODO: write valid target method; no need for this copy paste
	# have it return target, report
	target = " ".join(target) if target else ctx.author  # type: ignore
	if not isinstance(target, (nextcord.User, nextcord.Member)):
		report = "Invalid target!"
		target = misc.memSearch(ctx.message, target)  # type: ignore
	if target:
		try:
			await ctx.send(embed=brawl.getRank(target, brawlKey))  # type: ignore
		except Exception as e:
			misc.logException(e, ctx)
			report = brawl.reqLimit
		else:
			return None
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Rank", report)
	)
	return 1


@bot.command(name="brawlstats")  # type: ignore
async def cmdBrawlstats(ctx: commands.Context, *target) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not (brawlKey and ctx.guild):
		return 0
	target = " ".join(target) if target else ctx.author  # type: ignore
	if not isinstance(target, (nextcord.User, nextcord.Member)):
		report = "Invalid target!"
		target = misc.memSearch(ctx.message, target)  # type: ignore
	if target:
		try:
			await ctx.send(embed=brawl.getStats(target, brawlKey))  # type: ignore
		except Exception as e:
			misc.logException(e, ctx)
			report = brawl.reqLimit
		else:
			return 1
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Stats", report)
	)
	return 0


@bot.command(name="brawlclan")  # type: ignore
async def cmdBrawlclan(ctx: commands.Context, *target) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if not (brawlKey and ctx.guild):
		return 0
	target = " ".join(target) if target else ctx.author  # type: ignore
	if not isinstance(target, (nextcord.User, nextcord.Member)):
		report = "Invalid target!"
		target = misc.memSearch(ctx.message, target)  # type: ignore
	if target:
		try:
			await ctx.send(embed=brawl.getClan(target, brawlKey))  # type: ignore
		except Exception as e:
			misc.logException(e, ctx)
			report = brawl.reqLimit
		else:
			return 1
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Clan", report)
	)
	return 0


@bot.command(name="brawllegend")  # type: ignore
async def cmdBrawllegend(
	ctx: commands.Context, legend: Optional[str] = None, *args
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
			emb = brawl.legendInfo(brawlKey, legend.lower())
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


@bot.command(name="tweet", aliases=("eggtweet",))  # type: ignore
async def cmdTweet(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.guild and ctx.guild.id == 442403231864324119:
		emb = misc.bbEmbed(
			"eggsoup(@eggsouptv)", misc.formattedTweet(misc.tweet()), 0x1DA1F2
		).set_thumbnail(url=misc.tweetThumb)
		await ctx.send(embed=emb)
		return 1
	return 0


@bot.command(name="reddit")  # type: ignore
async def cmdReddit(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.guild and ctx.guild.id == 442403231864324119:
		await ctx.send(embed=misc.redditEmb)
		return 1
	return 0


@bot.command(name="guide")  # type: ignore
async def cmdGuide(ctx: commands.Context) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	if ctx.guild and ctx.guild.id == 442403231864324119:
		await ctx.send(
			embed=misc.bbEmbed(
				"The Eggsoup Improvement Guide",
				"https://www.youtube.com/watch?v=nH0TOoJIU80"
			)
		)
		return 1
	return 0


@bot.command(name="search", aliases=("google", "lmgtfy"))  # type: ignore
async def cmdSearch(ctx: commands.Context, *words) -> int:
	if misc.ctxCreatedThread(ctx):
		return -1
	await ctx.send(embed=misc.search(" ".join(words)))
	return 1


@bot.listen()
async def on_command_error(
	ctx: commands.Context, e: commands.errors.CommandError
) -> int:
	if isinstance(e, commands.CommandNotFound):
		return -1
	if isinstance(
		e, (commands.UnexpectedQuoteError, commands.ExpectedClosingQuoteError)
	):
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
		logging.info("Possible nitro scam detected in " + str(message.guild))
		author = message.author
		role = get(message.guild.roles, name="Muted")
		if not role:
			role = await misc.createMutedRole(message.guild)
		await author.add_roles(role)  # type: ignore
		for channel in message.guild.text_channels:
			if channel.name in ("infractions", "bb-log"):
				await channel.send(
					misc.scamReport.format(
						author.mention,
						message.channel.mention,  # type: ignore
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
	except nextcord.DiscordException as e:
		logging.exception(e)
