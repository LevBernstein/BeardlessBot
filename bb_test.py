# Beardless Bot unit tests

import asyncio
from dotenv import dotenv_values
from json import load
from os import environ
from random import choice
from typing import List, Tuple, Union

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


# TODO: add _state attribute to all mock objects


# MockUser class is a superset of discord.User with some features of
# discord.Member; still working on adding all features of discord.Member,
# at which point I will switch the parent from discord.User to discord.Member

class MockUser(discord.User):

	class MockUserState():
		def __init__(self):
			self._guilds = {}
			self.allowed_mentions = discord.AllowedMentions(everyone=True)
			self.loop = asyncio.new_event_loop()
			self.http = discord.http.HTTPClient(loop=self.loop)
			self.user = None

		def _get_private_channel_by_user(self, id):
			return MockChannel()

	def __init__(
		self,
		name: str = "testname",
		nick: str = "testnick",
		discriminator: str = "0000",
		id: int = 123456789,
		roles=()
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
		self._public_flags = 0
		self._state = self.MockUserState()

	def set_state(self):
		self._state.user = self

	def avatar_url_as(self, format=None, size=1024):
		# Discord doesn't like it when you construct its objects manually;
		# the avatar_url field is entirely broken. Here, I overwrite it.
		return "https://cdn.discordapp.com/embed/avatars/0.png"


class MockChannel(discord.TextChannel):
	def __init__(self):
		self.name = "testchannelname"
		self.id = 123456789
		self.position = 0
		self.slowmode_delay = 0
		self.nsfw = False
		self._type = 0
		self.category_id = 0
		self.guild = None


class MockMessage(discord.Message):
	def __init__(
		self,
		content: str = "testcontent",
		author: discord.User = MockUser(),
		guild: Union[discord.Guild, None] = None
	):
		self.author = author
		self.content = content
		self.id = 123456789
		self.channel = MockChannel()
		self.type = discord.MessageType.default
		self.flags = discord.MessageFlags(
			crossposted=False,
			is_crossposted=False,
			suppress_embeds=False,
			source_message_deleted=False,
			urgent=False
		)
		self.guild = guild
		self.mentions = ()
		self.mention_everyone = False


class MockRole(discord.Role):
	def __init__(
		self,
		name: str = "Test Role",
		id: int = 123456789
	):
		self.name = name
		self.id = id
		self.hoist = False
		self.mentionable = True


class MockGuild(discord.Guild):

	class FlagWrapper():
		class FlagValues():
			def __init__(self):
				self.joined = True
				self.online = True
				self.voice = True

		def __init__(self):
			self.member_cache_flags = self.FlagValues()
			self.self_id = 1
			self.shard_count = 1

	def __init__(
		self,
		members: List[discord.User] = [MockUser(), MockUser()],
		numMembers: int = 1,
		name: str = "Test Guild",
		id: int = 0,
		channels: List[discord.TextChannel] = [MockChannel()],
		roles: List[discord.Role] = [MockRole()]
	):
		self.name = name
		self.id = id
		self._state = self.FlagWrapper()
		self._channels = {i: c for i, c in enumerate(channels)}
		self._roles = {i: r for i, r in enumerate(roles)}
		self._members = {i: m for i, m in enumerate(members)}
		self._member_count = len(self._members)
		self.owner_id = 123456789


class MockContext(commands.Context):
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
		message.state = 0
		self.message = message
		self.channel = channel
		self.author = author
		self.guild = guild


brawlKey = environ.get("BRAWLKEY")
if not brawlKey:
	env = dotenv_values(".env")
	brawlKey = env["BRAWLKEY"]
if not brawlKey:
	print("No Brawlhalla API key. Brawlhalla-specific tests will fail.\n")


def test_pep8Compliance():
	styleGuide = flake8.get_style_guide(ignore=["W191", "W504", "W503"])
	report = styleGuide.check_files(["./"])
	assert len(report.get_statistics("W")) == 0
	assert len(report.get_statistics("E")) == 0
	assert len(report.get_statistics("F")) == 0


def test_bot():
	assert Bot.bot.command_prefix == "!"
	assert Bot.bot.case_insensitive is True
	assert Bot.bot.help_command is None
	assert Bot.bot.intents == discord.Intents.all()


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
		sideRoll = misc.roll(message)
		assert 1 <= sideRoll and sideRoll <= sideNum
		assert (
			misc.rollReport(message, user).description.startswith("You got")
		)
	sideRoll = misc.roll("d20-4")
	assert -3 <= sideRoll and sideRoll <= 16
	assert misc.rollReport("d20-4", user).description.startswith("You got")
	assert not misc.roll("d9")
	assert not misc.roll("wrongroll")
	assert misc.rollReport("d9", user).description.startswith("Invalid")


def test_logDeleteMsg():
	msg = MockMessage()
	assert (
		logs.logDeleteMsg(msg).description ==
		f"**Deleted message sent by {msg.author.mention}"
		f" in **{msg.channel.mention}\n{msg.content}"
	)


def test_logPurge():
	msg = MockMessage()
	assert (
		logs.logPurge(msg, (msg, msg, msg)).description ==
		f"Purged 2 messages in {msg.channel.mention}."
	)
	assert (
		logs.logPurge(msg, (msg,) * 105).description ==
		f"Purged 99+ messages in {msg.channel.mention}."
	)


def test_logEditMsg():
	before = MockMessage("oldcontent")
	after = MockMessage("newcontent")
	emb = logs.logEditMsg(before, after)
	assert (
		emb.description ==
		f"Messaged edited by {after.author.mention}"
		f" in {after.channel.mention}."
	)
	assert emb.fields[0].value == before.content
	assert (
		emb.fields[1].value ==
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


def test_logDeleteChannel():
	channel = MockChannel()
	assert (
		logs.logDeleteChannel(channel).description ==
		f"Channel \"{channel.name}\" deleted."
	)


def test_logCreateChannel():
	channel = MockChannel()
	assert (
		logs.logCreateChannel(channel).description ==
		f"Channel \"{channel.name}\" created."
	)


def test_logMemberJoin():
	member = MockUser()
	assert (
		logs.logMemberJoin(member).description ==
		f"Member {member.mention} joined\nAccount registered"
		f" on {misc.truncTime(member)}\nID: {member.id}"
	)


def test_logMemberRemove():
	member = MockUser()
	assert (
		logs.logMemberRemove(member).description ==
		f"Member {member.mention} left\nID: {member.id}"
	)
	member.roles = MockRole(), MockRole()
	assert (
		logs.logMemberRemove(member).fields[0].value ==
		member.roles[1].mention
	)


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
	assert (
		logs.logMemberRolesChange(before, after).description ==
		f"Role {after.roles[0].mention} added to {after.mention}."
	)
	assert (
		logs.logMemberRolesChange(after, before).description ==
		f"Role {after.roles[0].mention} removed from {before.mention}."
	)


def test_logBan():
	member = MockUser()
	assert (
		logs.logBan(member).description ==
		f"Member {member.mention} banned\n{member.name}"
	)


def test_logUnban():
	member = MockUser()
	assert (
		logs.logUnban(member).description ==
		f"Member {member.mention} unbanned\n{member.name}"
	)


def test_logMute():
	message = MockMessage()
	member = MockUser()
	assert (
		logs.logMute(member, message, "5", "hours", 18000).description ==
		f"Muted {member.mention} for 5 hours in {message.channel.mention}."
	)
	assert (
		logs.logMute(member, message, None, None, None).description ==
		f"Muted {member.mention} in {message.channel.mention}."
	)


def test_logUnmute():
	member = MockUser()
	assert (
		logs.logUnmute(member, MockUser()).description ==
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
	assert (
		bucks.register(bb).description ==
		"You are already in the system! Hooray! You"
		f" have 200 BeardlessBucks, {bb.mention}."
	)
	bb.name = ",badname,"
	assert (
		bucks.register(bb).description == bucks.commaWarn.format(bb.mention)
	)


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
	assert (
		bucks.balance(auth, text).description ==
		f"{auth.mention}'s balance is 200 BeardlessBucks."
	)
	text.content = "!balance " + auth.name
	assert (
		bucks.balance(auth, text).description ==
		f"{auth.mention}'s balance is 200 BeardlessBucks."
	)
	text.content = "!balance"
	text.author.name = ",badname,"
	assert (
		bucks.balance(text.author, text).description ==
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
	assert (
		bucks.reset(bb).description ==
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
	assert (
		game.startingHand(False, True)
		.startswith("Your starting hand consists of two Aces.")
	)


def test_info():
	namedUser = MockUser("searchterm", roles=(MockRole(), MockRole()))
	guild = MockGuild(members=(MockUser(), namedUser))
	text = MockMessage("!info searchterm", guild=guild)
	namedUserInfo = misc.info("searchterm", text)
	assert namedUserInfo.fields[0].value == misc.truncTime(namedUser) + " UTC"
	assert namedUserInfo.fields[1].value == misc.truncTime(namedUser) + " UTC"
	assert namedUserInfo.fields[2].value == MockRole().mention
	assert misc.info("!infoerror", text).title == "Invalid target!"


def test_av():
	namedUser = MockUser("searchterm")
	guild = MockGuild(members=(MockUser(), namedUser))
	text = MockMessage("!av searchterm", guild=guild)
	assert misc.av("searchterm", text).image.url == namedUser.avatar_url
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
	guild = discord.Guild
	guild.name = "Test Guild"
	role = MockRole(id=0)
	guild.roles = role,
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
	assert (
		brawl.getRank(user, brawlKey).description ==
		brawl.unclaimed.format(user.mention)
	)
	user.id = 743238109898211389
	assert (
		brawl.getRank(user, brawlKey).footer.text ==
		"Brawl ID 12502880"
	)
	user.id = 196354892208537600
	assert (
		brawl.getRank(user, brawlKey).description ==
		"You haven't played ranked yet this season."
	)


def test_getStats():
	user = MockUser(id=0)
	assert (
		brawl.getStats(user, brawlKey).description ==
		brawl.unclaimed.format(user.mention)
	)
	user.id = 196354892208537600
	emb = brawl.getStats(user, brawlKey)
	assert emb.footer.text == "Brawl ID 7032472"
	assert len(emb.fields) in (3, 4)


def test_getClan():
	user = MockUser(id=0)
	assert (
		brawl.getClan(user, brawlKey).description ==
		brawl.unclaimed.format(user.mention)
	)
	user.id = 196354892208537600
	assert brawl.getClan(user, brawlKey).title == "DinersDriveInsDives"
	brawl.claimProfile(196354892208537600, 5895238)
	assert (
		brawl.getClan(user, brawlKey).description ==
		"You are not in a clan!"
	)
	brawl.claimProfile(196354892208537600, 7032472)


def test_brawlCommands():
	assert len(brawl.brawlCommands().fields) == 6
