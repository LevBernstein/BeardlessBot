# Beardless Bot Unit Tests

from json import dump, load
from random import randint

import discord
import pytest
import requests

from brawl import *
from bucks import *
from logs import *
from misc import *

class TestUser(discord.User):
	def __init__(self, name = "testname", nick = "testnick", discriminator = "0000", id = 123456789):
		self.name = name
		self.nick = nick
		self.id = id
		self.discriminator = discriminator
		self.bot = False
		self.avatar = self.default_avatar
		self.roles = ()
		self.joined_at = self.created_at
		self.activity = None

	def avatar_url_as(self, format = None, size = 1024):
		# Discord really doesn't like it when you construct its objects manually;
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
	def __init__(self, content = "testcontent", author = TestUser()):
		self.author = author
		self.content = content
		self.id = 123456789
		self.channel = TestChannel()
		self.type = discord.MessageType.default
		self.flags = discord.MessageFlags(crossposted = False, is_crossposted = False,
		suppress_embeds = False, source_message_deleted = False, urgent = False)
		self.mentions = ()

try:
	with open("resources/brawlhallaKey.txt", "r") as f:
		# In brawlhallaKey.txt, paste in your own Brawlhalla API key
		brawlKey = f.readline()
except:
	print("No Brawlhalla API key. Brawlhalla-specific tests will not fire.")
	brawlKey = None

def test_animals():
	assert len(animals().fields) == 13

def test_animal():
	imageTypes = "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"
	imageSigs = ("b'\\xff\\xd8\\xff\\xe0\\x00\\x10JFIF", "b'\\x89\\x50\\x4e\\x47\\x0d\\x",
	"b'\\xff\\xd8\\xff\\xe2\\x024ICC_PRO", "b'\\x89PNG\\r\\n\\x1a\\n\\", "b'\\xff\\xd8\\xff\\xe1\\tPh")
	for animalName in animals().fields[:-4]:
		print(animalName)
		r = requests.get(animal(animalName.name[1:]))
		assert r.ok and r.headers["content-type"] in imageTypes

	for animalName in animals().fields[-4:]:
		print(animalName)
		# Koala, Bird, Raccoon, Kangaroo APIs lack a content-type field; check if URL points to an image instead
		r = requests.get(animal(animalName.name[1:]))
		print(str(r.content)[:30])
		assert r.ok and any(str(r.content).startswith(signature) for signature in imageSigs)

	breeds = animal("dog", "breeds")[12:-1].split(", ")
	assert len(breeds) >= 94
	for breed in breeds:
		r = requests.head(animal("dog", breed))
		assert r.ok and r.headers["content-type"] in imageTypes
	assert animal("dog", "invalidbreed") == "Breed not found! Do !dog breeds to see all the breeds."
	assert animal("dog", "invalidbreed1234") == "Breed not found! Do !dog breeds to see all the breeds."

	with pytest.raises(Exception):
		animal("invalidAnimal")

def test_fact():
	with open("resources/facts.txt", "r") as f:
		assert fact() in f.read().splitlines()

def test_tweet():
	eggTweet = tweet().split(" ")
	assert len(eggTweet) >= 11 and len(eggTweet) <= 37

def test_egg_formatted_tweet():
	eggTweet = tweet()
	assert ("\n" + eggTweet).startswith(formattedTweet(eggTweet))
	assert not "." in formattedTweet("test tweet.")
	assert not "." in formattedTweet("test tweet")

def test_dice():
	user = TestUser()
	for sideNum in 4, 6, 8, 100, 10, 12, 20:
		message = "!d" + str(sideNum)
		sideRoll = roll(message)
		assert 1 <= sideRoll and sideRoll <= sideNum
		assert rollReport(message, user).description.startswith("You got")
	sideRoll = roll("!d20-4")
	assert -3 <= sideRoll and sideRoll <= 16
	assert rollReport("!d20-4", user).description.startswith("You got")
	assert not roll("!d9")
	assert rollReport("!d9", user).description.startswith("Invalid side number.")

def test_logDeleteMsg():
	msg = TestMessage()
	assert logDeleteMsg(msg).description == f"**Deleted message sent by {msg.author.mention} in **{msg.channel.mention}\n{msg.content}"

def test_logPurge():
	msg = TestMessage()
	assert logPurge(msg, (msg, msg, msg)).description == f"Purged 2 messages in {msg.channel.mention}."

def test_logEditMsg():
	before = TestMessage()
	after = TestMessage("newcontent")
	emb = logEditMsg(before, after)
	assert emb.description == f"Messaged edited by {after.author.mention} in {after.channel.mention}."
	assert emb.fields[0].value == before.content
	assert emb.fields[1].value == f"{after.content}\n[Jump to Message]({after.jump_url})"

def test_logClearReacts():
	msg = TestMessage()
	emb = logClearReacts(msg, (1, 2, 3))
	assert emb.description.startswith(f"Reactions cleared from message sent by {msg.author.mention} in {msg.channel.mention}.")
	assert emb.fields[0].value.startswith(msg.content)
	assert emb.fields[1].value == "1, 2, 3"

def test_logDeleteChannel():
	channel = TestChannel()
	assert logDeleteChannel(channel).description == f"Channel \"{channel.name}\" deleted."

def test_logCreateChannel():
	channel = TestChannel()
	assert logCreateChannel(channel).description == f"Channel \"{channel.name}\" created."

def test_logMemberJoin():
	member = TestUser()
	assert logMemberJoin(member).description == ("Member {} joined\nAccount registered on {}\nID: {}"
	.format(member.mention, str(member.created_at)[:-7], member.id))

def test_logMemberRemove():
	member = TestUser()
	assert logMemberRemove(member).description == f"Member {member.mention} left\nID: {member.id}"
	member.roles = TestUser(), TestUser() # hacky but works; TODO create test roles
	assert logMemberRemove(member).fields[0].value == member.roles[1].mention

def test_logMemberNickChange():
	before = TestUser()
	after = TestUser("testuser", "newnick")
	emb = logMemberNickChange(before, after)
	assert emb.description == "Nickname of" + after.mention + " changed."
	assert emb.fields[0].value == before.nick
	assert emb.fields[1].value == after.nick

def test_logMemberRolesChange():
	before = TestUser()
	after = TestUser()
	after.roles = TestUser(),
	assert logMemberRolesChange(before, after).description == f"Role {after.roles[0].mention} added to {after.mention}."
	assert logMemberRolesChange(after, before).description == f"Role {after.roles[0].mention} removed from {before.mention}."

def test_logBan():
	member = TestUser()
	assert logBan(member).description == f"Member {member.mention} banned\n{member.name}"

def test_logUnban():
	member = TestUser()
	assert logUnban(member).description == f"Member {member.mention} unbanned\n{member.name}"

def test_logMute():
	message = TestMessage()
	member = TestUser()
	assert logMute(member, message, "5", "hours", 18000).description == f"Muted {member.mention} for 5 hours in {message.channel.mention}."
	assert logMute(member, message, None, None, None).description == f"Muted {member.mention} in {message.channel.mention}."

def test_logUnmute():
	member = TestUser()
	assert logUnmute(member, TestUser()).description == f"Unmuted {member.mention}."

def test_memSearch():
	text = TestMessage()
	namedUser = TestUser("searchterm", "testnick", "9999")
	text.guild.members = (TestUser(), namedUser)
	contentList = "searchterm#9999", "searchterm", "search", "testnick"
	for content in contentList:
		text.content = content
		assert memSearch(text, content) == namedUser
	namedUser.name = "hash#name"
	text.content = "hash#name"
	assert memSearch(text, text.content) == namedUser
	text.content = "invalidterm"
	assert not memSearch(text, text.content)

def test_register():
	bb = TestUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	assert register(bb).description == f"You are already in the system! Hooray! You have 200 BeardlessBucks, {bb.mention}."
	bb.name = ",badname,"
	assert register(bb).description == commaWarn.format(bb.mention)

def test_balance():
	text = TestMessage("!bal", TestUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837))
	assert balance(text.author, text).description == f"{text.author.mention}'s balance is 200 BeardlessBucks."
	text.guild.members = (TestUser(), text.author)
	text.content = "!balance " + text.author.name
	assert balance(text.author, text).description == f"{text.author.mention}'s balance is 200 BeardlessBucks."
	text.content = "!balance"
	text.author.name = ",badname,"
	assert balance(text.author, text).description == commaWarn.format(text.author.mention)
	text.content = "!balance invaliduser"
	assert balance("badtarget", text).description.startswith("Invalid user!")

def test_reset():
	bb = TestUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	assert reset(bb).description == f"You have been reset to 200 BeardlessBucks, {bb.mention}."
	bb.name = ",badname,"
	assert reset(bb).description == commaWarn.format(bb.mention)

def test_writeMoney():
	user = TestUser()
	user.id = 654133911558946837
	assert writeMoney(user, "-all", False, False)
	assert writeMoney(user, -1000000, True, False) == (-2, None)

def test_leaderboard():
	lb = leaderboard()
	assert lb.title == "BeardlessBucks Leaderboard"
	if len(lb.fields) >= 2: # This check in case of an empty leaderboard
		assert int(lb.fields[0].value) > int(lb.fields[1].value)

def test_define():
	word = define("test")
	assert word.title == "TEST" and word.description.startswith("Audio: ")
	word = define("pgp")
	assert word.title == "PGP" and word.description == ""
	assert define("invalidword").description == "Invalid word!"

def test_flip():
	bb = TestUser("Beardless Bot", "Beardless Bot", 5757, 654133911558946837)
	assert flip(bb, "0").endswith("if you had actually bet anything.")
	assert flip(bb, "invalidbet").startswith("Invalid bet amount.")
	reset(bb)
	flip(bb, "all")
	balMsg = balance(bb, TestMessage("!bal", bb))
	assert ("400" in balMsg.description or "0" in balMsg.description)
	assert flip(bb, "10000000000000").startswith("You do not have")
	balMsg = reset(bb)
	assert "200" in balance(bb, TestMessage("!bal", bb)).description

def test_blackjack_perfect():
	game = Instance(TestUser(), 10)
	game.cards = 10, 11
	assert game.perfect() == True

def test_blackjack_deal():
	game = Instance(TestUser(), 10)
	game.cards = [2, 3]
	game.deal()
	assert len(game.cards) == 3
	game.cards = [11, 9]
	game.deal()
	assert sum(game.cards) <= 21
	assert "will be treated as a 1" in game.message

def test_blackjack_cardName():
	game = Instance(TestUser(), 10)
	assert game.cardName(10) in ("a 10", "a Jack", "a Queen", "a King")
	assert game.cardName(11) == "an Ace"
	assert game.cardName(8) == "an 8"
	assert game.cardName(5) == "a 5"

def test_blackjack_checkBust():
	game = Instance(TestUser(), 10)
	game.cards = 10, 10, 10
	assert game.checkBust() == True

def test_blackjack_getUser():
	user = TestUser()
	game = Instance(user, 10)
	assert game.getUser() == user

def test_blackjack_stay():
	game = Instance(TestUser(), 0)
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
	game = Instance(TestUser(), 10)
	game.cards = []
	game.message = game.startingHand()
	assert len(game.cards) == 2
	assert game.message.startswith("Your starting hand consists of ")

def test_randomBrawl():
	assert randomBrawl("legend").title == "Random Legend"
	assert randomBrawl("weapon").title == "Random Weapon"
	assert randomBrawl("invalidrandom").title == "Brawlhalla Randomizer"
	assert randomBrawl("invalidrandom").title == "Brawlhalla Randomizer"

def test_info():
	text = TestMessage("!info searchterm")
	namedUser = TestUser("searchterm")
	text.guild.members = (TestUser(), namedUser)
	namedUser.roles = (namedUser, namedUser)
	namedUserInfo = info("searchterm", text)
	assert namedUserInfo.fields[0].value == str(namedUser.created_at)[:-7] + " UTC"
	assert namedUserInfo.fields[1].value == str(namedUser.joined_at)[:-7] + " UTC"
	assert namedUserInfo.fields[2].value == namedUser.mention
	assert info("!infoerror", text).title == "Invalid target!"

def test_av():
	text = TestMessage("!av searchterm")
	namedUser = TestUser("searchterm")
	text.guild.members = (TestUser(), namedUser)
	assert av("searchterm", text).image.url == namedUser.avatar_url
	assert av("error", text).title == "Invalid target!"

def test_commands():
	text = TestMessage()
	text.guild = None
	assert len(bbCommands(text).fields) == 15

def test_hints():
	with open("resources/hints.txt", "r") as f:
		assert len(hints().fields) == len(f.read().splitlines())

def test_claimProfile():
	with open("resources/claimedProfs.json", "r") as f:
		profsLen = len(load(f))
	claimProfile(196354892208537600, 1)
	with open("resources/claimedProfs.json", "r") as f:
		assert profsLen == len(load(f))
	assert fetchBrawlID(196354892208537600) == 1
	claimProfile(196354892208537600, 7032472)
	assert fetchBrawlID(196354892208537600) == 7032472

def test_pingMsg():
	namedUser = TestUser("likesToPing")
	assert pingMsg(namedUser.mention, 1, 1, 1).endswith("You can ping again in 1 hour, 1 minute, and 1 second.")
	assert pingMsg(namedUser.mention, 2, 2, 2).endswith("You can ping again in 2 hours, 2 minutes, and 2 seconds.")

def test_scamCheck():
	assert scamCheck("http://freediscordnitro.com.")
	assert scamCheck("@everyone http://scamlink.com free nitro!")
	assert not scamCheck("Hey Discord friends, check out https://top.gg/bot/654133911558946837")

if brawlKey:
	def test_fetchBrawlID():
		assert fetchBrawlID(196354892208537600) == 7032472
		assert not fetchBrawlID(654133911558946837)

	def test_fetchLegends():
		assert len(fetchLegends()) == 54

	def test_getBrawlID():
		assert getBrawlID(brawlKey, "https://steamcommunity.com/id/beardless") == 7032472
		assert not getBrawlID(brawlKey, "badurl")
		assert not getBrawlID(brawlKey, "https://steamcommunity.com/badurl")

	def test_getLegends():
		oldLegends = fetchLegends()
		getLegends(brawlKey)
		assert fetchLegends() == oldLegends

	def test_legendInfo():
		assert legendInfo(brawlKey, "hugin").title == "Munin, The Raven"
		assert not legendInfo(brawlKey, "invalidname")

	def test_getRank():
		user = TestUser()
		user.id = 0
		assert getRank(user, brawlKey) == f"{user.mention} needs to claim their profile first! Do !brawlclaim."
		user.id = 743238109898211389 #12502880
		assert getRank(user, brawlKey).footer.text == "Brawl ID 12502880"

	def test_getStats():
		user = TestUser()
		user.id = 0
		assert getStats(user, brawlKey) == f"{user.mention} needs to claim their profile first! Do !brawlclaim."
		user.id = 196354892208537600
		emb = getStats(user, brawlKey)
		assert emb.footer.text == "Brawl ID 7032472"
		assert len(emb.fields) == 3

	def test_getClan():
		user = TestUser()
		user.id = 0
		assert getClan(user, brawlKey) == f"{user.mention} needs to claim their profile first! Do !brawlclaim."
		user.id = 196354892208537600
		assert getClan(user, brawlKey).title == "DinersDriveInsDives"
		claimProfile(196354892208537600, 5895238)
		assert getClan(user, brawlKey) == "You are not in a clan!"
		claimProfile(196354892208537600, 7032472)

	def test_brawlCommands():
		assert len(brawlCommands().fields) == 6