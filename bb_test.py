# Beardless Bot unit tests

from json import load

import discord
import pytest
import requests

import Bot
import brawl
import bucks
import logs
import misc


class TestUser(discord.User):
	def __init__(
		self,
		name: str = "testname",
		nick: str = "testnick",
		discriminator: str = "0000",
		id: int = 123456789
	):
		self.name = name
		self.nick = nick
		self.id = id
		self.discriminator = discriminator
		self.bot = False
		self.avatar = self.default_avatar
		self.roles = ()
		self.joined_at = self.created_at
		self.activity = None

	def avatar_url_as(self, format=None, size=1024):
		# Discord doesn't like it when you construct its objects manually;
		# the avatar_url field is entirely broken. Here, I overwrite it.
		return "https://cdn.discordapp.com/embed/avatars/0.png"


class TestChannel(discord.TextChannel):
	def __init__(self):
		self.name = "testchannelname"
		self.guild = discord.Guild
		self.id = 123456789
		self.position = 0
		self.slowmode_delay = 0
		self.nsfw = False
		self._type = 0
		self.category_id = 0


class TestMessage(discord.Message):
	def __init__(
		self,
		content: str = "testcontent",
		author: discord.User = TestUser()
	):
		self.author = author
		self.content = content
		self.id = 123456789
		self.channel = TestChannel()
		self.type = discord.MessageType.default
		self.flags = discord.MessageFlags(
			crossposted=False,
			is_crossposted=False,
			suppress_embeds=False,
			source_message_deleted=False,
			urgent=False
		)
		self.mentions = ()


try:
	with open("resources/brawlhallaKey.txt", "r") as f:
		# In brawlhallaKey.txt, paste in your own Brawlhalla API key
		brawlKey = f.readline()
except Exception as err:
	print(
		"No Brawlhalla API key.",
		"Brawlhalla-specific tests will not fire.\n",
		err
	)
	brawlKey = None


def test_bot():
	assert Bot.bot.command_prefix == "!"
	assert Bot.bot.case_insensitive == True
	assert Bot.bot.help_command == None
	assert Bot.bot.intents == discord.Intents.all()


def test_animal():
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
	for animalName in misc.animals.fields[:-4]:
		print(animalName)
		r = requests.get(misc.animal(animalName.name[1:]))
		assert r.ok and r.headers["content-type"] in imageTypes

	for animalName in misc.animals.fields[-4:]:
		print(animalName)
		# Koala, Bird, Raccoon, Kangaroo APIs lack a content-type field;
		# check if URL points to an image instead
		r = requests.get(misc.animal(animalName.name[1:]))
		print(str(r.content)[:30])
		assert r.ok and any(
			str(r.content).startswith(signature) for signature in imageSigs
		)

	breeds = misc.animal("dog", "breeds")[12:-1].split(", ")
	assert len(breeds) >= 94
	for breed in breeds:
		r = requests.head(misc.animal("dog", breed))
		assert r.ok and r.headers["content-type"] in imageTypes
	assert misc.animal("dog", "invalidbreed").startswith("Breed not")
	assert misc.animal("dog", "invalidbreed1234").startswith("Breed not")

	with pytest.raises(Exception):
		misc.animal("invalidAnimal")


def test_fact():
	with open("resources/facts.txt", "r") as f:
		assert misc.fact() in f.read().splitlines()


def test_tweet():
	eggTweet = misc.tweet()
	assert ("\n" + eggTweet).startswith(misc.formattedTweet(eggTweet))
	assert "." not in misc.formattedTweet("test tweet.")
	assert "." not in misc.formattedTweet("test tweet")
	eggTweet = eggTweet.split(" ")
	assert len(eggTweet) >= 11 and len(eggTweet) <= 37


def test_dice():
	user = TestUser()
	for sideNum in 4, 6, 8, 100, 10, 12, 20:
		message = "!d" + str(sideNum)
		sideRoll = misc.roll(message)
		assert 1 <= sideRoll and sideRoll <= sideNum
		assert (
			misc.rollReport(message, user)
			.description
			.startswith("You got")
		)
	sideRoll = misc.roll("!d20-4")
	assert -3 <= sideRoll and sideRoll <= 16
	assert misc.rollReport("!d20-4", user).description.startswith("You got")
	assert not misc.roll("!d9")
	assert (
		misc.rollReport("!d9", user)
		.description
		.startswith("Invalid side number.")
	)


def test_logDeleteMsg():
	msg = TestMessage()
	assert (
		logs.logDeleteMsg(msg).description ==
		f"**Deleted message sent by {msg.author.mention}"
		f" in **{msg.channel.mention}\n{msg.content}"
	)


def test_logPurge():
	msg = TestMessage()
	assert (
		logs.logPurge(msg, (msg, msg, msg)).description ==
		f"Purged 2 messages in {msg.channel.mention}."
	)


def test_logEditMsg():
	before = TestMessage()
	after = TestMessage("newcontent")
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
	msg = TestMessage()
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
	channel = TestChannel()
	assert (
		logs.logDeleteChannel(channel).description ==
		f"Channel \"{channel.name}\" deleted."
	)


def test_logCreateChannel():
	channel = TestChannel()
	assert (
		logs.logCreateChannel(channel).description ==
		f"Channel \"{channel.name}\" created."
	)


def test_logMemberJoin():
	member = TestUser()
	assert (
		logs.logMemberJoin(member).description ==
		f"Member {member.mention} joined\nAccount registered on"
		f" {misc.truncTime(member)}\nID: {member.id}"
	)


def test_logMemberRemove():
	member = TestUser()
	assert (
		logs.logMemberRemove(member).description ==
		f"Member {member.mention} left\nID: {member.id}"
	)
	member.roles = TestUser(), TestUser()
	# hacky but works; TODO create test roles
	assert (
		logs.logMemberRemove(member).fields[0].value ==
		member.roles[1].mention
	)


def test_logMemberNickChange():
	before = TestUser()
	after = TestUser("testuser", "newnick")
	emb = logs.logMemberNickChange(before, after)
	assert emb.description == "Nickname of " + after.mention + " changed."
	assert emb.fields[0].value == before.nick
	assert emb.fields[1].value == after.nick


def test_logMemberRolesChange():
	before = TestUser()
	after = TestUser()
	after.roles = (TestUser(),)
	assert (
		logs.logMemberRolesChange(before, after).description ==
		f"Role {after.roles[0].mention} added to {after.mention}."
	)
	assert (
		logs.logMemberRolesChange(after, before).description ==
		f"Role {after.roles[0].mention} removed from {before.mention}."
	)


def test_logBan():
	member = TestUser()
	assert (
		logs.logBan(member).description ==
		f"Member {member.mention} banned\n{member.name}"
	)


def test_logUnban():
	member = TestUser()
	assert (
		logs.logUnban(member).description ==
		f"Member {member.mention} unbanned\n{member.name}"
	)


def test_logMute():
	message = TestMessage()
	member = TestUser()
	assert (
		logs.logMute(member, message, "5", "hours", 18000).description ==
		f"Muted {member.mention} for 5 hours in {message.channel.mention}."
	)
	assert (
		logs.logMute(member, message, None, None, None).description ==
		f"Muted {member.mention} in {message.channel.mention}."
	)


def test_logUnmute():
	member = TestUser()
	assert (
		logs.logUnmute(member, TestUser()).description ==
		f"Unmuted {member.mention}."
	)


def test_memSearch():
	text = TestMessage()
	namedUser = TestUser("searchterm", "testnick", "9999")
	text.guild.members = (TestUser(), namedUser)
	contentList = "searchterm#9999", "searchterm", "search", "testnick"
	for content in contentList:
		text.content = content
		assert misc.memSearch(text, content) == namedUser
	namedUser.name = "hash#name"
	text.content = "hash#name"
	assert misc.memSearch(text, text.content) == namedUser
	text.content = "invalidterm"
	assert not misc.memSearch(text, text.content)


def test_register():
	bb = TestUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	bucks.reset(bb)
	assert (
		bucks.register(bb).description ==
		"You are already in the system! Hooray! You"
		f" have 200 BeardlessBucks, {bb.mention}."
	)
	bb.name = ",badname,"
	assert (
		bucks.register(bb).description ==
		bucks.commaWarn.format(bb.mention)
	)


def test_balance():
	text = TestMessage(
		"!bal",
		TestUser(
			"Beardless Bot",
			"Beardless Bot",
			5757,
			654133911558946837
		)
	)
	assert (
		bucks.balance(text.author, text).description ==
		f"{text.author.mention}'s balance is 200 BeardlessBucks."
	)
	text.guild.members = (TestUser(), text.author)
	text.content = "!balance " + text.author.name
	assert (
		bucks.balance(text.author, text).description ==
		f"{text.author.mention}'s balance is 200 BeardlessBucks."
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
	bb = TestUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	assert (
		bucks.reset(bb).description ==
		f"You have been reset to 200 BeardlessBucks, {bb.mention}."
	)
	bb.name = ",badname,"
	assert bucks.reset(bb).description == bucks.commaWarn.format(bb.mention)


def test_writeMoney():
	user = TestUser()
	user.id = 654133911558946837
	assert bucks.writeMoney(user, "-all", False, False)
	assert bucks.writeMoney(user, -1000000, True, False) == (-2, None)


def test_leaderboard():
	lb = bucks.leaderboard()
	assert lb.title == "BeardlessBucks Leaderboard"
	if len(lb.fields) >= 2:  # This check in case of an empty leaderboard
		assert int(lb.fields[0].value) > int(lb.fields[1].value)


def test_define():
	word = misc.define("test")
	assert word.title == "TEST" and word.description.startswith("Audio: ")
	word = misc.define("pgp")
	assert word.title == "PGP" and word.description == ""
	assert misc.define("invalidword").description == "Invalid word!"


def test_flip():
	bb = TestUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	assert (
		bucks.flip(bb, "0", True)
		.endswith("if you had actually bet anything.")
	)
	assert bucks.flip(bb, "invalidbet").startswith("Invalid bet.")
	bucks.reset(bb)
	bucks.flip(bb, "all")
	balMsg = bucks.balance(bb, TestMessage("!bal", bb))
	assert ("400" in balMsg.description or "0" in balMsg.description)
	assert bucks.flip(bb, "10000000000000").startswith("You do not have")
	bucks.reset(bb)
	assert "200" in bucks.balance(bb, TestMessage("!bal", bb)).description
	bb.name = ",invalidname,"
	assert bucks.flip(bb, "0") == bucks.commaWarn.format(bb.mention)


def test_blackjack():
	bb = TestUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	assert bucks.blackjack(bb, "invalidbet")[0].startswith("Invalid bet.")
	bucks.reset(bb)
	report, game = bucks.blackjack(bb, "all")
	assert isinstance(game, bucks.Instance) or "You hit 21!" in report
	bucks.reset(bb)
	report, game = bucks.blackjack(bb, 0)
	assert isinstance(game, bucks.Instance) or "You hit 21!" in report
	bucks.reset(bb)
	report, game = bucks.blackjack(bb, "10000000000000")
	assert report.startswith("You do not have")
	bb.name = ",invalidname,"
	assert bucks.blackjack(bb, "all")[0] == bucks.commaWarn.format(bb.mention)


def test_blackjack_perfect():
	game = bucks.Instance(TestUser(), 10)
	game.cards = 10, 11
	assert game.perfect()


def test_blackjack_deal():
	game = bucks.Instance(TestUser(), 10)
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
	game = bucks.Instance(TestUser(), 10)
	assert game.cardName(10) in ("a 10", "a Jack", "a Queen", "a King")
	assert game.cardName(11) == "an Ace"
	assert game.cardName(8) == "an 8"
	assert game.cardName(5) == "a 5"


def test_blackjack_checkBust():
	game = bucks.Instance(TestUser(), 10)
	game.cards = 10, 10, 10
	assert game.checkBust()


def test_blackjack_stay():
	game = bucks.Instance(TestUser(), 0)
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
	game = bucks.Instance(TestUser(), 10)
	game.cards = []
	game.message = game.startingHand()
	assert len(game.cards) == 2
	assert game.message.startswith("Your starting hand consists of ")
	assert "You hit 21!" in game.startingHand(True)
	assert (
		game.startingHand(False, True)
		.startswith("Your starting hand consists of two Aces.")
	)


def test_randomBrawl():
	assert brawl.randomBrawl("legend").title == "Random Legend"
	assert brawl.randomBrawl("weapon").title == "Random Weapon"
	assert brawl.randomBrawl("invalidrandom").title == "Brawlhalla Randomizer"
	assert brawl.randomBrawl("invalidrandom").title == "Brawlhalla Randomizer"


def test_info():
	text = TestMessage("!info searchterm")
	namedUser = TestUser("searchterm")
	text.guild.members = (TestUser(), namedUser)
	namedUser.roles = (namedUser, namedUser)
	namedUserInfo = misc.info("searchterm", text)
	assert namedUserInfo.fields[0].value == misc.truncTime(namedUser) + " UTC"
	assert namedUserInfo.fields[1].value == misc.truncTime(namedUser) + " UTC"
	assert namedUserInfo.fields[2].value == namedUser.mention
	assert misc.info("!infoerror", text).title == "Invalid target!"


def test_av():
	text = TestMessage("!av searchterm")
	namedUser = TestUser("searchterm")
	text.guild.members = (TestUser(), namedUser)
	assert misc.av("searchterm", text).image.url == namedUser.avatar_url
	assert misc.av("error", text).title == "Invalid target!"


def test_commands():
	text = TestMessage()
	text.guild = None
	assert len(misc.bbCommands(text).fields) == 15


def test_hints():
	with open("resources/hints.txt", "r") as f:
		assert len(misc.hints().fields) == len(f.read().splitlines())


def test_pingMsg():
	namedUser = TestUser("likesToPing")
	assert (
		brawl.pingMsg(namedUser.mention, 1, 1, 1)
		.endswith("You can ping again in 1 hour, 1 minute, and 1 second.")
	)
	assert (
		brawl.pingMsg(namedUser.mention, 2, 2, 2)
		.endswith("You can ping again in 2 hours, 2 minutes, and 2 seconds.")
	)


def test_scamCheck():
	assert misc.scamCheck("http://freediscordnitro.com.")
	assert misc.scamCheck("@everyone http://scamlink.com free nitro!")
	assert not misc.scamCheck(
		"Hey Discord friends, check out https://top.gg/bot/654133911558946837"
	)


def test_onJoin():
	guild = discord.Guild
	guild.name = "Test Guild"
	role = discord.Role
	role.name = "Test Role"
	role.id = 0
	guild.roles = role,
	assert misc.onJoin(guild, role).title == "Hello, Test Guild!"


def test_fetchBrawlID():
	if not brawlKey:
		return
	assert brawl.fetchBrawlID(196354892208537600) == 7032472
	assert not brawl.fetchBrawlID(654133911558946837)


def test_claimProfile():
	if not brawlKey:
		return
	with open("resources/claimedProfs.json", "r") as f:
		profsLen = len(load(f))
	brawl.claimProfile(196354892208537600, 1)
	with open("resources/claimedProfs.json", "r") as f:
		assert profsLen == len(load(f))
	assert brawl.fetchBrawlID(196354892208537600) == 1
	brawl.claimProfile(196354892208537600, 7032472)
	assert brawl.fetchBrawlID(196354892208537600) == 7032472


def test_fetchLegends():
	if not brawlKey:
		return
	assert len(brawl.fetchLegends()) == 54


def test_getBrawlID():
	if not brawlKey:
		return
	assert brawl.getBrawlID(
		brawlKey,
		"https://steamcommunity.com/id/beardless"
	) == 7032472
	assert not brawl.getBrawlID(brawlKey, "badurl")
	assert not brawl.getBrawlID(
		brawlKey,
		"https://steamcommunity.com/badurl"
	)


def test_getLegends():
	if not brawlKey:
		return
	oldLegends = brawl.fetchLegends()
	brawl.getLegends(brawlKey)
	assert brawl.fetchLegends() == oldLegends


def test_legendInfo():
	if not brawlKey:
		return
	assert brawl.legendInfo(brawlKey, "hugin").title == "Munin, The Raven"
	assert not brawl.legendInfo(brawlKey, "invalidname")


def test_getRank():
	if not brawlKey:
		return
	user = TestUser()
	user.id = 0
	assert (
		brawl.getRank(user, brawlKey).description ==
		brawl.unclaimed.format(user.mention)
	)
	user.id = 743238109898211389  # 12502880
	assert (
		brawl.getRank(user, brawlKey).footer.text ==
		"Brawl ID 12502880"
	)


def test_getStats():
	if not brawlKey:
		return
	user = TestUser()
	user.id = 0
	assert (
		brawl.getStats(user, brawlKey).description ==
		brawl.unclaimed.format(user.mention)
	)
	user.id = 196354892208537600
	emb = brawl.getStats(user, brawlKey)
	assert emb.footer.text == "Brawl ID 7032472"
	assert len(emb.fields) == 3


def test_getClan():
	if not brawlKey:
		return
	user = TestUser()
	user.id = 0
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
	if not brawlKey:
		return
	assert len(brawl.brawlCommands().fields) == 6
