# Beardless Bot unit tests

import asyncio
from dotenv import dotenv_values
from json import load
from os import environ
from random import choice
from typing import Any, Dict, List, Tuple, Union

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


# TODO: add _state attribute to all mock objects, inherit from State
# Switch to a single MockState class for all Messageable objects


class MockHTTPClient(discord.http.HTTPClient):
	def __init__(
		self,
		loop: asyncio.AbstractEventLoop,
		user: Union[discord.User, None] = None
	):
		self.loop = loop
		self.user_agent = user
		self.token = None
		self.proxy = None
		self.proxy_auth = None
		self._locks = {}

	async def create_role(
		self, roleId: int, reason: Union[str, None] = None, **fields: Any
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
		content: Union[str, None] = None,
		*,
		tts: bool = False,
		embed: Union[discord.Embed, None] = None,
		embeds: Union[List[discord.Embed], None] = None,
		nonce: Union[str, None] = None,
		allowed_mentions: Union[Dict[str, Any], None] = None,
		message_reference: Union[Dict[str, Any], None] = None,
		stickers: Union[List[discord.Sticker], None] = None,
		components: Union[List[Any], None] = None
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
		def __init__(self, messageNum: int = 0):
			self._guilds = {}
			self.allowed_mentions = discord.AllowedMentions(everyone=True)
			self.loop = asyncio.new_event_loop()
			self.http = MockHTTPClient(self.loop)
			self.user = None
			self.last_message_id = messageNum
			self.channel = MockChannel()

		def create_message(
			self, *, channel: discord.abc.Messageable, data: Dict
		) -> discord.Message:
			data["id"] = self.last_message_id
			self.last_message_id += 1
			return discord.Message(state=self, channel=channel, data=data)

		def store_user(self, data: Dict) -> discord.User:
			return MockUser()

		def setClientUser(self):
			self.http.user_agent = self.user

		def _get_private_channel_by_user(self, id: int):
			return self.channel

	def __init__(
		self,
		name: str = "testname",
		nick: str = "testnick",
		discriminator: str = "0000",
		id: int = 123456789,
		roles: List[discord.Role] = []
	):
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
		self._public_flags = 0
		self._state = self.MockUserState(messageNum=len(self.messages))

	def setStateUser(self):
		self._state.user = self
		self._state.setClientUser()


# TODO: edit Messageable.send() to add messages to self.messages
class MockChannel(discord.TextChannel):

	class MockChannelState():
		def __init__(
			self, user: Union[discord.User, None] = None, messageNum: int = 0
		):
			self.loop = asyncio.new_event_loop()
			self.http = MockHTTPClient(self.loop, user)
			self.allowed_mentions = discord.AllowedMentions(everyone=True)
			self.user = user
			self.last_message_id = messageNum

		def create_message(
			self, *, channel: discord.abc.Messageable, data: Dict
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
		):
			self.id = id
			self.type = type
			self.allow = allow
			self.deny = deny

	def __init__(
		self,
		name: str = "testchannelname",
		guild: Union[discord.Guild, None] = None,
		messages: List[discord.Message] = []
	):
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
		reason: Union[str, None] = None
	):
		pair = overwrite.pair()
		self._overwrites.append(
			self.Mock_Overwrites(
				target.id,
				0 if isinstance(target, discord.Role) else 1,
				pair[0].value,
				pair[1].value
			)
		)

	def history(self):
		# TODO: make self.send() add message to self.messages
		return list(reversed(self.messages))


# TODO: Write message.edit(), message.delete()
class MockMessage(discord.Message):
	def __init__(
		self,
		content: str = "testcontent",
		author: discord.User = MockUser(),
		guild: Union[discord.Guild, None] = None,
		channel: discord.TextChannel = MockChannel()
	):
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
	):
		self.name = name
		self.id = id
		self.hoist = False
		self.mentionable = True
		self._permissions = (
			permissions if isinstance(permissions, int) else permissions.value
		)


class MockGuild(discord.Guild):

	class MockGuildState():
		def __init__(self):
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
	):
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
			user: Union[discord.User, None] = None,
			channel: discord.TextChannel = MockChannel()
		):
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
		guild: Union[discord.Guild, None] = MockGuild()
	):
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

		def __init__(self, bot: commands.Bot):
			self.bot = bot

		async def change_presence(
			self,
			*,
			activity: Union[discord.Activity, None] = None,
			status: Union[str, None] = None,
			afk: bool = False
		):
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

		async def send(self, data: Dict[str, any], /):
			self.bot.status = data["d"]["status"]
			self.bot.activity = data["d"]["activities"][0]
			return data

	class MockClientUser(discord.ClientUser):
		def __init__(self, bot: commands.Bot):
			baseUser = MockUser()
			self._state = baseUser._state
			self.id = 0
			self.name = "testclientuser"
			self.discriminator = "0000"
			self.avatar = baseUser.avatar
			self.bot = bot
			self.verified = True
			self.mfa_enabled = False

		async def edit(self, avatar: str):
			self.avatar = avatar

	def __init__(self, bot: commands.Bot):
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


def test_pep8Compliance():
	styleGuide = flake8.get_style_guide(ignore=["W191"])
	report = styleGuide.check_files(["./"])
	assert len(report.get_statistics("W")) == 0
	assert len(report.get_statistics("E")) == 0
	assert len(report.get_statistics("F")) == 0


def test_mockContextChannels():
	ctx = MockContext(
		Bot.bot, channel=MockChannel(), guild=MockGuild(channels=[])
	)
	assert ctx.channel in ctx.guild.channels


def test_mockContextMembers():
	ctx = MockContext(Bot.bot, author=MockUser(), guild=MockGuild(members=[]))
	assert ctx.author in ctx.guild.members


def test_createMutedRole():
	g = MockGuild(roles=[])
	role = asyncio.run(Bot.createMutedRole(g))
	assert role.name == "Muted"
	assert len(g.roles) == 1 and g.roles[0] == role


def test_on_ready():
	Bot.bot = MockBot(Bot.bot)
	asyncio.run(Bot.on_ready())
	assert Bot.bot.activity.name == "try !blackjack and !flip"
	assert Bot.bot.status == "online"
	with open("resources/images/prof.png", "rb") as f:
		assert Bot.bot.user.avatar == f.read()


def test_on_message_delete():
	m = MockMessage(channel=MockChannel(name="bb-log"))
	m.guild = MockGuild(channels=[m.channel])
	emb = asyncio.run(Bot.on_message_delete(m))
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


def test_on_bulk_message_delete():
	m = MockMessage(channel=MockChannel(name="bb-log"))
	m.guild = MockGuild(channels=[m.channel])
	messages = [m, m, m]
	emb = asyncio.run(Bot.on_bulk_message_delete(messages))
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
	emb = asyncio.run(Bot.on_bulk_message_delete(messages))
	log = logs.logPurge(messages[0], messages)
	assert emb.description == log.description
	assert log.description == f"Purged 99+ messages in {m.channel.mention}."


def test_on_guild_channel_delete():
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	channel = MockChannel(guild=g)
	emb = asyncio.run(Bot.on_guild_channel_delete(channel))
	log = logs.logDeleteChannel(channel)
	assert emb.description == log.description
	assert log.description == f"Channel \"{channel.name}\" deleted."
	"""
	# TODO: append sent messages to channel.messages
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	"""


def test_on_guild_channel_create():
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	channel = MockChannel(guild=g)
	emb = asyncio.run(Bot.on_guild_channel_create(channel))
	log = logs.logCreateChannel(channel)
	assert emb.description == log.description
	assert log.description == f"Channel \"{channel.name}\" created."
	"""
	# TODO: append sent messages to channel.messages
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	"""


def test_on_member_ban():
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	member = MockUser()
	emb = asyncio.run(Bot.on_member_ban(g, member))
	log = logs.logBan(member)
	assert emb.description == log.description
	assert log.description == f"Member {member.mention} banned\n{member.name}"
	"""
	# TODO: append sent messages to channel.messages
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	"""


def test_on_member_unban():
	g = MockGuild(channels=[MockChannel(name="bb-log")])
	member = MockUser()
	emb = asyncio.run(Bot.on_member_unban(g, member))
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


def test_on_member_join():
	member = MockUser()
	member.guild = MockGuild(channels=[MockChannel(name="bb-log")])
	emb = asyncio.run(Bot.on_member_join(member))
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


def test_on_member_remove():
	member = MockUser()
	member.guild = MockGuild(channels=[MockChannel(name="bb-log")])
	emb = asyncio.run(Bot.on_member_remove(member))
	log = logs.logMemberRemove(member)
	assert emb.description == log.description
	assert log.description == f"Member {member.mention} left\nID: {member.id}"
	member.roles = [MockRole(), MockRole()]
	emb = asyncio.run(Bot.on_member_remove(member))
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


"""
def test_on_message_edit():
	member = MockUser()
	g = MockGuild(
		channels=[MockChannel(name="bb-log"), MockChannel(name="infractions")]
	)
	asyncio.run(Bot.createMutedRole(g))
	before = MockMessage(content="old", author=member, guild=g)
	after = MockMessage(content="new", author=member, guild=g)
	# TODO: write discord.Message.delete(). Requires _state for discord.Message
	emb = asyncio.run(Bot.on_message_edit(before, after)
	log = logs.logEditMsg(before, after)
	assert emb.description == log.description
	# Insert content of test_logEditMsg
	'''
	# TODO: append sent messages to channel.messages, user.messages
	channel = member.guild.channels[0]
	assert any(
		(i.embed.description == log.description for i in channel.history())
	)
	'''
"""


# TODO: now that mock context has state, write tests for other Bot methods


def test_fact():
	with open("resources/facts.txt", "r") as f:
		lines = f.read().splitlines()
	assert misc.fact() in lines


def test_tweet():
	eggTweet = misc.tweet()
	assert ("\n" + eggTweet).startswith(misc.formattedTweet(eggTweet))
	assert "." not in misc.formattedTweet("test tweet.")
	assert "." not in misc.formattedTweet("test tweet")
	eggTweet = eggTweet.split(" ")
	assert len(eggTweet) >= 11 and len(eggTweet) <= 37


def test_dice():
	user = MockUser()
	for sideNum in 4, 6, 8, 100, 10, 12, 20:
		message = "d" + str(sideNum)
		assert misc.roll(message) in range(1, sideNum + 1)
		assert (
			misc.rollReport(message, user).description.startswith("You got")
		)
	assert misc.roll("d20-4") in range(-3, 17)
	assert misc.rollReport("d20-4", user).description.startswith("You got")
	assert not misc.roll("d9")
	assert not misc.roll("wrongroll")
	assert misc.rollReport("d9", user).description.startswith("Invalid")


def test_logEditMsg():
	g = MockGuild()
	before = asyncio.run(g.channels[0].send("oldcontent"))
	after = asyncio.run(g.channels[0].send("newcontent"))
	emb = logs.logEditMsg(before, after)
	assert emb.description == (
		f"Messaged edited by {after.author.mention}"
		f" in {after.channel.mention}."
	)
	assert emb.fields[0].value == before.content
	assert emb.fields[1].value == (
		f"{after.content}\n[Jump to Message]({after.jump_url})"
	)


def test_logClearReacts():
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


def test_logMemberNickChange():
	before = MockUser()
	after = MockUser("testuser", "newnick")
	emb = logs.logMemberNickChange(before, after)
	assert emb.description == "Nickname of " + after.mention + " changed."
	assert emb.fields[0].value == before.nick
	assert emb.fields[1].value == after.nick


def test_logMemberRolesChange():
	before = MockUser()
	after = MockUser(roles=(MockRole(),))
	assert logs.logMemberRolesChange(before, after).description == (
		f"Role {after.roles[0].mention} added to {after.mention}."
	)
	assert logs.logMemberRolesChange(after, before).description == (
		f"Role {after.roles[0].mention} removed from {before.mention}."
	)


def test_logMute():
	message = MockMessage()
	member = MockUser()
	assert logs.logMute(member, message, "5", "hours", 18000).description == (
		f"Muted {member.mention} for 5 hours in {message.channel.mention}."
	)
	assert logs.logMute(member, message, None, None, None).description == (
		f"Muted {member.mention} in {message.channel.mention}."
	)


def test_logUnmute():
	member = MockUser()
	assert logs.logUnmute(member, MockUser()).description == (
		f"Unmuted {member.mention}."
	)


def test_memSearch():
	namedUser = MockUser("searchterm", "testnick", "9999")
	contentList = "searchterm#9999", "searchterm", "search", "testnick"
	text = MockMessage(guild=MockGuild(members=(MockUser(), namedUser)))
	for content in contentList:
		text.content = content
		assert misc.memSearch(text, content) == namedUser
	namedUser.name = "hash#name"
	text.content = "hash#name"
	assert misc.memSearch(text, text.content) == namedUser
	text.content = "invalidterm"
	assert not misc.memSearch(text, text.content)


def test_register():
	bb = MockUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	bucks.reset(bb)
	assert bucks.register(bb).description == (
		"You are already in the system! Hooray! You"
		f" have 200 BeardlessBucks, {bb.mention}."
	)
	bb.name = ",badname,"
	assert bucks.register(bb).description == bucks.commaWarn.format(bb.mention)


def test_balance():
	auth = MockUser(
		"Beardless Bot",
		"Beardless Bot",
		5757,
		654133911558946837
	)
	text = MockMessage(
		"!bal",
		auth,
		MockGuild(members=(MockUser(), auth))
	)
	assert bucks.balance(auth, text).description == (
		f"{auth.mention}'s balance is 200 BeardlessBucks."
	)
	text.content = "!balance " + auth.name
	assert bucks.balance(auth, text).description == (
		f"{auth.mention}'s balance is 200 BeardlessBucks."
	)
	text.content = "!balance"
	text.author.name = ",badname,"
	assert bucks.balance(text.author, text).description == (
		bucks.commaWarn.format(text.author.mention)
	)
	text.content = "!balance invaliduser"
	assert (
		bucks.balance("badtarget", text)
		.description
		.startswith("Invalid user!")
	)


def test_reset():
	bb = MockUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	assert bucks.reset(bb).description == (
		f"You have been reset to 200 BeardlessBucks, {bb.mention}."
	)
	bb.name = ",badname,"
	assert bucks.reset(bb).description == bucks.commaWarn.format(bb.mention)


def test_writeMoney():
	bb = MockUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	bucks.reset(bb)
	assert bucks.writeMoney(bb, "-all", False, False) == (0, 200)
	assert bucks.writeMoney(bb, -1000000, True, False) == (-2, None)


def test_leaderboard():
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


def test_define():
	word = misc.define("test")
	assert word.title == "TEST" and word.description.startswith("Audio: ")
	word = misc.define("pgp")
	assert word.title == "PGP" and word.description == ""
	assert misc.define("invalidword").description == "Invalid word!"


def test_flip():
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


def test_blackjack():
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


def test_blackjack_perfect():
	game = bucks.Instance(MockUser(), 10)
	game.cards = 10, 11
	assert game.perfect()


def test_blackjack_deal():
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


def test_blackjack_cardName():
	game = bucks.Instance(MockUser(), 10)
	assert game.cardName(10) in ("a 10", "a Jack", "a Queen", "a King")
	assert game.cardName(11) == "an Ace"
	assert game.cardName(8) == "an 8"
	assert game.cardName(5) == "a 5"


def test_blackjack_checkBust():
	game = bucks.Instance(MockUser(), 10)
	game.cards = 10, 10, 10
	assert game.checkBust()


def test_blackjack_stay():
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


def test_blackjack_startingHand():
	game = bucks.Instance(MockUser(), 10)
	game.cards = []
	game.message = game.startingHand()
	assert len(game.cards) == 2
	assert game.message.startswith("Your starting hand consists of ")
	assert "You hit 21!" in game.startingHand(True)
	assert "two Aces" in game.startingHand(False, True)


def test_activeGame():
	author = MockUser(name="target", id=0)
	games = [bucks.Instance(MockUser(name="not", id=1), 10)] * 9
	assert not bucks.activeGame(games, author)
	games.append(bucks.Instance(author, 10))
	assert bucks.activeGame(games, author)


def test_info():
	namedUser = MockUser("searchterm", roles=[MockRole(), MockRole()])
	guild = MockGuild(members=[MockUser(), namedUser])
	text = MockMessage("!info searchterm", guild=guild)
	namedUserInfo = misc.info("searchterm", text)
	assert namedUserInfo.fields[0].value == misc.truncTime(namedUser) + " UTC"
	assert namedUserInfo.fields[1].value == misc.truncTime(namedUser) + " UTC"
	assert namedUserInfo.fields[2].value == namedUser.roles[1].mention
	assert misc.info("!infoerror", text).title == "Invalid target!"


def test_av():
	namedUser = MockUser("searchterm")
	guild = MockGuild(members=[MockUser(), namedUser])
	text = MockMessage("!av searchterm", guild=guild)
	assert misc.av("searchterm", text).image.url == str(namedUser.avatar_url)
	assert misc.av("error", text).title == "Invalid target!"


def test_commands():
	ctx = MockContext(Bot.bot, guild=None)
	assert len(misc.bbCommands(ctx).fields) == 15
	ctx.guild = MockGuild()
	ctx.author.guild_permissions = discord.Permissions(manage_messages=True)
	assert len(misc.bbCommands(ctx).fields) == 20
	ctx.author.guild_permissions = discord.Permissions(manage_messages=False)
	assert len(misc.bbCommands(ctx).fields) == 17


def test_hints():
	with open("resources/hints.txt", "r") as f:
		assert len(misc.hints().fields) == len(f.read().splitlines())


def test_pingMsg():
	namedUser = MockUser("likesToPing")
	assert (
		brawl.pingMsg(namedUser.mention, 1, 1, 1)
		.endswith("You can ping again in 1 hour, 1 minute, and 1 second.")
	)
	assert (
		brawl.pingMsg(namedUser.mention, 2, 2, 2)
		.endswith("You can ping again in 2 hours, 2 minutes, and 2 seconds.")
	)


def test_scamCheck():
	assert misc.scamCheck("http://dizcort.com free nitro!")
	assert misc.scamCheck("@everyone http://didcord.gg free nitro!")
	assert misc.scamCheck("gift nitro http://d1zcordn1tr0.co.uk free!")
	assert not misc.scamCheck(
		"Hey Discord friends, check out https://top.gg/bot/654133911558946837"
	)


def test_onJoin():
	role = MockRole(id=0)
	guild = MockGuild(name="Test Guild", roles=[role])
	assert misc.onJoin(guild, role).title == "Hello, Test Guild!"


def test_animal():

	def goodURL(
		request: requests.models.Response, fileTypes: Tuple[str]
	) -> bool:
		return request.ok and request.headers["content-type"] in imageTypes

	imageTypes = (
		"image/png",
		"image/jpeg",
		"image/jpg",
		"image/gif",
		"image/webp"
	)
	imageSigs = (
		"b'\\xff\\xd8\\xff\\xe0\\x00\\x10JFIF",
		"b'\\x89\\x50\\x4e\\x47\\x0d\\x",
		"b'\\xff\\xd8\\xff\\xe2\\x024ICC_PRO",
		"b'\\x89PNG\\r\\n\\x1a\\n\\",
		"b'\\xff\\xd8\\xff\\xe1\\tPh"
	)
	for animalName in misc.animalList[:-4]:
		assert goodURL(requests.get(misc.animal(animalName)), imageTypes)

	for animalName in misc.animalList[-4:]:
		# Koala, Bird, Raccoon, Kangaroo APIs lack a content-type field;
		# check if URL points to an image instead
		r = requests.get(misc.animal(animalName))
		assert r.ok and any(
			str(r.content).startswith(signature) for signature in imageSigs
		)

	assert goodURL(requests.get(misc.animal("dog")), imageTypes)

	breeds = misc.animal("dog", "breeds")[12:-1].split(", ")
	assert len(breeds) >= 94
	r = requests.get(misc.animal("dog", choice(breeds)))
	assert goodURL(r, imageTypes)
	assert misc.animal("dog", "invalidbreed").startswith("Breed not")
	assert misc.animal("dog", "invalidbreed1234").startswith("Breed not")

	assert goodURL(requests.get(misc.animal("dog", "moose")), imageTypes)

	with pytest.raises(Exception):
		misc.animal("invalidAnimal")


# Tests for commands that require a Brawlhalla API key:


def test_randomBrawl():
	assert brawl.randomBrawl("weapon").title == "Random Weapon"
	assert brawl.randomBrawl("legend").title == "Random Legend"
	assert len(brawl.randomBrawl("legend", brawlKey).fields) == 2
	assert brawl.randomBrawl("invalidrandom").title == "Brawlhalla Randomizer"
	assert brawl.randomBrawl("invalidrandom").title == "Brawlhalla Randomizer"


def test_fetchBrawlID():
	assert brawl.fetchBrawlID(196354892208537600) == 7032472
	assert not brawl.fetchBrawlID(654133911558946837)


def test_claimProfile():
	with open("resources/claimedProfs.json", "r") as f:
		profsLen = len(load(f))
	brawl.claimProfile(196354892208537600, 1)
	with open("resources/claimedProfs.json", "r") as f:
		assert profsLen == len(load(f))
	assert brawl.fetchBrawlID(196354892208537600) == 1
	brawl.claimProfile(196354892208537600, 7032472)
	assert brawl.fetchBrawlID(196354892208537600) == 7032472


def test_fetchLegends():
	assert len(brawl.fetchLegends()) == 54


def test_getBrawlID():
	assert brawl.getBrawlID(
		brawlKey, "https://steamcommunity.com/id/beardless"
	) == 7032472
	assert not brawl.getBrawlID(brawlKey, "badurl")
	assert not brawl.getBrawlID(
		brawlKey, "https://steamcommunity.com/badurl"
	)
	assert not brawl.getBrawlID(
		brawlKey, "https://steamcommunity.com/id/dksjnw"
	)


def test_getLegends():
	oldLegends = brawl.fetchLegends()
	brawl.getLegends(brawlKey)
	assert brawl.fetchLegends() == oldLegends


def test_legendInfo():
	assert brawl.legendInfo(brawlKey, "hugin").title == "Munin, The Raven"
	assert brawl.legendInfo(brawlKey, "teros").title == "Teros, The Minotaur"
	assert not brawl.legendInfo(brawlKey, "invalidname")


def test_getRank():
	user = MockUser(id=0)
	assert brawl.getRank(user, brawlKey).description == (
		brawl.unclaimed.format(user.mention)
	)
	user.id = 743238109898211389
	assert brawl.getRank(user, brawlKey).footer.text == "Brawl ID 12502880"
	user.id = 196354892208537600
	assert brawl.getRank(user, brawlKey).description == (
		"You haven't played ranked yet this season."
	)


def test_getStats():
	user = MockUser(id=0)
	assert brawl.getStats(user, brawlKey).description == (
		brawl.unclaimed.format(user.mention)
	)
	user.id = 196354892208537600
	emb = brawl.getStats(user, brawlKey)
	assert emb.footer.text == "Brawl ID 7032472"
	assert len(emb.fields) in (3, 4)


def test_getClan():
	user = MockUser(id=0)
	assert brawl.getClan(user, brawlKey).description == (
		brawl.unclaimed.format(user.mention)
	)
	user.id = 196354892208537600
	assert brawl.getClan(user, brawlKey).title == "DinersDriveInsDives"
	brawl.claimProfile(196354892208537600, 5895238)
	assert brawl.getClan(user, brawlKey).description == (
		"You are not in a clan!"
	)
	brawl.claimProfile(196354892208537600, 7032472)


def test_brawlCommands():
	assert len(brawl.brawlCommands().fields) == 6
