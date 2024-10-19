# ruff: noqa: D103, PLR2004, S101, S603, SLF001
# D103: Missing docstring in public function
# PLR2004: Magic value used in comparison
# S101: Assert used
# S603: Subprocess call
# SLF001: Private member accessed
"""Beardless Bot unit tests."""

import asyncio
import json
import logging
import subprocess
import sys
import weakref
from collections import deque
from copy import copy
from datetime import datetime
from os import environ
from pathlib import Path
from time import sleep
from typing import Any, Final, overload, override

import dotenv
import httpx
import nextcord
import pytest
import requests
import responses
from aiohttp import ClientWebSocketResponse
from bs4 import BeautifulSoup
from codespell_lib import main as codespell
from flake8.api import legacy as flake8  # type: ignore[import-untyped]
from mypy.api import run as mypy
from nextcord.abc import Snowflake as SnowflakeABC
from nextcord.ext import commands
from nextcord.types.emoji import Emoji as EmojiPayload
from nextcord.types.emoji import PartialEmoji as PartialEmojiPayload
from nextcord.types.message import Message as MessagePayload
from nextcord.types.message import Reaction as ReactionPayload
from nextcord.types.snowflake import Snowflake
from nextcord.types.user import User as UserPayload
from nextcord.utils import SnowflakeList
from pytest_httpx import HTTPXMock

import Bot
import brawl
import bucks
import logs
import misc

ImageTypes: set[str] = {
	"image/" + i for i in ("png", "jpeg", "jpg", "gif", "webp")
}

FilesToCheck: tuple[str, ...] = tuple(f.name for f in Path().glob("*.py"))

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

SnowflakeTime = datetime | SnowflakeABC

StyleGuide = flake8.get_style_guide(ignore=["W191", "W503"])

BrawlKey: str | None = (
	environ.get("BRAWLKEY") or dotenv.dotenv_values(".env").get("BRAWLKEY")
)


def validImageUrl(resp: requests.models.Response | httpx.Response) -> bool:
	"""Make sure an image url points to a valid image."""
	return (
		misc.Ok <= resp.status_code < 400
		and resp.headers["content-type"] in ImageTypes
	)


# TODO: add _state attribute to all mock objects, inherit from State
# Switch to a single MockState class for all Messageable objects
# Implements nextcord.state.ConnectionState

class MockHTTPClient(nextcord.http.HTTPClient):
	"""Drop-in replacement for HTTPClient to enable offline testing."""

	@override
	def __init__(
		self,
		loop: asyncio.AbstractEventLoop,
		user: nextcord.ClientUser | None = None
	) -> None:
		self.loop = loop
		self.user = user
		self.user_agent = str(user)
		self.token = None
		self.proxy = None
		self.proxy_auth = None
		self._locks = weakref.WeakValueDictionary()
		self._global_over = asyncio.Event()
		self._global_over.set()

	@override
	async def create_role(  # type: ignore[override]
		self,
		guild_id: Snowflake,
		reason: str | None = None,
		**fields: Any
	) -> dict[str, Any]:
		data = dict(fields)
		data["id"] = guild_id
		if reason:
			logging.info("Role creation reason: %s", reason)
		return data

	@override
	async def send_message(  # type: ignore[override]
		self,
		channel_id: Snowflake,
		content: str | None = None,
		*,
		tts: bool = False,
		embed: nextcord.Embed | None = None,
		embeds: list[nextcord.Embed] | None = None,
		nonce: int | str | None = None,
		allowed_mentions: nextcord.AllowedMentions | None = None,
		message_reference: nextcord.MessageReference | None = None,
		stickers: list[int] | None = None,
		components: list[nextcord.Component] | None = None,
		flags: int | None = None
	) -> dict[str, Any]:
		return {
			"attachments": [],
			"edited_timestamp": None,
			"type": nextcord.Message,
			"pinned": False,
			"mention_everyone": content and "@everyone" in content,
			"tts": tts,
			"author": MockUser(),
			"content": content or "",
			"nonce": nonce,
			"allowed_mentions": allowed_mentions,
			"message_reference": message_reference,
			"components": components,
			"stickers": stickers,
			"flags": flags,
			"channel_id": channel_id,
			"embeds": [embed] if embed else embeds or []
		}

	@override
	async def leave_guild(self, guild_id: Snowflake) -> None:
		if (
			self.user
			and hasattr(self.user, "guild")
			and self.user.guild
			and self.user.guild.id == guild_id
		):
			self.user.guild = None


class MockHistoryIterator(nextcord.iterators.HistoryIterator):
	"""Mock HistoryIterator class for offline testing."""

	@override
	def __init__(
		self,
		messageable: nextcord.abc.Messageable,
		limit: int | None = None,
		before: SnowflakeTime | None = None,
		after: SnowflakeTime | None = None,
		around: SnowflakeTime | None = None,
		oldest_first: bool | None = False
	) -> None:
		self.messageable = messageable
		self.limit = min(limit or 100, 100)
		self.messages: asyncio.Queue[nextcord.Message] = asyncio.Queue()
		self.reverse = (
			(after is not None) if oldest_first is None else oldest_first
		)

	@override
	async def fill_messages(self) -> None:
		if not hasattr(self, "channel"):
			self.channel = await self.messageable._get_channel()
		assert hasattr(self.channel, "messages")
		assert isinstance(self.channel.messages, list)
		assert self.limit is not None
		data = (
			list(reversed(self.channel.messages))
			if self.reverse
			else self.channel.messages
		)
		for _ in range(min(len(data), self.limit)):
			await self.messages.put(data.pop())


class MockMember(nextcord.Member):
	"""Mock Member class for offline testing."""

	@override
	def __init__(
		self,
		user: nextcord.User | None = None,
		nick: str | None = None,
		roles: list[nextcord.Role] | None = None,
		guild: nextcord.Guild | None = None,
		customAvatar: bool = True,
		perms: nextcord.Permissions | None = None,
		adminPowers: bool = False
	) -> None:
		self._user = user or MockUser()
		self._user.bot = False
		self.nick = nick
		self.guild = guild or MockGuild()
		self.activities = ()
		self._user._banner = None
		self.roleList = [MockRole("everyone", 0)] + (roles or [])
		self._roles = SnowflakeList(map(int, []))
		self._timeout = None
		self._avatar = (
			"7b6ea511d6e0ef6d1cdb2f7b53946c03" if customAvatar else None
		)
		self.perms = (
			nextcord.Permissions.all()
			if adminPowers
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
		*roles: SnowflakeABC,
		reason: str | None = None,
		atomic: bool = True
	) -> None:
		if reason or atomic:
			logging.info(
				"Role add reason: %s. Atomic operation: %s", reason, atomic
			)
		for role in roles:
			assert isinstance(role, nextcord.Role)
			self.roleList.append(role)

	@override
	async def send(  # type: ignore[override]
		self, *args: str | None, **kwargs: Any
	) -> None:
		await self._user.send(*args, **kwargs)

	@override
	async def _get_channel(self) -> nextcord.DMChannel:
		return await self._user._get_channel()


class MockUser(nextcord.User):
	"""
	Mock User class for offline testing.

	MockUser is a superset of nextcord.User with some features of
	nextcord.Member.

	TODO: move MockUserState out, apply to all classes, make generic
	"""

	class MockUserState(nextcord.state.ConnectionState):
		"""Drop-in replacement for ConnetionState."""

		@override
		def __init__(self, messageNum: int = 0) -> None:
			self._guilds: dict[int, nextcord.Guild] = {}
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop)
			self.user = None
			self.last_message_id = messageNum
			self.channel = MockChannel()

		@override
		def create_message(
			self, *, channel: MessageableChannel, data: MessagePayload
		) -> nextcord.Message:
			data["id"] = self.user.id if self.user else "0"
			data["components"] = []
			data["message_reference"] = {
				"message_id": self.last_message_id,
				"channel_id": str(channel.id)
			}
			self.last_message_id += 1
			message = nextcord.Message(state=self, channel=channel, data=data)
			assert self.channel._state._messages is not None
			self.channel._state._messages.append(message)
			return message

		@override
		def store_user(
			self, data: UserPayload | nextcord.User
		) -> nextcord.User:
			if isinstance(data, nextcord.User):
				return data
			storedUser = self.user or MockUser(uid=int(data.get("id", "0")))
			assert isinstance(storedUser, nextcord.User)
			return storedUser

		@override
		def get_channel(
			self, chid: int | None
		) -> ConnectionStateGetChannelTypes | None:
			return MockChannel(chid=chid) if chid is not None else self.channel

	@override
	def __init__(
		self,
		name: str = "testname",
		discriminator: str = "0000",
		uid: int = 123456789,
		messages: list[nextcord.Message] | None = None,
		*,
		customAvatar: bool = True,
		adminPowers: bool = False
	) -> None:
		self.name = name
		self.global_name = name
		self.id = uid
		self.discriminator = discriminator
		self.bot = False
		self.activity = None
		self.system = False
		self.messages = messages or []
		self._public_flags = 0
		self._state = self.MockUserState(messageNum=len(self.messages))
		self._state._private_channels_by_user = {
			uid: MockChannel()  # type: ignore[dict-item]
		}
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
		"""Assign the User object to its ConnectionState."""
		self._state.user = MockBot.MockClientUser(self)
		self._state.http.user_agent = str(self._state.user)

	@override
	def history(
		self,
		*,
		limit: int | None = 100,
		before: SnowflakeTime | None = None,
		after: SnowflakeTime | None = None,
		around: SnowflakeTime | None = None,
		oldest_first: bool | None = False
	) -> nextcord.iterators.HistoryIterator:
		channel = self._state.get_channel(None)
		assert isinstance(channel, nextcord.abc.Messageable)
		return MockHistoryIterator(
			channel,
			limit,
			before,
			after,
			around,
			oldest_first
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
			self, user: nextcord.ClientUser | None = None, messageNum: int = 0
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.user = user
			self.last_message_id = messageNum
			self._messages: deque[nextcord.Message] = deque()

		@override
		def create_message(
			self, *, channel: MessageableChannel, data: MessagePayload
		) -> nextcord.Message:
			data["id"] = self.last_message_id
			data["components"] = []
			user = self.user or MockUser()
			data["author"] = UserPayload(
				id=user.id,
				username=user.name,
				discriminator=user.discriminator,
				avatar=user._avatar
			)
			data["message_reference"] = {
				"message_id": self.last_message_id,
				"channel_id": str(channel.id)
			}
			self.last_message_id += 1
			message = nextcord.Message(state=self, channel=channel, data=data)
			self._messages.append(message)
			return message

		@override
		def store_user(self, data: UserPayload) -> nextcord.User:
			storedUser = self.user or MockUser(uid=int(data["id"]))
			assert isinstance(storedUser, nextcord.User)
			return storedUser

	@override
	def __init__(
		self,
		name: str = "testchannelname",
		guild: nextcord.Guild | None = None,
		messages: list[nextcord.Message] | None = None,
		chid: int = 123456789
	) -> None:
		self.name = name
		self.id = chid
		self.position = 0
		self.slowmode_delay = 0
		self.nsfw = False
		self.topic = None
		self.category_id = 0
		self.guild = guild  # type: ignore[assignment]
		self.messages = messages or []
		self._type = 0
		self._state = self.MockChannelState(messageNum=len(self.messages))
		self._overwrites = []
		self.assignChannelToGuild(self.guild)

	@overload
	@override
	async def set_permissions(
		self,
		target: nextcord.Member | nextcord.Role,
		*,
		overwrite: nextcord.PermissionOverwrite | None = ...,
		reason: str | None = ...
	) -> None:
		...

	@overload
	@override
	async def set_permissions(
		self,
		target: nextcord.Member | nextcord.Role,
		*,
		reason: str | None = ...,
		**permissions: bool
	) -> None:
		...

	@override
	async def set_permissions(
		self,
		target: nextcord.Member | nextcord.Role,
		*,
		reason: str | None = None,
		**kwargs: Any
	) -> None:
		if reason:
			logging.info("Permissions set reason: %s", reason)
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
			self._overwrites.append(nextcord.abc._Overwrites(payload))
		else:
			for ow in self._overwrites:
				if ow.id == target.id:
					self._overwrites.remove(ow)

	@override
	def history(
		self,
		*,
		limit: int | None = 100,
		before: SnowflakeTime | None = None,
		after: SnowflakeTime | None = None,
		around: SnowflakeTime | None = None,
		oldest_first: bool | None = False
	) -> nextcord.iterators.HistoryIterator:
		return MockHistoryIterator(
			self,
			limit,
			before,
			after,
			around,
			oldest_first
		)

	@override
	async def _get_channel(self) -> nextcord.TextChannel:
		return self

	@override
	async def send(self, *args: str | None, **kwargs: Any) -> nextcord.Message:
		msg = await super().send(*args, **kwargs)
		self.messages.append(msg)
		return msg

	def assignChannelToGuild(self, guild: nextcord.Guild) -> None:
		"""
		Add a channel to its Guild's list of channels.

		Args:
			guild (nextcord.Guild): The Guild to which the channel belongs

		"""
		if guild and self not in guild.channels:
			guild.channels.append(self)


# TODO: Write message.edit()
class MockMessage(nextcord.Message):
	"""Drop-in replacement for Message to enable offline testing."""

	class MockMessageState(nextcord.state.ConnectionState):
		"""Drop-in replacement for ConnetionState."""

		@override
		def __init__(
			self, user: nextcord.User, guild: nextcord.Guild | None = None
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(
				self.loop, user=MockBot.MockClientUser(user)
			)
			self.guild = guild or MockGuild()

		@override
		def get_reaction_emoji(
			self, data: EmojiPayload
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
		embed: nextcord.Embed | None = None
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
			), guild
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
	def getMockReactionPayload(
		name: str = "MockEmojiName",
		emojiId: int = 0,
		*,
		me: bool = False,
		count: int = 1
	) -> ReactionPayload:
		"""
		Create the payload for a Reaction.

		Args:
			name (str): The reaction emoji's name (default is "MockEmojiName")
			emojiId (int): The emoji's id (default is 0)
			me (bool): If the BotUser sent this reaction (default is False)
			count (int): Number of users who added this reaction for a given
				nextcord.Message (default is 1)

		Returns:
			ReactionPayload: The TypedDict that will be used to create a new
				Reaction, constructed with the provided arguments.

		"""
		return ReactionPayload(
			me=me,
			count=count,
			emoji=PartialEmojiPayload(id=emojiId, name=name)
		)


class MockRole(nextcord.Role):
	"""Drop-in replacement for Role to enable offline testing."""

	@override
	def __init__(
		self,
		name: str = "Test Role",
		rid: int = 123456789,
		permissions: int | nextcord.Permissions = 1879573680,
		colour: int = 0
	) -> None:
		self.name = name
		self.id = rid
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
		def __init__(self) -> None:
			user = MockBot.MockClientUser()
			self.member_cache_flags = nextcord.MemberCacheFlags.all()
			self.shard_count = 1
			self.loop = asyncio.get_event_loop()
			self.user = user
			self.http = MockHTTPClient(self.loop, user=user)
			self._intents = nextcord.Intents.all()
			self._guilds = {}

		@override
		async def chunk_guild(
			self,
			guild: nextcord.Guild,
			*,
			wait: bool = True,
			cache: bool | None = None
		) -> None:
			guild._member_count = len(guild._members)
			logging.info(
				"Chunked Guild %s with wait=%s and cache=%s",
				guild,
				wait,
				cache
			)

		@override
		async def query_members(
			self,
			guild: nextcord.Guild,
			query: str | None,
			limit: int,
			user_ids: list[int] | None,
			cache: bool,
			presences: bool
		) -> list[nextcord.Member]:
			logging.info(
				"Queried members in guild %s with query=%s, presences=%s",
				guild,
				query,
				presences
			)
			members: list[nextcord.Member] = []
			if self.user is not None and limit >= 1:
				await self.chunk_guild(guild, cache=cache)
				if not user_ids or (self.user.id in user_ids):
					assert hasattr(self.user, "baseUser")
					members.append(MockMember(self.user.baseUser, guild=guild))
			return members

	@override
	def __init__(
		self,
		members: list[nextcord.Member] | None = None,
		name: str = "Test Guild",
		gid: int = 0,
		channels: list[nextcord.TextChannel] | None = None,
		roles: list[nextcord.Role] | None = None,
		chunked: bool = True
	) -> None:
		self.name = name
		self.id = gid
		self._state = self.MockGuildState()
		self._members = dict(enumerate(members or []))
		self._member_count = len(self._members) if chunked else 0
		self._channels = dict(
			enumerate(channels or [MockChannel()])
		)
		self._roles = dict(enumerate(
			[MockRole(name="everyone", rid=0)]
			+ (roles if roles is not None else [MockRole()])
		))
		self.owner_id = 123456789
		for role in self._roles.values():
			self.assignGuild(role)

	@override
	@property
	def me(self) -> nextcord.Member:
		assert self._state.user is not None
		user = (
			self._state.user.baseUser
			if hasattr(self._state.user, "baseUser")
			else self._state.user
		)
		assert isinstance(user, nextcord.User)
		return MockMember(
			user,
			guild=self,
			perms=(
				user.guild_permissions
				if hasattr(user, "guild_permissions")
				else None
			)
		)

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
		icon: str | IconTypes | None = ...
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
		icon: str | IconTypes | None = ...
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
		reason: str | None = None
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
		if isinstance(icon, str):
			fields["unicode_emoji"] = icon
		else:
			fields["icon"] = await nextcord.utils.obj_to_base64_data(icon)

		data = await self._state.http.create_role(
			self.id, reason=reason, **fields
		)
		role = nextcord.Role(guild=self, data=data, state=self._state)
		self._roles[len(self.roles)] = role

		return role

	@override
	async def chunk(
		self, *, cache: bool = True
	) -> list[nextcord.Member] | None:
		await self._state.chunk_guild(self, cache=cache)
		return self.members

	def assignGuild(self, role: nextcord.Role) -> None:
		"""
		Set a Role's Guild to this Guild.

		Args:
			role (nextcord.Role): The role whose Guild will be set

		"""
		role.guild = self

	@override
	def get_member(self, userId: int, /) -> nextcord.Member | None:
		return MockMember(MockUser(uid=userId))

	@override
	def get_channel(self, channelId: int, /) -> GuildChannel | None:
		return self._channels.get(channelId)


class MockThread(nextcord.Thread):
	"""Drop-in replacement for Thread to enable offline testing."""

	@override
	def __init__(
		self,
		*,
		name: str = "testThread",
		owner: nextcord.User | None = None,
		channelId: int = 0,
		me: nextcord.Member | None = None,
		parent: nextcord.TextChannel | None = None,
		archived: bool = False,
		locked: bool = False
	) -> None:
		Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
		channel = parent or MockChannel(chid=channelId, guild=MockGuild())
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
		self.me = me  # type: ignore[assignment]
		self._members = copy(channel.guild._members)  # type: ignore[arg-type]
		if self.me and Bot.BeardlessBot.user is not None and not any(
			user.id == Bot.BeardlessBot.user.id for user in self.members
		):
			assert isinstance(Bot.BeardlessBot.user, MockBot.MockClientUser)
			self._members[
				len(self.members)
			] = MockMember(  # type: ignore[assignment]
				Bot.BeardlessBot.user.baseUser, guild=self.guild
			)
		self.member_count = len(self.members)

	@override
	async def join(self) -> None:
		# TODO: switch this to using self.me
		assert isinstance(
			Bot.BeardlessBot.user, MockBot.MockClientUser
		)
		if not any(
			user.id == Bot.BeardlessBot.user.id for user in self.members
		):
			if not any(
				user.id == Bot.BeardlessBot.user.id
				for user in self.guild.members
			):
				self.guild._members[
					len(self.guild.members)
				] = MockMember(
					Bot.BeardlessBot.user.baseUser, guild=self.guild
				)
			self._members[len(self.members)] = MockMember(  # type: ignore[assignment]
				Bot.BeardlessBot.user.baseUser, guild=self.guild
			)

	@override
	async def _get_channel(self) -> nextcord.Thread:
		return self


class MockContext(misc.BotContext):
	"""Drop-in replacement for Context to enable offline testing."""

	class MockContextState(nextcord.state.ConnectionState):
		"""Drop-in replacement for ConnetionState."""

		# TODO: make context inherit state from message,
		# as in actual Context._state
		@override
		def __init__(
			self,
			user: nextcord.ClientUser | None = None,
			channel: nextcord.TextChannel | None = None
		) -> None:
			self.loop = asyncio.get_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = nextcord.AllowedMentions(everyone=True)
			self.user = user
			self.channel = channel or MockChannel(guild=MockGuild())
			self.message = MockMessage()

		@override
		def create_message(
			self, *, channel: MessageableChannel, data: MessagePayload
		) -> nextcord.Message:
			assert isinstance(
				self.channel._state, MockChannel.MockChannelState
			)
			data["id"] = self.user.id if self.user else "0"
			data["components"] = []
			data["message_reference"] = {
				"message_id": self.channel._state.last_message_id,
				"channel_id": str(channel.id)
			}
			self.channel._state.last_message_id += 1
			message = nextcord.Message(state=self, channel=channel, data=data)
			assert self.channel._state._messages is not None
			self.channel._state._messages.append(message)
			return message

		@override
		def store_user(
			self, data: UserPayload | nextcord.User
		) -> nextcord.User:
			if isinstance(data, nextcord.User):
				return data
			storedUser = self.user or MockUser(uid=int(data.get("id", "0")))
			assert isinstance(storedUser, nextcord.User)
			return storedUser

	@override
	def __init__(
		self,
		bot: commands.Bot,
		message: nextcord.Message | None = None,
		channel: nextcord.TextChannel | None = None,
		author: nextcord.User | nextcord.Member | None = None,
		guild: nextcord.Guild | None = None,
		invoked_with: str | None = None
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
		oldest_first: bool | None = False
	) -> nextcord.iterators.HistoryIterator:
		assert hasattr(self._state, "channel")
		return MockHistoryIterator(
			self._state.channel,
			limit,
			before,
			after,
			around,
			oldest_first
		)

	@override
	async def _get_channel(self) -> MessageableChannel:
		return self.channel

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
			conn: nextcord.state.ConnectionState
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
		def __init__(self, baseUser: nextcord.User | None = None) -> None:
			self.baseUser = baseUser or MockUser(uid=misc.BbId)
			self.baseUser.bot = True
			self._state = self.baseUser._state
			self.id = self.baseUser.id
			self.name = "testclientuser"
			self.discriminator = "0000"
			self._avatar = str(self.baseUser.avatar)
			self.bot = True
			self.verified = True
			self.mfa_enabled = False
			self.global_name = self.baseUser.global_name
			self.nick = ""

		@override
		async def edit(
			self,
			username: str = "",
			avatar: IconTypes | None = None
		) -> nextcord.ClientUser:
			self.name = username or self.name
			self._avatar = str(avatar)
			return self

	@override
	def __init__(self, bot: commands.Bot) -> None:
		self._connection = bot._connection
		self.activity = None
		self._connection.user = self.MockClientUser()
		self.command_prefix = bot.command_prefix
		self.case_insensitive = bot.case_insensitive
		self._help_command = bot.help_command
		self._intents = bot.intents
		self.owner_id = bot.owner_id
		self.status = nextcord.Status.offline
		self._connection._guilds = {1: MockGuild(members=[MockMember()])}
		self.all_commands = bot.all_commands
		self.ws = self.MockBotWebsocket(
			self.MockClientWebSocketResponse(),
			loop=asyncio.get_event_loop(),
			conn=bot._connection
		)

	@override
	async def change_presence(
		self,
		*,
		activity: nextcord.BaseActivity | None = None,
		status: str | None = None
	) -> None:
		self.activity = activity  # type: ignore[assignment]
		self.status = status or nextcord.Status.online


class MockEmoji(nextcord.emoji.Emoji):
	"""Drop-in replacement for Emoji to enable offline testing."""

	@override
	def __init__(
		self,
		guild: nextcord.Guild,
		data: EmojiPayload,
		stateMessage: nextcord.Message | None = None
	) -> None:
		self.guild_id = guild.id
		self._state = (stateMessage or MockMessage())._state
		self._from_data(data)


def test_with_ruff_for_code_quality() -> None:
	"""
	Ruff codes.

	Invalid:
		COM812: Trailing comma missing
			(I don't like it)
		D203: 1 blank line required before class docstring
			(Incompatible with D211)
		D206: Spaces instead of tabs in docstrings
			(Tabs are the BB standard)
		D212: Multi-line docstring summary should start on first line
			(Incompatible with D213)
		ERA001: Commented-out code
			(Too many false positives)
		N802: Function name should be lowercase
			(lowerCamelCase is the BB standard)
		N803: Argument name should be lowercase
			(lowerCamelCase is the BB standard)
		N806: Variable in function should be lowercase
			(lowerCamelCase is the BB standard)
		Q003: Change outer quotes to avoid escaping inner quotes
			(Double quotes is the BB standard)
		S311: Don't use random for crypto
			(Not doing any cryptography)
		TD002: Missing author in TODO
			(They're all Lev)
		W191: Spaces instead of tabs
			(Tabs are the BB standard)

	Temporarily disable, fix later:
		ASYNC251: Async functions should not call time.sleep
			(HACK until all api calls are mocked)
		D103: Missing docstring in public function
			(I'm working on it...)
		FIX002: Line contains FIXME/TODO/XXX/HACK
			(I'm working on it...)
		S101: Use of assert
			(Shouldn't be present in production code)
		TD003: Missing issue link in TODO
			(Only some TODOs have issue links)

	"""
	version = f"py{sys.version_info.major}{sys.version_info.minor}"
	invalidCodes = (
		"COM812,D203,D206,D212,ERA001,N802,N803,N806,Q003,S311,TD002,W191"
	)
	temporaryIgnoreCodes = ",ASYNC251,D103,FIX002,S101,TD003"
	assert subprocess.run(
		[
			sys.executable,
			"-m",
			"ruff",
			"check",
			*FilesToCheck,
			"--line-length=80",
			"--select=ALL",
			"--target-version=" + version,
			"--output-format=grouped",
			"--ignore=" + invalidCodes + temporaryIgnoreCodes
		], capture_output=True, check=False, input=None
	).stdout == b"All checks passed!\n"


# Run code quality tests with pytest -vk quality
@pytest.mark.parametrize(
	"letter", ["W", "E", "F", "B", "C", "A", "SIM"]
)
def test_code_quality_with_flake8(letter: str) -> None:
	assert StyleGuide.check_files(FilesToCheck).get_statistics(letter) == []


def test_full_type_checking_with_mypy_for_code_quality() -> None:
	# Ignores certain false positives that expect the "Never" type;
	# see https://github.com/python/mypy/pull/17310, which would resolve that.
	# After that has been changed, start testing against exit code.
	results: tuple[str, str, int] = mypy([*FilesToCheck, "--strict"])
	# mypy.api.run() returns stdout, stderr, exit code
	errors = [
		i for i in results[0].split("\n")
		if ": error: " in i and "\"__call__\" of \"Command\"" not in i
	]
	assert len(errors) == 0
	assert results[1] == ""


def test_no_spelling_errors_with_codespell_for_code_quality() -> None:
	assert codespell(*FilesToCheck) == 0


def test_no_out_of_date_requirements_for_code_quality() -> None:
	pipListOutdated = subprocess.run(
		[sys.executable, "-m", "pip", "list", "--outdated"],
		capture_output=True,
		check=True,
		input=None
	).stdout.decode().split("\n")
	outdated = {i.split(" ")[0].lower() for i in pipListOutdated}
	with Path("resources/requirements.txt").open("r") as f:
		lines = f.read().split("\n")
	reqs = {i.split("==")[0].split("[")[0].lower() for i in lines}
	assert len(reqs.intersection(outdated)) == 0


def test_mockContext_channel_added_to_guild() -> None:
	ctx = MockContext(
		Bot.BeardlessBot,
		channel=MockChannel(chid=92835, guild=None),
		guild=MockGuild(channels=[])
	)
	assert ctx.guild is not None
	assert ctx.channel in ctx.guild.channels


def test_mockContext_author_added_to_members() -> None:
	ctx = MockContext(
		Bot.BeardlessBot, author=MockMember(), guild=MockGuild(members=[])
	)
	assert ctx.guild is not None
	assert ctx.author in ctx.guild.members


@pytest.mark.asyncio
async def test_mockGuild_chunked() -> None:
	member = MockMember(MockUser("foobar"))
	guild = MockGuild(members=[member], chunked=False)
	assert not guild.chunked
	chunkedUsers = await guild.chunk()
	assert chunkedUsers is not None
	assert len(chunkedUsers) == 1
	assert chunkedUsers[0] == member
	assert guild.chunked


@pytest.mark.asyncio
async def test_logException(caplog: pytest.LogCaptureFixture) -> None:
	author = MockMember(adminPowers=True)
	guild = MockGuild()
	assert isinstance(guild._state, MockGuild.MockGuildState)
	ctx = MockContext(
		Bot.BeardlessBot,
		message=MockMessage(content="!brawllegend foobar"),
		author=author,
		guild=guild,
		invoked_with="brawllegend"
	)
	exc = commands.errors.CommandError("Foobar")
	assert await Bot.on_command_error(ctx, exc) == 1
	assert caplog.records[0].args == (
		exc,
		"brawllegend",
		author,
		"!brawllegend foobar",
		guild,
		commands.errors.CommandError
	)


@pytest.mark.asyncio
async def test_createMutedRole(caplog: pytest.LogCaptureFixture) -> None:
	g = MockGuild(roles=[])
	assert len(g.roles) == 1
	caplog.set_level(logging.INFO)
	role = await misc.createMutedRole(g)
	assert role.name == "Muted"
	assert g.roles[1] == role
	assert caplog.records[0].getMessage() == (
		"Role creation reason: BB Muted Role"
	)
	assert caplog.records[1].getMessage() == (
		"Permissions set reason: Preventing Muted"
		" users from chatting in this channel"
	)

	role = MockRole("Muted", 500)
	assert await misc.createMutedRole(MockGuild(roles=[role])) == role


@pytest.mark.asyncio
async def test_role_creation_reason_logged(
	caplog: pytest.LogCaptureFixture
) -> None:
	# Reasons for actions are normally recorded in the audit log; I don't
	# have an easy way to access that. Instead, log it.
	g = MockGuild(roles=[])
	assert len(g.roles) == 1
	caplog.set_level(logging.INFO)
	await g.create_role(name="Spamalot", reason="FooBarSpam")
	assert caplog.records[0].getMessage() == "Role creation reason: FooBarSpam"
	assert len(g.roles) == 2
	assert g.roles[1].name == "Spamalot"


def test_bot_avatar_correct_on_creation() -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	assert Bot.BeardlessBot.user is not None
	assert isinstance(Bot.BeardlessBot.user._avatar, str)
	assert isinstance(Bot.BeardlessBot.user.avatar, nextcord.Asset)
	assert Bot.BeardlessBot.user.avatar.url == (
		f"https://cdn.discordapp.com/avatars/{misc.BbId}/"
		f"{Bot.BeardlessBot.user.avatar.key}.png?size=1024"
	)


@pytest.mark.asyncio
async def test_on_ready(caplog: pytest.LogCaptureFixture) -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	caplog.set_level(logging.INFO)
	await Bot.on_ready()
	assert Bot.BeardlessBot.activity is not None
	assert Bot.BeardlessBot.activity.name == "try !blackjack and !flip"
	assert Bot.BeardlessBot.status == nextcord.Status.online
	assert caplog.records[-1].args == (1, 1)

	Bot.BeardlessBot._connection._guilds[2] = MockGuild(
		name="Foo",
		gid=1,
		members=Bot.BeardlessBot._connection._guilds[1].members
	)
	await Bot.on_ready()
	assert caplog.records[-1].args == (1, 2)

	Bot.BeardlessBot._connection._guilds[3] = MockGuild(
		name="Foo",
		gid=1,
		members=[MockMember(MockUser(uid=12, name="Foobar"))]
	)
	await Bot.on_ready()
	assert caplog.records[-1].args == (2, 3)


@pytest.mark.asyncio
async def test_on_ready_raises_exceptions(
	caplog: pytest.LogCaptureFixture
) -> None:

	def mock_raise_HTTPException(
		Bot: commands.Bot, activity: nextcord.Game
	) -> None:
		resp = requests.Response()
		resp.status = misc.BadRequest  # type: ignore[attr-defined]
		raise nextcord.HTTPException(resp, f"{Bot}, activity {activity}")

	def mock_raise_FileNotFoundError(filepath: str, mode: str) -> None:
		raise FileNotFoundError(filepath + "," + mode)

	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	Bot.BeardlessBot._connection._guilds = {}
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
	ch = MockChannel()
	g = MockGuild(
		name="Foo", roles=[MockRole(name="Beardless Bot")], channels=[ch]
	)
	g._state.user = MockUser(adminPowers=True)  # type: ignore[assignment]
	await Bot.on_guild_join(g)
	emb = (await ch.history().next()).embeds[0]
	assert emb.title == "Hello, Foo!"
	assert isinstance(emb.description, str)
	assert emb.description.startswith("Thanks for adding me to Foo!")
	assert "my <@&123456789> role" in emb.description

	g._state.user = MockUser(adminPowers=False)  # type: ignore[assignment]
	caplog.set_level(logging.INFO)
	await Bot.on_guild_join(g)
	emb = (await ch.history().next()).embeds[0]
	assert emb.title == "I need admin perms!"
	assert emb.description == misc.AdminPermsReasons
	assert caplog.records[3].getMessage() == "Left Foo."


@pytest.mark.parametrize(
	("msgLength", "description"),
	[
		(1, "e"),
		(0, "**Embed**"),
		(1025, "**Message length exceeds 1024 characters.**")
	]
)
def test_contCheck(msgLength: int, description: str) -> None:
	assert misc.contCheck(MockMessage("e" * msgLength)) == description


def test_contCheck_custom_limit() -> None:
	assert misc.contCheck(
		MockMessage("e" * 917), 108
	) == "**Message length exceeds 1024 characters.**"

	assert misc.contCheck(
		MockMessage("e" * 2000), -2000
	) == "**Message length exceeds 1024 characters.**"

	assert misc.contCheck(
		MockMessage(""), 1025
	) == "**Embed**"


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
	assert (await ch.history().next()).embeds[0].description == log.description

	assert await Bot.on_message_delete(MockMessage()) is None


@pytest.mark.asyncio
async def test_on_bulk_message_delete() -> None:
	ch = MockChannel(name="bb-log")
	m = MockMessage(channel=ch)
	m.guild = MockGuild(channels=[ch])
	messages = [m, m, m]
	emb = await Bot.on_bulk_message_delete(messages)
	assert emb is not None
	log = logs.logPurge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == "Purged 2 messages in <#123456789>."
	assert (await ch.history().next()).embeds[0].description == log.description

	messages = [m] * 105
	emb = await Bot.on_bulk_message_delete(messages)
	assert emb is not None
	log = logs.logPurge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == "Purged 99+ messages in <#123456789>."

	assert await Bot.on_bulk_message_delete(
		[MockMessage(guild=MockGuild())]
	) is None


@pytest.mark.asyncio
async def test_on_reaction_clear() -> None:
	ch = MockChannel(chid=0, name="bb-log")
	guild = MockGuild(channels=[ch])
	ch.guild = guild
	reaction = nextcord.Reaction(
		message=MockMessage(), data=MockMessage.getMockReactionPayload("foo")
	)
	otherReaction = nextcord.Reaction(
		message=MockMessage(), data=MockMessage.getMockReactionPayload("bar")
	)
	msg = MockMessage(guild=guild)
	emb = await Bot.on_reaction_clear(msg, [reaction, otherReaction])
	assert emb is not None
	assert emb.description == (
		"Reactions cleared from message sent by <@123456789> in <#123456789>."
	)

	assert emb.fields[0].value is not None
	assert emb.fields[0].value.startswith(msg.content)
	assert emb.fields[1].value == "<:foo:0>, <:bar:0>"
	assert (await ch.history().next()).embeds[0].description == emb.description

	assert await Bot.on_reaction_clear(
		MockMessage(guild=MockGuild()), [reaction, otherReaction]
	) is None


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
	assert (await ch.history().next()).embeds[0].description == log.description

	assert await Bot.on_guild_channel_delete(
		MockChannel(guild=MockGuild())
	) is None


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
	assert (await ch.history().next()).embeds[0].description == log.description

	assert await Bot.on_guild_channel_create(
		MockChannel(guild=MockGuild())
	) is None


@pytest.mark.asyncio
async def test_on_member_ban() -> None:
	ch = MockChannel(name="bb-log")
	g = MockGuild(channels=[ch])
	member = MockMember()
	emb = await Bot.on_member_ban(g, member)
	assert emb is not None
	log = logs.logBan(member)
	assert emb.description == log.description
	assert log.description == "Member <@123456789> banned\ntestname"
	assert (await ch.history().next()).embeds[0].description == log.description

	assert await Bot.on_member_ban(
		MockGuild(), MockMember(guild=MockGuild())
	) is None


@pytest.mark.asyncio
async def test_on_member_unban() -> None:
	ch = MockChannel(name="bb-log")
	g = MockGuild(channels=[ch])
	member = MockMember()
	emb = await Bot.on_member_unban(g, member)
	assert emb is not None
	log = logs.logUnban(member)
	assert emb.description == log.description
	assert (
		log.description == "Member <@123456789> unbanned\ntestname"
	)
	assert (await ch.history().next()).embeds[0].description == log.description

	assert await Bot.on_member_unban(
		MockGuild(), MockMember(guild=MockGuild())
	) is None


@pytest.mark.asyncio
async def test_on_member_join() -> None:
	member = MockMember()
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
	assert (await ch.history().next()).embeds[0].description == log.description

	assert await Bot.on_member_join(MockMember(guild=MockGuild())) is None


@pytest.mark.asyncio
async def test_on_member_remove() -> None:
	member = MockMember()
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
	assert (await ch.history().next()).embeds[0].description == log.description

	assert await Bot.on_member_remove(MockMember(guild=MockGuild())) is None


@pytest.mark.asyncio
async def test_on_member_update() -> None:
	ch = MockChannel(name="bb-log")
	guild = MockGuild(channels=[ch])
	old = MockMember(nick="a", roles=[], guild=guild)
	new = MockMember(nick="b", roles=[], guild=guild)
	emb = await Bot.on_member_update(old, new)
	assert emb is not None
	log = logs.logMemberNickChange(old, new)
	assert emb.description == log.description
	assert log.description == "Nickname of <@123456789> changed."
	assert log.fields[0].value == old.nick
	assert log.fields[1].value == new.nick
	assert (await ch.history().next()).embeds[0].description == log.description

	newRole = MockRole()
	newRole.guild = guild
	new = MockMember(nick="a", guild=guild, roles=[newRole])
	assert new.guild is not None
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

	m = MockMember(guild=MockGuild())
	assert await Bot.on_member_update(m, m) is None


@pytest.mark.asyncio
async def test_on_message_edit() -> None:
	ch = MockChannel(name="bb-log")
	member = MockMember()
	g = MockGuild(
		channels=[ch, MockChannel(name="infractions")],
		roles=[]
	)
	assert len(g.roles) == 1
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

	assert len(g.roles) == 2
	assert g.roles[1].name == "Muted"
	# TODO: edit after to have content of len > 1024 via message.edit
	h = ch.history()
	assert not any(i.content == after.content for i in ch.messages)
	assert (await h.next()).embeds[0].description == log.description
	assert (await h.next()).content.startswith("Deleted possible")

	assert await Bot.on_message_edit(MockMessage(), MockMessage()) is None


@pytest.mark.asyncio
async def test_on_thread_join() -> None:
	ch = MockChannel(chid=0, name="bb-log")
	guild = MockGuild(channels=[ch])
	ch.guild = guild
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
	assert (await ch.history().next()).embeds[0].description == emb.description

	ch.name = "bar"
	assert await Bot.on_thread_join(
		MockThread(parent=ch, me=None, name="Foo")
	) is None


@pytest.mark.asyncio
async def test_on_thread_delete() -> None:
	ch = MockChannel(chid=0, name="bb-log")
	guild = MockGuild(channels=[ch])
	ch.guild = guild
	thread = MockThread(parent=ch, name="Foo")
	emb = await Bot.on_thread_delete(thread)
	assert emb is not None
	assert emb.description == (
		"Thread \"Foo\" deleted."
	)
	assert (await ch.history().next()).embeds[0].description == emb.description

	ch.name = "bar"
	assert await Bot.on_thread_delete(
		MockThread(parent=ch, me=MockMember(), name="Foo")
	) is None


@pytest.mark.asyncio
async def test_on_thread_update() -> None:
	ch = MockChannel(chid=0, name="bb-log")
	guild = MockGuild(channels=[ch])
	ch.guild = guild
	before = MockThread(parent=ch, name="Foo")
	after = MockThread(parent=ch, name="Foo")
	assert await Bot.on_thread_update(before, after) is None

	before.archived = True
	before.archive_timestamp = datetime.now(misc.TimeZone)
	emb = await Bot.on_thread_update(before, after)
	assert emb is not None
	assert emb.description == "Thread \"Foo\" unarchived."
	assert (await ch.history().next()).embeds[0].description == emb.description

	emb = await Bot.on_thread_update(after, before)
	assert emb is not None
	assert emb.description == "Thread \"Foo\" archived."
	assert (await ch.history().next()).embeds[0].description == emb.description

	ch.name = "bar"
	th = MockThread(parent=ch, name="Foo")
	assert await Bot.on_thread_update(th, th) is None


@pytest.mark.asyncio
async def test_cmdDice() -> None:
	ch = MockChannel()
	ctx = MockContext(
		Bot.BeardlessBot,
		channel=ch,
		author=MockMember(MockUser(uid=400005678)),
		guild=MockGuild(channels=[ch])
	)
	emb: nextcord.Embed = await Bot.cmdDice(ctx)
	assert isinstance(emb, nextcord.Embed)
	assert isinstance(emb.description, str)
	assert emb.description.startswith(
		"Welcome to Beardless Bot dice, <@400005678>!"
	)
	assert (await ch.history().next()).embeds[0].description == emb.description


@pytest.mark.asyncio
async def test_fact() -> None:
	ch = MockChannel()
	ctx = MockContext(
		Bot.BeardlessBot, channel=ch, guild=MockGuild(channels=[ch])
	)
	firstFact = (
		"The scientific term for brain freeze"
		" is sphenopalatine ganglioneuralgia."
	)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.choice", lambda x: x[0])
		assert misc.fact() == firstFact

		mp.setattr("random.randint", lambda _, y: y)
		assert await Bot.cmdFact(ctx) == 1
	emb = (await ch.history().next()).embeds[0]
	assert emb.description == firstFact
	assert emb.title == "Beardless Bot Fun Fact #111111111"


@pytest.mark.asyncio
async def test_cmdAnimals() -> None:
	ch = MockChannel()
	ctx = MockContext(
		Bot.BeardlessBot, channel=ch, guild=MockGuild(channels=[ch])
	)
	assert await Bot.cmdAnimals(ctx) == 1
	emb = (await ch.history().next()).embeds[0]
	assert len(emb.fields) == 9
	assert emb.fields[0].value == (
		"Can also do !dog breeds to see breeds you"
		" can get pictures of with !dog [breed]"
	)
	assert all(i.value == "_ _" for i in emb.fields[1:])

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("misc.AnimalList", ("frog", "cat"))
		assert await Bot.cmdAnimals(ctx) == 1
	assert len((await ch.history().next()).embeds[0].fields) == 3


def test_tweet() -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda x, _: x)
		eggTweet = misc.tweet()
	assert ("\n" + eggTweet).startswith(misc.formattedTweet(eggTweet))
	assert len(eggTweet.split(" ")) == 11

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.choice", lambda _: "the")
		mp.setattr("random.randint", lambda x, _: x)
		eggTweet = misc.tweet()

	assert eggTweet == "The" + (" the" * 10)

	assert "." not in misc.formattedTweet("test tweet.")
	assert "." not in misc.formattedTweet("test tweet")


@pytest.mark.parametrize("side", [4, 6, 8, 10, 12, 20, 100])
def test_dice_regular(side: int) -> None:
	member = MockMember()
	text = "d" + str(side)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda _, y: y)
		roll = misc.roll(text)
	assert roll is not None
	assert roll[0] == side

	report = misc.rollReport(text, member)
	assert isinstance(report.description, str)
	assert report.description.startswith("You got")
	assert isinstance(report.title, str)
	assert text in report.title


def test_dice_irregular() -> None:
	member = MockMember()
	emb = misc.rollReport("d20-4", member)
	assert isinstance(emb.description, str)
	assert emb.description.startswith("You got")

	assert misc.roll("wrongroll") is None

	assert misc.roll("d9") is None

	emb = misc.rollReport("d9", member)
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


def test_logMute() -> None:
	message = MockMessage(channel=MockChannel(chid=1))
	member = MockMember(MockUser(uid=2))
	assert logs.logMute(member, message, "5 hours").description == (
		"Muted <@2> for 5 hours in <#1>."
	)

	assert logs.logMute(member, message, None).description == (
		"Muted <@2> in <#1>."
	)


def test_logUnmute() -> None:
	assert logs.logUnmute(
		MockMember(MockUser(uid=3)), MockMember()
	).description == "Unmuted <@3>."


def test_getLogChannel() -> None:
	assert misc.getLogChannel(MockGuild()) is None
	ch = misc.getLogChannel(
		MockGuild(channels=[MockChannel(name="bb-log")])
	)
	assert isinstance(ch, nextcord.TextChannel)
	assert ch.name == "bb-log"


def test_fetchAvatar_custom() -> None:
	member = MockUser(uid=12121212)
	assert isinstance(member.avatar, nextcord.Asset)
	assert member.avatar.url == (
		"https://cdn.discordapp.com/avatars/12121212/"
		"7b6ea511d6e0ef6d1cdb2f7b53946c03.png?size=1024"
	)
	assert misc.fetchAvatar(member) == member.avatar.url


def test_fetchAvatar_default() -> None:
	member = MockMember(MockUser(uid=5000000, customAvatar=False))
	assert member.avatar is None
	assert member.default_avatar.url == (
		f"https://cdn.discordapp.com/embed/avatars/{member.id >> 22}.png"
	)
	assert misc.fetchAvatar(member) == member.default_avatar.url


@pytest.mark.parametrize(
	("username", "content"),
	[
		("searchterm", "searchterm#9999"),
		("searchterm", "searchterm"),
		("searchterm", "search"),
		("searchterm", "testnick"),
		("hash#name", "hash#name")
	]
)
def test_memSearch_valid(username: str, content: str) -> None:
	namedMember = MockMember(
		MockUser(username, discriminator="9999"), "testnick"
	)
	text = MockMessage(
		content=content, guild=MockGuild(members=[MockMember(), namedMember])
	)
	assert misc.memSearch(text, content) == namedMember


def test_memSearch_invalid() -> None:
	namedMember = MockMember(MockUser("searchterm", discriminator="9999"))
	text = MockMessage(
		content="invalidterm",
		guild=MockGuild(members=[MockMember(), namedMember])
	)
	assert misc.memSearch(text, text.content) is None


def test_register() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", uid=misc.BbId),
		"Beardless Bot"
	)
	bucks.reset(bb)
	assert bucks.register(bb).description == (
		"You are already in the system! Hooray! You"
		f" have 200 BeardlessBucks, <@{misc.BbId}>."
	)

	bb._user.name = ",badname,"
	assert bucks.register(bb).description == (
		bucks.CommaWarn.format(f"<@{misc.BbId}>")
	)


@pytest.mark.parametrize(
	("target", "result"),
	[
		(
			MockMember(MockUser("Test", "5757", misc.BbId)),
			"'s balance is 200"
		),
		(MockMember(MockUser(",")), bucks.CommaWarn.format("<@123456789>")),
		("Invalid user", "Invalid user!")
	]
)
def test_balance(target: nextcord.User, result: str) -> None:
	msg = MockMessage("!bal", guild=MockGuild())
	desc = bucks.balance(target, msg).description
	assert isinstance(desc, str)
	assert result in desc


def test_reset() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", uid=misc.BbId),
		"Beardless Bot"
	)
	assert bucks.reset(bb).description == (
		f"You have been reset to 200 BeardlessBucks, <@{misc.BbId}>."
	)

	bb._user.name = ",badname,"
	assert bucks.reset(bb).description == (
		bucks.CommaWarn.format(f"<@{misc.BbId}>")
	)


def test_writeMoney() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", uid=misc.BbId),
		"Beardless Bot"
	)
	bucks.reset(bb)
	assert bucks.writeMoney(
		bb, "-all", writing=False, adding=False
	) == (bucks.MoneyFlags.BalanceUnchanged, 200)

	assert bucks.writeMoney(
		bb, -1000000, writing=True, adding=False
	) == (bucks.MoneyFlags.NotEnoughBucks, None)


def test_leaderboard() -> None:
	lb = bucks.leaderboard()
	assert lb.title == "BeardlessBucks Leaderboard"
	assert len(lb.fields) == 10
	assert lb.fields[0].value is not None
	assert lb.fields[1].value is not None
	assert int(lb.fields[0].value) > int(lb.fields[1].value)

	lb = bucks.leaderboard(
		MockMember(MockUser(name="bad,name", uid=0)),
		MockMessage(author=MockMember())
	)
	assert len(lb.fields) == 10

	lb = bucks.leaderboard(
		MockMember(
			MockUser("Beardless Bot", discriminator="5757", uid=misc.BbId),
			"Beardless Bot"
		),
		MockMessage()
	)
	assert len(lb.fields) == 12
	assert lb.fields[-1].name == "Beardless Bot's balance:"

	g = MockGuild([
		MockMember(MockUser("Foobar", uid=misc.BbId)),
		MockMember(MockUser("Spam"))
	])
	lb = bucks.leaderboard("Foobar", MockMessage(guild=g))
	assert lb.fields[-1].name == "Foobar's balance:"


@pytest.mark.asyncio
async def test_define_valid(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		json=[{
			"word": "foo",
			"phonetics": [{"audio": "spam"}],
			"meanings": [{"definitions": [{"definition": "Foobar"}]}]
		}]
	)
	word = await misc.define("foo")
	assert word.title == "FOO"
	assert word.description == "Audio: spam"


@pytest.mark.asyncio
async def test_define_no_audio_has_blank_description(
	httpx_mock: HTTPXMock
) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		json=[{
			"word": "foo",
			"phonetics": [],
			"meanings": [{"definitions": [{"definition": "Foobar"}]}]
		}]
	)
	word = await misc.define("foo")
	assert word.title == "FOO"
	assert word.description == ""


@pytest.mark.asyncio
async def test_define_invalid_word_returns_no_results_found(
	httpx_mock: HTTPXMock
) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/foo",
		status_code=misc.BadRequest
	)
	emb = await misc.define("foo")
	assert emb.description == "No results found."


@pytest.mark.asyncio
async def test_define_api_down_returns_error_message(
	httpx_mock: HTTPXMock
) -> None:
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/test",
		status_code=400
	)
	word = await misc.define("test")
	assert isinstance(word.description, str)
	assert word.description.startswith("There was an error")


@pytest.mark.asyncio
@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
async def test_cmdDefine(httpx_mock: HTTPXMock) -> None:
	ch = MockChannel(guild=MockGuild())
	ctx = MockContext(Bot.BeardlessBot, channel=ch)
	resp = [{"word": "f", "phonetics": [], "meanings": [{"definitions": []}]}]
	httpx_mock.add_response(
		url="https://api.dictionaryapi.dev/api/v2/entries/en_US/f", json=resp
	)
	assert await Bot.cmdDefine(ctx, words="f") == 1
	emb = (await ch.history().next()).embeds[0]
	definition = await misc.define("f")
	assert emb.title == definition.title == "F"


@pytest.mark.asyncio
async def test_cmdPing() -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	ch = MockChannel(guild=MockGuild())
	ctx = MockContext(Bot.BeardlessBot, channel=ch)
	assert await Bot.cmdPing(ctx) == 1
	emb = (await ch.history().next()).embeds[0]
	assert emb.description == "Beardless Bot's latency is 25 ms."

	Bot.BeardlessBot._connection.user = None
	assert await Bot.cmdPing(ctx) == -1


def test_flip() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", uid=misc.BbId),
		"Beardless Bot"
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
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(balMsg.description, str)
	assert "is 0" in balMsg.description

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda *_: 0)
		bucks.flip(bb, 37)
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(balMsg.description, str)
	assert "is 163" in balMsg.description

	bucks.reset(bb)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("random.randint", lambda *_: 1)
		assert bucks.flip(bb, "all") == (
			"Heads! You win! Your winnings have been"
			f" added to your balance, <@{misc.BbId}>."
		)
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(balMsg.description, str)
	assert "is 400" in balMsg.description

	bucks.reset(bb)
	assert bucks.flip(bb, "10000000000000").startswith("You do not have")
	bucks.reset(bb)
	balMsg = bucks.balance(bb, MockMessage("!bal", bb))
	assert isinstance(balMsg.description, str)
	assert "200" in balMsg.description

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"bucks.writeMoney",
			lambda *_, **__: (bucks.MoneyFlags.Registered, 0)
		)
		assert bucks.flip(bb, "0") == (
			bucks.NewUserMsg.format(f"<@{misc.BbId}>")
		)

	bb._user.name = ",invalidname,"
	assert bucks.flip(bb, "0") == bucks.CommaWarn.format(f"<@{misc.BbId}>")


@pytest.mark.asyncio
async def test_cmdFlip() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", uid=misc.BbId),
		"Beardless Bot"
	)
	ch = MockChannel(guild=MockGuild())
	ctx = MockContext(
		Bot.BeardlessBot, MockMessage("!flip 0"), ch, bb, MockGuild()
	)
	Bot.Games = []
	assert await Bot.cmdFlip(ctx, bet="0") == 1
	emb = (await ch.history().next()).embeds[0]
	assert emb.description is not None
	assert emb.description.endswith("actually bet anything.")

	Bot.Games.append(bucks.BlackjackGame(bb, 10))
	assert await Bot.cmdFlip(ctx, bet="0") == 1
	emb = (await ch.history().next()).embeds[0]
	assert emb.description == bucks.FinMsg.format(f"<@{misc.BbId}>")


def test_blackjack() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", uid=misc.BbId),
		"Beardless Bot"
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
			"bucks.writeMoney",
			lambda *_, **__: (bucks.MoneyFlags.Registered, 0)
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


@pytest.mark.asyncio
async def test_cmdBlackjack() -> None:
	bb = MockMember(
		MockUser("Beardless Bot", discriminator="5757", uid=misc.BbId),
		"Beardless Bot"
	)
	ch = MockChannel(guild=MockGuild())
	ctx = MockContext(
		Bot.BeardlessBot, MockMessage("!blackjack 0"), ch, bb, MockGuild()
	)
	Bot.Games = []
	assert await Bot.cmdBlackjack(ctx, bet="all") == 1
	emb = (await ch.history().next()).embeds[0]
	assert emb.description is not None
	assert emb.description.startswith("Your starting hand consists of")

	Bot.Games.append(bucks.BlackjackGame(bb, 10))
	assert await Bot.cmdBlackjack(ctx, bet="0") == 1
	emb = (await ch.history().next()).embeds[0]
	assert emb.description is not None
	assert emb.description == bucks.FinMsg.format(f"<@{misc.BbId}>")


def test_blackjack_perfect() -> None:
	game = bucks.BlackjackGame(MockMember(), 10)
	game.cards = [10, 11]
	assert game.perfect()


@pytest.mark.asyncio
async def test_cmdDeal() -> None:
	Bot.Games = []
	bb = MockMember(
		MockUser("Beardless,Bot", discriminator="5757", uid=misc.BbId)
	)
	ch = MockChannel(guild=MockGuild())
	ctx = MockContext(
		Bot.BeardlessBot, MockMessage("!hit"), ch, bb, MockGuild()
	)
	assert await Bot.cmdDeal(ctx) == 1
	emb = (await ch.history().next()).embeds[0]
	assert emb.description == bucks.CommaWarn.format(f"<@{misc.BbId}>")

	bb._user.name = "Beardless Bot"
	assert await Bot.cmdDeal(ctx) == 1
	emb = (await ch.history().next()).embeds[0]
	assert emb.description == bucks.NoGameMsg.format(f"<@{misc.BbId}>")

	game = bucks.BlackjackGame(bb, 0)
	game.cards = [2, 2]
	Bot.Games = []
	Bot.Games.append(game)
	assert await Bot.cmdDeal(ctx) == 1
	emb = (await ch.history().next()).embeds[0]
	assert len(game.cards) == 3
	assert emb.description is not None
	assert emb.description.startswith("You were dealt")

	game = bucks.BlackjackGame(bb, 0)
	game.cards = [10, 10, 10]
	Bot.Games = []
	Bot.Games.append(game)
	assert await Bot.cmdDeal(ctx) == 1
	emb = (await ch.history().next()).embeds[0]
	assert emb.description is not None
	assert f"You busted. Game over, <@{misc.BbId}>." in emb.description
	assert len(Bot.Games) == 0

	game = bucks.BlackjackGame(bb, 0)
	game.cards = [10, 10]
	Bot.Games.append(game)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("bucks.BlackjackGame.perfect", lambda _: True)
		mp.setattr("bucks.BlackjackGame.checkBust", lambda _: False)
		assert await Bot.cmdDeal(ctx) == 1
	emb = (await ch.history().next()).embeds[0]
	assert emb.description is not None
	assert f"You hit 21! You win, <@{misc.BbId}>!" in emb.description
	assert len(Bot.Games) == 0


def test_blackjack_deal() -> None:
	game = bucks.BlackjackGame(MockMember(), 10)
	game.cards = [2, 3]
	game.deal()
	assert len(game.cards) == 3

	game.cards = [11, 9]
	game.deal()
	assert sum(game.cards) <= 21
	assert "will be treated as a 1" in game.message

	game.cards = []
	assert "You hit 21!" in game.deal(debug=True)


def test_blackjack_cardName() -> None:
	assert bucks.BlackjackGame.cardName(10) in {
		"a 10", "a Jack", "a Queen", "a King"
	}
	assert bucks.BlackjackGame.cardName(11) == "an Ace"

	assert bucks.BlackjackGame.cardName(8) == "an 8"

	assert bucks.BlackjackGame.cardName(5) == "a 5"


def test_blackjack_checkBust() -> None:
	game = bucks.BlackjackGame(MockMember(), 10)
	game.cards = [10, 10, 10]
	assert game.checkBust()

	game.cards = [3, 4]
	assert not game.checkBust()


def test_blackjack_stay() -> None:
	game = bucks.BlackjackGame(MockMember(), 0)
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
	game = bucks.BlackjackGame(MockMember(), 10)
	game.cards = []
	game.message = game.startingHand()
	assert len(game.cards) == 2
	assert game.message.startswith("Your starting hand consists of ")

	game.cards = []
	assert "You hit 21!" in game.startingHand(debugBlackjack=True)
	assert len(game.cards) == 2

	game.cards = []
	assert "two Aces" in game.startingHand(debugDoubleAces=True)
	assert len(game.cards) == 2
	assert game.cards[1] == 1


def test_activeGame() -> None:
	author = MockMember(MockUser(name="target", uid=0))
	games = [
		bucks.BlackjackGame(MockMember(MockUser(name="not", uid=1)), 10)
	] * 9
	assert bucks.activeGame(games, author) is None

	games.append(bucks.BlackjackGame(author, 10))
	assert bucks.activeGame(games, author)


def test_info() -> None:
	namedMember = MockMember(MockUser("searchterm"))
	guild = MockGuild(members=[MockMember(), namedMember])
	namedMember.roles = [guild.roles[0], guild.roles[0]]
	text = MockMessage("!info searchterm", guild=guild)
	namedUserInfo = misc.info("searchterm", text)
	assert namedUserInfo.fields[0].value == (
		misc.truncTime(namedMember) + " UTC"
	)
	assert namedUserInfo.fields[1].value == (
		misc.truncTime(namedMember) + " UTC"
	)
	assert namedUserInfo.fields[2].value == "<@&123456789>"

	assert misc.info("!infoerror", text).title == "Invalid target!"


def test_avatar() -> None:
	namedMember = MockMember(MockUser("searchterm"))
	guild = MockGuild(members=[MockMember(), namedMember])
	text = MockMessage("!av searchterm", guild=guild)
	avatar = str(misc.fetchAvatar(namedMember))
	assert misc.avatar("searchterm", text).image.url == avatar

	assert misc.avatar("error", text).title == "Invalid target!"

	assert misc.avatar(namedMember, text).image.url == avatar

	text.guild = None
	text.author = namedMember
	assert misc.avatar("searchterm", text).image.url == avatar


@pytest.mark.asyncio
async def test_BbHelpCommand(caplog: pytest.LogCaptureFixture) -> None:
	helpCommand = misc.BbHelpCommand()
	assert helpCommand.command_attrs["aliases"] == ["commands"]
	ch = MockChannel()
	author = MockMember()
	helpCommand.context = MockContext(
		Bot.BeardlessBot, author=author, guild=None, channel=ch
	)
	await helpCommand.send_bot_help({})

	helpCommand.context.guild = MockGuild()
	author.guild_permissions = nextcord.Permissions(manage_messages=True)
	await helpCommand.send_bot_help({})

	author.guild_permissions = nextcord.Permissions(manage_messages=False)
	await helpCommand.send_bot_help({})

	h = ch.history()
	assert len((await h.next()).embeds[0].fields) == 17
	assert len((await h.next()).embeds[0].fields) == 20
	assert len((await h.next()).embeds[0].fields) == 15

	helpCommand.context.message.type = nextcord.MessageType.thread_created
	assert await helpCommand.send_bot_help({}) == -1

	# For the time being, just pass on all invalid help calls;
	# don't send any messages.
	await helpCommand.send_error_message("Bar")
	assert caplog.records[0].getMessage() == "No command Bar"
	assert len(caplog.records) == 1


def test_pingMsg() -> None:
	assert brawl.pingMsg("<@200>", 1, 1, 1).endswith(
		"You can ping again in 1 hour, 1 minute, and 1 second."
	)
	assert brawl.pingMsg("<@200", 2, 2, 2).endswith(
		"You can ping again in 2 hours, 2 minutes, and 2 seconds."
	)


def test_scamCheck() -> None:
	assert misc.scamCheck("http://dizcort.com free nitro!")
	assert misc.scamCheck("@everyone http://didcord.gg free nitro!")
	assert misc.scamCheck("gift nitro http://d1zcordn1tr0.co.uk free!")
	assert misc.scamCheck(
		"hey @everyone check it! http://discocl.com/ nitro!"
	)
	assert not misc.scamCheck(
		"Hey Discord friends, check out https://top.gg/bot/" + str(misc.BbId)
	)
	assert not misc.scamCheck(
		"Here's an actual gift link https://discord.gift/s23d35fls55d13l1fjds"
	)


# TODO: cmdSearch with mock context, add test for error with quotation marks
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
	sleep(0.4)


@pytest.mark.parametrize(
	("searchterm", "title"), [("", "Google"), (" ", "- Google Search")]
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
async def test_moose_failed_connection_raises_AnimalException(
	httpx_mock: HTTPXMock
) -> None:
	httpx_mock.add_response(
		url="https://github.com/LevBernstein/moosePictures/",
		status_code=522
	)
	with pytest.raises(
		misc.AnimalException, match="Failed to call Moose Animal API"
	):
		await misc.getMoose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
	"animalName", misc.AnimalList
)
async def test_getAnimal_with_goodUrl(animalName: str) -> None:
	url = await misc.getAnimal(animalName)
	async with httpx.AsyncClient(timeout=10) as client:
		response = await client.get(url)
	assert validImageUrl(response)


@pytest.mark.asyncio
async def test_dog_with_goodUrl() -> None:
	url = await misc.getDog()
	async with httpx.AsyncClient(timeout=10) as client:
		response = await client.get(url)
	assert validImageUrl(response)

	url = await misc.getMoose()
	async with httpx.AsyncClient(timeout=10) as client:
		response = await client.get(url)
	assert validImageUrl(response)


@pytest.mark.asyncio
async def test_dog_breed() -> None:
	msg = await misc.getDog("breeds")
	breeds = msg[12:-1].split(", ")
	assert len(breeds) == 107
	url = await misc.getDog(breeds[0])
	assert "affenpinscher" in url
	async with httpx.AsyncClient(timeout=10) as client:
		response = await client.get(url)
	assert validImageUrl(response)

	msg = await misc.getDog("invalidbreed")
	assert msg.startswith("Breed not")

	msg = await misc.getDog("invalidbreed1234")
	assert msg.startswith("Breed not")

	url = await misc.getDog("moose")
	async with httpx.AsyncClient(timeout=10) as client:
		response = await client.get(url)
	assert validImageUrl(response)


@pytest.mark.asyncio
async def test_invalid_animal_raises_ValueError() -> None:
	with pytest.raises(ValueError, match="Invalid Animal: invalidAnimal"):
		await misc.getAnimal("invalidAnimal")


@pytest.mark.asyncio
async def test_dog_api_down_raises_AnimalException(
	httpx_mock: HTTPXMock
) -> None:
	httpx_mock.add_response(
		url="https://dog.ceo/api/breeds/image/random",
		status_code=522
	)

	with pytest.raises(
		misc.AnimalException, match="Failed to call Dog Animal API"
	):
		await misc.getDog()


@pytest.mark.asyncio
async def test_animal_api_down_raises_AnimalException(
	httpx_mock: HTTPXMock
) -> None:
	httpx_mock.add_response(
		url="https://random-d.uk/api/quack",
		status_code=522
	)

	with pytest.raises(
		misc.AnimalException, match="Failed to call Duck Animal API"
	):
		await misc.getAnimal("duck")


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
	assert frogs[0] == "0"


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
	assert frogs[0] == "0\\"


@pytest.mark.asyncio
async def test_handleMessages() -> None:
	u = MockMember()
	u._user.bot = True
	m = MockMessage(author=u)
	assert await Bot.handleMessages(m) == 0

	u._user.bot = False
	m.guild = None
	assert await Bot.handleMessages(m) == 0

	u = MockMember()
	m = MockMessage(guild=MockGuild(), author=u)
	u._user.bot = False
	assert await Bot.handleMessages(m) == 1

	u = MockMember(MockUser("bar", uid=999999999))
	infractions = MockChannel(name="infractions")
	ch = MockChannel(name="foo")
	m = MockMessage(
		content="http://dizcort.com free nitro!",
		channel=ch,
		guild=MockGuild(members=[u], channels=[infractions]),
		author=u
	)
	u._user.bot = False
	assert len(u.roles) == 1
	ch.messages = [m]
	msg = await ch.history().next()
	assert msg.content == "http://dizcort.com free nitro!"
	assert len(list(infractions.messages)) == 0

	assert await Bot.handleMessages(m) == -1

	assert len(u.roles) == 2
	assert len(list(ch.messages)) == 1
	msg = await ch.history().next()
	assert msg.content == (
		"**Deleted possible nitro scam link. Alerting mods.**"
	)
	assert ch._state._messages is not None
	assert m not in ch._state._messages
	assert len(list(infractions.messages)) == 1
	msg = await infractions.history().next()
	assert isinstance(msg.content, str)
	assert msg.content.startswith(
		"Deleted possible scam nitro link sent by <@999999999>"
	)


@pytest.mark.asyncio
async def test_cmdGuide() -> None:
	ctx = MockContext(Bot.BeardlessBot, author=MockMember(), guild=MockGuild())
	ctx.message.type = nextcord.MessageType.default
	assert await Bot.cmdGuide(ctx) == 0

	assert ctx.guild is not None
	ctx.guild.id = Bot.EggGuildId
	assert await Bot.cmdGuide(ctx) == 1
	assert (await ctx.history().next()).embeds[0].title == (
		"The Eggsoup Improvement Guide"
	)


@pytest.mark.asyncio
async def test_cmdMute() -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	g = MockGuild()
	ctx = MockContext(
		Bot.BeardlessBot,
		message=MockMessage(content="!mute foo"),
		author=MockMember(adminPowers=True),
		guild=g
	)

	# if the MemberConverter fails
	assert await Bot.cmdMute(ctx, target="foo") == 0

	# if trying to mute the bot
	assert await Bot.cmdMute(ctx, target=f"<@{misc.BbId}>") == 0

	# if no target
	assert await Bot.cmdMute(ctx, target=None) == 0

	# if no perms
	ctx.author = MockMember(adminPowers=False)
	assert await Bot.cmdMute(ctx, target=None) == 0

	# if not in guild
	ctx.guild = None
	assert await Bot.cmdMute(ctx, target="foo") == -1
	# TODO: remaining branches


@pytest.mark.asyncio
async def test_processMuteTarget_converts_target() -> None:
	Bot.BeardlessBot = MockBot(Bot.BeardlessBot)
	g = MockGuild()
	ctx = MockContext(
		Bot.BeardlessBot,
		message=MockMessage(content="!mute foo"),
		author=MockMember(MockUser("foo"), adminPowers=True),
		guild=g
	)
	assert await misc.processMuteTarget(
		ctx, "foo", Bot.BeardlessBot
	) == ctx.author


def test_getLastNumericChar() -> None:
	assert misc.getLastNumericChar("") == 0

	assert misc.getLastNumericChar("a") == 0

	assert misc.getLastNumericChar("5") == 1

	assert misc.getLastNumericChar("134") == 3

	assert misc.getLastNumericChar("5s") == 1

	assert misc.getLastNumericChar("55d") == 2

	assert misc.getLastNumericChar("13h foobar") == 2


def test_processMuteDuration() -> None:
	assert misc.processMuteDuration("43H", "") == ("43 hours", "", 154800.0)

	assert misc.processMuteDuration("15minutes", "") == (
		"15 minutes", "", 900.0
	)

	assert misc.processMuteDuration("24second", "") == (
		"24 seconds", "", 24.0
	)

	assert misc.processMuteDuration("foobar", "") == (None, "foobar", None)

	assert misc.processMuteDuration("being", "annoying") == (
		None, "being annoying", None
	)

	assert misc.processMuteDuration("3d", "being annoying") == (
		"3 days", "being annoying", 259200.0
	)

	assert misc.processMuteDuration("4z", "invalid time") == (
		None, "4z invalid time", None
	)


def test_getTarget() -> None:
	author = MockMember(MockUser("author"))
	ctx = MockContext(Bot.BeardlessBot, author=author, guild=MockGuild())
	target = MockMember(MockUser("foobar"))
	assert misc.getTarget(ctx, "") == author

	assert misc.getTarget(ctx, "foobar") == "foobar"

	ctx.message.mentions = [target, MockMember()]
	assert misc.getTarget(ctx, "") == target


@pytest.mark.asyncio
async def test_thread_creation_does_not_invoke_commands() -> None:
	ctx = MockContext(Bot.BeardlessBot, author=MockMember(), guild=MockGuild())
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


def test_launch_invalid_discord_token_raises_DiscordException(
	caplog: pytest.LogCaptureFixture
) -> None:

	def mock_raise_DiscordException(bot: commands.Bot, token: str) -> None:
		msg = f"Failed launching {bot.command_prefix} bot with token {token}."
		raise nextcord.DiscordException(msg)

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(
			"dotenv.dotenv_values",
			lambda _: {"BRAWLKEY": "foo", "DISCORDTOKEN": "bar"}
		)
		mp.setattr(
			"nextcord.ext.commands.Bot.run",
			mock_raise_DiscordException
		)
		Bot.launch()
	assert caplog.records[0].msg == "Encountered DiscordException!"
	assert caplog.records[0].exc_info is not None
	assert caplog.records[0].exc_info[1] is not None
	assert caplog.records[0].exc_info[1].args[0] == (
		"Failed launching ! bot with token bar."
	)


def test_brawlCommands() -> None:
	assert len(brawl.brawlCommands().fields) == 6


def test_fetchBrawlID() -> None:
	assert brawl.fetchBrawlId(Bot.OwnerId) == OwnerBrawlId
	assert brawl.fetchBrawlId(misc.BbId) is None


def test_claimProfile() -> None:
	with Path("resources/claimedProfs.json").open("r") as f:
		profsLen = len(json.load(f))
	try:
		brawl.claimProfile(Bot.OwnerId, 1)
		with Path("resources/claimedProfs.json").open("r") as f:
			assert profsLen == len(json.load(f))
		assert brawl.fetchBrawlId(Bot.OwnerId) == 1
	finally:
		brawl.claimProfile(Bot.OwnerId, OwnerBrawlId)
		assert brawl.fetchBrawlId(Bot.OwnerId) == OwnerBrawlId


@pytest.mark.asyncio
async def test_brawpApiCall_raises_httpxException_with_bad_status_code(
	httpx_mock: HTTPXMock
) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/search?steamid=1&api_key=foo",
		status_code=400
	)
	with pytest.raises(
		httpx.RequestError, match="Request failed with 400"
	):
		await brawl.brawlApiCall("search?steamid=", "1", "foo", "&")


@pytest.mark.asyncio
async def test_getRank_monkeypatched_for_1s_top_rating(
	httpx_mock: HTTPXMock
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
					"tier": "Gold 3"
				}
			],
			"2v2": []
		}
	)

	try:
		brawl.claimProfile(Bot.OwnerId, 1)
		emb = await brawl.getRank(MockMember(MockUser(uid=Bot.OwnerId)), "foo")
		assert emb.fields[0].name == "Ranked 1s"
		assert emb.fields[0].value == (
			"**Gold 2** (1540/1577 Peak)\n2 W / 1 L / 66.7% winrate"
			"\nTop Legend: Bodvar, 1400 Elo"
		)
		assert hasattr(emb.color, "value")
		assert emb.color.value == brawl.RankColors["Gold"]
	finally:
		brawl.claimProfile(Bot.OwnerId, OwnerBrawlId)


@pytest.mark.asyncio
async def test_getRank_monkeypatched_for_2s_top_rating(
	httpx_mock: HTTPXMock
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
					"peak_rating": 1824,
					"wins": 1,
					"games": 2
				}
			]
		}
	)

	try:
		brawl.claimProfile(Bot.OwnerId, 1)
		emb = await brawl.getRank(MockMember(MockUser(uid=Bot.OwnerId)), "foo")
		assert emb.fields[0].name == "Ranked 2s"
		assert emb.fields[0].value == (
			"**Foo+Bar\nPlatinum 3** (1812 / 1824 Peak)"
			"\n1 W / 1 L / 50.0% winrate"
		)
		assert hasattr(emb.color, "value")
		assert emb.color.value == brawl.RankColors["Platinum"]
	finally:
		brawl.claimProfile(Bot.OwnerId, OwnerBrawlId)


@pytest.mark.asyncio
async def test_getRank_monkeypatched_unplayed(
	httpx_mock: HTTPXMock
) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/ranked?api_key=foo",
		json={"name": "Foo", "region": "us-east-1", "games": 0, "2v2": []}
	)

	try:
		brawl.claimProfile(Bot.OwnerId, 1)
		rank = await brawl.getRank(
			MockMember(MockUser(uid=Bot.OwnerId)), "foo"
		)
		assert rank.footer.text == "Brawl ID 1"
		assert rank.description == (
			"You haven't played ranked yet this season."
		)
	finally:
		brawl.claimProfile(Bot.OwnerId, OwnerBrawlId)


@pytest.mark.asyncio
async def test_getRank_unclaimed() -> None:
	member = MockMember(MockUser(uid=0))
	rank = await brawl.getRank(member, "foo")
	assert rank.description == brawl.UnclaimedMsg.format("<@0>")


@pytest.mark.asyncio
@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
async def test_getBrawlId_returns_None_when_never_played(
	httpx_mock: HTTPXMock
) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/search?steamid=37&api_key=foo", json=[]
	)
	assert await brawl.brawlApiCall("search?steamid=", "37", "foo", "&") == []

	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("steam.steamid.SteamID.from_url", lambda _: "37")
		assert await brawl.getBrawlId("foo", "foo.bar") is None


@pytest.mark.asyncio
async def test_getBrawlId_returns_None_when_id_is_invalid() -> None:
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("steam.steamid.SteamID.from_url", lambda _: None)
		assert await brawl.getBrawlId("foo", "foo.bar") is None


@pytest.mark.asyncio
async def test_getBrawlId(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/search?steamid=1&api_key=foo",
		json={"brawlhalla_id": 2}
	)
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr("steam.steamid.SteamID.from_url", lambda _: "1")
		assert await brawl.getBrawlId("foo", "foo.bar") == 2


@pytest.mark.asyncio
async def test_getClan_unclaimed() -> None:
	member = MockMember(MockUser(uid=0))
	clan = await brawl.getClan(member, "foo")
	assert clan.description == brawl.UnclaimedMsg.format("<@0>")


@pytest.mark.asyncio
async def test_getClan(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/stats?api_key=foo",
		json={"clan": {"clan_id": 2}}
	)
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/clan/2/?api_key=foo",
		json={
			"clan_id": 2,
			"clan_name": "FooBar",
			"clan_create_date": 18000,
			"clan_xp": 1257,
			"clan": [{
				"name": "Spam",
				"rank": "Leader",
				"xp": 1000,
				"join_date": 18000
			}]
		}
	)
	try:
		brawl.claimProfile(Bot.OwnerId, 1)
		clan = await brawl.getClan(
			MockMember(MockUser(uid=Bot.OwnerId)), "foo"
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
		brawl.claimProfile(Bot.OwnerId, OwnerBrawlId)


@pytest.mark.asyncio
async def test_getClan_not_in_a_clan(httpx_mock: HTTPXMock) -> None:
	httpx_mock.add_response(
		url="https://api.brawlhalla.com/player/1/stats?api_key=foo", json={}
	)
	try:
		brawl.claimProfile(Bot.OwnerId, 1)
		clan = await brawl.getClan(
			MockMember(MockUser(uid=Bot.OwnerId)), "foo"
		)
		assert clan.description == "You are not in a clan!"
	finally:
		brawl.claimProfile(Bot.OwnerId, OwnerBrawlId)


# Tests for commands that require a Brawlhalla API key:

if BrawlKey:
	@pytest.mark.asyncio
	async def test_randomBrawl() -> None:
		# TODO: remove randomness
		assert BrawlKey is not None
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

		legend = await brawl.randomBrawl("legend", BrawlKey)
		assert len(legend.fields) == 2
		assert legend.title is not None
		legendInfo = await brawl.legendInfo(
			BrawlKey, legend.title.split(" ")[0].lower().replace(",", "")
		)
		assert legendInfo is not None
		assert legend.title == legendInfo.title

		legend = await brawl.randomBrawl("invalidrandom")
		assert legend.title == "Brawlhalla Randomizer"

	@pytest.mark.asyncio
	async def test_getLegends() -> None:
		# This one should not be mocked; just remove the sleep
		assert BrawlKey is not None
		sleep(5)
		oldLegends = brawl.fetchLegends()
		await brawl.getLegends(BrawlKey)
		assert brawl.fetchLegends() == oldLegends

	@pytest.mark.asyncio
	async def test_legendInfo() -> None:
		assert BrawlKey is not None
		sleep(5)
		legend = await brawl.legendInfo(BrawlKey, "hugin")
		assert legend is not None
		assert legend.title == "Munin, The Raven"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/"
			"2021/12/a_Roster_Pose_BirdBardM.png"
		)

		legend = await brawl.legendInfo(BrawlKey, "teros")
		assert legend is not None
		assert legend.title == "Teros, The Minotaur"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/2021/07/teros.png"
		)

		legend = await brawl.legendInfo(BrawlKey, "redraptor")
		assert legend is not None
		assert legend.title == "Red Raptor, The Last Sentai"
		assert legend.thumbnail.url == (
			"https://cms.brawlhalla.com/c/uploads/"
			"2023/06/a_Roster_Pose_SentaiM.png"
		)

		assert await brawl.legendInfo(BrawlKey, "invalidname") is None

	@pytest.mark.asyncio
	async def test_getStats() -> None:
		assert BrawlKey is not None
		sleep(5)
		member = MockMember(MockUser(uid=0))
		stats = await brawl.getStats(member, BrawlKey)
		assert stats.description == brawl.UnclaimedMsg.format("<@0>")

		member._user.id = Bot.OwnerId
		try:
			brawl.claimProfile(Bot.OwnerId, OwnerBrawlId)
			emb = await brawl.getStats(member, BrawlKey)
			assert emb.footer.text == "Brawl ID " + str(OwnerBrawlId)
			assert len(emb.fields) in {3, 4}

			brawl.claimProfile(Bot.OwnerId, 1247373426)
			emb = await brawl.getStats(member, BrawlKey)
			assert emb.description is not None
			assert emb.description.startswith(
				"This profile doesn't have stats"
			)
		finally:
			brawl.claimProfile(Bot.OwnerId, OwnerBrawlId)
