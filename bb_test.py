"""Beardless Bot unit tests"""

import asyncio
import logging
import typing
from collections import deque
from collections.abc import Iterator
from copy import copy
from datetime import datetime
from json import load
from os import environ, listdir
from random import choice
from time import sleep

import aiofiles
import httpx
import nextcord
import pytest
import requests
import responses
from aiohttp import ClientWebSocketResponse
from bandit.core.config import BanditConfig  # type: ignore
from bandit.core.manager import BanditManager  # type: ignore
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
bbId: typing.Final[int] = 654133911558946837

messageable = typing.Union[
	nextcord.TextChannel,
	nextcord.Thread,
	nextcord.DMChannel,
	nextcord.PartialMessageable,
	nextcord.VoiceChannel,
	nextcord.StageChannel,
	nextcord.GroupChannel
]

channelTypes = typing.Union[
	nextcord.StageChannel,
	nextcord.VoiceChannel,
	nextcord.TextChannel,
	nextcord.CategoryChannel,
	nextcord.ForumChannel,
	None
]

iconTypes = typing.Union[
	bytes, nextcord.Asset, nextcord.Attachment, nextcord.File, None
]


def goodURL(
	resp: typing.Union[requests.models.Response, httpx.Response]
) -> bool:
	return (
		200 <= resp.status_code < 400
		and resp.headers["content-type"] in imageTypes
	)


# TODO: add _state attribute to all mock objects, inherit from State
# Switch to a single MockState class for all Messageable objects
# Implements nextcord.state.ConnectionState

class MockHTTPClient(nextcord.http.HTTPClient):
	def __init__(
		self,
		loop: asyncio.AbstractEventLoop,
		user: typing.Optional[nextcord.User] = None
	) -> None:
		self.loop = loop
		self.user = user
		self.user_agent = str(user)
		self.token = None
		self.proxy = None
		self.proxy_auth = None
		self._locks = {}  # type: ignore
		self._global_over = asyncio.Event()
		self._global_over.set()

	async def create_role(  # type: ignore
		self,
		guild_id: typing.Union[str, int],
		reason: typing.Optional[str] = None,
		**fields: typing.Any
	) -> dict[str, typing.Any]:
		data = dict(fields)
		data["id"] = guild_id
		data["name"] = fields["name"] if "name" in fields else "TestRole"
		return data

	async def send_message(  # type: ignore
		self,
		channel_id: typing.Union[str, int],
		content: typing.Optional[str] = None,
		*,
		tts: bool = False,
		embed: typing.Optional[nextcord.Embed] = None,
		embeds: typing.Optional[list[nextcord.Embed]] = None,
		nonce: typing.Union[int, str, None] = None,
		allowed_mentions: typing.Optional[nextcord.AllowedMentions] = None,
		message_reference: typing.Optional[nextcord.MessageReference] = None,
		stickers: typing.Optional[list[int]] = None,
		components: typing.Optional[list[nextcord.Component]] = None,
		flags: typing.Optional[int] = None
	) -> dict[str, typing.Any]:
		data: dict[str, typing.Any] = {
			"attachments": [],
			"edited_timestamp": None,
			"type": nextcord.Message,
			"pinned": False,
			"mention_everyone": (
				"@everyone" in content
			) if content else False,
			"tts": tts,
			"author": MockUser(),
			"content": content or ""
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
		self, guild_id: typing.Union[str, int]
	) -> None:
		if self.user and self.user.guild and self.user.guild.id == guild_id:
			self.user.guild = None


# MockUser class is a superset of nextcord.User with some features of
# nextcord.Member.
# TODO: separate into MockUser and MockMember
# TODO: give default @everyone role
# TODO: move MockState out, apply to all classes, make generic
class MockUser(nextcord.User):

	class MockUserState(nextcord.state.ConnectionState):
		def __init__(self, messageNum: int = 0) -> None:
			self._guilds: dict[int, nextcord.Guild] = {}
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop)
			self.user = None
			self.last_message_id = messageNum
			self.channel = MockChannel()

		def create_message(
			self,
			*,
			channel: nextcord.abc.Messageable,
			data: dict[str, typing.Any]  # type: ignore
		) -> nextcord.Message:
			data["id"] = self.last_message_id
			self.last_message_id += 1
			message = nextcord.Message(
				state=self, channel=channel, data=data  # type: ignore
			)
			assert self.channel._state._messages is not None
			self.channel._state._messages.append(message)
			return message

		def store_user(
			self,
			data: dict[str, typing.Any]  # type: ignore
		) -> nextcord.User:
			return MockUser()

		def _get_private_channel_by_user(  # type: ignore
			self, user_id: typing.Optional[int]
		) -> nextcord.TextChannel:
			return self.channel

	def __init__(
		self,
		name: str = "testname",
		nick: str = "testnick",
		discriminator: str = "0000",
		id: int = 123456789,
		roles: typing.Optional[list[nextcord.Role]] = None,
		guild: typing.Optional[nextcord.Guild] = None,
		customAvatar: bool = True,
		adminPowers: bool = False,
		messages: typing.Optional[list[nextcord.Message]] = None
	) -> None:
		self.name = name
		self.global_name = name
		self.nick = nick
		self.id = id
		self.discriminator = discriminator
		self.bot = False
		self.roles = roles if roles is not None else []
		self.joined_at = self.created_at
		self.activity = None
		self.system = False
		self.messages = messages if messages is not None else []
		self.guild = guild
		self._public_flags = 0
		self._state = self.MockUserState(messageNum=len(self.messages))
		self._avatar = (
			"7b6ea511d6e0ef6d1cdb2f7b53946c03" if customAvatar else None
		)
		self.setUserState()
		self.guild_permissions = (
			nextcord.Permissions.all()
			if adminPowers
			else nextcord.Permissions.none()
		)

	def setUserState(self) -> None:
		self._state.user = self
		self._state.http.user_agent = str(self)

	@typing.no_type_check
	def history(self) -> Iterator[nextcord.Message]:
		return self._state.channel.history()

	async def add_roles(self, role: nextcord.Role) -> None:
		self.roles.append(role)


class MockChannel(nextcord.TextChannel):

	class MockChannelState(nextcord.state.ConnectionState):
		def __init__(
			self,
			user: typing.Optional[nextcord.User] = None,
			messageNum: int = 0
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.user = user
			self.last_message_id = messageNum
			self._messages: deque[nextcord.Message] = deque()

		def create_message(
			self,
			*,
			channel: messageable,
			data: dict[str, typing.Any]  # type: ignore
		) -> nextcord.Message:
			data["id"] = self.last_message_id
			self.last_message_id += 1
			message = nextcord.Message(
				state=self,
				channel=channel,
				data=data  # type: ignore
			)
			self._messages.append(message)
			return message

		def store_user(
			self,
			data: dict  # type: ignore
		) -> nextcord.User:
			return self.user or MockUser()

	def __init__(
		self,
		name: str = "testchannelname",
		guild: typing.Optional[nextcord.Guild] = None,
		messages: typing.Optional[list[nextcord.Message]] = None,
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
		self.messages = messages if messages is not None else []
		self._type = 0
		self._state = self.MockChannelState(messageNum=len(self.messages))
		self._overwrites = []
		self.assignChannelToGuild(self.guild)

	@typing.overload
	async def set_permissions(
		self,
		target: typing.Union[nextcord.Member, nextcord.Role],
		*,
		overwrite: typing.Optional[nextcord.PermissionOverwrite] = ...,
		reason: typing.Optional[str] = ...,
	) -> None:
		...

	@typing.overload
	async def set_permissions(
		self,
		target: typing.Union[nextcord.Member, nextcord.Role],
		*,
		reason: typing.Optional[str] = ...,
		**permissions: bool,
	) -> None:
		...

	async def set_permissions(
		self,
		target: typing.Union[nextcord.Member, nextcord.Role],
		*,
		reason: typing.Optional[str] = None,
		**kwargs: typing.Any,
	) -> None:
		overwrite = kwargs.pop("overwrite", None)
		permissions: dict[str, bool] = kwargs
		if overwrite is None and len(permissions) != 0:
			overwrite = nextcord.PermissionOverwrite(**permissions)
		if overwrite is not None:
			allow, deny = overwrite.pair()
			payload = {
				"id": target.id,
				"type": 0 if isinstance(target, nextcord.Role) else 1,
				"allow": allow.value,
				"deny": deny.value
			}
			self._overwrites.append(
				nextcord.abc._Overwrites(payload)  # type: ignore
			)
		else:
			for overwrite in self._overwrites:
				if overwrite["id"] == target.id:
					self._overwrites.remove(overwrite)

	def history(self) -> Iterator[nextcord.Message]:  # type: ignore
		assert self._state._messages is not None
		return iter(reversed(self._state._messages))

	def assignChannelToGuild(self, guild: nextcord.Guild) -> None:
		if guild and self not in guild.channels:
			guild.channels.append(self)


# TODO: Write message.edit()
class MockMessage(nextcord.Message):

	class MockMessageState(nextcord.state.ConnectionState):
		def __init__(
			self,
			user: nextcord.User,
			guild: typing.Optional[nextcord.Guild] = None
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user=user)
			self.guild = guild or MockGuild()

		def get_reaction_emoji(
			self, data: dict[str, str]
		) -> nextcord.emoji.Emoji:
			return MockEmoji(self.guild, data, MockMessage())

	def __init__(
		self,
		content: typing.Optional[str] = "testcontent",
		author: typing.Optional[nextcord.User] = None,
		guild: typing.Optional[nextcord.Guild] = None,
		channel: typing.Optional[nextcord.TextChannel] = None,
		embeds: typing.Optional[list[nextcord.Embed]] = None,
		embed: typing.Optional[nextcord.Embed] = None
	) -> None:
		self.author = author or MockUser()
		self.content = content or ""
		self.id = 123456789
		self.channel = channel or MockChannel()
		self.type = nextcord.MessageType.default
		self.guild = guild
		self.mentions = []
		self.embeds = embeds or ([embed] if embed is not None else [])
		self.mention_everyone = False
		self.flags = nextcord.MessageFlags._from_value(0)  # type: ignore
		self._state = self.MockMessageState(self.author, guild)
		assert self.channel._state._messages is not None
		self.channel._state._messages.append(self)

	async def delete(self, *, delay: typing.Optional[float] = None) -> None:
		assert self.channel._state._messages is not None
		self.channel._state._messages.remove(self)

	@staticmethod
	def getMockReactionPayload(
		emojiName: str = "MockEmojiName", emojiId: int = 0, me: bool = False
	) -> dict[str, typing.Any]:
		return {"me": me, "emoji": {"id": emojiId, "name": emojiName}}


# TODO: switch to guild.MockRole(*kwargs) factory method:
# return role, add to _roles
class MockRole(nextcord.Role):
	def __init__(
		self,
		name: str = "Test Role",
		id: int = 123456789,
		permissions: typing.Union[int, nextcord.Permissions] = 1879573680
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

	class MockGuildState(nextcord.state.ConnectionState):
		def __init__(self) -> None:
			user = MockUser()
			self.member_cache_flags = nextcord.MemberCacheFlags.all()
			self.shard_count = 1
			self.loop = asyncio.get_event_loop()
			self.user = user
			self.http = MockHTTPClient(self.loop, user=user)
			self._intents = nextcord.Intents.all()

		def is_guild_evicted(
			self, guild: nextcord.Guild
		) -> typing.Literal[False]:
			return False

		async def chunk_guild(
			self,
			guild: nextcord.Guild,
			wait: bool = True,
			cache: typing.Any = None
		) -> None:
			pass

		async def query_members(
			self,
			guild: nextcord.Guild,
			query: typing.Optional[str],
			limit: int,
			user_ids: typing.Optional[list[int]],
			cache: bool,
			presences: bool
		) -> list[nextcord.Member]:
			return [self.user]

		def setUserGuild(self, guild: nextcord.Guild) -> None:
			assert self.user is not None
			self.user.guild = guild
			self.http.user = self.user

	def __init__(
		self,
		members: typing.Optional[list[nextcord.User]] = None,
		name: str = "Test Guild",
		id: int = 0,
		channels: typing.Optional[list[nextcord.TextChannel]] = None,
		roles: typing.Optional[list[nextcord.Role]] = None
	) -> None:
		self.name = name
		self.id = id
		self._state = self.MockGuildState()
		self._members = dict(
			enumerate(
				members if members is not None else [MockUser(), MockUser()]
			)
		)
		self._member_count = len(self._members)
		self._channels = dict(
			enumerate(channels if channels is not None else [MockChannel()])
		)
		self._roles = dict(
			enumerate(roles if roles is not None else [MockRole()])
		)
		self.owner_id = 123456789
		for role in self._roles.values():
			self.assignGuild(role)

	@typing.overload
	async def create_role(
		self,
		*,
		reason: typing.Optional[str] = ...,
		name: str = ...,
		permissions: nextcord.Permissions = ...,
		colour: typing.Union[nextcord.Colour, int] = ...,
		hoist: bool = ...,
		mentionable: bool = ...,
		icon: typing.Union[str, iconTypes] = ...
	) -> nextcord.Role:
		...

	@typing.overload
	async def create_role(
		self,
		*,
		reason: typing.Optional[str] = ...,
		name: str = ...,
		permissions: nextcord.Permissions = ...,
		color: typing.Union[nextcord.Colour, int] = ...,
		hoist: bool = ...,
		mentionable: bool = ...,
		icon: typing.Union[str, iconTypes] = ...
	) -> nextcord.Role:
		...

	async def create_role(
		self,
		*,
		name: str = "",
		permissions: typing.Optional[nextcord.Permissions] = None,
		color: typing.Union[nextcord.Colour, int] = 0,
		colour: typing.Union[nextcord.Colour, int] = 0,
		hoist: bool = False,
		mentionable: bool = False,
		icon: typing.Union[str, iconTypes] = None,
		reason: typing.Optional[str] = None
	) -> nextcord.Role:
		col = color or colour or nextcord.Colour.default()
		perms = permissions or nextcord.Permissions.none()
		fields = {
			"name": name,
			"permissions": str(perms.value),
			"mentionable": mentionable,
			"hoist": hoist,
			"colour": col if isinstance(col, int) else col.value
		}

		data = await self._state.http.create_role(
			self.id, reason=None, **fields
		)
		role = nextcord.Role(guild=self, data=data, state=self._state)
		self._roles[len(self.roles)] = role

		return role

	def assignGuild(self, role: nextcord.Role) -> None:
		role.guild = self

	def get_member(self, userId: int) -> typing.Optional[nextcord.Member]:
		class MockGuildMember(nextcord.Member):
			def __init__(self, id: int):
				self.data = {"user": "foo", "roles": "0"}
				self.guild = MockGuild()
				self.state = MockUser.MockUserState()
				self._user = MockUser(id=id)
				self._client_status = {}
				self.nick = "foobar"
		return MockGuildMember(userId)

	def get_channel(self, channelId: int) -> channelTypes:
		return self._channels.get(channelId)

	@property
	def me(self) -> nextcord.Member:
		return self._state.user


class MockThread(nextcord.Thread):
	def __init__(
		self,
		name: str = "testThread",
		owner: typing.Optional[nextcord.User] = None,
		channelId: int = 0,
		me: typing.Optional[nextcord.Member] = None,
		parent: typing.Optional[nextcord.TextChannel] = None,
		archived: bool = False,
		locked: bool = False
	):
		Bot.bot = MockBot(Bot.bot)
		channel = parent or MockChannel(
			id=channelId, guild=MockGuild()
		)
		self.guild = channel.guild
		self._state = channel._state
		self.state = self._state
		self.id = 0
		self.name = name
		self.parent_id = channel.id
		self.owner_id = (owner or MockUser()).id
		self.archived = archived
		self.archive_timestamp = datetime.now()
		self.locked = locked
		self.message_count = 0
		self._type = 0  # type: ignore
		self.auto_archive_duration = 10080
		self.me = me  # type: ignore
		self._members = copy(channel.guild._members)  # type: ignore
		if self.me and Bot.bot.user is not None and not any(
			user.id == Bot.bot.user.id for user in self.members
		):
			self._members[
				len(self.members)
			] = Bot.bot.user.baseUser  # type: ignore
		self.member_count = len(self.members)

	async def join(self) -> None:
		assert Bot.bot.user is not None
		if not any(user.id == Bot.bot.user.id for user in self.members):
			if not any(
				user.id == Bot.bot.user.id for user in self.guild.members
			):
				self.guild._members[
					len(self.guild.members)
				] = Bot.bot.user.baseUser
			self._members[len(self.members)] = Bot.bot.user.baseUser


class MockContext(misc.botContext):

	class MockContextState(nextcord.state.ConnectionState):
		# TODO: make context inherit state from message,
		# as in actual Context._state
		def __init__(
			self,
			user: typing.Optional[nextcord.User] = None,
			channel: typing.Optional[nextcord.TextChannel] = None
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.user = user  # type: ignore
			self.channel = channel or MockChannel()
			self.message = MockMessage()

		def create_message(
			self,
			*,
			channel: messageable,
			data: dict[str, typing.Any]  # type: ignore
		) -> nextcord.Message:
			data["id"] = self.channel._state.last_message_id
			self.channel._state.last_message_id += 1
			message = nextcord.Message(
				state=self,
				channel=channel,
				data=data  # type: ignore
			)
			assert self.channel._state._messages is not None
			self.channel._state._messages.append(message)
			return message

		def store_user(
			self,
			data: dict  # type: ignore
		) -> nextcord.User:
			return self.user or MockUser()

	def __init__(
		self,
		bot: commands.Bot,
		message: typing.Optional[nextcord.Message] = None,
		channel: typing.Optional[nextcord.TextChannel] = None,
		author: typing.Optional[nextcord.User] = None,
		guild: typing.Optional[nextcord.Guild] = None
	) -> None:
		self.bot = bot
		self.prefix = str(bot.command_prefix) if bot.command_prefix else "!"
		self.message = message or MockMessage()
		self.channel = channel or MockChannel()
		self.author = author or MockUser()
		self.guild = guild
		if self.guild and self.channel not in self.guild.channels:
			self.guild._channels[len(self.guild.channels)] = self.channel
		if self.guild and self.author not in self.guild.members:
			self.guild._members[len(self.guild.members)] = self.author
		self._state = self.MockContextState(channel=self.channel)
		self.invoked_with = None

	@typing.no_type_check
	def history(self) -> Iterator[nextcord.Message]:
		return self._state.channel.history()


class MockBot(commands.Bot):

	class MockBotWebsocket(nextcord.gateway.DiscordWebSocket):

		PRESENCE = 3

		def __init__(
			self,
			socket: ClientWebSocketResponse,
			*,
			loop: typing.Optional[asyncio.AbstractEventLoop] = None,
			_connection: nextcord.state.ConnectionState
		) -> None:
			self.loop = loop or asyncio.get_event_loop()
			self._connection = _connection

		@property
		def latency(self) -> float:
			return 0.025

	class MockClientUser(nextcord.ClientUser):
		def __init__(self, bot: commands.Bot) -> None:
			self.baseUser = MockUser(id=bbId)
			self.baseUser.bot = True
			self._state = self.baseUser._state
			self.id = self.baseUser.id
			self.name = "testclientuser"
			self.discriminator = "0000"
			self._avatar: typing.Union[str, nextcord.Asset, None] = (
				self.baseUser.avatar  # type: ignore
			)
			self.bot = True
			self.verified = True
			self.mfa_enabled = False
			self.global_name = self.baseUser.global_name

		async def edit(
			self,
			username: str = "",
			avatar: iconTypes = None
		) -> nextcord.ClientUser:
			self.name = username or self.name
			self._avatar = str(avatar)
			return self

	def __init__(self, bot: commands.Bot) -> None:
		self._connection = bot._connection
		self.activity = None
		self._connection.user = self.MockClientUser(self)
		self.command_prefix = bot.command_prefix
		self.case_insensitive = bot.case_insensitive
		self._help_command = bot.help_command
		self._intents = bot.intents
		self.owner_id = bot.owner_id
		self.status = nextcord.Status.offline
		self._connection._guilds = {1: MockGuild()}
		self.all_commands = bot.all_commands
		self.ws = self.MockBotWebsocket(
			None,  # type: ignore
			_connection=bot._connection
		)

	async def change_presence(
		self,
		*,
		activity: typing.Optional[nextcord.BaseActivity] = None,
		status: typing.Optional[str] = None,
		since: float = 0.0
	) -> None:
		self.activity = activity  # type: ignore
		self.status = nextcord.Status.online


class MockEmoji(nextcord.emoji.Emoji):
	def __init__(
		self,
		guild: nextcord.Guild,
		data: dict[str, typing.Any],
		stateMessage: typing.Optional[nextcord.Message] = None
	) -> None:
		self.guild_id = guild.id
		self._state = (stateMessage or MockMessage())._state
		self._from_data(data)  # type: ignore


if not (brawlKey := environ.get("BRAWLKEY")):
	env = dotenv_values(".env")
	try:
		brawlKey = env["BRAWLKEY"]
	except KeyError:
		logging.warning(
			"No Brawlhalla API key. Brawlhalla-"
			"specific tests will not be run.\n"
		)


# Run code quality tests with pytest -vk quality
@pytest.mark.parametrize("letter", ["W", "E", "F", "I", "B"])
def test_pep8_compliance_with_flake8_for_code_quality(letter: str) -> None:
	styleGuide = flake8.get_style_guide(ignore=["W191", "W503"])
	assert styleGuide.check_files(bbFiles).get_statistics(letter) == []


def test_full_type_checking_with_mypy_for_code_quality() -> None:
	results = api.run(bbFiles + ["--strict"])
	# assert results[0].startswith("Success: no issues found")
	errors = [
		i for i in results[0].split("\n")
		if ": error: " in i and "\"__call__\" of \"Command\"" not in i
	]
	assert len(errors) <= 67
	# TODO: After switching from MockUser to MockMember, bring this to 0.
	# Also remove majority of # type: ignores
	assert results[1] == ""
	# assert results[2] == 0


def test_no_security_vulnerabilities_with_bandit_for_code_quality() -> None:
	mgr = BanditManager(
		BanditConfig(), "file", profile={"exclude": ["B101", "B311"]}
	)
	mgr.discover_files(bbFiles)
	mgr.run_tests()
	# Cast to List[str] for the sake of reporting
	assert [str(i) for i in mgr.results] == []


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
		author=MockUser(adminPowers=True),
		guild=MockGuild()
	)
	ctx.invoked_with = "mute"
	assert await Bot.cmdMute(ctx, "foo") == 0
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
	assert Bot.bot.status == nextcord.Status.online
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

	def mock_raise_HTTPException(
		Bot: commands.Bot, activity: nextcord.Game
	) -> None:
		resp = requests.Response()
		resp.status = 404  # type: ignore
		raise nextcord.HTTPException(resp, str(Bot) + str(activity))

	def mock_raise_FileNotFoundError(filepath: str, mode: str) -> None:
		raise FileNotFoundError()

	Bot.bot = MockBot(Bot.bot)
	Bot.bot._connection._guilds = {}
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"bb_test.MockBot.change_presence", mock_raise_HTTPException
		)
		await Bot.on_ready()
		assert caplog.records[0].msg == (
			"Failed to update avatar or status!"
		)
	assert caplog.records[1].msg == (
		"Bot is in no servers! Add it to a server."
	)

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("aiofiles.open", mock_raise_FileNotFoundError)
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
	ch = MockChannel()
	g = MockGuild(
		name="Foo", roles=[MockRole(name="Beardless Bot")], channels=[ch]
	)
	g._state.user = MockUser(adminPowers=True)
	await Bot.on_guild_join(g)
	emb = next(ch.history()).embeds[0]
	assert emb.title == "Hello, Foo!"
	assert emb.description == misc.joinMsg.format(g.name, "<@&123456789>")

	g._state.user = MockUser(adminPowers=False)
	g._state.setUserGuild(g)  # type: ignore
	caplog.set_level(logging.INFO)
	await Bot.on_guild_join(g)
	emb = next(ch.history()).embeds[0]
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
	ch = MockChannel(name="bb-log")
	m = MockMessage(channel=ch)
	m.guild = MockGuild(channels=[ch])
	emb = await Bot.on_message_delete(m)
	assert emb is not None
	log = logs.logDeleteMsg(m)
	assert emb.description == log.description
	assert log.description == (
		"**Deleted message sent by <@123456789>"
		" in **<#123456789>\ntestcontent"
	)
	assert next(ch.history()).embeds[0].description == log.description

	assert not await Bot.on_message_delete(MockMessage())


@pytest.mark.asyncio
async def test_on_bulk_message_delete() -> None:
	ch = MockChannel(name="bb-log")
	m = MockMessage(channel=ch)
	m.guild = MockGuild(channels=[ch])
	messages = [m, m, m]
	emb = await Bot.on_bulk_message_delete(messages)  # type: ignore
	assert emb is not None
	log = logs.logPurge(messages[0], messages)  # type: ignore
	assert emb.description == log.description
	assert log.description == "Purged 2 messages in <#123456789>."
	assert next(ch.history()).embeds[0].description == log.description

	messages = [m] * 105
	emb = await Bot.on_bulk_message_delete(messages)  # type: ignore
	assert emb is not None
	log = logs.logPurge(messages[0], messages)  # type: ignore
	assert emb.description == log.description
	assert log.description == "Purged 99+ messages in <#123456789>."

	assert not await Bot.on_bulk_message_delete(
		[MockMessage(guild=MockGuild())]
	)


@pytest.mark.asyncio
async def test_on_reaction_clear() -> None:
	ch = MockChannel(id=0, name="bb-log")
	guild = MockGuild(channels=[ch])
	ch.guild = guild
	reaction = nextcord.Reaction(
		message=MockMessage(),
		data=MockMessage.getMockReactionPayload("foo")  # type: ignore
	)
	otherReaction = nextcord.Reaction(
		message=MockMessage(),
		data=MockMessage.getMockReactionPayload("bar")  # type: ignore
	)
	msg = MockMessage(guild=guild)
	emb = await Bot.on_reaction_clear(msg, [reaction, otherReaction])
	assert emb is not None
	assert isinstance(emb.description, str)
	assert emb.description.startswith(
		"Reactions cleared from message sent by <@123456789> in <#123456789>."
	)

	assert emb.fields[0].value is not None
	assert emb.fields[0].value.startswith(msg.content)
	assert emb.fields[1].value == "<:foo:0>, <:bar:0>"
	assert next(ch.history()).embeds[0].description == emb.description

	assert not await Bot.on_reaction_clear(
		MockMessage(guild=MockGuild()), [reaction, otherReaction]
	)


@pytest.mark.asyncio
async def test_on_guild_channel_delete() -> None:
	ch = MockChannel(name="bb-log")
	g = MockGuild(channels=[ch])
	newChannel = MockChannel(guild=g)
	emb = await Bot.on_guild_channel_delete(newChannel)
	assert emb is not None
	log = logs.logDeleteChannel(newChannel)
	assert emb.description == log.description
	assert log.description == "Channel \"testchannelname\" deleted."
	assert next(ch.history()).embeds[0].description == log.description

	assert not await Bot.on_guild_channel_delete(
		MockChannel(guild=MockGuild())
	)


@pytest.mark.asyncio
async def test_on_guild_channel_create() -> None:
	ch = MockChannel(name="bb-log")
	g = MockGuild(channels=[ch])
	newChannel = MockChannel(guild=g)
	emb = await Bot.on_guild_channel_create(newChannel)
	assert emb is not None
	log = logs.logCreateChannel(newChannel)
	assert emb.description == log.description
	assert log.description == "Channel \"testchannelname\" created."
	assert next(ch.history()).embeds[0].description == log.description

	assert not await Bot.on_guild_channel_create(
		MockChannel(guild=MockGuild())
	)


@pytest.mark.asyncio
async def test_on_member_ban() -> None:
	ch = MockChannel(name="bb-log")
	g = MockGuild(channels=[ch])
	member = MockUser()
	emb = await Bot.on_member_ban(g, member)
	assert emb is not None
	log = logs.logBan(member)
	assert emb.description == log.description
	assert log.description == "Member <@123456789> banned\ntestname"
	assert next(ch.history()).embeds[0].description == log.description

	assert not await Bot.on_member_ban(
		MockGuild(), MockUser(guild=MockGuild())
	)


@pytest.mark.asyncio
async def test_on_member_unban() -> None:
	ch = MockChannel(name="bb-log")
	g = MockGuild(channels=[ch])
	member = MockUser()
	emb = await Bot.on_member_unban(g, member)
	assert emb is not None
	log = logs.logUnban(member)
	assert emb.description == log.description
	assert (
		log.description == "Member <@123456789> unbanned\ntestname"
	)
	assert next(ch.history()).embeds[0].description == log.description

	assert not await Bot.on_member_unban(
		MockGuild(), MockUser(guild=MockGuild())
	)


@pytest.mark.asyncio
async def test_on_member_join() -> None:
	member = MockUser()
	ch = MockChannel(name="bb-log")
	member.guild = MockGuild(channels=[ch])
	emb = await Bot.on_member_join(member)
	assert emb is not None
	log = logs.logMemberJoin(member)
	assert emb.description == log.description
	assert log.description == (
		"Member <@123456789> joined\nAccount registered"
		f" on {misc.truncTime(member)}\nID: 123456789"
	)
	assert next(ch.history()).embeds[0].description == log.description

	assert not await Bot.on_member_join(MockUser(guild=MockGuild()))


@pytest.mark.asyncio
async def test_on_member_remove() -> None:
	member = MockUser()
	ch = MockChannel(name="bb-log")
	member.guild = MockGuild(channels=[ch])
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
	assert next(ch.history()).embeds[0].description == log.description

	assert not await Bot.on_member_remove(MockUser(guild=MockGuild()))


@pytest.mark.asyncio
async def test_on_member_update() -> None:
	ch = MockChannel(name="bb-log")
	guild = MockGuild(channels=[ch])
	old = MockUser(nick="a", roles=[], guild=guild)
	new = MockUser(nick="b", roles=[], guild=guild)
	emb = await Bot.on_member_update(old, new)
	assert emb is not None
	log = logs.logMemberNickChange(old, new)
	assert emb.description == log.description
	assert log.description == "Nickname of <@123456789> changed."
	assert log.fields[0].value == old.nick
	assert log.fields[1].value == new.nick
	assert next(ch.history()).embeds[0].description == log.description

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
	ch = MockChannel(name="bb-log")
	member = MockUser()
	g = MockGuild(
		channels=[ch, MockChannel(name="infractions")],
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

	assert len(g.roles) == 1 and g.roles[0].name == "Muted"
	# TODO: edit after to have content of len > 1024 via message.edit
	h = ch.history()
	assert next(h).embeds[0].description == log.description
	assert next(h).content.startswith("Deleted possible")
	assert not any(
		i.content.startswith("http://dizcort.com") for i in ch.history()
	)

	assert not await Bot.on_message_edit(MockMessage(), MockMessage())


@pytest.mark.asyncio
async def test_on_thread_join() -> None:
	ch = MockChannel(id=0, name="bb-log")
	guild = MockGuild(channels=[ch])
	ch.guild = guild
	thread = MockThread(parent=ch, me=MockUser(), name="Foo")
	assert await Bot.on_thread_join(thread) is None

	thread.me = None
	thread._members = {}
	emb = await Bot.on_thread_join(thread)
	assert len(thread.members) == 1
	assert emb is not None
	assert emb.description == (
		"Thread \"Foo\" created in parent channel <#0>."
	)
	assert next(ch.history()).embeds[0].description == emb.description

	ch.name = "bar"
	assert not await Bot.on_thread_join(
		MockThread(parent=ch, me=None, name="Foo")
	)


@pytest.mark.asyncio
async def test_on_thread_delete() -> None:
	ch = MockChannel(id=0, name="bb-log")
	guild = MockGuild(channels=[ch])
	ch.guild = guild
	thread = MockThread(parent=ch, name="Foo")
	emb = await Bot.on_thread_delete(thread)
	assert emb is not None
	assert emb.description == (
		"Thread \"Foo\" deleted."
	)
	assert next(ch.history()).embeds[0].description == emb.description

	ch.name = "bar"
	assert not await Bot.on_thread_delete(
		MockThread(parent=ch, me=MockUser(), name="Foo")
	)


@pytest.mark.asyncio
async def test_on_thread_update() -> None:
	ch = MockChannel(id=0, name="bb-log")
	guild = MockGuild(channels=[ch])
	ch.guild = guild
	before = MockThread(parent=ch, name="Foo")
	after = MockThread(parent=ch, name="Foo")
	assert await Bot.on_thread_update(before, after) is None

	before.archived = True
	before.archive_timestamp = datetime.now()
	emb = await Bot.on_thread_update(before, after)
	assert emb is not None
	assert emb.description == "Thread \"Foo\" unarchived."
	assert next(ch.history()).embeds[0].description == emb.description

	emb = await Bot.on_thread_update(after, before)
	assert emb is not None
	assert emb.description == "Thread \"Foo\" archived."
	assert next(ch.history()).embeds[0].description == emb.description

	ch.name = "bar"
	th = MockThread(parent=ch, name="Foo")
	assert not await Bot.on_thread_update(th, th)


@pytest.mark.asyncio
async def test_cmdDice() -> None:
	ch = MockChannel()
	ctx = MockContext(Bot.bot, channel=ch, guild=MockGuild(channels=[ch]))
	emb: nextcord.Embed = await Bot.cmdDice(ctx)
	assert isinstance(emb, nextcord.Embed)
	assert emb.description == misc.diceMsg
	assert next(ch.history()).embeds[0].description == emb.description


@pytest.mark.asyncio
async def test_fact() -> None:
	async with aiofiles.open("resources/facts.txt") as f:
		lines = (await f.read()).splitlines()
	assert misc.fact() in lines
	ch = MockChannel()
	ctx = MockContext(Bot.bot, channel=ch, guild=MockGuild(channels=[ch]))
	assert await Bot.cmdFact(ctx) == 1
	assert next(ch.history()).embeds[0].description in lines


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
def test_dice_multiple(count: int) -> None:
	assert misc.roll(str(count) + "d4")[0] in range(1, (abs(count) * 4) + 1)


def test_dice_multiple_irregular() -> None:
	assert misc.roll("10d20-4")[0] in range(6, 197)

	assert misc.roll("ad100")[0] in range(1, 101)

	assert misc.roll("0d8")[0] == 0

	assert misc.roll("0d12+57")[0] == 57


def test_logMute() -> None:
	message = MockMessage(channel=MockChannel(id=1))
	member = MockUser(id=2)
	assert logs.logMute(member, message, "5", "hours", 18000).description == (
		"Muted <@2> for 5 hours in <#1>."
	)

	assert logs.logMute(member, message, None, None, None).description == (
		"Muted <@2> in <#1>."
	)


def test_logUnmute() -> None:
	member = MockUser(id=3)
	assert logs.logUnmute(member, MockUser()).description == "Unmuted <@3>."


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
		content=content, guild=MockGuild(members=[MockUser(), namedUser])
	)
	assert misc.memSearch(text, content) == namedUser


def test_memSearch_invalid() -> None:
	namedUser = MockUser("searchterm", "testnick", "9999")
	text = MockMessage(
		content="invalidterm",
		guild=MockGuild(members=[MockUser(), namedUser])
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
		(MockUser("Test", "", "5757", bbId), "'s balance is 200"),
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


@pytest.mark.asyncio
async def test_define_valid(  # type: ignore
	httpx_mock
) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		json=[
			{
				"word": "foo",
				"phonetics": [{"audio": "spam"}],
				"meanings": [{"definitions": [{"definition": "Foobar"}]}]
			}
		]
	)
	word = await misc.define("foo")
	assert word.title == "FOO" and word.description == "Audio: spam"


@pytest.mark.asyncio
async def test_define_no_audio_has_blank_description(  # type: ignore
	httpx_mock
) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		json=[
			{
				"word": "foo",
				"phonetics": [],
				"meanings": [{"definitions": [{"definition": "Foobar"}]}]
			}
		]
	)
	word = await misc.define("foo")
	assert word.title == "FOO" and word.description == ""


@pytest.mark.asyncio
async def test_define_invalid_word_returns_no_results_found(  # type: ignore
	httpx_mock
) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		status_code=404
	)
	emb = await misc.define("foo")
	assert emb.description == "No results found."


@pytest.mark.asyncio
async def test_define_api_down_returns_error_message(  # type: ignore
	httpx_mock
) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/test",
		status_code=400
	)
	word = await misc.define("test")
	assert isinstance(word.description, str)
	assert word.description.startswith("There was an error")


@pytest.mark.asyncio
async def test_cmdDefine(  # type: ignore
	httpx_mock
) -> None:
	Bot.bot = MockBot(Bot.bot)
	ch = MockChannel()
	ctx = MockContext(
		Bot.bot,
		message=MockMessage("!define f"),
		channel=ch,
		guild=MockGuild()
	)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("misc.define", "raise Exception")
		assert await Bot.cmdDefine(ctx, "f") == 0  # type: ignore
	assert next(ch.history()).content.startswith("The API I use to get")

	resp = [{"word": "f", "phonetics": [], "meanings": [{"definitions": []}]}]
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/f", json=resp
	)
	assert await Bot.cmdDefine(ctx, "f") == 1
	emb = next(ch.history()).embeds[0]
	definition = await misc.define("f")
	assert emb.title == definition.title == "F"


def test_flip() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", "5757", bbId)
	assert bucks.flip(bb, "0").endswith("actually bet anything.")

	assert bucks.flip(bb, "invalidbet").startswith("Invalid bet.")

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda x, y: 0)
		assert bucks.flip(bb, "all") == (
			"Tails! You lose! Your losses have been"
			f" deducted from your balance, <@{bbId}>."
		)
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(balMsg.description, str)
	assert "is 0" in balMsg.description

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda x, y: 0)
		bucks.flip(bb, 37)
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(balMsg.description, str)
	assert "is 163" in balMsg.description

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda x, y: 1)
		assert bucks.flip(bb, "all") == (
			"Heads! You win! Your winnings have been"
			f" added to your balance, <@{bbId}>."
		)
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(balMsg.description, str)
	assert "is 400" in balMsg.description

	bucks.reset(bb)
	bucks.flip(bb, "100")
	assert bucks.flip(bb, "10000000000000").startswith("You do not have")
	bucks.reset(bb)
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(balMsg.description, str) and "200" in balMsg.description

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.writeMoney", lambda *x: (2, 0))
		assert bucks.flip(bb, "0") == bucks.newUserMsg.format(f"<@{bbId}>")

	bb.name = ",invalidname,"
	assert bucks.flip(bb, "0") == bucks.commaWarn.format(f"<@{bbId}>")


@pytest.mark.asyncio
async def test_cmdFlip() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", "5757", bbId)
	Bot.bot = MockBot(Bot.bot)
	ch = MockChannel()
	ctx = MockContext(Bot.bot, MockMessage("!flip 0"), ch, bb, MockGuild())
	Bot.games = []
	assert await Bot.cmdFlip(ctx, "0") == 1  # type: ignore
	emb = next(ch.history()).embeds[0]
	assert emb.description is not None
	assert emb.description.endswith("actually bet anything.")

	Bot.games.append(bucks.BlackjackGame(bb, 10))
	assert await Bot.cmdFlip(ctx, "0") == 1
	emb = next(ch.history()).embeds[0]
	assert emb.description == bucks.finMsg.format(f"<@{bbId}>")


def test_blackjack() -> None:
	bb = MockUser("Beardless Bot", "Beardless Bot", "5757", bbId)
	assert bucks.blackjack(bb, "invalidbet")[0].startswith("Invalid bet.")

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.BlackjackGame.perfect", lambda x: False)
		report, game = bucks.blackjack(bb, 0)
		assert isinstance(game, bucks.BlackjackGame)
		assert "You hit 21!" not in report

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.BlackjackGame.perfect", lambda x: True)
		report, game = bucks.blackjack(bb, "0")
		assert game is None and "You hit 21" in report

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.writeMoney", lambda *x: (2, 0))
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
	ch = MockChannel()
	Bot.bot = MockBot(Bot.bot)
	ctx = MockContext(
		Bot.bot, MockMessage("!blackjack 0"), ch, bb, MockGuild()
	)
	Bot.games = []
	assert await Bot.cmdBlackjack(ctx, "all") == 1  # type: ignore
	emb = next(ch.history()).embeds[0]
	assert emb.description is not None
	assert emb.description.startswith("Your starting hand consists of")

	Bot.games.append(bucks.BlackjackGame(bb, 10))
	assert await Bot.cmdBlackjack(ctx, "0") == 1
	emb = next(ch.history()).embeds[0]
	assert emb.description is not None
	assert emb.description == bucks.finMsg.format(f"<@{bbId}>")


def test_blackjack_perfect() -> None:
	game = bucks.BlackjackGame(MockUser(), 10)
	game.cards = [10, 11]
	assert game.perfect()


@pytest.mark.asyncio
async def test_cmdDeal() -> None:
	Bot.games = []
	bb = MockUser("Beardless,Bot", "Beardless Bot", "5757", bbId)
	ch = MockChannel()
	ctx = MockContext(Bot.bot, MockMessage("!hit"), ch, bb, MockGuild())
	assert await Bot.cmdDeal(ctx) == 1
	emb = next(ch.history()).embeds[0]
	assert emb.description == bucks.commaWarn.format(f"<@{bbId}>")

	bb.name = "Beardless Bot"
	assert await Bot.cmdDeal(ctx) == 1
	emb = next(ch.history()).embeds[0]
	assert emb.description == bucks.noGameMsg.format(f"<@{bbId}>")

	game = bucks.BlackjackGame(bb, 0)
	game.cards = [2, 2]
	Bot.games = []
	Bot.games.append(game)
	assert await Bot.cmdDeal(ctx) == 1
	emb = next(ch.history()).embeds[0]
	assert len(game.cards) == 3
	assert emb.description is not None
	assert emb.description.startswith("You were dealt")

	game.cards = [10, 10, 10]
	assert await Bot.cmdDeal(ctx) == 1
	emb = next(ch.history()).embeds[0]
	assert emb.description is not None
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
	ch = MockChannel()
	helpCommand.context = MockContext(Bot.bot, guild=None, channel=ch)
	await helpCommand.send_bot_help({})

	helpCommand.context.guild = MockGuild()
	helpCommand.context.author.guild_permissions = (  # type: ignore
		nextcord.Permissions(manage_messages=True)
	)
	await helpCommand.send_bot_help({})

	helpCommand.context.author.guild_permissions = (  # type: ignore
		nextcord.Permissions(manage_messages=False)
	)
	await helpCommand.send_bot_help({})

	h = ch.history()
	assert len(next(h).embeds[0].fields) == 17
	assert len(next(h).embeds[0].fields) == 20
	assert len(next(h).embeds[0].fields) == 15

	helpCommand.context.message.type = nextcord.MessageType.thread_created
	assert await helpCommand.send_bot_help({}) == -1

	# For the time being, just pass on all invalid help calls
	assert not await helpCommand.send_error_message("Foo")  # type: ignore


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
	assert misc.scamCheck(
		"hey @everyone check it! http://discocl.com/ nitro!"
	)
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
	url = misc.search(searchterm).description
	assert isinstance(url, str)
	r = requests.get(url, timeout=10)
	assert r.ok
	assert next(
		BeautifulSoup(r.content, "html.parser").stripped_strings
	) == searchterm + " - Google Search"


@pytest.mark.parametrize(
	"searchterm, title", [("", "Google"), (" ", "- Google Search")]
)
def test_search_irregular(searchterm: str, title: str) -> None:
	url = misc.search(searchterm).description
	assert isinstance(url, str)
	r = requests.get(url, timeout=10)
	assert r.ok
	assert next(
		BeautifulSoup(r.content, "html.parser").stripped_strings
	) == title


@pytest.mark.asyncio
@pytest.mark.parametrize("animalName", list(misc.animalList) + ["dog"])
async def test_animal_with_goodUrl(animalName: str) -> None:
	url = await misc.animal(animalName)
	async with httpx.AsyncClient() as client:
		response = await client.get(url, timeout=10)
	assert goodURL(response)


@pytest.mark.asyncio
async def test_animal_dog_breed() -> None:
	msg = await misc.animal("dog", "breeds")
	breeds = msg[12:-1].split(", ")
	assert len(breeds) == 107
	# TODO: remove randomness
	url = await misc.animal("dog", choice(breeds))
	async with httpx.AsyncClient() as client:
		response = await client.get(url, timeout=10)
	assert goodURL(response)

	msg = await misc.animal("dog", "invalidbreed")
	assert msg.startswith("Breed not")

	msg = await misc.animal("dog", "invalidbreed1234")
	assert msg.startswith("Breed not")

	url = await misc.animal("dog", "moose")
	async with httpx.AsyncClient() as client:
		response = await client.get(url, timeout=10)
	assert goodURL(response)


@pytest.mark.asyncio
async def test_invalid_animal_throws_exception() -> None:
	with pytest.raises(ValueError):
		await misc.animal("invalidAnimal")


@pytest.mark.asyncio
async def test_dog_api_down_throws_exception(  # type: ignore
	caplog: pytest.LogCaptureFixture,
	httpx_mock
) -> None:
	httpx_mock.add_response(
		url="https://dog.ceo/api/breeds/image/random",
		status_code=522
	)

	with pytest.raises(httpx.RequestError):
		await misc.animal("dog")

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
	ch = MockChannel(name="infractions")
	g = MockGuild(members=[u], channels=[ch])
	m = MockMessage(
		content="http://dizcort.com free nitro!", guild=g, author=u
	)
	assert len(u.roles) == 0
	assert len(list(ch.history())) == 0
	assert await Bot.handleMessages(m) == -1
	assert len(u.roles) == 1
	assert len(list(ch.history())) == 1


@pytest.mark.asyncio
async def test_cmdGuide() -> None:
	Bot.bot = MockBot(Bot.bot)
	ctx = MockContext(Bot.bot, author=MockUser(), guild=MockGuild())
	ctx.message.type = nextcord.MessageType.default
	assert await Bot.cmdGuide(ctx) == 0

	assert ctx.guild is not None
	ctx.guild.id = 442403231864324119
	assert await Bot.cmdGuide(ctx) == 1
	assert next(
		ctx.history()
	).embeds[0].title == "The Eggsoup Improvement Guide"


@pytest.mark.asyncio
async def test_cmdMute() -> None:
	Bot.bot = MockBot(Bot.bot)
	ctx = MockContext(
		Bot.bot,
		message=MockMessage(content="!mute foo"),
		author=MockUser(adminPowers=True),
		guild=MockGuild()
	)
	# if the MemberConverter fails
	assert await Bot.cmdMute(ctx, "foo") == 0

	# if trying to mute the bot
	assert await Bot.cmdMute(ctx, f"<@{bbId}>") == 0

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


@pytest.mark.asyncio
async def test_getRank_monkeypatched_for_2s_top_rating(  # type: ignore
	httpx_mock
) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/ranked?api_key=foo",
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
		emb = await brawl.getRank(MockUser(id=196354892208537600), "foo")
		assert emb.fields[0].name == "Ranked 2s"
		assert isinstance(emb.fields[0].value, str)
		assert emb.fields[0].value.startswith("**Foo+Bar")
		assert emb.fields[0].value.endswith("50.0% winrate")
		assert isinstance(emb.color, nextcord.Colour)
		assert emb.color.value == 20916
	finally:
		brawl.claimProfile(196354892208537600, 7032472)


@pytest.mark.asyncio
async def test_brawlApiCall_returns_None_when_never_played(  # type: ignore
	httpx_mock
) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/search?steamid=37&api_key=foo", json=[]
	)
	assert await brawl.brawlApiCall(
		"search?steamid=", "37", "foo", "&"
	) is None

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("steam.steamid.SteamID.from_url", lambda x: "37")
		assert await brawl.getBrawlId("foo", "foo.bar") is None


# Tests for commands that require a Brawlhalla API key:

if brawlKey:
	@pytest.mark.asyncio
	async def test_randomBrawl() -> None:
		assert brawlKey is not None
		weapon = await brawl.randomBrawl("weapon")
		assert weapon.title == "Random Weapon"
		assert weapon.thumbnail.url is not None
		assert weapon.description is not None
		assert (
			weapon.description.split(" ")[-1][:-2].lower()
			in weapon.thumbnail.url.lower().replace("guantlet", "gauntlet")
		)

		legend = await brawl.randomBrawl("legend")
		assert legend.title == "Random Legend"
		assert legend.description is not None
		assert legend.description.startswith("Your legend is ")

		legend = await brawl.randomBrawl("legend", brawlKey)
		assert len(legend.fields) == 2
		assert legend.title is not None
		legendInfo = await brawl.legendInfo(
			brawlKey, legend.title.split(" ")[0].lower().replace(",", "")
		)
		assert legendInfo is not None
		assert legend.title == legendInfo.title

		legend = await brawl.randomBrawl("invalidrandom")
		assert legend.title == "Brawlhalla Randomizer"

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

	@pytest.mark.asyncio
	@pytest.mark.parametrize(
		"url, result", [
			("https://steamcommunity.com/id/beardless", 7032472),
			("badurl", None),
			("https://steamcommunity.com/badurl", None)
		]
	)
	async def test_getBrawlId(url: str, result: typing.Optional[int]) -> None:
		assert brawlKey is not None
		sleep(2)
		assert await brawl.getBrawlId(brawlKey, url) == result

	@pytest.mark.asyncio
	async def test_getRank() -> None:
		assert brawlKey is not None
		sleep(5)
		user = MockUser(id=0)
		rank = await brawl.getRank(user, brawlKey)
		assert rank.description == brawl.unclaimed.format("<@0>")

		user.id = 196354892208537600
		rank = await brawl.getRank(user, brawlKey)
		assert rank.footer.text == "Brawl ID 7032472"

		rank = await brawl.getRank(user, brawlKey)
		assert rank.description == (
			"You haven't played ranked yet this season."
		)

		try:
			brawl.claimProfile(196354892208537600, 37)
			rank = await brawl.getRank(user, brawlKey)
			assert isinstance(rank.color, nextcord.Colour)
			assert rank.color.value == 16306282
		finally:
			brawl.claimProfile(196354892208537600, 7032472)

	@pytest.mark.asyncio
	async def test_getLegends() -> None:
		assert brawlKey is not None
		sleep(5)
		oldLegends = brawl.fetchLegends()
		await brawl.getLegends(brawlKey)
		assert brawl.fetchLegends() == oldLegends

	@pytest.mark.asyncio
	async def test_legendInfo() -> None:
		assert brawlKey is not None
		sleep(5)
		legend = await brawl.legendInfo(brawlKey, "hugin")

		assert legend is not None
		assert legend.title == "Munin, The Raven"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/"
			"2021/12/a_Roster_Pose_BirdBardM.png"
		)

		legend = await brawl.legendInfo(brawlKey, "teros")
		assert legend is not None
		assert legend.title == "Teros, The Minotaur"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/2021/07/teros.png"
		)

		legend = await brawl.legendInfo(brawlKey, "redraptor")
		assert legend is not None
		assert legend.title == "Red Raptor, The Last Sentai"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/"
			"2023/06/a_Roster_Pose_SentaiM.png"
		)

		assert not await brawl.legendInfo(brawlKey, "invalidname")

	@pytest.mark.asyncio
	async def test_getStats() -> None:
		assert brawlKey is not None
		sleep(5)
		user = MockUser(id=0)
		stats = await brawl.getStats(user, brawlKey)
		assert stats.description == brawl.unclaimed.format("<@0>")

		user.id = 196354892208537600
		try:
			brawl.claimProfile(196354892208537600, 7032472)
			emb = await brawl.getStats(user, brawlKey)
			assert emb.footer.text == "Brawl ID 7032472"
			assert len(emb.fields) in (3, 4)

			brawl.claimProfile(196354892208537600, 1247373426)
			emb = await brawl.getStats(user, brawlKey)
			assert emb.description is not None
			assert emb.description.startswith(
				"This profile doesn't have stats"
			)
		finally:
			brawl.claimProfile(196354892208537600, 7032472)

	@pytest.mark.asyncio
	async def test_getClan() -> None:
		assert brawlKey is not None
		sleep(5)
		user = MockUser(id=0)
		clan = await brawl.getClan(user, brawlKey)
		assert clan.description == brawl.unclaimed.format("<@0>")

		user.id = 196354892208537600
		try:
			brawl.claimProfile(196354892208537600, 7032472)
			clan = await brawl.getClan(user, brawlKey)
			assert clan.title == "DinersDriveInsDives"

			brawl.claimProfile(196354892208537600, 5895238)
			clan = await brawl.getClan(user, brawlKey)
			assert clan.description == "You are not in a clan!"
		finally:
			brawl.claimProfile(196354892208537600, 7032472)

	def test_brawlCommands() -> None:
		assert len(brawl.brawlCommands().fields) == 6
