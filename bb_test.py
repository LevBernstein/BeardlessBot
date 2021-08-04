# Beardless Bot Unit Tests

import discord
import requests

from animals import *
from bucks import *
from dice import *
from eggTweet import *
from fact import *
from logs import *

IMAGETYPES = ("image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp")
IMAGESIGS = ("b'\\xff\\xd8\\xff\\xe0\\x00\\x10JFIF", "b'\\x89\\x50\\x4e\\x47\\x0d\\x", "b'\\xff\\xd8\\xff\\xe2\\x024ICC_PRO")

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

class TestUser(discord.User):
    def __init__(self):
        self.name = "testname"
        self.id = 123456789
        self.discriminator = "0000"
        self.bot = False
        self.avatar = self.default_avatar

class TestMessage(discord.Message):
    def __init__(self):
        self.author = TestUser()
        self.content = "testcontent"
        self.id = 123456789
        self.channel = TestChannel()
        self.type = discord.MessageType.default
        self.flags = discord.MessageFlags(crossposted = False, is_crossposted = False, suppress_embeds = False, source_message_deleted = False, urgent = False)
        self.mentions = []

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

def test_lizard():
    r = requests.head(animal("lizard"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_duck():
    r = requests.head(animal("duck"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_fact():
    with open("resources/facts.txt", "r") as f:
        assert fact() in f.read().splitlines()

def test_tweet():
    eggTweet = tweet().split(" ")
    assert len(eggTweet) >= 10 and len(eggTweet) <= 35

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

def test_logPurge():
    msg = TestMessage()
    assert logPurge(msg, (3, 4, 5)).description == "Purged 2 messages in " + msg.channel.mention + "."

def test_logDeleteChannel():
    channel = TestChannel()
    assert logDeleteChannel(channel).description == "Channel \"" + channel.name + "\" deleted"

def test_logCreateChannel():
    channel = TestChannel()
    assert logCreateChannel(channel).description == "Channel " + channel.mention + " created"

# TODO: Fix the problem with avatar_url in constructed Users

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
    if len(lb.fields) >= 2: # This check in case of creating new, empty leaderboard
        assert int(lb.fields[0].value) > int(lb.fields[1].value)