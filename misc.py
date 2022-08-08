# Beardless Bot miscellaneous methods

import re
from datetime import datetime
from random import choice, randint
from typing import Optional, Union
from urllib.parse import quote_plus

import discord
import requests
from bs4 import BeautifulSoup
from discord.ext import commands


diceMsg = (
	"Enter !d[number][+/-][modifier] to roll a [number]-sided die and"
	" add or subtract a modifier. For example: !d8+3, or !d100-17, or !d6."
)

prof = (
	"https://cdn.discordapp.com/attachments/613030322644451349/"
	"947434005878435910/CapGift.jpg"
)

animalList = (
	"cat",
	"duck",
	"fox",
	"rabbit",
	"panda",
	"lizard",
	"frog",
	"axolotl",
	"bear",
	"zoo",
	"bird",
	"koala",
	"raccoon",
	"kangaroo"
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


def truncTime(member: Union[discord.User, discord.Member]) -> str:
	return str(member.created_at)[:-7]


# Wrapper for discord.Embed.init() that defaults to
# commonly-used values and is easier to call
def bbEmbed(
	name: str = "",
	value: str = "",
	col: int = 0xFFF994,
	showTime: bool = False
) -> discord.Embed:
	return discord.Embed(
		title=name,
		description=value,
		color=col,
		timestamp=datetime.utcnow() if showTime else discord.Embed.Empty
	)


def memSearch(
	message: discord.Message, target: str
) -> Optional[discord.Member]:
	"""
	User lookup helper method. Finds user based on
	username and/or discriminator (#1234).
	Runs in linear time; worst case, does not find a
	loosely-matching target, takes O(n) operations
	"""
	term = str(target).lower()
	semiMatch = looseMatch = None
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


def animal(animalType: str, breed: Optional[str] = None) -> str:
	r = "Invalid Animal"

	if "moose" in (animalType, breed):
		r = requests.get("https://github.com/LevBernstein/moosePictures/")
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
		for i in range(10):
			# Dog API has been throwing 522 errors
			if not breed:
				r = requests.get("https://dog.ceo/api/breeds/image/random")
				if r.status_code == 200:
					return r.json()["message"]
			elif breed.startswith("breeds"):
				r = requests.get("https://dog.ceo/api/breeds/list/all")
				if r.status_code == 200:
					return "Dog breeds: {}.".format(
						", ".join(dog for dog in r.json()["message"])
					)
			elif breed.isalpha():
				r = requests.get(
					"https://dog.ceo/api/breed/" + breed + "/images/random"
				)
				if r.status_code == 200:
					if not r.json()["message"].startswith("Breed not found"):
						return r.json()["message"]
				return "Breed not found! Do !dog breeds to see all breeds."
			else:
				return "Breed not found! Do !dog breeds to see all breeds."

	elif animalType == "cat":
		# Cat API has been throwing 503 errors every other call,
		# likely due to rate limiting
		for i in range(10):
			# The loop is to try to make another request if one pulls a 503.
			r = requests.get("https://aws.random.cat/meow")
			if r.status_code == 200:
				return r.json()["file"]

	elif animalType in ("bunny", "rabbit"):
		r = requests.get("https://api.bunnies.io/v2/loop/random/?media=gif")
		if r.status_code == 200:
			return r.json()["media"]["gif"]

	elif animalType in ("panda", "koala", "bird", "raccoon", "kangaroo", "fox"):
		if animalType == "fox":
			r = requests.get("https://randomfox.ca/floof/")
		else:
			r = requests.get(
				"https://some-random-api.ml/animal/" + animalType
			)
		if r.status_code == 200:
			return r.json()["image"]

	elif animalType in ("duck", "lizard"):
		if animalType == "duck":
			r = requests.get("https://random-d.uk/api/quack")
		else:
			r = requests.get("https://nekos.life/api/v2/img/lizard")
		if r.status_code == 200:
			return r.json()["url"]

	elif animalType == "zoo":
		r = requests.get("https://zoo-animal-api.herokuapp.com/animals/rand")
		return r.json()["image_link"]

	elif animalType == "bear":
		return f"https://placebear.com/{randint(200, 400)}/{randint(200,400)}"

	elif animalType == "frog":
		r = requests.get("https://github.com/a9-i/frog/tree/main/ImgSetOpt")
		soup = BeautifulSoup(r.content.decode("utf-8"), "html.parser")
		frog = choice(
			tuple(f for f in soup.stripped_strings if f.endswith(".jpg"))
		)

		return (
			"https://raw.githubusercontent.com/"
			f"a9-i/frog/main/ImgSetOpt/{frog}"
		)

	if animalType == "axolotl":
		r = requests.get("https://axoltlapi.herokuapp.com/").json()["url"]
		if not r.startswith("404"):
			return r

	raise Exception(str(r) + ": " + animalType)


def define(word: str) -> discord.Embed:
	r = requests.get(
		"https://api.dictionaryapi.dev/api/v2/entries/en_US/" + word
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
	return bbEmbed("Beardless Bot Definitions", "No results found.")


def roll(text: str) -> Optional[int]:
	# Takes a string of the format dn+b and rolls one
	# n-sided die with a modifier of b. Modifier is optional.
	try:
		command = text.split("d", 1)[1]
	except IndexError:
		return None
	modifier = -1 if "-" in command else 1
	for side in "4", "6", "8", "100", "10", "12", "20":
		if command.startswith(side):
			if len(command) > len(side) and command[len(side)] in ("+", "-"):
				b = modifier * int(command[1 + len(side):])
				return randint(1, int(side)) + b
			return randint(1, int(side)) if command == side else None
	return None


def rollReport(
	text: str,
	author: Union[discord.User, discord.Member]
) -> discord.Embed:
	if (result := roll(text.lower())) is not None:
		report = f"You got {result}, {author.mention}."
	else:
		report = (
			"Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100,"
			" as well as modifiers. No spaces allowed. Ex: !roll d4+3"
		)
	return bbEmbed("Beardless Bot Dice", report)


def fact() -> str:
	with open("resources/facts.txt", "r") as f:
		return choice(f.read().splitlines())


def info(target: discord.Member, msg: discord.Message) -> discord.Embed:
	if not isinstance(target, discord.User):
		target = memSearch(msg, target)
	if target:
		# Discord occasionally reports people with an activity as
		# not having one; if so, go invisible and back online
		emb = (
			bbEmbed(
				value=target.activity.name if target.activity else "",
				col=target.color
			)
			.set_author(name=target, icon_url=target.avatar_url)
			.set_thumbnail(url=target.avatar_url)
			.add_field(
				name="Registered for Discord on",
				value=truncTime(target) + " UTC"
			)
			.add_field(
				name="Joined this server on",
				value=str(target.joined_at)[:-7] + " UTC"
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


def av(target: discord.Member, msg: discord.Message) -> discord.Embed:
	if not isinstance(target, discord.Member):
		target = memSearch(msg, target)
	if target:
		return (
			bbEmbed(col=target.color)
			.set_image(url=target.avatar_url)
			.set_author(name=target, icon_url=target.avatar_url)
		)
	return invalidTargetEmbed


def bbCommands(ctx: commands.Context) -> discord.Embed:
	emb = bbEmbed("Beardless Bot Commands")
	if not ctx.guild:
		commandNum = 15
	elif ctx.author.guild_permissions.manage_messages:
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
			"!roll d[num][+/-][mod]",
			"Rolls a [num]-sided die and adds or subtracts [mod]."
			" Example: !roll d8, or !roll d100-17."
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
	for commandPair in commandList[:commandNum]:
		emb.add_field(name=commandPair[0], value=commandPair[1])
	return emb


def hints() -> discord.Embed:
	with open("resources/hints.txt", "r") as f:
		hints = f.read().splitlines()
	emb = bbEmbed("Hints for Beardless Bot's Secret Word")
	for i in range(len(hints)):
		emb.add_field(name=i + 1, value=hints[i])
	return emb


def scamCheck(text: str) -> bool:
	msg = text.lower()
	checkOne = re.compile(r"^.*https?://d\w\wc\wr(d|t)\.\w{2,4}.*")
	checkTwo = re.compile(r"^.*(nitro|gift|@everyone).*")
	checkThree = re.compile(r"^.*https?://d\w\wc\wr\wn\wtr\w\.\w{2,5}.*")
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
	checkFive = re.compile(r"^.*https://discord.gift/.*")

	return (
		(
			(
				bool(checkOne.match(msg)) or bool(checkThree.match(msg))
			) and bool(checkTwo.match(msg))
		) or checkFour
	) and not bool(checkFive.match(msg))


def onJoin(guild: discord.Guild, role: discord.Role) -> discord.Embed:
	return bbEmbed(
		f"Hello, {guild.name}!", joinMsg.format(guild.name, role.mention)
	).set_thumbnail(url=prof)


def search(searchterm: str = "") -> discord.Embed:
	try:
		emb = bbEmbed(
			"Search Results",
			"https://www.google.com/search?q=" + quote_plus(searchterm)
		)
	except TypeError:
		emb = bbEmbed("Invalid Search!", "Please enter a valid search term.")
	return emb.set_thumbnail(url=prof)


# The following Markov chain code was originally provided by CSTUY SHIP.
def tweet() -> str:
	with open("resources/eggtweets_clean.txt", "r") as f:
		words = f.read().split()
	chains = {}
	keySize = randint(1, 2)
	for i in range(len(words) - keySize):
		if (key := " ".join(words[i:i + keySize])) not in chains:
			chains[key] = []
		chains[key].append(words[i + keySize])
	key = s = choice(list(chains.keys()))
	for i in range(randint(10, 35)):
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
	"\nValid regions are US-E, US-W, BRZ, EU, JPN, AUS, SEA."
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

redditEmb = (
	bbEmbed(
		"The Official Eggsoup Subreddit",
		"https://www.reddit.com/r/eggsoup/"
	)
	.set_thumbnail(url=redditThumb)
)

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
