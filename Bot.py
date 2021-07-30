# Beardless Bot
# Author: Lev Bernstein
# Version: Full Release 1.1.0

# Default modules:
import asyncio
import csv
import requests
from collections import OrderedDict
from datetime import datetime
from math import floor
from operator import itemgetter
from random import choice, randint
from sys import exit as sysExit
from time import time

# Installed modules:
import discord
from discord.ext import commands
from discord.utils import get

# Other:
from animals import *
from blackjack import *
from define import *
from dice import *
from eggTweet import *
from fact import *

try:
    with open("resources/token.txt", "r") as f: # in token.txt, paste in your own Discord API token
        token = f.readline()
except Exception as err:
    print(err)
    sysExit(-1)

try:
    with open("resources/secretWord.txt") as f:
        secretWord = f.readline()
except:
    secretWord = "".join(str(randint(0, 9)) for n in range(20))

secretFound = False

# This dictionary is for keeping track of pings in the various looking-for-spar channels.
sparPings = {}

games = [] # Stores the active instances of blackjack. A list works for storing these, but once the Bot reaches verified status
# (more than 75 servers), will have to switch to a more efficient data structure

def memSearch(text): # method for finding a user based on username if no @ is provided
    term = (text.content.split(" ", 1)[1]).lower()
    for member in text.guild.members:
        if term in member.name.lower():
            return member
    return None

client = discord.Client(intents = discord.Intents.all())
class DiscordClass(client):
    
    @client.event
    async def on_ready():
        print("Beardless Bot online!")
        try:
            await client.change_presence(activity = discord.Game(name = 'try !blackjack and !flip'))
            print("Status updated!")
        except discord.HTTPException:
            print("Failed to update status! You might be restarting the bot too many times.")
        intents = discord.Intents.default()
        intents.members = True
        try:
            with open("images/prof.png", "rb") as g:
                pic = g.read()
                await client.user.edit(avatar = pic)
                print("Avatar live!")
        except discord.HTTPException:
            print("Avatar failed to update! You might be sending requests too quickly.")
        except FileNotFoundError:
            print("Avatar file not found! Check your directory structure.")
        print("Beardless Bot is in " + str(len(client.guilds)) + " servers.")
        global sparPings
        for server in client.guilds:
            sparPings[str(server.id)] = {'jpn': 0, 'brz': 0, 'us-w': 0, 'us-e': 0, 'sea': 0, 'aus': 0, 'eu': 0}
    
    @client.event
    async def on_guild_join(guild):
        global sparPings
        sparPings[str(guild.id)] = {'jpn': 0, 'brz': 0, 'us-w': 0, 'us-e': 0, 'sea': 0, 'aus': 0, 'eu': 0}
        print("Just joined " + guild.name + "!")
        try:
            for key, value in sparPings[str(guild.id)].items():
                role = get(guild.roles, name = key.upper())
                if not role:
                    await guild.create_role(name = key.upper(), mentionable = False)
        except:
            print("Not given admin perms in " + guild.name + "...")
            for channel in guild.channels:
                try:
                    emb = discord.Embed(title = "I need admin perms!", description = "Beardless Bot requires permissions in order to do just about anything. Without them, I can't do much, so I'm leaving. If you add me back to this server, please make sure to leave checked the box that grants me the Administrator permission.", color = 0xff0000)
                    emb.set_author(name = "Beardless Bot", icon_url = "https://cdn.discordapp.com/avatars/654133911558946837/78c6e18d8febb2339b5513134fa76b94.webp?size=1024")
                    await channel.send(embed = emb)
                    break
                except:
                    pass
            await guild.leave()
            print("Left " + guild.name + ". Beardless Bot is now in " + str(len(client.guilds)) + " servers.")
        return
        
    @client.event
    async def on_message_delete(text):
        if (text.content or text.author.id != 654133911558946837 or text.channel.name != "bb-log") and text.guild: # Prevents embeds from causing a loop
            for channel in text.guild.channels:
                if channel.name == "bb-log":
                    emb = discord.Embed(description = "**Deleted message sent by " + text.author.mention + " in **" + text.channel.mention + "\n" + text.content, color = 0xff0000)
                    emb.set_author(name = str(text.author), icon_url = text.author.avatar_url)
                    await channel.send(embed = emb)
                    break
        return
    
    @client.event
    async def on_bulk_message_delete(textArr):
        text = textArr[0]
        if text.guild:
            for channel in text.guild.channels:
                if channel.name == "bb-log":
                    try:
                        emb = discord.Embed(description = "Purged " + str(len(textArr) - 1) + " messages in " + text.channel.mention + ".", color = 0xff0000)
                        emb.set_author(name = "Purge!", icon_url = "https://cdn.discordapp.com/avatars/654133911558946837/78c6e18d8febb2339b5513134fa76b94.webp?size=1024")
                        await channel.send(embed = emb)
                    except:
                        pass
                    break
        return
    
    @client.event
    async def on_message_edit(before, after):
        if before.guild and before.content != after.content: # This check prevents embeds from getting logged, as they have no "content" field
            for channel in before.guild.channels:
                if channel.name == "bb-log":
                    try:
                        emb = discord.Embed(description = "Messaged edited by" + before.author.mention + " in " + before.channel.mention, color = 0xffff00)
                        emb.set_author(name = str(before.author), icon_url = before.author.avatar_url)
                        emb.add_field(name = "Before:", value = before.content, inline = False)
                        emb.add_field(name = "After:", value = after.content + "\n[Jump to Message](" + after.jump_url +")", inline = False)
                        await channel.send(embed = emb)
                    except:
                        pass
                    break
        return
    
    @client.event
    async def on_reaction_clear(text, reactions):
        if text.guild:
            for channel in text.guild.channels:
                if channel.name == "bb-log":
                    try:
                        emb = discord.Embed(description = "Reactions cleared from message sent by" + text.author.mention + " in " + text.channel.mention, color = 0xff0000)
                        emb.set_author(name = str(text.author), icon_url = text.author.avatar_url)
                        emb.add_field(name = "Message content:", value = text.content)
                        emb.add_field(name = "Reactions:", value = ", ".join(str(reaction) for reaction in reactions))
                        await channel.send(embed = emb)
                    except:
                        pass
                    break
        return
    
    @client.event
    async def on_guild_channel_delete(ch):
        for channel in ch.guild.channels:
            if channel.name == "bb-log":
                emb = discord.Embed(description = "Channel \"" + ch.name + "\" deleted", color = 0xff0000)
                emb.set_author(name = "Channel deleted", icon_url = "https://cdn.discordapp.com/avatars/654133911558946837/78c6e18d8febb2339b5513134fa76b94.webp?size=1024")
                await channel.send(embed = emb)
                break
        return
    
    @client.event
    async def on_guild_channel_create(ch):
        for channel in ch.guild.channels:
            if channel.name == "bb-log":
                emb = discord.Embed(description = "Channel " + ch.mention + " created", color = 0x00ff00)
                emb.set_author(name = "Channel created", icon_url = "https://cdn.discordapp.com/avatars/654133911558946837/78c6e18d8febb2339b5513134fa76b94.webp?size=1024")
                await channel.send(embed = emb)
                break
        return
    
    @client.event
    async def on_member_join(member):
        for channel in member.guild.channels:
            if channel.name == "bb-log":
                emb = discord.Embed(description = "Member " + member.mention + " joined\nAccount registered on " + str(member.created_at)[:-7] + "\nID: " + str(member.id), color = 0x00ff00)
                emb.set_author(name = str(member) + " joined the server", icon_url = member.avatar_url)
                await channel.send(embed = emb)
                break
        return
    
    @client.event
    async def on_member_remove(member):
        for channel in member.guild.channels:
            if channel.name == "bb-log":
                emb = discord.Embed(description = "Member " + member.mention + " left\nID: " + str(member.id), color = 0xff0000)
                emb.set_author(name = str(member) +" left the server", icon_url = member.avatar_url)
                if len(member.roles) > 1:
                    emb.add_field(name = "Roles:", value = ", ".join(role.mention for role in member.roles[:1:-1]))
                await channel.send(embed = emb)
                break
        return
    
    @client.event
    async def on_member_update(before, after):
        for channel in after.guild.channels:
            if channel.name == "bb-log":
                if before.nick != after.nick:
                    emb = discord.Embed(description = "Nickname of" + after.mention + " changed", color = 0xffff00)
                    emb.set_author(name = str(after), icon_url = after.avatar_url)
                    emb.add_field(name = "Before:", value = before.nick, inline = False)
                    emb.add_field(name = "After:", value = after.nick, inline = False)
                    await channel.send(embed = emb)
                elif before.roles != after.roles:
                    newRole = None
                    for role in before.roles:
                        if role not in after.roles:
                            newRole = role
                            break
                    if not newRole:
                        for role in after.roles:
                            if role not in before.roles:
                                newRole = role
                                break
                    removed = [" removed from ", 0xff0000] if len(before.roles) > len(after.roles) else [" added to ", 0x00ff00]
                    emb = discord.Embed(description = "Role " + newRole.mention + removed[0]  + after.mention, color = removed[1])
                    emb.set_author(name = str(after), icon_url = after.avatar_url)
                    await channel.send(embed = emb)
                break
        return
    
    @client.event
    async def on_member_ban(guild, member):
        for channel in guild.channels:
            if channel.name == "bb-log":
                emb = discord.Embed(description = "Member " + member.mention + " banned\n" + member.name, color = 0xff0000)
                emb.set_author(name = "Member banned", icon_url = member.avatar_url)
                emb.set_thumbnail(url = member.avatar_url)
                await channel.send(embed = emb)
                break
        return
    
    @client.event
    async def on_member_unban(guild, member):
        for channel in guild.channels:
            if channel.name == "bb-log":
                emb = discord.Embed(description = "Member " + member.mention + " unbanned\n" + member.name, color = 0x00ff00)
                emb.set_author(name = "Member unbanned", icon_url = member.avatar_url)
                emb.set_thumbnail(url = member.avatar_url)
                await channel.send(embed = emb)
                break
        return
    
    # TODO: switch to command event instead of on_message for most commands
    @client.event
    async def on_message(text):
        if not text.author.bot:
            msg = text.content.lower()
            if msg.startswith('!bj') or msg.startswith('!bl'):
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                report = "You need to register first! Type !register to get started, " + text.author.mention + "."
                strbet = '10' # Bets default to 10. If someone just types !blackjack, they will bet 10 by default.
                if msg.startswith('!blackjack') and len(msg) > 11:
                    strbet = msg.split('!blackjack ',1)[1]
                elif msg == "!blackjack" or msg == "!bl":
                    pass
                elif msg.startswith('!bl ') and len(msg) > 4:
                    strbet = msg.split('!bl ',1)[1]
                elif msg.startswith('!bl'):
                    # This way, other bots' commands that start with !bl won't trigger blackjack.
                    return
                elif msg.startswith('!bj') and len(msg) > 4:
                    strbet = msg.split('!bj ',1)[1]
                allBet = False
                if strbet == "all":
                    allBet = True
                    bet = 0
                else:
                    try:
                        bet = int(strbet)
                    except:
                        bet = 10
                        if ' ' in msg:
                            print("Failed to cast bet to int! Bet msg: " + msg)
                            bet = -1
                if bet < 0:
                    report = "Invalid bet. Please choose a number greater than or equal to 0."
                else:
                    with open('resources/money.csv', 'r') as csvfile: # In future, maybe switch to some kind of NoSQL db like Mongo instead of storing in a csv
                        reader = csv.reader(csvfile, delimiter = ',')
                        for row in reader:
                            if str(text.author.id) == row[0]:
                                bank = int(row[1])
                                if allBet:
                                    bet = bank
                                exist = False
                                for i in range(len(games)):
                                    if games[i].getUser() == text.author:
                                        exist = True
                                        report = "You already have an active game, " + text.author.mention + "."
                                        break      
                                if not exist:
                                    report = "You do not have enough BeardlessBucks to bet that much, " + text.author.mention + "!"
                                    if bet <= bank:
                                        x = Instance(text.author, bet)
                                        report = x.message
                                        if x.perfect():
                                            totalsum = bank + bet
                                            oldliner = str(text.author.id) + "," + str(bank) + "," + row[2]
                                            liner = str(text.author.id) + "," + str(totalsum) + "," + str(text.author)
                                            texter = open("resources/money.csv", "r")
                                            texter = ''.join([i for i in texter]).replace(oldliner, liner)
                                            with open("resources/money.csv", "w") as money:
                                                money.writelines(texter)
                                        else:
                                            games.append(x)
                                break
                await text.channel.send(embed = discord.Embed(title = "Beardless Bot Blackjack", description = report, color = 0xfff994))
                return
            
            if msg == '!deal' or msg == '!hit':
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                report = "You do not currently have a game of blackjack going, " + text.author.mention + ". Type !blackjack to start one."
                for i in range(len(games)):
                    if games[i].getUser() == text.author:
                        gamer = games[i]
                        report = gamer.deal()
                        if gamer.checkBust() or gamer.perfect():
                            bet = gamer.bet * (-1 if gamer.checkBust() else 1)
                            with open('resources/money.csv', 'r') as csvfile:
                                reader = csv.reader(csvfile, delimiter = ',')
                                for row in reader:
                                    if str(text.author.id) == row[0]:
                                        totalsum = int(row[1]) + bet
                                        oldliner = row[0] + "," + row[1] + "," + row[2]
                                        liner = str(text.author.id) + "," + str(totalsum) + "," + str(text.author)
                                        texter = open("resources/money.csv", "r")
                                        texter = ''.join([j for j in texter]).replace(oldliner, liner)
                                        with open("resources/money.csv", "w") as money:
                                            money.writelines(texter)
                                        games.pop(i)
                                        break
                        break
                await text.channel.send(embed = discord.Embed(title = "Beardless Bot Blackjack", description = report, color = 0xfff994))
                return
            
            if msg =='!stay' or msg == '!stand':
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                report = "You do not currently have a game of blackjack going, " + text.author.mention + ". Type !blackjack to start one."
                for i in range(len(games)):
                    if games[i].getUser() == text.author:
                        gamer = games[i]
                        bet = gamer.bet
                        result = gamer.stay()
                        report = "The dealer has a total of " + str(gamer.dealerSum) + "."
                        if result == -3:
                            report += " That's closer to 21 than your sum of " + str(sum(gamer.cards)) + ". You lose"
                            bet *= -1
                            if bet:
                                report +=  ". Your loss has been deducted from your balance"
                        elif result == 0:
                            report += " That ties your sum of " + str(sum(gamer.cards))
                            if bet:
                                report += ". Your money has been returned"
                        elif result == 3:
                            report += " You're closer to 21 with a sum of " + str(sum(gamer.cards))
                        elif result == 4:
                            report += " You have a sum of " + str(sum(gamer.cards)) + ". The dealer busts"
                        if (result == 3 or result == 4) and bet:
                            report += ". You win! Your winnings have been added to your balance"
                        if result and bet:
                            with open('resources/money.csv', 'r') as csvfile:
                                reader = csv.reader(csvfile, delimiter = ',')
                                for row in reader:
                                    if str(text.author.id) == row[0]:
                                        totalsum = int(row[1]) + bet
                                        oldliner = row[0] + "," + row[1] + "," + row[2]
                                        liner = str(text.author.id) + "," + str(totalsum) + "," + str(text.author)
                                        texter = open("resources/money.csv", "r")
                                        texter = ''.join([j for j in texter]).replace(oldliner, liner)
                                        with open("resources/money.csv", "w") as money:
                                            money.writelines(texter)
                                        break
                        elif not bet:
                            report += (". Y" if not result else ". However, y") + "ou bet nothing, so your balance has not changed"
                        report += ", " + text.author.mention + "."
                        games.pop(i)
                        break
                await text.channel.send(embed = discord.Embed(title = "Beardless Bot Blackjack", description = report, color = 0xfff994))
                return
            
            if secretWord in msg:
                global secretFound
                if not secretFound:
                    secretFound = True
                    await text.channel.send(embed = discord.Embed(title = "Well done! You found the secret word," + secretWord + "!", description = "Ping Captain No-Beard for your prize!",  color = 0xfff994))
                    print("Secret word found!")
                return
                
            if msg == "!hint" or msg == "!hints":
                if not secretWord.isnumeric():
                    with open("resources/hints.txt", "r") as f:
                        hints = f.read().splitlines()
                    emb = discord.Embed(title = "Hints for Beardless Bot's Secret Word", description = "", color = 0xfff994)
                    for i in range(len(hints)):
                        emb.add_field(name = str(i+1), value = hints[i], inline = True)
                    await text.channel.send(embed = emb)
                else:
                    await text.channel.send("Secret word has not been defined!")
                return
            
            if msg.startswith('!flip'):
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                allBet = False
                strbet = msg.split('!flip ',1)[1] if len(msg) > 6 else 10
                if strbet == "all":
                    allBet = True
                    bet = 0
                else:
                    try:
                        bet = int(strbet)
                    except:
                        bet = 10
                        if ' ' in msg:
                            print("Failed to cast bet to int! Bet msg: " + msg)
                            bet = -1
                if (not allBet) and int(strbet) < 0:
                    report = "Invalid bet amount. Please choose a number >-1, " + text.author.mention + "."
                else:
                    report = "You need to register first! Type !register, " + text.author.mention + "!"
                    with open('resources/money.csv', 'r') as csvfile:
                        reader = csv.reader(csvfile, delimiter = ',')
                        for row in reader:
                            if str(text.author.id) == row[0]:
                                bank = int(row[1])
                                if allBet:
                                    bet = bank
                                found = False
                                for i in range(len(games)):
                                    if games[i].getUser() == text.author:
                                        found = True
                                        break
                                if found:
                                    report = "Please finish your game of blackjack first, " +  text.author.mention + "."
                                elif bet <= bank: # As of 11 AM ET on January 22nd, 2021, there have been 31765 flips that got heads and 31664 flips that got tails in the eggsoup server. This is 50/50. Stop complaining.
                                    result = randint(0,1)
                                    report = ("Heads! You win! Your winnings have been added to" if result else "Tails! You lose! Your loss has been deducted from") + " your balance, " + text.author.mention + "."
                                    totalsum = bank + (bet * (1 if result else -1))
                                    if not bet:
                                        report += " However, you bet nothing, so your balance will not change."
                                    else:
                                        oldliner = row[0] + "," + row[1] + "," + row[2]
                                        liner = row[0] + "," + str(totalsum) + "," + str(text.author)
                                        texter = open("resources/money.csv", "r")
                                        texter = ''.join([i for i in texter]).replace(oldliner, liner)
                                        with open("resources/money.csv", "w") as money:
                                            money.writelines(texter)
                                else:
                                    report = "You do not have enough BeardlessBucks to bet that much, " + text.author.mention + "!"
                                break
                await text.channel.send(embed = discord.Embed(title = "Beardless Bot Coin Flip", description = report, color = 0xfff994))
                return
            
            if msg.startswith('!buy'): # Requires roles named special blue, special pink, special orange, and special red.
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                if not text.guild:
                    await text.channel.send("This command can only be used in a server.")
                    return
                if msg == "!buy":
                    report = "Invalid color. Choose blue, red, orange, or pink, " + text.author.mention + "."
                else:
                    color = msg.split(" ", 1)[1]
                    role = get(text.guild.roles, name = 'special ' + color)
                    if color not in ["blue", "pink", "orange", "red"]:
                        report = "Invalid color. Choose blue, red, orange, or pink, " + text.author.mention + "."
                    elif not role:
                        report = "Special color roles do not exist in this server, " + text.author.mention + "."
                    elif role in text.author.roles:
                        report = "You already have this special color, " + text.author.mention + "."
                    else:
                        report = "Not enough Beardess Bucks. You need 50000 to buy a special color, " + text.author.mention + "."
                        with open('resources/money.csv', 'r') as csvfile:
                            reader = csv.reader(csvfile, delimiter = ',')
                            for row in reader:
                                if str(text.author.id) == row[0]:
                                    if  50000 <= int(row[1]):
                                        oldliner = row[0] + "," + row[1] + "," + row[2]
                                        liner = row[0] + "," + str(int(row[1]) - 50000) + "," + str(text.author)
                                        texter = open("resources/money.csv", "r")
                                        texter = ''.join([i for i in texter]).replace(oldliner, liner)
                                        with open("resources/money.csv", "w") as money:
                                            money.writelines(texter)
                                        await text.author.add_roles(role)
                                        report = "Color \"special " + color + "\" purchased successfully, " + text.author.mention + "!"
                                    break
                await text.channel.send(embed = discord.Embed(title = "Beardless Bot Special Colors", description = report, color = 0xfff994))
                return
            
            if msg.startswith('!av'):
                target = text.mentions[0] if text.mentions else (text.author if not " " in msg else memSearch(text))
                if not target:
                    await text.channel.send("Invalid target!")
                    return
                try:
                    await text.channel.send(target.avatar_url)
                except discord.NotFound:
                    await text.channel.send(embed = discord.Embed(title = "Error!", description = "Discord Member " + target.mention + " not found!", color = 0xfff994))
                return
                
            if msg.startswith('!mute'):
                if not text.guild:
                    await text.channel.send("This command can only be used in a server.")
                    return
                if text.author.guild_permissions.manage_messages:
                    if text.mentions:
                        target = text.mentions[0]
                        duration = msg.split('>', 1)[1]
                        if str(target.id) == "654133911558946837": # If user tries to mute Beardless Bot:
                            await text.channel.send("I am too powerful to be muted. Stop trying.")
                            return
                        print("Author: " + str(text.author.id) + " muting target: " + str(target.id))
                        role = get(text.guild.roles, name = 'Muted')
                        if not role:
                            role = await text.guild.create_role(name = "Muted", colour = discord.Colour(0x818386), permissions = discord.Permissions(send_messages = False, read_messages = True))
                        mTime = 0.0
                        mString = None
                        if 'h' in duration:
                            duration = duration[1:]
                            duration = duration.split('h', 1)[0]
                            mString = " hours" if int(duration) != 1 else " hour"
                            mTime = float(duration) * 3600.0
                        elif 'm' in duration:
                            duration = duration[1:]
                            duration = duration.split('m', 1)[0]
                            mString = " minutes" if int(duration) != 1 else " minute"
                            mTime = float(duration) * 60.0
                        elif 's' in duration:
                            duration = duration[1:]
                            duration = duration.split('s', 1)[0]
                            mString = " seconds" if int(duration) != 1 else " second"
                            mTime = float(duration)
                        await target.add_roles(role)
                        emb = discord.Embed(title = "Beardless Bot Mute", description = "Muted " + target.mention + ((" for " + duration + mString + ".") if mTime else "."), color = 0xfff994)
                        emb.set_author(name = str(text.author), icon_url = text.author.avatar_url)
                        await text.channel.send(embed = emb)
                        for channel in text.guild.channels:
                            if channel.name == "bb-log":
                                emb = discord.Embed(title = "Beardless Bot Mute", description = "Muted " + target.mention + ((" for " + duration + mString) if mTime else "") + " in " + text.channel.mention + ".", color = 0xff0000)
                                emb.set_author(name = str(text.author), icon_url = text.author.avatar_url)
                                await channel.send(embed = emb)
                                break
                        if mTime: # Autounmute:
                            print("Muted for " + str(mTime))
                            await asyncio.sleep(mTime)
                            await target.remove_roles(role)
                            print("Unmuted " + target.name)
                            for channel in text.guild.channels:
                                if channel.name == "bb-log":
                                    emb = discord.Embed(title = "Beardless Bot Mute", description = "Unmuted " + target.mention + ".", color = 0x00ff00)
                                    emb.set_author(name = str(text.author), icon_url = text.author.avatar_url)
                                    await channel.send(embed = emb)
                                    break
                    else:
                        await text.channel.send("Invalid target!")
                else:
                    await text.channel.send("You do not have permission to use this command, " + text.author.mention + ".")
                return
            
            if msg.startswith('!unmute') or msg.startswith('-unmute'):
                if text.author.guild_permissions.manage_messages:
                    if not text.mentions:
                        await text.channel.send("Invalid target!")
                        return
                    target = text.mentions[0]
                    role = get(text.guild.roles, name = 'Muted')
                    await target.remove_roles(role)
                    await text.channel.send(embed = discord.Embed(title = "Beardless Bot Unmute", description = "Unmuted " + target.mention + ".", color = 0xfff994))
                    for channel in text.guild.channels:
                        if channel.name == "bb-log":
                            emb = discord.Embed(title = "Beardless Bot Mute", description = "Unmuted " + target.mention + ".", color = 0x00ff00)
                            emb.set_author(name = str(text.author), icon_url = text.author.avatar_url)
                            await channel.send(embed = emb)
                            break
                else:
                    await text.channel.send("You do not have permission to use this command, " + text.author.mention + ".")
                return

            if msg == '!playlist' or msg == '!music':
                await text.channel.send('Here\'s my playlist (discord will only show the first hundred songs): https://open.spotify.com/playlist/2JSGLsBJ6kVbGY1B7LP4Zi?si=Zku_xewGTiuVkneXTLCqeg')
                return
            
            if msg == '!leaderboard' or msg == "!leaderboards" or msg == '!lb':
                diction = {}
                emb = discord.Embed(title = "BeardlessBucks Leaderboard", description = "", color = 0xfff994)
                with open('resources/money.csv') as csvfile:
                    reader = csv.reader(csvfile, delimiter = ',')
                    for row in reader:
                        if int(row[1]): # Don't bother displaying info for people with 0 BeardlessBucks
                            diction[(row[2])[:-5]] = int(row[1])
                sortedDict = OrderedDict(sorted(diction.items(), key = itemgetter(1))) # Sort by value for each key in diction, which is Beardless Bucks balance
                for i in range(len(sortedDict.items()) if len(sortedDict) < 10 else 10):
                    tup = sortedDict.popitem()
                    emb.add_field(name = (str(i + 1) + ". " + tup[0]), value = str(tup[1]), inline = True)
                await text.channel.send(embed = emb)
                return
            
            if msg.startswith('!dice'):
                await text.channel.send(embed = discord.Embed(title = "Beardless Bot Dice", description = "Enter !d[number][+/-][modifier] to roll a [number]-sided die and add or subtract a modifier. For example: !d8+3, or !d100-17, or !d6.", color = 0xfff994))
                return
            
            if msg == '!reset':
                report = 'You have been reset to 200 BeardlessBucks, ' + text.author.mention + "."
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                with open('resources/money.csv') as csvfile:
                    reader = csv.reader(csvfile, delimiter = ',')
                    exist = False
                    for row in reader:
                        if str(text.author.id) == row[0]:
                            exist = True
                            oldliner = row[0] + "," + row[1] + "," + row[2]
                            liner = row[0] + "," + str(200) + "," + str(text.author)
                            texter = open("resources/money.csv", "r")
                            texter = ''.join([i for i in texter]).replace(oldliner, liner)
                            with open("resources/money.csv", "w") as money:
                                money.writelines(texter)
                    if not exist:
                        report ="Successfully registered. You have 300 BeardlessBucks, " + text.author.mention + "."
                        with open('resources/money.csv', 'a') as money:
                            writer = csv.writer(csvfile)
                            newline = "\r\n" + str(text.author.id) + ",300," + str(text.author)
                            money.write(newline)
                await text.channel.send(embed = discord.Embed(title = "Beardless Bucks Reset", description = report, color = 0xfff994))
                return
            
            if msg.startswith("!balance") or msg.startswith("!bal"):
                report = ""
                if msg == ("!balance") or msg == ("!bal"):
                    selfMode = True
                    if ',' in text.author.name:
                        await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                        return
                    authorstring = str(text.author.id)
                elif msg.startswith("!balance ") or msg.startswith("!bal "):
                    selfMode = False
                    target = text.mentions[0] if text.mentions else (text.author if not " " in msg else memSearch(text))
                    if target:
                        try:
                            authorstring = str(target.id)
                        except discord.NotFound as err:
                            report = "Discord Member " + target.mention + " not found!"
                            print(err)
                    else:
                        report = "Invalid user! Please @ a user when you do !balance (or enter their username), or do !balance without a target to see your own balance, " + text.author.mention + "."
                else:
                    return
                if not report:
                    report = "Oops! You aren't in the system! Type \"!register\" to get a starting balance, " + text.author.mention + "." if selfMode else "Oops! That user isn't in the system! They can type \"!register\" to get a starting balance."
                    with open('resources/money.csv') as csvfile:
                        reader = csv.reader(csvfile, delimiter = ',')
                        for row in reader:
                            if authorstring == row[0]:
                                if selfMode:
                                    report = "Your balance is " + row[1] + " BeardlessBucks, " + text.author.mention + "."
                                else:
                                    report = target.mention + "'s balance is " + row[1] + " BeardlessBucks."
                                break
                await text.channel.send(embed = discord.Embed(title = "Beardless Bucks Balance", description = report, color = 0xfff994))
                return
            
            if msg == "!register": # Make sure resources/money.csv is not open in any other program
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                with open('resources/money.csv') as csvfile:
                    reader = csv.reader(csvfile, delimiter = ',')
                    exist = False
                    for row in reader:
                        if str(text.author.id) == row[0]:
                            exist = True
                            report = "You are already in the system! Hooray! You have " + row[1] + " BeardlessBucks, " + text.author.mention + "."
                            break
                    if not exist:
                        report = "Successfully registered. You have 300 BeardlessBucks, " + text.author.mention + "."
                        with open('resources/money.csv', 'a') as money:
                            writer = csv.writer(csvfile)
                            newline = "\r\n" + str(text.author.id) + ",300," + str(text.author)
                            money.write(newline)
                    await text.channel.send(embed = discord.Embed(title = "Beardless Bucks Registration", description = report, color = 0xfff994))
                    return
            
            if msg == "!bucks":
                await text.channel.send(embed = discord.Embed(title = "Beardless Bucks", description = "BeardlessBucks are this bot's special currency. You can earn them by playing games. First, do !register to get yourself started with a balance.", color = 0xfff994))
                return
            
            if msg == "!hello" or msg == "!hi":
                answers = ["How ya doin?", "Yo!", "What's cookin?", "Hello!", "Ahoy!", "Hi!", "What's up?", "Hey!", "How's it goin?", "Greetings!"]
                await text.channel.send(choice(answers))
                return
            
            if msg == "!source":
                await text.channel.send(embed = discord.Embed(title = "Beardless Bot Fun Facts", description = "Most facts taken from [this website](https://www.thefactsite.com/1000-interesting-facts/).", color = 0xfff994))
                return
            
            if msg == "!add" or msg == "!join":
                emb = discord.Embed(title = "Want to add this bot to your server?", description = "[Click this link!](https://discord.com/api/oauth2/authorize?client_id=654133911558946837&permissions=8&scope=bot)", color = 0xfff994)
                emb.set_thumbnail(url = "https://cdn.discordapp.com/avatars/654133911558946837/78c6e18d8febb2339b5513134fa76b94.webp?size=1024")
                await text.channel.send(embed = emb)
                return
            
            if msg == "!rohan":
                await text.channel.send(file = discord.File('images/cute.png'))
                return
            
            if msg.startswith("!random"):
                try:
                    ranType = msg.split(' ', 1)[1]
                    if ranType == "legend" or ranType == "weapon":
                        legends = ["Bodvar", "Cassidy", "Orion", "Lord Vraxx", "Gnash", "Queen Nai", "Hattori", "Sir Roland", "Scarlet", "Thatch", "Ada", "Sentinel", "Lucien", "Teros", "Brynn", "Asuri", "Barraza", "Ember", "Azoth", "Koji", "Ulgrim", "Diana", "Jhala", "Kor", "Wu Shang", "Val", "Ragnir", "Cross", "Mirage", "Nix", "Mordex", "Yumiko", "Artemis", "Caspian", "Sidra", "Xull", "Kaya", "Isaiah", "Jiro", "Lin Fei", "Zariel", "Rayman", "Dusk", "Fait", "Thor", "Petra", "Vector", "Volkov", "Onyx", "Jaeyun", "Mako", "Magyar", "Reno"]
                        weapons = ["Sword", "Spear", "Orb", "Cannon", "Hammer", "Scythe", "Greatsword", "Bow", "Gauntlets", "Katars", "Blasters", "Axe"]
                        await text.channel.send(embed = discord.Embed(title = "Random " + ranType, description = "Your " + ("legend" if ranType == "legend" else "weapon") + " is " + choice(legends if ranType == "legend" else weapons) + ".", color = 0xfff994))
                    else:
                        await text.channel.send(embed = discord.Embed(title = "Invalid random!", description = "Please do !random legend or !random weapon.", color = 0xfff994))
                except:
                    await text.channel.send(embed = discord.Embed(title = "Brawlhalla Randomizer", description = "Please do !random legend or !random weapon to get a random legend or weapon.", color = 0xfff994))
                return
            
            if msg == "!fact":
                await text.channel.send(embed = discord.Embed(title = "Beardless Bot Fun Fact #" + str(randint(1,111111111)), description = fact(), color = 0xfff994))
                return
            
            if msg == "!animals":
                emb = discord.Embed(title = "Animals photo commands:", description = "", color = 0xfff994)
                emb.add_field(name = "!dog", value = "Can also do !dog breeds to see breeds you can get pictures of with !dog <breed>", inline = False)
                emb.add_field(name = "!cat", value = "_ _", inline = True)
                emb.add_field(name = "!duck", value = "_ _", inline = True)
                emb.add_field(name = "!fish", value = "_ _", inline = True)
                emb.add_field(name = "!fox", value = "_ _", inline = True)
                emb.add_field(name = "!rabbit", value = "_ _", inline = True)
                emb.add_field(name = "!panda", value = "_ _", inline = True)
                emb.add_field(name = "!bird", value = "_ _", inline = True)
                emb.add_field(name = "!koala", value = "_ _", inline = True)
                emb.add_field(name = "!lizard", value = "_ _", inline = True)
                await text.channel.send(embed = emb)
            
            if msg.startswith("!dog") or msg.startswith("!moose"):
                if msg.startswith("!dog moose") or msg.startswith("!moose"):
                    mooseNum = randint(1, 27)
                    mooseFile = 'images/moose/moose' + str(mooseNum) + (".gif" if mooseNum < 4 else ".jpg")
                    await text.channel.send(file = discord.File(mooseFile))
                    return
                try:
                    await text.channel.send(animal(msg[1:]))
                except:
                    await text.channel.send("Something's gone wrong with the dog API! Please ping my creator and he'll see what's going on.")
                return

            animalName = msg[1:].split(" ", 1)[0]
            if msg.startswith("!") and animalName in ["cat", "duck", "fish", "fox", "rabbit", "bunny", "panda", "bird", "koala", "lizard"]:
                try:
                    await text.channel.send(animal(animalName))
                except Exception as err:
                    print(err)
                    await text.channel.send("Something's gone wrong with the " + animalName + " API! Please ping my creator and he'll see what's going on.")
                return
           
            if (msg.startswith("!clear") or msg.startswith("!purge")) and text.guild:
                if not text.author.guild_permissions.manage_messages:
                    await text.channel.send("You do not have permission to use this command, " + text.author.mention + ".")
                    return
                try:
                   messageNumber = int(msg.split(" ", 1)[1]) + 1
                   await text.channel.purge(limit = messageNumber, check = lambda msg: not msg.pinned)
                except:
                    await text.channel.send("Invalid message number!")
                return

            if msg.startswith("!define "):
                await text.channel.send(embed = define(msg))
                return
            
            if msg == "!ping":
                startTime = datetime.now()
                message = await text.channel.send(embed = discord.Embed(title = "Pinging...", description = "", color = 0xfff994))
                emb = discord.Embed(title = "Pinged!", description = "Beardless Bot's latency is " + str(int((datetime.now() - startTime).total_seconds() * 1000)) + "ms.", color = 0xfff994)
                emb.set_thumbnail(url = "https://cdn.discordapp.com/avatars/654133911558946837/78c6e18d8febb2339b5513134fa76b94.webp?size=1024")
                await message.edit(embed = emb)
                return
            
            if msg.startswith('!d') and ((msg.split('!d',1)[1])[0]).isnumeric() and len(msg) < 12:
                # The isnumeric check ensures that you can't activate this command by typing !deal or !debase or anything else.
                report = roll(msg)
                if report:
                    await text.channel.send(embed = discord.Embed(title = "Rolling Dice...", description = "You got " + str(report) + ", " + text.author.mention, color = 0xfff994))
                else:
                    await text.channel.send(embed = discord.Embed(title = "Beardless Bot Dice", description = "Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100, as well as modifiers. No spaces allowed. Ex: !d4+3", color = 0xfff994))
                return
            
            if msg == "!commands" or msg == "!help":
                emb = discord.Embed(title = "Beardless Bot Commands", description = "!commands to pull up this list", color=0xfff994)
                emb.add_field(name = "!register", value = "Registers you with the currency system.", inline = True)
                emb.add_field(name = "!balance", value = "Checks your BeardlessBucks balance. You can write !balance <@someone>/<username> to see that person's balance.", inline = True)
                emb.add_field(name = "!bucks", value = "Shows you an explanation for how BeardlessBucks work.", inline = True)
                emb.add_field(name = "!reset", value = "Resets you to 200 BeardlessBucks.", inline = True)
                emb.add_field(name = "!fact", value = "Gives you a random fun fact.", inline = True)
                emb.add_field(name = "!source", value = "Shows you the source of most facts used in !fact.", inline = True)
                emb.add_field(name = "!flip [number]", value = "Bets a certain amount on flipping a coin. Heads you win, tails you lose. Defaults to 10.", inline = True)
                emb.add_field(name = "!blackjack [number]", value = "Starts up a game of blackjack. Once you're in a game, you can use !hit and !stay to play.", inline = True)
                emb.add_field(name = "!buy [red/blue/pink/orange]", value = "Takes away 50000 BeardlessBucks from your account and grants you a special color role.", inline = True)
                emb.add_field(name = "!leaderboard", value = "Shows you the BeardlessBucks leaderboard.", inline = True)
                emb.add_field(name = "!d[number][+/-][modifier]", value = "Rolls a [number]-sided die and adds or subtracts the modifier. Example: !d8+3, or !d100-17.", inline = True)
                emb.add_field(name = "!random [legend/weapon]", value = "Randomly selects a Brawlhalla legend or weapon for you.", inline = True)
                emb.add_field(name = "!add", value = "Gives you a link to add this bot to your server.", inline = True)
                emb.add_field(name = "!av [user/username]", value = "Display a user's avatar. Write just !av if you want to see your own avatar.", inline = True)
                emb.add_field(name = "!info [user/username]", value = "Displays general information about a user. Write just !info to see your own info.", inline = True)
                emb.add_field(name = "![animal name]", value = "Gets a random cat/dog/duck/fish/fox/rabbit/panda/lizard/koala/bird picture. Example: !duck", inline = True)
                emb.add_field(name = "!define [word]", value = "Shows you the definition(s) of a word.", inline = True)
                emb.add_field(name = "!ping", value = "Checks Beardless Bot's latency.", inline = True)
                if text.guild and text.author.guild_permissions.manage_messages:
                    emb.add_field(name = "!purge [number]", value = "Mass-deletes messages", inline = True)
                    emb.add_field(name = "!mute [target] [duration]", value = "Mutes someone for an amount of time. Excepts either seconds, minutes orhours. Requires a Muted role that has no send message perms.", inline = True)
                    emb.add_field(name = "!unmute [target]", value = "Unmutes the target.", inline = True)
                await text.channel.send(embed = emb)
                return
            
            if text.guild: # Server-specific commands; this check prevents an error caused by commands being used in DMs
                if msg.startswith("!info"):
                    target = text.mentions[0] if text.mentions else (text.author if not " " in msg else memSearch(text))
                    if not target:
                        await text.channel.send("Invalid target!")
                        return
                    emb = discord.Embed(description = str(target.activity) if target.activity else " ", color = target.color) # Discord occasionally reports people with an activity as not having them;
                    # if so, go invisible and back online
                    emb.set_author(name = str(target), icon_url = target.avatar_url)
                    emb.set_thumbnail(url = target.avatar_url)
                    emb.add_field(name = "Registered for Discord on", value = str(target.created_at)[:-7], inline = True)
                    emb.add_field(name = "Joined this server on", value = str(target.joined_at)[:-7], inline = True)
                    if len(target.roles) > 1: # Every user has the "@everyone" role, so check if they have more roles than that
                        emb.add_field(name = "Roles", value = ", ".join(role.mention for role in target.roles[:1:-1]), inline = False)
                        # I reverse target.roles in order to make them display in order of power; this way, it displays roles from your most powerful role to your least
                    await text.channel.send(embed = emb)
                    return
                
                if msg.startswith('!spar'):
                    report = "Please only use !spar in looking-for-spar, " + text.author.mention + "."
                    if text.channel.name == "looking-for-spar":
                        cooldown = 7200
                        report = "Please specify a valid region, " + text.author.mention + "! Valid regions are US-E, US-W, EU, AUS, SEA, BRZ, JPN. Check the pinned message if you need help, or do !pins."
                        tooRecent = None
                        found = False
                        global sparPings
                        global regions
                        splitMsg = msg.split(" ")
                        for server, pings in sparPings.items():
                            if server == str(text.guild.id):
                                for key, value in sparPings[server].items():
                                    if key in splitMsg:
                                        found = True
                                        if time() - value > cooldown:
                                            sparPings[server][key] = time()
                                            role = get(text.guild.roles, name = key.upper())
                                            if not role:
                                                role = await text.guild.create_role(name = key.upper(), mentionable = False)
                                            report = role.mention + " come spar " + text.author.mention + "!"
                                        else:
                                            tooRecent = value
                                        break
                                if not found:
                                    if "usw" in splitMsg or "use" in splitMsg:
                                        spelledRole = "us-w" if "usw" in splitMsg else "us-e"
                                        found = True
                                        if time() - sparPings[server][spelledRole] > cooldown:
                                            sparPings[server][spelledRole] = time()
                                            role = get(text.guild.roles, name = spelledRole.upper())
                                            if not role:
                                                role = await text.guild.create_role(name = spelledRole.upper(), mentionable = False)
                                            report = role.mention + " come spar " + text.author.mention + "!"
                                        else:
                                            tooRecent = sparPings[server][spelledRole]
                                break
                        if found and tooRecent:
                            seconds = 7200 - (time() - tooRecent)
                            minutes = floor(seconds/60)
                            seconds = floor(seconds % 60)
                            hours = floor(minutes/60)
                            minutes = minutes % 60
                            hourString = " hour, " if hours == 1 else " hours, "
                            minuteString = " minute, " if minutes == 1 else " minutes, "
                            secondString = " second." if seconds == 1 else " seconds."
                            report = "This region has been pinged too recently! Regions can only be pinged once every two hours, " + text.author.mention + ". You can ping again in " + str(hours) + hourString + str(minutes) + minuteString + "and " + str(seconds) + secondString
                    else:
                        for channel in text.guild.channels:
                            if channel.name == "looking-for-spar":
                                report = "Please only use !spar in " + channel.mention + ", " + text.author.mention + "."
                                break
                    await text.channel.send(report)
                    return
                
                if text.guild.id == 797140390993068035: # Commands only used in Jetspec's Discord server.
                    if msg == '!file':
                        jet = await text.guild.fetch_member("579316676642996266")
                        await text.channel.send(jet.mention)
                        print("Pinging Jetspec.")
                        return
                
                if text.guild.id == 442403231864324119: # Commands only used in eggsoup's Discord server.
                    if msg == '!tweet' or msg == '!eggtweet':
                        emb = discord.Embed(title = "eggsoup(@eggsouptv)", description = "", color = 0x1da1f2)
                        emb.add_field(name = "_ _", value = formattedTweet(tweet()))
                        await text.channel.send(embed = emb)
                        return
                    
                    if msg == '!reddit':
                        emb = discord.Embed(title = "The Official Eggsoup Subreddit", description = "https://www.reddit.com/r/eggsoup/", color = 0xfff994)
                        emb.set_thumbnail(url = "https://styles.redditmedia.com/t5_2m5xhn/styles/communityIcon_0yqex29y6lu51.png?width=256&s=fcf916f19b8f0bffff91d512691837630b378d80")
                        await text.channel.send(embed = emb)
                        return
                    
                    if msg == '!twitch':
                        emb = discord.Embed(title = "Captain No-Beard's Twitch Stream", description = "https://twitch.tv/capnnobeard", color = 0xfff994)
                        emb.set_thumbnail(url = "https://yt3.ggpht.com/ytc/AKedOLStPqU8W7FinOREV9HpU1P9Zm23O9qOlbmbPWoZ=s88-c-k-c0x00ffffff-no-rj")
                        await text.channel.send(embed = emb)
                        return
                    
                    if msg == '!guide':
                        await text.channel.send(embed = discord.Embed(title = "The Eggsoup Improvement Guide", description = "https://www.youtube.com/watch?v=nH0TOoJIU80", color = 0xfff994))
                        return
                    
                    if msg == "!notify":
                        report = "On " + choice(["Youtube, sub -> eggsoup", "Twitch, Subscribe -> Eggsoup", "r/eggsoup, join -> now", "Twitter, follow -> eggsoup", "brawlhalla, settings -> quit", "brawlhalla, scythe -> miss", "Unarmed, dlight -> everything", "Sword, dlight -> sair", "all legends, design rework -> ugly", "Toilet, poop -> flush", "Microsoft Word, ctrl c -> ctrl v", ]) + " is true. He might get mad if I randomly ping him, so I’d rather somebody more important than me tell him this. This could be in a future brawlhalla guide or something do I just wanted to let him know"
                        await text.channel.send(embed = discord.Embed(title = "Hey can someone notify egg about this?", description = report, color = 0xfff994))
                        return
                    
                    if text.channel.id == 605083979737071616:
                        if msg == '!pins' or msg == '!rules':
                            emb = discord.Embed(title = "How to use this channel.", description = "", color = 0xfff994)
                            emb.add_field(name = "To spar someone from your region:", value = "Do the command !spar <region> <other info>. For instance, to find a diamond from US-E to play 2s with, I would do:\n!spar US-E looking for a diamond 2s partner. \nValid regions are US-E, US-W, BRZ, EU, JPN, AUS, SEA. !spar has a 2 hour cooldown. Please use <#833566541831208971> to give yourself the correct roles.", inline = False)
                            emb.add_field(name = "If you don't want to get pings:", value = "Remove your region role in <#833566541831208971>. Otherwise, responding 'no' to calls to spar is annoying and counterproductive, and will earn you a warning.", inline = False)
                            await text.channel.send(embed = emb)
                            return
                    
                    if all([msg.startswith('!warn'), text.channel.id != 705098150423167059, len(msg) > 6, text.author.guild_permissions.manage_messages]):
                        emb = discord.Embed(title = "Infraction Logged.", description = "", color = 0xfff994)
                        emb.add_field(name = "_ _", value = "Mods can view the infraction details in <#705098150423167059>.", inline = True)
                        await text.channel.send(embed = emb)
                        return
                
                if text.guild.id == 781025281590165555: # Commands for the Day Care Discord server.
                    if 'twitter.com/year_progress' in msg:
                        await text.delete()
                        return

    client.run(token)