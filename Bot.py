""" Beardless Bot """
__version__ = "Full Release 1.7.5"

import asyncio
from random import choice, randint
from time import time
from typing import List

import discord
from discord.ext import commands
from discord.utils import get
from dotenv import dotenv_values

import brawl
import bucks
import logs
import misc


bot = commands.Bot(
	command_prefix="!",
	case_insensitive=True,
	help_command=None,
	intents=discord.Intents.all(),
	owner_id=196354892208537600
	# Replace owner_id with your Discord id
)


async def createMutedRole(guild: discord.Guild) -> discord.Role:
	role = await guild.create_role(
		name="Muted",
		colour=discord.Colour(0x818386),
		mentionable=False,
		permissions=discord.Permissions(
			send_messages=False, read_messages=True
		)
	)
	for channel in guild.channels:
		await channel.set_permissions(role, send_messages=False)
	return role


@bot.event
async def on_ready():
	print("Beardless Bot online!")

	status = discord.Game(name="try !blackjack and !flip")
	try:
		await bot.change_presence(activity=status)
		print("Status updated!")
		with open("resources/images/prof.png", "rb") as f:
			await bot.user.edit(avatar=f.read())
		print("Avatar updated!")
	except discord.HTTPException:
		print("Failed to update avatar or status!")
	except FileNotFoundError:
		print("Avatar file not found! Check your directory structure.")

	# Initialize ping waiting time to 0 for each server:
	global sparPings
	mems = 0
	for guild in bot.guilds:
		sparPings[guild.id] = brawl.defaultPings
		mems += guild.member_count
		await guild.chunk()

	print(
		"Beardless Bot serves",
		mems,
		"members across",
		len(bot.guilds),
		"servers."
	)


@bot.event
async def on_guild_join(guild: discord.Guild):
	print(f"Just joined {guild.name}!")

	if guild.me.guild_permissions.administrator:
		role = get(guild.roles, name="Beardless Bot")
		for channel in guild.channels:
			try:
				await channel.send(embed=misc.onJoin(guild, role))
			except Exception as e:
				print(e)
			else:
				break
		print("Beardless Bot is now in", len(bot.guilds), "servers.")
		global sparPings
		sparPings[guild.id] = brawl.defaultPings
	else:
		print(f"Not given admin perms in {guild.name}.")
		for channel in guild.channels:
			try:
				await channel.send(embed=misc.noPerms)
			except Exception as e:
				print(e)
			else:
				print(f"Sent no perms msg in {channel.name}.")
				break
		await guild.leave()
		print(f"Left {guild.name}.")


# Event logging


@bot.event
async def on_message_delete(msg: discord.Message):
	if msg.guild and (msg.channel.name != "bb-log" or msg.content):
		# Prevents embeds from causing a loop
		for channel in msg.guild.channels:
			if channel.name == "bb-log":
				await channel.send(embed=logs.logDeleteMsg(msg))
				return


@bot.event
async def on_bulk_message_delete(msgList: List[discord.Message]):
	for channel in msgList[0].guild.channels:
		if channel.name == "bb-log":
			try:
				await channel.send(
					embed=logs.logPurge(msgList[0], msgList)
				)
			except Exception as e:
				print(e)
			return


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
	if before.guild and (before.content != after.content):
		if after.guild.name == "egg" and misc.scamCheck(after.content):
			await after.author.add_roles(
				get(after.guild.roles, name="Muted")
			)
			for channel in after.guild.channels:
				if channel.name == "infractions":
					await channel.send(
						"Deleted possible scam nitro link sent by"
						f" {after.author.mention} in {after.channel.mention}."
						f"\nMessage content:\n{after.content}"
					)
					break
			await after.channel.send(
				"Deleted possible nitro scam link. Alerting mods."
			)
			await after.delete()
		for channel in before.guild.channels:
			if channel.name == "bb-log":
				try:
					await channel.send(embed=logs.logEditMsg(before, after))
				except Exception as e:
					print(e)
				return


@bot.event
async def on_reaction_clear(
	msg: discord.Message, reactions: List[discord.Reaction]
):
	if not msg.guild:
		return
	for channel in msg.guild.channels:
		if channel.name == "bb-log":
			try:
				await channel.send(embed=logs.logClearReacts(msg, reactions))
			except Exception as e:
				print(e)
			return


@bot.event
async def on_guild_channel_delete(ch: discord.abc.GuildChannel):
	for channel in ch.guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed=logs.logDeleteChannel(ch))
			return


@bot.event
async def on_guild_channel_create(ch: discord.abc.GuildChannel):
	for channel in ch.guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed=logs.logCreateChannel(ch))
			return


@bot.event
async def on_member_join(member: discord.Member):
	for channel in member.guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed=logs.logMemberJoin(member))
			return


@bot.event
async def on_member_remove(member: discord.Member):
	for channel in member.guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed=logs.logMemberRemove(member))
			return


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
	for channel in after.guild.channels:
		if channel.name == "bb-log":
			# This event covers nickname changes and role changes
			if before.nick != after.nick:
				await channel.send(
					embed=logs.logMemberNickChange(before, after)
				)
			# as such, need separate log msgs for each
			elif before.roles != after.roles:
				await channel.send(
					embed=logs.logMemberRolesChange(before, after)
				)
			return


@bot.event
async def on_member_ban(guild: discord.Guild, member: discord.Member):
	for channel in guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed=logs.logBan(member))
			return


@bot.event
async def on_member_unban(guild: discord.Guild, member: discord.Member):
	for channel in guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed=logs.logUnban(member))
			return


# Commands:


@bot.command(name="flip")
async def cmdFlip(ctx, bet="10", *args):
	if any(ctx.author == game.user for game in games):
		report = bucks.finMsg.format(ctx.author.mention)
	else:
		report = bucks.flip(ctx.author, bet.lower())
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Coin Flip", report))


@bot.command(name="blackjack", aliases=("bj",))
async def cmdBlackjack(ctx, bet="10", *args):
	if any(ctx.author == game.user for game in games):
		report = bucks.finMsg.format(ctx.author.mention)
	else:
		report, game = bucks.blackjack(ctx.author, bet)
		if game:
			games.append(game)
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Blackjack", report))


@bot.command(name="deal", aliases=("hit",))
async def cmdDeal(ctx, *args):
	if "," in ctx.author.name:
		report = bucks.commaWarn.format(ctx.author.mention)
	else:
		report = bucks.noGameMsg.format(ctx.author.mention)
		for game in games:
			if game.user == ctx.author:
				report = game.deal()
				if game.checkBust() or game.perfect():
					game.checkBust()
					bucks.writeMoney(ctx.author, game.bet, True, True)
					games.remove(game)
				break
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Blackjack", report))


@bot.command(name="stay", aliases=("stand",))
async def cmdStay(ctx, *args):
	if "," in ctx.author.name:
		report = bucks.commaWarn.format(ctx.author.mention)
	else:
		report = bucks.noGameMsg.format(ctx.author.mention)
		for game in games:
			if game.user == ctx.author:
				result = game.stay()
				report = game.message
				if result and game.bet:
					written, bonus = bucks.writeMoney(
						ctx.author, game.bet, True, True
					)
					if written == -1:
						report = bonus
				games.remove(game)
				break
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Blackjack", report))


@bot.command(name="hint", aliases=("hints",))
async def cmdHints(ctx, *args):
	if secretWord:
		await ctx.send(embed=misc.hints())
	else:
		await ctx.send("Secret word has not been defined.")


@bot.command(name="av", aliases=("avatar",))
async def cmdAv(ctx, *target):
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	elif target:
		target = " ".join(target)
	else:
		target = ctx.author
	await ctx.send(embed=misc.av(target, ctx.message))


@bot.command(name="info")
async def cmdInfo(ctx, *target):
	if not ctx.guild:
		return
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	elif target:
		target = " ".join(target)
	else:
		target = ctx.author
	await ctx.send(embed=misc.info(target, ctx.message))


@bot.command(name="balance", aliases=("bal",))
async def cmdBalance(ctx, *target):
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	elif target:
		target = " ".join(target)
	else:
		target = ctx.author
	await ctx.send(embed=bucks.balance(target, ctx.message))


@bot.command(name="leaderboard", aliases=("leaderboards", "lb"))
async def cmdLeaderboard(ctx, *target):
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	elif target:
		target = " ".join(target)
	else:
		target = ctx.author
	await ctx.send(embed=bucks.leaderboard(target, ctx.message))


@bot.command(name="dice")
async def cmdDice(ctx, *args):
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Dice", misc.diceMsg))


@bot.command(name="reset")
async def cmdReset(ctx, *args):
	await ctx.send(embed=bucks.reset(ctx.author))


@bot.command(name="register")
async def cmdRegister(ctx, *args):
	await ctx.send(embed=bucks.register(ctx.author))


@bot.command(name="bucks")
async def cmdBucks(ctx, *args):
	await ctx.send(embed=misc.bbEmbed("BeardlessBucks", bucks.buckMsg))


@bot.command(name="hello", aliases=("hi",))
async def cmdHello(ctx, *args):
	await ctx.send(choice(misc.greetings))


@bot.command(name="source")
async def cmdSource(ctx, *args):
	source = (
		"Most facts taken from [this website]."
		"(https://www.thefactsite.com/1000-interesting-facts/)"
	)
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Fun Facts", source))


@bot.command(name="add", aliases=("join",))
async def cmdAdd(ctx, *args):
	await ctx.send(embed=misc.joinMsg)


@bot.command(name="rohan")
async def cmdRohan(ctx, *args):
	await ctx.send(file=discord.File("resources/images/cute.png"))


@bot.command(name="random")
async def cmdRandomBrawl(ctx, ranType="None", *args):
	await ctx.send(embed=brawl.randomBrawl(ranType.lower(), brawlKey))


@bot.command(name="fact")
async def cmdFact(ctx, *args):
	await ctx.send(
		embed=misc.bbEmbed(
			f"Beardless Bot Fun Fact #{randint(1, 111111111)}", misc.fact()
		)
	)


@bot.command(name="animals", aliases=("animal", "pets"))
async def cmdAnimals(ctx, *args):
	await ctx.send(embed=misc.animals)


@bot.command(name="define")
async def cmdDefine(ctx, *words):
	await ctx.send(embed=misc.define(" ".join(words)))


@bot.command(name="ping")
async def cmdPing(ctx, *args):
	emb = misc.bbEmbed(
		"Pinged", f"Beardless Bot's latency is {int(1000 * bot.latency)} ms."
	).set_thumbnail(url=bot.user.avatar_url)
	await ctx.send(embed=emb)


@bot.command(name="roll")
async def cmdRoll(ctx, dice="None", *args):
	await ctx.send(embed=misc.rollReport(dice, ctx.author))


@bot.command(name="dog", aliases=misc.animalList + ("moose",))
async def cmdAnimal(ctx, breed=None, *args):
	species = ctx.invoked_with.lower()
	if breed:
		breed = breed.lower()
	if "moose" in (species, breed):
		try:
			moose = misc.animal("moose", "moose")
		except Exception as e:
			print(species, breed, e)
			emb = misc.bbEmbed(
				"Something's gone wrong with the Moose API!",
				"Please inform my creator and he'll see what's going on."
			)
		else:
			print(moose)
			emb = misc.bbEmbed("Random Moose").set_image(url=moose)
		await ctx.send(embed=emb)
		return
	if species == "dog":
		try:
			dogUrl = misc.animal("dog", breed)
		except Exception as e:
			print(species, breed, e)
			emb = misc.bbEmbed(
				"Something's gone wrong with the Dog API!",
				"Please inform my creator and he'll see what's going on."
			)
		else:
			if any(dogUrl.startswith(s) for s in ("Breed", "Dog")):
				await ctx.send(dogUrl)
				return
			dogBreed = "Hound" if "hound" in dogUrl else dogUrl.split("/")[-2]
			emb = misc.bbEmbed(
				"Random " + dogBreed.title()
			).set_image(url=dogUrl)
		await ctx.send(embed=emb)
		return
	try:
		emb = misc.bbEmbed(
			"Random " + species.title()
		).set_image(url=misc.animal(species))
	except Exception as e:
		print(e)
		emb = misc.bbEmbed(
			"Something's gone wrong!",
			"Please inform my creator and he'll see what's going on."
		)
	await ctx.send(embed=emb)


@bot.command(name="help", aliases=("commands",))
async def cmdHelp(ctx, *args):
	await ctx.send(embed=misc.bbCommands(ctx))


# Server-only commands (not usable in DMs):


@bot.command(name="mute")
async def cmdMute(ctx, target=None, duration=None, *args):
	if not ctx.guild:
		return
	if not ctx.author.guild_permissions.manage_messages:
		await ctx.send(misc.naughty.format(ctx.author.mention))
		return
	if not target:
		await ctx.send(f"Please specify a target, {ctx.author.mention}.")
		return
	# TODO: switch to converter in arg
	try:
		converter = commands.MemberConverter()
		target = await converter.convert(ctx, target)
	except Exception as e:
		print(e)
		await ctx.send(
			embed=misc.bbEmbed(
				"Beardless Bot Mute",
				"Invalid target! Target must be a mention or user ID."
			)
		)
		return
	else:
		if target.id == 654133911558946837:  # If user tries to mute BB:
			await ctx.send("I am too powerful to be muted. Stop trying.")
			return
	role = get(ctx.guild.roles, name="Muted")
	if not role:
		role = await createMutedRole(ctx.guild)
	mTime = mString = None
	if duration:
		duration = duration.lower()
		times = (
			("day", 86400.0),
			("hour", 3600.0),
			("minute", 60.0),
			("second", 1.0)
		)
		for mPair in times:
			if (mPair[0])[0] in duration:
				duration = duration.split((mPair[0])[0], 1)[0]
				mTime = float(duration) * mPair[1]
				mString = " " + mPair[0] + ("" if duration == "1" else "s")
	try:
		await target.add_roles(role)
	except Exception as e:
		print(e)
		await ctx.send(misc.hierarchyMsg)
	else:
		report = "Muted " + target.mention
		report += (" for " + duration + mString + ".") if mTime else "."
		emb = misc.bbEmbed("Beardless Bot Mute", report).set_author(
			name=ctx.author, icon_url=ctx.author.avatar_url
		)
		if args:
			emb.add_field(
				name="Mute Reason:", value=" ".join(args), inline=False
			)
		await ctx.send(embed=emb)
		# Iterate through channels, make Muted unable to send msgs
		for channel in ctx.guild.channels:
			if channel.name == "bb-log":
				await channel.send(
					embed=logs.logMute(
						target,
						ctx.message,
						duration,
						mString,
						mTime
					)
				)
				break
		if mTime:
			# Autounmute
			print("Muted", target, "for", mTime, "in", ctx.guild.name)
			await asyncio.sleep(mTime)
			await target.remove_roles(role)
			print("Autounmuted", target.name)
			for channel in ctx.guild.channels:
				if channel.name == "bb-log":
					await channel.send(
						embed=logs.logUnmute(target, ctx.author)
					)
					return


@bot.command(name="unmute")
async def cmdUnmute(ctx, target=None, *args):
	if not ctx.guild:
		return
	report = misc.naughty.format(ctx.author.mention)
	if ctx.author.guild_permissions.manage_messages:
		if target:
			converter = commands.MemberConverter()
			try:
				target = await converter.convert(ctx, target)
				await target.remove_roles(get(ctx.guild.roles, name="Muted"))
			except Exception as e:
				print(e)
				report = misc.hierarchyMsg
			else:
				report = f"Unmuted {target.mention}."
				for channel in ctx.guild.channels:
					if channel.name == "bb-log":
						await channel.send(
							embed=logs.logUnmute(target, ctx.author)
						)
						break
		else:
			report = f"Invalid target, {ctx.author.mention}."
	await ctx.send(embed=misc.bbEmbed("Beardless Bot Unmute", report))


@bot.command(name="purge")
async def cmdPurge(ctx, num=None, *args):
	if ctx.guild and ctx.author.guild_permissions.manage_messages:
		try:
			mNum = int(num)
		except ValueError:
			emb = misc.bbEmbed(
				"Beardless Bot Purge", "Invalid message number!"
			)
			await ctx.send(embed=emb)
		else:
			await ctx.channel.purge(
				limit=mNum + 1, check=lambda msg: not msg.pinned
			)
	elif ctx.guild:
		desc = misc.naughty.format(ctx.author.mention)
		await ctx.send(embed=misc.bbEmbed("Beardless Bot Purge", desc))


@bot.command(name="buy")
async def cmdBuy(ctx, color="none", *args):
	if not ctx.guild:
		return
	report = "Invalid color. Choose blue, red, orange, or pink, {}."
	color = color.lower()
	colors = {
		"blue": 0x3C9EFD,
		"pink": 0xD300FF,
		"orange": 0xFAAA24,
		"red": 0xF5123D
	}
	if color in colors.keys():
		role = get(ctx.guild.roles, name="special " + color)
		if not role:
			report = "That color role does not exist in this server, {}."
		elif role in ctx.author.roles:
			report = "You already have this special color, {}."
		else:
			if not role.color.value:
				await role.edit(colour=discord.Colour(colors[color]))
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
				await ctx.author.add_roles(role)
			if result == -1:
				report = bonus
			if result == 2:
				report = bucks.newUserMsg
	await ctx.send(
		embed=misc.bbEmbed(
			"Beardless Bot Special Colors",
			report.format(ctx.author.mention)
		)
	)


@bot.command(name="pins")
async def cmdPins(ctx, *args):
	if ctx.guild and ctx.channel.name == "looking-for-spar":
		await ctx.send(embed=misc.sparPins)


@bot.command(name="spar")
async def cmdSpar(ctx, region=None, *args):
	if not ctx.guild:
		return
	author = ctx.author.mention
	if ctx.channel.name != "looking-for-spar":
		await ctx.send(f"Please only use !spar in looking-for-spar, {author}.")
		return
	if not region:
		await ctx.send(embed=misc.sparPins)
		return
	report = brawl.badRegion.format(author)
	tooRecent = role = None
	global sparPings
	region = region.lower()
	if region in ("usw", "use"):
		region = region[:2] + "-" + region[2]
	for guild, pings in sparPings.items():
		if guild == ctx.guild.id:
			for key, value in sparPings[guild].items():
				if key == region:
					role = get(ctx.guild.roles, name=key.upper())
					if not role:
						role = await ctx.guild.create_role(
							name=key.upper(), mentionable=False
						)
					if time() - value > 7200:
						sparPings[guild][key] = int(time())
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
		await ctx.send(f"Additional info: \"{' '.join(args)}\"")


# Commands requiring a Brawlhalla API key:


@bot.command(name="brawl")
async def cmdBrawl(ctx, *args):
	if brawlKey:
		await ctx.send(embed=brawl.brawlCommands())


@bot.command(name="brawlclaim")
async def cmdBrawlclaim(ctx, profUrl="None", *args):
	if not brawlKey:
		return
	if profUrl.isnumeric():
		brawlID = int(profUrl)
	else:
		brawlID = brawl.getBrawlID(brawlKey, profUrl)
	if brawlID:
		try:
			brawl.claimProfile(ctx.author.id, brawlID)
		except Exception as e:
			print(e)
			report = brawl.reqLimit
		else:
			report = "Profile claimed."
	else:
		report = "Invalid profile URL/Brawlhalla ID! " if profUrl else ""
		report += brawl.badClaim
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Rank", report)
	)


@bot.command(name="brawlrank")
async def cmdBrawlrank(ctx, *target):
	if not (brawlKey and ctx.guild):
		return
	target = " ".join(target) if target else ctx.author
	if not isinstance(target, discord.User):
		report = "Invalid target!"
		target = misc.memSearch(ctx.message, target)
	if target:
		try:
			await ctx.send(embed=brawl.getRank(target, brawlKey))
			return
		except Exception as e:
			print(e)
			report = brawl.reqLimit
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Rank", report)
	)


@bot.command(name="brawlstats")
async def cmdBrawlstats(ctx, *target):
	if not (brawlKey and ctx.guild):
		return
	target = " ".join(target) if target else ctx.author
	if not isinstance(target, discord.User):
		report = "Invalid target!"
		target = misc.memSearch(ctx.message, target)
	if target:
		try:
			await ctx.send(embed=brawl.getStats(target, brawlKey))
			return
		except Exception as e:
			print(e)
			report = brawl.reqLimit
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Stats", report)
	)


@bot.command(name="brawlclan")
async def cmdBrawlclan(ctx, *target):
	if not (brawlKey and ctx.guild):
		return
	target = " ".join(target) if target else ctx.author
	if not isinstance(target, discord.User):
		report = "Invalid target!"
		target = misc.memSearch(ctx.message, target)
	if target:
		try:
			await ctx.send(embed=brawl.getClan(target, brawlKey))
			return
		except Exception as e:
			print(e)
			report = brawl.reqLimit
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Clan", report)
	)


@bot.command(name="brawllegend")
async def cmdBrawllegend(ctx, legend=None, *args):
	if not brawlKey:
		return
	report = (
		"Invalid legend! Please do !brawllegend followed by a legend name."
	)
	if legend:
		try:
			legend = brawl.legendInfo(brawlKey, legend)
		except Exception as e:
			print(e)
			report = brawl.reqLimit
		else:
			if legend:
				await ctx.send(embed=legend)
				return
	await ctx.send(
		embed=misc.bbEmbed("Beardless Bot Brawlhalla Legend Info", report)
	)


# Server-specific commands:


@bot.command(name="tweet", aliases=("eggtweet",))
async def cmdTweet(ctx, *args):
	if ctx.guild and ctx.guild.id == 442403231864324119:
		await ctx.send(
			embed=misc.bbEmbed(
				"eggsoup(@eggsouptv)",
				misc.formattedTweet(misc.tweet()),
				0x1DA1F2
			).set_thumbnail(url=misc.tweetThumb)
		)


@bot.command(name="reddit")
async def cmdReddit(ctx, *args):
	if ctx.guild and ctx.guild.id == 442403231864324119:
		await ctx.send(embed=misc.redditEmb)


@bot.command(name="guide")
async def cmdGuide(ctx, *args):
	if ctx.guild and ctx.guild.id == 442403231864324119:
		await ctx.send(
			embed=misc.bbEmbed(
				"The Eggsoup Improvement Guide",
				"https://www.youtube.com/watch?v=nH0TOoJIU80"
			)
		)


@bot.listen()
async def on_command_error(ctx, e):
	if isinstance(e, commands.CommandNotFound):
		return
	print(e)


@bot.listen("on_message")
async def handleMessages(message):
	if message.author.bot or not message.guild:
		return

	text = message.content.lower()

	if misc.scamCheck(text):
		author = message.author
		role = get(message.guild.roles, name="Muted")
		if not role:
			role = await createMutedRole(message.guild)
		await author.add_roles(role)
		for channel in message.guild.channels:
			if channel.name in ("infractions", "bb-log"):
				await channel.send(
					"Deleted possible scam nitro link sent by"
					f" {author.mention} in {message.channel.mention}."
					f"\nMessage content:\n{message.content}"
				)
		await message.channel.send(
			"**Deleted possible nitro scam link. Alerting mods.**"
		)
		await message.delete()
		await author.send(misc.scamDM.format(message.guild))

	elif message.guild.name == "Day Care":
		if "twitter.com/year_progress" in text:
			await message.delete()

	elif secretWord and secretWord in text:
		global secretFound
		if secretFound:
			return
		secretFound = True
		print(
			f"Secret word, {secretWord}, found by",
			f"{message.author.mention} in {message.guild.name}."
		)
		result, bonus = bucks.writeMoney(message.author, 100000, True, True)
		if result == -1:
			report = "Ping Captain No-Beard for your prize"
		elif result == 2:
			bucks.writeMoney(message.author, 100000, True, True)
		else:
			report = "100000 BeardlessBucks have been added to your account"
		await message.channel.send(
			embed=misc.bbEmbed(
				f"Well done! You found the secret word, {secretWord}!",
				f"{report}, {message.author.mention}!"
			)
		)


if __name__ == "__main__":

	env = dotenv_values(".env")

	try:
		brawlKey = env["BRAWLKEY"]
	except KeyError:
		brawlKey = None
		print(
			"No Brawlhalla API key. Brawlhalla-specific",
			"commands will not be active."
		)

	try:
		secretWord = env["SECRETWORD"]
	except KeyError:
		secretWord = None
		print("Secret word has not been defined. Continuing as normal.")

	# This dictionary is for keeping track of pings in the lfs channels.
	sparPings = {}

	# This array stores the active instances of blackjack.
	games = []

	try:
		bot.run(env["DISCORDTOKEN"])
	except KeyError:
		print(
			"Fatal error! DISCORDTOKEN environment variable has not",
			"been defined. See: README.MD's installation section."
		)
	except discord.DiscordException as e:
		print(e)
