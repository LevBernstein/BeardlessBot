# Beardless Bot
# Author: Lev Bernstein
# Version: 8.9.1

# Default modules:
import asyncio
import csv
import requests
from collections import OrderedDict
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
import eggTweetGenerator
from dice import *
from facts import *
from animals import *

try:
    with open("resources/token.txt", "r") as f: # in token.txt, paste in your own Discord API token
        token = f.readline()
    with open("resources/catToken.txt", "r") as f: # in catToken.txt, paste in your own Cat API Key
        catKey = f.readline()
        if catKey.endswith("\n"): # API doesn't handle line and carriage return characters well
            catKey = catKey[:-1]
        if catKey.endswith("\r"):
            catKey = catKey[:-1]
except Exception as err:
    print(err)
    sysExit(-1)

# Blackjack class. New Instance is made for each game of Blackjack and is kept around until the player finishes the game.
# An active Instance for a given user prevents the creation of a new Instance. Instances are server-agnostic.
class Instance:
    def __init__(self, user, bet):
        self.user = user
        self.bet = bet
        self.cards = []
        self.dealerUp = randint(2,11)
        self.dealerSum = self.dealerUp
        while self.dealerSum < 17:
            self.dealerSum += randint(1,10)
        self.vals = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]
        self.message = self.deal()
        self.message = self.deal() # Deals two cards

    def perfect(self, cardSet):
        return sum(cardSet) == 21
    
    def deal(self):
        card3 = choice(self.vals)
        self.cards.append(card3)
        if card3 == 11:
            self.message = "You were dealt an Ace, bringing your total to " + str(sum(self.cards)) + ". " 
        elif card3 == 8:
            self.message = "You were dealt an " + str(card3) + ", bringing your total to " + str(sum(self.cards)) + ". "
        elif card3 == 10:
            self.message = "You were dealt a " + choice(["10", "Jack", "Queen", "King"]) + ", bringing your total to " + str(sum(self.cards)) + ". "
        else:
            self.message = "You were dealt a " + str(card3) + ", bringing your total to " + str(sum(self.cards)) + ". "
        if 11 in self.cards and self.checkBust(self.cards):
            for i in range(len(self.cards)):
                if self.cards[i] == 11:
                    self.cards[i] = 1
                    break
            self.message += "Because you would have busted, your Ace has been changed from an 11 to 1 . Your new total is " + str(sum(self.cards)) + ". "
        self.message += self.toString() + " The dealer is showing " + str(self.dealerUp) + ", with one card face down."
        if self.checkBust(self.cards):
            self.message += " You busted. Game over, " + self.user.mention + "."
        elif self.perfect(self.cards):
            self.message += " You hit 21! You win, " + self.user.mention + "!"
        else:
            self.message += " Type !hit to deal another card to yourself, or !stay to stop at your current total, " + self.user.mention+ "."
        return self.message

    def toString(self):
        return "Your cards are " + str(self.cards)[1:-1] + "."

    def checkBust(self, cardSet):
        return sum(cardSet) > 21

    def getUser(self):
        return self.user
    
    def stay(self):
        if sum(self.cards) > self.dealerSum:
            return 3
        if sum(self.cards) == self.dealerSum:
            return 0
        return 4 if self.dealerSum > 21 else -3
        
games = [] # Stores the active instances of blackjack. An array might not be the most efficient place to store these, 
# but because this bot sees use on a relatively small scale, this is not an issue.
# TODO: switch to BST sorted based on user ID

# This dictionary is for keeping track of pings in eggsoup's Discord server.
regions = {'jpn': 0, 'brz': 0, 'us-w': 0, 'us-e': 0, 'sea': 0, 'aus': 0, 'eu': 0}

client = discord.Client()
class DiscordClass(client):
    
    intents = discord.Intents()
    intents.members = True
   
    @client.event
    async def on_ready():
        print("Beardless Bot online!")
        try:
            await client.change_presence(activity = discord.Game(name = 'try !blackjack and !flip'))
            print("Status updated!")
        except discord.HTTPException:
            print("Failed to update status!")
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
    
    @client.event
    async def on_message(text):
        if not text.author.bot:
            text.content = text.content.lower()
            if text.content.startswith('!bj') or text.content.startswith('!bl'):
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                report = "You need to register first! Type !register to get started, " + text.author.mention + "."
                strbet = '10' # Bets default to 10. If someone just types !blackjack, they will bet 10 by default.
                if text.content.startswith('!blackjack') and len(str(text.content)) > 11:
                    strbet = text.content.split('!blackjack ',1)[1]
                elif text.content.startswith('!blackjack'):
                    pass
                elif text.content.startswith('!bl ') and len(str(text.content)) > 4:
                    strbet = text.content.split('!bl ',1)[1]
                elif text.content == '!bl':
                    pass
                elif text.content.startswith('!bl'):
                    # This way, other bots' commands that start with !bl won't trigger blackjack.
                    return
                elif text.content.startswith('!bj') and len(str(text.content)) > 4:
                    strbet = text.content.split('!bj ',1)[1]
                allBet = False
                if strbet == "all":
                    allBet = True
                    bet = 0
                else:
                    try:
                        bet = int(strbet)
                    except:
                        if (' ' not in text.content):
                            bet = 10
                        else:
                            print("Failed to cast bet to int!")
                            await text.channel.send("Invalid bet amount. Please choose a number >-1, " + text.author.mention + ".")
                            return
                if bet < 0:
                    report = "Invalid bet. Choose a value greater than or equal to 0."
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
                                        break
                                if exist:
                                    report = "You already have an active game, " + text.author.mention + "."
                                else:
                                    if bet <= bank:
                                        x = Instance(text.author, bet)
                                        games.append(x)
                                        report = x.message
                                        if x.checkBust(x.cards) or x.perfect(x.cards):
                                            totalsum = bank + ((bet * -1) if x.checkBust(x.cards) else bet)
                                            oldliner = str(text.author.id) + "," + str(bank) + "," + row[2]
                                            liner = str(text.author.id) + "," + str(totalsum) + "," + str(text.author)
                                            texter = open("resources/money.csv", "r")
                                            texter = ''.join([i for i in texter]).replace(oldliner, liner)
                                            with open("resources/money.csv", "w") as money:
                                                money.writelines(texter)
                                            for i in range(len(games)):
                                                if games[i].getUser() == text.author:
                                                    games.pop(i)
                                                    break
                                    else:
                                        report = "You do not have enough BeardlessBucks to bet that much, " + text.author.mention + "!"
                                break
                await text.channel.send(report)
                return
            
            if text.content.startswith('!deal') or text.content == '!hit':
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                report = "You do not currently have a game of blackjack going, " + text.author.mention + ". Type !blackjack to start one."
                exist = False
                for i in range(len(games)):
                    if games[i].getUser() == text.author:
                        exist = True
                        gamer = games[i]
                        break
                if exist:
                    report = gamer.deal()
                    if gamer.checkBust(gamer.cards) or gamer.perfect(gamer.cards):
                        bet = (gamer.bet * -1) if gamer.checkBust(gamer.cards) else gamer.bet
                        with open('resources/money.csv', 'r') as csvfile:
                            reader = csv.reader(csvfile, delimiter = ',')
                            for row in reader:
                                if str(text.author.id) == row[0]:
                                    totalsum = int(row[1]) + bet
                                    oldliner = row[0] + "," + row[1] + "," + row[2]
                                    liner = str(text.author.id) + "," + str(totalsum) + "," + str(text.author)
                                    texter = open("resources/money.csv", "r")
                                    texter = ''.join([i for i in texter]).replace(oldliner, liner)
                                    with open("resources/money.csv", "w") as money:
                                        money.writelines(texter)
                                    for i in range(len(games)):
                                        if games[i].getUser() == text.author:
                                            games.pop(i)
                                            break
                                    break
                await text.channel.send(report)
                return

            if text.content.startswith('!stay') or text.content.startswith('!stand'):
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                report = "You do not currently have a game of blackjack going, " + text.author.mention + ". Type !blackjack to start one."
                exist = False
                for i in range(len(games)):
                    if games[i].getUser() == text.author:
                        exist = True
                        gamer = games[i]
                        bet = gamer.bet
                        break
                if exist:
                    result = gamer.stay()
                    report = "The dealer has a total of " + str(gamer.dealerSum) + "."
                    if result == -3:
                        report += " That's closer to 21 than your sum of " + str(sum(gamer.cards)) + ". You lose"
                        bet *= -1
                        if bet != 0:
                            report +=  ". Your loss has been deducted from your balance"
                    if result == 0:
                        report += " That ties your sum of " + str(sum(gamer.cards))
                        if bet != 0:
                            report += ". Your money has been returned"
                    if result == 3:
                        report += " You're closer to 21 with a sum of " + str(sum(gamer.cards))
                    if result == 4:
                        report += " You have a sum of " + str(sum(gamer.cards)) + ". The dealer busts"
                    if (result == 3 or result == 4) and bet != 0:
                        report += ". You win! Your winnings have been added to your balance"
                    if result != 0 and bet != 0:
                        with open('resources/money.csv', 'r') as csvfile:
                            reader = csv.reader(csvfile, delimiter = ',')
                            for row in reader:
                                if str(text.author.id) == row[0]:
                                    totalsum = int(row[1]) + bet
                                    oldliner = row[0] + "," + row[1] + "," + row[2]
                                    liner = str(text.author.id) + "," + str(totalsum) + "," + str(text.author)
                                    texter = open("resources/money.csv", "r")
                                    texter = ''.join([i for i in texter]).replace(oldliner, liner)
                                    with open("resources/money.csv", "w") as money:
                                        money.writelines(texter)
                                    break
                    elif bet == 0:
                        report += ". Y" if result == 0 else ". However, y"
                        report += "ou bet nothing, so your balance has not changed"
                    report += ", " + text.author.mention + "."
                    for i in range(len(games)):
                        if games[i].getUser() == text.author:
                            games.pop(i)
                            break
                await text.channel.send(report)
                return
                
            if text.content.startswith('!flip'):
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                allBet = False
                strbet = text.content.split('!flip ',1)[1] if len(text.content) > 5 else 10
                if strbet == "all":
                    allBet = True
                    bet = 0
                else:
                    try:
                        bet = int(strbet)
                    except:
                        if (' ' not in text.content):
                            bet = 10
                        else:
                            print("Failed to cast bet to int!")
                            await text.channel.send("Invalid bet amount. Please choose a number >-1, " + text.author.mention + ".")
                            return
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
                                    if games[i].getUser() == str(text.author):
                                        found = True
                                        break
                                if found:
                                    report = "Please finish your game of blackjack first, " +  text.author.mention + "."
                                    break
                                if bet <= bank: # As of 11 AM ET on January 22nd, 2021, there have been 31765 flips that got heads and 31664 flips that got tails in the eggsoup server. This is 50/50. Stop complaining.
                                    result = randint(0,1)
                                    if result:
                                        report = "Heads! You win! Your winnings have been added to your balance, " + text.author.mention + "."
                                    else:
                                        report = "Tails! You lose! Your loss has been deducted from your balance, " + text.author.mention + "."
                                    totalsum = bank + (bet if result else bet * -1)
                                    if not bet:
                                        report += " However, you bet nothing, so your balance will not change."
                                    else:
                                        oldliner = row[0] + "," + str(bank) + "," + row[2]
                                        liner = row[0] + "," + str(totalsum) + "," + str(text.author)
                                        texter = open("resources/money.csv", "r")
                                        texter = ''.join([i for i in texter]).replace(oldliner, liner)
                                        with open("resources/money.csv", "w") as money:
                                            money.writelines(texter)
                                else:
                                    report = "You do not have enough BeardlessBucks to bet that much, " + text.author.mention + "!"
                                break
                await text.channel.send(report)
                return
            
            if text.content.startswith('!buy'): # Requires roles named special blue, special pink, special orange, and special red.
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                print("Running buy...")
                with open('resources/money.csv', 'r') as csvfile:
                    reader = csv.reader(csvfile, delimiter = ',')
                    for row in reader:
                        if str(text.author.id) == row[0]:
                            if  'blue' in text.content or 'pink' in text.content or 'orange' in text.content or 'red' in text.content:
                                if  50000 <= int(row[1]):
                                    if ('blue' in text.content):
                                        role = get(text.guild.roles, name = 'special blue')
                                    elif ('pink' in text.content):
                                        role = get(text.guild.roles, name = 'special pink')
                                    elif ('orange' in text.content):
                                        role = get(text.guild.roles, name = 'special orange')
                                    elif ('red' in text.content):
                                        role = get(text.guild.roles, name = 'special red')
                                    oldliner = row[0] + "," + row[1] + "," + row[2]
                                    liner = row[0] + "," + str(int(row[1]) - 50000) + "," + str(text.author)
                                    texter = open("resources/money.csv", "r")
                                    texter = ''.join([i for i in texter]).replace(oldliner, liner)
                                    with open("resources/money.csv", "w") as money:
                                        money.writelines(texter)
                                    await text.author.add_roles(role)
                                    report = "Color purchased successfully, " + text.author.mention + "!"
                                else:
                                    report = "Not enough Beardess Bucks. You need 50000 to buy a special color, " + text.author.mention + "."
                            else:
                                report = "Invalid color. Choose blue, red, orange, or pink, " + text.author.mention + "."
                            break
                await text.channel.send(report)
                return
            
            if text.content.startswith('!av'):
                bar = 8 if text.content.startswith('!avatar') else 4
                report = text.author.avatar_url
                if len(text.content) > bar:
                    if '@' in text.content:
                        target = text.content.split('@', 1)[1]
                        if target.startswith('!'): # Resolves a discrepancy between mobile and desktop Discord
                            target = target[1:]
                        target, brick = target.split('>', 1)
                        try:
                            newtarg = await text.guild.fetch_member(str(target))
                            report = newtarg.avatar_url
                        except discord.NotFound:
                            report = "Discord Member " + str(target) + " not found!"
                await text.channel.send(report)
                
            if text.content.startswith('-mute') or text.content.startswith('!mute'):
                # TODO switch to message.mentions for target acquisition
                if text.author.guild_permissions.manage_messages:
                    if '@' in text.content:
                        target = text.content.split('@', 1)[1]
                        if target.startswith('!'): # Resolves a discrepancy between mobile and desktop Discord
                            target = target[1:]
                        target, duration = target.split('>', 1)
                        if target == "654133911558946837": # If user tries to mute Beardless Bot:
                            await text.channel.send("I am too powerful to be muted. Stop trying.")
                            return
                        print("Author: " + str(text.author.id) + " muting target: " + target)
                        role = get(text.guild.roles, name = 'Muted')
                        newtarg = await text.guild.fetch_member(str(target))
                        await newtarg.add_roles(role)
                        await text.channel.send("Muted " + str(newtarg.mention) + ".")
                        mTime = 0.0 # Autounmute:
                        if 'h' in duration:
                            duration = duration[1:]
                            duration, brick = duration.split('h', 1)
                            mTime = float(duration) * 3600.0
                        elif 'm' in duration:
                            duration = duration[1:]
                            duration, brick = duration.split('m', 1)
                            mTime = float(duration) * 60.0
                        elif 's' in duration:
                            duration = duration[1:]
                            duration, brick = duration.split('s', 1)
                            mTime = float(duration)
                        if mTime != 0.0:
                            print(mTime)
                            await asyncio.sleep(mTime)
                            await newtarg.remove_roles(role)
                            print("Unmuted " + newtarg.name)
                    else:
                        await text.channel.send("Invalid target!")
                else:
                    await text.channel.send("You do not have permission to use this command!")
                return
            
            if text.content.startswith('-unmute') or text.content.startswith('!unmute'):
                if text.author.guild_permissions.manage_messages:
                    if '@' in text.content:
                        print("Original message: " + text.content)
                        target = text.content.split('@', 1)[1]
                        target = target[1:-1] if target.startswith('!') else target[:-1]
                        print("Author: " + str(text.author.id))
                        print("Target: " + target)
                        role = get(text.guild.roles, name = 'Muted')
                        newtarg = await text.guild.fetch_member(str(target))
                        await newtarg.remove_roles(role)
                        await text.channel.send("Unmuted " + str(newtarg.mention) + ".")
                    else:
                        await text.channel.send("Invalid target!")
                else:
                    await text.channel.send("You do not have permission to use this command!")
                return
            
            if text.content.startswith('!video'):
                await text.channel.send('My creator made a new video! Check it out at https://youtu.be/-4FzBLS-UVI')
                return
            
            if text.content.startswith('!song') or text.content.startswith('!playlist') or text.content.startswith('!music'):
                await text.channel.send('Here\'s my playlist (discord will only show the first hundred songs): https://open.spotify.com/playlist/2JSGLsBJ6kVbGY1B7LP4Zi?si=Zku_xewGTiuVkneXTLCqeg')
                return
            
            if text.content.startswith('!leaderboard') or text.content.startswith('!lb'):
                diction = {}
                emb = discord.Embed(title = "BeardlessBucks Leaderboard", description = "", color = 0xfff994)
                with open('resources/money.csv') as csvfile:
                    reader = csv.reader(csvfile, delimiter = ',')
                    for row in reader:
                        if int(row[1]) != 0: # Don't bother displaying info for people with 0 BeardlessBucks
                            diction[(row[2])[:-5]] = int(row[1])
                sortedDict = OrderedDict(sorted(diction.items(), key = itemgetter(1)))
                for i in range(len(sortedDict.items()) if len(sortedDict) < 10 else 10):
                    tup = sortedDict.popitem()
                    emb.add_field(name = (str(i + 1) + ". " + tup[0]), value = str(tup[1]), inline = True)
                await text.channel.send(embed=emb)
                return
            
            if text.content.startswith('!dice'):
                await text.channel.send("Enter !d[number][+/-][modifier] to roll a [number]-sided die and add or subtract a modifier. For example: !d8+3, or !d100-17, or !d6.")
                return
            
            if text.content.startswith('!reset'):
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
                        message3="Successfully registered. You have 300 BeardlessBucks, " + text.author.mention + "."
                        with open('resources/money.csv', 'a') as money:
                            writer = csv.writer(csvfile)
                            newline = "\r\n" + str(text.author.id) + ",300," + str(text.author)
                            money.write(newline)
                await text.channel.send('You have been reset to 200 BeardlessBucks, ' + text.author.mention + ".")
                return
            
            if text.content.startswith("!balance") or text.content.startswith("!bal"):
                message2 = ""
                if text.content == ("!balance") or text.content == ("!bal"):
                    selfMode = True
                    if ',' in text.author.name:
                        await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                        return
                    authorstring = str(text.author.id)
                elif text.content.startswith("!balance ") or text.content.startswith("!bal "):
                    selfMode = False
                    if '@' in text.content:
                        target = text.content.split('@', 1)[1]
                        if target.startswith('!'): # Resolves a discrepancy between mobile and desktop Discord
                            target = target[1:]
                        target, brick = target.split('>', 1)
                        try:
                            newtarg = await text.guild.fetch_member(str(target))
                            authorstring = str(newtarg.id)
                        except discord.NotFound as err:
                            message2 = "Error code 10007: Discord Member not found!"
                            print(err)
                    else:
                        message2 = "Invalid user! Please @ a user when you do !balance, or do !balance without a target to see your own balance, " + text.author.mention + "."
                else:
                    return
                if message2 == "":
                    message2 = "Oops! You aren't in the system! Type \"!register\" to get a starting balance, " + text.author.mention + "." if selfMode else "Oops! That user isn't in the system! They can type \"!register\" to get a starting balance."
                    with open('resources/money.csv') as csvfile:
                        reader = csv.reader(csvfile, delimiter = ',')
                        for row in reader:
                            if authorstring == row[0]:
                                if selfMode:
                                    message2 = "Your balance is " + row[1] + " BeardlessBucks, " + text.author.mention + "."
                                else:
                                    message2 = (newtarg.name if newtarg.nick is None else newtarg.nick) + "'s balance is " + row[1] + " BeardlessBucks."
                                break
                await text.channel.send(message2)
                return
            
            if text.content.startswith("!register"): # Make sure resources/money.csv is not open in any other program
                if ',' in text.author.name:
                    await text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                    return
                with open('resources/money.csv') as csvfile:
                    reader = csv.reader(csvfile, delimiter = ',')
                    exist = False
                    for row in reader:
                        if str(text.author.id) == row[0]:
                            exist = True
                            message3 = "You are already in the system! Hooray! You have " + row[1] + " BeardlessBucks, " + text.author.mention + "."
                            break
                    if not exist:
                        message3 = "Successfully registered. You have 300 BeardlessBucks, " + text.author.mention + "."
                        with open('resources/money.csv', 'a') as money:
                            writer = csv.writer(csvfile)
                            newline = "\r\n" + str(text.author.id) + ",300," + str(text.author)
                            money.write(newline)
                    await text.channel.send(message3)
                    return
            
            if text.content.startswith("!bucks"):
                await text.channel.send("BeardlessBucks are this bot's special currency. You can earn them by playing games. First, do !register to get yourself started with a balance.")
                return
            
            if any([text.content.startswith("!hello"), text.content == "!hi", (("hello" in text.content or "hi" in text.content) and ("beardless" in text.content or "bb" in text.content))]):
                answers = ["How ya doin?", "Yo!", "What's cookin?", "Hello!", "Ahoy!", "Hi!", "What's up?", "Hey!", "How's it goin?", "Greetings!"]
                await text.channel.send(choice(answers))
                return
            
            if text.content.startswith("!source"):
                await text.channel.send("Most facts taken from https://www.thefactsite.com/1000-interesting-facts/.")
                return
            
            if text.content.startswith("!link") or text.content.startswith("!add") or text.content.startswith("!join"):
                await text.channel.send("Want to add this bot to your server? Click https://discord.com/api/oauth2/authorize?client_id=654133911558946837&permissions=8&scope=bot")
                return
            
            if text.content.startswith("!rohan"):
                await text.channel.send(file = discord.File('images/cute.png'))
                return
            
            if text.content.startswith("!random"):
                message = "Invalid random."
                if "legend" in text.content:
                    legends = ["Bodvar", "Cassidy", "Orion", "Lord Vraxx", "Gnash", "Queen Nai", "Hattori", "Sir Roland", "Scarlet", "Thatch", "Ada", "Sentinel", "Lucien", "Teros", "Brynn", "Asuri", "Barraza", "Ember", "Azoth", "Koji", "Ulgrim", "Diana", "Jhala", "Kor", "Wu Shang", "Val", "Ragnir", "Cross", "Mirage", "Nix", "Mordex", "Yumiko", "Artemis", "Caspian", "Sidra", "Xull", "Kaya", "Isaiah", "Jiro", "Lin Fei", "Zariel", "Rayman", "Dusk", "Fait", "Thor", "Petra", "Vector", "Volkov", "Onyx", "Jaeyun", "Mako", "Magyar", "Reno"]
                    ran = choice(legends)
                    message = "Your legend is " + ran + "."
                    try:
                        gerard = await text.guild.fetch_member("193041297538285568") # Checks to see if the Gerard bot is in this server
                        message += " Type \"!legend " + ran + "\" to learn more about this legend."
                    except:
                        pass
                elif "weapon" in text.content:
                    weapons = ["Sword", "Spear", "Orb", "Cannon", "Hammer", "Scythe", "Greatsword", "Bow", "Gauntlets", "Katars", "Blasters", "Axe"]
                    message = "Your weapon is " + choice(weapons) + "."
                await text.channel.send(message)
                return
            
            if text.content.startswith("!fact"):
                emb = discord.Embed(title = "Beardless Bot Fun Fact", description = "", color = 0xfff994)
                emb.add_field(name = "Fun fact #" + str(randint(1,1111111111)), value = fact(), inline = False)
                await text.channel.send(embed = emb)
                return
            
            if text.content.startswith("!dog"):
                if text.content.startswith("!dog moose"):
                    mooseNum = randint(1, 23)
                    mooseFile = 'images/moose/moose' + str(mooseNum) + (".gif" if mooseNum < 4 else ".jpg")
                    await text.channel.send(file = discord.File(mooseFile))
                    return
                if text.content.startswith("!dogs"):
                    return
                text.content = "!dog" if text.content == "!dog " else text.content
                try:
                    dogURL = animal(text.content[1:])
                    await text.channel.send(dogURL)
                except:
                    await text.channel.send("Something's gone wrong with the dog API! Please ping my creator and he'll see what's going on.")
                return
            
            if text.content.startswith("!cat"):
                try:
                    catURL = animal("cat", catKey)
                    await text.channel.send(catURL)
                except:
                    await text.channel.send("Cat API Limit Reached! It should reset at the end of the month.")
                return
            
            animalName = text.content[1:].split(" ", 1)[0]
            if animalName in ["duck", "fish", "fox", "rabbit", "bunny", "panda", "bird", "koala", "lizard"]:
                try:
                    animalURL = animal(animalName)
                    await text.channel.send(animalURL)
                except:
                    await text.channel.send("Something's gone wrong with the " + animalName + " API! Please ping my creator and he'll see what's going on.")
                return
           
            if text.content.startswith("!define "):
                word = text.content.split(' ', 1)[1]
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
                            await text.channel.send(embed = emb)
                            return
                        except:
                            report = "Invalid word!"
                    else:
                        report = "Error!"
                await text.channel.send(report)
                return
            
            if text.content.startswith('!d') and ((text.content.split('!d',1)[1])[0]).isnumeric() and len(text.content) < 12:
                # The isnumeric check ensures that you can't activate this command by typing !deal or !debase or anything else.
                await text.channel.send(roll(text.content))
                return
            
            if text.content.startswith("!help") or text.content.startswith("!commands"):
                emb = discord.Embed(title = "Beardless Bot Commands", description = "", color=0xfff994)
                emb.add_field(name = "!register", value = "Registers you with the currency system.", inline = True)
                emb.add_field(name = "!balance", value = "Checks your BeardlessBucks balance. You can write !balance <@someone> to see that person's balance.", inline = True)
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
                emb.add_field(name = "!hello", value = "Exchanges a pleasant greeting with the bot.", inline = True)
                emb.add_field(name = "!video", value = "Shows you my latest YouTube video.", inline = True)
                emb.add_field(name = "!add", value = "Gives you a link to add this bot to your server.", inline = True)
                emb.add_field(name = "!av", value = "Display a user's avatar. Write just !av if you want to see your own avatar.", inline = True)
                emb.add_field(name = "![animal name]", value = "Gets a random cat/dog/duck/fish/fox/rabbit/panda/lizard/koala/bird picture. Example: !duck", inline = True)
                emb.add_field(name = "!define [word]", value = "Shows you the definition(s) of a word.", inline = True)
                emb.add_field(name = "!commands", value = "Shows you this list.", inline = True)
                await text.channel.send(embed = emb)
                return
            
            if text.guild is not None: # Server-specific commands; this check prevents an error caused by commands being used in DMs
                if text.guild.id == 797140390993068035: # Commands only used in Jetspec's Discord server.
                    if text.content.startswith('!file'):
                        jet = await text.guild.fetch_member("579316676642996266")
                        await text.channel.send(jet.mention)
                        return
                
                if text.guild.id == 442403231864324119: # Commands only used in eggsoup's Discord server.
                    if text.content.startswith('!eggtweet') or text.content.startswith('!tweet'):
                        emb = discord.Embed(title = "eggsoup(@eggsouptv)", description = "", color = 0x1da1f2)
                        emb.add_field(name = "_ _", value = eggTweetGenerator.final())
                        await text.channel.send(embed = emb)
                        return
                    
                    if text.content.startswith('!reddit'):
                        await text.channel.send("https://www.reddit.com/r/eggsoup/")
                        return
                    
                    if text.content.startswith('!guide'):
                        await text.channel.send("https://www.youtube.com/watch?v=nH0TOoJIU80")
                        return
                    
                    if text.content.startswith('!mee6'):
                        mee6 = await text.guild.fetch_member("159985870458322944")
                        await text.channel.send('Silence ' + mee6.mention + "!")
                        return
                    
                    if text.channel.id == 605083979737071616:
                        if text.content.startswith('!pins') or text.content.startswith('!rules'):
                            emb = discord.Embed(title = "How to use this channel.", description = "", color = 0xfff994)
                            emb.add_field(name = "To spar someone from your region:", value = "Do the command !spar <region> <other info>. For instance, to find a diamond from US-E to play 2s with, I would do:\n!spar US-E looking for a diamond 2s partner. \nValid regions are US-E, US-W, BRZ, EU, JPN, AUS, SEA. !spar has a 2 hour cooldown. Please use <#833566541831208971> to give yourself the correct roles.", inline = False)
                            emb.add_field(name = "If you don't want to get pings:", value = "Remove your region role in <#833566541831208971>. Otherwise, responding 'no' to calls to spar is annoying and counterproductive, and will earn you a warning.", inline = False)
                            await text.channel.send(embed = emb)
                            return
                    
                    if all([text.content.startswith('!warn'), text.channel.id != 705098150423167059, len(text.content) > 6, text.author.guild_permissions.manage_messages]):
                        emb = discord.Embed(title = "Infraction Logged.", description = "", color = 0xfff994)
                        emb.add_field(name = "_ _", value = "Mods can view the infraction details in <#705098150423167059>.", inline = True)
                        await text.channel.send(embed = emb)
                        return
                    
                    if text.content.startswith('!spar'):
                        if text.channel.id == 605083979737071616: # This is the "looking-for-spar" channel in eggsoup's Discord server.
                            cooldown = 7200
                            report = "Please specify a valid region, " + text.author.mention + "! Valid regions are US-E, US-W, EU, AUS, SEA, BRZ, JPN. Check the pinned message if you need help, or do !pins."
                            tooRecent = None
                            found = False
                            if "use" in text.content: text.content = "us-e"
                            if "usw" in text.content: text.content = "us-w"
                            global regions
                            for key, value in regions.items():
                                if key in text.content:
                                    found = True
                                    if time() - value > cooldown:
                                        regions.update({key: time()})
                                        role = get(text.guild.roles, name = key.upper())
                                        report = role.mention + " come spar " + text.author.mention + "!"
                                    else:
                                        tooRecent = value
                                    break
                            if found and (tooRecent is not None):
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
                            report = "Please only use !spar in <#605083979737071616>, " + text.author.mention + "."
                        await text.channel.send(report)
                        return                
                
                if text.guild.id == 781025281590165555: # Commands for the Day Care Discord server.
                    if 'twitter.com/year_progress' in text.content:
                        await text.delete()
                        return

    client.run(token)