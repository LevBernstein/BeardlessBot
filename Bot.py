# Beardless Bot
# Author: Lev Bernstein
# Version: Full Release 1.3.11

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

from blackjack import *
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

client = discord.Client(intents = discord.Intents.all())
class DiscordClass(client):
	@client.event
	async def on_ready():
		print("Beardless Bot online!")
		try:
			await client.change_presence(activity = discord.Game(name = 'try !blackjack and !flip'))
			print("Status updated!")
		except discord.HTTPException:
			print("Failed to update status! You might be restarting the bot too many times.")
		try:
			with open("images/prof.png", "rb") as f:
				await client.user.edit(avatar = f.read())
				print("Avatar live!")
		except discord.HTTPException:
			print("Avatar failed to update! You might be sending requests too quickly.")
		except FileNotFoundError:
			print("Avatar file not found! Check your directory structure.")
		print("Beardless Bot is in {} servers".format(len(client.guilds)))
		global sparPings
		for guild in client.guilds:
			sparPings[guild.id] = {'jpn': 0, 'brz': 0, 'us-w': 0, 'us-e': 0, 'sea': 0, 'aus': 0, 'eu': 0}

	@client.event
	async def on_guild_join(guild):
		global sparPings
		sparPings[guild.id] = {'jpn': 0, 'brz': 0, 'us-w': 0, 'us-e': 0, 'aus': 0, 'sea': 0, 'eu': 0}
		print("Just joined " + guild.name + "!")
		try:
			for key, value in sparPings[guild.id].items():
				if not get(guild.roles, name = key.upper()):
					await guild.create_role(name = key.upper(), mentionable = False)
		except:
			print("Not given admin perms in " + guild.name + ".")
			for channel in guild.channels:
				try:
					await channel.send(embed = noPerms())
					break
				except:
					pass
			await guild.leave()
			print("Left {}. Beardless Bot is now in {} servers.".format(guild.name, len(client.guilds)))
	
	@client.event
	async def on_message_delete(text):
		if text.guild and any((text.content, text.author.id != 654133911558946837, text.channel.name != "bb-log")):
			# Prevents embeds from causing a loop
			for channel in text.guild.channels:
				if channel.name == "bb-log":
					await channel.send(embed = logDeleteMsg(text))
					return
	
	@client.event
	async def on_bulk_message_delete(textArr):
		if textArr[0].guild:
			for channel in textArr[0].guild.channels:
				if channel.name == "bb-log":
					try:
						await channel.send(embed = logPurge(textArr[0], textArr))
					except:
						return
					return
	
	@client.event
	async def on_message_edit(before, after):
		if before.guild and before.content != after.content:
			# The above check prevents embeds from getting logged, as they have no "content" field
			for channel in before.guild.channels:
				if channel.name == "bb-log":
					try:
						await channel.send(embed = logEditMsg(before, after))
					except:
						return
					return
	
	@client.event
	async def on_reaction_clear(text, reactions):
		if text.guild:
			for channel in text.guild.channels:
				if channel.name == "bb-log":
					try:
						await channel.send(embed = logClearReacts(text, reactions))
					except:
						return
					return
	
	@client.event
	async def on_guild_channel_delete(ch):
		for channel in ch.guild.channels:
			if channel.name == "bb-log":
				await channel.send(embed = logDeleteChannel(ch))
				return
	
	@client.event
	async def on_guild_channel_create(ch):
		for channel in ch.guild.channels:
			if channel.name == "bb-log":
				await channel.send(embed = logCreateChannel(ch))
				return
	
	@client.event
	async def on_member_join(member):
		for channel in member.guild.channels:
			if channel.name == "bb-log":
				await channel.send(embed = logMemberJoin(member))
				return
	
	@client.event
	async def on_member_remove(member):
		for channel in member.guild.channels:
			if channel.name == "bb-log":
				await channel.send(embed = logMemberRemove(member))
				return
	
	@client.event
	async def on_member_update(before, after):
		for channel in after.guild.channels:
			if channel.name == "bb-log":
				if before.nick != after.nick:
					await channel.send(embed = logMemberNickChange(before, after))
				elif before.roles != after.roles:
					await channel.send(embed = logMemberRolesChange(before, after))
				return
	
	@client.event
	async def on_member_ban(guild, member):
		for channel in guild.channels:
			if channel.name == "bb-log":
				await channel.send(embed = logBan(member))
				return
	
	@client.event
	async def on_member_unban(guild, member):
		for channel in guild.channels:
			if channel.name == "bb-log":
				await channel.send(embed = logUnban(member))
				return
	
	# TODO: switch to command event instead of on_message for most commands
	@client.event
	async def on_message(text):
		if not text.author.bot:
			msg = text.content.lower()
			if msg.startswith('!bj') or msg.startswith('!bl'): # for command: alias blackjack !bj, bet
				if ',' in text.author.name:
					report = commaWarn.format(text.author.mention)
				else:
					report = "You need to register first! Type !register to get started, " + text.author.mention + "."
					strbet = '10' # Bets default to 10. If someone just types !blackjack, they will bet 10 by default.
					if msg.startswith('!blackjack ') and len(msg) > 11:
						strbet = msg.split('!blackjack ',1)[1]
					elif msg in ("!blackjack", "!bl"):
						pass
					elif msg.startswith('!bl ') and len(msg) > 4:
						strbet = msg.split('!bl ',1)[1]
					elif msg.startswith('!bl'):
						# This way, other bots' commands that start with !bl won't trigger blackjack.
						return
					elif msg.startswith('!bj') and len(msg) > 4:
						strbet = msg.split('!bj ',1)[1]
					allBet = False
					if strbet == "all":
						allBet = True
						bet = 0
					else:
						try:
							bet = int(strbet)
						except:
							bet = 10
							if ' ' in msg:
								print("Failed to cast bet to int! Bet msg: " + msg)
								bet = -1
					if bet < 0:
						report = "Invalid bet. Please choose a number greater than or equal to 0."
					elif any(text.author == game.getUser() for game in games):
						report = "You already have an active game, " + text.author.mention + "."
					else: # TODO: rewrite to use writeMoney to find bank
						with open('resources/money.csv', 'r') as csvfile:
							for row in csv.reader(csvfile, delimiter = ','):
								if str(text.author.id) == row[0]:
									bank = int(row[1])
									if allBet:
										bet = bank
									report = "You do not have enough BeardlessBucks to bet that much, " + text.author.mention + "!"
									if bet <= bank:
										x = Instance(text.author, bet)
										report = x.message
										if x.perfect():
											newLine = ",".join((row[0], str(bank + bet), str(text.author)))
											with open("resources/money.csv", "r") as oldMoney:
												oldMoney = ''.join([i for i in oldMoney]).replace(",".join(row), newLine)
												with open("resources/money.csv", "w") as money:
													money.writelines(oldMoney)
										else:
											games.append(x)
									break
				await text.channel.send(embed = discord.Embed(title = "Beardless Bot Blackjack", description = report, color = 0xfff994))
				return
			
			if msg in ('!deal', '!hit'):
				if ',' in text.author.name:
					report = commaWarn.format(text.author.mention)
				else:
					report = "You do not currently have a game of blackjack going, " + text.author.mention + ". Type !blackjack to start one."
					for i in range(len(games)):
						if games[i].getUser() == text.author:
							gamer = games[i]
							gamer.deal()
							report = gamer.message
							if gamer.checkBust() or gamer.perfect():
								writeMoney(text.author, gamer.bet * (-1 if gamer.checkBust() else 1), True, True)
								games.pop(i)
							break
				await text.channel.send(embed = discord.Embed(title = "Beardless Bot Blackjack", description = report, color = 0xfff994))
				return
			
			if msg in ('!stay', '!stand'):
				report = "You do not currently have a game of blackjack going, " + text.author.mention + ". Type !blackjack to start one."
				for i in range(len(games)):
					if games[i].getUser() == text.author:
						gamer = games[i]
						result = gamer.stay()
						report = gamer.message
						if result and gamer.bet:
							written, bonus = writeMoney(text.author, gamer.bet, True, True)
							if written == -1:
								report = bonus
						games.pop(i)
						break
				await text.channel.send(embed = discord.Embed(title = "Beardless Bot Blackjack", description = report, color = 0xfff994))
				return
			
			if secretWord:
				if secretWord in msg.split(" "):
					global secretFound
					if not secretFound:
						secretFound = True
						print("Secret word found by {} in {}.".format(text.author.name, text.guild.name))
						result, bonus = writeMoney(text.author, 100000, True, True)
						report = "Ping Captain No-Beard for your prize" if result == -1 else "100000 BeardlessBucks have been added to your account"
						await text.channel.send(embed = discord.Embed(title = "Well done! You found the secret word, " + secretWord + "!",
						description = "{}, {}!".format(report, text.author.mention),  color = 0xfff994))
					return
			
			if msg in ("!hint", "!hints"):
				if secretWord:
					await text.channel.send(embed = hints())
				else:
					await text.channel.send("Secret word has not been defined.")
				return
			
			if msg.startswith('!flip'):
				if any(text.author == game.getUser() for game in games):
					report = "Please finish your game of blackjack first, {}."
				else:
					heads = randint(0, 1)
					strBet = msg.split('!flip ',1)[1] if len(msg) > 6 else 10
					if msg == "!flip":
						bet = 10
					elif strBet == "all":
						bet = "all" if heads else "-all"
					else:
						try:
							bet = int(strBet)
						except:
							print("Failed to cast bet to int! Bet msg: " + msg)
							bet = -1
					report = "Invalid bet amount. Please choose a number >-1, {}."
					if (isinstance(bet, str) and "all" in bet) or (isinstance(bet, int) and bet >= 0):
						result, bank = writeMoney(text.author, 300, False, False)
						if not (isinstance(bet, str) or (isinstance(bet, int) and result == 0 and bet <= bank)):
							report = "You do not have enough BeardlessBucks to bet that much, {}!"
						else:
							if isinstance(bet, int) and not heads:
								bet *= -1
							result, bonus = writeMoney(text.author, bet, True, True)
							report = "Tails! You lose! Your loss has been deducted from your balance, {}."
							if heads:
								report = "Heads! You win! Your winnings have been added to your balance, {}."
							if result == -1:
								report = bonus
							elif result == 2:
								report = ("You were not registered for BeardlessBucks gambling, so I have " +
								"automatically registered you. You now have 300 BeardlessBucks, {}.")
							elif result == 0:
								report += " Or, they would have been, if you had actually bet anything."
				await text.channel.send(embed = discord.Embed(title = "Beardless Bot Coin Flip",
				description = report.format(text.author.mention), color = 0xfff994))
				return
			
			if brawlKey:
				if msg == "!brawl":
					await text.channel.send(embed = brawlCommands())
					return
				
				if msg.startswith("!brawlclaim"):
					brawlID = None
					try:
						profUrl = msg.split(" ")[1]
						brawlID = int(profUrl) if profUrl.isnumeric() else getBrawlID(brawlKey, profUrl)
						if not brawlID:
							raise Exception
					except:
						report = (("" if msg == "!brawlclaim" else "Invalid profile URL/Brawlhalla ID! ") + "Please do !brawlclaim followed by the " +
						"URL of your steam profile.\nExample: !brawlclaim https://steamcommunity.com/id/beardless\nAlternatively, you can claim " +
						"via your Brawlhalla ID, which you can find in the top right corner of your inventory.\nExample: !brawlclaim 7032472.")
					if brawlID:
						try:
							claimProfile(text.author.id, brawlID)
							report = "Profile claimed."
						except Exception as err:
							print(err)
							report = "I've reached the request limit for the Brawlhalla API. Please wait 15 minutes and try again later."
					await text.channel.send(embed = discord.Embed(title = "Beardless Bot Brawlhalla Rank", description = report, color = 0xfff994))
					return
				
				if msg.startswith("!brawlrank"):
					try:
						target = text.mentions[0] if text.mentions else text.author if not " " in msg else memSearch(text)
						report = "Invalid target!"
						if target:
							rank = getRank(target, brawlKey)
							if isinstance(rank, discord.Embed):
								await text.channel.send(embed = rank)
								return
							report = target.mention + " needs to claim their profile first! Do !brawlclaim."
							if rank:
								report = "You haven't played ranked yet this season."
					except Exception as err:
						print(err)
						report = "I've reached the request limit for the Brawlhalla API. Please wait 15 minutes and try again later."
					await text.channel.send(embed = discord.Embed(title = "Beardless Bot Brawlhalla Rank", description = report, color = 0xfff994))
					return
				
				if msg.startswith("!brawlstats"):
					try:
						target = text.mentions[0] if text.mentions else text.author if not " " in msg else memSearch(text)
						report = "Invalid target!"
						if target:
							stats = getStats(target, brawlKey)
							if stats:
								await text.channel.send(embed = stats)
								return
							report = target.mention + " needs to claim their profile first! Do !brawlclaim."
					except Exception as err:
						print(err)
						report = "I've reached the request limit for the Brawlhalla API. Please wait 15 minutes and try again later."
					await text.channel.send(embed = discord.Embed(title = "Beardless Bot Brawlhalla Stats", description = report, color = 0xfff994))
					return
				
				if msg.startswith("!brawllegend ") and not msg == "!brawllegend ":
					report = "Invalid legend! Please do !brawllegend followed by a legend name."
					try:
						legend = legendInfo(brawlKey, msg.split("!brawllegend ", 1)[1])
						if legend:
							await text.channel.send(embed = legend)
							return
					except Exception as err:
						print(err)
						report = "I've reached the request limit for the Brawlhalla API. Please wait 15 minutes and try again later."
					await text.channel.send(embed = discord.Embed(title = "Beardless Bot Brawlhalla Legend Info", description = report, color = 0xfff994))
					return
				
				if msg.startswith("!brawlclan"):
					try:
						target = text.mentions[0] if text.mentions else text.author if not " " in msg else memSearch(text)
						report = "Invalid target!"
						if target:
							clan = getClan(target.id, brawlKey)
							if isinstance(clan, discord.Embed):
								await text.channel.send(embed = clan)
								return
							report = target.mention + " needs to claim their profile first! Do !brawlclaim." if not clan else "You are not in a clan!"
					except Exception as err:
						print(err)
						report = "I've reached the request limit for the Brawlhalla API. Please wait 15 minutes and try again later."
					await text.channel.send(embed = discord.Embed(title = "Beardless Bot Brawlhalla Clan", description = report, color = 0xfff994))
					return
			
			if msg.startswith('!av'):
				await text.channel.send(embed = av(text))
				return
			
			if msg in ('!playlist', '!music'):
				report = ("Here's my playlist (discord will only show the first hundred songs):\n" +
				"https://open.spotify.com/playlist/2JSGLsBJ6kVbGY1B7LP4Zi?si=Zku_xewGTiuVkneXTLCqeg")
				await text.channel.send(report)
				return
			
			if msg in ("!leaderboard", "!leaderboards", "!lb"):
				await text.channel.send(embed = leaderboard())
				return
			
			if msg.startswith('!dice'):
				report = ("Enter !d[number][+/-][modifier] to roll a [number]-sided die " +
				"and add or subtract a modifier. For example: !d8+3, or !d100-17, or !d6.")
				await text.channel.send(embed = discord.Embed(title = "Beardless Bot Dice", color = 0xfff994, description = report))
				return
			
			if msg == '!reset':
				await text.channel.send(embed = reset(text))
				return
			
			if (msg.startswith("!balance") or msg.startswith("!bal")) and any((msg == "!bal", msg == "!balance", msg.count(" ") > 0)):
				await text.channel.send(embed = balance(text))
				return
			
			if msg == "!register": # Make sure resources/money.csv is not open in any other program
				await text.channel.send(embed = register(text))
				return
			
			if msg == "!bucks":
				report = ("BeardlessBucks are this bot's special currency. You can earn them " +
				"by playing games. First, do !register to get yourself started with a balance.")
				await text.channel.send(embed = discord.Embed(title = "BeardlessBucks", color = 0xfff994, description = report))
				return
			
			if msg in ("!hello", "!hi"):
				greetings = "How ya doin?", "Yo!", "What's cookin?", "Hello!", "Ahoy!", "Hi!", "What's up?", "Hey!", "How's it goin?", "Greetings!"
				await text.channel.send(choice(greetings))
				return
			
			if msg == "!source":
				report = "Most facts taken from [this website](https://www.thefactsite.com/1000-interesting-facts/)."
				await text.channel.send(embed = discord.Embed(title = "Beardless Bot Fun Facts", color = 0xfff994, description = report))
				return
			
			if msg in ("!add", "!join"):
				await text.channel.send(embed = join())
				return
			
			if msg == "!rohan":
				await text.channel.send(file = discord.File('images/cute.png'))
				return
			
			if msg.startswith("!random"):
				await text.channel.send(embed = randomBrawl(msg))
				return
			
			if msg == "!fact":
				header = "Beardless Bot Fun Fact #" + str(randint(1,111111111))
				await text.channel.send(embed = discord.Embed(title = header, description = fact(), color = 0xfff994))
				return
			
			if msg in ("!animals", "!pets"):
				await text.channel.send(embed = animals())
				return
			
			animalName = msg[1:].split(" ", 1)[0]
			if animalName in ("dog", "moose"):
				if "moose" in msg:
					await text.channel.send(file = discord.File("images/moose/moose{}.jpg".format(randint(1, 45))))
					return
				try:
					dogUrl = animal(msg[1:])
					if dogUrl.startswith("Breed not found") or dogUrl.startswith("Dog breeds"):
						await text.channel.send(dogUrl)
						return
					breed = "Hound" if "hound" in dogUrl else dogUrl.split("/")[-2]
					await text.channel.send(embed = discord.Embed(title = "Random " + breed.title(), color = 0xfff994).set_image(url = dogUrl))
				except:
					await text.channel.send("Something's gone wrong with the dog API! Please ping my creator and he'll see what's going on.")
				return
			
			animalList = "cat", "duck", "fish", "fox", "rabbit", "bunny", "panda", "bird", "koala", "lizard", "raccoon", "kangaroo"
			if msg.startswith("!") and animalName in animalList:
				try:
					await text.channel.send(embed = discord.Embed(title = "Random " + animalName.title(), color = 0xfff994)
					.set_image(url = animal(animalName)))
				except Exception as err:
					print(err)
					report = "Something's gone wrong! Please ping my creator and he'll see what's going on."
					if animalName == "fish":
						report = "The fish API is currently down. I do not know when it will come back up."
					await text.channel.send(report)
				return
			
			if msg.startswith("!define "):
				await text.channel.send(embed = define(msg))
				return
			
			if msg == "!ping":
				startTime = datetime.now()
				message = await text.channel.send(embed = discord.Embed(title = "Pinging...", color = 0xfff994))
				report = "Beardless Bot's latency is {} ms.".format(int((datetime.now() - startTime).total_seconds() * 1000))
				link = "https://cdn.discordapp.com/avatars/654133911558946837/78c6e18d8febb2339b5513134fa76b94.webp?size=1024"
				await message.edit(embed = discord.Embed(title = "Pinged!", description = report, color = 0xfff994).set_thumbnail(url = link))
				return
			
			if msg.startswith('!d') and len(msg) > 2 and ((msg.split('!d',1)[1])[0]).isnumeric() and len(msg) < 12:
				# The isnumeric check ensures that you can't activate this command by typing !deal or !debase or anything else.
				await text.channel.send(embed = rollReport(text))
				return
			
			if msg in ("!commands", "!help"):
				await text.channel.send(embed = commands(text))
				return
			
			if text.guild: # Server-specific commands; this check prevents an error caused by commands being used in DMs
				if msg.startswith('!mute'):
					if text.author.guild_permissions.manage_messages:
						if text.mentions:
							target = text.mentions[0]
							duration = msg.split('>', 1)[1]
							if target.id == 654133911558946837: # If user tries to mute Beardless Bot:
								await text.channel.send("I am too powerful to be muted. Stop trying.")
								return
							role = get(text.guild.roles, name = 'Muted')
							if not role: # Creates a Muted role
								role = await text.guild.create_role(name = "Muted", colour = discord.Color(0x818386),
								permissions = discord.Permissions(send_messages = False, read_messages = True))
							mTime = 0.0 # TODO: iterate through channels, make Muted unable to send msgs
							mString = None
							if len(duration) > 1:
								duration = duration[1:]
								if 'h' in duration:
									duration = duration.split('h', 1)[0]
									mString = " hour"
									mTime = float(duration) * 3600.0
								elif 'm' in duration:
									duration = duration.split('m', 1)[0]
									mString = " minute"
									mTime = float(duration) * 60.0
								elif 's' in duration:
									duration = duration.split('s', 1)[0]
									mString = " second"
									mTime = float(duration)
								if duration != "1":
									mString += "s"
							await target.add_roles(role)
							report = "Muted " + target.mention + ((" for " + duration + mString + ".") if mTime else ".")
							
							await text.channel.send(embed = discord.Embed(title = "Beardless Bot Mute", description = report,
							color = 0xfff994).set_author(name = str(text.author), icon_url = text.author.avatar_url))
							for channel in text.guild.channels:
								if channel.name == "bb-log":
									await channel.send(embed = logMute(target, text, duration, mString, mTime))
									break
							if mTime: # Autounmute:
								print("Muted {} for {} in {}.".format(target, mTime, text.guild.name))
								await asyncio.sleep(mTime)
								await target.remove_roles(role)
								print("Autounmuted " + target.name)
								for channel in text.guild.channels:
									if channel.name == "bb-log":
										await channel.send(embed = logUnmute(target, text.author))
										return
						else:
							await text.channel.send("Invalid target!")
					else:
						await text.channel.send("You do not have permission to use this command, " + text.author.mention + ".")
					return
				
				if msg.startswith('!unmute') or msg.startswith('-unmute'):
					report = "You do not have permission to use this command, " + text.author.mention + "."
					if text.author.guild_permissions.manage_messages:
						report = "Invalid target, " + text.author.mention + "."
						if text.mentions:
							target = text.mentions[0]
							await target.remove_roles(get(text.guild.roles, name = 'Muted'))
							report = "Unmuted " + target.mention + "."
							for channel in text.guild.channels:
								if channel.name == "bb-log":
									await channel.send(embed = logUnmute(target, text.author))
									break
					await text.channel.send(embed = discord.Embed(title = "Beardless Bot Unmute", description = report, color = 0xfff994))
					return
				
				if msg.startswith("!clear") or msg.startswith("!purge"):
					if not text.author.guild_permissions.manage_messages:
						await text.channel.send("You do not have permission to use this command, " + text.author.mention + ".")
						return
					try:
						await text.channel.purge(limit = int(msg.split(" ", 1)[1]) + 1, check = lambda message: not message.pinned)
					except:
						await text.channel.send("Invalid message number!")
					return
				
				if msg.startswith('!buy'): # Requires roles named special blue, special pink, special orange, and special red.
					report = "Invalid color. Choose blue, red, orange, or pink, {}."
					if msg != "!buy":
						color = msg.split(" ", 1)[1]
						role = get(text.guild.roles, name = 'special ' + color)
						if color not in ("blue", "pink", "orange", "red"):
							report = "Invalid color. Choose blue, red, orange, or pink, {}."
						elif not role:
							report = "Special color roles do not exist in this server, {}."
						elif role in text.author.roles:
							report = "You already have this special color, {}."
						else:
							report = "Not enough BeardlessBucks. You need 50000 to buy a special color, {}."
							with open('resources/money.csv', 'r') as csvfile:
								result, bonus = writeMoney(text.author, -50000, True, True)
								if result == 1:
									report = "Color " + role.mention + " purchased successfully, {}!"
									await text.author.add_roles(role)
								if result == -1:
									report = bonus
								if result == 2:
									report = ("You were not registered for BeardlessBucks gambling, so I " +
									"have automatically registered you. You now have 300 BeardlessBucks, {}.")
					await text.channel.send(embed = discord.Embed(title = "Beardless Bot Special Colors",
					description = report.format(text.author.mention), color = 0xfff994))
					return
				
				if msg.startswith("!info"):
					await text.channel.send(embed = info(text))
					return
				
				if msg.startswith('!spar '): # command rewrite will use region, *
					if text.channel.name == "looking-for-spar":
						report = ("Please specify a valid region, " + text.author.mention + "! Valid " +
						"regions are US-E, US-W, EU, AUS, SEA, BRZ, JPN. If you need help, try doing !pins.")
						tooRecent = role = None
						global sparPings
						splitMsg = msg.split(" ")
						for guild, pings in sparPings.items():
							if guild == text.guild.id:
								for key, value in sparPings[guild].items():
									if key in splitMsg:
										role = get(text.guild.roles, name = key.upper())
										if not role:
											role = await text.guild.create_role(name = key.upper(), mentionable = False)
										if time() - value > 7200:
											sparPings[guild][key] = int(time())
											report = role.mention + " come spar " + text.author.mention + "!"
										else:
											tooRecent = value
										break
								if not role:
									if "usw" in splitMsg or "use" in splitMsg:
										spelledRole = "us-w" if "usw" in splitMsg else "us-e"
										role = get(text.guild.roles, name = spelledRole.upper())
										if not role:
											role = await text.guild.create_role(name = spelledRole.upper(), mentionable = False)
										if time() - sparPings[guild][spelledRole] > 7200:
											sparPings[guild][spelledRole] = int(time())
											report = role.mention + " come spar " + text.author.mention + "!"
										else:
											tooRecent = sparPings[guild][spelledRole]
								break
						if role and tooRecent:
							hours, seconds = divmod(7200 - (int(time()) - tooRecent), 3600)
							minutes, seconds = divmod(seconds, 60)
							report = ("This region has been pinged too recently! Regions can only be pinged once every two hours, " +
							"{}. You can ping again in {} hour{}, {} minute{}, and {} second{}.".format(text.author.mention, str(hours),
							"" if hours == 1 else "s", str(minutes), "" if minutes == 1 else "s", str(seconds), "" if seconds == 1 else "s"))
					else:
						report = "Please only use !spar in looking-for-spar, " + text.author.mention + "."
						for channel in text.guild.channels:
							if channel.name == "looking-for-spar":
								report = "Please only use !spar in " + channel.mention + ", " + text.author.mention + "."
								break
					await text.channel.send(report)
					return
				
				if text.channel.name == "looking-for-spar" and msg in ('!pins', '!rules', '!spar'):
					await text.channel.send(embed = sparPins())
					return
				
				if msg == '!twitch':
					link = "https://yt3.ggpht.com/ytc/AKedOLStPqU8W7FinOREV9HpU1P9Zm23O9qOlbmbPWoZ=s88-c-k-c0x00ffffff-no-rj"
					await text.channel.send(embed = discord.Embed(title = "Captain No-Beard's Twitch Stream",
					description = "https://twitch.tv/capnnobeard", color = 0xfff994).set_thumbnail(url = link))
					return
				
				if text.guild.id == 797140390993068035 and msg == '!file': # Command for Jetspec's Discord server.
					jet = await text.guild.fetch_member("579316676642996266")
					await text.channel.send(jet.mention)
					print("Pinging Jetspec.")
					return
				
				if text.guild.id == 442403231864324119: # Commands for eggsoup's Discord server.
					if msg in ('!tweet', '!eggtweet'):
						await text.channel.send(embed = discord.Embed(title = "eggsoup(@eggsouptv)",
						description = formattedTweet(tweet()), color = 0x1da1f2))
						return
					
					if msg == '!reddit':
						image = ("https://styles.redditmedia.com/t5_2m5xhn/styles/communityIcon_" +
						"0yqex29y6lu51.png?width=256&s=fcf916f19b8f0bffff91d512691837630b378d80")
						await text.channel.send(embed = discord.Embed(title = "The Official Eggsoup Subreddit",
						description = "https://www.reddit.com/r/eggsoup/", color = 0xfff994).set_thumbnail(url = image))
						return
					
					if msg == '!guide':
						await text.channel.send(embed = discord.Embed(title = "The Eggsoup Improvement Guide",
						description = "https://www.youtube.com/watch?v=nH0TOoJIU80", color = 0xfff994))
						return
					
					if all((msg.startswith('!warn'), text.channel.name != "infractions", len(msg) > 6, text.author.guild_permissions.manage_messages)):
						await text.channel.send(embed = discord.Embed(title = "Infraction Logged.", color = 0xfff994),
						description = "Mods can view the infraction details in <#705098150423167059>.")
						return
				
				if text.guild.id == 781025281590165555: # Commands for the Day Care Discord server.
					if 'twitter.com/year_progress' in msg:
						await text.delete()
						return
	
	client.run(token)