"""Beardless Bot miscellaneous methods."""

import logging
import random
import re
from collections.abc import Mapping
from datetime import datetime
from json import loads
from pathlib import Path
from typing import Any, Final, override
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import httpx
import nextcord
from bs4 import BeautifulSoup
from nextcord.ext import commands
from nextcord.utils import get

logger = logging.getLogger(__name__)

MaxMsgLength: Final[int] = 1024
MaxEmbedFields: Final[int] = 25
Ok: Final[int] = 200
BadRequest: Final[int] = 404
BbColor: Final[int] = 0xFFF994
BbId: Final[int] = 654133911558946837
LogChannelName: Final[str] = "bb-log"
SparChannelName: Final[str] = "looking-for-spar"
TimeZone = ZoneInfo("America/New_York")

ProfUrl = (
	"https://cdn.discordapp.com/attachments/61303032"
	"2644451349/947434005878435910/CapGift.jpg"
)

AnimalList = (
	"cat", "duck", "fox", "seal", "rabbit", "lizard", "frog", "bear",
)

HierarchyMsg = (
	"It looks like I don't have permission to modify that user's roles!"
	" Raise my place in the role hierarchy, please."
)

Naughty = "You do not have permission to use this command, {}."

Greetings = (
	"How ya doin'?",
	"Yo!",
	"What's cookin?",
	"Hello!",
	"Ahoy!",
	"Hi!",
	"What's up?",
	"Hey!",
	"How's it goin'?",
	"Greetings!",
	"Howdy!",
	"G'day!",
)

SparDesc = (
	"Do the command !spar [region] [other info]."
	"\nFor instance, to find a diamond from US-E to play 2s with, I would do:"
	"\n**!spar US-E looking for a diamond 2s partner**."
	"\nValid regions are US-E, US-W, BRZ, EU, JPN, AUS, SEA, MEA, SAF."
	"\n!spar has a 2 hour cooldown."
	"\nPlease use the roles channel to give yourself the correct roles."
)

BearRootUrl = "https://placebear.com/{}/{}"
FrogRootUrl = "https://raw.githubusercontent.com/a9-i/frog/main/ImgSetOpt/"
SealRootUrl = "https://focabot.github.io/random-seal/seals/{}.jpg"

BotContext = commands.Context[commands.Bot]

TargetTypes = str | nextcord.User | nextcord.Member

MuteTimeConversion = {
	"day": 86400.0,
	"hour": 3600.0,
	"minute": 60.0,
	"second": 1.0,
}


def bb_embed(
	name: str = "",
	value: str = "",
	col: int | nextcord.Color = BbColor,
	*,
	show_time: bool = False,
) -> nextcord.Embed:
	"""
	nextcord.Embed wrapper.

	Act as a wrapper for nextcord.Embed that defaults to commonly used-values
	and is easier to call.

	Args:
		name (str): The title of the Embed (default is "")
		value (str): The description of the Embed (default is "")
		col (int | nextcord.Color): The color of the Embed (default is BbColor)
		show_time (bool): Whether to display the timestamp at the time of
			the Embed's creation (default is False)

	Returns:
		nextcord.Embed: The created Embed.

	"""
	return nextcord.Embed(
		title=name,
		description=value,
		color=col,
		timestamp=datetime.now(TimeZone) if show_time else None,
	)


def content_check(message: nextcord.Message, offset: int = 0) -> str:
	"""
	Check if a message contains any valid text content.

	Embed fields have a length limit of 1024 characters. This can lead to
	problems when logging message edit/deletion and displaying the content of
	those messages. As such, check if the content, including any additional
	information that needs to be displayed, exceeds 1024 characters in length.
	In addition, if the message length is 0, report that the message iactually
	contains an instance of nextcord.Embed, and therefore has no text content.

	Args:
		message (nextcord.Message): The message to check
		offset (int): The additional message length to account for; this is
			subtracted from MaxMsgLength to get the actual allowable message
			length (default is 0)

	Returns:
		str: The content to report, if it would be valid to do so.

	"""
	if message.content:
		if len(message.content) > max(
			min(MaxMsgLength - offset, MaxMsgLength), 0,
		):
			return f"**Message length exceeds {MaxMsgLength} characters.**"
		return message.content
	return "**Embed**"


def log_exception(e: Exception, ctx: BotContext) -> None:
	"""
	Act as a wrapper for logging.error to help with debugging.

	Args:
		e (Exception): The exception to log
		ctx (botContext): The command invocation context

	"""
	logger.error(
		"%s Command: %s; Author: %s; Content: %s; Guild: %s; Type: %s",
		e,
		ctx.invoked_with,
		ctx.author,
		content_check(ctx.message),
		ctx.guild,
		type(e),
	)


async def create_muted_role(guild: nextcord.Guild) -> nextcord.Role:
	"""
	Create a "Muted" role that prevents users from sending messages.

	Args:
		guild (nextcord.Guild): The guild in which to create the role

	Returns:
		nextcord.Role: The Muted role.

	"""
	if (role := get(guild.roles, name="Muted")) is not None:
		return role

	overwrite = nextcord.PermissionOverwrite(send_messages=False)
	# TODO: Add error handling for role creation, set_permissions
	role = await guild.create_role(
		name="Muted",
		colour=nextcord.Colour(0x818386),
		mentionable=False,
		permissions=nextcord.Permissions(
			send_messages=False,
			read_messages=True,
			send_messages_in_threads=False,
		),
		reason="BB Muted Role",
	)
	for channel in guild.channels:
		await channel.set_permissions(
			role,
			overwrite=overwrite,
			reason="Preventing Muted users from chatting in this channel",
		)
	return role


def member_search(
	message: nextcord.Message, target: str,
) -> nextcord.Member | None:
	"""
	User lookup helper method.

	Finds user based on username and/or discriminator (#1234).
	Runs in linear time; worst case, does not find a loosely-matching target,
	takes O(n) operations.

	Args:
		message (nextcord.Message): The message that invoked this command
		target (str): The target of the search. Ideally a username

	Returns:
		nextcord.Member or None: A matching user, if one can be found.

	"""
	term = str(target).lower()
	match = loose_match = None
	assert message.guild is not None
	for member in message.guild.members:
		if term == str(member).lower() or term == str(member.id):
			# Exact match
			return member
		if term == member.name.lower():
			if "#" not in term:
				return member
			match = member
		if (
			(member.nick and term == member.nick.lower() and not match)
			or (not (match or loose_match) and term in member.name.lower())
		):
			loose_match = member
	return match or loose_match


def get_log_channel(guild: nextcord.Guild) -> nextcord.TextChannel | None:
	"""
	LogChannelName channel lookup helper method.

	Return the first TextChannel with the name of LogChannelName if one exists.

	Args:
		guild (nextcord.Guild): The guild to search

	Returns:
		nextcord.TextChannel or None: The log channel if it exists;
			else, None.

	"""
	channels = [c for c in guild.text_channels if c.name == LogChannelName]
	return channels[0] if channels else None


def fetch_avatar(
	user: nextcord.Member | nextcord.User | nextcord.ClientUser,
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
	if user.avatar is not None:
		return user.avatar.url
	return user.default_avatar.url


class AnimalException(httpx.RequestError):
	"""Exception raised when an Animal API call fails."""

	def __init__(self, *, animal: str) -> None:
		"""
		httpx.RequestError wrapper.

		Call super().__init__ with an Exception message based on whatever
		animal API call has failed.

		Args:
			animal (str): The animal API call that has failed

		"""
		super().__init__(f"Failed to call {animal.title()} Animal API")


async def fetch_animal(url: str, *args: str | int) -> str | None:
	async with httpx.AsyncClient(timeout=10) as client:
		r = await client.get(url)
	if r.status_code == Ok:
		j = r.json()
		for arg in args:
			assert callable(j.pop)
			j = j.pop(arg)
		assert isinstance(j, str)
		return j
	return None


async def get_moose() -> str:
	async with httpx.AsyncClient(timeout=10) as client:
		r = await client.get("https://github.com/LevBernstein/moosePictures/")
	if r.status_code == Ok:
		soup = BeautifulSoup(r.content.decode("utf-8"), "html.parser")
		moose = random.choice(
			tuple(
				m for m in soup.stripped_strings
				if m.startswith("moose") and m.endswith(".jpg")
			),
		)

		return (
			"https://raw.githubusercontent.com/"
			f"LevBernstein/moosePictures/main/{moose}"
		)
	raise AnimalException(animal="moose")


async def get_dog(breed: str | None = None) -> str:
	if not breed:
		if isinstance(
			message := await fetch_animal(
				"https://dog.ceo/api/breeds/image/random", "message",
			), str,
		):
			return message
	elif breed == "moose":
		return await get_moose()
	elif breed.startswith("breed"):
		async with httpx.AsyncClient(timeout=10) as client:
			r = await client.get("https://dog.ceo/api/breeds/list/all")
		if r.status_code == Ok:
			return "Dog breeds: {}.".format(
				", ".join(dog for dog in r.json()["message"]),
			)
	elif breed.isalpha() and isinstance(
		message := await fetch_animal(
			f"https://dog.ceo/api/breed/{breed}/images/random", "message",
		), str,
	):
		return message
	else:
		return "Breed not found! Do !dog breeds to see all breeds."
	raise AnimalException(animal="dog")


def get_frog_list() -> list[str]:
	"""
	Get a list of filenames of frog images.

	On some requests, formatting fails, resulting in a KeyError when trying to
	find the payload key within the json body of a particular script tag.
	When that happens, massage the response a bit so that the proper payload
	can be located.

	Amortize the cost of pulling the frog images by making just one initial
	call within misc.py.

	Returns:
		list[str]: A list of frog image filenames.

	"""
	r = httpx.get(
		"https://github.com/a9-i/frog/tree/main/ImgSetOpt", timeout=10,
	)
	soup = BeautifulSoup(r.content.decode("utf-8"), "html.parser")
	try:
		j = loads(soup.find_all("script")[-1].text)["payload"]
	except KeyError:
		j = loads(
			soup.find_all("script")[-2].text.replace("\\", "\\\\"),
		)["payload"]
	return [i["name"] for i in j["tree"]["items"]]


FrogList = get_frog_list()


async def get_animal(animal_type: str) -> str:
	url: str | None = None

	if animal_type == "bear":
		url = BearRootUrl.format(
			random.randint(200, 400), random.randint(200, 400),
		)

	elif animal_type == "frog":
		url = FrogRootUrl + random.choice(FrogList)

	elif animal_type == "seal":
		url = SealRootUrl.format(str(random.randint(0, 83)).rjust(4, "0"))

	elif animal_type == "cat":
		url = await fetch_animal(
			"https://api.thecatapi.com/v1/images/search", 0, "url",
		)

	elif animal_type in {"bunny", "rabbit"}:
		url = await fetch_animal(
			"https://api.bunnies.io/v2/loop/random/?media=gif", "media", "gif",
		)

	elif animal_type == "fox":
		url = await fetch_animal("https://randomfox.ca/floof/", "image")

	elif animal_type == "duck":
		return "https://random-d.uk/api/randomimg"

	elif animal_type == "lizard":
		url = await fetch_animal(
			"https://nekos.life/api/v2/img/lizard", "url",
		)

	else:
		raise ValueError("Invalid Animal: " + animal_type)

	if isinstance(url, str):
		return url
	raise AnimalException(animal=animal_type)


async def define(word: str) -> nextcord.Embed:
	async with httpx.AsyncClient(timeout=10) as client:
		r = await client.get(
			"https://api.dictionaryapi.dev/api/v2/entries/en_US/" + word,
		)
	if r.status_code == Ok:
		j = r.json()
		p = j[0]["phonetics"]
		desc = (
			f"Audio: {p[0]["audio"]}"
			if p and "audio" in p[0] and p[0]["audio"]
			else ""
		)
		emb = bb_embed(j[0]["word"].upper(), desc)
		i = 0
		for entry in j:
			for meaning in entry["meanings"]:
				for definition in meaning["definitions"]:
					if i >= MaxEmbedFields:
						break
					i += 1
					emb.add_field(
						name=f"Definition {i}:",
						value=definition["definition"],
					)
		return emb
	if r.status_code == BadRequest:
		return bb_embed("Beardless Bot Definitions", "No results found.")
	return bb_embed(
		"Beardless Bot Definitions",
		"There was an error with the dictionary API. Please ping my creator.",
	)


def roll(text: str) -> tuple[int, int, str, bool, int] | None:
	"""
	Convert a roll message into a dice roll.

	Take a string of the format mdn+/-b and roll m n-sided dice with a modifier
	of b added to the final result. m and b are optional. b can be negative.

	Args:
		text (str): The roll string to process

	Returns:
		tuple[int, int, str, bool, int] | None: None if the roll failed due
		to invalid input; otherwise, a tuple with five elements:
				int: The total roll, with modifier (b) included
				int: The number of dice rolled (m), up to 999
				str: The number of sides (n) each rolled die has
				bool: Whether the modifier was negative
				int: The modifier
			This tuple is designed to be processed into a readable string
			by rollReport().

	"""
	number_of_dice: str | int
	try:
		number_of_dice, command = text.split("d", 1)
	except (IndexError, ValueError):
		return None
	number_of_dice = (
		abs(int(number_of_dice))
		if number_of_dice.replace("-", "").isnumeric()
		else 1
	)
	number_of_dice = min(number_of_dice, 999)
	valid_sides = {"4", "6", "8", "100", "10", "12", "20"}
	if (side := command.split("-")[0].split("+")[0]) in valid_sides:
		if (
			command != side
			and command[len(side)] in {"+", "-"}
			and (bonus := command[1 + len(side):]).isnumeric()
		):
			modifier = (-1 if "-" in command else 1) * min(int(bonus), 999999)
		else:
			modifier = 0
		dice_sum = sum(
			random.randint(1, int(side)) for i in range(number_of_dice)
		)
		return (
			dice_sum + modifier,
			number_of_dice,
			side,
			"-" in command,
			modifier,
		)
	return None


def roll_report(
	text: str, author: nextcord.User | nextcord.Member,
) -> nextcord.Embed:
	if (result := roll(text.lower())) is not None:
		modifier = "" if result[3] else "+"
		title = f"Rolling {result[1]}d{result[2]}{modifier}{result[4]}"
		report = f"You got {result[0]}, {author.mention}."
	else:
		title = "Beardless Bot Dice"
		report = (
			"Invalid roll. Enter d4, 6, 8, 10, 12, 20, or 100, as well as"
			" number of dice and modifiers. No spaces allowed. Ex: !roll 2d4+3"
		)
	return bb_embed(title, report)


def fact() -> str:
	"""
	Pull a random fun fact from resources/facts.txt.

	Returns:
		str: A fun fact.

	"""
	with Path("resources/facts.txt").open("r", encoding="UTF-8") as f:
		return random.choice(f.read().splitlines())


def truncate_time(member: nextcord.User | nextcord.Member) -> str:
	return str(member.created_at)[:-10]


def info(
	target: nextcord.Member | str, msg: nextcord.Message,
) -> nextcord.Embed:
	member = member_search(msg, target) if isinstance(target, str) else target
	if member and not isinstance(member, str):
		# Discord occasionally reports people with an activity as
		# not having one; if so, go invisible and back online
		activity = (
			member.activity.name
			if member.activity and member.activity.name
			else ""
		)
		emb = bb_embed(
			value=activity, col=member.color,
		).set_author(
			name=member.name, icon_url=fetch_avatar(member),
		).set_thumbnail(
			url=fetch_avatar(member),
		).add_field(
			name="Registered for Discord on",
			value=truncate_time(member) + " UTC",
		).add_field(
			name="Joined this server on",
			value=str(member.joined_at)[:-10] + " UTC",
		)
		if len(member.roles) > 1:
			# Every user has the "@everyone" role, so check
			# if they have more roles than that
			emb.add_field(
				name="Roles",
				value=", ".join(role.mention for role in member.roles[:0:-1]),
				inline=False,
			)
			# Reverse member.roles in order to make them
			# display in decreasing order of power
	else:
		emb = InvalidTargetEmbed
	return emb


def avatar(
	target: nextcord.User | nextcord.Member | str, msg: nextcord.Message,
) -> nextcord.Embed:
	member: nextcord.User | nextcord.Member | str | None
	if not msg.guild:
		member = msg.author
	elif isinstance(target, str):
		member = member_search(msg, target)
	else:
		member = target
	if member and not isinstance(member, str):
		return bb_embed(
			col=member.color,
		).set_image(url=fetch_avatar(member)).set_author(
			name=member.name, icon_url=fetch_avatar(member),
		)
	return InvalidTargetEmbed


def ctx_created_thread(ctx: BotContext) -> bool:
	"""
	Check if a thread creation triggers a command.

	Threads created with the name set to a command (e.g., a thread named !flip)
	will trigger that command as the first action in that thread. This is not
	intended behavior; as such, if the context event is a thread being created
	or a thread name being changed, this method will catch that.

	Args:
		ctx (botContext): The context in which the command is being invoked

	Returns:
		bool: Whether the event is valid to trigger a command.

	"""
	return ctx.message.type in {
		nextcord.MessageType.thread_created,
		nextcord.MessageType.channel_name_change,
	}


class BbHelpCommand(commands.HelpCommand):
	"""Nextcord !help command handler."""

	@override
	def __init__(self) -> None:
		"""
		Call the HelpCommand constructor with an extra alias.

		This is just for the sake of not having to pass extra arguments to
		the HelpCommand in the commands.Bot constructor.

		"""
		super().__init__(command_attrs={"aliases": ["commands"]})

	# TODO: configure proper send_command_help, send_error_message
	@override
	async def send_bot_help(
		self,
		_mapping: Mapping[
			commands.Cog | None, list[commands.core.Command[Any, Any, Any]],
		],
	) -> None:
		if ctx_created_thread(self.context):
			return
		if not self.context.guild:
			commands_to_display = 15
		elif (
			hasattr(self.context.author, "guild_permissions")
			and self.context.author.guild_permissions.manage_messages
		):
			commands_to_display = 20
		else:
			commands_to_display = 17
		command_list = (
			("!register", "Registers you with the currency system."),
			(
				"!balance [user/username]",
				"Display a user's balance. Write just !av"
				" if you want to see your own balance.",
			),
			(
				"!bucks",
				"Shows you an explanation for how BeardlessBucks work.",
			),
			("!reset", "Resets you to 200 BeardlessBucks."),
			("!fact", "Gives you a random fun fact."),
			("!source", "Shows you the source of most facts used in !fact."),
			(
				"!flip [bet]",
				"Bets a certain amount on flipping a coin. Heads"
				" you win, tails you lose. Defaults to 10.",
			),
			(
				"!blackjack [bet]",
				"Starts up a game of blackjack. Once you're in a"
				" game, you can use !hit and !stay to play.",
			),
			(
				"!roll [count]d[num][+/-][mod]",
				"Rolls [count] [num]-sided dice and adds or subtracts [mod]."
				" Example: !roll d8, or !roll d100-17, or !roll 4d6+3.",
			),
			("!brawl", "Displays Beardless Bot's Brawlhalla commands."),
			("!add", "Gives you a link to add this bot to your server."),
			(
				"!av [user/username]",
				"Display a user's avatar. Write just !av"
				" if you want to see your own avatar.",
			),
			(
				"![animal name]",
				"Gets a random animal picture. See the"
				" list of animals with !animals.",
			),
			("!define [word]", "Shows you the definition(s) of a word."),
			("!ping", "Checks Beardless Bot's latency."),
			(
				"!buy red/blue/pink/orange",
				"Removes 50k BeardlessBucks and"
				" grants you a special color role.",
			),
			(
				"!info [user/username]",
				"Displays general information about a user."
				" Write just !info to see your own info.",
			),
			("!purge [number]", "Mass-deletes messages."),
			(
				"!mute [target] [duration]",
				"Mutes someone for an amount of time."
				" Accepts either seconds, minutes, or hours.",
			),
			("!unmute [target]", "Unmutes the target."),
		)
		emb = bb_embed("Beardless Bot Commands")
		for command, description in command_list[:commands_to_display]:
			emb.add_field(name=command, value=description)
		await self.get_destination().send(  # type: ignore[no-untyped-call]
			embed=emb,
		)

	@override
	async def send_error_message(self, error: str) -> None:
		"""
		Non-existent command inovcation handler.

		Log an error when a user tries to view the help information for a
		command that does not exist, e.g. !help foobar.

		Args:
			error (str): The name of the non-existent command that was
				attempted to be called

		"""
		logger.error("No command %s", error)


def scam_check(text: str) -> bool:
	"""
	Check message content for common scam phrases.

	Args:
		text (str): The phrase to check

	Returns:
		bool: Whether the phrase is suspicious.

	"""
	msg = text.lower()
	suspicious_link = bool(
		re.compile(
			r"^.*https?://d\w\wc\wr(\wn\wtr\w\.\w{2,5}|(d|t)\.\w{2,4}).*",
		).match(msg),
	)
	keywords = bool(re.compile(r"^.*(nitro|gift|@everyone).*").match(msg))
	bulk_keywords = all((
		"http" in msg,
		"@everyone" in msg or "stym" in msg,
		any(("nitro" in msg, "discord" in msg, ".gift/" in msg)),
		any((
			"free" in msg,
			"airdrop" in msg,
			"gift" in msg,
			"left over" in msg,
			"discocl" in msg,
		)),
	))
	valid_gift = bool(re.compile(r"^.*https://discord.gift/.*").match(msg))

	return ((suspicious_link and keywords) or bulk_keywords) and not valid_gift


async def delete_scam_and_notify(message: nextcord.Message) -> None:
	"""
	Process a message that has been flagged as a scam.

	Delete a possible scam message, inform the user their account may have
	been compromised, mute the user, and inform server moderators about the
	possibly compromised account.

	Args:
		message (nextcord.Message): The message that has been flagged

	"""
	assert message.guild is not None
	logger.info(
		"Possible nitro scam detected in %s/%i",
		message.guild.name,
		message.guild.id,
	)

	role = await create_muted_role(message.guild)
	assert not isinstance(message.author, nextcord.User)
	await message.author.add_roles(role)

	await message.delete()
	await message.channel.send(
		"**Deleted possible nitro scam link. Alerting mods.**",
	)
	await message.author.send(
		"This is an automated message. You have sent a message that has been"
		f" identified as containing a scam nitro link in **{message.guild}**."
		" Your account may have been compromised. Please take the appropriate"
		" measures and be sure to reach out to an admin if you need help.",
	)

	assert hasattr(message.channel, "mention")
	scam_report = (
		f"Deleted possible scam nitro link sent by {message.author.mention}"
		f" in {message.channel.mention}.\nMessage content:\n{message.content}"
	)
	for channel in message.guild.text_channels:
		if channel.name in {"infractions", LogChannelName}:
			await channel.send(scam_report)


def on_join(guild: nextcord.Guild, role: nextcord.Role) -> nextcord.Embed:
	"""
	Send an explanatory message after joining a server.

	The message explains bb's basic functions and restrictions, as well as any
	further setup actions that should be taken.

	Args:
		guild (nextcord.Guild): The guild that has been joined
		role (nextcord.Role): Beardless Bot's default role in that server

	Returns:
		nextcord.Embed: An embed explaining important information.

	"""
	description = (
		f"Thanks for adding me to {guild.name}! There are a few things you"
		" can do to unlock my full potential.\nIf you want event logging,"
		f" make a channel named #{LogChannelName}.\nIf you want a"
		" region-based sparring system, make a channel named"
		f" #{SparChannelName}.\nIf you want special color roles, purchasable"
		" with BeardlessBucks, create roles named special"
		f" red/blue/orange/pink.\nDon't forget to move my {role.mention} role"
		" up to the top of the role hierarchy in order to allow me to"
		" moderate all users."
	)
	return bb_embed(
		f"Hello, {guild.name}!", description,
	).set_thumbnail(url=ProfUrl)


def search(searchterm: str = "") -> nextcord.Embed:
	"""
	Google something.

	Useful for when people can't seem to realize that they have the power to
	Google things themselves.

	Args:
		searchterm (str): The term to search via Google (default is "")

	Returns:
		nextcord.Embed: An embed containing a link to the search results.

	"""
	return bb_embed(
		"Search Results",
		"https://www.google.com/search?q=" + quote_plus(searchterm),
	).set_thumbnail(url=ProfUrl)


def tweet() -> str:
	"""
	Generate a tweet using a Markov text generator.

	The tweet resembles one by eggsoup. The generator uses a collection of
	eggsoup tweets scraped from Twitter and massaged to be easily parsable.

	Because of the small size of the collection of actual tweets, the
	generated tweets are usually neither semantically nor syntactically valid.

	The below Markov code was originally provided by CSTUY SHIP for use in
	another project; I have since migrated it to Python3 and made various
	other improvements, including adding type annotations, the walrus
	operator, the ternary operator, and other simplification.

	Returns:
		str: A fake eggsoup tweet.

	"""
	with Path("resources/eggtweets_clean.txt").open(
		"r", encoding="UTF-8",
	) as f:
		words = f.read().split()
	chains: dict[str, list[str]] = {}
	key_size = random.randint(1, 2)
	for i in range(len(words) - key_size):
		if (key := " ".join(words[i:i + key_size])) not in chains:
			chains[key] = []
		chains[key].append(words[i + key_size])

	key = s = random.choice(list(chains.keys()))
	for _ in range(random.randint(10, 35)):
		word = random.choice(chains[key])
		s += " " + word
		key = (
			(" ".join(key.split()[1:key_size + 1]) + " ")
			if key_size > 1
			else ""
		) + word
	return s[0].title() + s[1:]


def format_tweet(egg_tweet: str) -> str:
	"""
	Remove the last piece of punctuation to create a more realistic tweet.

	Args:
		egg_tweet (str): The tweet to format

	Returns:
		str: The formatted tweet.

	"""
	for i in range(len(egg_tweet) - 1, -1, -1):
		if egg_tweet[i] in {".", "!", "?"}:
			return "\n" + egg_tweet[:i]
	return "\n" + egg_tweet


def get_last_numeric_char(duration: str) -> int:
	"""
	Find the last numeric character in a string. For use in Bot.cmdMute.

	Args:
		duration (str): The string to check

	Returns:
		int: The position of the last numeric character in the string
			(beginning indexing at 1). If a numeric character cannot be found,
			return 0. This is a bit hacky, but results in sanitized user input
			for cmdMute.

	"""
	for i, c in enumerate(duration):
		if not c.isnumeric():
			return i
	return len(duration)


async def process_mute_target(
	ctx: BotContext, target: str | None, bot: commands.Bot,
) -> nextcord.Member | None:
	# TODO: unit test
	# https://github.com/LevBernstein/BeardlessBot/issues/47
	assert hasattr(ctx.author, "guild_permissions")
	if not ctx.author.guild_permissions.manage_messages:
		await ctx.send(Naughty.format(ctx.author.mention))
		return None
	if not target:
		await ctx.send(f"Please specify a target, {ctx.author.mention}.")
		return None
	try:
		mute_target = await commands.MemberConverter().convert(ctx, target)
	except commands.MemberNotFound:
		await ctx.send(embed=bb_embed(
			"Beardless Bot Mute",
			"Invalid target! Target must be a mention or user ID.",
		))
		return None
	if bot.user is not None and mute_target.id == bot.user.id:
		await ctx.send("I am too powerful to be muted. Stop trying.")
		return None
	return mute_target


def process_mute_duration(
	duration: str | None, additional: str,
) -> tuple[str | None, str, float | None]:
	"""
	Process user-provided mute input.

	Convert the input in the form of duration and additional in order to
	extract the actual mute time, reason, and mute time in seconds.

	Args:
		duration (str | None): The main string arg that contains the mute time
			in the form xy, where x is an integer and y is a valid time span
			in the keys of MuteTimeConversion
		additional (str): The remaining string portion of the user input,
			possibly containing the reason for the mute action

	Returns:
		tuple[str | None, str, float | None]: A tuple containing:
			str | None: The processed duration if it exists; else, None
			str: The mute reason if it exists; else, an empty string
			float | None: The actual mute duration, in seconds, if it exists;
				else, None.

	"""
	mute_time = None
	if duration:
		duration = duration.lower()
		if (last_numeric_char := get_last_numeric_char(duration)) != 0:
			unit = duration[last_numeric_char:]
			for key, value in MuteTimeConversion.items():
				# Check for first char, whole word, plural
				if unit in {key[0], key, key + "s"}:
					duration = duration[:last_numeric_char]  # the numeric part
					mute_time = float(duration) * value
					duration += " " + key + ("" if duration == "1" else "s")
					break
		if last_numeric_char == 0 or mute_time is None:
			# treat duration as mute reason
			additional = duration + " " + additional
			duration = None
	return duration, additional.strip(), mute_time


def get_target(ctx: BotContext, target: str) -> TargetTypes:
	"""
	Parse the command context and the target arg for the most valid target.

	Args:
		ctx (BotContext): The command invocation context
		target (str): The user-provided argument pointing to a target

	Returns:
		TargetTypes: A mentioned User/Member, if one exists; else, the
			user-provided target if one was given (target != ""); else, the
			user who is responsible for the invocation of the command.

	"""
	# TODO: refactor to call member_search.
	return (
		ctx.message.mentions[0]
		if ctx.message.mentions
		else target or ctx.author
	)


async def check_for_spar_channel(ctx: BotContext) -> bool:
	"""
	Check if the spar command has been invoked in the sparring channel.

	If so, send an informative embed explaining how to use the channel.

	Args:
		ctx (BotContext): The command invocation context

	Returns:
		bool: Whether the context was invoked in the sparring channel.

	"""
	if hasattr(ctx.channel, "name") and ctx.channel.name == SparChannelName:
		emb = bb_embed("How to use this channel.").add_field(
			name="To spar someone from your region:",
			value=SparDesc,
			inline=False,
		).add_field(
			name="If you don't want to get pings:",
			inline=False,
			value="Remove your region role. Otherwise, responding 'no' to"
			" calls to spar is annoying and counterproductive, and will earn"
			" you a warning.",
		)
		await ctx.send(embed=emb)
		return True
	return False


# Static embeds.
# TODO: convert these to methods

AdminPermsReasons = (
	"Beardless Bot requires permissions in order to do just about anything."
	" Without them, I can't do much, so I'm leaving. If you add me back to"
	" this server, please make sure to leave checked the box that grants me"
	" the Administrator permission.\nIf you have any questions, feel free"
	" to contact my creator, captainnobeard."
)

NoPermsEmbed = bb_embed(
	"I need admin perms!", AdminPermsReasons, 0xFF0000,
).set_author(name="Beardless Bot", icon_url=ProfUrl)

AddUrl = (
	"(https://discord.com/api/oauth2/authorize?client_id="
	f"{BbId}&permissions=8&scope=bot)"
)

Invite_Embed = bb_embed(
	"Want to add this bot to your server?", "[Click this link!]" + AddUrl,
).set_thumbnail(url=ProfUrl).add_field(
	name="If you like Beardless Bot...",
	inline=False,
	value=f"Please leave a review on [top.gg](https://top.gg/bot/{BbId}).",
)

EggRedditEmbed = bb_embed(
	"The Official Eggsoup Subreddit", "https://www.reddit.com/r/eggsoup/",
).set_thumbnail(url=(
	"https://b.thumbs.redditmedia.com/xJ1-nJJ"
	"zHopKe25_bMxKgePiT3HWADjtxioxlku7qcM.png"
))

InvalidTargetEmbed = bb_embed(
	"Invalid target!",
	(
		"Please choose a valid target. Valid targets"
		" are either a ping or a username."
	),
	0xFF0000,
)
