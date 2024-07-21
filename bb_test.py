# Beardless Bot unit tests

import asyncio
from dotenv import dotenv_values
from json import load
import logging
from os import environ
from random import choice
from time import sleep
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote_plus

import nextcord
import pytest
import requests
from nextcord.ext import commands
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


def goodURL(request: requests.models.Response) -> bool:
	return request.ok and request.headers["content-type"] in imageTypes


# TODO: add _state attribute to all mock objects, inherit from State
# Switch to a single MockState class for all Messageable objects


class MockHTTPClient(nextcord.http.HTTPClient):
	def __init__(
		self,
		loop: asyncio.AbstractEventLoop,
		user: Optional[nextcord.User] = None
	) -> None:
		self.loop = loop
		self.user_agent = user
		self.token = None
		self.proxy = None
		self.proxy_auth = None
		self._locks = {}
		self._global_over = asyncio.Event()
		self._global_over.set()

	async def create_role(
		self, roleId: int, reason: Optional[str] = None, **fields: Any
	) -> Dict[str, Any]:
		data = {key: value for key, value in fields.items()}
		data["id"] = roleId
		data["name"] = fields["name"] if "name" in fields else "TestRole"
		return data

	async def send_message(
		self,
		channel_id: Union[str, int],
		content: Optional[str] = None,
		*,
		tts: bool = False,
		embed: Optional[nextcord.Embed] = None,
		embeds: Optional[List[nextcord.Embed]] = None,
		nonce: Optional[str] = None,
		allowed_mentions: Optional[Dict[str, Any]] = None,
		message_reference: Optional[Dict[str, Any]] = None,
		stickers: Optional[List[nextcord.Sticker]] = None,
		components: Optional[List[Any]] = None,
		**kwargs
	) -> Dict[str, Any]:
		data = {
			"attachments": [],
			"edited_timestamp": None,
			"type": nextcord.Message,
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


# MockUser class is a superset of nextcord.User with some features of
# nextcord.Member; still working on adding all features of nextcord.Member,
# at which point I will switch the parent from nextcord.User to nextcord.Member
# TODO: give default @everyone role
# TODO: move MockState out, apply to all classes, make generic
class MockUser(nextcord.User):

	class MockUserState():
		def __init__(self, messageNum: int = 0) -> None:
			self._guilds = {}
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop)
			self.user = None
			self.last_message_id = messageNum
			self.channel = MockChannel()

		def create_message(
			self, *, channel: nextcord.abc.Messageable, data: Dict[str, Any]
		) -> nextcord.Message:
			data["id"] = self.last_message_id
			self.last_message_id += 1
			message = nextcord.Message(state=self, channel=channel, data=data)
			self.channel._state._messages.append(message)
			return message

		def store_user(self, data: Dict[str, Any]) -> nextcord.User:
			return MockUser()

		def setClientUser(self) -> None:
			self.http.user_agent = self.user

		def _get_private_channel_by_user(self, id: int) -> nextcord.TextChannel:
			return self.channel

	def __init__(
		self,
		name: str = "testname",
		nick: str = "testnick",
		discriminator: str = "0000",
		id: int = 123456789,
		roles: List[nextcord.Role] = [],
		guild: Optional[nextcord.Guild] = None,
		customAvatar: bool = True,
		adminPowers: bool = False,
		messages: List[nextcord.Message] = []
	) -> None:
		self.name = name
		self.global_name = name
		self.nick = nick
		self.id = id
		self.discriminator = discriminator
		self.bot = False
		self.roles = roles
		self.joined_at = self.created_at
		self.activity = None
		self.system = False
		self.messages = messages
		self.guild = guild
		self._public_flags = 0
		self._state = self.MockUserState(messageNum=len(self.messages))
		self._avatar = "7b6ea511d6e0ef6d1cdb2f7b53946c03" if customAvatar else None
		self.setUserState()
		self.guild_permissions = (
			nextcord.Permissions.all() if adminPowers else nextcord.Permissions.none()
		)

	def setUserState(self) -> None:
		self._state.user = self
		self._state.setClientUser()

	def history(self) -> List[nextcord.Message]:
		return self._state.channel.history()

	async def add_roles(self, role: nextcord.Role) -> None:
		self.roles.append(role)


class MockChannel(nextcord.TextChannel):

	class MockChannelState():
		def __init__(
			self, user: Optional[nextcord.User] = None, messageNum: int = 0
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.user = user
			self.last_message_id = messageNum
			self._messages = []

		def create_message(
			self, *, channel: nextcord.abc.Messageable, data: Dict[str, Any]
		) -> nextcord.Message:
			data["id"] = self.last_message_id
			self.last_message_id += 1
			message = nextcord.Message(state=self, channel=channel, data=data)
			self._messages.append(message)
			return message

		def store_user(self, data: Dict) -> nextcord.User:
			return self.user if self.user else MockUser()

	class Mock_Overwrites():
		def __init__(
			self,
			id: int,
			type: int,
			allow: nextcord.Permissions,
			deny: nextcord.Permissions
		) -> None:
			self.id = id
			self.type = type
			self.allow = allow
			self.deny = deny

	def __init__(
		self,
		name: str = "testchannelname",
		guild: Optional[nextcord.Guild] = None,
		messages: List[nextcord.Message] = [],
		id: int = 123456789
	) -> None:
		self.name = name
		self.id = id
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
		target: Union[nextcord.Role, nextcord.User],
		*,
		overwrite: nextcord.PermissionOverwrite,
		reason: Optional[str] = None
	) -> None:
		pair = overwrite.pair()
		self._overwrites.append(
			self.Mock_Overwrites(
				target.id,
				0 if isinstance(target, nextcord.Role) else 1,
				pair[0].value,
				pair[1].value
			)
		)

	def history(self) -> List[nextcord.Message]:
		return list(reversed(self._state._messages))


# TODO: Write message.edit(), message.delete()
class MockMessage(nextcord.Message):

	class MockMessageState():
		def __init__(self, user: nextcord.User) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user=user)

	def __init__(
		self,
		content: Optional[str] = "testcontent",
		author: nextcord.User = MockUser(),
		guild: Optional[nextcord.Guild] = None,
		channel: nextcord.TextChannel = MockChannel(),
		embed: Optional[nextcord.Embed] = None
	) -> None:
		self.author = author
		self.content = content
		self.id = 123456789
		self.channel = channel
		self.type = nextcord.MessageType.default
		self.guild = guild
		self.mentions = []
		self.mention_everyone = False
		self.flags = nextcord.MessageFlags._from_value(0)
		self._state = self.MockMessageState(author)
		self.channel._state._messages.append(self)

	async def delete(self):
		self.channel._state._messages.remove(self)


# TODO: switch to guild.MockRole(*kwargs) factory method:
# return role, add to _roles
class MockRole(nextcord.Role):
	def __init__(
		self,
		name: str = "Test Role",
		id: int = 123456789,
		permissions: Union[int, nextcord.Permissions] = 1879573680
	) -> None:
		self.name = name
		self.id = id
		self.hoist = False
		self.mentionable = True
		self.position = 1
		self._permissions = (
			permissions if isinstance(permissions, int) else permissions.value
		)


class MockGuild(nextcord.Guild):

	class MockGuildState():
		def __init__(self) -> None:
			self.member_cache_flags = nextcord.MemberCacheFlags.all()
			self.self_id = 1
			self.shard_count = 1
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop)
			self.user = MockUser()
			self._intents = nextcord.Intents.all()

		def is_guild_evicted(self, *args, **kwargs: Any) -> False:
			return False

		async def chunk_guild(self, *args, **kwargs: Any) -> None:
			pass

		async def query_members(self, *args, **kwargs: Any) -> List[nextcord.Member]:
			return [self.user]

	def __init__(
		self,
		members: List[nextcord.User] = [MockUser(), MockUser()],
		name: str = "Test Guild",
		id: int = 0,
		channels: List[nextcord.TextChannel] = [MockChannel()],
		roles: List[nextcord.Role] = [MockRole()]
	) -> None:
		self.name = name
		self.id = id
		self._state = self.MockGuildState()
		self._members = {i: m for i, m in enumerate(members)}
		self._member_count = len(self._members)
		self._channels = {i: c for i, c in enumerate(channels)}
		self._roles = {i: r for i, r in enumerate(roles)}
		self.owner_id = 123456789
		for role in self._roles.values():
			self.assignGuild(role)

	async def create_role(
		self,
		*,
		name: str,
		permissions: nextcord.Permissions,
		mentionable: bool = False,
		hoist: bool = False,
		colour: Union[nextcord.Colour, int] = 0,
		**kwargs: Any
	) -> nextcord.Role:

		fields = {
			"name": name,
			"permissions": str(permissions.value),
			"mentionable": mentionable,
			"hoist": hoist,
			"colour": colour if isinstance(colour, int) else colour.value
		}

		data = await self._state.http.create_role(len(self.roles), **fields)
		role = nextcord.Role(guild=self, data=data, state=self._state)
		self._roles[len(self.roles)] = role

		return role

	def assignGuild(self, role: nextcord.Role) -> None:
		role.guild = self
		return

	def get_member(self, userId: int) -> Optional[nextcord.Member]:
		class MockGuildMember(nextcord.Member):
			def __init__(self, id: int) -> None:
				self.data = {"user": "foo", "roles": "0"}
				self.guild = MockGuild()
				self.state = MockUser.MockUserState()
				self._user = MockUser(id=id)
				self._client_status = {}
		return MockGuildMember(userId)

	def get_channel(self, channelId: int) -> Optional[nextcord.TextChannel]:
		return self._channels.get(channelId)


class MockThread(nextcord.Thread):
	def __init__(
		self,
		name: str = "testThread",
		owner: nextcord.User = MockUser(),
		channelId: int = 0
	):
		channel = MockChannel(id=channelId)
		self.guild = MockGuild(channels=[channel])
		self._state = channel._state
		self.state = self._state
		self.id = 0
		self.name = name
		self.parent_id = channel.id
		self.owner_id = owner.id
		self.locked = False
		self.archived = False
		self.message_count = 0
		self._type = 0
		self.auto_archive_duration = 10080
		self.archive_timestamp = None
		self.member_count = len(self.guild.members)


class MockContext(commands.Context):

	class MockContextState():
		def __init__(
			self,
			user: Optional[nextcord.User] = None,
			channel: nextcord.TextChannel = MockChannel()
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.user = user
			self.channel = channel
			self.message = MockMessage()

		def create_message(
			self, *, channel: nextcord.abc.Messageable, data: Dict
		) -> nextcord.Message:
			data["id"] = self.channel._state.last_message_id
			self.channel._state.last_message_id += 1
			message = nextcord.Message(state=self, channel=channel, data=data)
			self.channel._state._messages.append(message)
			return message

		def store_user(self, data: Dict) -> nextcord.User:
			return self.user if self.user else MockUser()

	def __init__(
		self,
		bot: commands.Bot,
		message: nextcord.Message = MockMessage(),
		channel: nextcord.TextChannel = MockChannel(),
		author: nextcord.User = MockUser(),
		guild: Optional[nextcord.Guild] = MockGuild()
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
		self.invoked_with = None

	def history(self) -> List[nextcord.Message]:
		return self._state.channel.history()


class MockBot(commands.Bot):

	class MockBotWebsocket():

		PRESENCE = 3

		def __init__(self, bot: commands.Bot) -> None:
			self.bot = bot
			self.latency = 0.025

		async def change_presence(
			self,
			*,
			activity: Optional[nextcord.Activity] = None,
			status: Optional[str] = None,
			since: float = 0.0
		) -> None:
			data = {
				"op": self.PRESENCE,
				"d": {
					"activities": [activity],
					"status": nextcord.Status(value="online"),
					"since": since
				}
			}
			await self.send(data)

		async def send(self, data: Dict[str, any], /) -> Dict[str, Any]:
			self.bot.status = nextcord.Status(value="online")
			self.bot.activity = data["d"]["activities"][0]
			return data

	class MockClientUser(nextcord.ClientUser):
		def __init__(self, bot: commands.Bot) -> None:
			baseUser = MockUser(id=654133911558946837)
			self._state = baseUser._state
			self.id = 654133911558946837
			self.name = "testclientuser"
			self.discriminator = "0000"
			self._avatar = baseUser.avatar
			self.bot = bot
			self.verified = True
			self.mfa_enabled = False

		async def edit(self, avatar: str) -> None:
			self._avatar = str(avatar)

	def __init__(self, bot: commands.Bot) -> None:
		self._connection = bot._connection
		self._connection.user = self.MockClientUser(self)
		self.command_prefix = bot.command_prefix
		self.case_insensitive = bot.case_insensitive
		self._help_command = bot.help_command
		self._intents = bot.intents
		self.owner_id = bot.owner_id
		self.status = nextcord.Status(value="online")
		self.ws = self.MockBotWebsocket(self)
		self._connection._guilds = {1: MockGuild()}
		self.all_commands = bot.all_commands


brawlKey = environ.get("BRAWLKEY")
if not brawlKey:
	env = dotenv_values(".env")
	try:
		brawlKey = env["BRAWLKEY"]
	except KeyError:
		print("No Brawlhalla API key. Brawlhalla-specific tests will fail.\n")


@pytest.mark.parametrize("letter", ["W", "E", "F"])
def test_pep8Compliance(letter: str) -> None:
	styleGuide = flake8.get_style_guide(ignore=["W191", "W503"])
	files = [
		"bb_test.py",
		"Bot.py",
		"brawl.py",
		"bucks.py",
		"logs.py",
		"misc.py"
	]
	report = styleGuide.check_files(files)
	assert len(report.get_statistics(letter)) == 0


def test_mockContextChannels() -> None:
	ctx = MockContext(
		Bot.bot, channel=MockChannel(), guild=MockGuild(channels=[])
	)
	assert ctx.channel in ctx.guild.channels


def test_mockContextMembers() -> None:
	ctx = MockContext(Bot.bot, author=MockUser(), guild=MockGuild(members=[]))
	assert ctx.author in ctx.guild.members


@pytest.mark.asyncio
async def test_logException(caplog: pytest.LogCaptureFixture) -> None:
	ctx = MockContext(
		Bot.bot,
		message=MockMessage(content="!mute foo"),
		author=MockUser(adminPowers=True)
	)
	ctx.invoked_with = "mute"
	await Bot.cmdMute(ctx, "foo")
	assert caplog.records[0].msg == (
		"Member \"foo\" not found. Command: mute; Author:"
		" testname#0000; Content: !mute foo; Guild: Test Guild"
	)


@pytest.mark.asyncio
async def test_createMutedRole() -> None:
	g = MockGuild(roles=[])
	role = await Bot.createMutedRole(g)
	assert role.name == "Muted"
	assert len(g.roles) == 1 and g.roles[0] == role


@pytest.mark.asyncio
async def test_on_ready(caplog: pytest.LogCaptureFixture) -> None:
	Bot.bot = MockBot(Bot.bot)
	assert Bot.bot.user._avatar.url == (
		f"https://cdn.discordapp.com/avatars/{Bot.bot.user.id}/"
		f"{Bot.bot.user._avatar.key}.png?size=1024"
	)
	caplog.set_level(logging.INFO)
	await Bot.on_ready()
	assert Bot.bot.activity.name == "try !blackjack and !flip"
	assert Bot.bot.status == nextcord.Status(value="online")
	assert caplog.records[4].msg == (
		"Done! Beardless Bot serves 1 unique members across 1 servers."
	)

	Bot.bot._connection._guilds[2] = MockGuild(
		name="Foo", id=1, members=Bot.bot._connection._guilds[1].members
	)
	await Bot.on_ready()
	assert caplog.records[9].msg == (
		"Done! Beardless Bot serves 1 unique members across 2 servers."
	)

	Bot.bot._connection._guilds[3] = MockGuild(
		name="Foo", id=1, members=[MockUser(id=12, name="Foobar")]
	)
	await Bot.on_ready()
	assert caplog.records[14].msg == (
		"Done! Beardless Bot serves 2 unique members across 3 servers."
	)

	caplog.set_level(logging.WARN)


@pytest.mark.asyncio
async def test_on_ready_no_guilds(caplog: pytest.LogCaptureFixture) -> None:
	Bot.bot = MockBot(Bot.bot)
	Bot.bot._connection._guilds = {}
	await Bot.on_ready()
	assert caplog.records[0].msg == (
		"Bot is in no servers! Add it to a server."
	)


@pytest.mark.parametrize(
	"content,description",
	[("e", "e"), ("", "**Embed**"), ("e" * 1025, logs.msgMaxLength)]
)
def test_contCheck(content: str, description: str) -> None:
	m = MockMessage(content)
	assert logs.contCheck(m) == description


@pytest.mark.asyncio
async def test_on_message_delete() -> None:
	m = MockMessage(channel=MockChannel(name="bb-log"))
	m.guild = MockGuild(channels=[m.channel])
	emb = await Bot.on_message_delete(m)
	log = logs.logDeleteMsg(m)
	assert emb.description == log.description
	assert log.description == (
		f"**Deleted message sent by {m.author.mention}"
		f" in **{m.channel.mention}\n{m.content}"
	)
	history = m.channel.history()
	assert any(
		(i.embeds[0].description == log.description for i in history)
	)


@pytest.mark.asyncio
async def test_on_bulk_message_delete() -> None:
	m = MockMessage(channel=MockChannel(name="bb-log"))
	m.guild = MockGuild(channels=[m.channel])
	messages = [m, m, m]
	emb = await Bot.on_bulk_message_delete(messages)
	log = logs.logPurge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == f"Purged 2 messages in {m.channel.mention}."
	history = m.channel.history()
	assert any(
		(i.embeds[0].description == log.description for i in history)
	)
	messages = [m] * 105
	emb = await Bot.on_bulk_message_delete(messages)
	log = logs.logPurge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == f"Purged 99+ messages in {m.channel.mention}."


@pytest.mark.asyncio
async def test_on_guild_channel_delete() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	channel = MockChannel(guild=g)
	emb = await Bot.on_guild_channel_delete(channel)
	log = logs.logDeleteChannel(channel)
	assert emb.description == log.description
	assert log.description == f"Channel \"{channel.name}\" deleted."
	history = g.channels[0].history()
	assert any(
		(i.embeds[0].description == log.description for i in history)
	)


@pytest.mark.asyncio
async def test_on_guild_channel_create() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	channel = MockChannel(guild=g)
	emb = await Bot.on_guild_channel_create(channel)
	log = logs.logCreateChannel(channel)
	assert emb.description == log.description
	assert log.description == f"Channel \"{channel.name}\" created."
	history = g.channels[0].history()
	assert any(
		(i.embeds[0].description == log.description for i in history)
	)


@pytest.mark.asyncio
async def test_on_member_ban() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	member = MockUser()
	emb = await Bot.on_member_ban(g, member)
	log = logs.logBan(member)
	assert emb.description == log.description
	assert log.description == f"Member {member.mention} banned\n{member.name}"
	history = g.channels[0].history()
	assert any(
		(i.embeds[0].description == log.description for i in history)
	)


@pytest.mark.asyncio
async def test_on_member_unban() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	member = MockUser()
	emb = await Bot.on_member_unban(g, member)
	log = logs.logUnban(member)
	assert emb.description == log.description
	assert (
		log.description == f"Member {member.mention} unbanned\n{member.name}"
	)
	history = g.channels[0].history()
	assert any(
		(i.embeds[0].description == log.description for i in history)
	)


@pytest.mark.asyncio
async def test_on_member_join() -> None:
	member = MockUser()
	member.guild = MockGuild(channels=[MockChannel(name="bb-log")])
	emb = await Bot.on_member_join(member)
	log = logs.logMemberJoin(member)
	assert emb.description == log.description
	assert log.description == (
		f"Member {member.mention} joined\nAccount registered"
		f" on {misc.truncTime(member)}\nID: {member.id}"
	)
	history = member.guild.channels[0].history()
	assert any(
		(i.embeds[0].description == log.description for i in history)
	)


@pytest.mark.asyncio
async def test_on_member_remove() -> None:
	member = MockUser()
	member.guild = MockGuild(channels=[MockChannel(name="bb-log")])
	emb = await Bot.on_member_remove(member)
	log = logs.logMemberRemove(member)
	assert emb.description == log.description
	assert log.description == f"Member {member.mention} left\nID: {member.id}"
	member.roles = member.guild.roles[0], member.guild.roles[0]
	emb = await Bot.on_member_remove(member)
	log = logs.logMemberRemove(member)
	assert emb.description == log.description
	assert log.fields[0].value == member.roles[1].mention
	history = member.guild.channels[0].history()
	assert any(
		(i.embeds[0].description == log.description for i in history)
	)


@pytest.mark.asyncio
async def test_on_member_update() -> None:
	guild = MockGuild(channels=[MockChannel(name="bb-log")])
	old = MockUser(nick="a", roles=[], guild=guild)
	new = MockUser(nick="b", roles=[], guild=guild)
	emb = await Bot.on_member_update(old, new)
	log = logs.logMemberNickChange(old, new)
	assert emb.description == log.description
	assert log.description == "Nickname of " + new.mention + " changed."
	assert log.fields[0].value == old.nick
	assert log.fields[1].value == new.nick
	history = guild.channels[0].history()
	assert any(
		(i.embeds[0].description == log.description for i in history)
	)

	new = MockUser(nick="a", guild=guild)
	new.roles = [new.guild.roles[0], new.guild.roles[0]]
	emb = await Bot.on_member_update(old, new)
	log = logs.logMemberRolesChange(old, new)
	assert emb.description == log.description
	assert log.description == (
		f"Role {new.roles[0].mention} added to {new.mention}."
	)

	emb = await Bot.on_member_update(new, old)
	log = logs.logMemberRolesChange(new, old)
	assert emb.description == log.description
	assert log.description == (
		f"Role {new.roles[0].mention} removed from {old.mention}."
	)


@pytest.mark.asyncio
async def test_on_message_edit() -> None:
	member = MockUser()
	g = MockGuild(
		channels=[MockChannel(name="bb-log"), MockChannel(name="infractions")]
	)
	await Bot.createMutedRole(g)
	before = MockMessage(content="old", author=member, guild=g)
	after = MockMessage(content="new", author=member, guild=g)
	emb = await Bot.on_message_edit(before, after)
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
	after.content = "http://dizcort.com free nitro!"
	emb = await Bot.on_message_edit(before, after)
	assert any(
		i.content.startswith("Deleted possible") for i in g.channels[0].history()
	)
	# TODO: edit after to have content of len > 1024 via message.edit
	assert any(
		(i.embeds[0].description == log.description for i in g.channels[0].history())
	)
	assert not any(
		i.content.startswith("http://dizcort.com") for i in g.channels[0].history()
	)


def test_logCreateThread() -> None:
	thread = MockThread()
	assert logs.logCreateThread(thread).description == (
		"Thread \"testThread\" created in parent channel <#0>."
	)


def test_logDeleteThread() -> None:
	thread = MockThread()
	assert logs.logDeleteThread(thread).description == (
		"Thread \"testThread\" deleted."
	)


def test_logThreadArchived() -> None:
	thread = MockThread()
	assert logs.logThreadArchived(thread).description == (
		"Thread \"testThread\" archived."
	)


def test_logThreadUnarchived() -> None:
	thread = MockThread()
	assert logs.logThreadUnarchived(thread).description == (
		"Thread \"testThread\" unarchived."
	)


@pytest.mark.asyncio
async def test_cmdDice() -> None:
	ch = MockChannel()
	ctx = MockContext(Bot.bot, channel=ch, guild=MockGuild(channels=[ch]))
	emb = await Bot.cmdDice(ctx)
	assert emb.description == misc.diceMsg
	assert any(
		(i.embeds[0].description == emb.description for i in ch.history())
	)


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
	assert misc.roll(text)[0] in range(1, side + 1)
	report = misc.rollReport(text, user)
	assert report.description.startswith("You got")
	assert text in report.title


def test_dice_irregular() -> None:
	user = MockUser()
	assert misc.roll("d20-4")[0] in range(-3, 17)
	assert misc.rollReport("d20-4", user).description.startswith("You got")
	assert not misc.roll("wrongroll")[0]
	assert not misc.roll("d9")[0]
	assert misc.rollReport("d9", user).description.startswith("Invalid")
	assert not misc.roll("d40")[0]
	results = misc.roll("d100+asfjksdfhkdsfhksd")
	assert results[0] in range(1, 101)
	assert results[4] == 0


@pytest.mark.parametrize("count", [-5, 1, 2, 3, 5, 100])
def test_dice_multiple(count) -> None:
	assert misc.roll(f"{count}d4")[0] in range(1, (abs(count) * 4) + 1)


def test_dice_multiple_irregular() -> None:
	assert misc.roll("10d20-4")[0] in range(6, 197)
	assert misc.roll("ad100")[0] in range(1, 101)
	assert misc.roll("0d8")[0] == 0
	assert misc.roll("0d12+57")[0] == 57


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


def test_fetchAvatar_custom() -> None:
	userId = 12121212
	member = MockUser(id=userId)
	assert member.avatar.url == (
		f"https://cdn.discordapp.com/avatars/{userId}/"
		f"{member._avatar}.png?size=1024"
	)
	assert misc.fetchAvatar(member) == member.avatar.url


def test_fetchAvatar_default() -> None:
	member = MockUser(id=5000000, customAvatar=False)
	assert member.avatar is None
	assert member.default_avatar.url == (
		f"https://cdn.discordapp.com/embed/avatars/{member.id >> 22}.png"
	)
	assert misc.fetchAvatar(member) == member.default_avatar.url


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
def test_balance(target: nextcord.User, result: str) -> None:
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
	assert isinstance(game, bucks.BlackjackGame) or "You hit 21!" in report
	bucks.reset(bb)
	report, game = bucks.blackjack(bb, 0)
	assert isinstance(game, bucks.BlackjackGame) or "You hit 21!" in report
	bucks.reset(bb)
	game = bucks.BlackjackGame(bb, "all", True)
	assert "You hit 21!" in game.message
	bucks.reset(bb)
	report, game = bucks.blackjack(bb, "10000000000000")
	assert report.startswith("You do not have")
	bb.name = ",invalidname,"
	assert bucks.blackjack(bb, "all")[0] == bucks.commaWarn.format(bb.mention)


def test_blackjack_perfect() -> None:
	game = bucks.BlackjackGame(MockUser(), 10)
	game.cards = 10, 11
	assert game.perfect()


def test_blackjack_deal() -> None:
	game = bucks.BlackjackGame(MockUser(), 10)
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
	assert bucks.BlackjackGame.cardName(10) in (
		"a 10", "a Jack", "a Queen", "a King"
	)
	assert bucks.BlackjackGame.cardName(11) == "an Ace"
	assert bucks.BlackjackGame.cardName(8) == "an 8"
	assert bucks.BlackjackGame.cardName(5) == "a 5"


def test_blackjack_checkBust() -> None:
	game = bucks.BlackjackGame(MockUser(), 10)
	game.cards = 10, 10, 10
	assert game.checkBust()


def test_blackjack_stay() -> None:
	game = bucks.BlackjackGame(MockUser(), 0)
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
	game = bucks.BlackjackGame(MockUser(), 10)
	game.cards = []
	game.message = game.startingHand()
	assert len(game.cards) == 2
	assert game.message.startswith("Your starting hand consists of ")
	assert "You hit 21!" in game.startingHand(True)
	assert "two Aces" in game.startingHand(False, True)


def test_activeGame() -> None:
	author = MockUser(name="target", id=0)
	games = [bucks.BlackjackGame(MockUser(name="not", id=1), 10)] * 9
	assert not bucks.activeGame(games, author)
	games.append(bucks.BlackjackGame(author, 10))
	assert bucks.activeGame(games, author)


def test_info() -> None:
	namedUser = MockUser("searchterm")
	guild = MockGuild(members=[MockUser(), namedUser])
	namedUser.roles = [guild.roles[0], guild.roles[0]]
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
	avatar = str(misc.fetchAvatar(namedUser))
	assert misc.av("searchterm", text).image.url == avatar
	assert misc.av("error", text).title == "Invalid target!"


@pytest.mark.asyncio
async def test_commands() -> None:
	helpCommand = misc.bbHelpCommand()
	helpCommand.context = MockContext(Bot.bot, guild=None)
	await helpCommand.send_bot_help(None)
	helpCommand.context.guild = MockGuild()
	helpCommand.context.author.guild_permissions = nextcord.Permissions(
		manage_messages=True
	)
	await helpCommand.send_bot_help(None)
	helpCommand.context.author.guild_permissions = nextcord.Permissions(
		manage_messages=False
	)
	await helpCommand.send_bot_help(None)

	h = helpCommand.context.channel.history()
	assert len(h[2].embeds[0].fields) == 15
	assert len(h[1].embeds[0].fields) == 20
	assert len(h[0].embeds[0].fields) == 17
	helpCommand.context.message.type = nextcord.MessageType.thread_created
	assert await helpCommand.send_bot_help(None) == -1


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


# TODO: switch to mock context, add test for error with quotation marks
@pytest.mark.parametrize("searchterm", ["лексика", "two words", "", " ", "/"])
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


@pytest.mark.parametrize("animalName", list(misc.animalList) + ["dog"])
def test_animal_with_goodUrl(animalName: str) -> None:
	assert goodURL(requests.get(misc.animal(animalName)))


def test_animal_dog_breed() -> None:
	breeds = misc.animal("dog", "breeds")[12:-1].split(", ")
	assert len(breeds) == 107
	assert goodURL(requests.get(misc.animal("dog", choice(breeds))))
	assert misc.animal("dog", "invalidbreed").startswith("Breed not")
	assert misc.animal("dog", "invalidbreed1234").startswith("Breed not")
	assert goodURL(requests.get(misc.animal("dog", "moose")))


def test_invalid_animal_raises_exception() -> None:
	with pytest.raises(ValueError):
		misc.animal("invalidAnimal")


@pytest.mark.asyncio
async def test_cmdMute() -> None:
	ctx = MockContext(
		Bot.bot,
		message=MockMessage(content="!mute foo"),
		author=MockUser(adminPowers=True)
	)
	# if the MemberConverter fails
	assert await Bot.cmdMute(ctx, "foo") == 0

	# if trying to mute the bot
	assert await Bot.cmdMute(
		ctx, MockUser(id=654133911558946837, guild=MockGuild()).mention
	) == 0

	# if no target
	assert await Bot.cmdMute(ctx, None) == 0

	# if no perms
	ctx.author = MockUser(adminPowers=False)
	assert await Bot.cmdMute(ctx, None) == 0

	# if not in guild
	ctx.guild = None
	assert await Bot.cmdMute(ctx, "foo") == 0
	# TODO: remaining branches


@pytest.mark.asyncio
async def test_thread_creation_does_not_invoke_commands() -> None:
	ctx = MockContext(Bot.bot, author=MockUser(), guild=MockGuild())
	ctx.message.type = nextcord.MessageType.thread_created
	for command in Bot.bot.commands:
		if command.name != "help":
			assert await command(ctx) == -1


# Tests for commands that require a Brawlhalla API key:


def test_randomBrawl() -> None:
	weapon = brawl.randomBrawl("weapon")
	assert weapon.title == "Random Weapon"
	assert (
		weapon.description.split(" ")[-1][:-2].lower()
		in weapon.thumbnail.url.lower().replace("guantlet", "gauntlet")
	)
	legend = brawl.randomBrawl("legend")
	assert legend.title == "Random Legend"
	assert legend.description.startswith("Your legend is ")
	legend = brawl.randomBrawl("legend", brawlKey)
	assert len(legend.fields) == 2
	assert legend.title == brawl.legendInfo(
		brawlKey, legend.title.split(" ")[0].lower().replace(",", "")
	).title
	assert brawl.randomBrawl("invalidrandom").title == "Brawlhalla Randomizer"


def test_fetchBrawlID() -> None:
	assert brawl.fetchBrawlId(196354892208537600) == 7032472
	assert not brawl.fetchBrawlId(654133911558946837)


def test_claimProfile() -> None:
	with open("resources/claimedProfs.json", "r") as f:
		profsLen = len(load(f))
	brawl.claimProfile(196354892208537600, 1)
	with open("resources/claimedProfs.json", "r") as f:
		assert profsLen == len(load(f))
	assert brawl.fetchBrawlId(196354892208537600) == 1
	brawl.claimProfile(196354892208537600, 7032472)
	assert brawl.fetchBrawlId(196354892208537600) == 7032472


@pytest.mark.parametrize(
	"url,result", [
		("https://steamcommunity.com/id/beardless", 7032472),
		("badurl", None),
		("https://steamcommunity.com/badurl", None)
	]
)
def test_getBrawlID(url: str, result: Optional[int]) -> None:
	sleep(2)
	assert brawl.getBrawlId(brawlKey, url) == result


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
	brawl.claimProfile(196354892208537600, 37)
	assert brawl.getRank(user, brawlKey).color.value == 16306282
	brawl.claimProfile(196354892208537600, 7032472)


def test_getLegends() -> None:
	sleep(5)
	oldLegends = brawl.fetchLegends()
	brawl.getLegends(brawlKey)
	assert brawl.fetchLegends() == oldLegends


def test_legendInfo() -> None:
	sleep(5)
	legend = brawl.legendInfo(brawlKey, "hugin")
	assert legend.title == "Munin, The Raven"
	assert legend.thumbnail.url == (
		"https://cms.brawlhalla.com/c/uploads/2021/12/a_Roster_Pose_BirdBardM.png"
	)
	legend = brawl.legendInfo(brawlKey, "teros")
	assert legend.title == "Teros, The Minotaur"
	assert legend.thumbnail.url == (
		"https://cms.brawlhalla.com/c/uploads/2021/07/teros.png"
	)
	legend = brawl.legendInfo(brawlKey, "redraptor")
	assert legend.title == "Red Raptor, The Last Sentai"
	assert legend.thumbnail.url == (
		"https://cms.brawlhalla.com/c/uploads/2023/06/a_Roster_Pose_SentaiM.png"
	)
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
	brawl.claimProfile(196354892208537600, 1247373426)
	emb = brawl.getStats(user, brawlKey)
	assert emb.description.startswith("This profile doesn't have stats")
	brawl.claimProfile(196354892208537600, 7032472)


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


def test_brawlCommands() -> None:
	sleep(5)
	assert len(brawl.brawlCommands().fields) == 6
