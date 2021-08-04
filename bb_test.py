# Beardless Bot Unit Tests

import discord
import requests

from animals import *
from blackjack import *
from bucks import *
from define import *
from dice import *
from eggTweet import *
from fact import *
from logs import *

class TestUser(discord.User):
    def __init__(self):
        self.name = "testname"
        self.nick = "testnick"
        self.id = 123456789
        self.discriminator = "0000"
        self.bot = False
        self.avatar = self.default_avatar
        self.roles = []
    
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
    def __init__(self):
        self.author = TestUser()
        self.content = "testcontent"
        self.id = 123456789
        self.channel = TestChannel()
        self.type = discord.MessageType.default
        self.flags = discord.MessageFlags(crossposted = False, is_crossposted = False, suppress_embeds = False, source_message_deleted = False, urgent = False)
        self.mentions = []

IMAGETYPES = ("image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp")
IMAGESIGS = ("b'\\xff\\xd8\\xff\\xe0\\x00\\x10JFIF", "b'\\x89\\x50\\x4e\\x47\\x0d\\x", "b'\\xff\\xd8\\xff\\xe2\\x024ICC_PRO")

def test_cat():
    r = requests.head(animal("cat"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_dog():
    r = requests.head(animal("dog"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_dog_breeds():
    assert animal("dog breeds").startswith("Dog breeds:")
    assert len(animal("dog breeds")[12:-1].split(", ")) == 95

def test_dog_breed(): 
    #for breed in animal("dog breeds")[12:-1].split(", "):
        #r = requests.head(animal("dog " + breed))
        #assert r.ok and r.headers["content-type"] in IMAGETYPES
    assert animal("dog invalid breed") == "Breed not found! Do !dog breeds to see all the breeds."

#def test_fish(): # fish API is experiencing a server outage
    #r = requests.head(animal("fish"))
    #assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_fox():
    r = requests.head(animal("fox"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_rabbit():
    r = requests.head(animal("rabbit"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_panda():
    r = requests.head(animal("panda"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_koala(): # Koala API headers lack a content-type field, so check if the URL points to a jpg or png instead
    r = requests.get(animal("koala"))
    assert r.ok and any(str(r.content).startswith(signature) for signature in IMAGESIGS)

def test_bird():# Bird API headers lack a content-type field, so check if the URL points to a jpg or png instead
    r = requests.get(animal("bird"))
    assert r.ok and any(str(r.content).startswith(signature) for signature in IMAGESIGS)

#def test_lizard(): # lizard API is experiencing a server outage
    #r = requests.head(animal("lizard"))
    #assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_duck():
    r = requests.head(animal("duck"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_fact():
    with open("resources/facts.txt", "r") as f:
        assert fact() in f.read().splitlines()

def test_tweet():
    eggTweet = tweet().split(" ")
    assert len(eggTweet) >= 12 and len(eggTweet) <= 37

def test_egg_formatted_tweet():
    eggTweet = tweet()
    assert eggTweet.startswith(formattedTweet(eggTweet))

def test_dice():
    message = TestMessage()
    for sideNum in (4, 6, 8, 100, 10, 12, 20):
        message.content = "!d" + str(sideNum)
        sideRoll = roll(message.content)
        assert 1 <= sideRoll and sideRoll <= sideNum
        assert isinstance(rollReport(message), discord.Embed)
    message.content = "!d9"
    assert not roll(message.content)
    assert isinstance(rollReport(message), discord.Embed)

def test_logDeleteMsg():
    msg = TestMessage()
    assert logDeleteMsg(msg).description == "**Deleted message sent by " + msg.author.mention + " in **" + msg.channel.mention + "\n" + msg.content

def test_logPurge():
    msg = TestMessage()
    assert logPurge(msg, (msg, msg, msg)).description == "Purged 2 messages in " + msg.channel.mention + "."

def test_logEditMsg():
    before = TestMessage()
    after = TestMessage()
    emb = logEditMsg(before, after)
    assert emb.description == "Messaged edited by" + before.author.mention + " in " + before.channel.mention + "."
    assert emb.fields[0].value == before.content
    assert emb.fields[1].value == after.content + "\n[Jump to Message](" + after.jump_url + ")"

def test_logClearReacts():
    msg = TestMessage()
    emb = logClearReacts(msg, (1, 2, 3))
    assert emb.description == "Reactions cleared from message sent by" + msg.author.mention + " in " + msg.channel.mention + "."
    assert emb.fields[0].value == msg.content
    assert emb.fields[1].value == "1, 2, 3"

def test_logDeleteChannel():
    channel = TestChannel()
    assert logDeleteChannel(channel).description == "Channel \"" + channel.name + "\" deleted."

def test_logCreateChannel():
    channel = TestChannel()
    assert logCreateChannel(channel).description == "Channel " + channel.mention + " created."

def test_logMemberJoin():
    member = TestUser()
    assert logMemberJoin(member).description == "Member " + member.mention + " joined\nAccount registered on " + str(member.created_at)[:-7] + "\nID: " + str(member.id)

def test_logMemberRemove():
    member = TestUser()
    assert logMemberRemove(member).description == "Member " + member.mention + " left\nID: " + str(member.id)
    member.roles = [TestUser(), TestUser()]
    assert logMemberRemove(member).fields[0].value == member.roles[1].mention

def test_logMemberNickChange():
    before = TestUser()
    after = TestUser()
    emb = logMemberNickChange(before, after)
    assert emb.description == "Nickname of" + after.mention + " changed"
    assert emb.fields[0].value == before.nick
    assert emb.fields[1].value == after.nick
    
def test_logMemberRolesChange():
    before = TestUser()
    after = TestUser()
    after.roles = [TestUser()]
    assert logMemberRolesChange(before, after).description == "Role " + after.roles[0].mention + " added to " + after.mention
    assert logMemberRolesChange(after, before).description == "Role " + after.roles[0].mention + " removed from " + before.mention

def test_logBan():
    member = TestUser()
    assert logBan(member).description == "Member " + member.mention + " banned\n" + member.name

def test_logUnban():
    member = TestUser()
    assert logUnban(member).description == "Member " + member.mention + " unbanned\n" + member.name

def test_logMute():
    message = TestMessage()
    member = TestUser()
    duration = "5"
    mString = "hours"
    assert logMute(member, message, duration, mString, 18000).description == "Muted " + member.mention + " for " + duration + mString + " in " + message.channel.mention + "."
    assert logMute(member, message, None, None, None).description == "Muted " + member.mention + " in " + message.channel.mention + "."

def test_logUnmute():
    member = TestUser()
    assert logUnmute(member, TestUser()).description == "Autounmuted " + member.mention + "."

def test_register():
    text = TestMessage()
    text.author.id = 654133911558946837
    assert register(text).description == "You are already in the system! Hooray! You have 200 BeardlessBucks, " + text.author.mention + "."
    text.author.name = ",badname,"
    assert balance(text).description == "For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + "."

def test_balance():
    text = TestMessage()
    text.author.id = 654133911558946837
    assert balance(text).description == "Your balance is 200 BeardlessBucks, " + text.author.mention + "."
    text.author.name = ",badname,"
    assert balance(text).description == "For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + "."

def test_reset():
    text = TestMessage()
    text.author.id = 654133911558946837
    assert reset(text).description == "You have been reset to 200 BeardlessBucks, " + text.author.mention + "."
    text.author.name = ",badname,"
    assert reset(text).description == "For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + "."

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
    game.cards = [10, 11]
    assert game.perfect() == True and game.checkBust() == False

def test_blackjack_deal():
    game = Instance(TestUser(), 10)
    game.cards = [2, 3]
    game.deal()
    assert len(game.cards) == 3

def test_blackjack_cardName():
    game = Instance(TestUser(), 10)
    assert game.cardName(10) in ("a 10", "a Jack", "a Queen", "a King")

def test_blackjack_checkBust():
    game = Instance(TestUser(), 10)
    game.cards = [10, 10, 10]
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
    game.cards = [10, 10]
    assert game.stay() == 0

def test_blackjack_startingHand():
    game = Instance(TestUser(), 10)
    game.cards = []
    game.message = game.startingHand()
    assert len(game.cards) == 2
    assert game.message.startswith("Your starting hand consists of " + game.cardName(game.cards[0]) + " and " + game.cardName(game.cards[1]) + ". Your total is " + str(sum(game.cards)) + ". ")