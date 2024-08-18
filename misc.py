"""Beardless Bot miscellaneous methods"""

import logging
import re
from datetime import datetime
from json import loads
from random import choice, randint
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import quote_plus

import nextcord
import requests
from bs4 import BeautifulSoup
from nextcord.ext import commands

diceMsg = (
	"Enter !roll [count]d[number][+/-][modifier] to roll [count]"
	" [number]-sided dice and add or subtract a modifier. For example:"
	" !d8+3, or !4d100-17, or !d6."
)

prof = (
	"https://cdn.discordapp.com/attachments/613030322644451349/"
	"947434005878435910/CapGift.jpg"
)

animalList = (
	"cat",
	"duck",
	"fox",
	"seal",
	"rabbit",
	"lizard",
	"frog",
	"bear",
)

hierarchyMsg = (
	"It looks like I don't have permission to modify that user's roles!"
	" Raise my place in the role hierarchy, please."
)

naughty = "You do not have permission to use this command, {}."

greetings = (
	"How ya doin?",
	"Yo!",
	"What's cookin?",
	"Hello!",
	"Ahoy!",
	"Hi!",
	"What's up?",
	"Hey!",
	"How's it goin?",
	"Greetings!"
)

redditThumb = (
	"https://b.thumbs.redditmedia.com/xJ1-nJJ"
	"zHopKe25_bMxKgePiT3HWADjtxioxlku7qcM.png"
)

tweetThumb = (
	"https://pbs.twimg.com/profile_images/13"
	"97696436393836546/NgpD6O57_400x400.jpg"
)

scamDM = (
	"This is an automated message. You have sent a message that has"
	" been identified as containing a scam nitro link in **{}**. Your"
	" account may have been compromised. Please take the appropriate"
	" measures and be sure to reach out to an admin if you need help."
)

scamReport = (
	"Deleted possible scam nitro link sent by {} in {}.\nMessage content:\n{}"
)

scamDelete = "**Deleted possible nitro scam link. Alerting mods.**"

joinMsg = (
	"Thanks for adding me to {}! There are a few things you can do to unlock "
	"my full potential.\nIf you want event logging, make a channel named "
	"#bb-log.\nIf you want a region-based sparring system, make a channel "
	"named #looking-for-spar.\nIf you want special color roles, purchasable "
	"with BeardlessBucks, create roles named special red/blue/orange/pink.\n"
	"Don't forget to move my {} role up to the top of the role hierarchy in "
	"order to allow me to moderate all users."
)

msgMaxLength = "**Message length exceeds 1024 characters.**"


# Wrapper for nextcord.Embed() that defaults to
# commonly-used values and is easier to call
def bbEmbed(
	name: str = "",
	value: str = "",
	col: Union[int, nextcord.Color] = 0xFFF994,
	showTime: bool = False
) -> nextcord.Embed:
	return nextcord.Embed(
		title=name,
		description=value,
		color=col,
		timestamp=datetime.now() if showTime else None
	)


def contCheck(msg: nextcord.Message) -> str:
	if msg.content:
		if len(msg.content) > 1024:
			return msgMaxLength
		return msg.content
	return "**Embed**"


def logException(e: Exception, ctx: commands.Context) -> None:
	"""
	Act as a wrapper for logging.error to help with debugging.

	Args:
		e (Exception): The exception to log
		ctx (commands.Context): The command invocation context

	"""
	logging.error(
		f"{e} Command: {ctx.invoked_with}; Author: {ctx.author};"
		f" Content: {contCheck(ctx.message)}; Guild: {ctx.guild};"
		f" Type: {type(e)}"
	)


async def createMutedRole(guild: nextcord.Guild) -> nextcord.Role:
	"""
	Create a "Muted" role that prevents users from sending messages.

	Args:
		guild (nextcord.Guild): The guild in which to create the role

	Returns:
		nextcord.Role: The Muted role.

	"""
	overwrite = nextcord.PermissionOverwrite(send_messages=False)
	role = await guild.create_role(
		name="Muted",
		colour=nextcord.Colour(0x818386),
		mentionable=False,
		permissions=nextcord.Permissions(
			send_messages=False,
			read_messages=True,
			send_messages_in_threads=False
		)
	)
	for channel in guild.channels:
		await channel.set_permissions(role, overwrite=overwrite)
	return role


def memSearch(
	message: nextcord.Message, target: str
) -> Optional[nextcord.Member]:
	"""
	User lookup helper method. Finds user based on username and/or
	discriminator (#1234). Runs in linear time; worst case, does not find a
	loosely-matching target, takes O(n) operations

	Args:
		message (nextcord.Message): The message that invoked this command
		target (str): The target of the search. Ideally a username

	Returns:
		Optional[nextcord.Member]: A matching user, if one can be found.

	"""
	term = str(target).lower()
	semiMatch = looseMatch = None
	assert message.guild
	for member in message.guild.members:
		if term == str(member).lower() or term == str(member.id):
			return member
		if term == member.name.lower():
			if "#" not in term:
				return member
			semiMatch = member
		if member.nick and term == member.nick.lower() and not semiMatch:
			looseMatch = member
		if not (semiMatch or looseMatch) and term in member.name.lower():
			looseMatch = member
	return semiMatch if semiMatch else looseMatch


def getLogChannel(guild: nextcord.Guild) -> Optional[nextcord.TextChannel]:
	"""
	#bb-log channel lookup helper method.

	Args:
		guild (nextcord.Guild): The guild to search

	Returns:
		Optional[nextcord.TextChannel]: The bb-log channel if it exists;
			else, None.

	"""
	channels = [c for c in guild.text_channels if c.name == "bb-log"]
	if channels and isinstance(channels[0], nextcord.TextChannel):
		return channels[0]
	return None


def fetchAvatar(
	user: Union[nextcord.Member, nextcord.User, nextcord.ClientUser]
) -> str:
	"""
	Pull a given user's avatar url.

	Args:
		user (nextcord.Member or User or ClientUser): The user whose avatar
			url should be returned

	Returns:
		str: The user's avatar url if they have one; else the user's default
			avatar url.

	"""
	if user.avatar:
		return user.avatar.url
	return user.default_avatar.url


def animal(animalType: str, breed: Optional[str] = None) -> str:
	r: Optional[requests.Response] = None

	if "moose" in (animalType, breed):
		r = requests.get(
			"https://github.com/LevBernstein/moosePictures/", timeout=10
		)
		if r.status_code == 200:
			soup = BeautifulSoup(r.content.decode("utf-8"), "html.parser")
			moose = choice(
				tuple(
					m for m in soup.stripped_strings
					if m.startswith("moose") and m.endswith(".jpg")
				)
			)

			return (
				"https://raw.githubusercontent.com/"
				f"LevBernstein/moosePictures/main/{moose}"
			)

	elif animalType == "dog":
		# Dog API has been throwing 522 errors
		for i in range(10):
			if i != 0:
				logging.error(f"Dog API trying again, call {i}")
			if not breed:
				r = requests.get(
					"https://dog.ceo/api/breeds/image/random", timeout=10
				)
				if r.status_code == 200:
					return r.json()["message"]
			elif breed.startswith("breed"):
				r = requests.get(
					"https://dog.ceo/api/breeds/list/all", timeout=10
				)
				if r.status_code == 200:
					return "Dog breeds: {}.".format(
						", ".join(dog for dog in r.json()["message"])
					)
			elif breed.isalpha():
				r = requests.get(
					"https://dog.ceo/api/breed/" + breed + "/images/random",
					timeout=10
				)
				if (
					r.status_code == 200
					and "message" in r.json()
					and not r.json()["message"].startswith("Breed not found")
				):
					return r.json()["message"]
				return "Breed not found! Do !dog breeds to see all breeds."
			else:
				return "Breed not found! Do !dog breeds to see all breeds."

	elif animalType == "cat":
		r = requests.get(
			"https://api.thecatapi.com/v1/images/search", timeout=10
		)
		if r.status_code == 200:
			return r.json()[0]["url"]

	elif animalType in ("bunny", "rabbit"):
		r = requests.get(
			"https://api.bunnies.io/v2/loop/random/?media=gif", timeout=10
		)
		if r.status_code == 200:
			return r.json()["media"]["gif"]

	elif animalType == "fox":
		r = requests.get("https://randomfox.ca/floof/", timeout=10)
		if r.status_code == 200:
			return r.json()["image"]

	elif animalType in ("duck", "lizard"):
		if animalType == "duck":
			r = requests.get("https://random-d.uk/api/quack", timeout=10)
		else:
			r = requests.get(
				"https://nekos.life/api/v2/img/lizard", timeout=10
			)
		if r.status_code == 200:
			return r.json()["url"]

	elif animalType == "bear":
		return f"https://placebear.com/{randint(200, 400)}/{randint(200, 400)}"

	elif animalType == "frog":
		frog = choice(frogList)["name"]
		return (
			f"https://raw.githubusercontent.com/a9-i/frog/main/ImgSetOpt/{frog}"
		)

	elif animalType == "seal":
		sealID = str(randint(0, 83)).rjust(4, "0")
		return f"https://focabot.github.io/random-seal/seals/{sealID}.jpg"

	if r is not None and r.status_code != 200:
		raise requests.exceptions.RequestException(
			f"Failed to call {animalType} Animal API"
		)
	raise ValueError("Invalid Animal: " + animalType)


# Amortize the cost of pulling the frog images by making one initial call.
# Two possible layouts, one when formatting fails.
def getFrogList() -> List[Dict[str, str]]:
	r = requests.get(
		"https://github.com/a9-i/frog/tree/main/ImgSetOpt", timeout=10
	)
	soup = BeautifulSoup(r.content.decode("utf-8"), "html.parser")
	try:
		j = loads(soup.findAll("script")[-1].text)["payload"]
	except KeyError:
		j = loads(
			soup.findAll("script")[-2].text.replace("\\", "\\\\")
		)["payload"]
	return j["tree"]["items"]


frogList = getFrogList()


def define(word: str) -> nextcord.Embed:
	r = requests.get(
		"https://api.dictionaryapi.dev/api/v2/entries/en_US/" + word,
		timeout=10
	)
	if r.status_code == 200:
		j = r.json()
		desc = ""
		p = j[0]["phonetics"]
		if p and "audio" in p[0] and p[0]["audio"]:
			desc = f"Audio: {j[0]['phonetics'][0]['audio']}"
		emb = bbEmbed(j[0]["word"].upper(), desc)
		i = 0
		for entry in j:
			for meaning in entry["meanings"]:
				for definition in meaning["definitions"]:
					i += 1
					emb.add_field(
						name=f"Definition {i}:",
						value=definition["definition"]
					)
		return emb
	if r.status_code == 404:
		return bbEmbed("Beardless Bot Definitions", "No results found.")
	return bbEmbed(
		"Beardless Bot Definitions",
		"There was an error with the dictionary API. Please ping my creator."
	)


def roll(text: str) -> Union[Tuple[None], Tuple[int, int, str, bool, int]]:
	# Takes a string of the format mdn+b and rolls m
	# n-sided dice with a modifier of b. m and b are optional.
	diceNum: Union[str, int]
	try:
		diceNum, command = text.split("d", 1)
	except (IndexError, ValueError):
		return (None,)
	diceNum = abs(int(diceNum)) if diceNum.replace("-", "").isnumeric() else 1
	diceNum = min(diceNum, 999)
	side = command.split("-")[0].split("+")[0]
	if side in ("4", "6", "8", "100", "10", "12", "20"):
		if (
			command != side
			and command[len(side)] in ("+", "-")
			and (bonus := command[1 + len(side):]).isnumeric()
		):
			b = (-1 if "-" in command else 1) * min(int(bonus), 999999)
		else:
			b = 0
		diceSum = sum(randint(1, int(side)) for i in range(diceNum))
		return diceSum + b, diceNum, side, "-" in command, b
	return (None,)


def rollReport(
	text: str, author: Union[nextcord.User, nextcord.Member]
) -> nextcord.Embed:
	result = roll(text.lower())
	if result[0] is not None:
		modifier = "" if result[3] else "+"
		title = f"Rolling {result[1]}d{result[2]}{modifier}{result[4]}"
		report = f"You got {result[0]}, {author.mention}."
	else:
		title = "Beardless Bot Dice"
		report = (
			"Invalid roll. Enter d4, 6, 8, 10, 12, 20, or 100, as well as"
			" number of dice and modifiers. No spaces allowed. Ex: !roll 2d4+3"
		)
	return bbEmbed(title, report)


def fact() -> str:
	with open("resources/facts.txt") as f:
		return choice(f.read().splitlines())


def truncTime(member: Union[nextcord.User, nextcord.Member]) -> str:
	return str(member.created_at)[:-10]


def info(
	target: Union[nextcord.Member, str], msg: nextcord.Message
) -> nextcord.Embed:
	if isinstance(target, str):
		target = memSearch(msg, target)  # type: ignore
	if target and not isinstance(target, str):
		# Discord occasionally reports people with an activity as
		# not having one; if so, go invisible and back online
		emb = (
			bbEmbed(
				value=target.activity.name if target.activity else "",  # type: ignore
				col=target.color
			)
			.set_author(name=target, icon_url=fetchAvatar(target))
			.set_thumbnail(url=fetchAvatar(target))
			.add_field(
				name="Registered for Discord on",
				value=truncTime(target) + " UTC"
			)
			.add_field(
				name="Joined this server on",
				value=str(target.joined_at)[:-10] + " UTC"
			)
		)
		if len(target.roles) > 1:
			# Every user has the "@everyone" role, so check
			# if they have more roles than that
			emb.add_field(
				name="Roles",
				value=", ".join(role.mention for role in target.roles[:0:-1]),
				inline=False
			)
			# Reverse target.roles in order to make them
			# display in decreasing order of power
	else:
		emb = invalidTargetEmbed
	return emb


def av(
	target: Union[nextcord.User, nextcord.Member, str], msg: nextcord.Message
) -> nextcord.Embed:
	if not msg.guild:
		target = msg.author
	elif isinstance(target, str):
		target = memSearch(msg, target)  # type: ignore
	if target and not isinstance(target, str):
		return (
			bbEmbed(col=target.color)
			.set_image(url=fetchAvatar(target))
			.set_author(name=target, icon_url=fetchAvatar(target))
		)
	return invalidTargetEmbed


def ctxCreatedThread(ctx: commands.Context) -> bool:
	"""
	Threads created with the name set to a command (e.g., a thread named !flip)
	will trigger that command as the first action in that thread. This is not
	intended behavior; as such, if the context event is a thread being created
	or a thread name being changed, this method will catch that.

	Args:
		ctx (commands.Context): The context in which the command is being invoked

	Returns:
		bool: Whether the event is valid to trigger a command.

	"""
	return ctx.message.type in (
		nextcord.MessageType.thread_created,
		nextcord.MessageType.channel_name_change
	)


class bbHelpCommand(commands.HelpCommand):
	async def send_bot_help(
		self, mapping: Dict[commands.Cog, List[commands.Command]]
	) -> int:
		if ctxCreatedThread(self.context):
			return -1
		if not self.context.guild:
			commandNum = 15
		elif self.context.author.guild_permissions.manage_messages:  # type: ignore
			commandNum = 20
		else:
			commandNum = 17
		commandList = (
			("!register", "Registers you with the currency system."),
			(
				"!balance [user/username]",
				"Display a user's balance. Write just !av"
				" if you want to see your own balance."
			),
			("!bucks", "Shows you an explanation for how BeardlessBucks work."),
			("!reset", "Resets you to 200 BeardlessBucks."),
			("!fact", "Gives you a random fun fact."),
			("!source", "Shows you the source of most facts used in !fact."),
			(
				"!flip [bet]",
				"Bets a certain amount on flipping a coin. Heads"
				" you win, tails you lose. Defaults to 10."
			),
			(
				"!blackjack [bet]",
				"Starts up a game of blackjack. Once you're in a"
				" game, you can use !hit and !stay to play."
			),
			(
				"!roll [count]d[num][+/-][mod]",
				"Rolls [count] [num]-sided dice and adds or subtracts [mod]."
				" Example: !roll d8, or !roll d100-17, or !roll 4d6+3."
			),
			("!brawl", "Displays Beardless Bot's Brawlhalla commands."),
			("!add", "Gives you a link to add this bot to your server."),
			(
				"!av [user/username]",
				"Display a user's avatar. Write just !av"
				" if you want to see your own avatar."
			),
			(
				"![animal name]",
				"Gets a random animal picture. See the"
				" list of animals with !animals."
			),
			("!define [word]", "Shows you the definition(s) of a word."),
			("!ping", "Checks Beardless Bot's latency."),
			(
				"!buy red/blue/pink/orange",
				"Removes 50k BeardlessBucks and grants you a special color role."
			),
			(
				"!info [user/username]",
				"Displays general information about a user."
				" Write just !info to see your own info."
			),
			("!purge [number]", "Mass-deletes messages."),
			(
				"!mute [target] [duration]",
				"Mutes someone for an amount of time."
				" Accepts either seconds, minutes, or hours."
			),
			("!unmute [target]", "Unmutes the target.")
		)
		emb = bbEmbed("Beardless Bot Commands")
		for commandPair in commandList[:commandNum]:
			emb.add_field(name=commandPair[0], value=commandPair[1])
		await self.get_destination().send(embed=emb)
		return 1

	async def send_error_message(self, error: str) -> None:
		# TODO: configure proper send_command_help, send_error_message
		return None


def scamCheck(text: str) -> bool:
	"""
	Check message content for common scam phrases.

	Args:
		text (str): The phrase to check

	Returns:
		bool: Whether the phrase is suspicious.

	"""
	msg = text.lower()
	checkOne = re.compile(r"^.*https?://d\w\wc\wr(d|t)\.\w{2,4}.*").match(msg)
	checkTwo = re.compile(r"^.*https?://d\w\wc\wr\wn\wtr\w\.\w{2,5}.*").match(msg)
	checkThree = re.compile(r"^.*(nitro|gift|@everyone).*").match(msg)
	checkFour = all((
		"http" in msg,
		"@everyone" in msg or "stym" in msg,
		any(("nitro" in msg, "discord" in msg, ".gift/" in msg)),
		any((
			"free" in msg,
			"airdrop" in msg,
			"gift" in msg,
			"left over" in msg,
			"discocl" in msg
		))
	))
	checkFive = re.compile(r"^.*https://discord.gift/.*").match(msg)

	return (
		((bool(checkOne) or bool(checkTwo)) and bool(checkThree)) or checkFour
	) and not bool(checkFive)


def onJoin(guild: nextcord.Guild, role: nextcord.Role) -> nextcord.Embed:
	return bbEmbed(
		f"Hello, {guild.name}!", joinMsg.format(guild.name, role.mention)
	).set_thumbnail(url=prof)


def search(searchterm: str = "") -> nextcord.Embed:
	return bbEmbed(
		"Search Results",
		"https://www.google.com/search?q=" + quote_plus(searchterm)
	).set_thumbnail(url=prof)


# The following Markov chain code was originally provided by CSTUY SHIP.
def tweet() -> str:
	with open("resources/eggtweets_clean.txt") as f:
		words = f.read().split()
	chains: Dict[str, List[str]] = {}
	keySize = randint(1, 2)
	for i in range(len(words) - keySize):
		if (key := " ".join(words[i:i + keySize])) not in chains:
			chains[key] = []
		chains[key].append(words[i + keySize])
	key = s = choice(list(chains.keys()))
	for _i in range(randint(10, 35)):
		word = choice(chains[key])
		s += " " + word
		key = (
			" ".join(key.split()[1:keySize + 1]) + " " + word
			if keySize > 1
			else word
		)
	return s[0].title() + s[1:]


def formattedTweet(eggTweet: str) -> str:
	# Removes the last piece of punctuation to create a more realistic tweet
	for i in range(len(eggTweet) - 1, -1, -1):
		if eggTweet[i] in (".", "!", "?"):
			return "\n" + eggTweet[:i]
	return "\n" + eggTweet


# Stock embeds:
# TODO: convert these to methods

reasons = (
	"Beardless Bot requires permissions in order to do just about anything."
	" Without them, I can't do much, so I'm leaving. If you add me back to"
	" this server, please make sure to leave checked the box that grants me"
	" the Administrator permission.\nIf you have any questions, feel free"
	" to contact my creator, Captain No-Beard#7511."
)

noPerms = bbEmbed(
	"I need admin perms!", reasons, 0xFF0000
).set_author(name="Beardless Bot", icon_url=prof)

addUrl = (
	"(https://discord.com/api/oauth2/authorize?client_id="
	"654133911558946837&permissions=8&scope=bot)"
)

inviteMsg = (
	bbEmbed(
		"Want to add this bot to your server?", "[Click this link!]" + addUrl
	)
	.set_thumbnail(url=prof)
	.add_field(
		name="If you like Beardless Bot...",
		inline=False,
		value="Please leave a review on [top.gg]"
		"(https://top.gg/bot/654133911558946837)."
	)
)

sparDesc = (
	"Do the command !spar [region] [other info]."
	"\nFor instance, to find a diamond from US-E to play 2s with, I would do:"
	"\n**!spar US-E looking for a diamond 2s partner**."
	"\nValid regions are US-E, US-W, BRZ, EU, JPN, AUS, SEA, MEA, SAF."
	"\n!spar has a 2 hour cooldown."
	"\nPlease use the roles channel to give yourself the correct roles."
)

sparPins = (
	bbEmbed("How to use this channel.")
	.add_field(
		name="To spar someone from your region:",
		value=sparDesc,
		inline=False
	)
	.add_field(
		name="If you don't want to get pings:",
		inline=False,
		value="Remove your region role. Otherwise, responding"
		" 'no' to calls to spar is annoying and counterproductive,"
		" and will earn you a warning."
	)
)

redditEmb = bbEmbed(
	"The Official Eggsoup Subreddit", "https://www.reddit.com/r/eggsoup/"
).set_thumbnail(url=redditThumb)


animals = bbEmbed("Animal Photo Commands:").add_field(
	name="!dog",
	value=(
		"Can also do !dog breeds to see breeds you"
		" can get pictures of with !dog [breed]"
	),
	inline=False
)
for animalName in animalList:
	animals.add_field(name="!" + animalName, value="_ _")

invalidTargetEmbed = bbEmbed(
	"Invalid target!",
	(
		"Please choose a valid target. Valid targets"
		" are either a ping or a username."
	),
	0xFF0000
)
