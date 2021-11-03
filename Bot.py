# Beardless Bot
# Author: Lev Bernstein
# Version: Full Release 1.5.15

import asyncio
import csv
import json
from datetime import datetime
from random import choice, randint
from sys import exit as sysExit
from time import time

import discord
from discord.ext import commands
from discord.utils import get

from brawl import *
from bucks import *
from logs import *
from misc import *

operator = 196354892208537600 # Replace with your Discord id

bot = commands.Bot(command_prefix = "!", case_insensitive = True, help_command = None, intents = discord.Intents.all(), owner_id = operator)

@bot.event
async def on_ready():
	print("Beardless Bot online!")
	try:
		await bot.change_presence(activity = discord.Game(name = "try !blackjack and !flip"))
		print("Status updated!")
	except discord.HTTPException:
		print("Failed to update status! You might be sending requests too quickly.")
	try:
		with open("resources/images/prof.png", "rb") as f:
			await bot.user.edit(avatar = f.read())
			print("Avatar updated!")
	except discord.HTTPException:
		print("Failed to update avatar! You might be sending requests too quickly.")
	except FileNotFoundError:
		print("Avatar file not found! Check your directory structure.")
	print("Beardless Bot is in", len(bot.guilds), "servers.")
	# Initialize ping waiting time for each channel at 0 for each server bb is in:
	global sparPings
	for guild in bot.guilds:
		sparPings[guild.id] = {"jpn": 0, "brz": 0, "us-w": 0, "us-e": 0, "sea": 0, "aus": 0, "eu": 0}

@bot.event
async def on_guild_join(guild):
	global sparPings # create sparPings entry for this new server
	sparPings[guild.id] = {"jpn": 0, "brz": 0, "us-w": 0, "us-e": 0, "aus": 0, "sea": 0, "eu": 0}
	print(f"Just joined {guild.name}! Beardless Bot is now in {len(bot.guilds)} servers.")
	if not guild.me.guild_permissions.administrator:
		print(f"Not given admin perms in {guild.name}.")
		for channel in guild.channels:
			try:
				await channel.send(embed = noPerms)
				break
			except:
				pass
		await guild.leave()
		print(f"Left {guild.name}. Beardless Bot is now in {len(bot.guilds)} servers.")
	else:
		for channel in guild.channels:
			try:
				await channel.send(embed = onJoin(guild, get(guild.roles, name = "Beardless Bot")))
				break
			except:
				pass
	return

@bot.event
async def on_message_delete(msg):
	if msg.guild and (msg.channel.name != "bb-log" or msg.content):
		# Prevents embeds from causing a loop
		for channel in msg.guild.channels:
			if channel.name == "bb-log":
				await channel.send(embed = logDeleteMsg(msg))
				return

@bot.event
async def on_bulk_message_delete(msgList):
	if msgList[0].guild: # if one message in the list is in a guild, they all are
		for channel in msgList[0].guild.channels:
			if channel.name == "bb-log":
				try:
					await channel.send(embed = logPurge(msgList[0], msgList))
				except Exception as err:
					print(err)
				return

@bot.event
async def on_message_edit(before, after):
	if before.guild and before.content != after.content:
		# The above check prevents embeds from getting logged, as they have no "content" field
		for channel in before.guild.channels:
			if channel.name == "bb-log":
				try:
					await channel.send(embed = logEditMsg(before, after))
				except Exception as err:
					print(err)
				return

@bot.event
async def on_reaction_clear(msg, reactions):
	if msg.guild:
		for channel in msg.guild.channels:
			if channel.name == "bb-log":
				try:
					await channel.send(embed = logClearReacts(msg, reactions))
				except Exception as err:
					print(err)
				return

@bot.event
async def on_guild_channel_delete(ch):
	for channel in ch.guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed = logDeleteChannel(ch))
			return

@bot.event
async def on_guild_channel_create(ch):
	for channel in ch.guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed = logCreateChannel(ch))
			return

@bot.event
async def on_member_join(member):
	for channel in member.guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed = logMemberJoin(member))
			return

@bot.event
async def on_member_remove(member):
	for channel in member.guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed = logMemberRemove(member))
			return

@bot.event
async def on_member_update(before, after):
	for channel in after.guild.channels:
		if channel.name == "bb-log":
			if before.nick != after.nick: # This event covers nickname changes and role changes
				await channel.send(embed = logMemberNickChange(before, after))
			elif before.roles != after.roles: # as such, need separate log msgs for each
				await channel.send(embed = logMemberRolesChange(before, after))
			return

@bot.event
async def on_member_ban(guild, member):
	for channel in guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed = logBan(member))
			return

@bot.event
async def on_member_unban(guild, member):
	for channel in guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed = logUnban(member))
			return

@bot.command(name = "flip")
async def cmdFlip(ctx, bet = "10", *args):
	if any(ctx.author == game.user for game in games):
		report = f"Please finish your game of blackjack first, {ctx.author.mention}."
	else:
		report = flip(ctx.author, bet.lower())
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Coin Flip", report))
	return

@bot.command(name = "blackjack", aliases = ("bj",))
async def cmdBlackjack(ctx, bet = "10", *args):
	if any(ctx.author == game.user for game in games):
		report = f"Please finish your game of blackjack first, {ctx.author.mention}."
	else:
		report, game = blackjack(ctx.author, bet)
		if game:
			games.append(game)
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Blackjack", report))
	return

@bot.command(name = "deal", aliases = ("hit",))
async def cmdDeal(ctx, *args):
	if "," in ctx.author.name:
		report = commaWarn.format(ctx.author.mention)
	else:
		report = f"You do not currently have a game of blackjack going, {ctx.author.mention}. Type !blackjack to start one."
		for i, game in enumerate(games):
			if game.user == ctx.author:
				report = game.deal()
				if game.checkBust() or game.perfect():
					writeMoney(ctx.author, game.bet * (-1 if game.checkBust() else 1), True, True)
					games.pop(i)
				break
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Blackjack", report))
	return

@bot.command(name = "stay", aliases = ("stand",))
async def cmdStay(ctx, *args):
	if "," in ctx.author.name:
		report = commaWarn.format(ctx.author.mention)
	else:
		report = f"You do not currently have a game of blackjack going, {ctx.author.mention}. Type !blackjack to start one."
		for i, game in enumerate(games):
			if game.user == ctx.author:
				result = game.stay()
				report = game.message
				if result and game.bet:
					written, bonus = writeMoney(ctx.author, game.bet, True, True)
					if written == -1:
						report = bonus
				games.pop(i)
				break
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Blackjack", report))
	return

@bot.command(name = "hint", aliases = ("hints",))
async def cmdHints(ctx, *args):
	if secretWord:
		await ctx.channel.send(embed = hints())
	else:
		await ctx.channel.send("Secret word has not been defined.")
	return

@bot.command(name = "av", aliases = ("avatar",))
async def cmdAv(ctx, target = None, *args):
	if not target:
		target = ctx.author
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	await ctx.channel.send(embed = av(target, ctx.message))
	return

@bot.command(name = "balance", aliases = ("bal",))
async def cmdBalance(ctx, target = None, *args):
	if not target:
		target = ctx.author
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	await ctx.channel.send(embed = balance(target, ctx.message))
	return

@bot.command(name = "playlist", aliases = ("music",))
async def cmdPlaylist(ctx, *args):
	await ctx.channel.send(f"Here's my playlist (Discord will only show the first hundred songs):\n{spotify}")
	return

@bot.command(name = "leaderboard", aliases=("leaderboards", "lb"))
async def cmdLeaderboard(ctx, *args): # TODO: also report user's position on the leaderboard?
	await ctx.channel.send(embed = leaderboard())
	return

@bot.command(name = "dice")
async def cmdDice(ctx, *args):
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Dice", diceMsg))
	return

@bot.command(name = "reset")
async def cmdReset(ctx, *args):
	await ctx.channel.send(embed = reset(ctx.author))
	return

@bot.command(name = "register")
async def cmdRegister(ctx, *args):
	await ctx.channel.send(embed = register(ctx.author))
	return

@bot.command(name = "bucks")
async def cmdBucks(ctx, *args):
	await ctx.channel.send(embed = bbEmbed("BeardlessBucks", buckMsg))
	return

@bot.command(name = "hello", aliases = ("hi",))
async def cmdHello(ctx, *args):
	greetings = "How ya doin?", "Yo!", "What's cookin?", "Hello!", "Ahoy!", "Hi!", "What's up?", "Hey!", "How's it goin?", "Greetings!"
	await ctx.channel.send(choice(greetings))
	return

@bot.command(name = "source")
async def cmdSource(ctx, *args):
	report = "Most facts taken from [this website](https://www.thefactsite.com/1000-interesting-facts/)."
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Fun Facts", report))
	return

@bot.command(name = "add", aliases = ("join",))
async def cmdAdd(ctx, *args):
	await ctx.channel.send(embed = joinMsg)
	return

@bot.command(name = "rohan")
async def cmdRohan(ctx, *args):
	await ctx.channel.send(file = discord.File("resources/images/cute.png"))
	return

@bot.command(name = "random")
async def cmdRandomBrawl(ctx, ranType = "None", *args):
	await ctx.channel.send(embed = randomBrawl(ranType.lower()))
	return

@bot.command(name = "fact")
async def cmdFact(ctx, *args):
	await ctx.channel.send(embed = bbEmbed(f"Beardless Bot Fun Fact #{randint(1, 111111111)}", fact()))
	return

@bot.command(name = "animals", aliases = ("animal", "pets"))
async def cmdAnimals(ctx, *args):
	await ctx.channel.send(embed = animals())
	return

@bot.command(name = "define")
async def cmdDefine(ctx, *words):
	await ctx.channel.send(embed = define(" ".join(words)))
	return

@bot.command(name = "ping")
async def cmdPing(ctx, *args):
	startTime = datetime.now()
	message = await ctx.channel.send(embed = bbEmbed("Pinging..."))
	report = f"Beardless Bot's latency is {int((datetime.now() - startTime).total_seconds() * 1000)} ms."
	await message.edit(embed = bbEmbed("Pinged!", report).set_thumbnail(url = bot.user.avatar_url))
	return

@bot.command(name = "roll")
async def cmdRoll(ctx, dice, *args):
	await ctx.channel.send(embed = rollReport(dice, ctx.author))
	return

@bot.command(name = "dog", aliases = animalList + ("moose",))
async def cmdAnimal(ctx, breed = None, *args):
	species = ctx.invoked_with.lower()
	if species == "moose" or (breed and breed.lower() == "moose"):
		await ctx.channel.send(file = discord.File(f"resources/images/moose/moose{randint(1, 62)}.jpg"))
		return
	if species == "dog":
		try:
			if breed:
				dogBreed = breed.lower()
				dogUrl = animal("dog", dogBreed)
				if dogUrl.startswith("Breed not found") or dogUrl.startswith("Dog breeds"):
					await ctx.channel.send(dogUrl)
					return
			else:
				dogUrl = animal("dog")
				dogBreed = "Hound" if "hound" in dogUrl else dogUrl.split("/")[-2]
			await ctx.channel.send(embed = bbEmbed("Random " + dogBreed.title()).set_image(url = dogUrl))
		except:
			await ctx.channel.send("Something's gone wrong with the dog API! Please ping my creator and he'll see what's going on.")
		return
	try:
		await ctx.channel.send(embed = bbEmbed("Random " + species.title()).set_image(url = animal(species)))
	except Exception as err:
		print(err)
		await ctx.channel.send("Something's gone wrong! Please ping my creator and he'll see what's going on.")
	return

@bot.command(name = "help", aliases = ("commands",))
async def cmdHelp(ctx, *args):
	await ctx.channel.send(embed = bbCommands(ctx))
	return

# Server-only commands (the above commands are usable in DMs; those below are not):

@bot.command(name = "mute")
async def cmdMute(ctx, target = None, duration = None, *args):
	if not ctx.guild:
		return
	if not ctx.author.guild_permissions.manage_messages:
		await ctx.channel.send(f"You do not have permission to use this command, {ctx.author.mention}.")
		return
	if not target:
		await ctx.channel.send(f"Please specify a target, {ctx.author.mention}.")
		return
	try:
		converter = commands.MemberConverter() # look into replacing with a converter in def
		target = await converter.convert(ctx, target)
		if target.id == 654133911558946837: # If user tries to mute Beardless Bot:
			await ctx.channel.send("I am too powerful to be muted. Stop trying.")
			return
	except Exception as err:
		print(err)
		await ctx.channel.send(embed = bbEmbed("Beardless Bot Mute", "Invalid target! Target must be a mention or user ID."))
		return
	role = get(ctx.guild.roles, name = "Muted")
	if not role: # Creates a Muted role.
		role = await ctx.guild.create_role(name = "Muted", colour = discord.Color(0x818386), mentionable = False,
		permissions = discord.Permissions(send_messages = False, read_messages = True))
	mTime = 0.0
	mString = None
	if duration:
		duration = duration.lower()
		for mPair in ("day", 86400.0), ("hour", 3600.0), ("minute", 60.0), ("second", 1.0):
			if (mPair[0])[0] in duration:
				duration = duration.split((mPair[0])[0], 1)[0]
				mTime = float(duration) * mPair[1]
				mString = " " + mPair[0] + ("" if duration == "1" else "s")
	try:
		await target.add_roles(role)
		report = "Muted " + target.mention + ((" for " + duration + mString + ".") if mTime else ".")
		emb = bbEmbed("Beardless Bot Mute", report).set_author(name = str(ctx.author), icon_url = ctx.author.avatar_url)
		if args:
			emb.add_field(name = "", value = " ".join(args), inline = False)
		await ctx.channel.send(embed = emb)
		for channel in ctx.guild.channels: # iterates through channels, makes Muted unable to send msgs
			await channel.set_permissions(role, send_messages = False)
			if channel.name == "bb-log":
				await channel.send(embed = logMute(target, ctx.message, duration, mString, mTime))
		if mTime: # Autounmute
			print("Muted", target, "for", mTime, "in", ctx.guild.name)
			await asyncio.sleep(mTime)
			await target.remove_roles(role)
			print("Autounmuted", target.name)
			for channel in ctx.guild.channels:
				if channel.name == "bb-log":
					await channel.send(embed = logUnmute(target, ctx.author))
					return
	except Exception as err:
		print(err)
		await ctx.channel.send(hierarchyMsg)
	return

@bot.command(name = "unmute")
async def cmdUnmute(ctx, target = None, *args):
	if not ctx.guild:
		return
	try:
		report = f"You do not have permission to use this command, {ctx.author.mention}."
		if ctx.author.guild_permissions.manage_messages:
			if not target:
				report = f"Invalid target, {ctx.author.mention}."
			else:
				converter = commands.MemberConverter()
				target = await converter.convert(ctx, target)
				await target.remove_roles(get(ctx.guild.roles, name = "Muted"))
				report = f"Unmuted {target.mention}."
				for channel in ctx.guild.channels:
					if channel.name == "bb-log":
						await channel.send(embed = logUnmute(target, ctx.author))
						break
		await ctx.channel.send(embed = bbEmbed("Beardless Bot Unmute", report))
	except:
		await ctx.channel.send(hierarchyMsg)
	return

@bot.command(name = "purge")
async def cmdPurge(ctx, num = None, *args):
	if not ctx.guild:
		return
	if not ctx.author.guild_permissions.manage_messages:
		await ctx.channel.send(embed = bbEmbed("Beardless Bot Purge", f"You do not have permission to use this command, {ctx.author.mention}."))
	else:
		try:
			mNum = int(num) # look into replacing with a converter
			await ctx.channel.purge(limit = mNum + 1, check = lambda message: not message.pinned)
		except:
			await ctx.channel.send(embed = bbEmbed("Beardless Bot Purge", "Invalid message number!"))
	return

@bot.command(name = "buy")
async def cmdBuy(ctx, color = "None", *args):
	if not ctx.guild:
		return
	report = "Invalid color. Choose blue, red, orange, or pink, {}."
	color = color.lower()
	if color in ("blue", "pink", "orange", "red"):
		role = get(ctx.guild.roles, name = "special " + color)
		if not role:
			report = "That special color role does not exist in this server, {}."
		elif role in ctx.author.roles:
			report = "You already have this special color, {}."
		else:
			report = "Not enough BeardlessBucks. You need 50000 to buy a special color, {}."
			with open("resources/money.csv", "r") as csvfile:
				result, bonus = writeMoney(ctx.author, -50000, True, True)
				if result == 1:
					report = "Color " + role.mention + " purchased successfully, {}!"
					await ctx.author.add_roles(role)
				if result == -1:
					report = bonus
				if result == 2:
					report = newUserMsg
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Special Colors", report.format(ctx.author.mention)))
	return

@bot.command(name = "info")
async def cmdInfo(ctx, target = None, *args):
	if not ctx.guild:
		return
	if not target:
		target = ctx.author
	if ctx.message.mentions:
		target = ctx.message.mentions[0]
	await ctx.channel.send(embed = info(target, ctx.message))
	return

@bot.command(name = "pins")
async def cmdPins(ctx, *args):
	if not ctx.guild:
		return
	if ctx.channel.name == "looking-for-spar":
		await ctx.channel.send(embed = sparPins)
	return

@bot.command(name = "twitch")
async def cmdTwitch(ctx, *args):
	await ctx.channel.send(embed = bbEmbed("Captain No-Beard's Twitch Stream", "https://twitch.tv/capnnobeard")
	.set_thumbnail(url = "https://static-cdn.jtvnw.net/jtv_user_pictures/capnnobeard-profile_image-423aa718d334e220-70x70.jpeg"))
	return

@bot.command(name = "spar")
async def cmdSpar(ctx, region = None, *misc):
	if not ctx.guild:
		return
	if ctx.channel.name != "looking-for-spar":
		report = "Please only use !spar in looking-for-spar, {}."
		for channel in ctx.guild.channels:
			if channel.name == "looking-for-spar":
				report = "Please only use !spar in " + channel.mention + ", {}."
				break
		await ctx.channel.send(report.format(ctx.author.mention))
		return
	if not region:
		await ctx.channel.send(embed = sparPins)
		return
	report = badRegion.format(ctx.author.mention)
	tooRecent = role = None
	global sparPings
	region = region.lower()
	if region in ("usw", "use"):
		region = region[:2] + "-" + region[2]
	for guild, pings in sparPings.items():
		if guild == ctx.guild.id:
			for key, value in sparPings[guild].items():
				if key == region:
					role = get(ctx.guild.roles, name = key.upper())
					if not role:
						role = await ctx.guild.create_role(name = key.upper(), mentionable = False)
					if time() - value > 7200:
						sparPings[guild][key] = int(time())
						report = f"{role.mention} come spar {ctx.author.mention}!"
					else:
						tooRecent = value
					break
			break
	if role and tooRecent:
		hours, seconds = divmod(7200 - (int(time()) - tooRecent), 3600)
		minutes, seconds = divmod(seconds, 60)
		report = pingMsg(ctx.author.mention, hours, minutes, seconds)
	await ctx.channel.send(report)
	if misc and role and not tooRecent:
		await ctx.channel.send("Additional info: \"{}\"".format(" ".join(misc)))
	return

# Commands requiring a Brawlhalla API key:

@bot.command(name = "brawl")
async def cmdBrawl(ctx, *args):
	if brawlKey:
		await ctx.channel.send(embed = brawlCommands())
	return

@bot.command(name = "brawlclaim")
async def cmdBrawlclaim(ctx, profUrl = "None", *args):
	if not brawlKey:
		return
	brawlID = int(profUrl) if profUrl.isnumeric() else getBrawlID(brawlKey, profUrl)
	if not brawlID:
		report = ("Invalid profile URL/Brawlhalla ID! " if profUrl else "") + badClaim
	else:
		try:
			claimProfile(ctx.author.id, brawlID)
			report = "Profile claimed."
		except Exception as err:
			print(err)
			report = reqLimit
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Brawlhalla Rank", report))
	return

@bot.command(name = "brawlrank")
async def cmdBrawlrank(ctx, target = None, *args):
	if not (brawlKey and ctx.guild):
		return
	if not target:
		target = ctx.author
	if not isinstance(target, discord.User):
		report = "Invalid target!"
		target = memSearch(ctx.message, target)
	if target:
		try:
			report = getRank(target, brawlKey)
			if isinstance(report, discord.Embed):
				await ctx.channel.send(embed = report)
				return
		except Exception as err:
			print(err)
			report = reqLimit
		await ctx.channel.send(embed = bbEmbed("Beardless Bot Brawlhalla Rank", report))
		return

@bot.command(name = "brawlstats")
async def cmdBrawlstats(ctx, target = None, *args):
	if not (brawlKey and ctx.guild):
		return
	if not target:
		target = ctx.author
	if not isinstance(target, discord.User):
		report = "Invalid target!"
		target = memSearch(ctx.message, target)
	if target:
		try:
			report = getStats(target, brawlKey)
			if isinstance(report, discord.Embed):
				await ctx.channel.send(embed = report)
				return
		except Exception as err:
			print(err)
			report = reqLimit
		await ctx.channel.send(embed = bbEmbed("Beardless Bot Brawlhalla Stats", report))
		return

@bot.command(name = "brawlclan")
async def cmdBrawlclan(ctx, target = None, *args):
	if not (brawlKey and ctx.guild):
		return
	if not target:
		target = ctx.author
	if not isinstance(target, discord.User):
		report = "Invalid target!"
		target = memSearch(ctx.message, target)
	if target:
		try:
			report = getClan(target, brawlKey)
			if isinstance(report, discord.Embed):
				await ctx.channel.send(embed = report)
				return
		except Exception as err:
			print(err)
			report = reqLimit
		await ctx.channel.send(embed = bbEmbed("Beardless Bot Brawlhalla Clan", report))
		return

@bot.command(name = "brawllegend")
async def cmdBrawllegend(ctx, legend = None, *args):
	if not brawlKey:
		return
	report = "Invalid legend! Please do !brawllegend followed by a legend name."
	if legend:
		try:
			legend = legendInfo(brawlKey, legend)
			if legend:
				await ctx.channel.send(embed = legend)
				return
		except Exception as err:
			print(err)
			report = reqLimit
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Brawlhalla Legend Info", report))
	return

# Server-specific commands:

@bot.command(name = "tweet", aliases = ("eggtweet",))
async def cmdTweet(ctx, *args):
	if ctx.guild and ctx.guild.id == 442403231864324119:
		await ctx.channel.send(embed = bbEmbed("eggsoup(@eggsouptv)", formattedTweet(tweet()), 0x1da1f2))
	return

@bot.command(name = "reddit")
async def cmdReddit(ctx, *args):
	if ctx.guild and ctx.guild.id == 442403231864324119:
		await ctx.channel.send(embed = redditEmb)
	return

@bot.command(name = "guide")
async def cmdGuide(ctx, *args):
	if ctx.guild and ctx.guild.id == 442403231864324119:
		await ctx.channel.send(embed = bbEmbed("The Eggsoup Improvement Guide", "https://www.youtube.com/watch?v=nH0TOoJIU80"))
	return

@bot.event
async def on_message(message):
	if not message.author.bot:
		if message.guild:
			text = message.content.lower()

			if secretWord and secretWord in text:
				global secretFound
				if not secretFound:
					secretFound = True
					print("Secret word found by", message.author.name, "in", message.guild.name)
					result, bonus = writeMoney(message.author, 100000, True, True)
					report = "Ping Captain No-Beard for your prize" if result == -1 else "100000 BeardlessBucks have been added to your account"
					await message.channel.send(embed = bbEmbed(f"Well done! You found the secret word, {secretWord}!",
					f"{report}, {message.author.mention}!"))

			elif message.guild.name == "egg" and scamCheck(text):
				await message.author.add_roles(get(message.guild.roles, name = "Muted"))
				for channel in message.guild.channels:
					if channel.name == "infractions":
						await channel.send("Deleted possible scam nitro link sent by {} in {}.\nMessage content: {}"
						.format(message.author.mention, message.channel.mention, message.content))
						break
				await message.channel.send("Deleted possible nitro scam link. Alerting mods.")
				await message.delete()

			elif message.guild.name == "Day Care" and "twitter.com/year_progress" in text:
				await message.delete()
		try:
			await bot.process_commands(message) # Needed in order to run commands alongside on_message
		except Exception as err:
			print(err)
	return

if __name__ == "__main__":
	try:
		with open("resources/token.txt", "r") as f:
			# In token.txt, paste in your own Discord API token
			token = f.readline()
	except:
		print("Fatal error: no Discord API token. Shutting down.")
		sysExit(-1)

	try:
		with open("resources/brawlhallaKey.txt", "r") as f:
			# In brawlhallaKey.txt, paste in your own Brawlhalla API key
			brawlKey = f.readline()
	except:
		print("No Brawlhalla API key. Brawlhalla-specific commands will not be active.")
		brawlKey = None

	try:
		with open("resources/secretWord.txt") as f:
			secretWord = f.readline()
			if len(secretWord) < 2:
				raise Exception
		secretFound = False
	except:
		print("Secret word has not been defined. Continuing as normal.")
		secretWord = None

	# This dictionary is for keeping track of pings in the various looking-for-spar channels.
	global sparPings
	sparPings = {}

	global games
	games = [] # Stores the active instances of blackjack.

	bot.run(token)