# Beardless Bot Unit Tests

from json import dump, load
from random import randint

import discord
import pytest
import requests

from blackjack import *
from brawl import *
from bucks import *
from logs import *
from misc import *

class TestUser(discord.User):
    def __init__(self, name = "testname", nick = "testnick", discriminator = "0000"):
        self.name = name
        self.nick = nick
        self.id = 123456789
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
    def __init__(self, content = "testcontent"):
        self.author = TestUser()
        self.content = content
        self.id = 123456789
        self.channel = TestChannel()
        self.type = discord.MessageType.default
        self.flags = discord.MessageFlags(crossposted = False, is_crossposted = False,
        suppress_embeds = False, source_message_deleted = False, urgent = False)
        self.mentions = ()

try:
    with open("resources/brawlhallaKey.txt", "r") as f: # in brawlhallaKey.txt, paste in your own Brawlhalla API key
        brawlKey = f.readline()
except:
    print("No Brawlhalla API key. Brawlhalla-specific tests will not fire.")
    brawlKey = None

def test_animals():
    assert len(animals().fields) == 13

def test_animal():
    imageTypes = ("image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp")
    imageSigs = ("b'\\xff\\xd8\\xff\\xe0\\x00\\x10JFIF", "b'\\x89\\x50\\x4e\\x47\\x0d\\x", "b'\\xff\\xd8\\xff\\xe2\\x024ICC_PRO")
    for animalName in animals().fields[:-4]:
        if not "fish" in animalName.name: # fish API is experiencing a server outage
            r = requests.get(animal(animalName.name[1:]))
            assert r.ok and r.headers["content-type"] in imageTypes
    
    for animalName in animals().fields[-4:]: # Koala, Bird, Raccoon, Kangaroo APIs lack a content-type field; check if URL points to an image instead
        r = requests.get(animal(animalName.name[1:]))
        assert r.ok and any(str(r.content).startswith(signature) for signature in imageSigs)
    
    assert animal("dog breeds").startswith("Dog breeds:")
    assert len(animal("dog breeds")[12:-1].split(", ")) == 95
    
    for breed in animal("dog breeds")[12:-1].split(", "):
        r = requests.head(animal("dog " + breed))
        assert r.ok and r.headers["content-type"] in imageTypes
    assert animal("dog invalid breed") == "Breed not found! Do !dog breeds to see all the breeds."
    
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
    assert not "." in formattedTweet("test.")
    assert not "." in formattedTweet("test")

def test_dice():
    message = TestMessage()
    for sideNum in (4, 6, 8, 100, 10, 12, 20):
        message.content = "!d" + str(sideNum)
        sideRoll = roll(message.content)
        assert 1 <= sideRoll and sideRoll <= sideNum
        assert rollReport(message).description.startswith("You got")
    message.content = "!d20-4"
    sideRoll = roll(message.content)
    assert -3 <= sideRoll and sideRoll <= 16
    assert rollReport(message).description.startswith("You got")
    message.content = "!d9"
    assert not roll(message.content)
    assert rollReport(message).description.startswith("Invalid side number.")

def test_logDeleteMsg():
    msg = TestMessage()
    assert logDeleteMsg(msg).description == "**Deleted message sent by {} in **{}\n{}".format(msg.author.mention, msg.channel.mention, msg.content)

def test_logPurge():
    msg = TestMessage()
    assert logPurge(msg, (msg, msg, msg)).description == "Purged 2 messages in " + msg.channel.mention + "."

def test_logEditMsg():
    before = TestMessage()
    after = TestMessage("newcontent")
    emb = logEditMsg(before, after)
    assert emb.description == "Messaged edited by" + before.author.mention + " in " + before.channel.mention + "."
    assert emb.fields[0].value == before.content
    assert emb.fields[1].value == after.content + "\n[Jump to Message](" + after.jump_url + ")"

def test_logClearReacts():
    msg = TestMessage()
    emb = logClearReacts(msg, (1, 2, 3))
    assert emb.description == "Reactions cleared from message sent by " + msg.author.mention + " in " + msg.channel.mention + "."
    assert emb.fields[0].value == msg.content
    assert emb.fields[1].value == "1, 2, 3"

def test_logDeleteChannel():
    channel = TestChannel()
    assert logDeleteChannel(channel).description == "Channel \"" + channel.name + "\" deleted."

def test_logCreateChannel():
    channel = TestChannel()
    assert logCreateChannel(channel).description == "Channel " + channel.name + " created."

def test_logMemberJoin():
    member = TestUser()
    assert logMemberJoin(member).description == ("Member {} joined\nAccount registered on {}\nID: {}"
    .format(member.mention, str(member.created_at)[:-7], member.id))

def test_logMemberRemove():
    member = TestUser()
    assert logMemberRemove(member).description == "Member " + member.mention + " left\nID: " + str(member.id)
    member.roles = (TestUser(), TestUser()) # hacky but works; TODO create test roles
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
    after.roles = [TestUser()]
    assert logMemberRolesChange(before, after).description == "Role " + after.roles[0].mention + " added to " + after.mention + "."
    assert logMemberRolesChange(after, before).description == "Role " + after.roles[0].mention + " removed from " + before.mention + "."

def test_logBan():
    member = TestUser()
    assert logBan(member).description == "Member " + member.mention + " banned\n" + member.name

def test_logUnban():
    member = TestUser()
    assert logUnban(member).description == "Member " + member.mention + " unbanned\n" + member.name

def test_logMute():
    message = TestMessage()
    member = TestUser()
    assert logMute(member, message, "5", "hours", 18000).description == "Muted " + member.mention + " for 5 hours in " + message.channel.mention + "."
    assert logMute(member, message, None, None, None).description == "Muted " + member.mention + " in " + message.channel.mention + "."

def test_logUnmute():
    member = TestUser()
    assert logUnmute(member, TestUser()).description == "Autounmuted " + member.mention + "."

def test_memSearch():
    text = TestMessage()
    namedUser = TestUser("searchterm", "testnick", "9999")
    text.guild.members = [TestUser(), namedUser]
    text.content = "!av searchterm#9999"
    assert memSearch(text) == namedUser
    text.content = "!info searchterm"
    assert memSearch(text) == namedUser
    text.content = "!bal search"
    assert memSearch(text) == namedUser
    text.content = "!info invalidterm"
    assert not memSearch(text)

def test_register():
    text = TestMessage("!register")
    text.author.id = 654133911558946837
    assert register(text).description == "You are already in the system! Hooray! You have 200 BeardlessBucks, " + text.author.mention + "."
    text.author.name = ",badname,"
    text.author.id = 999999999999999999
    assert register(text).description == ("For the sake of safety, Beardless Bot gambling is not usable by Discord " +
    "users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")

def test_balance():
    text = TestMessage("!bal")
    text.author.id = 654133911558946837
    assert balance(text).description == text.author.mention + "'s balance is 200 BeardlessBucks."
    text.author.name = ",badname,"
    assert register(text).description == ("For the sake of safety, Beardless Bot gambling is not usable by Discord " +
    "users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")

def test_reset():
    text = TestMessage("!reset")
    text.author.id = 654133911558946837
    assert reset(text).description == "You have been reset to 200 BeardlessBucks, " + text.author.mention + "."
    text.author.name = ",badname,"
    assert register(text).description == ("For the sake of safety, Beardless Bot gambling is not usable by Discord " +
    "users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")

def test_leaderboard():
    lb = leaderboard()
    assert lb.title == "BeardlessBucks Leaderboard"
    if len(lb.fields) >= 2: # This check in case of an empty leaderboard
        assert int(lb.fields[0].value) > int(lb.fields[1].value)

def test_define():
    word = define("!define test")
    assert word.title == "TEST" and word.description.startswith("Audio: ")
    assert define("!define invalidword").description == "Invalid word!"
    assert define("!define spaced words").description == "Please only look up individual words."

def test_blackjack_perfect():
    game = Instance(TestUser(), 10)
    game.cards = (10, 11)
    assert game.perfect() == True

def test_blackjack_deal():
    game = Instance(TestUser(), 10)
    game.cards = [2, 3]
    game.deal()
    assert len(game.cards) == 3
    game.cards = [11, 9]
    game.deal()
    assert sum(game.cards) <= 21
    assert "your Ace has been changed" in game.message

def test_blackjack_cardName():
    game = Instance(TestUser(), 10)
    assert game.cardName(10) in ("a 10", "a Jack", "a Queen", "a King")
    assert game.cardName(11) == "an Ace"
    assert game.cardName(8) == "an 8"
    assert game.cardName(5) == "a 5"

def test_blackjack_checkBust():
    game = Instance(TestUser(), 10)
    game.cards = (10, 10, 10)
    assert game.checkBust() == True

def test_blackjack_getUser():
    user = TestUser()
    game = Instance(user, 10)
    assert game.getUser() == user

def test_blackjack_stay():
    game = Instance(TestUser(), 10)
    game.cards = [10, 10, 1]
    game.dealerSum = 25
    assert game.stay() == 4
    game.dealerSum = 20
    assert game.stay() == 3
    game.deal()
    assert game.stay() == -3
    game.cards = (10, 10)
    assert game.stay() == 0

def test_blackjack_startingHand():
    game = Instance(TestUser(), 10)
    game.cards = []
    game.message = game.startingHand()
    assert len(game.cards) == 2
    assert game.message.startswith("Your starting hand consists of a")

def test_randomBrawl():
    assert randomBrawl("!random legend").title == "Random Legend"
    assert randomBrawl("!random weapon").title == "Random Weapon"
    assert randomBrawl("!randominvalidrandom").title == "Brawlhalla Randomizer"
    assert randomBrawl("!random invalidrandom").title == "Brawlhalla Randomizer"

def test_info():
    text = TestMessage("!info searchterm")
    namedUser = TestUser("searchterm")
    text.guild.members = (TestUser(), namedUser)
    namedUser.roles = (namedUser, namedUser)
    namedUserInfo = info(text)
    assert namedUserInfo.fields[0].value == str(namedUser.created_at)[:-7] + " UTC"
    assert namedUserInfo.fields[1].value == str(namedUser.joined_at)[:-7] + " UTC"
    assert namedUserInfo.fields[2].value == namedUser.mention
    assert info("!infoerror").title == "Invalid target!"

def test_sparPins():
    emb = sparPins()
    assert emb.title == "How to use this channel."
    assert len(emb.fields) == 2

def test_av():
    text = TestMessage("!av searchterm")
    namedUser = TestUser("searchterm")
    text.guild.members = (TestUser(), namedUser)
    assert av(text).image.url == namedUser.avatar_url
    assert av("!averror").title == "Invalid target!"

def test_commands():
    text = TestMessage()
    text.guild = None
    assert len(commands(text).fields) == 15

def test_join():
    assert join().title == "Want to add this bot to your server?"

def test_hints():
    with open("resources/hints.txt", "r") as f:
        assert len(hints().fields) == len(f.read().splitlines())

def test_fetchBrawlID():
    assert fetchBrawlID(196354892208537600) == 7032472
    assert not fetchBrawlID(654133911558946837)

def test_fetchLegends():
    assert len(fetchLegends()) == 53

def test_claimProfile():
    with open("resources/claimedProfs.json", "r") as f:
        profsLen = len(load(f))
    claimProfile(196354892208537600, 1)
    with open("resources/claimedProfs.json", "r") as f:
        assert profsLen == len(load(f))
    assert fetchBrawlID(196354892208537600) == 1
    claimProfile(196354892208537600, 7032472)
    assert fetchBrawlID(196354892208537600) == 7032472

if brawlKey:
    def test_getBrawlID():
        assert getBrawlID(brawlKey, "https://steamcommunity.com/id/beardless") == 7032472
        assert not getBrawlID(brawlKey, "badurl")
        assert not getBrawlID(brawlKey, "https://steamcommunity.com/badurl")
    
    def test_getLegends():
        oldLegends = fetchLegends()
        getLegends(brawlKey)
        assert fetchLegends() == oldLegends
    
    def test_legendInfo():
        assert legendInfo(brawlKey, "sidra").title == "Sidra, The Corsair Queen"
        assert not legendInfo(brawlKey, "invalidname")
    
    def test_getRank():
        user = TestUser()
        user.id = 0
        assert not getRank(user, brawlKey)
        user.id = 196354892208537600
        assert getRank(user, brawlKey).footer.text == "Brawl ID 7032472"
    
    def test_getStats():
        user = TestUser()
        user.id = 0
        assert not getStats(user, brawlKey)
        user.id = 196354892208537600
        emb = getStats(user, brawlKey)
        assert emb.footer.text == "Brawl ID 7032472"
        assert len(emb.fields) == 3
    
    def test_getClan():
        assert not getClan(0, brawlKey)
        assert getClan(196354892208537600, brawlKey).title == "DinersDriveInsDives"