# Beardless Bot Command Event Rewrite
# Author: Lev Bernstein
# Version: Full Release 1.5.10

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
sparPings = {}

games = [] # Stores the active instances of blackjack.

bot = commands.Bot(command_prefix = "!", case_insensitive = True, help_command = None, owner_id = 196354892208537600, intents = discord.Intents.all())

@bot.event
async def on_ready():
	print("Beardless Bot online!")
	try:
		await bot.change_presence(activity = discord.Game(name = 'try !blackjack and !flip'))
		print("Status updated!")
	except discord.HTTPException:
		print("Failed to update status! You might be restarting the bot too many times.")
	try:
		with open("resources/images/prof.png", "rb") as f:
			await bot.user.edit(avatar = f.read())
			print("Avatar live!")
	except discord.HTTPException:
		print("Avatar failed to update! You might be sending requests too quickly.")
	except FileNotFoundError:
		print("Avatar file not found! Check your directory structure.")
	print(f"Beardless Bot is in {len(bot.guilds)} servers.")
	# Initialize ping waiting time for each channel at 0 for each server bb is in:
	global sparPings
	for guild in bot.guilds:
		sparPings[guild.id] = {'jpn': 0, 'brz': 0, 'us-w': 0, 'us-e': 0, 'sea': 0, 'aus': 0, 'eu': 0}

@bot.event
async def on_guild_join(guild):
	global sparPings # create sparPings entry for this new server
	sparPings[guild.id] = {'jpn': 0, 'brz': 0, 'us-w': 0, 'us-e': 0, 'aus': 0, 'sea': 0, 'eu': 0}
	print(f"Just joined {guild.name}! Beardless Bot is now in {len(bot.guilds)} servers.")
	try: # Create roles for sparring. If unable to do so, then bb was not given admin perms.
		for key, value in sparPings[guild.id].items():
			if not get(guild.roles, name = key.upper()):
				await guild.create_role(name = key.upper(), mentionable = False)
	except: # Switch to creating muted role
		print(f"Not given admin perms in {guild.name}.")
		for channel in guild.channels:
			try:
				await channel.send(embed = noPerms())
				break
			except:
				pass
		await guild.leave()
		print(f"Left {guild.name}. Beardless Bot is now in {len(bot.guilds)} servers.")

@bot.event
async def on_message_delete(text):
	if text.guild and (text.channel.name != "bb-log" or text.content):
		# Prevents embeds from causing a loop
		for channel in text.guild.channels:
			if channel.name == "bb-log":
				await channel.send(embed = logDeleteMsg(text))
				return

@bot.event
async def on_bulk_message_delete(textArr):
	if textArr[0].guild:
		for channel in textArr[0].guild.channels:
			if channel.name == "bb-log":
				try:
					await channel.send(embed = logPurge(textArr[0], textArr))
				except Exception as err:
					print(err)
					return
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
				return

@bot.event
async def on_reaction_clear(text, reactions):
	if text.guild:
		for channel in text.guild.channels:
			if channel.name == "bb-log":
				try:
					await channel.send(embed = logClearReacts(text, reactions))
				except Exception as err:
					print(err)
					return
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

@bot.command(name = "blackjack", aliases = ("bj",))
async def cmdBlackjack(ctx, wagered = "10", *args):
	if "," in ctx.author.name:
		report = commaWarn.format(ctx.author.mention)
	else:
		report = f"You need to register first! Type !register to get started, {ctx.author.mention}."
		allBet = (wagered.lower() == "all")
		if allBet:
			bet = 0
		else:
			try:
				bet = int(wagered)
			except:
				print("Failed to cast bet to int! Bet msg: " + ctx.message.content)
				bet = -1
		if any(ctx.author == game.getUser() for game in games):
			report = f"You already have an active game, {ctx.author.mention}."
		elif bet < 0:
			report = "Invalid bet. Please choose a number greater than or equal to 0, or enter \"all\" to bet your whole balance."
		else:
			with open('resources/money.csv', 'r') as csvfile:
				for row in csv.reader(csvfile, delimiter = ','):
					if str(ctx.author.id) == row[0]:
						bank = int(row[1])
						if allBet:
							bet = bank
						report = f"You do not have enough BeardlessBucks to bet that much, {ctx.author.mention}!"
						if bet <= bank:
							game = Instance(ctx.author, bet)
							report = game.message
							if game.perfect():
								newLine = ",".join((row[0], str(bank + bet), str(ctx.author)))
								with open("resources/money.csv", "r") as oldMoney:
									oldMoney = ''.join([i for i in oldMoney]).replace(",".join(row), newLine)
									with open("resources/money.csv", "w") as newMoney:
										newMoney.writelines(oldMoney)
							else:
								games.append(game)
						break
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Blackjack", report))
	return

@bot.command(name = "deal", aliases = ("hit",))
async def cmdDeal(ctx, *args):
	if "," in ctx.author.name:
		report = commaWarn.format(ctx.author.mention)
	else:
		report = f"You do not currently have a game of blackjack going, {ctx.author.mention}. Type !blackjack to start one."
		for i in range(len(games)):
			if games[i].getUser() == ctx.author:
				game = games[i]
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
		for i in range(len(games)):
			if games[i].getUser() == ctx.author:
				game = games[i]
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

@bot.command(name = "flip")
async def cmdFlip(ctx, bet = "10", *args):
	if any(ctx.author == game.getUser() for game in games):
		report = f"Please finish your game of blackjack first, {ctx.author.mention}."
	else:
		report = flip(ctx.author, bet.lower())
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Coin Flip", report))
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
	link = "https://open.spotify.com/playlist/2JSGLsBJ6kVbGY1B7LP4Zi?si=Zku_xewGTiuVkneXTLCqeg"
	await ctx.channel.send(f"Here's my playlist (Discord will only show the first hundred songs):\n{link}")
	return

@bot.command(name = "leaderboard", aliases=("leaderboards", "lb"))
async def cmdLeaderboard(ctx, *args): # TODO: also report user's position on the leaderboard
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
	await ctx.channel.send(embed = joinMsg())
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
	header = f"Beardless Bot Fun Fact #{randint(1, 111111111)}"
	await ctx.channel.send(embed = bbEmbed(header, fact()))
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
	role = get(ctx.guild.roles, name = 'Muted')
	if not role: # Creates a Muted role. TODO: iterate through channels, make Muted unable to send msgs
		role = await ctx.guild.create_role(name = "Muted", colour = discord.Color(0x818386),
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
	await target.add_roles(role)
	report = "Muted " + target.mention + ((" for " + duration + mString + ".") if mTime else ".")
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Mute", report).set_author(name = str(ctx.author), icon_url = ctx.author.avatar_url))
	for channel in ctx.guild.channels:
		if channel.name == "bb-log":
			await channel.send(embed = logMute(target, ctx.message, duration, mString, mTime))
			break
	if mTime: # Autounmute
		print(f"Muted {target} for {mTime} in {ctx.guild.name}")
		await asyncio.sleep(mTime)
		await target.remove_roles(role)
		print("Autounmuted " + target.name)
		for channel in ctx.guild.channels:
			if channel.name == "bb-log":
				await channel.send(embed = logUnmute(target, ctx.author))
				return
	return

@bot.command(name = "unmute")
async def cmdUnmute(ctx, target = None, *args):
	if not ctx.guild:
		return
	report = f"You do not have permission to use this command, {ctx.author.mention}."
	if ctx.author.guild_permissions.manage_messages:
		if not target:
			report = f"Invalid target, {ctx.author.mention}."
		else:
			converter = commands.MemberConverter() # look into replacing with a converter in def
			target = await converter.convert(ctx, target)
			await target.remove_roles(get(ctx.guild.roles, name = 'Muted'))
			report = f"Unmuted {target.mention}."
			for channel in ctx.guild.channels:
				if channel.name == "bb-log":
					await channel.send(embed = logUnmute(target, ctx.author))
					break
	await ctx.channel.send(embed = bbEmbed("Beardless Bot Unmute", report))
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
		role = get(ctx.guild.roles, name = 'special ' + color)
		if not role:
			report = "That special color role does not exist in this server, {}."
		elif role in ctx.author.roles:
			report = "You already have this special color, {}."
		else:
			report = "Not enough BeardlessBucks. You need 50000 to buy a special color, {}."
			with open('resources/money.csv', 'r') as csvfile:
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
		await ctx.channel.send(embed = sparPins())
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
		await ctx.channel.send(embed = sparPins())
		return
	report = badRegion.format(ctx.author.mention)
	tooRecent = role = None
	global sparPings
	region = region.lower()
	if region == "usw":
		region = "us-w"
	if region == "use":
		region = "us-e"
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
						if misc:
							report += " Additional info: \"{}\"".format(" ".join(misc))
					else:
						tooRecent = value
					break
			break
	if role and tooRecent:
		hours, seconds = divmod(7200 - (int(time()) - tooRecent), 3600)
		minutes, seconds = divmod(seconds, 60)
		report = pingMsg(ctx.author.mention, hours, minutes, seconds)
	await ctx.channel.send(report)
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
		report = ("{}" if not profUrl else "Invalid profile URL/Brawlhalla ID! {}").format(badClaim)
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
			rank = getRank(target, brawlKey)
			if isinstance(rank, discord.Embed):
				await ctx.channel.send(embed = rank)
				return
			report = rank if rank else f"{target.mention} needs to claim their profile first! Do !brawlclaim."
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
			stats = getStats(target, brawlKey)
			if isinstance(stats, discord.Embed):
				await ctx.channel.send(embed = stats)
				return
			report = stats if stats else f"{target.mention} needs to claim their profile first! Do !brawlclaim."
		except Exception as err:
			print(err)
			report = reqLimit
		await ctx.channel.send(embed = bbEmbed("Beardless Bot Brawlhalla Stats", report))
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
			clan = getClan(target.id, brawlKey)
			if isinstance(clan, discord.Embed):
				await ctx.channel.send(embed = clan)
				return
			report = clan if clan else f"{target.mention} needs to claim their profile first! Do !brawlclaim."
		except Exception as err:
			print(err)
			report = reqLimit
		await ctx.channel.send(embed = bbEmbed("Beardless Bot Brawlhalla Clan", report))
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
		await ctx.channel.send(embed = bbEmbed("The Official Eggsoup Subreddit", "https://www.reddit.com/r/eggsoup/")
		.set_thumbnail(url = "https://b.thumbs.redditmedia.com/xJ1-nJJzHopKe25_bMxKgePiT3HWADjtxioxlku7qcM.png"))
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
					print(f"Secret word found by {message.author.name} in {message.guild.name}.")
					result, bonus = writeMoney(message.author, 100000, True, True)
					report = "Ping Captain No-Beard for your prize" if result == -1 else "100000 BeardlessBucks have been added to your account"
					await message.channel.send(embed = bbEmbed(f"Well done! You found the secret word, {secretWord}!",
					f"{report}, {message.author.mention}!"))

			elif all((message.guild.name == "egg", "discord" in text, ("nitro" in text or "gift" in text), "http" in text)):
				await message.author.add_roles(get(message.guild.roles, name = 'Muted'))
				for channel in message.guild.channels:
					if channel.name == "infractions":
						await channel.send("Deleted possible scam nitro link sent by {} in {}.\nMessage content: {}"
						.format(message.author.mention, message.channel.mention, message.content))
						break
				await message.channel.send("Deleted possible nitro scam link. Alerting mods.")
				await message.delete()

			elif message.guild.name == "Day Care" and 'twitter.com/year_progress' in text:
				await message.delete()

		await bot.process_commands(message) # Needed in order to run commands alongside on_message
	return

bot.run(token)