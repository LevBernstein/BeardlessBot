# mypy: ignore-errors
# TODO: resolve all remaining errors
"""Beardless Bot unit tests"""

import asyncio
import logging
from copy import copy
from datetime import datetime
from json import load
from os import environ, listdir, remove
from random import choice
from time import sleep
from typing import Any, Dict, Final, List, Literal, Optional, Union
from urllib.parse import quote_plus

import aiofiles
import bandit  # type: ignore
import nextcord
import pytest
import requests
import responses
from bs4 import BeautifulSoup
from dotenv import dotenv_values
from flake8.api import legacy as flake8  # type: ignore
from mypy import api
from nextcord.ext import commands

import Bot
import brawl
import bucks
import logs
import misc

imageTypes = ["image/" + i for i in ("png", "jpeg", "jpg", "gif", "webp")]

bbFiles = [f for f in listdir() if f.endswith(".py")]

# TODO: refactor away from this magic number
bbId: Final[int] = 654133911558946837


def goodURL(request: requests.models.Response) -> bool:
	return request.ok and request.headers["content-type"] in imageTypes


# TODO: add _state attribute to all mock objects, inherit from State
# Switch to a single MockState class for all Messageable objects
# Implements nextcord.state.ConnectionState

class MockHTTPClient(nextcord.http.HTTPClient):
	def __init__(
		self,
		loop: asyncio.AbstractEventLoop,
		user: Optional[nextcord.User] = None
	) -> None:
		self.loop = loop
		self.user = user
		self.user_agent = str(user)
		self.token = None
		self.proxy = None
		self.proxy_auth = None
		self._locks = {}
		self._global_over = asyncio.Event()
		self._global_over.set()

	async def create_role(
		self,
		guild_id: Union[str, int],
		reason: Optional[str] = None,
		**fields: Any
	) -> Dict[str, Any]:
		data = {key: value for key, value in fields.items()}
		data["id"] = guild_id
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
		data: Dict[str, Any] = {
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

	async def leave_guild(
		self, guild_id: nextcord.types.snowflake.Snowflake
	) -> None:
		if self.user and self.user.guild and self.user.guild.id == guild_id:
			self.user.guild = None


# MockUser class is a superset of nextcord.User with some features of
# nextcord.Member; still working on adding all features of nextcord.Member,
# at which point I will switch the parent from nextcord.User to nextcord.Member
# TODO: give default @everyone role
# TODO: move MockState out, apply to all classes, make generic
class MockUser(nextcord.User):

	class MockUserState():
		def __init__(self, messageNum: int = 0) -> None:
			self._guilds: Dict[int, nextcord.Guild] = {}
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
			assert self.channel._state._messages is not None
			self.channel._state._messages.append(message)
			return message

		def store_user(self, data: Dict[str, Any]) -> nextcord.User:
			return MockUser()

		def setClientUser(self) -> None:
			self.http.user_agent = str(self.user)

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
			self._messages: List[nextcord.Message] = []

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
			allow: Union[nextcord.Permissions, int],
			deny: Union[nextcord.Permissions, int]
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
		self.guild = guild  # type: ignore
		self.messages: List[nextcord.Message] = []
		self._type = 0
		self._state = self.MockChannelState(messageNum=len(messages))
		self._overwrites = []
		self.assignChannelToGuild(self.guild)

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
		assert self._state._messages is not None
		return list(reversed(self._state._messages))

	def assignChannelToGuild(self, guild: nextcord.Guild) -> None:
		if guild and self not in guild.channels:
			guild.channels.append(self)


# TODO: Write message.edit()
class MockMessage(nextcord.Message):

	class MockMessageState():
		def __init__(
			self, user: nextcord.User, guild: Optional[nextcord.Guild] = None
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user=user)
			self.guild = guild if guild else MockGuild()

		def get_reaction_emoji(
			self, data: Dict[str, str]
		) -> nextcord.emoji.Emoji:
			return MockEmoji(self.guild, data, MockMessage())

	def __init__(
		self,
		content: Optional[str] = "testcontent",
		author: nextcord.User = MockUser(),
		guild: Optional[nextcord.Guild] = None,
		channel: nextcord.TextChannel = MockChannel(),
		embed: Optional[nextcord.Embed] = None
	) -> None:
		self.author = author
		self.content = content if content else ""
		self.id = 123456789
		self.channel = channel
		self.type = nextcord.MessageType.default
		self.guild = guild
		self.mentions = []
		self.mention_everyone = False
		self.flags = nextcord.MessageFlags._from_value(0)
		self._state = self.MockMessageState(author, guild)
		assert self.channel._state._messages is not None
		self.channel._state._messages.append(self)

	async def delete(self) -> None:
		assert self.channel._state._messages is not None
		self.channel._state._messages.remove(self)

	@staticmethod
	def getMockReactionPayload(
		emojiName: str = "MockEmojiName", emojiId: int = 0, me: bool = False
	) -> Dict[str, Any]:
		return {"me": me, "emoji": {"id": emojiId, "name": emojiName}}


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
			user = MockUser()
			self.member_cache_flags = nextcord.MemberCacheFlags.all()
			self.self_id = 1
			self.shard_count = 1
			self.loop = asyncio.get_event_loop()
			self.user = user
			self.http = MockHTTPClient(self.loop, user=user)
			self._intents = nextcord.Intents.all()

		def is_guild_evicted(self, *args, **kwargs: Any) -> Literal[False]:
			return False

		async def chunk_guild(self, *args, **kwargs: Any) -> None:
			pass

		async def query_members(self, *args, **kwargs: Any) -> List[nextcord.Member]:
			return [self.user]

		def setUserGuild(self, guild: nextcord.Guild) -> None:
			self.user.guild = guild
			self.http.user = self.user

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

		data = await self._state.http.create_role(self.id, **fields)
		role = nextcord.Role(guild=self, data=data, state=self._state)
		self._roles[len(self.roles)] = role

		return role

	def assignGuild(self, role: nextcord.Role) -> None:
		role.guild = self

	def get_member(self, userId: int) -> Optional[nextcord.Member]:
		class MockGuildMember(nextcord.Member):
			def __init__(self, id: int) -> None:
				self.data = {"user": "foo", "roles": "0"}
				self.guild = MockGuild()
				self.state = MockUser.MockUserState()
				self._user = MockUser(id=id)
				self._client_status = {}
				self.nick = "foobar"
		return MockGuildMember(userId)

	def get_channel(self, channelId: int) -> Optional[nextcord.TextChannel]:
		return self._channels.get(channelId)

	@property
	def me(self) -> nextcord.User:
		return self._state.user


class MockThread(nextcord.Thread):
	def __init__(
		self,
		name: str = "testThread",
		owner: nextcord.User = MockUser(),
		channelId: int = 0,
		me: Optional[nextcord.Member] = None,
		parent: Optional[nextcord.TextChannel] = None,
		archived: bool = False,
		locked: bool = False
	):
		Bot.bot = MockBot(Bot.bot)
		channel = parent if parent else MockChannel(id=channelId, guild=MockGuild())
		self.guild = channel.guild
		self._state = channel._state
		self.state = self._state
		self.id = 0
		self.name = name
		self.parent_id = channel.id
		self.owner_id = owner.id
		self.archived = archived
		self.archive_timestamp = datetime.now()
		self.locked = locked
		self.message_count = 0
		self._type = 0  # type: ignore
		self.auto_archive_duration = 10080
		self.me = me
		self._members = copy(channel.guild._members)
		if self.me and Bot.bot.user is not None and not any(
			user.id == Bot.bot.user.id for user in self.members
		):
			self._members[len(self.members)] = Bot.bot.user.baseUser
		self.member_count = len(self.members)

	async def join(self):
		if not any(user.id == Bot.bot.user.id for user in self.members):
			if not any(user.id == Bot.bot.user.id for user in self.guild.members):
				self.guild._members[len(self.guild.members)] = Bot.bot.user.baseUser
			self._members[len(self.members)] = Bot.bot.user.baseUser


class MockContext(commands.Context):

	class MockContextState():
		# TODO: make context inherit state from message, as in actual Context._state
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
			assert self.channel._state._messages is not None
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
		if self.guild and channel not in self.guild.channels:
			self.guild._channels[len(self.guild.channels)] = channel
		if self.guild and author not in self.guild.members:
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

		async def send(self, data: Dict[str, Any], /) -> Dict[str, Any]:
			self.bot.status = nextcord.Status(value="online")
			self.bot.activity = data["d"]["activities"][0]
			return data

	class MockClientUser(nextcord.ClientUser):
		def __init__(self, bot: commands.Bot) -> None:
			self.baseUser = MockUser(id=bbId)
			self.baseUser.bot = True
			self._state = self.baseUser._state
			self.id = self.baseUser.id
			self.name = "testclientuser"
			self.discriminator = "0000"
			self._avatar: Union[str, nextcord.Asset, None] = (
				self.baseUser.avatar
			)
			self.bot = True
			self.verified = True
			self.mfa_enabled = False
			self.global_name = self.baseUser.global_name

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


class MockEmoji(nextcord.emoji.Emoji):
	def __init__(
		self,
		guild: nextcord.Guild,
		data: Dict[str, Any],
		stateMessage: nextcord.Message = MockMessage()
	) -> None:
		self.guild_id = guild.id
		self._state = stateMessage._state
		self._from_data(data)


brawlKey = environ.get("BRAWLKEY")
if not brawlKey:
	env = dotenv_values(".env")
	try:
		brawlKey = env["BRAWLKEY"]
	except KeyError:
		logging.warning(
			"No Brawlhalla API key. Brawlhalla-specific tests will not be run.\n"
		)


@pytest.mark.parametrize("letter", ["W", "E", "F", "I"])
def test_pep8_compliance_with_flake8_for_code_quality(letter: str) -> None:
	styleGuide = flake8.get_style_guide(ignore=["W191", "W503"])
	assert styleGuide.check_files(bbFiles).get_statistics(letter) == []


def test_full_type_checking_with_mypy_for_code_quality() -> None:
	results = api.run(bbFiles + ["--pretty"])
	assert results[0].startswith("Success: no issues found")
	assert results[1] == ""
	assert results[2] == 0


def test_no_security_vulnerabilities_with_bandit_for_code_quality() -> None:
	mgr = bandit.manager.BanditManager(
		bandit.config.BanditConfig(),
		"file",
		profile={"exclude": ["B101", "B311"]}
	)
	mgr.discover_files(bbFiles)
	mgr.run_tests()
	try:
		with open("bandit.txt", "w") as f:
			mgr.output_results(3, "LOW", "LOW", f, "txt")
		with open("bandit.txt") as f:
			results = f.read()
		assert results.splitlines()[3].endswith("No issues identified.")
	finally:
		remove("bandit.txt")


def test_mockContextChannels() -> None:
	ctx = MockContext(
		Bot.bot, channel=MockChannel(), guild=MockGuild(channels=[])
	)
	assert ctx.guild is not None
	assert ctx.channel in ctx.guild.channels


def test_mockContextMembers() -> None:
	ctx = MockContext(Bot.bot, author=MockUser(), guild=MockGuild(members=[]))
	assert ctx.guild is not None
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
		" testname#0000; Content: !mute foo; Guild: Test Guild;"
		" Type: <class 'nextcord.ext.commands.errors.MemberNotFound'>"
	)


@pytest.mark.asyncio
async def test_createMutedRole() -> None:
	g = MockGuild(roles=[])
	role = await misc.createMutedRole(g)
	assert role.name == "Muted"
	assert len(g.roles) == 1 and g.roles[0] == role


@pytest.mark.asyncio
async def test_on_ready(caplog: pytest.LogCaptureFixture) -> None:
	Bot.bot = MockBot(Bot.bot)
	assert Bot.bot.user is not None
	assert isinstance(Bot.bot.user._avatar, nextcord.Asset)
	assert Bot.bot.user._avatar.url == (
		f"https://cdn.discordapp.com/avatars/{bbId}/"
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


@pytest.mark.asyncio
async def test_on_ready_raises_exceptions(
	caplog: pytest.LogCaptureFixture
) -> None:

	def mock_raise_HTTPException(Bot: commands.Bot, activity: str) -> None:
		resp = requests.Response()
		resp.status = 404  # type: ignore
		raise nextcord.HTTPException(resp, "Bar")

	def mock_raise_FileNotFoundError(filepath: str, mode: str) -> None:
		raise FileNotFoundError()

	Bot.bot = MockBot(Bot.bot)
	Bot.bot._connection._guilds = {}
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"nextcord.ext.commands.Bot.change_presence",
			mock_raise_HTTPException
		)
		await Bot.on_ready()
		assert caplog.records[0].msg == (
			"Failed to update avatar or status!"
		)
	assert caplog.records[1].msg == (
		"Bot is in no servers! Add it to a server."
	)

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"aiofiles.open",
			mock_raise_FileNotFoundError
		)
		await Bot.on_ready()
		assert caplog.records[2].msg == (
			"Avatar file not found! Check your directory structure."
		)
	assert caplog.records[3].msg == (
		"Bot is in no servers! Add it to a server."
	)


@pytest.mark.asyncio
async def test_on_guild_join(caplog: pytest.LogCaptureFixture) -> None:
	Bot.bot = MockBot(Bot.bot)
	g = MockGuild(name="Foo", roles=[MockRole(name="Beardless Bot")])
	g._state.user = MockUser(adminPowers=True)
	await Bot.on_guild_join(g)
	emb = g.channels[0].history()[0].embeds[0]
	assert emb.title == "Hello, Foo!"
	assert emb.description == misc.joinMsg.format(g.name, "<@&123456789>")

	g._state.user = MockUser(adminPowers=False)
	g._state.setUserGuild(g)
	caplog.set_level(logging.INFO)
	await Bot.on_guild_join(g)
	emb = g.channels[0].history()[0].embeds[0]
	assert emb.title == "I need admin perms!"
	assert emb.description == misc.reasons
	assert caplog.records[3].msg == "Left Foo."


@pytest.mark.parametrize(
	"content, description",
	[("e", "e"), ("", "**Embed**"), ("e" * 1025, misc.msgMaxLength)]
)
def test_contCheck(content: str, description: str) -> None:
	assert misc.contCheck(MockMessage(content)) == description


@pytest.mark.asyncio
async def test_on_message_delete() -> None:
	m = MockMessage(channel=MockChannel(name="bb-log"))
	m.guild = MockGuild(channels=[m.channel])
	emb = await Bot.on_message_delete(m)
	assert emb is not None
	log = logs.logDeleteMsg(m)
	assert emb.description == log.description
	assert log.description == (
		"**Deleted message sent by <@123456789>"
		" in **<#123456789>\ntestcontent"
	)
	history = m.channel.history()
	assert history[0].embeds[0].description == log.description

	assert not await Bot.on_message_delete(MockMessage())


@pytest.mark.asyncio
async def test_on_bulk_message_delete() -> None:
	m = MockMessage(channel=MockChannel(name="bb-log"))
	m.guild = MockGuild(channels=[m.channel])
	messages = [m, m, m]
	emb = await Bot.on_bulk_message_delete(messages)
	assert emb is not None
	log = logs.logPurge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == "Purged 2 messages in <#123456789>."
	history = m.channel.history()
	assert history[0].embeds[0].description == log.description

	messages = [m] * 105
	emb = await Bot.on_bulk_message_delete(messages)
	assert emb is not None
	log = logs.logPurge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == "Purged 99+ messages in <#123456789>."

	assert not await Bot.on_bulk_message_delete(
		[MockMessage(guild=MockGuild())]
	)


@pytest.mark.asyncio
async def test_on_reaction_clear() -> None:
	channel = MockChannel(id=0, name="bb-log")
	guild = MockGuild(channels=[channel])
	channel.guild = guild
	reaction = nextcord.Reaction(
		message=MockMessage(), data=MockMessage.getMockReactionPayload("foo")
	)
	otherReaction = nextcord.Reaction(
		message=MockMessage(), data=MockMessage.getMockReactionPayload("bar")
	)
	msg = MockMessage(guild=guild)
	emb = await Bot.on_reaction_clear(msg, [reaction, otherReaction])
	assert emb is not None
	assert isinstance(emb.description, str)
	assert (
		emb.description.startswith(
			"Reactions cleared from message sent by"
			" <@123456789> in <#123456789>."
		)
	)
	assert emb.fields[0].value is not None
	assert emb.fields[0].value.startswith(msg.content)
	assert emb.fields[1].value is not None
	assert emb.fields[1].value == "<:foo:0>, <:bar:0>"
	assert channel.history()[0].embeds[0].description == emb.description

	assert not await Bot.on_reaction_clear(
		MockMessage(guild=MockGuild()), [reaction, otherReaction]
	)


@pytest.mark.asyncio
async def test_on_guild_channel_delete() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	channel = MockChannel(guild=g)
	emb = await Bot.on_guild_channel_delete(channel)
	assert emb is not None
	log = logs.logDeleteChannel(channel)
	assert emb.description == log.description
	assert log.description == "Channel \"testchannelname\" deleted."
	history = g.channels[0].history()
	assert history[0].embeds[0].description == log.description

	assert not await Bot.on_guild_channel_delete(MockChannel(guild=MockGuild()))


@pytest.mark.asyncio
async def test_on_guild_channel_create() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	channel = MockChannel(guild=g)
	emb = await Bot.on_guild_channel_create(channel)
	assert emb is not None
	log = logs.logCreateChannel(channel)
	assert emb.description == log.description
	assert log.description == "Channel \"testchannelname\" created."
	history = g.channels[0].history()
	assert history[0].embeds[0].description == log.description

	assert not await Bot.on_guild_channel_create(MockChannel(guild=MockGuild()))


@pytest.mark.asyncio
async def test_on_member_ban() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	member = MockUser()
	emb = await Bot.on_member_ban(g, member)
	assert emb is not None
	log = logs.logBan(member)
	assert emb.description == log.description
	assert log.description == "Member <@123456789> banned\ntestname"
	history = g.channels[0].history()
	assert history[0].embeds[0].description == log.description

	assert not await Bot.on_member_ban(MockGuild(), MockUser(guild=MockGuild()))


@pytest.mark.asyncio
async def test_on_member_unban() -> None:
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	member = MockUser()
	emb = await Bot.on_member_unban(g, member)
	assert emb is not None
	log = logs.logUnban(member)
	assert emb.description == log.description
	assert (
		log.description == "Member <@123456789> unbanned\ntestname"
	)
	history = g.channels[0].history()
	assert history[0].embeds[0].description == log.description

	assert not await Bot.on_member_unban(MockGuild(), MockUser(guild=MockGuild()))


@pytest.mark.asyncio
async def test_on_member_join() -> None:
	member = MockUser()
	member.guild = MockGuild(channels=[MockChannel(name="bb-log")])
	emb = await Bot.on_member_join(member)
	assert emb is not None
	log = logs.logMemberJoin(member)
	assert emb.description == log.description
	assert log.description == (
		"Member <@123456789> joined\nAccount registered"
		f" on {misc.truncTime(member)}\nID: 123456789"
	)
	history = member.guild.channels[0].history()
	assert history[0].embeds[0].description == log.description

	assert not await Bot.on_member_join(MockUser(guild=MockGuild()))


@pytest.mark.asyncio
async def test_on_member_remove() -> None:
	member = MockUser()
	member.guild = MockGuild(channels=[MockChannel(name="bb-log")])
	emb = await Bot.on_member_remove(member)
	assert emb is not None
	log = logs.logMemberRemove(member)
	assert emb.description == log.description
	assert log.description == "Member <@123456789> left\nID: 123456789"

	member.roles = [member.guild.roles[0], member.guild.roles[0]]
	emb = await Bot.on_member_remove(member)
	assert emb is not None
	log = logs.logMemberRemove(member)
	assert emb.description == log.description
	assert log.fields[0].value == "<@&123456789>"
	history = member.guild.channels[0].history()
	assert history[0].embeds[0].description == log.description

	assert not await Bot.on_member_remove(MockUser(guild=MockGuild()))


@pytest.mark.asyncio
async def test_on_member_update() -> None:
	guild = MockGuild(channels=[MockChannel(name="bb-log")])
	old = MockUser(nick="a", roles=[], guild=guild)
	new = MockUser(nick="b", roles=[], guild=guild)
	emb = await Bot.on_member_update(old, new)
	assert emb is not None
	log = logs.logMemberNickChange(old, new)
	assert emb.description == log.description
	assert log.description == "Nickname of <@123456789> changed."
	assert log.fields[0].value == old.nick
	assert log.fields[1].value == new.nick
	history = guild.channels[0].history()
	assert history[0].embeds[0].description == log.description

	new = MockUser(nick="a", guild=guild)
	assert new.guild is not None
	new.roles = [new.guild.roles[0], new.guild.roles[0]]
	emb = await Bot.on_member_update(old, new)
	assert emb is not None
	log = logs.logMemberRolesChange(old, new)
	assert emb.description == log.description
	assert log.description == (
		"Role <@&123456789> added to <@123456789>."
	)

	emb = await Bot.on_member_update(new, old)
	assert emb is not None
	log = logs.logMemberRolesChange(new, old)
	assert emb.description == log.description
	assert log.description == (
		"Role <@&123456789> removed from <@123456789>."
	)

	m = MockUser(guild=MockGuild())
	assert not await Bot.on_member_update(m, m)


@pytest.mark.asyncio
async def test_on_message_edit() -> None:
	member = MockUser()
	g = MockGuild(
		channels=[MockChannel(name="bb-log"), MockChannel(name="infractions")],
		roles=[]
	)
	assert g.roles == []
	before = MockMessage(content="old", author=member, guild=g)
	after = MockMessage(content="new", author=member, guild=g)

	emb = await Bot.on_message_edit(before, after)
	assert isinstance(emb, nextcord.Embed)
	log = logs.logEditMsg(before, after)
	assert emb.description == log.description
	assert emb.description == (
		"Messaged edited by <@123456789> in <#123456789>."
	)
	assert emb.fields[0].value == before.content
	assert emb.fields[1].value == (
		f"new\n[Jump to Message]({after.jump_url})"
	)

	after.content = "http://dizcort.com free nitro!"
	emb = await Bot.on_message_edit(before, after)
	assert emb is not None
	assert g.channels[0].history()[1].content.startswith("Deleted possible")
	assert len(g.roles) == 1 and g.roles[0].name == "Muted"
	# TODO: edit after to have content of len > 1024 via message.edit
	assert g.channels[0].history()[0].embeds[0].description == log.description
	assert not any(
		i.content.startswith("http://dizcort.com") for i in g.channels[0].history()
	)

	assert not await Bot.on_message_edit(MockMessage(), MockMessage())


@pytest.mark.asyncio
async def test_on_thread_join() -> None:
	channel = MockChannel(id=0, name="bb-log")
	guild = MockGuild(channels=[channel])
	channel.guild = guild
	thread = MockThread(parent=channel, me=MockUser(), name="Foo")

	assert await Bot.on_thread_join(thread) is None

	thread.me = None
	thread._members = {}
	emb = await Bot.on_thread_join(thread)
	assert len(thread.members) == 1
	assert emb is not None
	assert emb.description == (
		"Thread \"Foo\" created in parent channel <#0>."
	)
	assert channel.history()[0].embeds[0].description == emb.description

	channel.name = "bar"
	assert not await Bot.on_thread_join(
		MockThread(parent=channel, me=None, name="Foo")
	)


@pytest.mark.asyncio
async def test_on_thread_delete() -> None:
	channel = MockChannel(id=0, name="bb-log")
	guild = MockGuild(channels=[channel])
	channel.guild = guild
	thread = MockThread(parent=channel, name="Foo")

	emb = await Bot.on_thread_delete(thread)
	assert emb is not None
	assert emb.description == (
		"Thread \"Foo\" deleted."
	)
	assert channel.history()[0].embeds[0].description == emb.description

	channel.name = "bar"
	assert not await Bot.on_thread_delete(
		MockThread(parent=channel, me=MockUser(), name="Foo")
	)


@pytest.mark.asyncio
async def test_on_thread_update() -> None:
	channel = MockChannel(id=0, name="bb-log")
	guild = MockGuild(channels=[channel])
	channel.guild = guild
	before = MockThread(parent=channel, name="Foo")
	after = MockThread(parent=channel, name="Foo")

	assert await Bot.on_thread_update(before, after) is None

	before.archived = True
	before.archive_timestamp = datetime.now()
	emb = await Bot.on_thread_update(before, after)
	assert emb is not None
	assert emb.description == "Thread \"Foo\" unarchived."
	assert channel.history()[0].embeds[0].description == emb.description

	emb = await Bot.on_thread_update(after, before)
	assert emb is not None
	assert emb.description == "Thread \"Foo\" archived."
	assert channel.history()[0].embeds[0].description == emb.description

	channel.name = "bar"
	ch = MockThread(parent=channel, name="Foo")
	assert not await Bot.on_thread_update(ch, ch)


@pytest.mark.asyncio
async def test_cmdDice() -> None:
	ch = MockChannel()
	ctx = MockContext(Bot.bot, channel=ch, guild=MockGuild(channels=[ch]))
	emb = await Bot.cmdDice(ctx)  # type: ignore
	assert isinstance(emb, nextcord.Embed)
	assert emb.description == misc.diceMsg
	assert ch.history()[0].embeds[0].description == emb.description


@pytest.mark.asyncio
async def test_fact() -> None:
	async with aiofiles.open("resources/facts.txt") as f:
		lines = (await f.read()).splitlines()
	assert misc.fact() in lines
	ch = MockChannel()
	ctx = MockContext(Bot.bot, channel=ch, guild=MockGuild(channels=[ch]))
	assert await Bot.cmdFact(ctx) == 1
	assert ch.history()[0].embeds[0].description in lines


def test_tweet() -> None:
	eggTweet = misc.tweet()
	assert ("\n" + eggTweet).startswith(misc.formattedTweet(eggTweet))
	assert "." not in misc.formattedTweet("test tweet.")
	assert "." not in misc.formattedTweet("test tweet")
	tweetLen = len(eggTweet.split(" "))
	assert 11 <= tweetLen <= 37


@pytest.mark.parametrize("side", [4, 6, 8, 10, 12, 20, 100])
def test_dice_regular(side: int) -> None:
	user = MockUser()
	text = "d" + str(side)
	assert misc.roll(text)[0] in range(1, side + 1)
	report = misc.rollReport(text, user)
	assert isinstance(report.description, str)
	assert report.description.startswith("You got")
	assert isinstance(report.title, str)
	assert text in report.title


def test_dice_irregular() -> None:
	user = MockUser()
	assert misc.roll("d20-4")[0] in range(-3, 17)
	emb = misc.rollReport("d20-4", user)
	assert isinstance(emb.description, str)
	assert emb.description.startswith("You got")

	assert not misc.roll("wrongroll")[0]

	assert not misc.roll("d9")[0]

	emb = misc.rollReport("d9", user)
	assert isinstance(emb.description, str)
	assert emb.description.startswith("Invalid")

	assert not misc.roll("d40")[0]

	results = misc.roll("d100+asfjksdfhkdsfhksd")
	assert len(results) == 5
	assert results[0] in range(1, 101)
	assert results[4] == 0


@pytest.mark.parametrize("count", [-5, 1, 2, 3, 5, 100])
def test_dice_multiple(count) -> None:
	assert misc.roll(str(count) + "d4")[0] in range(1, (abs(count) * 4) + 1)


def test_dice_multiple_irregular() -> None:
	assert misc.roll("10d20-4")[0] in range(6, 197)
	assert misc.roll("ad100")[0] in range(1, 101)
	assert misc.roll("0d8")[0] == 0
	assert misc.roll("0d12+57")[0] == 57


def test_logMute() -> None:
	message = MockMessage()
	member = MockUser()
	assert logs.logMute(member, message, "5", "hours", 18000).description == (
		"Muted <@123456789> for 5 hours in <#123456789>."
	)
	assert logs.logMute(member, message, None, None, None).description == (
		"Muted <@123456789> in <#123456789>."
	)


def test_logUnmute() -> None:
	member = MockUser()
	assert logs.logUnmute(member, MockUser()).description == (
		"Unmuted <@123456789>."
	)


def test_getLogChannel() -> None:
	assert not misc.getLogChannel(MockGuild())
	ch = misc.getLogChannel(
		MockGuild(channels=[MockChannel(name="bb-log")])
	)
	assert isinstance(ch, nextcord.TextChannel) and ch.name == "bb-log"


def test_fetchAvatar_custom() -> None:
	userId = 12121212
	member = MockUser(id=userId)
	assert isinstance(member.avatar, nextcord.Asset)
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
	"username, content", [
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
	bb = MockUser("Beardless Bot", "Beardless Bot", "5757", bbId)
	bucks.reset(bb)
	assert bucks.register(bb).description == (
		"You are already in the system! Hooray! You"
		f" have 200 BeardlessBucks, <@{bbId}>."
	)
	bb.name = ",badname,"
	assert bucks.register(bb).description == (
		bucks.commaWarn.format(f"<@{bbId}>")
	)


@pytest.mark.parametrize(
	"target, result", [
		(MockUser("Test", "", "5757", bbId), "'s balance is"),
		(MockUser(","), bucks.commaWarn.format("<@123456789>")),
		("Invalid user", "Invalid user!")
	]
)
def test_balance(target: nextcord.User, result: str) -> None:
	msg = MockMessage("!bal", guild=MockGuild())
	desc = bucks.balance(target, msg).description
	assert isinstance(desc, str) and result in desc


def test_reset() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", "5757", bbId)
	assert bucks.reset(bb).description == (
		f"You have been reset to 200 BeardlessBucks, <@{bbId}>."
	)
	bb.name = ",badname,"
	assert bucks.reset(bb).description == bucks.commaWarn.format(f"<@{bbId}>")


def test_writeMoney() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", "5757", bbId)
	bucks.reset(bb)
	assert bucks.writeMoney(bb, "-all", False, False) == (0, 200)
	assert bucks.writeMoney(bb, -1000000, True, False) == (-2, None)


def test_leaderboard() -> None:
	lb = bucks.leaderboard()

	assert lb.title == "BeardlessBucks Leaderboard"
	fields = lb.fields
	if len(fields) >= 2:  # This check in case of an empty leaderboard
		assert fields[0].value is not None and fields[1].value is not None
		assert int(fields[0].value) > int(fields[1].value)

	lb = bucks.leaderboard(MockUser(name="bad,name", id=0), MockMessage())
	assert len(lb.fields) == len(fields)

	lb = bucks.leaderboard(
		MockUser("Beardless Bot", "Beardless Bot", "5757", bbId),
		MockMessage()
	)
	assert len(lb.fields) == len(fields) + 2


@responses.activate
def test_define_valid() -> None:
	responses.get(
		"https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		json=[
			{
				"word": "foo",
				"phonetics": [{"audio": "spam"}],
				"meanings": [{"definitions": [{"definition": "Foobar"}]}]
			}
		]
	)
	word = misc.define("foo")
	assert word.title == "FOO" and word.description == "Audio: spam"


@responses.activate
def test_define_no_audio_has_blank_description() -> None:
	responses.get(
		"https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		json=[
			{
				"word": "foo",
				"phonetics": [],
				"meanings": [{"definitions": [{"definition": "Foobar"}]}]
			}
		]
	)
	word = misc.define("foo")
	assert word.title == "FOO" and word.description == ""


@responses.activate
def test_define_invalid_word_returns_no_results_found() -> None:
	responses.get(
		"https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		status=404
	)
	assert misc.define("foo").description == "No results found."


@responses.activate
def test_define_api_down_returns_error_message() -> None:
	responses.get(
		"https://api.dictionaryapi.dev/api/v2/entries/en_US/test",
		status=400
	)
	word = misc.define("test")
	assert isinstance(word.description, str)
	assert word.description.startswith("There was an error")


@responses.activate
@pytest.mark.asyncio
async def test_cmdDefine() -> None:
	Bot.bot = MockBot(Bot.bot)
	ctx = MockContext(Bot.bot, message=MockMessage("!define f"))

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"misc.define",
			"raise Exception"
		)
		assert await Bot.cmdDefine(ctx, "f") == 0
	assert ctx.channel.history()[0].content.startswith("The API I use to get")

	resp = [{"word": "f", "phonetics": [], "meanings": [{"definitions": []}]}]
	responses.get(
		"https://api.dictionaryapi.dev/api/v2/entries/en_US/f", json=resp
	)
	assert await Bot.cmdDefine(ctx, "f") == 1
	emb = ctx.channel.history()[0].embeds[0]
	assert emb.title == misc.define("f").title == "F"


def test_flip() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", "5757", bbId)

	assert bucks.flip(bb, "0").endswith("actually bet anything.")

	assert bucks.flip(bb, "invalidbet").startswith("Invalid bet.")

	bucks.reset(bb)
	bucks.flip(bb, "all")
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(balMsg.description, str)
	assert ("400" in balMsg.description or "0" in balMsg.description)

	bucks.reset(bb)
	bucks.flip(bb, "100")
	assert bucks.flip(bb, "10000000000000").startswith("You do not have")
	bucks.reset(bb)
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(balMsg.description, str) and "200" in balMsg.description

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"bucks.writeMoney",
			lambda *x: (2, 0)
		)
		assert bucks.flip(bb, "0") == bucks.newUserMsg.format(f"<@{bbId}>")

	bb.name = ",invalidname,"
	assert bucks.flip(bb, "0") == bucks.commaWarn.format(f"<@{bbId}>")


@pytest.mark.asyncio
async def test_cmdFlip() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", "5757", bbId)
	Bot.bot = MockBot(Bot.bot)
	ctx = MockContext(Bot.bot, author=bb, message=MockMessage("!flip 0"))
	Bot.games = []

	assert await Bot.cmdFlip(ctx, "0") == 1
	emb = ctx.channel.history()[0].embeds[0]
	assert emb.description.endswith("actually bet anything.")

	Bot.games.append(bucks.BlackjackGame(bb, 10))
	assert await Bot.cmdFlip(ctx, "0") == 1
	emb = ctx.channel.history()[0].embeds[0]
	assert emb.description == bucks.finMsg.format(f"<@{bbId}>")


def test_blackjack() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", "5757", bbId)

	assert bucks.blackjack(bb, "invalidbet")[0].startswith("Invalid bet.")

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"bucks.BlackjackGame.perfect",
			lambda x: False
		)
		report, game = bucks.blackjack(bb, 0)
		assert isinstance(game, bucks.BlackjackGame)
		assert "You hit 21!" not in report

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"bucks.BlackjackGame.perfect",
			lambda x: True
		)
		report, game = bucks.blackjack(bb, "0")
		assert game is None and "You hit 21" in report

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"bucks.writeMoney",
			lambda *x: (2, 0)
		)
		assert bucks.blackjack(bb, "0")[0] == (
			bucks.newUserMsg.format(f"<@{bbId}>")
		)

	bucks.reset(bb)
	report = bucks.blackjack(bb, "10000000000000")[0]
	assert report.startswith("You do not have")

	bucks.reset(bb)
	bb.name = ",invalidname,"
	assert bucks.blackjack(bb, 0)[0] == bucks.commaWarn.format(f"<@{bbId}>")


@pytest.mark.asyncio
async def test_cmdBlackjack() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", "5757", bbId)
	Bot.bot = MockBot(Bot.bot)
	ctx = MockContext(Bot.bot, author=bb, message=MockMessage("!blackjack 0"))
	Bot.games = []

	assert await Bot.cmdBlackjack(ctx, "all") == 1
	emb = ctx.channel.history()[0].embeds[0]
	assert emb.description.startswith("Your starting hand consists of")

	Bot.games.append(bucks.BlackjackGame(bb, 10))
	assert await Bot.cmdBlackjack(ctx, "0") == 1
	emb = ctx.channel.history()[0].embeds[0]
	assert emb.description == bucks.finMsg.format(f"<@{bbId}>")


def test_blackjack_perfect() -> None:
	game = bucks.BlackjackGame(MockUser(), 10)
	game.cards = [10, 11]
	assert game.perfect()


@pytest.mark.asyncio
async def test_cmdDeal() -> None:
	Bot.games = []
	bb = MockUser("Beardless,Bot", "Beardless Bot", "5757", bbId)
	ctx = MockContext(Bot.bot, author=bb, message=MockMessage("!hit"))
	assert await Bot.cmdDeal(ctx) == 1
	emb = ctx.channel.history()[0].embeds[0]
	assert emb.description == bucks.commaWarn.format(f"<@{bbId}>")

	bb.name = "Beardless Bot"
	assert await Bot.cmdDeal(ctx) == 1
	emb = ctx.channel.history()[0].embeds[0]
	assert emb.description == bucks.noGameMsg.format(f"<@{bbId}>")

	game = bucks.BlackjackGame(bb, 0)
	game.cards = [2, 2]
	Bot.games = []
	Bot.games.append(game)
	assert await Bot.cmdDeal(ctx) == 1
	emb = ctx.channel.history()[0].embeds[0]
	assert len(game.cards) == 3
	assert emb.description.startswith("You were dealt")

	game.cards = [10, 10, 10]
	assert await Bot.cmdDeal(ctx) == 1
	emb = ctx.channel.history()[0].embeds[0]
	assert f"You busted. Game over, <@{bbId}>." in emb.description
	assert len(Bot.games) == 0

	# TODO: use monkeypatch to force a perfect
	# game = bucks.BlackjackGame(bb, 0)
	# game.cards = [10, 10]
	# Bot.games.append(game)
	# ...
	# assert f"You hit 21! You win, <@{bbId}>!" in emb.description
	# assert len(Bot.games) == 0


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

	game.cards = [10, 10, 10]
	assert game.checkBust()

	game.cards = [3, 4]
	assert not game.checkBust()


def test_blackjack_stay() -> None:
	game = bucks.BlackjackGame(MockUser(), 0)

	game.cards = [10, 10, 1]
	game.dealerSum = 25
	assert game.stay() == 1

	game.dealerSum = 20
	assert game.stay() == 1
	game.deal()
	assert game.stay() == 1

	game.cards = [10, 10]
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
	assert namedUserInfo.fields[2].value == "<@&123456789>"
	assert misc.info("!infoerror", text).title == "Invalid target!"


def test_av() -> None:
	namedUser = MockUser("searchterm")
	guild = MockGuild(members=[MockUser(), namedUser])
	text = MockMessage("!av searchterm", guild=guild)
	avatar = str(misc.fetchAvatar(namedUser))
	assert misc.av("searchterm", text).image.url == avatar
	assert misc.av("error", text).title == "Invalid target!"
	assert misc.av(namedUser, text).image.url == avatar
	text.guild = None
	text.author = namedUser
	assert misc.av("searchterm", text).image.url == avatar


@pytest.mark.asyncio
async def test_bbHelpCommand() -> None:
	helpCommand = misc.bbHelpCommand()
	helpCommand.context = MockContext(Bot.bot, guild=None)
	await helpCommand.send_bot_help({})
	helpCommand.context.guild = MockGuild()
	helpCommand.context.author.guild_permissions = nextcord.Permissions(
		manage_messages=True
	)
	await helpCommand.send_bot_help({})
	helpCommand.context.author.guild_permissions = nextcord.Permissions(
		manage_messages=False
	)
	await helpCommand.send_bot_help({})

	h = helpCommand.context.channel.history()
	assert len(h[2].embeds[0].fields) == 15
	assert len(h[1].embeds[0].fields) == 20
	assert len(h[0].embeds[0].fields) == 17
	helpCommand.context.message.type = nextcord.MessageType.thread_created
	assert await helpCommand.send_bot_help({}) == -1

	# For the time being, just pass on all invalid help calls
	assert not await helpCommand.send_error_message("Foo")


def test_pingMsg() -> None:
	assert (
		brawl.pingMsg("<@200>", 1, 1, 1)
		.endswith("You can ping again in 1 hour, 1 minute, and 1 second.")
	)
	assert (
		brawl.pingMsg("<@200", 2, 2, 2)
		.endswith("You can ping again in 2 hours, 2 minutes, and 2 seconds.")
	)


def test_scamCheck() -> None:
	assert misc.scamCheck("http://dizcort.com free nitro!")
	assert misc.scamCheck("@everyone http://didcord.gg free nitro!")
	assert misc.scamCheck("gift nitro http://d1zcordn1tr0.co.uk free!")
	assert misc.scamCheck("hey @everyone check it! http://discocl.com/ nitro!")
	assert not misc.scamCheck(
		"Hey Discord friends, check out https://top.gg/bot/" + str(bbId)
	)
	assert not misc.scamCheck(
		"Here's an actual gift link https://discord.gift/s23d35fls55d13l1fjds"
	)


# TODO: switch to mock context, add test for error with quotation marks
@pytest.mark.parametrize(
	"searchterm", ["лексика", "spaced words", "/", "'", "''", "'foo'", "\\\""]
)
def test_search_valid(searchterm: str) -> None:
	url = "https://www.google.com/search?q=" + quote_plus(searchterm)
	assert url == misc.search(searchterm).description
	r = requests.get(url, timeout=10)
	assert r.ok
	assert next(
		BeautifulSoup(r.content, "html.parser").stripped_strings
	) == searchterm + " - Google Search"


@pytest.mark.parametrize(
	"searchterm, title", [("", "Google"), (" ", "- Google Search")]
)
def test_search_irregular(searchterm: str, title: str) -> None:
	url = "https://www.google.com/search?q=" + quote_plus(searchterm)
	assert url == misc.search(searchterm).description
	r = requests.get(url, timeout=10)
	assert r.ok
	assert next(
		BeautifulSoup(r.content, "html.parser").stripped_strings
	) == title


@pytest.mark.parametrize("animalName", list(misc.animalList) + ["dog"])
def test_animal_with_goodUrl(animalName: str) -> None:
	assert goodURL(requests.get(misc.animal(animalName), timeout=10))


def test_animal_dog_breed() -> None:
	breeds = misc.animal("dog", "breeds")[12:-1].split(", ")
	assert len(breeds) == 107
	assert goodURL(
		requests.get(misc.animal("dog", choice(breeds)), timeout=10)
	)
	assert misc.animal("dog", "invalidbreed").startswith("Breed not")
	assert misc.animal("dog", "invalidbreed1234").startswith("Breed not")
	assert goodURL(requests.get(misc.animal("dog", "moose"), timeout=10))


def test_invalid_animal_throws_exception() -> None:
	with pytest.raises(ValueError):
		misc.animal("invalidAnimal")


@responses.activate
def test_dog_api_down_throws_exception(
	caplog: pytest.LogCaptureFixture
) -> None:
	responses.get(
		"https://dog.ceo/api/breeds/image/random",
		status=522
	)

	with pytest.raises(requests.exceptions.RequestException):
		misc.animal("dog")

	assert len(caplog.records) == 9
	assert caplog.records[8].msg == "Dog API trying again, call 9"


@responses.activate
def test_getFrogList_standard_layout() -> None:
	responses.get(
		"https://github.com/a9-i/frog/tree/main/ImgSetOpt",
		body=(
			b"<!DOCTYPE html><html><script>{\"payload\":{\"tree\":{\"items\":"
			b"[{\"name\":\"0\"}]}}}</script></html>"
		)
	)

	frogs = misc.getFrogList()
	assert len(frogs) == 1
	assert frogs[0]["name"] == "0"


@responses.activate
def test_getFrogList_alt_layout() -> None:
	responses.get(
		"https://github.com/a9-i/frog/tree/main/ImgSetOpt",
		body=(
			b"<!DOCTYPE html><html><script>{\"payload\":{\"tree\":{\"items\":"
			b"[{\"name\":\"0\\\"}]}}}</script><script>{}</script></html>"
		)
	)

	frogs = misc.getFrogList()
	assert len(frogs) == 1
	assert frogs[0]["name"] == "0\\"


@pytest.mark.asyncio
async def test_handleMessages() -> None:
	Bot.bot = MockBot(Bot.bot)
	u = MockUser()
	u.bot = True
	m = MockMessage(author=u)

	assert await Bot.handleMessages(m) == -1

	u.bot = False
	m.guild = None
	assert await Bot.handleMessages(m) == -1

	assert await Bot.handleMessages(MockMessage(guild=MockGuild())) == 1

	u = MockUser(name="bar", roles=[])
	g = MockGuild(members=[u], channels=[MockChannel(name="infractions")])
	m = MockMessage(
		content="http://dizcort.com free nitro!", guild=g, author=u
	)
	assert len(u.roles) == 0
	assert len(g.channels[0].history()) == 0
	assert await Bot.handleMessages(m) == -1
	assert len(u.roles) == 1
	assert len(g.channels[0].history()) == 1


@pytest.mark.asyncio
async def test_cmdGuide() -> None:
	Bot.bot = MockBot(Bot.bot)
	ctx = MockContext(Bot.bot, author=MockUser())
	ctx.message.type = nextcord.MessageType.default

	assert await Bot.cmdGuide(ctx) == 0

	ctx.guild.id = 442403231864324119
	assert await Bot.cmdGuide(ctx) == 1
	assert ctx.history()[0].embeds[0].title == "The Eggsoup Improvement Guide"


@pytest.mark.asyncio
async def test_cmdMute() -> None:
	Bot.bot = MockBot(Bot.bot)
	ctx = MockContext(
		Bot.bot,
		message=MockMessage(content="!mute foo"),
		author=MockUser(adminPowers=True)
	)

	# if the MemberConverter fails
	assert await Bot.cmdMute(ctx, "foo") == 0

	# if trying to mute the bot
	assert await Bot.cmdMute(
		ctx, MockUser(id=bbId, guild=MockGuild()).mention
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
	Bot.bot = MockBot(Bot.bot)
	ctx = MockContext(Bot.bot, author=MockUser(), guild=MockGuild())
	ctx.message.type = nextcord.MessageType.thread_created
	for command in Bot.bot.commands:
		if command.name != "help":
			assert await command(ctx) == -1


@responses.activate
def test_getRank_monkeypatched_for_2s_top_rating() -> None:
	responses.get(
		"https://api.brawlhalla.com/player/1/ranked?api_key=" + str(brawlKey),
		json={
			"name": "Foo",
			"region": "us-east-1",
			"rating": 0,
			"2v2": [
				{
					"teamname": "Foo+Bar",
					"tier": "Platinum 3",
					"rating": 1812,
					"peak_rating": 1812,
					"wins": 1,
					"games": 2
				}
			]
		}
	)

	try:
		brawl.claimProfile(196354892208537600, 1)
		emb = brawl.getRank(MockUser(id=196354892208537600), brawlKey)
		assert emb.fields[0].name == "Ranked 2s"
		assert isinstance(emb.fields[0].value, str)
		assert emb.fields[0].value.startswith("**Foo+Bar")
		assert emb.fields[0].value.endswith("50.0% winrate")
		assert emb.color.value == 20916
	finally:
		brawl.claimProfile(196354892208537600, 7032472)


# Tests for commands that require a Brawlhalla API key:

if brawlKey:
	def test_randomBrawl() -> None:
		weapon = brawl.randomBrawl("weapon")
		assert weapon is not None
		assert weapon.title == "Random Weapon"
		assert weapon.thumbnail.url is not None
		assert weapon.description is not None
		assert (
			weapon.description.split(" ")[-1][:-2].lower()
			in weapon.thumbnail.url.lower().replace("guantlet", "gauntlet")
		)

		legend = brawl.randomBrawl("legend")
		assert legend is not None
		assert legend.title == "Random Legend"
		assert legend.description is not None
		assert legend.description.startswith("Your legend is ")

		legend = brawl.randomBrawl("legend", brawlKey)
		assert legend is not None
		assert len(legend.fields) == 2
		assert legend.title is not None
		assert legend.title == brawl.legendInfo(  # type: ignore
			brawlKey, legend.title.split(" ")[0].lower().replace(",", "")
		).title

		assert brawl.randomBrawl("invalidrandom").title == "Brawlhalla Randomizer"

	def test_fetchBrawlID() -> None:
		assert brawl.fetchBrawlId(196354892208537600) == 7032472
		assert not brawl.fetchBrawlId(bbId)

	def test_claimProfile() -> None:
		with open("resources/claimedProfs.json") as f:
			profsLen = len(load(f))
		try:
			brawl.claimProfile(196354892208537600, 1)
			with open("resources/claimedProfs.json") as f:
				assert profsLen == len(load(f))
			assert brawl.fetchBrawlId(196354892208537600) == 1
		finally:
			brawl.claimProfile(196354892208537600, 7032472)
			assert brawl.fetchBrawlId(196354892208537600) == 7032472

	@pytest.mark.parametrize(
		"url, result", [
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
		try:
			brawl.claimProfile(196354892208537600, 37)
			assert brawl.getRank(user, brawlKey).color.value == 16306282
		finally:
			brawl.claimProfile(196354892208537600, 7032472)

	def test_getLegends() -> None:
		sleep(5)
		oldLegends = brawl.fetchLegends()
		brawl.getLegends(brawlKey)
		assert brawl.fetchLegends() == oldLegends

	def test_legendInfo() -> None:
		sleep(5)
		legend = brawl.legendInfo(brawlKey, "hugin")

		assert legend is not None
		assert legend.title == "Munin, The Raven"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/2021/12/a_Roster_Pose_BirdBardM.png"
		)

		legend = brawl.legendInfo(brawlKey, "teros")
		assert legend is not None
		assert legend.title == "Teros, The Minotaur"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/2021/07/teros.png"
		)

		legend = brawl.legendInfo(brawlKey, "redraptor")
		assert legend is not None
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
		try:
			brawl.claimProfile(196354892208537600, 7032472)
			emb = brawl.getStats(user, brawlKey)
			assert emb.footer.text == "Brawl ID 7032472"
			assert len(emb.fields) in (3, 4)
			brawl.claimProfile(196354892208537600, 1247373426)
			emb = brawl.getStats(user, brawlKey)
			assert emb.description is not None
			assert emb.description.startswith("This profile doesn't have stats")
		finally:
			brawl.claimProfile(196354892208537600, 7032472)

	def test_getClan() -> None:
		sleep(5)
		user = MockUser(id=0)
		assert brawl.getClan(user, brawlKey).description == (
			brawl.unclaimed.format(user.mention)
		)
		user.id = 196354892208537600
		try:
			brawl.claimProfile(196354892208537600, 7032472)
			assert brawl.getClan(
				user, brawlKey
			).title == "DinersDriveInsDives"
			brawl.claimProfile(196354892208537600, 5895238)
			assert brawl.getClan(
				user, brawlKey
			).description == "You are not in a clan!"
		finally:
			brawl.claimProfile(196354892208537600, 7032472)

	def test_brawlCommands() -> None:
		sleep(5)
		assert len(brawl.brawlCommands().fields) == 6
