"""
Beardless Bot unit tests.

Module-wide ruff ignore codes:

D103: Missing docstring in public function
	(Tests don't need docstrings)
PLR2004: Magic value used in comparison
	(Several tests compare against magic values)
S101: Assert used
	(Most tests rely on assert)
S603: Subprocess call
	(Two quality tests ruly on subprocess calls to sys.executable)
SLF001: Private member accessed
	(Some of the mocking/monkeypatching requires accessing private members)
"""

# ruff: noqa: PLR2004, S603, SLF001

import asyncio
import json
import logging
import operator
import os
import subprocess
import sys
import time
from collections import deque
from collections.abc import AsyncIterator
from copy import copy
from datetime import datetime
from pathlib import Path
from typing import Any, Final, overload, override
from urllib.parse import quote_plus

import aiofiles
import dotenv
import httpx
import nextcord
import pytest
import requests
from aiohttp import ClientWebSocketResponse
from bs4 import BeautifulSoup
from codespell_lib import main as codespell
from flake8.api import legacy as flake8
from mypy.api import run as mypy
from nextcord.ext import commands
from nextcord.types import channel as channel_payloads
from nextcord.types import emoji as emoji_payloads
from nextcord.types import message as message_payloads
from nextcord.types.embed import Embed as EmbedPayload
from nextcord.types.role import Role as RolePayload
from nextcord.types.user import User as UserPayload
from pytest_httpx import HTTPXMock

import Bot
import brawl
import bucks
import logs
import misc

logger = logging.getLogger(__name__)

ImageTypes: set[str] = {
	"image/" + i for i in ("png", "jpeg", "jpg", "gif", "webp")
}

FilesToCheck: list[str] = [f.name for f in Path().glob("*.py")]

OwnerBrawlId: Final[int] = 7032472

GuildChannel = (
	nextcord.StageChannel
	| nextcord.VoiceChannel
	| nextcord.TextChannel
	| nextcord.CategoryChannel
	| nextcord.ForumChannel
)

IconTypes = bytes | nextcord.Asset | nextcord.Attachment | nextcord.File

MessageableChannel = (
	nextcord.TextChannel
	| nextcord.Thread
	| nextcord.DMChannel
	| nextcord.PartialMessageable
	| nextcord.VoiceChannel
	| nextcord.StageChannel
	| nextcord.GroupChannel
)

ConnectionStateGetChannelTypes = (
	GuildChannel
	| nextcord.Thread
	| nextcord.PartialMessageable
	| nextcord.abc.PrivateChannel
)

SnowflakeTime = datetime | nextcord.abc.Snowflake

StyleGuide = flake8.get_style_guide(ignore=["W191", "W503"])

dotenv.load_dotenv(".env")
BrawlKey: str | None = os.environ.get("BRAWLKEY")

MarkAsync = pytest.mark.asyncio(loop_scope="module")


def response_ok(resp: httpx.Response) -> bool:
	"""
	Make sure a response has an ok exit code.

	Args:
		resp (httpx.Response): The response to check

	Returns:
		bool: Whether the exit code is ok.

	"""
	return misc.Ok <= resp.status_code < 400


def valid_image_url(resp: httpx.Response) -> bool:
	"""
	Make sure an image url points to a valid image.

	Args:
		resp (httpx.Response): The response to check

	Returns:
		bool: Whether the url points to a valid image.

	"""
	return response_ok(resp) and resp.headers["content-type"] in ImageTypes


async def latest_message(
	ch: nextcord.abc.Messageable,
) -> nextcord.Message | None:
	"""
	Get the most recent message from a messageable's history.

	Args:
		ch (nextcord.abc.Messageable): The messageable from which the most
			recent message will be pulled.

	Returns:
		nextcord.Message | None: The most recent message, if one exists;
			else, None.

	"""
	h = [i async for i in ch.history()]
	if len(h) == 0:
		return None
	return h[-1]


# TODO: Write generic MockState
# https://github.com/LevBernstein/BeardlessBot/issues/48

class MockHTTPClient(nextcord.http.HTTPClient):
	"""Drop-in replacement for HTTPClient to enable offline testing."""

	@override
	def __init__(
		self,
		loop: asyncio.AbstractEventLoop,
		user: nextcord.ClientUser | None = None,
	) -> None:
		self.loop = loop
		self.user = user
		self._user_agent = str(user)
		self.token = None
		self.proxy = None
		self.proxy_auth = None
		self._global_over = asyncio.Event()
		self._global_over.set()

	@override
	async def create_role(
		self,
		guild_id: nextcord.types.snowflake.Snowflake,
		reason: str | None = None,
		auth: str | None = None,
		retry_request: bool = True,
		**fields: Any,
	) -> RolePayload:
		data = dict(fields)
		if reason:
			logger.info("Role creation reason: %s", reason)
		return RolePayload(
			id=guild_id,
			name=data["name"],
			color=data.get("color", 0),
			hoist=data.get("hoist", False),
			position=data.get("position", 0),
			permissions=data.get("permissions", 0),
			managed=False,
			mentionable=data.get("mentionable", True),
			flags=0,
		)

	@override
	async def send_message(
		self,
		channel_id: nextcord.types.snowflake.Snowflake,
		content: str | None,
		*,
		tts: bool = False,
		embed: EmbedPayload | None = None,
		embeds: list[EmbedPayload] | None = None,
		nonce: int | str | None = None,
		allowed_mentions: message_payloads.AllowedMentions | None = None,
		message_reference: message_payloads.MessageReference | None = None,
		stickers: list[int] | None = None,
		components: list[nextcord.types.components.Component] | None = None,
		flags: int | None = None,
		auth: str | None = None,
		retry_request: bool = True,
	) -> message_payloads.Message:
		user = MockUser()
		up = UserPayload(
			id=user.id,
			username=user.name,
			discriminator=user.discriminator,
			avatar=user._avatar,
		)
		mention_everyone = (content is not None and ("@everyone" in content))
		return message_payloads.Message(
			id=0,
			channel_id=channel_id,
			author=up,
			content=content or "",
			timestamp=str(datetime.now(misc.TimeZone)),
			edited_timestamp=None,
			tts=tts,
			mention_everyone=mention_everyone,
			mentions=[],
			mention_roles=[],
			attachments=[],
			embeds=[embed] if embed else embeds or [],
			pinned=False,
			type=0,
			nonce=nonce or 0,
			message_reference=message_payloads.MessageReference(type=0),
			flags=flags or 0,
			components=components or [],
		)

	@override
	async def leave_guild(
		self,
		guild_id: nextcord.types.snowflake.Snowflake,
		*,
		auth: str | None = None,
		retry_request: bool = True,
	) -> None:
		if (
			self.user
			and hasattr(self.user, "guild")
			and self.user.guild
			and self.user.guild.id == guild_id
		):
			self.user.guild = None


class MockHistoryIterator(AsyncIterator[nextcord.Message]):
	"""Mock AsyncIterator class for offline testing."""

	@override
	def __init__(
		self,
		messageable: nextcord.abc.Messageable,
		limit: int | None = None,
		before: SnowflakeTime | None = None,
		after: SnowflakeTime | None = None,
		around: SnowflakeTime | None = None,
		oldest_first: bool | None = False,
	) -> None:
		self.messageable = messageable
		self.limit = min(limit or 100, 100)
		self.yielded: int = 0
		self.messages: asyncio.Queue[nextcord.Message] = asyncio.Queue()
		self.reverse = (
			(after is not None) if oldest_first is None else oldest_first
		)

	@override
	async def __anext__(self) -> nextcord.Message:
		if not hasattr(self, "channel"):
			self.channel = await self.messageable._get_channel()
		assert hasattr(self.channel, "messages")
		assert isinstance(self.channel.messages, list)
		assert self.limit is not None
		self.limit = min(self.limit, len(self.channel.messages))
		if self.yielded < self.limit:
			data = (
				list(reversed(self.channel.messages))
				if self.reverse
				else self.channel.messages
			)
			message = data[self.yielded]
			assert isinstance(message, nextcord.Message)
			self.yielded += 1
			return message
		raise StopAsyncIteration


class MockMember(nextcord.Member):
	"""Mock Member class for offline testing."""

	@override
	def __init__(
		self,
		user: nextcord.User | None = None,
		nick: str | None = None,
		roles: list[nextcord.Role] | None = None,
		guild: nextcord.Guild | None = None,
		custom_avatar: bool = True,
		perms: nextcord.Permissions | None = None,
		admin_powers: bool = False,
	) -> None:
		self._user = user or MockUser()
		self._user.bot = False
		self.nick = nick
		self.guild = guild or MockGuild()
		self.activities = ()
		self._user._banner = None
		self.roleList = [MockRole("everyone", self.guild.id)] + (roles or [])
		self._roles = nextcord.utils.SnowflakeList([])
		self._timeout = None
		self._avatar = (
			"7b6ea511d6e0ef6d1cdb2f7b53946c03" if custom_avatar else None
		)
		self.perms = (
			nextcord.Permissions.all()
			if admin_powers
			else (perms or nextcord.Permissions.none())
		)
		self.joined_at = self.created_at

	@override
	@property
	def guild_permissions(self) -> nextcord.Permissions:
		return self.perms

	@guild_permissions.setter
	def guild_permissions(self, perms: nextcord.Permissions) -> None:
		self.perms = perms

	@override
	@property
	def roles(self) -> list[nextcord.Role]:
		return self.roleList

	@roles.setter
	def roles(self, roles: list[nextcord.Role]) -> None:
		self.roleList = roles

	@override
	async def add_roles(
		self,
		*roles: nextcord.abc.Snowflake,
		reason: str | None = None,
		atomic: bool = True,
	) -> None:
		logger.info(
			"Role add reason: %s. Atomic operation: %s", reason, atomic,
		)
		for role in roles:
			assert isinstance(role, nextcord.Role)
			if role not in self.roleList:
				self.roleList.append(role)

	@override
	async def send(  # type: ignore[override]
		self, *args: str | None, **kwargs: Any,
	) -> None:
		# It's not worth trying to match the original signature. Trust me.
		await (await self._get_channel()).send(*args, **kwargs)

	@override
	async def _get_channel(self) -> nextcord.DMChannel:
		return await self._user._get_channel()

	@override
	def history(
		self,
		*,
		limit: int | None = 100,
		before: SnowflakeTime | None = None,
		after: SnowflakeTime | None = None,
		around: SnowflakeTime | None = None,
		oldest_first: bool | None = False,
	) -> AsyncIterator[nextcord.Message]:
		return self._user.history(
			limit=limit,
			before=before,
			after=after,
			around=around,
			oldest_first=oldest_first,
		)


class MockUser(nextcord.User):
	"""
	Mock User class for offline testing.

	MockUser also contains some features of nextcord.Member for the sake of
	testing the Bot user's permissions. That probably should not be the case.
	"""

	class MockUserState(nextcord.state.ConnectionState):
		"""Drop-in replacement for ConnetionState."""

		# TODO: move MockUserState out, apply to all classes, make generic
		# https://github.com/LevBernstein/BeardlessBot/issues/48

		@override
		def __init__(self, message_number: int = 0) -> None:
			self._guilds: dict[int, nextcord.Guild] = {}
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop)
			self.user = None
			self.last_message_id = message_number
			self.channel = MockChannel()

		@override
		def create_message(
			self,
			*,
			channel: MessageableChannel,
			data: message_payloads.Message,
		) -> nextcord.Message:
			data["id"] = self.user.id if self.user else "0"
			data["components"] = []
			data["message_reference"] = {
				"message_id": self.last_message_id,
				"channel_id": str(channel.id),
			}
			self.last_message_id += 1
			message = nextcord.Message(state=self, channel=channel, data=data)
			assert self.channel._state._messages is not None
			self.channel._state._messages.append(message)
			return message

		@override
		def store_user(
			self, data: UserPayload | nextcord.User,
		) -> nextcord.User:
			if isinstance(data, nextcord.User):
				return data
			stored_user = (
				self.user or MockUser(user_id=int(data.get("id", "0")))
			)
			assert isinstance(stored_user, nextcord.User)
			return stored_user

		@override
		def get_channel(
			self, channel_id: int | None,
		) -> ConnectionStateGetChannelTypes | None:
			return (
				MockChannel(channel_id=channel_id)
				if channel_id is not None
				else self.channel
			)

	@override
	def __init__(
		self,
		name: str = "testname",
		discriminator: str = "0000",
		user_id: int = 123456789,
		messages: list[nextcord.Message] | None = None,
		*,
		custom_avatar: bool = True,
		admin_powers: bool = False,
	) -> None:
		self.name = name
		self.global_name = name
		self.id = user_id
		self.discriminator = discriminator
		self.bot = False
		self.activity = None
		self.system = False
		self.messages = messages or []
		self._public_flags = 0
		self._state = self.MockUserState(message_number=len(self.messages))
		# TODO: Switch to DMChannel
		self._state._private_channels_by_user = {
			user_id: MockChannel(),  # type: ignore[dict-item]
		}
		self._avatar = (
			"7b6ea511d6e0ef6d1cdb2f7b53946c03" if custom_avatar else None
		)
		self.set_user_state()
		self.guild_permissions = (
			nextcord.Permissions.all()
			if admin_powers
			else nextcord.Permissions.none()
		)

	def set_user_state(self) -> None:
		"""Assign the User object to its ConnectionState."""
		self._state.user = MockBot.MockClientUser(self)
		self._state.http._user_agent = str(self._state.user)

	@override
	def history(
		self,
		*,
		limit: int | None = 100,
		before: SnowflakeTime | None = None,
		after: SnowflakeTime | None = None,
		around: SnowflakeTime | None = None,
		oldest_first: bool | None = False,
	) -> AsyncIterator[nextcord.Message]:
		channel = self._state.get_channel(None)
		assert isinstance(channel, nextcord.abc.Messageable)
		return MockHistoryIterator(
			channel,
			limit,
			before,
			after,
			around,
			oldest_first,
		)

	@override
	async def _get_channel(self) -> MessageableChannel:  # type: ignore[override]
		# TODO: switch to DMChannel
		ch = self._state.get_channel(None)
		assert isinstance(ch, MessageableChannel)
		return ch


class MockChannel(nextcord.TextChannel):
	"""Drop-in replacement for TextChannel to enable offline testing."""

	class MockChannelState(nextcord.state.ConnectionState):
		"""Drop-in replacement for ConnetionState."""

		@override
		def __init__(
			self,
			user: nextcord.ClientUser | None = None,
			message_number: int = 0,
			messages: list[nextcord.Message] | None = None,
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.user = user
			self.last_message_id = message_number
			self._messages: deque[nextcord.Message] = deque(messages or [])

		@override
		def create_message(
			self,
			*,
			channel: MessageableChannel,
			data: message_payloads.Message,
		) -> nextcord.Message:
			data["id"] = self.last_message_id
			data["components"] = []
			user = self.user or MockUser()
			data["author"] = UserPayload(
				id=user.id,
				username=user.name,
				discriminator=user.discriminator,
				avatar=user._avatar,
			)
			data["message_reference"] = {
				"message_id": self.last_message_id,
				"channel_id": str(channel.id),
			}
			self.last_message_id += 1
			message = nextcord.Message(state=self, channel=channel, data=data)
			self._messages.append(message)
			return message

		@override
		def store_user(self, data: UserPayload) -> nextcord.User:
			stored_user = self.user or MockUser(user_id=int(data["id"]))
			assert isinstance(stored_user, nextcord.User)
			return stored_user

	@override
	def __init__(
		self,
		name: str = "testchannelname",
		guild: nextcord.Guild | None = None,
		messages: list[nextcord.Message] | None = None,
		channel_id: int = 123456789,
	) -> None:
		self.name = name
		self.id = channel_id
		self.position = 0
		self.slowmode_delay = 0
		self.nsfw = False
		self.topic = None
		self.category_id = 0
		self.guild = guild or nextcord.utils.MISSING
		clean_messages = messages or []
		self._state = self.MockChannelState(
			message_number=len(clean_messages), messages=clean_messages,
		)
		self.assign_channel_to_guild(self.guild)
		self._overwrites = []

	@overload
	@override
	async def set_permissions(
		self,
		target: nextcord.Member | nextcord.Role,
		*,
		overwrite: nextcord.PermissionOverwrite | None = ...,
		reason: str | None = ...,
	) -> None:
		...

	@overload
	@override
	async def set_permissions(
		self,
		target: nextcord.Member | nextcord.Role,
		*,
		reason: str | None = ...,
		**permissions: bool,
	) -> None:
		...

	@override
	async def set_permissions(
		self,
		target: nextcord.Member | nextcord.Role,
		*,
		reason: str | None = None,
		**kwargs: Any,
	) -> None:
		overwrite = kwargs.pop("overwrite", None)
		permissions: dict[str, bool] = kwargs
		if overwrite is None and len(permissions) != 0:
			overwrite = nextcord.PermissionOverwrite(**permissions)
		if overwrite is not None:
			allow, deny = overwrite.pair()
			permission_payload = channel_payloads.PermissionOverwrite(
				id=target.id,
				type=0 if isinstance(target, nextcord.Role) else 1,
				allow=allow.value,
				deny=deny.value,
			)
			channel_payload = channel_payloads.TextChannel(
				guild_id=self.guild.id,
				position=self.position,
				permission_overwrites=[permission_payload],
				nsfw=self.nsfw,
				id=self.id,
				name=self.name,
				rate_limit_per_user=0,
				default_auto_archive_duration=60,
				default_thread_rate_limit_per_user=0,
				type=0,
				parent_id=None,
			)
			self._fill_overwrites(channel_payload)
			logger.info(
				"Setting perms on channel: %s for target: %s, reason: %s",
				self.id,
				target.id,
				reason,
			)
		else:
			# TODO: proper removal logic here--remove from _overwrites
			logger.info(
				"Deleting perms on channel: %s for target: %s, reason: %s",
				self.id,
				target.id,
				reason,
			)

	@override
	def history(
		self,
		*,
		limit: int | None = 100,
		before: SnowflakeTime | None = None,
		after: SnowflakeTime | None = None,
		around: SnowflakeTime | None = None,
		oldest_first: bool | None = False,
	) -> AsyncIterator[nextcord.Message]:
		return MockHistoryIterator(
			self,
			limit,
			before,
			after,
			around,
			oldest_first,
		)

	@override
	async def send(self, *args: str | None, **kwargs: Any) -> nextcord.Message:
		return (await super().send(*args, **kwargs))

	def assign_channel_to_guild(self, guild: nextcord.Guild) -> None:
		"""
		Add a channel to its Guild's list of channels.

		Args:
			guild (nextcord.Guild): The Guild to which the channel belongs

		"""
		if guild and self not in guild.channels:
			guild.channels.append(self)

	@property
	def messages(self) -> list[nextcord.Message]:
		"""
		Return the channel's sent messages as a list.

		Returns:
			list[nextcord.Message]: A list of messages.

		"""
		assert self._state._messages is not None
		return list(self._state._messages)


# TODO: Write message.edit()
class MockMessage(nextcord.Message):
	"""Drop-in replacement for Message to enable offline testing."""

	class MockMessageState(nextcord.state.ConnectionState):
		"""Drop-in replacement for ConnetionState."""

		@override
		def __init__(
			self, user: nextcord.User, guild: nextcord.Guild | None = None,
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(
				self.loop, user=MockBot.MockClientUser(user),
			)
			self.guild = guild or MockGuild()

		@override
		def get_reaction_emoji(
			self, data: emoji_payloads.Emoji,
		) -> nextcord.emoji.Emoji:
			return MockEmoji(self.guild, data, MockMessage())

	@override
	def __init__(
		self,
		content: str | None = "testcontent",
		author: nextcord.User | nextcord.Member | None = None,
		guild: nextcord.Guild | None = None,
		channel: nextcord.TextChannel | None = None,
		embeds: list[nextcord.Embed] | None = None,
		embed: nextcord.Embed | None = None,
	) -> None:
		self.author = author or MockMember()
		self.content = content or ""
		self.id = 123456789
		self.type = nextcord.MessageType.default
		self.guild = guild
		self.channel = channel or MockChannel(guild=self.guild or MockGuild())
		self.mentions = []
		self.embeds = embeds or ([embed] if embed is not None else [])
		self.mention_everyone = False
		self.flags = nextcord.MessageFlags()
		self._state = self.MockMessageState(
			(
				self.author
				if isinstance(self.author, nextcord.User)
				else self.author._user
			), guild,
		)
		assert self.channel._state._messages is not None
		self.channel._state._messages.append(self)

	@override
	async def delete(self, *, delay: float | None = None) -> None:
		assert self.channel._state._messages is not None
		if delay:
			await asyncio.sleep(delay)
		self.channel._state._messages.remove(self)

	@staticmethod
	def get_mock_reaction_payload(
		name: str = "MockEmojiName",
		emoji_id: int = 0,
		*,
		me: bool = False,
		count: int = 1,
	) -> message_payloads.Reaction:
		"""
		Create the payload for a Reaction.

		Args:
			name (str): The reaction emoji's name (default is "MockEmojiName")
			emoji_id (int): The emoji's id (default is 0)
			me (bool): If the BotUser sent this reaction (default is False)
			count (int): Number of users who added this reaction for a given
				nextcord.Message (default is 1)

		Returns:
			message_payloads.Reaction: The TypedDict that will be used to
				create a new Reaction, constructed with the provided arguments.

		"""
		return message_payloads.Reaction(
			me=me,
			count=count,
			emoji=emoji_payloads.PartialEmoji(id=emoji_id, name=name),
		)


class MockRole(nextcord.Role):
	"""Drop-in replacement for Role to enable offline testing."""

	@override
	def __init__(
		self,
		name: str = "Test Role",
		role_id: int = 123456789,
		permissions: int | nextcord.Permissions = 1879573680,
		colour: int = 0,
	) -> None:
		self.name = name
		self.id = role_id
		self.hoist = False
		self.mentionable = True
		self.position = 1
		self._permissions = (
			permissions if isinstance(permissions, int) else permissions.value
		)
		self._colour = colour


class MockGuild(nextcord.Guild):
	"""Drop-in replacement for Guild to enable offline testing."""

	class MockGuildState(nextcord.state.ConnectionState):
		"""Drop-in replacement for ConnetionState."""

		@override
		def __init__(self, guild_id: int = 0) -> None:
			user = MockBot.MockClientUser()
			self.member_cache_flags = nextcord.MemberCacheFlags.all()
			self.shard_count = 1
			self.loop = asyncio.get_event_loop()
			self.user = user
			self.http = MockHTTPClient(self.loop, user=user)
			self._intents = nextcord.Intents.all()
			self._guilds = {guild_id: nextcord.utils.MISSING}

		@override
		async def chunk_guild(
			self,
			guild: nextcord.Guild,
			*,
			wait: bool = True,
			cache: bool | None = None,
		) -> list[nextcord.Member]:
			guild._member_count = len(guild._members)
			logger.info(
				"Chunked Guild %s with wait=%s and cache=%s",
				guild,
				wait,
				cache,
			)
			return guild.members

		@override
		async def query_members(
			self,
			guild: nextcord.Guild,
			query: str | None,
			limit: int,
			user_ids: list[int] | None,
			cache: bool,
			presences: bool,
		) -> list[nextcord.Member]:
			logger.info(
				"Queried members in Guild %s with query=%s, presences=%s",
				guild,
				query,
				presences,
			)
			members: list[nextcord.Member] = []
			if self.user is not None and limit >= 1:
				await self.chunk_guild(guild, cache=cache)
				if not user_ids or (self.user.id in user_ids):
					assert hasattr(self.user, "base_user")
					members.append(
						MockMember(self.user.base_user, guild=guild),
					)
			return members

	@override
	def __init__(
		self,
		members: list[nextcord.Member] | None = None,
		name: str = "Test Guild",
		guild_id: int = 0,
		channels: list[nextcord.TextChannel] | None = None,
		roles: list[nextcord.Role] | None = None,
		chunked: bool = True,
	) -> None:
		self.name = name
		self.id = guild_id
		self._state = self.MockGuildState(self.id)
		self._members = dict(enumerate(members or []))
		self._member_count = len(self._members) if chunked else 0
		self._channels = dict(
			enumerate(channels or [MockChannel()]),
		)
		self._roles = dict(enumerate(
			[MockRole(name="everyone", role_id=0)]
			+ (roles if roles is not None else [MockRole()]),
		))
		self.owner_id = 123456789
		for role in self._roles.values():
			self.assign_guild_to_role(role)
		for ch in self._channels.values():
			self.assign_guild_to_channel(ch)

	@override
	@property
	def me(self) -> nextcord.Member:
		assert self._state.user is not None
		user = (
			self._state.user.base_user
			if hasattr(self._state.user, "base_user")
			else self._state.user
		)
		assert isinstance(user, nextcord.User)
		perms = (
			user.guild_permissions
			if hasattr(user, "guild_permissions")
			else None
		)
		assert isinstance(perms, nextcord.Permissions | None)
		return MockMember(user, guild=self, perms=perms)

	@overload
	@override
	async def create_role(
		self,
		*,
		reason: str | None = ...,
		name: str = ...,
		permissions: nextcord.Permissions = ...,
		colour: nextcord.Colour | int = ...,
		hoist: bool = ...,
		mentionable: bool = ...,
		icon: str | IconTypes | None = ...,
	) -> nextcord.Role:
		...

	@overload
	@override
	async def create_role(
		self,
		*,
		reason: str | None = ...,
		name: str = ...,
		permissions: nextcord.Permissions = ...,
		color: nextcord.Colour | int = ...,
		hoist: bool = ...,
		mentionable: bool = ...,
		icon: str | IconTypes | None = ...,
	) -> nextcord.Role:
		...

	@override
	async def create_role(
		self,
		*,
		name: str = "TestRole",
		permissions: nextcord.Permissions | None = None,
		color: nextcord.Colour | int = 0,
		colour: nextcord.Colour | int = 0,
		hoist: bool = False,
		mentionable: bool = False,
		icon: str | IconTypes | None = None,
		reason: str | None = None,
	) -> nextcord.Role:
		col = color or colour or nextcord.Colour.default()
		perms = permissions or nextcord.Permissions.none()
		fields = {
			"name": name,
			"permissions": str(perms.value),
			"mentionable": mentionable,
			"hoist": hoist,
			"color": col if isinstance(col, int) else col.value,
		}
		if isinstance(icon, str):
			fields["unicode_emoji"] = icon
		else:
			fields["icon"] = await nextcord.utils.obj_to_base64_data(icon)

		data = await self._state.http.create_role(
			self.id, reason=reason, auth=None, retry_request=False, **fields,
		)
		role = nextcord.Role(guild=self, data=data, state=self._state)
		self._roles[len(self.roles)] = role
		return role

	def assign_guild_to_role(self, role: nextcord.Role) -> None:
		"""
		Set a Role's Guild to this Guild.

		Args:
			role (nextcord.Role): The role whose Guild will be set

		"""
		role.guild = self

	def assign_guild_to_channel(self, channel: GuildChannel) -> None:
		"""
		Set a GuildChannel's Guild to this Guild.

		Args:
			channel (GuildChannel): The channel whose Guild will be set

		"""
		channel.guild = self

	@override
	def get_member(self, user_id: int, /) -> nextcord.Member | None:
		return MockMember(MockUser(user_id=user_id))


class MockThread(nextcord.Thread):
	"""Drop-in replacement for Thread to enable offline testing."""

	@override
	def __init__(
		self,
		*,
		name: str = "testThread",
		owner: nextcord.User | None = None,
		channel_id: int = 0,
		me: nextcord.Member | None = None,
		parent: nextcord.TextChannel | None = None,
		archived: bool = False,
		locked: bool = False,
	) -> None:
		Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
		channel = (
			parent or MockChannel(channel_id=channel_id, guild=MockGuild())
		)
		self.guild = channel.guild
		self._state = channel._state
		self.state = self._state
		self.id = 0
		self.name = name
		self.parent_id = channel.id
		self.owner_id = (owner or MockUser()).id
		self.archived = archived
		self.archive_timestamp = datetime.now(misc.TimeZone)
		self.locked = locked
		self.message_count = 0
		self._type = nextcord.enums.ChannelType(0)
		self.auto_archive_duration = 10080
		self.bot_user = Bot.BeardlessBot.user
		assert isinstance(self.bot_user, MockBot.MockClientUser)
		self.me = me or MockMember(  # type: ignore[assignment]
			self.bot_user.base_user, guild=self.guild,
		)
		self._members = copy(channel.guild._members)  # type: ignore[arg-type]
		self._safe_join()

	@override
	async def join(self) -> None:
		self._safe_join()

	def _safe_join(self) -> None:
		"""Non-async version of join for testing."""
		assert isinstance(self.bot_user, MockBot.MockClientUser)
		if not any(user.id == self.bot_user.id for user in self.members):
			self._members[
				len(self.members)
			] = self.me  # type: ignore[assignment]
		if not any(user.id == self.bot_user.id for user in self.guild.members):
			self.guild._members[
				len(self.guild.members)
			] = self.me  # type: ignore[assignment]
		self.member_count = len(self.members)


class MockContext(misc.BotContext):
	"""Drop-in replacement for Context to enable offline testing."""

	class MockContextState(nextcord.state.ConnectionState):
		"""Drop-in replacement for ConnetionState."""

		# TODO: Inherit state from message, as in actual Context._state
		@override
		def __init__(
			self,
			user: nextcord.ClientUser | None = None,
			channel: nextcord.TextChannel | None = None,
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.user = user
			self.channel = channel or MockChannel(guild=MockGuild())
			self.message = MockMessage()

		@override
		def create_message(
			self,
			*,
			channel: MessageableChannel,
			data: message_payloads.Message,
		) -> nextcord.Message:
			assert isinstance(
				self.channel._state, MockChannel.MockChannelState,
			)
			data["id"] = self.user.id if self.user else "0"
			data["components"] = []
			data["message_reference"] = {
				"message_id": self.channel._state.last_message_id,
				"channel_id": str(channel.id),
			}
			self.channel._state.last_message_id += 1
			message = nextcord.Message(state=self, channel=channel, data=data)
			assert self.channel._state._messages is not None
			self.channel._state._messages.append(message)
			return message

		@override
		def store_user(
			self, data: UserPayload | nextcord.User,
		) -> nextcord.User:
			if isinstance(data, nextcord.User):
				return data
			stored_user = (
				self.user or MockUser(user_id=int(data.get("id", "0")))
			)
			assert isinstance(stored_user, nextcord.User)
			return stored_user

	@override
	def __init__(
		self,
		bot: commands.Bot,
		message: nextcord.Message | None = None,
		channel: nextcord.TextChannel | None = None,
		author: nextcord.User | nextcord.Member | None = None,
		guild: nextcord.Guild | None = None,
		invoked_with: str | None = None,
	) -> None:
		self.bot = bot
		self.prefix = str(bot.command_prefix) if bot.command_prefix else "!"
		self.message = message or MockMessage()
		self.author = author or MockUser()
		self.guild = guild
		self.channel = channel or MockChannel(guild=self.guild or MockGuild())
		if self.guild is not None and self.channel not in self.guild.channels:
			self.guild._channels[len(self.guild.channels)] = self.channel
		if (
			self.guild
			and isinstance(self.author, nextcord.Member)
			and self.author not in self.guild.members
		):
			self.guild._members[len(self.guild.members)] = self.author
		self._state = self.MockContextState(channel=self.channel)
		self.invoked_with = invoked_with

	@override
	def history(
		self,
		*,
		limit: int | None = 100,
		before: SnowflakeTime | None = None,
		after: SnowflakeTime | None = None,
		around: SnowflakeTime | None = None,
		oldest_first: bool | None = False,
	) -> AsyncIterator[nextcord.Message]:
		assert hasattr(self._state, "channel")
		assert isinstance(self._state.channel, nextcord.abc.Messageable)
		return MockHistoryIterator(
			self._state.channel,
			limit,
			before,
			after,
			around,
			oldest_first,
		)

	@override
	async def send(self, *args: str | None, **kwargs: Any) -> nextcord.Message:
		msg = await super().send(*args, **kwargs)
		assert hasattr(self.channel, "messages")
		self.channel.messages.append(msg)
		return msg


class MockBot(commands.Bot):
	"""Drop-in replacement for Bot to enable offline testing."""

	class MockClientWebSocketResponse(ClientWebSocketResponse):
		"""
		Drop-in replacement for ClientWebSocketResponse.

		This just exists for the sake of mypy. Hacky, I know.
		"""

		@override
		def __init__(self) -> None:
			self._protocol = ""

	class MockBotWebsocket(nextcord.gateway.DiscordWebSocket):
		"""Drop-in replacement for DiscordWebSocket."""

		@override
		def __init__(
			self,
			socket: ClientWebSocketResponse,
			*,
			loop: asyncio.AbstractEventLoop,
			conn: nextcord.state.ConnectionState,
		) -> None:
			self.socket = socket
			self.loop = loop
			self._connection = conn

		@override
		@property
		def latency(self) -> float:
			return 0.025

	class MockClientUser(nextcord.ClientUser):
		"""Drop-in replacement for ClientUser."""

		@override
		def __init__(self, base_user: nextcord.User | None = None) -> None:
			self.base_user = base_user or MockUser(user_id=misc.BbId)
			self.base_user.bot = True
			self._state = self.base_user._state
			self.id = self.base_user.id
			self.name = "testclientuser"
			self.discriminator = "0000"
			self._avatar = str(self.base_user.avatar)
			self.bot = True
			self.verified = True
			self.mfa_enabled = False
			self.global_name = self.base_user.global_name
			self.nick = ""

		@override
		async def edit(
			self,
			*,
			username: str = "",
			avatar: IconTypes | None = None,
			banner: IconTypes | None = None,
		) -> nextcord.ClientUser:
			self.name = username or self.name
			self._avatar = str(avatar)
			return self

	@override
	def __init__(self, bot: commands.Bot) -> None:
		self._connection = bot._connection
		self.activity = nextcord.CustomActivity(
			name="Try !blackjack and !flip",
		)
		self._connection.user = self.MockClientUser()
		self.command_prefix = bot.command_prefix
		self.case_insensitive = bot.case_insensitive
		self._help_command = bot.help_command
		self._intents = bot.intents
		self.owner_id = bot.owner_id
		self.status = nextcord.Status.online
		self._connection._guilds = {1: MockGuild(members=[MockMember()])}
		self.all_commands = bot.all_commands
		self.ws = self.MockBotWebsocket(
			self.MockClientWebSocketResponse(),
			loop=asyncio.get_event_loop(),
			conn=bot._connection,
		)

	@override
	async def change_presence(
		self,
		*,
		activity: nextcord.BaseActivity | None = None,
		status: str | None = None,
	) -> None:
		if activity is None:
			self._connection._activity = None
		else:
			self._connection._activity = activity.to_dict()
		self.status = status or nextcord.Status.online


class MockEmoji(nextcord.emoji.Emoji):
	"""Drop-in replacement for Emoji to enable offline testing."""

	@override
	def __init__(
		self,
		guild: nextcord.Guild,
		data: emoji_payloads.Emoji,
		state_message: nextcord.Message | None = None,
	) -> None:
		self.guild_id = guild.id
		self._state = (state_message or MockMessage())._state
		self._from_data(data)


# Run suite of code quality tests with pytest -vvk quality
def test_with_ruff_for_code_quality() -> None:
	"""
	Test against ruff executable's output to ensure compliance.

	Ruff codes:
		Invalid:
			D203: 1 blank line required before class docstring
				(Incompatible with D211)
			D206: Spaces instead of tabs in docstrings
				(Tabs are the BB standard)
			D212: Multi-line docstring summary should start on first line
				(Incompatible with D213)
			ERA001: Commented-out code
				(Too many false positives)
			Q003: Change outer quotes to avoid escaping inner quotes
				(Double quotes is the BB standard)
			S311: Don't use random for cryptography
				(Not doing any cryptography)
			TD002: Missing author in TODO
				(They're all Lev)
			W191: Spaces instead of tabs
				(Tabs are the BB standard)

		Temporarily disable, fix later:
			D103: Missing docstring in public function
				(I'm working on it...)
			FIX002: Line contains FIXME/TODO/XXX/HACK
				(I'm working on it...)
			S101: Use of assert
				(Shouldn't be present in production code)
			TD003: Missing issue link in TODO
				(Only some TODOs have issue links)

	"""
	version = sys.version_info
	invalid_codes = "D203,D206,D212,ERA001,Q003,S311,TD002,W191"
	temporary_ignore_codes = "D103,FIX002,S101,TD003"
	assert subprocess.run(
		[
			sys.executable,
			"-m",
			"ruff",
			"check",
			*FilesToCheck,
			"--line-length=80",
			"--select=ALL",
			f"--target-version=py{version.major}{version.minor}",
			"--output-format=grouped",
			"--ignore=" + invalid_codes + "," + temporary_ignore_codes,
		], capture_output=True, check=False, input=None, text=True,
	).stdout[:-1] == "All checks passed!"


@pytest.mark.parametrize("letter", ["W", "E", "C", "A"])
def test_code_quality_with_flake8(letter: str) -> None:
	assert StyleGuide.check_files(FilesToCheck).get_statistics(letter) == []


def test_full_type_checking_with_mypy_for_code_quality() -> None:
	stdout, stderr, exit_code = mypy([
		*FilesToCheck,
		"--strict",
		"--follow-untyped-imports",
		"--python-executable=" + sys.executable,
		f"--python-version={sys.version_info.major}.{sys.version_info.minor}",
	])
	assert stdout == "Success: no issues found in 6 source files\n"
	assert not stderr
	assert exit_code == 0


def test_no_spelling_errors_with_codespell_for_code_quality() -> None:
	assert codespell(*FilesToCheck) == 0


def test_no_out_of_date_requirements_for_code_quality() -> None:
	"""Assumes requirements.txt is of the format foo==bar, not >= or <=."""
	pip_list_outdated = json.loads(subprocess.run(
		[sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
		capture_output=True,
		check=True,
		input=None,
	).stdout.decode().lower())
	outdated = {i["name"]: i["latest_version"] for i in pip_list_outdated}

	with Path("resources/requirements.txt").open("r", encoding="UTF-8") as f:
		req_lines = {
			i.split("==")[0].split("[")[0]
			for i in f.read().lower().split("\n")
		}

	assert len([
		lib + version for lib, version in outdated.items() if lib in req_lines
	]) == 0


def test_mock_context_channel_added_to_guild() -> None:
	g = MockGuild(channels=[])
	ch = MockChannel(channel_id=92835, guild=None)
	assert ch not in g.channels
	ctx = MockContext(Bot.BeardlessBot, channel=ch, guild=g)
	assert ctx.guild == g
	assert ch in g.channels


def test_mock_context_author_added_to_members() -> None:
	g = MockGuild(members=[])
	m = MockMember(nick="Foobar")
	assert m not in g.members
	ctx = MockContext(Bot.BeardlessBot, author=m, guild=g)
	assert ctx.guild == g
	assert m in g.members


@MarkAsync
async def test_mock_guild_chunked() -> None:
	member = MockMember(MockUser("foobar"))
	guild = MockGuild(members=[member], chunked=False)
	assert not guild.chunked
	assert await guild.chunk() == [member]
	assert guild.chunked


@MarkAsync
async def test_msg_delete_waits_for_delay() -> None:
	ch = MockChannel()
	msg = MockMessage(content="foo", channel=ch, guild=MockGuild())
	assert len([i async for i in ch.history()]) == 1

	start_time = time.perf_counter()
	await msg.delete(delay=0.25)
	end_time = time.perf_counter()
	assert round(end_time - start_time, 2) == 0.25

	assert len([i async for i in ch.history()]) == 0


@MarkAsync
async def test_on_command_error(caplog: pytest.LogCaptureFixture) -> None:
	author = MockMember(admin_powers=True)
	guild = MockGuild()
	ctx = MockContext(
		Bot.BeardlessBot,
		message=MockMessage(content="!brawllegend foobar"),
		author=author,
		guild=guild,
		invoked_with="brawllegend",
	)
	exc = commands.errors.CommandError("Foobar")
	assert await Bot.on_command_error(ctx, exc) == 1
	assert caplog.records[0].args == (
		exc,
		"brawllegend",
		author,
		"!brawllegend foobar",
		guild,
		commands.errors.CommandError,
	)

	exc = commands.CommandNotFound("Foobar")
	assert await Bot.on_command_error(ctx, exc) == 0

	ctx.message.content = "!brawllegend \""
	quote_error = commands.UnexpectedQuoteError("\"")
	assert await Bot.on_command_error(ctx, quote_error) == 1
	assert caplog.records[1].args == (
		quote_error,
		"brawllegend",
		author,
		"!brawllegend \"",
		guild,
		commands.errors.UnexpectedQuoteError,
	)
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].title == "Careful with quotation marks!"


@MarkAsync
async def test_role_creation_reason_logged(
	caplog: pytest.LogCaptureFixture,
) -> None:
	# Reasons for actions are normally recorded in the audit log; I don't
	# have an easy way to access that. Instead, log it.
	g = MockGuild(roles=[])
	assert len(g.roles) == 1
	caplog.set_level(logging.INFO)
	await g.create_role(name="Spamalot", reason="FooBarSpam")
	assert len(caplog.records) == 1
	assert caplog.records[0].getMessage() == "Role creation reason: FooBarSpam"
	assert len(g.roles) == 2
	assert g.roles[1].name == "Spamalot"

	await g.create_role(name="Foobar")
	assert len(caplog.records) == 1
	assert len(g.roles) == 3
	assert g.roles[2].name == "Foobar"


@MarkAsync
async def test_create_muted_role(caplog: pytest.LogCaptureFixture) -> None:
	g = MockGuild(roles=[])
	assert len(g.roles) == 1
	caplog.set_level(logging.INFO)
	role = await misc.create_muted_role(g)
	assert role.name == "Muted"
	assert role.colour.value == 0x818386
	assert not role.permissions.send_messages
	assert role.permissions.read_messages
	assert len(g.roles) == 2
	assert g.roles[1] == role
	assert not g.channels[0].permissions_for(role).send_messages
	assert caplog.records[0].getMessage() == (
		"Role creation reason: BB Muted Role"
	)
	assert caplog.records[1].args == (
		g.channels[0].id,
		role.id,
		"Preventing Muted users from chatting in this channel",
	)

	role = MockRole("Muted", 500)
	assert await misc.create_muted_role(MockGuild(roles=[role])) == role


def test_bot_avatar_correct_on_creation() -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	assert Bot.BeardlessBot.user is not None
	assert isinstance(Bot.BeardlessBot.user._avatar, str)
	assert isinstance(Bot.BeardlessBot.user.avatar, nextcord.Asset)
	assert Bot.BeardlessBot.user.avatar.url == (
		f"https://cdn.discordapp.com/avatars/{misc.BbId}/"
		f"{Bot.BeardlessBot.user.avatar.key}.png?size=1024"
	)


@MarkAsync
async def test_bot_change_presence() -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	assert Bot.BeardlessBot.activity is not None
	assert Bot.BeardlessBot.activity.name == "Try !blackjack and !flip"
	assert Bot.BeardlessBot.status == nextcord.Status.online
	await Bot.BeardlessBot.change_presence(
		activity=None, status=nextcord.Status.dnd,
	)
	assert Bot.BeardlessBot.activity is None
	assert Bot.BeardlessBot.status == nextcord.Status.dnd

	await Bot.BeardlessBot.change_presence(activity=nextcord.Game("Foo"))
	assert Bot.BeardlessBot.activity is not None
	assert Bot.BeardlessBot.activity.name == "Foo"


@MarkAsync
async def test_on_ready(caplog: pytest.LogCaptureFixture) -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	caplog.set_level(logging.INFO)
	await Bot.on_ready()
	assert isinstance(Bot.BeardlessBot.activity, nextcord.CustomActivity)
	assert Bot.BeardlessBot.activity.state == "Try !blackjack and !flip"
	assert Bot.BeardlessBot.status == nextcord.Status.online
	assert caplog.records[-1].msg == (
		"Chunking complete! Beardless Bot serves"
		" %i unique members across %i servers."
	)
	assert caplog.records[-1].args == (1, 1)

	Bot.BeardlessBot._connection._guilds[2] = MockGuild(
		name="Foo",
		guild_id=1,
		members=Bot.BeardlessBot._connection._guilds[1].members,
	)
	await Bot.on_ready()
	assert caplog.records[-1].args == (1, 2)

	Bot.BeardlessBot._connection._guilds[3] = MockGuild(
		name="Foo",
		guild_id=1,
		members=[MockMember(MockUser(user_id=12, name="Foobar"))],
	)
	await Bot.on_ready()
	assert caplog.records[-1].args == (2, 3)


@MarkAsync
async def test_on_ready_raises_exceptions(
	caplog: pytest.LogCaptureFixture,
) -> None:

	def mock_raise_http_exception(
		bot: commands.Bot, avatar: str,
	) -> None:
		resp = requests.Response()
		resp.status = misc.BadRequest  # type: ignore[attr-defined]
		raise nextcord.HTTPException(resp, f"{bot}, avatar {avatar}")

	def mock_raise_file_not_found_error(filepath: str, mode: str) -> None:
		raise FileNotFoundError(filepath + "," + mode)

	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	Bot.BeardlessBot._connection._guilds = {}
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(MockBot.MockClientUser, "edit", mock_raise_http_exception)
		await Bot.on_ready()
	assert caplog.records[0].msg == "Failed to update avatar!"
	assert caplog.records[1].msg == "Bot is in no servers! Add it to a server."

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("aiofiles.open", mock_raise_file_not_found_error)
		await Bot.on_ready()
	assert caplog.records[2].msg == (
		"Avatar file not found! Check your directory structure."
	)
	assert caplog.records[3].msg == "Bot is in no servers! Add it to a server."


@MarkAsync
async def test_on_guild_join(caplog: pytest.LogCaptureFixture) -> None:
	ch = MockChannel()
	g = MockGuild(
		guild_id=39,
		name="Foo",
		roles=[MockRole(name="Beardless Bot")],
		channels=[ch],
	)
	g._state.user = MockUser(admin_powers=True)  # type: ignore[assignment]
	await Bot.on_guild_join(g)
	m = await latest_message(ch)
	assert m is not None
	emb = m.embeds[0]
	assert emb.title == "Hello, Foo!"
	assert isinstance(emb.description, str)
	assert emb.description.startswith("Thanks for adding me to Foo!")
	assert "my <@&123456789> role" in emb.description

	u = MockUser(admin_powers=False)
	g._state.user = u  # type: ignore[assignment]
	assert hasattr(g._state.http, "user")
	g._state.http.user = u
	caplog.set_level(logging.INFO)
	u.guild = g  # type: ignore[attr-defined]
	g._members[len(g._members)] = MockMember(u)
	assert hasattr(u, "guild")
	assert u.guild == g
	await Bot.on_guild_join(g)
	m = await latest_message(ch)
	assert m is not None
	emb = m.embeds[0]
	assert emb.title == "I need admin perms!"
	assert emb.description == misc.AdminPermsReasons
	assert caplog.records[3].getMessage() == "Left Foo."
	assert hasattr(u, "guild")
	assert u.guild is None


@pytest.mark.parametrize(
	("msg_length", "description"),
	[
		(1, "e"),
		(0, "**Embed**"),
		(1025, "**Message length exceeds 1024 characters.**"),
	],
)
def test_content_check(msg_length: int, description: str) -> None:
	assert misc.content_check(MockMessage("e" * msg_length)) == description


def test_content_check_custom_limit() -> None:
	assert misc.content_check(
		MockMessage("e" * 917), 108,
	) == "**Message length exceeds 1024 characters.**"

	assert misc.content_check(
		MockMessage("e" * 2000), -2000,
	) == "**Message length exceeds 1024 characters.**"

	assert misc.content_check(MockMessage(""), 1025) == "**Embed**"


@MarkAsync
async def test_no_log_messages_sent_when_no_log_channel_defined() -> None:
	ch = MockChannel(channel_id=0, name="bar")
	guild = MockGuild(channels=[ch])
	m = MockMember(guild=guild)
	message = MockMessage(content="foo", guild=guild)
	assert await Bot.on_message_delete(message) is None
	assert await Bot.on_member_join(m) is None
	assert await Bot.on_member_remove(m) is None
	assert await Bot.on_message_edit(
		message, MockMessage(content="spam", guild=guild),
	) is None
	assert await Bot.on_member_ban(guild, m) is None
	assert await Bot.on_member_unban(guild, m) is None
	assert await Bot.on_member_update(m, m) is None
	assert await Bot.on_bulk_message_delete([message]) is None
	assert await Bot.on_guild_channel_delete(ch) is None
	assert await Bot.on_guild_channel_create(ch) is None

	reaction = nextcord.Reaction(
		message=message, data=MockMessage.get_mock_reaction_payload("foo"),
	)
	assert await Bot.on_reaction_clear(message, [reaction]) is None

	th = MockThread(parent=ch, me=None, name="Foo")
	assert await Bot.on_thread_join(th) is None
	th.me = None
	assert await Bot.on_thread_join(th) is None
	assert await Bot.on_thread_delete(th) is None
	assert await Bot.on_thread_update(th, th) is None


@MarkAsync
async def test_on_message_delete() -> None:
	ch = MockChannel(name=misc.LogChannelName)
	m = MockMessage(channel=ch)
	m.guild = MockGuild(channels=[ch])
	emb = await Bot.on_message_delete(m)
	assert emb is not None
	log = logs.log_delete_msg(m)
	assert emb.description == log.description
	assert log.description == (
		"**Deleted message sent by <@123456789>"
		" in **<#123456789>\ntestcontent"
	)
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == log.description


@MarkAsync
async def test_on_bulk_message_delete() -> None:
	ch = MockChannel(name=misc.LogChannelName)
	m = MockMessage(channel=ch)
	m.guild = MockGuild(channels=[ch])
	messages = [m, m, m]
	emb = await Bot.on_bulk_message_delete(messages)
	assert emb is not None
	log = logs.log_purge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == "Purged 2 messages in <#123456789>."
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == log.description

	messages = [m] * 105
	emb = await Bot.on_bulk_message_delete(messages)
	assert emb is not None
	log = logs.log_purge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == "Purged 99+ messages in <#123456789>."


@MarkAsync
async def test_on_reaction_clear() -> None:
	ch = MockChannel(channel_id=0, name=misc.LogChannelName)
	guild = MockGuild(channels=[ch])
	reaction = nextcord.Reaction(
		message=MockMessage(),
		data=MockMessage.get_mock_reaction_payload("foo"),
	)
	other_reaction = nextcord.Reaction(
		message=MockMessage(),
		data=MockMessage.get_mock_reaction_payload("bar"),
	)
	msg = MockMessage(guild=guild)
	emb = await Bot.on_reaction_clear(msg, [reaction, other_reaction])
	assert emb is not None
	assert emb.description == (
		"Reactions cleared from message sent by <@123456789> in <#123456789>."
	)

	assert emb.fields[0].value is not None
	assert emb.fields[0].value.startswith(msg.content)
	assert emb.fields[1].value == "<:foo:0>, <:bar:0>"
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == emb.description


@MarkAsync
async def test_on_guild_channel_delete() -> None:
	ch = MockChannel(name=misc.LogChannelName)
	g = MockGuild(channels=[ch])
	new_channel = MockChannel(guild=g)
	emb = await Bot.on_guild_channel_delete(new_channel)
	assert emb is not None
	log = logs.log_delete_channel(new_channel)
	assert emb.description == log.description
	assert log.description == "Channel \"testchannelname\" deleted."
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == log.description


@MarkAsync
async def test_on_guild_channel_create() -> None:
	ch = MockChannel(name=misc.LogChannelName)
	g = MockGuild(channels=[ch])
	new_channel = MockChannel(guild=g)
	emb = await Bot.on_guild_channel_create(new_channel)
	assert emb is not None
	log = logs.log_create_channel(new_channel)
	assert emb.description == log.description
	assert log.description == "Channel \"testchannelname\" created."
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == log.description


@MarkAsync
async def test_on_member_ban() -> None:
	ch = MockChannel(name=misc.LogChannelName)
	g = MockGuild(channels=[ch])
	member = MockMember()
	emb = await Bot.on_member_ban(g, member)
	assert emb is not None
	log = logs.log_ban(member)
	assert emb.description == log.description
	assert log.description == "Member <@123456789> banned\ntestname"
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == log.description


@MarkAsync
async def test_on_member_unban() -> None:
	ch = MockChannel(name=misc.LogChannelName)
	g = MockGuild(channels=[ch])
	member = MockMember()
	emb = await Bot.on_member_unban(g, member)
	assert emb is not None
	log = logs.log_unban(member)
	assert emb.description == log.description
	assert (
		log.description == "Member <@123456789> unbanned\ntestname"
	)
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == log.description


@MarkAsync
async def test_on_member_join() -> None:
	member = MockMember()
	ch = MockChannel(name=misc.LogChannelName)
	member.guild = MockGuild(channels=[ch])
	emb = await Bot.on_member_join(member)
	assert emb is not None
	log = logs.log_member_join(member)
	assert emb.description == log.description
	assert log.description == (
		"Member <@123456789> joined\nAccount registered"
		f" on {misc.truncate_time(member)}\nID: 123456789"
	)
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == log.description


@MarkAsync
async def test_on_member_remove() -> None:
	member = MockMember()
	ch = MockChannel(name=misc.LogChannelName)
	member.guild = MockGuild(channels=[ch])
	emb = await Bot.on_member_remove(member)
	assert emb is not None
	log = logs.log_member_remove(member)
	assert emb.description == log.description
	assert log.description == "Member <@123456789> left\nID: 123456789"

	member.roles = [member.guild.roles[0], member.guild.roles[0]]
	emb = await Bot.on_member_remove(member)
	assert emb is not None
	log = logs.log_member_remove(member)
	assert emb.description == log.description
	assert log.fields[0].value == "<@&123456789>"
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == log.description


@MarkAsync
async def test_on_member_update() -> None:
	ch = MockChannel(name=misc.LogChannelName)
	guild = MockGuild(channels=[ch])
	old = MockMember(nick="a", roles=[], guild=guild)
	new = MockMember(nick="b", roles=[], guild=guild)
	emb = await Bot.on_member_update(old, new)
	assert emb is not None
	log = logs.log_member_nick_change(old, new)
	assert emb.description == log.description
	assert log.description == "Nickname of <@123456789> changed."
	assert log.fields[0].value == old.nick
	assert log.fields[1].value == new.nick
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == log.description

	r = MockRole()
	guild.assign_guild_to_role(r)
	new = MockMember(nick="a", guild=guild, roles=[r])
	assert new.guild is not None
	emb = await Bot.on_member_update(old, new)
	assert emb is not None
	log = logs.log_member_roles_change(old, new)
	assert emb.description == log.description
	assert log.description == "Role <@&123456789> added to <@123456789>."

	emb = await Bot.on_member_update(new, old)
	assert emb is not None
	log = logs.log_member_roles_change(new, old)
	assert emb.description == log.description
	assert log.description == "Role <@&123456789> removed from <@123456789>."

	assert (await Bot.on_member_update(old, old)) is None


@MarkAsync
async def test_on_message_edit() -> None:
	ch = MockChannel(name=misc.LogChannelName)
	member = MockMember(user=MockUser(user_id=37))
	g = MockGuild(channels=[ch, MockChannel(name="infractions")], roles=[])
	assert len(g.roles) == 1
	before = MockMessage(content="old", author=member, guild=g)
	assert (await Bot.on_message_edit(before, before)) is None
	after = MockMessage(content="new", author=member, guild=g)
	emb = await Bot.on_message_edit(before, after)
	assert isinstance(emb, nextcord.Embed)
	log = logs.log_edit_msg(before, after)
	assert emb.description == log.description
	assert emb.description == (
		f"Messaged edited by {member.mention} in <#123456789>."
	)
	assert emb.fields[0].value == before.content
	assert emb.fields[1].value == (
		f"new\n[Jump to Message]({after.jump_url})"
	)

	scam_message = "http://dizcort.com free nitro!"
	after.content = scam_message
	emb = await Bot.on_message_edit(before, after)
	assert emb is not None
	assert len(g.roles) == len(member.roles) == 2
	assert g.roles[1].name == member.roles[1].name == "Muted"
	# TODO: edit after to have content of len > 1024 via message.edit
	h = [i async for i in ch.history()]
	assert len(h) == 3
	assert not any(i.content == scam_message for i in ch.messages)
	assert h[0].embeds[0].description == log.description
	assert h[1].content.startswith("Deleted possible")
	assert h[2].embeds[0].description == emb.description

	# Mute should not add muted role twice, should still log edit twice
	assert len(g.roles) == len(member.roles) == 2
	assert member.roles[1].name == "Muted"
	emb = await Bot.on_message_edit(
		before, MockMessage(content=scam_message, author=member, guild=g),
	)
	assert emb is not None
	assert len(member.roles) == 2
	h = [i async for i in ch.history()]
	assert len(h) == 5
	assert h[3].content == h[1].content
	assert h[4].embeds[0].description == h[2].embeds[0].description

	after.guild = None
	after.content = "bar"
	assert (await Bot.on_message_edit(before, after)) is None


@MarkAsync
async def test_on_thread_join() -> None:
	ch = MockChannel(channel_id=0, name=misc.LogChannelName)
	ch.guild = MockGuild(channels=[ch])
	thread = MockThread(parent=ch, me=MockMember(), name="Foo")
	assert await Bot.on_thread_join(thread) is None

	thread.me = None
	thread._members = {}
	emb = await Bot.on_thread_join(thread)
	assert len(thread.members) == 1
	assert emb is not None
	assert emb.description == (
		"Thread \"Foo\" created in parent channel <#0>."
	)
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == emb.description


@MarkAsync
async def test_on_thread_delete() -> None:
	ch = MockChannel(channel_id=0, name=misc.LogChannelName)
	ch.guild = MockGuild(channels=[ch])
	thread = MockThread(parent=ch, name="Foo")
	emb = await Bot.on_thread_delete(thread)
	assert emb is not None
	assert emb.description == (
		"Thread \"Foo\" deleted."
	)
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == emb.description


@MarkAsync
async def test_on_thread_update() -> None:
	ch = MockChannel(channel_id=0, name=misc.LogChannelName)
	ch.guild = MockGuild(channels=[ch])
	before = MockThread(parent=ch, name="Foo")
	after = MockThread(parent=ch, name="Foo")
	assert await Bot.on_thread_update(before, after) is None

	before.archived = True
	before.archive_timestamp = datetime.now(misc.TimeZone)
	emb = await Bot.on_thread_update(before, after)
	assert emb is not None
	assert emb.description == "Thread \"Foo\" unarchived."
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == emb.description

	emb = await Bot.on_thread_update(after, before)
	assert emb is not None
	assert emb.description == "Thread \"Foo\" archived."
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == emb.description

	before.archived = False
	before.locked = True
	emb = await Bot.on_thread_update(before, after)
	assert emb is not None
	assert emb.description == "Thread \"Foo\" unlocked."
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == emb.description

	emb = await Bot.on_thread_update(after, before)
	assert emb is not None
	assert emb.description == "Thread \"Foo\" locked."
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.embeds[0].description == emb.description


@MarkAsync
async def test_cmd_dice() -> None:
	ctx = MockContext(
		Bot.BeardlessBot,
		author=MockMember(MockUser(user_id=400005678)),
		guild=MockGuild(),
	)
	emb: nextcord.Embed = await Bot.cmd_dice(ctx)
	assert isinstance(emb, nextcord.Embed)
	assert isinstance(emb.description, str)
	assert emb.description.startswith(
		"Welcome to Beardless Bot dice, <@400005678>!",
	)
	latest = await latest_message(ctx)
	assert latest is not None
	assert latest.embeds[0].description == emb.description


@MarkAsync
async def test_cmd_bucks() -> None:
	ctx = MockContext(Bot.BeardlessBot)
	emb: nextcord.Embed = await Bot.cmd_bucks(ctx)
	assert isinstance(emb, nextcord.Embed)
	assert isinstance(emb.description, str)
	assert emb.description.startswith(
		"BeardlessBucks are this bot's special currency.",
	)
	latest = await latest_message(ctx)
	assert latest is not None
	assert latest.embeds[0].description == emb.description


@MarkAsync
async def test_cmd_hello() -> None:
	ctx = MockContext(Bot.BeardlessBot)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.choice", operator.itemgetter(0))
		assert await Bot.cmd_hello(ctx) == 1
	latest = await latest_message(ctx)
	assert latest is not None
	assert latest.content == "How ya doin'?"

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.choice", operator.itemgetter(5))
		assert await Bot.cmd_hello(ctx) == 1
	latest = await latest_message(ctx)
	assert latest is not None
	assert latest.content == "Hi!"


@MarkAsync
async def test_cmd_source() -> None:
	ctx = MockContext(Bot.BeardlessBot)
	assert await Bot.cmd_source(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].title == "Beardless Bot Fun Facts"


@MarkAsync
async def test_cmd_add() -> None:
	ctx = MockContext(Bot.BeardlessBot)
	assert await Bot.cmd_add(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	emb = m.embeds[0]
	misc_emb = misc.Invite_Embed
	assert emb.title == misc_emb.title
	assert emb.description == misc_emb.description
	assert isinstance(emb.description, str)
	assert emb.description.split("]")[1] == misc.AddUrl


@MarkAsync
async def test_cmd_fact() -> None:
	ctx = MockContext(Bot.BeardlessBot)
	first_fact = (
		"The scientific term for brain freeze"
		" is sphenopalatine ganglioneuralgia."
	)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.choice", operator.itemgetter(0))
		assert misc.fact() == first_fact

		mp.setattr("random.randint", lambda _, y: y)
		assert await Bot.cmd_fact(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	emb = m.embeds[0]
	assert emb.description == first_fact
	assert emb.title == "Beardless Bot Fun Fact #111111111"


@MarkAsync
async def test_cmd_animals() -> None:
	ctx = MockContext(Bot.BeardlessBot)
	assert await Bot.cmd_animals(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	emb = m.embeds[0]
	assert len(emb.fields) == 9
	assert emb.fields[0].value == (
		"Can also do !dog breeds to see breeds you"
		" can get pictures of with !dog [breed]"
	)
	assert all(i.value == "_ _" for i in emb.fields[1:])

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("misc.AnimalList", ("frog", "cat"))
		assert await Bot.cmd_animals(ctx) == 1
	latest = await latest_message(ctx)
	assert latest is not None
	assert len(latest.embeds[0].fields) == 3


def test_tweet() -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda x, _: x)
		egg_tweet = misc.tweet()
	assert ("\n" + egg_tweet).startswith(misc.format_tweet(egg_tweet))
	assert len(egg_tweet.split(" ")) == 11

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.choice", lambda _: "the")
		mp.setattr("random.randint", lambda x, _: x)
		egg_tweet = misc.tweet()

	assert egg_tweet == "The" + (" the" * 10)

	assert misc.format_tweet("test tweet.") == "\ntest tweet"
	assert misc.format_tweet("test tweet") == "\ntest tweet"


@MarkAsync
async def test_cmd_tweet() -> None:
	ctx = MockContext(
		Bot.BeardlessBot, guild=MockGuild(guild_id=Bot.EggGuildId),
	)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("misc.tweet", lambda: "foobar!")
		assert await Bot.cmd_tweet(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	emb = m.embeds[0]
	assert emb.description == "\nfoobar"

	ctx = MockContext(Bot.BeardlessBot, guild=MockGuild())
	assert await Bot.cmd_tweet(ctx) == 0


@pytest.mark.parametrize("side", [4, 6, 8, 10, 12, 20, 100])
def test_dice_regular(side: int) -> None:
	member = MockMember()
	text = "d" + str(side)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda _, y: y)
		roll = misc.roll(text)
	assert roll is not None
	assert roll[0] == side

	report = misc.roll_report(text, member)
	assert isinstance(report.description, str)
	assert report.description.startswith("You got")
	assert isinstance(report.title, str)
	assert text in report.title


def test_dice_irregular() -> None:
	member = MockMember()
	emb = misc.roll_report("d20-4", member)
	assert isinstance(emb.description, str)
	assert emb.description.startswith("You got")

	assert misc.roll("wrongroll") is None

	assert misc.roll("d9") is None

	emb = misc.roll_report("d9", member)
	assert isinstance(emb.description, str)
	assert emb.description.startswith("Invalid")

	assert misc.roll("d40") is None

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda _, y: y)
		roll = misc.roll("d20-4")
		assert roll is not None
		assert roll[0] == 16

		results = misc.roll("d100+asfjksdfhkdsfhksd")
	assert results is not None
	assert len(results) == 5
	assert results[0] == 100
	assert results[4] == 0


@pytest.mark.parametrize("count", [-5, 1, 2, 3, 5, 100])
def test_dice_multiple(count: int) -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda _, y: y)
		roll = misc.roll(str(count) + "d4")
	assert roll is not None
	assert roll[0] == abs(count) * 4


def test_dice_multiple_irregular() -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda _, y: y)
		roll = misc.roll("10d20-4")
		assert roll is not None
		assert roll[0] == 196

		roll = misc.roll("ad100")
		assert roll is not None
		assert roll[0] == 100

		roll = misc.roll("0d8")
		assert roll is not None
		assert roll[0] == 0

		roll = misc.roll("0d12+57")
		assert roll is not None
		assert roll[0] == 57


def test_log_mute() -> None:
	message = MockMessage(channel=MockChannel(channel_id=1))
	member = MockMember(MockUser(user_id=2))
	assert logs.log_mute(member, message, "5 hours").description == (
		"Muted <@2> for 5 hours in <#1>."
	)

	assert logs.log_mute(member, message, None).description == (
		"Muted <@2> in <#1>."
	)


def test_log_unmute() -> None:
	assert logs.log_unmute(
		MockMember(MockUser(user_id=3)), MockMember(),
	).description == "Unmuted <@3>."


def test_get_log_channel() -> None:
	assert misc.get_log_channel(MockGuild()) is None
	ch = misc.get_log_channel(
		MockGuild(channels=[MockChannel(name=misc.LogChannelName)]),
	)
	assert isinstance(ch, nextcord.TextChannel)
	assert ch.name == misc.LogChannelName


def test_fetch_avatar_custom() -> None:
	member = MockUser(user_id=12121212)
	assert isinstance(member.avatar, nextcord.Asset)
	assert member.avatar.url == (
		"https://cdn.discordapp.com/avatars/12121212/"
		"7b6ea511d6e0ef6d1cdb2f7b53946c03.png?size=1024"
	)
	assert misc.fetch_avatar(member) == member.avatar.url


def test_fetch_avatar_default() -> None:
	member = MockMember(MockUser(user_id=5000000, custom_avatar=False))
	assert member.avatar is None
	assert member.default_avatar.url == (
		f"https://cdn.discordapp.com/embed/avatars/{(member.id >> 22) - 1}.png"
	)
	assert misc.fetch_avatar(member) == member.default_avatar.url


@pytest.mark.parametrize(
	("username", "content"),
	[
		("searchterm", "searchterm#9999"),
		("searchterm", "searchterm"),
		("searchterm", "search"),
		("searchterm", "testnick"),
		("hash#name", "hash#name"),
	],
)
def test_member_search_valid(username: str, content: str) -> None:
	m = MockMember(MockUser(username, discriminator="9999"), "testnick")
	text = MockMessage(
		content=content, guild=MockGuild(members=[MockMember(), m]),
	)
	assert misc.member_search(text, content) == m


def test_member_search_invalid() -> None:
	m = MockMember(MockUser("searchterm", discriminator="9999"))
	text = MockMessage(
		content="invalidterm", guild=MockGuild(members=[MockMember(), m]),
	)
	assert misc.member_search(text, text.content) is None


@MarkAsync
async def test_cmd_register() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", user_id=misc.BbId),
		"Beardless Bot",
	)
	bucks.reset(bb)
	ctx = MockContext(Bot.BeardlessBot, author=bb)
	assert (await Bot.cmd_register(ctx)) == 1
	emb = bucks.register(bb)
	assert emb.description == (
		"You are already in the system! Hooray! You"
		f" have 200 BeardlessBucks, <@{misc.BbId}>."
	)
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description == emb.description

	bb._user.name = ",badname,"
	assert bucks.register(bb).description == (
		bucks.CommaWarn.format(f"<@{misc.BbId}>")
	)


@MarkAsync
@pytest.mark.parametrize(
	("target", "result"),
	[
		(
			MockMember(MockUser("Test", "5757", misc.BbId)),
			"'s balance is 200",
		),
		(MockMember(MockUser(",")), bucks.CommaWarn.format("<@123456789>")),
	],
)
async def test_cmd_balance(target: nextcord.User, result: str) -> None:
	msg = MockMessage("!bal", guild=MockGuild())
	desc = bucks.balance(target, msg).description
	ctx = MockContext(Bot.BeardlessBot, author=target, message=msg)
	assert isinstance(desc, str)
	assert result in desc
	assert (await Bot.cmd_balance(ctx, target="")) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description == desc


def test_balance_invalid() -> None:
	msg = MockMessage("!bal", guild=MockGuild())
	desc = bucks.balance("Invalid user", msg).description
	assert isinstance(desc, str)
	assert "Invalid user!" in desc


def test_reset() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", user_id=misc.BbId),
		"Beardless Bot",
	)
	assert bucks.reset(bb).description == (
		f"You have been reset to 200 BeardlessBucks, <@{misc.BbId}>."
	)

	bb._user.name = ",badname,"
	assert bucks.reset(bb).description == (
		bucks.CommaWarn.format(f"<@{misc.BbId}>")
	)


def test_write_money() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", user_id=misc.BbId),
		"Beardless Bot",
	)
	bucks.reset(bb)
	assert bucks.write_money(
		bb, "-all", writing=False, adding=False,
	) == (bucks.MoneyFlags.BalanceUnchanged, 200)

	assert bucks.write_money(
		bb, -1000000, writing=True, adding=False,
	) == (bucks.MoneyFlags.NotEnoughBucks, None)


def test_leaderboard() -> None:
	lb = bucks.leaderboard()
	assert lb.title == "BeardlessBucks Leaderboard"
	assert len(lb.fields) == 10
	assert lb.fields[0].value is not None
	assert lb.fields[1].value is not None
	assert int(lb.fields[0].value) > int(lb.fields[1].value)

	lb = bucks.leaderboard(
		MockMember(MockUser(name="bad,name", user_id=0)),
		MockMessage(author=MockMember()),
	)
	assert len(lb.fields) == 10

	lb = bucks.leaderboard(
		MockMember(
			MockUser("Beardless Bot", discriminator="5757", user_id=misc.BbId),
			"Beardless Bot",
		),
		MockMessage(),
	)
	assert len(lb.fields) == 12
	assert lb.fields[-1].name == "Beardless Bot's balance:"

	g = MockGuild([
		MockMember(MockUser("Foobar", user_id=misc.BbId)),
		MockMember(MockUser("Spam")),
	])
	lb = bucks.leaderboard("Foobar", MockMessage(guild=g))
	assert lb.fields[-1].name == "Foobar's balance:"


@MarkAsync
async def test_define_valid(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		json=[{
			"word": "foo",
			"phonetics": [{"audio": "spam"}],
			"meanings": [{"definitions": [{"definition": "Foobar"}]}],
		}],
	)
	word = await misc.define("foo")
	assert word.title == "FOO"
	assert word.description == "Audio: spam"


@MarkAsync
async def test_define_more_than_max_embed_fields(
	httpx_mock: HTTPXMock,
) -> None:
	excess_defns = [{"definition": "Foobar"}] * (misc.MaxEmbedFields + 5)
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		json=[{
			"word": "foo",
			"phonetics": [],
			"meanings": [{"definitions": excess_defns}],
		}],
	)
	word = await misc.define("foo")
	assert word.title == "FOO"
	assert len(word.fields) == misc.MaxEmbedFields


@MarkAsync
async def test_define_no_audio_has_blank_description(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		json=[{
			"word": "foo",
			"phonetics": [],
			"meanings": [{"definitions": [{"definition": "Foobar"}]}],
		}],
	)
	word = await misc.define("foo")
	assert word.title == "FOO"
	assert word.description == ""


@MarkAsync
async def test_define_invalid_word_returns_no_results_found(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		status_code=misc.BadRequest,
	)
	assert (await misc.define("foo")).description == "No results found."


@MarkAsync
async def test_define_api_down_returns_error_message(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/test",
		status_code=400,
	)
	word = await misc.define("test")
	assert isinstance(word.description, str)
	assert word.description.startswith("There was an error")


@MarkAsync
@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
async def test_cmd_define(httpx_mock: HTTPXMock) -> None:
	ctx = MockContext(Bot.BeardlessBot)
	resp = [{"word": "f", "phonetics": [], "meanings": [{"definitions": []}]}]
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/f", json=resp,
	)
	assert await Bot.cmd_define(ctx, words="f") == 1
	m = await latest_message(ctx)
	assert m is not None
	definition = await misc.define("f")
	assert m.embeds[0].title == definition.title == "F"


@MarkAsync
async def test_cmd_ping() -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	ctx = MockContext(Bot.BeardlessBot)
	assert await Bot.cmd_ping(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description == "Beardless Bot's latency is 25 ms."

	Bot.BeardlessBot._connection.user = None
	assert await Bot.cmd_ping(ctx) == -1


def test_flip() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", user_id=misc.BbId),
		"Beardless Bot",
	)
	assert bucks.flip(bb, "0").endswith("actually bet anything.")

	assert bucks.flip(bb, "invalidbet").startswith("Invalid bet.")

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda *_: 0)
		assert bucks.flip(bb, "all") == (
			"Tails! You lose! Your losses have been"
			f" deducted from your balance, <@{misc.BbId}>."
		)
	msg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(msg.description, str)
	assert "is 0" in msg.description

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda *_: 0)
		bucks.flip(bb, 37)
	msg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(msg.description, str)
	assert "is 163" in msg.description

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda *_: 1)
		assert bucks.flip(bb, "all") == (
			"Heads! You win! Your winnings have been"
			f" added to your balance, <@{misc.BbId}>."
		)
	msg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(msg.description, str)
	assert "is 400" in msg.description

	bucks.reset(bb)
	assert bucks.flip(bb, "10000000000000").startswith("You do not have")
	bucks.reset(bb)
	msg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(msg.description, str)
	assert "200" in msg.description

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"bucks.write_money",
			lambda *_, **__: (bucks.MoneyFlags.Registered, 0),
		)
		assert bucks.flip(bb, "0") == (
			bucks.NewUserMsg.format(f"<@{misc.BbId}>")
		)

	bb._user.name = ",invalidname,"
	assert bucks.flip(bb, "0") == bucks.CommaWarn.format(f"<@{misc.BbId}>")


@MarkAsync
async def test_cmd_flip() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", user_id=misc.BbId),
		"Beardless Bot",
	)
	ctx = MockContext(
		Bot.BeardlessBot, MockMessage("!flip 0"), author=bb, guild=MockGuild(),
	)
	Bot.BlackjackGames = []
	assert await Bot.cmd_flip(ctx, bet="0") == 1
	m = await latest_message(ctx)
	assert m is not None
	emb = m.embeds[0]
	assert emb.description is not None
	assert emb.description.endswith("actually bet anything.")

	Bot.BlackjackGames.append(bucks.BlackjackGame(bb, 10))
	assert await Bot.cmd_flip(ctx, bet="0") == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description == bucks.FinMsg.format(f"<@{misc.BbId}>")


def test_blackjack() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", user_id=misc.BbId),
		"Beardless Bot",
	)
	assert bucks.blackjack(bb, "invalidbet")[0].startswith("Invalid bet.")

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.BlackjackGame.perfect", lambda _: False)
		report, game = bucks.blackjack(bb, 0)
		assert isinstance(game, bucks.BlackjackGame)
		assert "You hit 21!" not in report

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.BlackjackGame.perfect", lambda _: True)
		report, game = bucks.blackjack(bb, "0")
		assert game is None
		assert "You hit 21" in report

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"bucks.write_money",
			lambda *_, **__: (bucks.MoneyFlags.Registered, 0),
		)
		assert bucks.blackjack(bb, "0")[0] == (
			bucks.NewUserMsg.format(f"<@{misc.BbId}>")
		)

	bucks.reset(bb)
	report = bucks.blackjack(bb, "10000000000000")[0]
	assert report.startswith("You do not have")

	bucks.reset(bb)
	bb._user.name = ",invalidname,"
	assert bucks.blackjack(bb, 0)[0] == (
		bucks.CommaWarn.format(f"<@{misc.BbId}>")
	)


@MarkAsync
async def test_cmd_blackjack() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", user_id=misc.BbId),
		"Beardless Bot",
	)
	ctx = MockContext(Bot.BeardlessBot, author=bb, guild=MockGuild())
	Bot.BlackjackGames = []
	assert await Bot.cmd_blackjack(ctx, bet="all") == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description is not None
	assert m.embeds[0].description.startswith("Your starting hand consists of")

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.BlackjackGame.perfect", lambda _: True)
		Bot.BlackjackGames = []
		assert await Bot.cmd_blackjack(ctx, bet="all") == 1
		m = await latest_message(ctx)
		assert m is not None
		assert m.embeds[0].description is not None
		assert m.embeds[0].description.endswith(
			f"You hit {bucks.BlackjackGame.Goal}! You win, {bb.mention}!",
		)

	Bot.BlackjackGames.append(bucks.BlackjackGame(bb, 10))
	assert await Bot.cmd_blackjack(ctx, bet="0") == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description is not None
	assert m.embeds[0].description == bucks.FinMsg.format(f"<@{misc.BbId}>")


@MarkAsync
async def test_cmd_deal() -> None:
	Bot.BlackjackGames = []
	bb = MockMember(
		MockUser("Beardless,Bot", discriminator="5757", user_id=misc.BbId),
	)
	ctx = MockContext(Bot.BeardlessBot, author=bb, guild=MockGuild())
	assert await Bot.cmd_deal(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description == bucks.CommaWarn.format(f"<@{misc.BbId}>")

	bb._user.name = "Beardless Bot"
	assert await Bot.cmd_deal(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description == bucks.NoGameMsg.format(f"<@{misc.BbId}>")

	game = bucks.BlackjackGame(bb, 0)
	game.hand = [2, 2]
	Bot.BlackjackGames = []
	Bot.BlackjackGames.append(game)
	assert await Bot.cmd_deal(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	emb = m.embeds[0]
	assert len(game.hand) == 3
	assert emb.description is not None
	assert emb.description.startswith("You were dealt")

	game = bucks.BlackjackGame(bb, 0)
	game.hand = [10, 10, 10]
	Bot.BlackjackGames = []
	Bot.BlackjackGames.append(game)
	assert await Bot.cmd_deal(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	emb = m.embeds[0]
	assert emb.description is not None
	assert f"You busted. Game over, <@{misc.BbId}>." in emb.description
	assert len(Bot.BlackjackGames) == 0

	game = bucks.BlackjackGame(bb, 0)
	game.hand = [10, 10]
	Bot.BlackjackGames.append(game)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.BlackjackGame.perfect", lambda _: True)
		mp.setattr("bucks.BlackjackGame.check_bust", lambda _: False)
		assert await Bot.cmd_deal(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	emb = m.embeds[0]
	assert emb.description is not None
	assert f"You hit 21! You win, <@{misc.BbId}>!" in emb.description
	assert len(Bot.BlackjackGames) == 0


def test_blackjack_deal_to_player_treats_ace_as_1_when_going_over() -> None:
	game = bucks.BlackjackGame(MockMember(), 10)
	game.hand = [8, 11]
	with pytest.MonkeyPatch.context() as mp:
		game.deck = [3, 4, 5]
		mp.setattr("random.randint", lambda x, _: x)
		game.deal_to_player()
	assert len(game.hand) == 3
	assert sum(game.hand) == 12
	assert game.message.startswith(
		"You were dealt a 3, bringing your total to 22. To avoid busting,"
		" your Ace will be treated as a 1. Your new total is 12.",
	)


def test_blackjack_deal_to_player_wins_when_reaching_21() -> None:
	m = MockMember()
	game = bucks.BlackjackGame(m, 10)
	game.hand = [10, 9]
	with pytest.MonkeyPatch.context() as mp:
		game.deck = [2, 3, 4]
		mp.setattr("random.randint", lambda x, _: x)
		game.deal_to_player()
	assert game.message.startswith(
		"You were dealt a 2, bringing your total to 21."
		" Your card values are 10, 9, 2. The dealer is showing ",
	)
	assert game.message.endswith(
		f", with one card face down. You hit 21! You win, {m.mention}!",
	)


def test_blackjack_deal_top_card_pops_top_card() -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda x, _: x)
		game = bucks.BlackjackGame(MockMember(), 10)
		# Two cards dealt to player, two to dealer
		# Dealer dealt 2, 3; player dealt 4, 5
		assert len(game.deck) == 48
		assert game.dealerUp == 2
		assert game.dealerSum == 5
		assert sum(game.hand) == 9
		# Next card should be a 6
		assert game.deal_top_card() == 6
		assert len(game.deck) == 47


def test_blackjack_card_name() -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.choice", operator.itemgetter(2))
		assert bucks.BlackjackGame.card_name(10) == "a Queen"
	assert bucks.BlackjackGame.card_name(11) == "an Ace"
	assert bucks.BlackjackGame.card_name(8) == "an 8"
	assert bucks.BlackjackGame.card_name(5) == "a 5"


def test_blackjack_check_bust() -> None:
	game = bucks.BlackjackGame(MockMember(), 10)
	game.hand = [10, 10, 10]
	assert game.check_bust()

	game.hand = [3, 4]
	assert not game.check_bust()


@MarkAsync
async def test_cmd_stay() -> None:
	Bot.BlackjackGames = []
	bb = MockMember(
		MockUser("Beardless,Bot", discriminator="5757", user_id=misc.BbId),
	)
	ctx = MockContext(Bot.BeardlessBot, author=bb, guild=MockGuild())
	assert await Bot.cmd_stay(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description == bucks.CommaWarn.format(f"<@{misc.BbId}>")
	# TODO: other branches


def test_blackjack_stay() -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda x, _: x)
		member = MockMember()
		game = bucks.BlackjackGame(member, 0)
		game.hand = [10, 10, 1]
		game.dealerSum = 25
		assert game.stay() == 1
		assert game.message.endswith(
			f"to your balance, {member.mention}."
			" Unfortunately, you bet nothing, so this was all pointless.",
		)

		game.bet = 10
		game.dealerSum = 20
		assert game.stay() == 1
		assert game.message.endswith(f"to your balance, {member.mention}.")
		game.deal_to_player()
		assert game.stay() == 1
		assert game.message.endswith(f"from your balance, {member.mention}.")

		game.hand = [10, 10]
		assert game.stay() == 0

		game.dealerSum = 14
		assert game.stay() == 1


def test_blackjack_starting_hand() -> None:
	m = MockMember()
	game = bucks.BlackjackGame(m, 10)
	game.hand = []
	game.message = game.starting_hand()
	assert len(game.hand) == 2
	assert game.message.startswith("Your starting hand consists of ")

	game.hand = []
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.BlackjackGame.perfect", lambda _: False)
		assert "You hit 21!" not in game.starting_hand()
	assert len(game.hand) == 2

	game.hand = []
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.BlackjackGame.perfect", lambda _: True)
		assert "You hit 21!" in game.starting_hand()
	assert len(game.hand) == 2

	game.hand = []
	game.deck = [bucks.BlackjackGame.AceVal, bucks.BlackjackGame.AceVal]
	assert game.starting_hand() == (
		"Your starting hand consists of two Aces."
		" One of them will act as a 1. Your total is 12."
		" Type !hit to deal another card to yourself, or !stay"
		f" to stop at your current total, {m.mention}."
	)
	assert len(game.hand) == 2
	assert game.hand[1] == 1


def test_active_game() -> None:
	author = MockMember(MockUser(name="target", user_id=0))
	games = [
		bucks.BlackjackGame(MockMember(MockUser(name="not", user_id=1)), 10),
	] * 9
	assert bucks.active_game(games, author) is None

	games.append(bucks.BlackjackGame(author, 10))
	assert bucks.active_game(games, author)


def test_info() -> None:
	m = MockMember(MockUser("searchterm"))
	guild = MockGuild(members=[MockMember(), m])
	m.roles = [guild.roles[0], guild.roles[0]]
	text = MockMessage("!info searchterm", guild=guild)
	m_info = misc.info("searchterm", text)
	assert len(m_info.fields) == 3
	assert m_info.fields[0].value == misc.truncate_time(m) + " UTC"
	assert m_info.fields[1].value == misc.truncate_time(m) + " UTC"
	assert m_info.fields[2].value == "<@&123456789>"

	m.roles = [guild.roles[0]]
	m_info = misc.info("searchterm", text)
	assert len(m_info.fields) == 2

	assert misc.info("!infoerror", text).title == "Invalid target!"


@MarkAsync
async def test_cmd_av() -> None:
	m = MockMember(MockUser("searchterm"))
	guild = MockGuild(members=[MockMember(), m])
	text = MockMessage("!av searchterm", guild=guild)
	assert isinstance(text.channel, nextcord.TextChannel)
	ctx = MockContext(
		Bot.BeardlessBot, text, text.channel, m, MockGuild(),
	)
	avatar = str(misc.fetch_avatar(m))
	emb = misc.avatar("searchterm", text)
	assert emb.image.url == avatar
	assert await Bot.cmd_av(ctx, target="searchterm") == 1
	latest = await latest_message(ctx)
	assert latest is not None
	assert emb.image.url == latest.embeds[0].image.url

	emb = misc.avatar("error", text)
	assert emb.title == "Invalid target!"

	emb = misc.avatar(m, text)
	assert emb.image.url == avatar

	text.guild = None
	ctx.guild = None
	text.author = m
	emb = misc.avatar("searchterm", text)
	assert emb.image.url == avatar


@MarkAsync
async def test_bb_help_command(caplog: pytest.LogCaptureFixture) -> None:
	help_command = misc.BbHelpCommand()
	assert help_command.command_attrs["aliases"] == ["commands"]
	author = MockMember()
	help_command.context = MockContext(
		Bot.BeardlessBot, author=author, guild=None,
	)
	await help_command.send_bot_help({})

	help_command.context.guild = MockGuild()
	author.guild_permissions = nextcord.Permissions(manage_messages=True)
	await help_command.send_bot_help({})

	author.guild_permissions = nextcord.Permissions(manage_messages=False)
	await help_command.send_bot_help({})

	h = [i async for i in help_command.context.history()]
	assert len(h[2].embeds[0].fields) == 17
	assert len(h[1].embeds[0].fields) == 20
	assert len(h[0].embeds[0].fields) == 15

	help_command.context.message.type = nextcord.MessageType.thread_created
	await help_command.send_bot_help({})

	# For the time being, just pass on all invalid help calls;
	# don't send any messages.
	await help_command.send_error_message("Bar")
	assert caplog.records[0].getMessage() == "No command Bar"
	assert len(caplog.records) == 1


def test_ping_msg() -> None:
	assert brawl.ping_msg("<@200>", 1, 1, 1).endswith(
		"You can ping again in 1 hour, 1 minute, and 1 second.",
	)
	assert brawl.ping_msg("<@200", 2, 2, 2).endswith(
		"You can ping again in 2 hours, 2 minutes, and 2 seconds.",
	)


def test_scam_check() -> None:
	assert misc.scam_check("http://dizcort.com free nitro!")
	assert misc.scam_check("@everyone http://didcord.gg free nitro!")
	assert misc.scam_check("gift nitro http://d1zcordn1tr0.co.uk free!")
	assert misc.scam_check(
		"hey @everyone check it! http://discocl.com/ nitro!",
	)
	assert not misc.scam_check(
		"Hey Discord friends, check out https://top.gg/bot/" + str(misc.BbId),
	)
	assert not misc.scam_check(
		"Here's an actual gift link https://discord.gift/s23d35fls55d13l1fjds",
	)


@MarkAsync
@pytest.mark.flaky(reruns=2, reruns_delay=2)
@pytest.mark.parametrize(
	"searchterm",
	["лексика", "spaced words", "/", "'", "'foo'", "\\\"", " "],
)
async def test_cmd_search_valid(searchterm: str) -> None:
	ctx = MockContext(Bot.BeardlessBot)
	assert await Bot.cmd_search(ctx, searchterm=searchterm) == 1
	latest = await latest_message(ctx)
	assert latest is not None
	url = latest.embeds[0].description
	assert isinstance(url, str)
	async with httpx.AsyncClient(timeout=10) as client:
		r = await client.get(url)
	assert response_ok(r)
	soup = BeautifulSoup(r.content, "html.parser")
	searchpath = soup.find_all("a")[-2].attrs["href"][10:]
	assert searchpath.startswith(quote_plus(searchterm).replace("%2F", "/"))
	await asyncio.sleep(0.4)


@MarkAsync
@pytest.mark.flaky(reruns=2, reruns_delay=2)
async def test_cmd_search_empty_argument_redirects_to_home() -> None:
	ctx = MockContext(Bot.BeardlessBot)
	assert await Bot.cmd_search(ctx, searchterm="") == 1
	latest = await latest_message(ctx)
	assert latest is not None
	url = latest.embeds[0].description
	assert isinstance(url, str)
	async with httpx.AsyncClient(timeout=10) as client:
		r = await client.get(url, follow_redirects=True)
	assert response_ok(r)
	assert next(
		BeautifulSoup(r.content, "html.parser").stripped_strings,
	) == "Google"


@MarkAsync
async def test_moose_failed_connection_raises_animal_exception(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://github.com/LevBernstein/moosePictures/",
		status_code=522,
	)
	with pytest.raises(
		misc.AnimalException, match="Failed to call Moose Animal API",
	):
		await misc.get_moose()


@MarkAsync
@pytest.mark.flaky(reruns=2, reruns_delay=2)
@pytest.mark.parametrize("animal_name", misc.AnimalList)
async def test_get_animal_with_good_url(animal_name: str) -> None:
	url = await misc.get_animal(animal_name)
	async with httpx.AsyncClient(timeout=10) as client:
		response = await client.get(url)
	assert valid_image_url(response)


@MarkAsync
async def test_dog_with_good_url() -> None:
	url = await misc.get_dog()
	async with httpx.AsyncClient(timeout=10) as client:
		response = await client.get(url)
	assert valid_image_url(response)

	url = await misc.get_moose()
	async with httpx.AsyncClient(timeout=10) as client:
		response = await client.get(url)
	assert valid_image_url(response)


@MarkAsync
async def test_dog_breed() -> None:
	msg = await misc.get_dog("breeds")
	breeds = msg[12:-1].split(", ")
	assert len(breeds) == 108
	url = await misc.get_dog(breeds[0])
	assert "affenpinscher" in url
	async with httpx.AsyncClient(timeout=10) as client:
		response = await client.get(url)
	assert valid_image_url(response)

	msg = await misc.get_dog("invalidbreed")
	assert msg.startswith("Breed not")

	msg = await misc.get_dog("invalidbreed1234")
	assert msg.startswith("Breed not")

	url = await misc.get_dog("moose")
	async with httpx.AsyncClient(timeout=10) as client:
		response = await client.get(url)
	assert valid_image_url(response)


@MarkAsync
async def test_invalid_animal_raises_value_error() -> None:
	with pytest.raises(ValueError, match="Invalid Animal: invalidAnimal"):
		await misc.get_animal("invalidAnimal")


@MarkAsync
async def test_dog_api_down_random_dog_raises_animal_exception(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://dog.ceo/api/breeds/image/random",
		status_code=522,
	)

	with pytest.raises(
		misc.AnimalException, match="Failed to call Dog Animal API",
	):
		await misc.get_dog()


@MarkAsync
async def test_dog_api_down_get_breeds_raises_animal_exception(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://dog.ceo/api/breeds/list/all",
		status_code=522,
	)

	with pytest.raises(
		misc.AnimalException, match="Failed to call Dog Animal API",
	):
		await misc.get_dog("breeds")


@MarkAsync
async def test_animal_api_down_raises_animal_exception(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://api.bunnies.io/v2/loop/random/?media=gif",
		status_code=522,
	)

	with pytest.raises(
		misc.AnimalException, match="Failed to call Rabbit Animal API",
	):
		await misc.get_animal("rabbit")


def test_get_frog_list_standard_layout(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://github.com/a9-i/frog/tree/main/ImgSetOpt",
		content=(
			b"<!DOCTYPE html><html><script>{\"payload\":{\"tree\":{\"items\":"
			b"[{\"name\":\"0\"}]}}}</script></html>"
		),
	)

	frogs = misc.get_frog_list()
	assert len(frogs) == 1
	assert frogs[0] == "0"


def test_get_frog_list_alt_layout(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://github.com/a9-i/frog/tree/main/ImgSetOpt",
		content=(
			b"<!DOCTYPE html><html><script>{\"payload\":{\"tree\":{\"items\":"
			b"[{\"name\":\"0\\\"}]}}}</script><script>{}</script></html>"
		),
	)

	frogs = misc.get_frog_list()
	assert len(frogs) == 1
	assert frogs[0] == "0\\"


@MarkAsync
async def test_handle_messages() -> None:
	u = MockMember()
	u._user.bot = True
	m = MockMessage(author=u)
	assert await Bot.handle_messages(m) == 0

	u._user.bot = False
	m.guild = None
	assert await Bot.handle_messages(m) == 0

	u = MockMember()
	m = MockMessage(guild=MockGuild(), author=u)
	u._user.bot = False
	assert await Bot.handle_messages(m) == 1

	u = MockMember(MockUser("bar", user_id=999999999))
	infractions = MockChannel(name="infractions")
	ch = MockChannel(name="foo")
	m = MockMessage(
		content="http://dizcort.com free nitro!",
		channel=ch,
		guild=MockGuild(members=[u], channels=[
			MockChannel(name="spam"),
			MockChannel(name=misc.LogChannelName),
			infractions,
			MockChannel(name="foobar"),
		]),
		author=u,
	)
	u._user.bot = False
	assert len(u.roles) == 1
	assert ch._state._messages is not None
	assert len(list(ch.messages)) == 1
	assert len(list(ch._state._messages)) == 1
	assert ch.messages[0] == m
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.content == "http://dizcort.com free nitro!"
	assert (await latest_message(infractions)) is None
	assert len(list(infractions.messages)) == 0
	assert len(list(ch.messages)) == 1
	assert len(list(ch._state._messages)) == 1
	assert m in ch._state._messages

	assert await Bot.handle_messages(m) == -1

	assert len(u.roles) == 2
	assert len(list(ch.messages)) == 1
	assert len(list(ch._state._messages)) == 1
	latest = await latest_message(ch)
	assert latest is not None
	assert latest.content == (
		"**Deleted possible nitro scam link. Alerting mods.**"
	)
	assert ch._state._messages is not None
	assert m not in ch._state._messages
	assert m not in ch.messages
	assert len(list(infractions.messages)) == 1
	msg = await latest_message(infractions)
	assert msg is not None
	assert isinstance(msg.content, str)
	assert msg.content.startswith(
		"Deleted possible scam nitro link sent by <@999999999>",
	)
	dm = await latest_message(m.author)
	assert dm is not None
	assert dm.content.startswith("This is an automated message.")
	assert dm == await latest_message(await m.author._get_channel())
	assert dm == await latest_message(u)


@MarkAsync
async def test_cmd_guide() -> None:
	ctx = MockContext(Bot.BeardlessBot, guild=MockGuild())
	ctx.message.type = nextcord.MessageType.default
	assert await Bot.cmd_guide(ctx) == 0

	assert ctx.guild is not None
	ctx.guild.id = Bot.EggGuildId
	assert await Bot.cmd_guide(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].title == "The Eggsoup Improvement Guide"


@MarkAsync
async def test_cmd_reddit() -> None:
	ctx = MockContext(Bot.BeardlessBot, guild=MockGuild())
	ctx.message.type = nextcord.MessageType.default
	assert await Bot.cmd_reddit(ctx) == 0

	assert ctx.guild is not None
	ctx.guild.id = Bot.EggGuildId
	assert await Bot.cmd_reddit(ctx) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].title == "The Official Eggsoup Subreddit"


@MarkAsync
async def test_cmd_buy() -> None:
	ctx = MockContext(Bot.BeardlessBot, author=MockMember(), guild=MockGuild())
	assert await Bot.cmd_buy(ctx, "invalid") == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].title == "Beardless Bot Special Colors"
	assert m.embeds[0].description == (
		"Invalid color. Choose blue, red, orange,"
		f" or pink, {ctx.author.mention}."
	)

	assert await Bot.cmd_buy(ctx, "blue") == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].title == "Beardless Bot Special Colors"
	assert m.embeds[0].description == (
		f"That color role does not exist in this server, {ctx.author.mention}."
	)
	# TODO: test remaining branches
	# https://github.com/LevBernstein/BeardlessBot/issues/47


@MarkAsync
async def test_cmd_mute() -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	ctx = MockContext(
		Bot.BeardlessBot,
		message=MockMessage(content="!mute foo"),
		author=MockMember(admin_powers=True),
		guild=MockGuild(),
	)

	# if the MemberConverter fails
	assert await Bot.cmd_mute(ctx, target="foo") == 0

	# if trying to mute the bot
	assert await Bot.cmd_mute(ctx, target=f"<@{misc.BbId}>") == 0

	# if no target
	assert await Bot.cmd_mute(ctx, target=None) == 0

	# if no perms
	ctx.author = MockMember(admin_powers=False)
	assert await Bot.cmd_mute(ctx, target=None) == 0

	# if not in guild
	ctx.guild = None
	assert await Bot.cmd_mute(ctx, target="foo") == -1
	# TODO: test remaining branches
	# https://github.com/LevBernstein/BeardlessBot/issues/47


@MarkAsync
async def test_cmd_unmute() -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	ctx = MockContext(
		Bot.BeardlessBot,
		message=MockMessage(content="!unmute foo"),
		author=MockMember(admin_powers=False),
		guild=MockGuild(),
	)
	assert await Bot.cmd_unmute(ctx, "foo") == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].title == "Beardless Bot Unmute"
	assert m.embeds[0].description == misc.Naughty.format(ctx.author.mention)

	ctx.author = MockMember(admin_powers=True)
	assert await Bot.cmd_unmute(ctx, "foo") == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description == (
		"Error! Muted role does not exist! Can't unmute!"
	)

	assert ctx.guild is not None
	assert await misc.create_muted_role(ctx.guild) is not None
	assert await Bot.cmd_unmute(ctx, None) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description == f"Invalid target, {ctx.author.mention}."

	assert await Bot.cmd_unmute(ctx, "foo") == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].description == (
		"Invalid target! Target must be a mention or user ID."
	)
	# TODO: test remaining branches
	# https://github.com/LevBernstein/BeardlessBot/issues/47


@MarkAsync
async def test_process_mute_target_converts_target() -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	ctx = MockContext(
		Bot.BeardlessBot,
		message=MockMessage(content="!mute foo"),
		author=MockMember(MockUser("foo"), admin_powers=True),
		guild=MockGuild(),
	)
	assert await misc.process_mute_target(
		ctx, "foo", Bot.BeardlessBot,
	) == ctx.author


def test_get_last_numeric_char() -> None:
	assert misc.get_last_numeric_char("") == 0

	assert misc.get_last_numeric_char("a") == 0

	assert misc.get_last_numeric_char("5") == 1

	assert misc.get_last_numeric_char("134") == 3

	assert misc.get_last_numeric_char("5s") == 1

	assert misc.get_last_numeric_char("55d") == 2

	assert misc.get_last_numeric_char("13h foobar") == 2


def test_process_mute_duration() -> None:
	assert misc.process_mute_duration("43H", "") == ("43 hours", "", 154800.0)

	assert misc.process_mute_duration("15minutes", "") == (
		"15 minutes", "", 900.0,
	)

	assert misc.process_mute_duration("24second", "") == (
		"24 seconds", "", 24.0,
	)

	assert misc.process_mute_duration("foobar", "") == (None, "foobar", None)

	assert misc.process_mute_duration("being", "annoying") == (
		None, "being annoying", None,
	)

	assert misc.process_mute_duration("3d", "being annoying") == (
		"3 days", "being annoying", 259200.0,
	)

	assert misc.process_mute_duration("4z", "invalid time") == (
		None, "4z invalid time", None,
	)

	assert misc.process_mute_duration(None, "") == (None, "", None)


def test_get_target() -> None:
	author = MockMember(MockUser("author"))
	ctx = MockContext(Bot.BeardlessBot, author=author, guild=MockGuild())
	target = MockMember(MockUser("foobar"))
	assert misc.get_target(ctx, "") == author

	assert misc.get_target(ctx, "foobar") == "foobar"

	ctx.message.mentions = [target, MockMember()]
	assert misc.get_target(ctx, "") == target


@MarkAsync
async def test_thread_creation_does_not_invoke_commands() -> None:
	ctx = MockContext(Bot.BeardlessBot, guild=MockGuild())
	ctx.message.type = nextcord.MessageType.thread_created
	for command in Bot.BeardlessBot.commands:
		if command.name != "help":
			assert await command(ctx) == -1


def test_launch_no_dotenv(caplog: pytest.LogCaptureFixture) -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("dotenv.dotenv_values", lambda _: {})
		Bot.launch()
	assert caplog.records[0].msg == (
		"No Brawlhalla API key. Brawlhalla-specific"
		" commands will not be active."
	)
	assert caplog.records[1].msg == (
		"Fatal error! DISCORDTOKEN environment variable has not"
		" been defined. See: README.MD's installation section."
	)


def test_launch_invalid_discord_token_raises_discord_exception(
	caplog: pytest.LogCaptureFixture,
) -> None:

	def mock_raise_discord_exception(bot: commands.Bot, token: str) -> None:
		msg = f"Failed launching {bot.command_prefix} bot with token {token}."
		raise nextcord.DiscordException(msg)

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"dotenv.dotenv_values",
			lambda _: {"BRAWLKEY": "foo", "DISCORDTOKEN": "bar"},
		)
		mp.setattr(
			"nextcord.ext.commands.Bot.run",
			mock_raise_discord_exception,
		)
		Bot.launch()
	assert caplog.records[0].msg == "Encountered DiscordException!"
	assert caplog.records[0].exc_info is not None
	assert caplog.records[0].exc_info[1] is not None
	assert caplog.records[0].exc_info[1].args[0] == (
		"Failed launching ! bot with token bar."
	)


@MarkAsync
async def test_cmd_pins() -> None:
	ctx = MockContext(Bot.BeardlessBot, guild=None)
	assert await Bot.cmd_pins(ctx) == -1

	ctx.guild = MockGuild()
	assert (await Bot.cmd_pins(ctx)) == 0
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].title == (
		f"Try using !spar in the {misc.SparChannelName} channel."
	)

	assert hasattr(ctx.channel, "name")
	ctx.channel.name = misc.SparChannelName
	assert (await Bot.cmd_pins(ctx)) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].title == "How to use this channel."


@MarkAsync
async def test_cmd_brawl() -> None:
	ctx = MockContext(Bot.BeardlessBot, guild=MockGuild())
	Bot.BrawlKey = "Foo"
	assert (await Bot.cmd_brawl(ctx)) == 1
	m = await latest_message(ctx)
	assert m is not None
	assert m.embeds[0].title == "Beardless Bot Brawlhalla Commands"
	assert len(m.embeds[0].fields) == 6

	Bot.BrawlKey = None
	assert (await Bot.cmd_brawl(ctx)) == 0


def test_fetch_brawl_id() -> None:
	assert brawl.fetch_brawl_id(Bot.OwnerId) == OwnerBrawlId
	assert brawl.fetch_brawl_id(misc.BbId) is None


def test_get_top_dps() -> None:
	payload: dict[str, str | int] = {
		"matchtime": 3,
		"legend_name_key": "sidra",
		"damagedealt": "10",
		"kos": 6,
	}
	top_dps = brawl.get_top_dps(payload)
	assert len(top_dps) == 2
	assert top_dps[0] == "Sidra"
	assert top_dps[1] == 3.3


def test_get_top_ttk() -> None:
	payload: dict[str, str | int] = {
		"matchtime": 3,
		"legend_name_key": "sidra",
		"damagedealt": "10",
		"kos": 6,
	}
	top_ttk = brawl.get_top_ttk(payload)
	assert len(top_ttk) == 2
	assert top_ttk[0] == "Sidra"
	assert top_ttk[1] == 0.5


def test_get_top_legend() -> None:
	legends: list[dict[str, str | int]] = [
		{"legend_name_key": "sidra", "rating": 1397},
		{"legend_name_key": "jhala", "rating": 1399},
		{"legend_name_key": "xull", "rating": 1398},
	]
	top_legend = brawl.get_top_legend(legends)
	assert top_legend is not None
	assert len(top_legend) == 2
	assert top_legend[0] == "jhala"
	assert top_legend[1] == 1399


def test_get_twos_rank_no_teams_returns_unmodified_embed() -> None:
	emb = misc.bb_embed("test embed", "test description")
	assert len(emb.fields) == 0
	new_emb = brawl.get_twos_rank(emb, {"2v2": []})
	assert len(emb.fields) == 0
	assert emb.title == new_emb.title
	assert emb.description == new_emb.description


@MarkAsync
async def test_claim_profile() -> None:
	assert brawl.fetch_brawl_id(Bot.OwnerId) == OwnerBrawlId
	async with aiofiles.open("resources/claimedProfs.json") as f:
		profs_len = len(json.loads(await f.read()))
	ctx = MockContext(
		Bot.BeardlessBot, author=MockMember(MockUser(user_id=Bot.OwnerId)),
	)
	Bot.BrawlKey = "Foo"
	try:
		assert (await Bot.cmd_brawlclaim(ctx, "1")) == 1
		async with aiofiles.open("resources/claimedProfs.json") as f:
			assert profs_len == len(json.loads(await f.read()))
		assert brawl.fetch_brawl_id(Bot.OwnerId) == 1
		m = await latest_message(ctx)
		assert m is not None
		assert m.embeds[0].description == "Profile claimed."
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)
		assert brawl.fetch_brawl_id(Bot.OwnerId) == OwnerBrawlId
		Bot.BrawlKey = None


@MarkAsync
async def test_brawl_api_call_raises_httpx_exception_with_bad_status_code(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/search?steamid=1&api_key=foo",
		status_code=400,
	)
	with pytest.raises(
		httpx.RequestError, match="Request failed with 400",
	):
		await brawl.brawl_api_call("search?steamid=", "1", "foo", "&")


@MarkAsync
async def test_get_rank_1s_top_rating(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/ranked?api_key=foo",
		json={
			"name": "Foo",
			"region": "us-east-1",
			"tier": "Gold 2",
			"rating": 1540,
			"peak_rating": 1577,
			"wins": 2,
			"games": 3,
			"legends": [
				{
					"legend_id": 0,
					"legend_name_key": "bodvar",
					"rating": 1400,
					"tier": "Gold 3",
				},
			],
			"2v2": [],
		},
	)

	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		emb = await brawl.get_rank(
			MockMember(MockUser(user_id=Bot.OwnerId)), "foo",
		)
		assert emb.fields[0].name == "Ranked 1s"
		assert emb.fields[0].value == (
			"**Gold 2** (1540/1577 Peak)\n2 W / 1 L / 66.7% winrate"
			"\nTop Legend: Bodvar, 1400 Elo"
		)
		assert hasattr(emb.color, "value")
		assert emb.color is not None
		assert emb.color.value == brawl.RankColors["Gold"]
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_rank_1s_top_rating_no_top_legend(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/ranked?api_key=foo",
		json={
			"name": "Foo",
			"region": "us-east-1",
			"tier": "Gold 2",
			"rating": 1540,
			"peak_rating": 1577,
			"wins": 2,
			"games": 3,
			"legends": [],
			"2v2": [],
		},
	)

	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		emb = await brawl.get_rank(
			MockMember(MockUser(user_id=Bot.OwnerId)), "foo",
		)
		assert emb.fields[0].name == "Ranked 1s"
		assert emb.fields[0].value == (
			"**Gold 2** (1540/1577 Peak)\n2 W / 1 L / 66.7% winrate"
		)
		assert hasattr(emb.color, "value")
		assert emb.color is not None
		assert emb.color.value == brawl.RankColors["Gold"]
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_rank_2s_top_rating(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/ranked?api_key=foo",
		json={
			"name": "Foo",
			"region": "us-east-1",
			"rating": 0,
			"2v2": [
				{
					"teamname": "Foo+Spam",
					"tier": "Gold 2",
					"rating": 1467,
					"peak_rating": 1467,
					"wins": 1,
					"games": 1,
				},
				{
					"teamname": "Foo+Bar",
					"tier": "Platinum 3",
					"rating": 1812,
					"peak_rating": 1824,
					"wins": 1,
					"games": 2,
				},
				{
					"teamname": "Foo+Splat",
					"tier": "Gold 2",
					"rating": 1465,
					"peak_rating": 1465,
					"wins": 1,
					"games": 1,
				},
			],
		},
	)

	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		emb = await brawl.get_rank(
			MockMember(MockUser(user_id=Bot.OwnerId)), "foo",
		)
		assert emb.fields[0].name == "Ranked 2s"
		assert emb.fields[0].value == (
			"**Foo+Bar\nPlatinum 3** (1812 / 1824 Peak)"
			"\n1 W / 1 L / 50.0% winrate"
		)
		assert emb.color is not None
		assert hasattr(emb.color, "value")
		assert emb.color.value == brawl.RankColors["Platinum"]
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_rank_unplayed(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/ranked?api_key=foo",
		json={"name": "Foo", "region": "us-east-1", "games": 0, "2v2": []},
	)

	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		rank = await brawl.get_rank(
			MockMember(MockUser(user_id=Bot.OwnerId)), "foo",
		)
		assert rank.footer.text == "Brawl ID 1"
		assert rank.description == (
			"You haven't played ranked yet this season."
		)
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_rank_unclaimed() -> None:
	member = MockMember(MockUser(user_id=0))
	rank = await brawl.get_rank(member, "foo")
	assert rank.description == brawl.UnclaimedMsg.format("<@0>")


@MarkAsync
@pytest.mark.httpx_mock
async def test_get_brawl_id_returns_none_when_never_played(
	httpx_mock: HTTPXMock,
) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/search?steamid=37&api_key=foo",
		json=[],
	)

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("steam.steamid.from_url", lambda _: "37")
		assert await brawl.get_brawl_id("foo", "foo.bar") is None


@MarkAsync
async def test_get_brawl_id_returns_none_when_id_is_invalid() -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("steam.steamid.from_url", lambda _: None)
		assert await brawl.get_brawl_id("foo", "foo.bar") is None


@MarkAsync
async def test_get_brawl_id_valid(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/search?steamid=1&api_key=foo",
		json={"brawlhalla_id": 2},
	)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("steam.steamid.from_url", lambda _: "1")
		assert await brawl.get_brawl_id("foo", "foo.bar") == 2


@MarkAsync
async def test_get_clan_unclaimed() -> None:
	member = MockMember(MockUser(user_id=0))
	clan = await brawl.get_clan(member, "foo")
	assert clan.description == brawl.UnclaimedMsg.format("<@0>")


@MarkAsync
async def test_get_clan(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/stats?api_key=foo",
		json={"clan": {"clan_id": 2}},
	)
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/clan/2/?api_key=foo",
		json={
			"clan_id": 2,
			"clan_name": "FooBar",
			"clan_create_date": 18000,
			"clan_lifetime_xp": 1257,
			"clan": [{
				"name": "Spam",
				"rank": "Leader",
				"xp": 1000,
				"join_date": 18000,
			}],
		},
	)
	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		clan = await brawl.get_clan(
			MockMember(MockUser(user_id=Bot.OwnerId)), "foo",
		)
		assert clan.title == "FooBar"
		assert clan.description == (
			"**Clan Created:** 1970-01-01 00:00"
			"\n**Experience:** 1257\n**Members:** 1"
		)
		assert len(clan.fields) == 1
		assert clan.fields[0].name == "Spam"
		assert clan.fields[0].value == (
			"Leader (1000 xp)\nJoined 1970-01-01 00:00"
		)
		assert clan.footer.text == "Clan ID 2"
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_stats(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/stats?api_key=foo",
		json={
			"clan": {"clan_id": 2, "clan_name": "test clan"},
			"brawlhalla_id": 1,
			"name": "test player",
			"games": 21,
			"wins": 20,
			"legends": [
				{
					"legend_id": 26,
					"legend_name_key": "jhala",
					"damagedealt": "24000",
					"damagetaken": "1200",
					"kos": 60,
					"falls": 40,
					"matchtime": 1200,
					"games": 20,
					"wins": 20,
					"xp": 100,
				},
				{
					"legend_id": 5,
					"legend_name_key": "orion",
					"damagedealt": "60",
					"damagetaken": "120",
					"kos": 2,
					"falls": 3,
					"matchtime": 36,
					"games": 1,
					"wins": 0,
					"xp": 5,
				},
			],
		},
	)
	member = MockMember(MockUser(user_id=0))
	stats = await brawl.get_stats(member, "foo")
	assert stats.description == brawl.UnclaimedMsg.format("<@0>")

	member._user.id = Bot.OwnerId
	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		emb = await brawl.get_stats(member, "foo")
		assert emb.footer.text == "Brawl ID 1"
		assert len(emb.fields) == 4
		assert emb.fields[0].value == "test player"
		assert emb.fields[1].value == (
			"20 Wins / 1 Losses\n21 Games\n95.2% Winrate"
		)
		assert emb.fields[2].value == (
			"**Most Played:** Jhala\n**Highest Winrate:** Jhala, 100.0%"
			"\n**Highest Avg DPS:** Jhala, 20.0\n**Shortest Avg TTK:**"
			" Orion, 18.0s"
		)
		assert emb.fields[3].value == "test clan\nClan ID 2"
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_stats_no_clan(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/stats?api_key=foo",
		json={
			"brawlhalla_id": 1,
			"name": "test player",
			"games": 20,
			"wins": 20,
			"legends": [
				{
					"legend_id": 26,
					"legend_name_key": "jhala",
					"damagedealt": "24000",
					"damagetaken": "1200",
					"kos": 60,
					"falls": 40,
					"matchtime": 1200,
					"games": 20,
					"wins": 20,
					"xp": 100,
				},
			],
		},
	)
	member = MockMember(MockUser(user_id=Bot.OwnerId))
	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		emb = await brawl.get_stats(member, "foo")
		assert len(emb.fields) == 3
		assert emb.fields[0].value == "test player"
		assert emb.fields[1].value == (
			"20 Wins / 0 Losses\n20 Games\n100.0% Winrate"
		)
		assert emb.fields[2].value == (
			"**Most Played:** Jhala\n**Highest Winrate:** Jhala, 100.0%"
			"\n**Highest Avg DPS:** Jhala, 20.0\n**Shortest Avg TTK:**"
			" Jhala, 20.0s"
		)
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_stats_no_advanced_stats(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/stats?api_key=foo",
		json={
			"clan": {"clan_id": 2, "clan_name": "test clan"},
			"brawlhalla_id": 1,
			"name": "test player",
			"games": 0,
			"wins": 0,
			"legends": [{"legend_name_key": "jhala"}],
		},
	)
	member = MockMember(MockUser(user_id=Bot.OwnerId))
	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		emb = await brawl.get_stats(member, "foo")
		assert emb.footer.text == "Brawl ID 1"
		assert len(emb.fields) == 3
		assert emb.fields[0].value == "test player"
		assert emb.fields[1].value == (
			"0 Wins / 0 Losses\n0 Games\n0.0% Winrate"
		)
		assert emb.fields[2].value == "test clan\nClan ID 2"
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_stats_no_legends(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/stats?api_key=foo",
		json={
			"clan": {"clan_id": 2, "clan_name": "test clan"},
			"brawlhalla_id": 1,
			"name": "test player",
			"games": 20,
			"wins": 20,
		},
	)
	member = MockMember(MockUser(user_id=Bot.OwnerId))
	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		emb = await brawl.get_stats(member, "foo")
		assert len(emb.fields) == 3
		assert emb.fields[0].value == "test player"
		assert emb.fields[1].value == (
			"20 Wins / 0 Losses\n20 Games\n100.0% Winrate"
		)
		assert emb.fields[2].value == "test clan\nClan ID 2"
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_stats_no_clan_or_legends(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/stats?api_key=foo",
		json={
			"brawlhalla_id": 1, "name": "test player", "games": 20, "wins": 20,
		},
	)
	member = MockMember(MockUser(user_id=Bot.OwnerId))
	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		emb = await brawl.get_stats(member, "foo")
		assert len(emb.fields) == 2
		assert emb.fields[0].value == "test player"
		assert emb.fields[1].value == (
			"20 Wins / 0 Losses\n20 Games\n100.0% Winrate"
		)
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_stats_no_stats(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/stats?api_key=foo", json={},
	)
	member = MockMember(MockUser(user_id=Bot.OwnerId))
	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		emb = await brawl.get_stats(member, "foo")
		assert emb.description is not None
		assert emb.description.startswith("This profile doesn't have stats")
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


@MarkAsync
async def test_get_clan_not_in_a_clan(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/stats?api_key=foo", json={},
	)
	try:
		brawl.claim_profile(Bot.OwnerId, 1)
		clan = await brawl.get_clan(
			MockMember(MockUser(user_id=Bot.OwnerId)), "foo",
		)
		assert clan.description == "You are not in a clan!"
	finally:
		brawl.claim_profile(Bot.OwnerId, OwnerBrawlId)


def test_get_brawl_data(httpx_mock: HTTPXMock) -> None:
	brawl_data_content = (
		b'<script /><script /><script /><script>{"body": "{\\"data\\":'
		b' {\\"weapons\\": {\\"nodes\\": [{\\"name\\":'
		b' \\"cannon\\"}]}}}"}</script>'
	)
	httpx_mock.add_response(
		url="https://www.brawlhalla.com/legends", content=brawl_data_content,
	)
	data = brawl.get_brawl_data()
	assert len(data["weapons"]["nodes"]) == 1
	assert data["weapons"]["nodes"][0]["name"] == "cannon"


@MarkAsync
async def test_random_brawl_weapon() -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"brawl.Data", {
				"weapons": {
					"nodes": [{
						"name": "gauntlets",
						"weaponFields": {"icon": {"sourceUrl": "foo.bar"}},
					}],
				},
			},
		)
		mp.setattr("random.choice", operator.itemgetter(0))
		weapon = await brawl.random_brawl("weapon")
	assert weapon.title == "Random Weapon"
	assert weapon.description == "Your weapon is gauntlets."
	assert weapon.thumbnail.url == "foo.bar"


@MarkAsync
async def test_random_brawl_legend_no_brawl_key() -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.choice", operator.itemgetter(0))
		legend = await brawl.random_brawl("legend")
	assert legend.title == "Random Legend"
	assert legend.description == "Your legend is Bodvar."


@MarkAsync
async def test_random_brawl_invalid() -> None:
	legend = await brawl.random_brawl("invalidrandom")
	assert legend.title == "Brawlhalla Randomizer"


# Tests for commands that require a Brawlhalla API key:

if BrawlKey:  # pragma: no branch
	@MarkAsync
	async def test_random_brawl_with_brawl_key() -> None:
		assert BrawlKey is not None
		with pytest.MonkeyPatch.context() as mp:
			mp.setattr("random.choice", operator.itemgetter(0))
			legend = await brawl.random_brawl("legend", BrawlKey)
		assert len(legend.fields) == 2
		assert legend.title == "Bödvar, The Unconquered Viking, The Great Bear"
		legend_info = await brawl.legend_info(BrawlKey, "bodvar")
		assert legend_info is not None
		assert legend.title == legend_info.title

	@MarkAsync
	async def test_pull_legends() -> None:
		assert BrawlKey is not None
		await asyncio.sleep(5)
		old_legends = brawl.fetch_legends()
		await brawl.pull_legends(BrawlKey)
		assert brawl.fetch_legends() == old_legends

	@MarkAsync
	async def test_legend_info() -> None:
		assert BrawlKey is not None
		await asyncio.sleep(5)
		legend = await brawl.legend_info(BrawlKey, "hugin")
		assert legend is not None
		assert legend.title == "Munin, The Raven"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/"
			"2021/12/a_Roster_Pose_BirdBardM.png"
		)

		legend = await brawl.legend_info(BrawlKey, "teros")
		assert legend is not None
		assert legend.title == "Teros, The Minotaur"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/2021/07/teros.png"
		)

		legend = await brawl.legend_info(BrawlKey, "redraptor")
		assert legend is not None
		assert legend.title == "Red Raptor, The Last Sentai"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/"
			"2023/06/a_Roster_Pose_SentaiM.png"
		)

		assert await brawl.legend_info(BrawlKey, "invalidname") is None
