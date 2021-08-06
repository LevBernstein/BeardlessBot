# Miscellaneous commands for Beardless Bot

import discord
import requests

from random import choice, randint

from bucks import memSearch

def define(msg):
    word = msg.split(' ', 1)[1]
    report = "Invalid word!"
    if " " in word:
        report = "Please only look up individual words."
    else:
        r = requests.get("https://api.dictionaryapi.dev/api/v2/entries/en_US/" + word)
        if r.status_code == 200:
            try:
                emb = discord.Embed(title = word.upper(), description = "Audio: " + r.json()[0]['phonetics'][0]['audio'], color = 0xfff994)
                i = 0
                for entry in r.json():
                    for meaning in entry["meanings"]:
                        for definition in meaning["definitions"]:
                            i += 1
                            emb.add_field(name = "Definition " + str(i) + ":", value = definition["definition"], inline = True)
                return emb
            except:
                pass
    return discord.Embed(title = "Beardless Bot Definitions", description = report, color = 0xfff994)

def roll(message): # takes a string of the format !dn+b and rolls one n-sided die with a modifier of b.
    command = message.split('!d', 1)[1]
    modifier = -1 if "-" in command else 1
    sides = (4, 6, 8, 10, 12, 20, 100)
    if command.startswith("4") or command.startswith("6") or command.startswith("8"):
        return randint(1, int(command[0])) + modifier * int(command[2:]) if len(command) != 1 and (command[1] == "+" or command[1] == "-") else randint(1, int(command[0])) if int(command) in sides else None
    elif command.startswith("100"):
        return randint(1, 100) + modifier*int(command[4:]) if len(command) != 3 and (command[3] == "+" or command[3] == "-") else randint(1, 100) if int(command) in sides else None
    elif command.startswith("10") or command.startswith("12") or command.startswith("20"):
        return randint(1, int(command[:2])) + modifier * int(command[3:]) if len(command) != 2 and (command[2] == "+" or command[2] == "-") else randint(1, int(command[:2])) if int(command) in sides else None
    return None

def rollReport(text):
    result = roll(text.content.lower())
    report = "You got " + str(result) + ", " + text.author.mention + "." if result else "Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100, as well as modifiers. No spaces allowed. Ex: !d4+3"
    return discord.Embed(title = "Beardless Bot Dice", description = report, color = 0xfff994)

def fact():
    with open("resources/facts.txt", "r") as f:
        return choice(f.read().splitlines())

def randomBrawl(msg):
    try:
        ranType = msg.split(' ', 1)[1]
        if ranType in ("legend", "weapon"):
            legends = ("Bodvar", "Cassidy", "Orion", "Lord Vraxx", "Gnash", "Queen Nai", "Hattori", "Sir Roland", "Scarlet", "Thatch", "Ada", "Sentinel", "Lucien", "Teros", "Brynn", "Asuri", "Barraza", "Ember", "Azoth", "Koji", "Ulgrim", "Diana", "Jhala", "Kor", "Wu Shang", "Val", "Ragnir", "Cross", "Mirage", "Nix", "Mordex", "Yumiko", "Artemis", "Caspian", "Sidra", "Xull", "Kaya", "Isaiah", "Jiro", "Lin Fei", "Zariel", "Rayman", "Dusk", "Fait", "Thor", "Petra", "Vector", "Volkov", "Onyx", "Jaeyun", "Mako", "Magyar", "Reno")
            weapons = ("Sword", "Spear", "Orb", "Cannon", "Hammer", "Scythe", "Greatsword", "Bow", "Gauntlets", "Katars", "Blasters", "Axe")
            return discord.Embed(title = "Random " + ranType.title(), description = "Your {} is {}.".format(ranType, choice(legends if ranType == "legend" else weapons)), color = 0xfff994)
        else:
            return discord.Embed(title = "Invalid random!", description = "Please do !random legend or !random weapon.", color = 0xfff994)
    except:
        return discord.Embed(title = "Brawlhalla Randomizer", description = "Please do !random legend or !random weapon to get a random legend or weapon.", color = 0xfff994)

def info(text):
    try:
        target = text.mentions[0] if text.mentions else (text.author if not " " in text.content else memSearch(text))
        if target:
            emb = discord.Embed(description = target.activity.name if target.activity else "", color = target.color)
            # Discord occasionally reports people with an activity as not having one; if so, go invisible and back online
            emb.set_author(name = str(target), icon_url = target.avatar_url)
            emb.set_thumbnail(url = target.avatar_url)
            emb.add_field(name = "Registered for Discord on", value = str(target.created_at)[:-7] + " UTC", inline = True)
            emb.add_field(name = "Joined this server on", value = str(target.joined_at)[:-7] + " UTC", inline = True)
            if len(target.roles) > 1: # Every user has the "@everyone" role, so check if they have more roles than that
                emb.add_field(name = "Roles", value = ", ".join(role.mention for role in target.roles[:0:-1]), inline = False)
                # Reverse target.roles in order to make them display in decreasing order of power
            return emb
    except:
        pass
    return discord.Embed(title = "Invalid target!", description = "Please choose a valid target. Valid targets are either a ping or a username.", color = 0xff0000)

def sparPins():
    emb = discord.Embed(title = "How to use this channel.", description = "", color = 0xfff994)
    emb.add_field(name = "To spar someone from your region:", value = "Do the command !spar <region> <other info>. For instance, to find a diamond from US-E to play 2s with, I would do:\n!spar US-E looking for a diamond 2s partner.\nValid regions are US-E, US-W, BRZ, EU, JPN, AUS, SEA. !spar has a 2 hour cooldown. Please use the roles channel to give yourself the correct roles.", inline = False)
    emb.add_field(name = "If you don't want to get pings:", value = "Remove your region role. Otherwise, responding 'no' to calls to spar is annoying and counterproductive, and will earn you a warning.", inline = False)
    return emb

def av(text):
    try:
        target = text.mentions[0] if text.mentions else (text.author if not text.guild or not " " in text.content else memSearch(text))
        if target:
            emb = discord.Embed(title = "", description = "", color = target.color)
            emb.set_author(name = str(target), icon_url = target.avatar_url)
            emb.set_image(url = target.avatar_url)
            return emb
    except:
        pass
    return discord.Embed(title = "Invalid target!", description = "Please choose a valid target. Valid targets are either a ping or a username.", color = 0xff0000)

def commands(text):
    emb = discord.Embed(title = "Beardless Bot Commands", description = "!commands to pull up this list", color = 0xfff994)
    commandNum = 15 if not text.guild else 20 if text.author.guild_permissions.manage_messages else 17
    commands = (("!register", "Registers you with the currency system."),
        ("!balance", "Checks your BeardlessBucks balance. You can write !balance <@someone>/<username> to see that person's balance."),
        ("!bucks", "Shows you an explanation for how BeardlessBucks work."),
        ("!reset", "Resets you to 200 BeardlessBucks."),
        ("!fact", "Gives you a random fun fact."),
        ("!source", "Shows you the source of most facts used in !fact."),
        ("!flip [number]", "Bets a certain amount on flipping a coin. Heads you win, tails you lose. Defaults to 10."),
        ("!blackjack [number]", "Starts up a game of blackjack. Once you're in a game, you can use !hit and !stay to play."),
        ("!d[number][+/-][modifier]", "Rolls a [number]-sided die and adds or subtracts the modifier. Example: !d8+3, or !d100-17."),
        ("!random legend/weapon", "Randomly selects a Brawlhalla legend or weapon for you."),
        ("!add", "Gives you a link to add this bot to your server."),
        ("!av [user/username]", "Display a user's avatar. Write just !av if you want to see your own avatar."),
        ("![animal name]", "Gets a random cat/dog/duck/fish/fox/rabbit/panda/lizard/koala/bird picture. Example: !duck"),
        ("!define [word]", "Shows you the definition(s) of a word."),
        ("!ping", "Checks Beardless Bot's latency."),
        ("!buy red/blue/pink/orange", "Takes away 50000 BeardlessBucks from your account and grants you a special color role."),
        ("!info [user/username]", "Displays general information about a user. Write just !info to see your own info."),
        ("!purge [number]", "Mass-deletes messages"),
        ("!mute [target] [duration]", "Mutes someone for an amount of time. Accepts either seconds, minutes, or hours."),
        ("!unmute [target]", "Unmutes the target."))
    for command in commands[:commandNum]:
        emb.add_field(name = command[0], value = command[1], inline = True)
    return emb