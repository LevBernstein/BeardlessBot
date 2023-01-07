# Beardless Bot unit tests

import asyncio
from dotenv import dotenv_values
from json import load
from os import environ
from random import choice
from time import sleep
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import quote_plus

import discord
import pytest
import requests
from discord.ext import commands
from flake8.api import legacy as flake8

import Bot
import brawl
import bucks
import logs
import misc


imageTypes = (
	"image/png",
	"image/jpeg",
	"image/jpg",
	"image/gif",
	"image/webp"
)

# Zoo API headers report text for some reason

imageSigs = (
	"b'\\xff\\xd8\\xff\\xe0\\x00\\x10JFIF",
	"b'\\x89\\x50\\x4e\\x47\\x0d\\x",
	"b'\\xff\\xd8\\xff\\xe2\\x024ICC_PRO",
	"b'\\x89PNG\\r\\n\\x1a\\n\\",
	"b'\\xff\\xd8\\xff\\xe1\\tPh"
)


def goodURL(
	request: requests.models.Response, fileTypes: Tuple[str]
) -> bool:
	return request.ok and request.headers["content-type"] in imageTypes


# TODO: add _state attribute to all mock objects, inherit from State
# Switch to a single MockState class for all Messageable objects


class MockHTTPClient(discord.http.HTTPClient):
	def __init__(
		self,
		loop: asyncio.AbstractEventLoop,
		user: Optional[discord.User] = None
	) -> None:
		self.loop = loop
		self.user_agent = user
		self.token = None
		self.proxy = None
		self.proxy_auth = None
		self._locks = {}

	async def create_role(
		self, roleId: int, reason: Optional[str] = None, **fields: Any
	) -> Dict[str, Any]:
		data = {
			"id": roleId,
			"name": fields["name"] if "name" in fields else "TestRole"
		}

		if "hoist" in fields:
			data["hoist"] = fields["hoist"]
		if "mentionable" in fields:
			data["mentionable"] = fields["mentionable"]
		if "colour" in fields:
			data["colour"] = fields["colour"]
		if "permissions" in fields:
			data["permissions"] = fields["permissions"]

		return data

	async def send_message(
		self,
		channel_id: Union[str, int],
		content: Optional[str] = None,
		*,
		tts: bool = False,
		embed: Optional[discord.Embed] = None,
		embeds: Optional[List[discord.Embed]] = None,
		nonce: Optional[str] = None,
		allowed_mentions: Optional[Dict[str, Any]] = None,
		message_reference: Optional[Dict[str, Any]] = None,
		stickers: Optional[List[discord.Sticker]] = None,
		components: Optional[List[Any]] = None
	) -> Dict[str, Any]:
		data = {
			"attachments": [],
			"edited_timestamp": None,
			"type": discord.Message,
			"pinned": False,
			"mention_everyone": ("@everyone" in content) if content else False,
			"tts": tts,
			"author": MockUser(),
			"content": content if content else ""
		}
		if embed:
			data["embeds"] = [embed]
		elif embeds:
			data["embeds"] = embeds
		else:
			data["embeds"] = []
		if nonce:
			data["nonce"] = nonce
		if allowed_mentions:
			data["allowed_mentions"] = allowed_mentions
		if message_reference:
			data["message_reference"] = message_reference
		if components:
			data["components"] = components
		if stickers:
			data["stickers"] = stickers
		return data


# MockUser class is a superset of discord.User with some features of
# discord.Member; still working on adding all features of discord.Member,
# at which point I will switch the parent from discord.User to discord.Member
# TODO: give default @everyone role
# TODO: edit Messageable.send() to add messages to self.messages
class MockUser(discord.User):

	class MockUserState():
		def __init__(self, messageNum: int = 0) -> None:
			self._guilds = {}
			self.allowed_mentions = discord.AllowedMentions(everyone=True)
			self.loop = asyncio.new_event_loop()
			self.http = MockHTTPClient(self.loop)
			self.user = None
			self.last_message_id = messageNum
			self.channel = MockChannel()

		def create_message(
			self, *, channel: discord.abc.Messageable, data: Dict[str, Any]
		) -> discord.Message:
			data["id"] = self.last_message_id
			self.last_message_id += 1
			return discord.Message(state=self, channel=channel, data=data)

		def store_user(self, data: Dict[str, Any]) -> discord.User:
			return MockUser()

		def setClientUser(self) -> None:
			self.http.user_agent = self.user

		def _get_private_channel_by_user(self, id: int) -> discord.TextChannel:
			return self.channel

	def __init__(
		self,
		name: str = "testname",
		nick: str = "testnick",
		discriminator: str = "0000",
		id: int = 123456789,
		roles: List[discord.Role] = [],
		guild: Optional[discord.Guild] = None
	) -> None:
		self.name = name
		self.nick = nick
		self.id = id
		self.discriminator = discriminator
		self.bot = False
		self.avatar = str(self.default_avatar)
		self.roles = roles
		self.joined_at = self.created_at
		self.activity = None
		self.system = False
		self.messages = []
		self.guild = guild
		self._public_flags = 0
		self._state = self.MockUserState(messageNum=len(self.messages))

	def setStateUser(self) -> None:
		self._state.user = self
		self._state.setClientUser()


# TODO: edit Messageable.send() to add messages to self.messages
class MockChannel(discord.TextChannel):

	class MockChannelState():
		def __init__(
			self, user: Optional[discord.User] = None, messageNum: int = 0
		) -> None:
			self.loop = asyncio.new_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = discord.AllowedMentions(everyone=True)
			self.user = user
			self.last_message_id = messageNum

		def create_message(
			self, *, channel: discord.abc.Messageable, data: Dict[str, Any]
		) -> discord.Message:
			data["id"] = self.last_message_id
			self.last_message_id += 1
			return discord.Message(state=self, channel=channel, data=data)

		def store_user(self, data: Dict) -> discord.User:
			return self.user if self.user else MockUser()

	class Mock_Overwrites():
		def __init__(
			self,
			id: int,
			type: int,
			allow: discord.Permissions,
			deny: discord.Permissions
		) -> None:
			self.id = id
			self.type = type
			self.allow = allow
			self.deny = deny

	def __init__(
		self,
		name: str = "testchannelname",
		guild: Optional[discord.Guild] = None,
		messages: List[discord.Message] = []
	) -> None:
		self.name = name
		self.id = 123456789
		self.position = 0
		self.slowmode_delay = 0
		self.nsfw = False
		self.topic = None
		self.category_id = 0
		self.guild = guild
		self.messages = []
		self._type = 0
		self._state = self.MockChannelState(messageNum=len(messages))
		self._overwrites = []

	async def set_permissions(
		self,
		target: Union[discord.Role, discord.User],
		*,
		overwrite: discord.PermissionOverwrite,
		reason: Optional[str] = None
	) -> None:
		pair = overwrite.pair()
		self._overwrites.append(
			self.Mock_Overwrites(
				target.id,
				0 if isinstance(target, discord.Role) else 1,
				pair[0].value,
				pair[1].value
			)
		)

	def history(self) -> List[discord.Message]:
		# TODO: make self.send() add message to self.messages
		return list(reversed(self.messages))


# TODO: Write message.edit(), message.delete()
class MockMessage(discord.Message):
	def __init__(
		self,
		content: str = "testcontent",
		author: discord.User = MockUser(),
		guild: Optional[discord.Guild] = None,
		channel: discord.TextChannel = MockChannel()
	) -> None:
		self.author = author
		self.content = content
		self.id = 123456789
		self.channel = channel
		self.type = discord.MessageType.default
		self.flags = discord.MessageFlags()
		self.guild = guild
		self.mentions = []
		self.mention_everyone = False


# TODO: switch to MockRole(guild, **kwargs) factory method
class MockRole(discord.Role):
	def __init__(
		self,
		name: str = "Test Role",
		id: int = 123456789,
		permissions: Union[int, discord.Permissions] = 1879573680
	) -> None:
		self.name = name
		self.id = id
		self.hoist = False
		self.mentionable = True
		self._permissions = (
			permissions if isinstance(permissions, int) else permissions.value
		)


class MockGuild(discord.Guild):

	class MockGuildState():
		def __init__(self) -> None:
			self.member_cache_flags = discord.MemberCacheFlags.all()
			self.self_id = 1
			self.shard_count = 1
			self.loop = asyncio.new_event_loop()
			self.http = MockHTTPClient(self.loop)
			self.user = MockUser()

	def __init__(
		self,
		members: List[discord.User] = [MockUser(), MockUser()],
		name: str = "Test Guild",
		id: int = 0,
		channels: List[discord.TextChannel] = [MockChannel()],
		roles: List[discord.Role] = [MockRole()]
	) -> None:
		self.name = name
		self.id = id
		self._state = self.MockGuildState()
		self._members = {i: m for i, m in enumerate(members)}
		self._member_count = len(self._members)
		self._channels = {i: c for i, c in enumerate(channels)}
		self._roles = {i: r for i, r in enumerate(roles)}
		self.owner_id = 123456789

	async def create_role(
		self,
		*,
		name: str,
		permissions: discord.Permissions,
		mentionable: bool = False,
		hoist: bool = False,
		colour: Union[discord.Colour, int] = 0,
		**kwargs: Any
	) -> discord.Role:

		fields = {
			"name": name,
			"permissions": str(permissions.value),
			"mentionable": mentionable,
			"hoist": hoist,
			"colour": colour if isinstance(colour, int) else colour.value
		}

		data = await self._state.http.create_role(len(self.roles), **fields)
		role = discord.Role(guild=self, data=data, state=self._state)
		self._roles[len(self.roles)] = role

		return role


class MockContext(commands.Context):

	class MockContextState():
		def __init__(
			self,
			user: Optional[discord.User] = None,
			channel: discord.TextChannel = MockChannel()
		) -> None:
			self.loop = asyncio.new_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = discord.AllowedMentions(everyone=True)
			self.user = user
			self.channel = channel

		def create_message(
			self, *, channel: discord.abc.Messageable, data: Dict
		) -> discord.Message:
			data["id"] = self.channel._state.last_message_id
			self.channel._state.last_message_id += 1
			return discord.Message(state=self, channel=channel, data=data)

		def store_user(self, data: Dict) -> discord.User:
			return self.user if self.user else MockUser()

	def __init__(
		self,
		bot: commands.Bot,
		message: discord.Message = MockMessage(),
		channel: discord.TextChannel = MockChannel(),
		author: discord.User = MockUser(),
		guild: Optional[discord.Guild] = MockGuild()
	) -> None:
		self.bot = bot
		self.prefix = bot.command_prefix
		self.message = message
		self.channel = channel
		self.author = author
		self.guild = guild
		if guild and channel not in guild.channels:
			self.guild._channels[len(self.guild.channels)] = channel
		if guild and author not in guild.members:
			self.guild._members[len(self.guild.members)] = author
		self._state = self.MockContextState(channel=self.channel)


class MockBot(commands.Bot):

	class MockBotWebsocket():

		PRESENCE = 3

		def __init__(self, bot: commands.Bot) -> None:
			self.bot = bot

		async def change_presence(
			self,
			*,
			activity: Optional[discord.Activity] = None,
			status: Optional[str] = None,
			afk: bool = False
		) -> None:
			# TODO: change "afk" to "since" for new versions of discord.py
			data = {
				"op": self.PRESENCE,
				"d": {
					"activities": [activity],
					"afk": afk,
					"status": status
				}
			}
			await self.send(data)

		async def send(self, data: Dict[str, any], /) -> Dict[str, Any]:
			self.bot.status = data["d"]["status"]
			self.bot.activity = data["d"]["activities"][0]
			return data

	class MockClientUser(discord.ClientUser):
		def __init__(self, bot: commands.Bot) -> None:
			baseUser = MockUser()
			self._state = baseUser._state
			self.id = 0
			self.name = "testclientuser"
			self.discriminator = "0000"
			self.avatar = baseUser.avatar
			self.bot = bot
			self.verified = True
			self.mfa_enabled = False

		async def edit(self, avatar: str) -> None:
			self.avatar = avatar

	def __init__(self, bot: commands.Bot) -> None:
		self.command_prefix = bot.command_prefix
		self.case_insensitive = bot.case_insensitive
		self._help_command = bot.help_command
		self._intents = bot.intents
		self.owner_id = bot.owner_id
		self.status = ""
		self.ws = self.MockBotWebsocket(self)
		self._connection = bot._connection
		self._connection.user = self.MockClientUser(self)


brawlKey = environ.get("BRAWLKEY")
if not brawlKey:
	env = dotenv_values(".env")
	try:
		brawlKey = env["BRAWLKEY"]
	except KeyError:
		print("No Brawlhalla API key. Brawlhalla-specific tests will fail.\n")

loop = asyncio.get_event_loop()


@pytest.mark.parametrize("letter", ["W", "E", "F"])
def test_pep8Compliance(letter: str) -> None:
	styleGuide = flake8.get_style_guide(ignore=["W191"])
	report = styleGuide.check_files(["./"])
	assert len(report.get_statistics(letter)) == 0


def test_mockContextChannels() -> None:
	ctx = MockContext(
		Bot.bot, channel=MockChannel(), guild=MockGuild(channels=[])
	)
	assert ctx.channel in ctx.guild.channels


def test_mockContextMembers() -> None:
	ctx = MockContext(Bot.bot, author=MockUser(), guild=MockGuild(members=[]))
	assert ctx.author in ctx.guild.members


@pytest.fixture
def test_logException(caplog: pytest.LogCaptureFixture) -> None:
	ctx = MockContext(
		Bot.bot,
		author=MockUser(name="testuser", discriminator="0000"),
		message=MockMessage(content="!axolotl"),
		guild=MockGuild(name="guild")
	)
	ctx.invoked_with = "axolotl"
	Bot.logException(Exception("404: Not Found: axolotl"), ctx)
	assert caplog.records[0].msg == (
		"404: Not Found: axolotl Command: axolotl; Author:"
		" testuser#0000; Content: !axolotl; Guild: guild"
	)


def test_createMutedRole() -> None:
	g = MockGuild(roles=[])
	role = loop.run_until_complete(Bot.createMutedRole(g))
	assert role.name == "Muted"
	assert len(g.roles) == 1 and g.roles[0] == role


def test_on_ready() -> None:
	Bot.bot = MockBot(Bot.bot)
	loop.run_until_complete(Bot.on_ready())
	assert Bot.bot.activity.name == "try !blackjack and !flip"
	assert Bot.bot.status == "online"
	with open("resources/images/prof.png", "rb") as f:
		assert Bot.bot.user.avatar == f.read()


@pytest.mark.parametrize(
	"content,description",
	[("e", "e"), ("", "**Embed**"), ("e" * 1025, logs.msgMaxLength)]
)
def test_contCheck(content: str, description: str) -> None:
	m = MockMessage(content)
	assert logs.contCheck(m) == description


def test_on_message_delete() -> None:
	m = MockMessage(channel=MockChannel(name="bb-log"))
	m.guild = MockGuild(channels=[m.channel])
	emb = loop.run_until_complete(Bot.on_message_delete(m))
	log = logs.logDeleteMsg(m)
	assert emb.description == log.description
	assert log.description == (
		f"**Deleted message sent by {m.author.mention}"
		f" in **{m.channel.mention}\n{m.content}"
	)
	"""
	# TODO: append sent messages to channel.messages
	assert any(
		(i.embed.description == log.description for i in m.channel.history())
	)
	"""


def test_on_bulk_message_delete() -> None:
	m = MockMessage(channel=MockChannel(name="bb-log"))
	m.guild = MockGuild(channels=[m.channel])
	messages = [m, m, m]
	emb = loop.run_until_complete(Bot.on_bulk_message_delete(messages))
	log = logs.logPurge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == f"Purged 2 messages in {m.channel.mention}."
	"""
	# TODO: append sent messages to channel.messages
	assert any(
		(i.embed.description == log.description for i in m.channel.history())
	)
	"""
	messages = [m] * 105
	emb = loop.run_until_complete(Bot.on_bulk_message_delete(messages))
	log = logs.logPurge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == f"Purged 99+ messages in {m.channel.mention}."


def test_on_guild_channel_delete() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	channel = MockChannel(guild=g)
	emb = loop.run_until_complete(Bot.on_guild_channel_delete(channel))
	log = logs.logDeleteChannel(channel)
	assert emb.description == log.description
	assert log.description == f"Channel \"{channel.name}\" deleted."
	"""
	# TODO: append sent messages to channel.messages
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	"""


def test_on_guild_channel_create() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	channel = MockChannel(guild=g)
	emb = loop.run_until_complete(Bot.on_guild_channel_create(channel))
	log = logs.logCreateChannel(channel)
	assert emb.description == log.description
	assert log.description == f"Channel \"{channel.name}\" created."
	"""
	# TODO: append sent messages to channel.messages
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	"""


def test_on_member_ban() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	member = MockUser()
	emb = loop.run_until_complete(Bot.on_member_ban(g, member))
	log = logs.logBan(member)
	assert emb.description == log.description
	assert log.description == f"Member {member.mention} banned\n{member.name}"
	"""
	# TODO: append sent messages to channel.messages
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	"""


def test_on_member_unban() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	member = MockUser()
	emb = loop.run_until_complete(Bot.on_member_unban(g, member))
	log = logs.logUnban(member)
	assert emb.description == log.description
	assert (
		log.description == f"Member {member.mention} unbanned\n{member.name}"
	)
	"""
	# TODO: append sent messages to channel.messages
	channel = member.guild.channels[0]
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	"""


def test_on_member_join() -> None:
	member = MockUser()
	member.guild = MockGuild(channels=[MockChannel(name="bb-log")])
	emb = loop.run_until_complete(Bot.on_member_join(member))
	log = logs.logMemberJoin(member)
	assert emb.description == log.description
	assert log.description == (
		f"Member {member.mention} joined\nAccount registered"
		f" on {misc.truncTime(member)}\nID: {member.id}"
	)
	"""
	# TODO: append sent messages to channel.messages
	channel = member.guild.channels[0]
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	"""


def test_on_member_remove() -> None:
	member = MockUser()
	member.guild = MockGuild(channels=[MockChannel(name="bb-log")])
	emb = loop.run_until_complete(Bot.on_member_remove(member))
	log = logs.logMemberRemove(member)
	assert emb.description == log.description
	assert log.description == f"Member {member.mention} left\nID: {member.id}"
	member.roles = [MockRole(), MockRole()]
	emb = loop.run_until_complete(Bot.on_member_remove(member))
	log = logs.logMemberRemove(member)
	assert emb.description == log.description
	assert log.fields[0].value == member.roles[1].mention
	"""
	# TODO: append sent messages to channel.messages
	channel = member.guild.channels[0]
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	"""


def test_on_member_update() -> None:
	guild = MockGuild(channels=[MockChannel(name="bb-log")])
	old = MockUser(nick="a", roles=[], guild=guild)
	new = MockUser(nick="b", roles=[], guild=guild)
	emb = loop.run_until_complete(Bot.on_member_update(old, new))
	log = logs.logMemberNickChange(old, new)
	assert emb.description == log.description
	assert log.description == "Nickname of " + new.mention + " changed."
	assert log.fields[0].value == old.nick
	assert log.fields[1].value == new.nick

	new = MockUser(nick="a", roles=[MockRole()], guild=guild)
	emb = loop.run_until_complete(Bot.on_member_update(old, new))
	log = logs.logMemberRolesChange(old, new)
	assert emb.description == log.description
	assert log.description == (
		f"Role {new.roles[0].mention} added to {new.mention}."
	)

	emb = loop.run_until_complete(Bot.on_member_update(new, old))
	log = logs.logMemberRolesChange(new, old)
	assert emb.description == log.description
	assert log.description == (
		f"Role {new.roles[0].mention} removed from {old.mention}."
	)


def test_on_message_edit() -> None:
	member = MockUser()
	g = MockGuild(
		channels=[MockChannel(name="bb-log"), MockChannel(name="infractions")]
	)
	loop.run_until_complete(Bot.createMutedRole(g))
	before = MockMessage(content="old", author=member, guild=g)
	after = MockMessage(content="new", author=member, guild=g)
	emb = loop.run_until_complete(Bot.on_message_edit(before, after))
	log = logs.logEditMsg(before, after)
	assert emb.description == log.description
	assert emb.description == (
		f"Messaged edited by {after.author.mention}"
		f" in {after.channel.mention}."
	)
	assert emb.fields[0].value == before.content
	assert emb.fields[1].value == (
		f"{after.content}\n[Jump to Message]({after.jump_url})"
	)
	# TODO: append sent msgs to channel.messages, user.messages, allowing
	# testing for scamCheck == True
	'''
	after.content = "http://dizcort.com free nitro!"
	emb = loop.run_until_complete(Bot.on_message_edit(before, after))
	assert g.channels[0].messages[0].content.startswith("Deleted possible")
	# TODO: edit after to have content of len > 1024 via message.edit
	channel = member.guild.channels[0]
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	'''


def test_cmdDice() -> None:
	ch = MockChannel()
	ctx = MockContext(Bot.bot, channel=ch, guild=MockGuild(channels=[ch]))
	emb = loop.run_until_complete(Bot.cmdDice(ctx))
	assert emb.description == misc.diceMsg
	"""
	# TODO: append sent messages to channel.messages
	assert any(
		(i.embed.description == emb.description for i in ch.history())
	)
	"""


# TODO: now that mock context has state, write tests for other Bot methods


def test_fact() -> None:
	with open("resources/facts.txt", "r") as f:
		lines = f.read().splitlines()
	assert misc.fact() in lines


def test_tweet() -> None:
	eggTweet = misc.tweet()
	assert ("\n" + eggTweet).startswith(misc.formattedTweet(eggTweet))
	assert "." not in misc.formattedTweet("test tweet.")
	assert "." not in misc.formattedTweet("test tweet")
	eggTweet = eggTweet.split(" ")
	assert len(eggTweet) >= 11 and len(eggTweet) <= 37


@pytest.mark.parametrize("side", [4, 6, 8, 10, 12, 20, 100])
def test_dice_regular(side: int) -> None:
	user = MockUser()
	text = "d" + str(side)
	assert misc.roll(text) in range(1, side + 1)
	assert (misc.rollReport(text, user).description.startswith("You got"))


def test_dice_irregular() -> None:
	user = MockUser()
	assert misc.roll("d20-4") in range(-3, 17)
	assert misc.rollReport("d20-4", user).description.startswith("You got")
	assert not misc.roll("wrongroll")
	assert not misc.roll("d9")
	assert misc.rollReport("d9", user).description.startswith("Invalid")


def test_logClearReacts() -> None:
	msg = MockMessage()
	emb = logs.logClearReacts(msg, (1, 2, 3))
	assert (
		emb.description.startswith(
			"Reactions cleared from message sent by"
			f" {msg.author.mention} in {msg.channel.mention}."
		)
	)
	assert emb.fields[0].value.startswith(msg.content)
	assert emb.fields[1].value == "1, 2, 3"


def test_logMute() -> None:
	message = MockMessage()
	member = MockUser()
	assert logs.logMute(member, message, "5", "hours", 18000).description == (
		f"Muted {member.mention} for 5 hours in {message.channel.mention}."
	)
	assert logs.logMute(member, message, None, None, None).description == (
		f"Muted {member.mention} in {message.channel.mention}."
	)


def test_logUnmute() -> None:
	member = MockUser()
	assert logs.logUnmute(member, MockUser()).description == (
		f"Unmuted {member.mention}."
	)


@pytest.mark.parametrize(
	"username,content", [
		("searchterm", "searchterm#9999"),
		("searchterm", "searchterm"),
		("searchterm", "search"),
		("searchterm", "testnick"),
		("hash#name", "hash#name")
	]
)
def test_memSearch_valid(username: str, content: str) -> None:
	namedUser = MockUser(username, "testnick", "9999")
	text = MockMessage(
		content=content, guild=MockGuild(members=(MockUser(), namedUser))
	)
	assert misc.memSearch(text, content) == namedUser


def test_memSearch_invalid() -> None:
	namedUser = MockUser("searchterm", "testnick", "9999")
	text = MockMessage(
		content="invalidterm", guild=MockGuild(members=(MockUser(), namedUser))
	)
	assert not misc.memSearch(text, text.content)


def test_register() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	bucks.reset(bb)
	assert bucks.register(bb).description == (
		"You are already in the system! Hooray! You"
		f" have 200 BeardlessBucks, {bb.mention}."
	)
	bb.name = ",badname,"
	assert bucks.register(bb).description == bucks.commaWarn.format(bb.mention)


@pytest.mark.parametrize(
	"target,result", [
		(MockUser("Test", "", 5757, 654133911558946837), "'s balance is"),
		(MockUser(","), bucks.commaWarn.format("<@123456789>")),
		("Invalid user", "Invalid user!")
	]
)
def test_balance(target: discord.User, result: str) -> None:
	msg = MockMessage("!bal", guild=MockGuild())
	assert result in bucks.balance(target, msg).description


def test_reset() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	assert bucks.reset(bb).description == (
		f"You have been reset to 200 BeardlessBucks, {bb.mention}."
	)
	bb.name = ",badname,"
	assert bucks.reset(bb).description == bucks.commaWarn.format(bb.mention)


def test_writeMoney() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	bucks.reset(bb)
	assert bucks.writeMoney(bb, "-all", False, False) == (0, 200)
	assert bucks.writeMoney(bb, -1000000, True, False) == (-2, None)


def test_leaderboard() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	lb = bucks.leaderboard()
	assert lb.title == "BeardlessBucks Leaderboard"
	fields = lb.fields
	if len(fields) >= 2:  # This check in case of an empty leaderboard
		assert int(fields[0].value) > int(fields[1].value)
	user = MockUser(name="bad,name", id=0)
	lb = bucks.leaderboard(user, MockMessage(author=user))
	assert len(lb.fields) == len(fields)
	lb = bucks.leaderboard(bb, MockMessage(author=bb))
	assert len(lb.fields) == len(fields) + 2


def test_define() -> None:
	word = misc.define("test")
	assert word.title == "TEST" and word.description.startswith("Audio: ")
	word = misc.define("gtg")
	assert word.title == "GTG" and word.description == ""
	assert misc.define("invalidword").description == "No results found."


def test_flip() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	assert bucks.flip(bb, "0", True).endswith("actually bet anything.")
	assert bucks.flip(bb, "invalidbet").startswith("Invalid bet.")
	bucks.reset(bb)
	bucks.flip(bb, "all")
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert ("400" in balMsg.description or "0" in balMsg.description)
	bucks.reset(bb)
	bucks.flip(bb, "100")
	assert bucks.flip(bb, "10000000000000").startswith("You do not have")
	bucks.reset(bb)
	assert "200" in bucks.balance(bb, MockMessage("!bal", bb)).description
	bb.name = ",invalidname,"
	assert bucks.flip(bb, "0") == bucks.commaWarn.format(bb.mention)


def test_blackjack() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	assert bucks.blackjack(bb, "invalidbet")[0].startswith("Invalid bet.")
	bucks.reset(bb)
	report, game = bucks.blackjack(bb, "all")
	assert isinstance(game, bucks.Instance) or "You hit 21!" in report
	bucks.reset(bb)
	report, game = bucks.blackjack(bb, 0)
	assert isinstance(game, bucks.Instance) or "You hit 21!" in report
	bucks.reset(bb)
	game = bucks.Instance(bb, "all", True)
	assert "You hit 21!" in game.message
	bucks.reset(bb)
	report, game = bucks.blackjack(bb, "10000000000000")
	assert report.startswith("You do not have")
	bb.name = ",invalidname,"
	assert bucks.blackjack(bb, "all")[0] == bucks.commaWarn.format(bb.mention)


def test_blackjack_perfect() -> None:
	game = bucks.Instance(MockUser(), 10)
	game.cards = 10, 11
	assert game.perfect()


def test_blackjack_deal() -> None:
	game = bucks.Instance(MockUser(), 10)
	game.cards = [2, 3]
	game.deal()
	assert len(game.cards) == 3
	game.cards = [11, 9]
	game.deal()
	assert sum(game.cards) <= 21
	assert "will be treated as a 1" in game.message
	game.cards = []
	assert "You hit 21!" in game.deal(True)


def test_blackjack_cardName() -> None:
	game = bucks.Instance(MockUser(), 10)
	assert game.cardName(10) in ("a 10", "a Jack", "a Queen", "a King")
	assert game.cardName(11) == "an Ace"
	assert game.cardName(8) == "an 8"
	assert game.cardName(5) == "a 5"


def test_blackjack_checkBust() -> None:
	game = bucks.Instance(MockUser(), 10)
	game.cards = 10, 10, 10
	assert game.checkBust()


def test_blackjack_stay() -> None:
	game = bucks.Instance(MockUser(), 0)
	game.cards = [10, 10, 1]
	game.dealerSum = 25
	assert game.stay() == 1
	game.dealerSum = 20
	assert game.stay() == 1
	game.deal()
	assert game.stay() == 1
	game.cards = 10, 10
	assert game.stay() == 0


def test_blackjack_startingHand() -> None:
	game = bucks.Instance(MockUser(), 10)
	game.cards = []
	game.message = game.startingHand()
	assert len(game.cards) == 2
	assert game.message.startswith("Your starting hand consists of ")
	assert "You hit 21!" in game.startingHand(True)
	assert "two Aces" in game.startingHand(False, True)


def test_activeGame() -> None:
	author = MockUser(name="target", id=0)
	games = [bucks.Instance(MockUser(name="not", id=1), 10)] * 9
	assert not bucks.activeGame(games, author)
	games.append(bucks.Instance(author, 10))
	assert bucks.activeGame(games, author)


def test_info() -> None:
	namedUser = MockUser("searchterm", roles=[MockRole(), MockRole()])
	guild = MockGuild(members=[MockUser(), namedUser])
	text = MockMessage("!info searchterm", guild=guild)
	namedUserInfo = misc.info("searchterm", text)
	assert namedUserInfo.fields[0].value == misc.truncTime(namedUser) + " UTC"
	assert namedUserInfo.fields[1].value == misc.truncTime(namedUser) + " UTC"
	assert namedUserInfo.fields[2].value == namedUser.roles[1].mention
	assert misc.info("!infoerror", text).title == "Invalid target!"


def test_av() -> None:
	namedUser = MockUser("searchterm")
	guild = MockGuild(members=[MockUser(), namedUser])
	text = MockMessage("!av searchterm", guild=guild)
	assert misc.av("searchterm", text).image.url == str(namedUser.avatar_url)
	assert misc.av("error", text).title == "Invalid target!"


def test_commands() -> None:
	ctx = MockContext(Bot.bot, guild=None)
	assert len(misc.bbCommands(ctx).fields) == 15
	ctx.guild = MockGuild()
	ctx.author.guild_permissions = discord.Permissions(manage_messages=True)
	assert len(misc.bbCommands(ctx).fields) == 20
	ctx.author.guild_permissions = discord.Permissions(manage_messages=False)
	assert len(misc.bbCommands(ctx).fields) == 17


def test_hints() -> None:
	with open("resources/hints.txt", "r") as f:
		assert len(misc.hints().fields) == len(f.read().splitlines())


def test_pingMsg() -> None:
	namedUser = MockUser("likesToPing")
	assert (
		brawl.pingMsg(namedUser.mention, 1, 1, 1)
		.endswith("You can ping again in 1 hour, 1 minute, and 1 second.")
	)
	assert (
		brawl.pingMsg(namedUser.mention, 2, 2, 2)
		.endswith("You can ping again in 2 hours, 2 minutes, and 2 seconds.")
	)


def test_scamCheck() -> None:
	assert misc.scamCheck("http://dizcort.com free nitro!")
	assert misc.scamCheck("@everyone http://didcord.gg free nitro!")
	assert misc.scamCheck("gift nitro http://d1zcordn1tr0.co.uk free!")
	assert misc.scamCheck("hey @everyone check it! http://discocl.com/ nitro!")
	assert not misc.scamCheck(
		"Hey Discord friends, check out https://top.gg/bot/654133911558946837"
	)
	assert not misc.scamCheck(
		"Here's an actual gift link https://discord.gift/s23d35fls55d13l1fjds"
	)


# TODO: switch to mock context, add test for error with quotation mark
@pytest.mark.parametrize("searchterm", ["Русская лексика", "two words", ""])
def test_search_valid(searchterm: str) -> None:
	url = "https://www.google.com/search?q=" + quote_plus(searchterm)
	assert url == misc.search(searchterm).description
	r = requests.get(url)
	assert r.ok


def test_search_invalid() -> None:
	assert misc.search(5).title == "Invalid Search!"


def test_onJoin() -> None:
	role = MockRole(id=0)
	guild = MockGuild(name="Test Guild", roles=[role])
	emb = misc.onJoin(guild, role)
	assert emb.title == "Hello, Test Guild!"
	assert emb.description == misc.joinMsg.format(guild.name, role.mention)


@pytest.mark.parametrize("animalName", list(misc.animalList[:-4]) + ["dog"])
def test_animal_with_goodUrl(animalName: str) -> None:
	assert goodURL(requests.get(misc.animal(animalName)), imageTypes)


@pytest.mark.parametrize("animalName", misc.animalList[-4:])
def test_animal_with_imageSigs(animalName: str) -> None:
	# Koala, Bird, Raccoon, Kangaroo APIs lack a content-type field;
	# check if URL points to an image instead
	r = requests.get(misc.animal(animalName))
	assert r.ok and any(
		str(r.content).startswith(signature) for signature in imageSigs
	)


def test_animal_dog_breed() -> None:
	breeds = misc.animal("dog", "breeds")[12:-1].split(", ")
	assert len(breeds) >= 94
	r = requests.get(misc.animal("dog", choice(breeds)))
	assert goodURL(r, imageTypes)
	assert misc.animal("dog", "invalidbreed").startswith("Breed not")
	assert misc.animal("dog", "invalidbreed1234").startswith("Breed not")
	assert goodURL(requests.get(misc.animal("dog", "moose")), imageTypes)


def test_invalid_animal_raises_exception() -> None:
	with pytest.raises(Exception):
		misc.animal("invalidAnimal")


# Tests for commands that require a Brawlhalla API key:


def test_randomBrawl() -> None:
	assert brawl.randomBrawl("weapon").title == "Random Weapon"
	assert brawl.randomBrawl("legend").title == "Random Legend"
	assert len(brawl.randomBrawl("legend", brawlKey).fields) == 2
	assert brawl.randomBrawl("invalidrandom").title == "Brawlhalla Randomizer"


def test_fetchBrawlID() -> None:
	assert brawl.fetchBrawlID(196354892208537600) == 7032472
	assert not brawl.fetchBrawlID(654133911558946837)


def test_claimProfile() -> None:
	with open("resources/claimedProfs.json", "r") as f:
		profsLen = len(load(f))
	brawl.claimProfile(196354892208537600, 1)
	with open("resources/claimedProfs.json", "r") as f:
		assert profsLen == len(load(f))
	assert brawl.fetchBrawlID(196354892208537600) == 1
	brawl.claimProfile(196354892208537600, 7032472)
	assert brawl.fetchBrawlID(196354892208537600) == 7032472


@pytest.mark.parametrize(
	"url,result", [
		("https://steamcommunity.com/id/beardless", 7032472),
		("badurl", None),
		("https://steamcommunity.com/badurl", None),
		("https://steamcommunity.com/badurl", None)
	]
)
def test_getBrawlID(url: str, result: Optional[int]) -> None:
	sleep(2)
	assert brawl.getBrawlID(brawlKey, url) == result


def test_getClan() -> None:
	sleep(5)
	user = MockUser(id=0)
	assert brawl.getClan(user, brawlKey).description == (
		brawl.unclaimed.format(user.mention)
	)
	user.id = 196354892208537600
	brawl.claimProfile(196354892208537600, 7032472)
	assert brawl.getClan(user, brawlKey).title == "DinersDriveInsDives"
	brawl.claimProfile(196354892208537600, 5895238)
	assert brawl.getClan(user, brawlKey).description == (
		"You are not in a clan!"
	)
	brawl.claimProfile(196354892208537600, 7032472)


def test_getRank() -> None:
	sleep(5)
	user = MockUser(id=0)
	assert brawl.getRank(user, brawlKey).description == (
		brawl.unclaimed.format(user.mention)
	)
	user.id = 196354892208537600
	assert brawl.getRank(user, brawlKey).footer.text == "Brawl ID 7032472"
	assert brawl.getRank(user, brawlKey).description == (
		"You haven't played ranked yet this season."
	)
	brawl.claimProfile(196354892208537600, 12502880)
	assert brawl.getRank(user, brawlKey).color.value == 0x3D2399
	brawl.claimProfile(196354892208537600, 7032472)


def test_getLegends() -> None:
	sleep(5)
	oldLegends = brawl.fetchLegends()
	brawl.getLegends(brawlKey)
	assert brawl.fetchLegends() == oldLegends


def test_legendInfo() -> None:
	sleep(5)
	assert brawl.legendInfo(brawlKey, "hugin").title == "Munin, The Raven"
	assert brawl.legendInfo(brawlKey, "teros").title == "Teros, The Minotaur"
	assert not brawl.legendInfo(brawlKey, "invalidname")


def test_getStats() -> None:
	sleep(5)
	user = MockUser(id=0)
	assert brawl.getStats(user, brawlKey).description == (
		brawl.unclaimed.format(user.mention)
	)
	user.id = 196354892208537600
	brawl.claimProfile(196354892208537600, 7032472)
	emb = brawl.getStats(user, brawlKey)
	assert emb.footer.text == "Brawl ID 7032472"
	assert len(emb.fields) in (3, 4)


def test_brawlCommands() -> None:
	sleep(5)
	assert len(brawl.brawlCommands().fields) == 6
