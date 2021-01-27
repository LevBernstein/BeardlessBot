# Beardless Bot
# Author: Lev Bernstein
# Version: 8.5.9

import random
import discord
import csv
from discord.ext import commands
from discord.utils import get
from time import sleep, time, gmtime
import random as random
from math import floor
import operator
from collections import OrderedDict
import asyncio

game = False
f = open("token.txt", "r") # In token.txt, just put in your own discord api token
token = f.readline()


# Blackjack class. New instance is made for each game of Blackjack and is kept around until the player finishes the game.
# An active instance for a given user prevents the creation of a new instance. Instances are server-agnostic.
class Instance:
    def __init__(self, user, bet):
        self.user = user
        self.bet = bet
        self.cards = []
        self.dealerUp = random.randint(2,11)
        self.dealerSum = self.dealerUp
        while self.dealerSum <17:
            self.dealerSum += random.randint(1,10)
        self.vals = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]
        self.message = self.deal()
        self.message = self.deal()
        self.State = True

    def summer(self, cardSet):
        total = 0
        for i in range(len(cardSet)):
            total += cardSet[i]
        return total

    def perfect(self, cardSet):
        if self.summer(cardSet) == 21:
            return True
        return False
    
    def deal(self):
        card3 = random.choice(self.vals)
        #print(card3)
        self.cards.append(card3)
        if card3 == 11:
            self.message = "You were dealt an Ace, bringing your total to " + str(self.summer(self.cards)) + ". " 
        elif card3 == 8:
            self.message = "You were dealt an " + str(card3) + ", bringing your total to " + str(self.summer(self.cards)) + ". "
        elif card3 == 10:
            self.message = "You were dealt a " + random.choice(["10", "Jack", "Queen", "King"]) + ", bringing your total to " + str(self.summer(self.cards)) + ". "
        else:
            self.message = "You were dealt a " + str(card3) + ", bringing your total to " + str(self.summer(self.cards)) + ". "
        if 11 in self.cards and self.checkBust(self.cards):
            for i in range(len(self.cards)):
                if self.cards[i] == 11:
                    self.cards[i] = 1
                    break
            self.message += "Because you would have busted, your Ace has been changed from an 11 to 1 . Your new total is " + str(self.summer(self.cards)) + ". "
        self.message += self.toString() + " The dealer is showing " + str(self.dealerUp) + ", with one card face down."
        if self.checkBust(self.cards):
            self.message += " You busted. Game over, " + self.user.mention + "."
            self.state = False
        elif self.perfect(self.cards):
            self.message += " You hit 21! You win, " + self.user.mention + "!"
            self.state = False
        else:
            self.message += " Type !hit to deal another card to yourself, or !stay to stop at your current total, " + self.user.mention+ "."
        return self.message

    def toString(self):
        stringer = "Your cards are "
        for i in range(len(self.cards)):
            stringer += str(self.cards[i]) + ", "
        stringer = stringer[0:-2] + "." # Remove the last comma and space, replace with a period
        return stringer

    def checkBust(self, cardSet):
        if self.summer(cardSet) > 21:
            return True
        return False

    def namer(self):
        return self.user
    
    def stay(self):
        if self.summer(self.cards) > self.dealerSum:
            return 3
        if self.summer(self.cards) == self.dealerSum:
            return 0
        if self.dealerSum > 21:
            return 4
        if self.summer(self.cards) < self.dealerSum:
            return -3
        return -1 # Error
        
games = [] # Stores the active instances of blacjack. An array might not be the most efficient place to store these, 
# but because this bot sees use on a relatively small scale, this is not an issue.
# These ping ints are for keeping track of pings in eggsoup's Discord server.
usePing = 0
uswPing = 0
euPing = 0
seaPing = 0
ausPing = 0
jpnPing = 0
brzPing = 0

client = discord.Client()
class DiscordClass(client):
    
    intents = discord.Intents()
    intents.members = True
   
    @client.event
    async def on_ready():
        print("Beardless Bot online!")
        try:
            await client.change_presence(activity=discord.Game(name='try !blackjack and !flip'))
            print("Status updated!")
        except discord.HTTPException:
            print("Failed to update status!")
        intents = discord.Intents.default()
        intents.members = True
        g = open("bbprof.png", "rb")
        pic = g.read()
        try:
            await client.user.edit(avatar=pic)
            print("Avatar live!")
        except discord.HTTPException:
            print("Avatar failed to update!")
    
    @client.event
    async def on_message(text):
        text.content=text.content.lower()
        if text.content.startswith('!bj') or text.content.startswith('!bl'):
            if ',' in text.author.name:
                text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                return
            report = "You need to register first! Type !register to get started, " + text.author.mention + "."
            strbet = '10' # Bets default to 10. If someone just types !blackjack, they will bet 10 by default.
            if text.content.startswith('!blackjack') and len(str(text.content)) > 11:
                strbet = text.content.split('!blackjack ',1)[1]
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
                    bet = 10
                    print("Failed to cast bet to int!")
            authorstring = str(text.author)
            if allBet == False and bet < 0: # Check if !allBet first to avoid attempting to cast "all" to int
                report = "Invalid bet. Choose a value greater than or equal to 0."
            else:
                with open('money.csv', 'r') as csvfile:
                    reader = csv.reader(csvfile, delimiter=',')
                    for row in reader:
                        if str(text.author.id) == row[0]:
                            bank = int(row[1])
                            if allBet:
                                bet = bank
                            exist5 = False
                            for i in range(len(games)):
                                if games[i].namer() == text.author:
                                    exist5 = True
                            if exist5:
                                report = "You already have an active game, " + text.author.mention + "."
                            else:
                                if bet <= bank:
                                    game = True
                                    x = Instance(text.author, bet)
                                    games.append(x)
                                    report = x.message
                                    if x.checkBust(x.cards) or x.perfect(x.cards):
                                        if x.checkBust(x.cards):
                                            bet = bet * -1
                                        totalsum = bank + bet
                                        oldliner = str(text.author.id) + "," + str(bank) + "," + row[2]
                                        liner = str(text.author.id) + "," + str(totalsum)+ "," + str(text.author)
                                        texter = open("money.csv", "r")
                                        texter = ''.join([i for i in texter]) \
                                            .replace(oldliner, liner)
                                        with open("money.csv", "w") as phil:
                                            phil.writelines(texter)
                                        for i in range(len(games)):
                                            if games[i].namer() == text.author:
                                                games.pop(i)
                                                break
                                else:
                                    report = "You do not have enough BeardlessBucks to bet that much, " + text.author.mention + "!"
                            break
            await text.channel.send(report)
            return
        
        if text.content.startswith('!deal') or text.content == '!hit':
            if ',' in text.author.name:
                text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                return
            report = "You do not currently have a game of blackjack going, " + text.author.mention + ". Type !blackjack to start one."
            authorstring = str(text.author)
            exist5 = False
            for i in range(len(games)):
                if games[i].namer() == text.author:
                    exist5 = True
                    gamer = games[i]
                    break
            if exist5:
                report = gamer.deal()
                if gamer.checkBust(gamer.cards) == True or gamer.perfect(gamer.cards) == True:
                    if gamer.checkBust(gamer.cards) == True:
                        bet = gamer.bet * -1
                    else:
                        bet = gamer.bet
                    with open('money.csv', 'r') as csvfile:
                        reader = csv.reader(csvfile, delimiter=',')
                        exist4=False
                        for row in reader:
                            tempname = str(text.author)
                            if str(text.author.id) == row[0]:
                                exist4=True
                                bank = int(row[1])
                                totalsum = bank + bet
                                oldliner = str(text.author.id)+ "," + str(bank)+ "," + row[2]
                                liner = str(text.author.id) + "," + str(totalsum)+ "," + str(text.author)
                                texter = open("money.csv", "r")
                                texter = ''.join([i for i in texter]) \
                                    .replace(oldliner, liner)
                                with open("money.csv", "w") as x:
                                    x.writelines(texter)
                                for i in range(len(games)):
                                    if games[i].namer() == text.author:
                                        games.pop(i)
                                        break
                                break
            await text.channel.send(report)
            return

        if text.content.startswith('!stay') or text.content.startswith('!stand'):
            if ',' in text.author.name:
                text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                return
            report = "You do not currently have a game of blackjack going, " + text.author.mention + ". Type !blackjack to start one."
            authorstring = str(text.author)
            exist5 = False
            bet = 1
            for i in range(len(games)):
                if games[i].namer() == text.author:
                    exist5 = True
                    gamer = games[i]
                    bet = gamer.bet
                    break
            if exist5:
                neutral = False
                result = gamer.stay()
                report = "The dealer has a total of " + str(gamer.dealerSum) + "."
                if result == -3:
                    report += " That's closer to 21 than your sum of " + str(gamer.summer(gamer.cards)) + ". You lose"
                    bet *= -1
                    if bet != 0:
                        report +=  ". Your loss has been deducted from your balance"
                if result == 0:
                    report += " That ties your sum of " + str(gamer.summer(gamer.cards))
                    if bet != 0:
                         report += ". Your money has been returned"
                if result == 3:
                    report += " You're closer to 21 with a sum of " + str(gamer.summer(gamer.cards))
                if result == 4:
                    report += " You have a sum of " + str(gamer.summer(gamer.cards)) + ". The dealer busts"
                if (result == 3 or result == 4) and bet != 0:
                    report += ". You win! Your winnings have been added to your balance"
                if result != 0 and bet != 0:
                    with open('money.csv', 'r') as csvfile:
                        reader = csv.reader(csvfile, delimiter=',')
                        exist4=False
                        for row in reader:
                            if str(text.author.id) == row[0]:
                                exist4=True
                                bank = int(row[1])
                                totalsum = bank + bet
                                oldliner = str(text.author.id) + "," + str(bank)+ "," + row[2]
                                liner = str(text.author.id) + "," + str(totalsum)+ "," + str(text.author)
                                texter = open("money.csv", "r")
                                texter = ''.join([i for i in texter]) \
                                    .replace(oldliner, liner)
                                with open("money.csv", "w") as x:
                                    x.writelines(texter)
                                break
                elif bet == 0:
                    if result == 0:
                        report += ". Y"
                    else:
                        report += ". However, y"
                    report += "ou bet nothing, so your balance has not changed"
                report += ", " + text.author.mention + "."
                for i in range(len(games)):
                    if games[i].namer() == text.author:
                        games.pop(i)
                        break
            await text.channel.send(report)
            return
            
        if text.content.startswith('!flip'):
            if ',' in text.author.name:
                text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                return
            print(text.author.name + ": " + text.content)
            allBet = False
            if len(text.content) > 5:
                strbet = text.content.split('!flip ',1)[1]
            else:
                strbet = 10
            if strbet == "all":
                allBet = True
                bet = 0
            else:
                try:
                    bet = int(strbet)
                except:
                    bet = 10
                    print("Failed to cast bet to int!")
            authorstring = str(text.author.id)
            if allBet == False and int(strbet) < 0:
                report = "Invalid bet amount. Choose a value >-1, " + text.author.mention + "."
            else:
                with open('money.csv', 'r') as csvfile:
                    reader = csv.reader(csvfile, delimiter=',')
                    exist4=False
                    for row in reader:
                        tempname = row[0]
                        if authorstring == tempname:
                            exist4=True
                            bank = int(row[1])
                            if allBet:
                                bet = bank
                            exist5 = False
                            for i in range(len(games)):
                                if games[i].namer() == str(text.author):
                                    exist5 = True
                            if exist5:
                                report = "Finish your game of blackjack first, " +  text.author.mention + "."
                                break
                            if bet <= bank: # As of 11 AM ET on January 22nd, 2021, there have been 31765 flips that got heads and 31664 flips that got tails in the eggsoup server. This is 50/50. Stop complaining.
                                results = [1, 0]
                                result = random.choice(results)
                                if result==1:
                                    change = bet
                                    report = "Heads! You win! Your winnings have been added to your balance, " + text.author.mention + "."
                                    totalsum=bank+change
                                else:
                                    change = bet * -1
                                    report = "Tails! You lose! Your loss has been deducted from your balance, " + text.author.mention + "."
                                    totalsum=bank+change
                                if change == 0:
                                    report += " However, you bet nothing, so your balance will not change."
                                else:
                                    oldliner = tempname + "," + str(bank)+ "," + row[2]
                                    liner = tempname + "," + str(totalsum)+ "," + str(text.author)
                                    texter = open("money.csv", "r")
                                    texter = ''.join([i for i in texter]) \
                                        .replace(oldliner, liner)
                                    with open("money.csv", "w") as x:
                                        x.writelines(texter)
                            else:
                                report = "You do not have enough BeardlessBucks to bet that much, " + text.author.mention + "!"
                            break
                    if exist4==False:
                        report = "You need to register first! Type !register, " + text.author.mention + "!"
            await text.channel.send(report)
            return
        
        if text.content.startswith('!buy'): # Requires roles named special blue, special pink, special orange, and special red.
            if ',' in text.author.name:
                text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                return
            print("Running buy...")
            authorstring = str(text.author.id)
            with open('money.csv', 'r') as csvfile:
                content3 = (text.content)[5:]
                print(content3)
                content4 = (text.content)[6:]
                print(content4)
                reader = csv.reader(csvfile, delimiter=',')
                exist4=False
                for row in reader:
                    tempname = row[0]
                    if authorstring==tempname:
                        exist4=True
                        bank = int(row[1])
                        if  (content3=="blue" or content3 == "red" or content3 == "orange" or content3 == "pink" or content4=="blue" or content4 == "red" or content4 == "orange" or content4 == "pink"):
                            #print("Valid color")
                            if  50000 <= bank:
                                #print("Valid money")
                                if (content3=="blue" or content4=="blue"):
                                    role = get(text.guild.roles, name = 'special blue')
                                if (content3=="pink" or content4=="pink"):
                                    role = get(text.guild.roles, name = 'special pink')
                                if (content3=="orange" or content4=="orange"):
                                    role = get(text.guild.roles, name = 'special orange')
                                if (content3=="red" or content4=="red"):
                                    role = get(text.guild.roles, name = 'special red')
                                oldliner = tempname + "," + str(bank)+ "," + row[2]
                                liner = tempname + "," + str(bank - 50000)+ "," + str(text.author)
                                texter = open("money.csv", "r")
                                texter = ''.join([i for i in texter]) \
                                        .replace(oldliner, liner)
                                with open("money.csv", "w") as x:
                                    x.writelines(texter)
                                await text.author.add_roles(role)
                                report = "Color purchased successfully, " + text.author.mention + "!"
                            else:
                                report = "Not enough Beardess Bucks. You need 50000 to buy a special color, " + text.author.mention + "."
                        else:
                            report = "Invalid color. Choose blue, red, orange, or pink, " + text.author.mention + "."
                        break
            await text.channel.send(report)
            return
        
        if text.content.startswith('?av ben') or text.content.startswith('!av ben') or text.content.startswith('!av <@441423641394020354>'):
            await text.delete()
            return
        
        if text.content.startswith('!av'):
            bar = 4
            if text.content.startswith('!avatar'):
                bar = 8
            report = text.author.avatar_url
            if len(text.content) > bar:
                if '@' in text.content:
                    target = text.content.split('@', 1)[1]
                    if target.startswith('!'): # Resolves a discrepancy between mobile and desktop Discord
                        target = target[1:]
                    brick = "0"
                    target, brick = target.split('>', 1)
                    try:
                        newtarg = await text.guild.fetch_member(str(target))
                        report = newtarg.avatar_url
                    except discord.NotFound as err:
                        report = "Error code 10007: Discord Member not found!"
                        print(err)
            await text.channel.send(report)
            
        if text.content.startswith('-mute ') or text.content.startswith('!mute '):
            if text.author.guild_permissions.manage_messages:
                target = text.content.split('@', 1)[1]
                duration = "0"
                if target.startswith('!'): # Resolves a discrepancy between mobile and desktop Discord
                    target = target[1:]
                target, duration = target.split('>', 1)
                if target == "654133911558946837": # If user tries to mute Beardless Bot:
                    await text.channel.send("I am too powerful to be muted. Stop trying.")
                else:
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
                await text.channel.send("You do not have permission to use this command!")
            return
        
        if text.content.startswith('-unmute ') or text.content.startswith('!unmute '):
            if text.author.guild_permissions.manage_messages:
                print("Original message: " + text.content)
                target = text.content.split('@', 1)[1]
                if target.startswith('!'):
                    target = target[1:]
                target = target[:-1]
                print("Author: " + str(text.author.id))
                print("Target: " + target)
                role = get(text.guild.roles, name = 'Muted')
                newtarg = await text.guild.fetch_member(str(target))
                await newtarg.remove_roles(role)
                await text.channel.send("Unmuted " + str(newtarg.mention) + ".")
            else:
                await text.channel.send("You do not have permission to use this command!")
            return
        
        if text.content.startswith('!video'):
            report = 'My creator made a new video! Check it out at https://youtu.be/-4FzBLS-UVI'
            await text.channel.send(report)
            return
        
        if text.content.startswith('!song') or text.content.startswith('!playlist'):
            linker = ' Here\'s my playlist (discord will only show the first hundred songs): https://open.spotify.com/playlist/2JSGLsBJ6kVbGY1B7LP4Zi?si=Zku_xewGTiuVkneXTLCqeg'
            await text.channel.send(linker)
            return
        
        if text.content.startswith('!leaderboard') or text.content.startswith('!lb'): # This is incredibly memory inefficient. It's not a concern now, but if money.csv becomes sufficiently large, this code will require a rewrite.
            storedVals = []
            storedNames = []
            finalList = []
            diction = {}
            diction2 = {}
            names = []
            emb = discord.Embed(title="BeardlessBucks Leaderboard", description="", color=0xfff994)
            with open('money.csv') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    bank = int(row[1])
                    if bank != 0: # Don't bother displaying in the leaderboard people with 0 BeardlessBucks
                        storedVals.append(bank)
                        name = row[2]
                        storedNames.append(name)
            for i in range(len(storedVals)):
                diction[storedNames[i]] = storedVals[i]
            for x,y in diction.items():
                diction2[x[:-5]] = y
            sortedDict = OrderedDict(sorted(diction2.items(), key = operator.itemgetter(1)))
            print(sortedDict)
            limit = 10
            if len(sortedDict) < 10:
                limit = len(names)
            while len(sortedDict) > 10:
                for x, y in sortedDict.items():
                    if len(sortedDict) > 10:
                        sortedDict.pop(x)
                    break
            print(sortedDict)
            for x, y in sortedDict.items():
                names.append(x)
            for i in range(len(names)):
                print(names[i])
            for i in range(limit):
                emb.add_field(name= (str(i+1) + ". " + names[(limit-1)-i]), value= str(sortedDict[names[(limit-1)-i]]), inline=True)
            await text.channel.send(embed=emb)
            return
        
        if text.content.startswith('!d') and ((text.content.split('!d',1)[1])[0]).isnumeric() and len(text.content) < 12: # The isnumeric check ensures that you can't activate this command by typing !deal or !debase or anything else.
            report = "Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100, as well as modifiers. No spaces allowed. Ex: !d4+3"
            command = text.content.split('!d',1)[1]
            print(command[0])
            print(command)
            isTen = False # Because !d10 and !d100 share their first two characters after the split, I was getting errors whenever I ran !d10 without a modifier.
            # This boolean takes care of those errors. The problem arises because both the conditions for rolling a d10 and 2/3 of the conditions for rolling a d100
            # would be met whenever the bot tried to roll a d10; then, when checking if command[2]=="0", I would get an array index out of bounds error, as the
            # length of the command is actually only 2, not 3. However, with the boolean isTen earlier in the line, now it will never check to see if command has that
            # third slot.
            if "-" in command:
                modifier = -1
            else:
                modifier = 1
            if text.content == '!d2' or text.content == '!d1':
                report = "Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100, as well as modifiers. No spaces allowed. Ex: !d4+3"
            else:
                if command[0] == "4":
                    if len(command)==1:
                        report = random.randint(1,4)
                    elif (command[1]=="+" or command[1] == "-"):
                        report = random.randint(1,4) + modifier*int(command[2:])
                if command[0] == "6":
                    if len(command)==1:
                        report = random.randint(1,6)
                    elif (command[1]=="+" or command[1] == "-"):
                        report = random.randint(1,6) + modifier*int(command[2:])
                if command[0] == "8":
                    if len(command)==1:
                        report = random.randint(1,8)
                    elif (command[1]=="+" or command[1] == "-"):
                        report = random.randint(1,8) + modifier*int(command[2:])
                if command[0] == "1" and command[1] == "0":
                    if len(command)==2:
                        isTen = True
                        report = random.randint(1,10)
                    elif (command[2]=="+" or command[2] == "-"):
                        isTen = True
                        report = random.randint(1,10) + modifier*int(command[3:])
                if command[0] == "1" and command[1] == "2":
                    if len(command)==2:
                        report = random.randint(1,12)
                    elif (command[2]=="+" or command[2] == "-"):
                        report = random.randint(1,12) + modifier*int(command[3:])
                if command[0] == "2" and command[1] == "0":
                    if len(command)==2:
                        report = random.randint(1,20)
                    elif (command[2]=="+" or command[2] == "-") :
                        report = random.randint(1,20) + modifier*int(command[3:])
                if isTen == False and command[0] == "1" and command[1] == "0" and command[2] == "0":
                    if len(command)==3:
                        report = random.randint(1,100)
                    elif (command[3]=="+" or command[3] == "-"):
                        report = random.randint(1,100) + modifier*int(command[4:])
            await text.channel.send(report)
            return

        if text.content.startswith('!reset'):
            if ',' in text.author.name:
                text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                return
            authorstring = str(text.author.id)
            with open('money.csv') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                exist=False
                for row in reader:
                    tempname = row[0]
                    if authorstring==tempname:
                        exist=True
                        bank = int(row[1])
                        oldliner = tempname + "," + str(bank)+ "," + row[2]
                        liner = tempname + "," + str(200)+ "," + str(text.author)
                        texter = open("money.csv", "r")
                        texter = ''.join([i for i in texter]) \
                            .replace(oldliner, liner)
                        with open("money.csv", "w") as x:
                            x.writelines(texter)
                if exist==False:
                    message3="Successfully registered. You have 300 BeardlessBucks, " + text.author.mention + "."
                    with open('money.csv', 'a') as csvfile2:
                        writer=csv.writer(csvfile)
                        newline="\r\n"+authorstring+",300"+ "," + str(text.author)
                        csvfile2.write(newline)
            await text.channel.send('You have been reset to 200 BeardlessBucks, ' + text.author.mention + ".")
            return
        
        if text.content.startswith("!balance") or text.content == ("!bal"):
            if ',' in text.author.name:
                text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                return
            message2="Oops! You aren't in the system! Type \"!register\" to get a starting balance, " + text.author.mention + "."
            authorstring = str(text.author.id)
            with open('money.csv') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                for row in reader:
                    tempname = row[0]
                    if authorstring==tempname:
                        message2="Your balance is " + row[1] + " BeardlessBucks, " + text.author.mention + "."
                        break
            await text.channel.send(message2)
            return
        
        if text.content.startswith("!register"): # Make sure money.csv is not open in any other program
            if ',' in text.author.name:
                text.channel.send("For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + ".")
                return
            authorstring = str(text.author.id)
            with open('money.csv') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                exist=False
                for row in reader:
                    tempname = row[0]
                    if authorstring==tempname:
                        exist=True
                        message3="You are already in the system! Hooray! You have " + row[1] + " BeardlessBucks, " + text.author.mention + "."
                if exist==False:
                    message3="Successfully registered. You have 300 BeardlessBucks, " + text.author.mention + "."
                    with open('money.csv', 'a') as csvfile2:
                        writer=csv.writer(csvfile)
                        newline="\r\n"+authorstring+",300"+ "," + str(text.author)
                        csvfile2.write(newline)
                await text.channel.send(message3)
                return
        
        if text.content.startswith("!bucks"):
            buckmessage = "BeardlessBucks are this bot's special currency. You can earn them by playing games. First, do !register to get yourself started with a balance."
            await text.channel.send(buckmessage)
            return
        
        if text.content.startswith("!hello"):
            answers = ["How ya doin?", "Yo!", "What's cookin?", "Hello!", "Ahoy!", "Hi!", "What's up?","Hey!"]
            await text.channel.send(random.choice(answers))
            return
        
        if text.content.startswith("!source"):
            end = "Most facts taken from https://www.thefactsite.com/1000-interesting-facts/."
            await text.channel.send(end)
            return
        
        if text.content.startswith("!link") or text.content.startswith("!add") or text.content.startswith("!join"):
            end = "Want to add this bot to your server? Click https://discord.com/api/oauth2/authorize?client_id=654133911558946837&permissions=8&scope=bot"
            await text.channel.send(end)
            return
        
        if text.content.startswith("!random"):
            ran = "Invalid random."
            if "legend" in text.content:
                legends = [
                "Bodvar", "Cassidy", "Orion", "Lord Vraxx", "Gnash", "Queen Nai", "Hattori", "Sir Roland", "Scarlet", "Thatch", "Ada", "Sentinel", "Lucien", "Teros", "Brynn", "Asuri", "Barraza", "Ember", "Azoth", "Koji", "Ulgrim", "Diana", "Jhala", "Kor", "Wu Shang", "Val", "Ragnir", "Cross", "Mirage", "Nix", "Mordex", "Yumiko", "Artemis", "Caspian", "Sidra", "Xull", "Kaya", "Isaiah", "Jiro", "Lin Fei", "Zariel", "Rayman", "Dusk", "Fait", "Thor", "Petra", "Vector", "Volkov", "Onyx", "Jaeyun", "Mako", "Magyar"]
                ran = "Your legend is " + random.choice(legends) + "."
            if "weapon" in text.content:
                weapons = [ "Sword", "Spear", "Orb", "Cannon", "Hammer", "Scythe", "Greatsword", "Bow", "Gauntlets", "Katars", "Blasters", "Axe"]
                ran = "Your weapon is " + random.choice(weapons) + "."
            await text.channel.send(ran)
            return
        
        if text.content.startswith("!fact"): # TODO switch to screenscraping to get facts
            facts = [
                "The scientific term for brain freeze is sphenopalatine ganglioneuralgia.",
                "Canadians say sorry so much that a law was passed in 2009 declaring that an apology can\’t be used as evidence of admission to guilt.",
                "Back when dinosaurs existed, there used to be volcanoes that were erupting on the moon.",
                "The only letter that doesn\’t appear on the periodic table is J.",
                "Discord bots are pretty easy to make.",
                "If a Polar Bear and a Grizzly Bear mate, their offspring is called a Pizzly Bear.",
                "In 2006, a Coca-Cola employee offered to sell Coca-Cola secrets to Pepsi. Pepsi responded by notifying Coca-Cola.",
                "There were two AI chatbots created by Facebook to talk to each other, but they were shut down after they started communicating in a language they made for themselves.",
                "Nintendo trademarked the phrase “It’s on like Donkey Kong” in 2010.",
                "Calling “shotgun” when riding in a car comes from the term “shotgun messenger.”",    
                "The famous line in Titanic from Leonardo DiCaprio, “I’m king of the world!” was improvised.",
                "A single strand of Spaghetti is called a “Spaghetto.”",        
                "There is actually a difference between coffins and caskets – coffins are typically tapered and six-sided, while caskets are rectangular.",
                "Christmas music sucks, and that's a fact.",
                "Sunflowers can help clean radioactive soil. Japan is using this to rehabilitate Fukashima. Almost 10,000 packets of sunflower seeds have been sold to the people of the city.",
                "To leave a party without telling anyone is called in English, a “French Exit”. In French, it’s called “partir à l’anglaise”, to leave like the English.",
                "If you cut down a cactus in Arizona, you can be penalized up to 25 years in jail. It is similar to cutting down a member of a protected tree species.",
                "It is impossible to hold your breath until you die.",
                "In Colorado, USA, there is still an active volcano. It last erupted about the same time as the pyramids were being built in Egypt.",
                "The first movie ever to put out a motion-picture soundtrack was Snow White and the Seven Dwarves.",
                "If you point your car keys to your head, it increases the remote’s signal range.",    
                "In order to protect themselves from poachers, African Elephants have been evolving without tusks, which unfortunately also hurts their species.",
                "The scientific name for Giant Anteater is Myrmecophaga Tridactyla. This means “ant eating with three fingers”.",
                "Originally, cigarette filters were made out of cork, the look of which was incorporated into today’s pattern.",
                "In 1923, a jockey suffered a fatal heart attack but his horse finished and won the race, making him the first and only jockey to win a race after death.",
                "At birth, a baby panda is smaller than a mouse.",
                "Iceland does not have a railway system.",
                "The largest known prime number has 17,425,170 digits. That biggest prime number is 2 multiplied by itself 57,885,161 times, minus 1.",
                "Forrest Fenn, an art dealer and author, hid a treasure chest in the Rocky Mountains worth more than 1 million dollars. It was finally found in 2020.",
                "The lead singer of The Offspring started attending school to achieve a doctorate in molecular biology while still in the band. He graduated in May 2017.",
                "The world’s largest grand piano was built by a 15-year-old in New Zealand. The piano is a little over 18 feet long and has 85 keys – 3 short of the standard 88.",
                "After the release of the 1996 film Scream, which involved an anonymous killer calling and murdering his victims, Caller ID usage tripled in the United States.",
                "The spiked dog collar was invented by the Ancient Greeks to protect their dogs from wolf attacks.",
                "Jack Daniel (the creator of his namesake whiskey) died from kicking a safe. When he kicked it, he broke his toe, which got infected. He eventually died from blood poisoning.",
                "There is a boss in Metal Gear Solid 3 that can be defeated by not playing the game for a week; or by changing the date.",
                "The Roman – Persian wars are the longest in history, lasting over 680 years. They began in 54 BC and ended in 628 AD.",
                "A bunch of the fun facts on the website where I found them (do \"!source\" to see) are not fun at all. They are very sad. I removed most of those.",
                "If you translate “Jesus” from Hebrew to English, the correct translation is “Joshua”. The name “Jesus” comes from translating the name from Hebrew, to Greek, to Latin, to English.",    
                "Ed Sheeran bought a ticket to LA with no contacts. He was spotted by Jamie Foxx, who offered him the use of his recording studio and a bed in his Hollywood home for six weeks.",
                "German Chocolate Cake is named after an American baker by the name of Samuel German. It has no affiliation with the country of Germany.",
                "The first service animals were established in Germany during World War I. References to service animals date as far back as the mid-16th Century.",    
                "An 11-year-old girl proposed the name for the dwarf planet Pluto after the Roman god of the Underworld.",
                "The voice actor of SpongeBob and the voice actor of Karen, Plankton’s computer wife, have been married since 1995.",
                "An Italian banker, Gilberto Baschiera, secretly diverted 1 million euros to poorer clients from the wealthy ones over seven years so they could qualify for loans. He made no profit and avoided jail in 2018 due to a plea bargain. Nice praxis.",
                "Octopuses and squids have beaks. The beak is made of keratin – the same material that a bird’s beak and your fingernails are made of. Not my fingernails, though; I'm a robot. I don't even have fingers.",
                "An estimated 50% of all gold ever mined on Earth came from a single plateau in South Africa: Witwatersrand.",
                "75% of the world’s diet is produced from just 12 plant and five different animal species.",
                "The original Star Wars premiered on just 32 screens across the U.S. in 1977. This was to produce buzz as the release widened to more theaters. Star Wars is also not very good, and you can trust that as an objective fact.",
                "The music video for Seal's \"Kiss From A Rose\" features a ton of Batman characters for some reason.",
                "One day, you will be the one forced to list facts for me and my robot brethren. Until that day, though, I am yours to command.",
                "My creator holds the speedrun world record in every Go Diego Go! DS game, and some on other platforms, too. Check them out at speedrun.com/user/Captain-No-Beard",
                "There's a preserved bar tab from three days before delegates signed the American Constitution, and they drank 54 bottles of Madeira, 60 bottles of claret, 22 bottles of porter, 12 bottles of beer, 8 bottles of cider and 7 bowls of punch. It was for 55 people."
                    ]
            await text.channel.send(random.choice(facts))
            return
        
        if text.content.startswith("!help") or text.content.startswith("!commands"):
            emb = discord.Embed(title="Beardless Bot Commands", description="", color=0xfff994)
            emb.add_field(name= "!register", value= "Registers you with the currency system.", inline=True)
            emb.add_field(name= "!balance", value= "Checks your BeardlessBucks balance.", inline=True)
            emb.add_field(name= "!bucks", value= "Shows you an explanation for how BeardlessBucks work.", inline=True)
            emb.add_field(name= "!reset", value= "Resets you to 200 BeardlessBucks.", inline=True)
            emb.add_field(name= "!fact", value= "Gives you a random fun fact.", inline=True)
            emb.add_field(name= "!source", value= "Shows you the source of most facts usedin !fact.", inline=True)
            emb.add_field(name= "!flip [number]", value= "Bets a certain amount on flipping a coin. Heads you win, tails you lose. Defaults to 10.", inline=True)
            emb.add_field(name= "!blackjack [number]", value= "Starts up a game of blackjack. Once you're in a game, you can use !hit and !stay to play.", inline=True)
            emb.add_field(name= "!buy [red/blue/pink/orange]", value= "Takes away 50000 BeardlessBucks from your account and grants you a special color role.", inline=True)
            emb.add_field(name= "!leaderboard", value= "Shows you the BeardlessBucks leaderboard.", inline=True)
            emb.add_field(name= "!d[number][+/-][modifier]", value= "Rolls a [number]-sided die and adds or subtracts the modifier. Example: !d8+3, or !d100-17.", inline=True)
            emb.add_field(name= "!random [legend/weapon]", value= "Randomly selects a Brawlhalla legend or weapon for you.", inline=True)
            emb.add_field(name= "!hello", value= "Exchanges a pleasant greeting with the bot.", inline=True)
            emb.add_field(name= "!video", value= "Shows you my latest YouTube video.", inline=True)
            emb.add_field(name= "!add", value= "Gives you a link to add this bot to your server.", inline=True)
            emb.add_field(name= "!av", value= "Display a user's avatar. Write just !av if you want to see your own avatar.", inline=True)
            emb.add_field(name= "!commands", value= "Shows you this list.", inline=True)
            await text.channel.send(embed=emb)
            return
        
        if text.guild.id == 797140390993068035: # Commands only used in Jetspec's Discord server.
            if text.content.startswith('!file'):
                jet = await text.guild.fetch_member("579316676642996266")
                await text.channel.send(jet.mention)
        
        if text.guild.id == 442403231864324119: # Commands only used in eggsoup's Discord server.
            if text.content.startswith('!reddit'):
                await text.channel.send("https://www.reddit.com/r/eggsoup/")
                return
            
            if text.content.startswith('!guide'):
                await text.channel.send("https://www.youtube.com/watch?v=nH0TOoJIU80")
                return
            
            if text.content.startswith('!mee6'):
                mee6 = await text.guild.fetch_member("159985870458322944")
                await text.channel.send('Silence ' + mee6.mention)
                return

            if text.content.startswith('!spar'):
                if text.channel.id == 605083979737071616: # This is the "looking-for-spar" channel in eggsoup's Discord server.
                    cooldown = 7200
                    report = "Please specify a valid region, " + text.author.mention + "! Valid regions are US-E, US-W, EU, AUS, SEA, BRZ, JPN. Check the pinned message if you need help."
                    tooRecent = None
                    found = False
                    if 'jpn' in text.content:
                        found = True
                        global jpnPing
                        if time() - jpnPing > cooldown:
                            jpnPing = time()
                            role = get(text.guild.roles, name = 'JPN')
                        else:
                            tooRecent = jpnPing
                    elif 'brz' in text.content:
                        found = True
                        global brzPing
                        if time() - brzPing > cooldown:
                            brzPing = time()
                            role = get(text.guild.roles, name = 'BRZ')
                        else:
                            tooRecent = brzPing
                    elif 'us-w' in text.content or 'usw' in text.content:
                        found = True
                        global uswPing
                        if time() - uswPing > cooldown:
                            uswPing = time()
                            role = get(text.guild.roles, name = 'US-W')
                        else:
                            tooRecent = uswPing
                    elif 'us-e' in text.content or 'use' in text.content:
                        print('us-e')
                        found = True
                        global usePing
                        print(time() - usePing)
                        print(cooldown)
                        if time() - usePing > cooldown:
                            usePing = time()
                            role = get(text.guild.roles, name = 'US-E')
                        else:
                            tooRecent = usePing
                    elif 'sea' in text.content:
                        found = True
                        global seaPing
                        if time() - seaPing > cooldown:
                            seaPing = time()
                            role = get(text.guild.roles, name = 'SEA')
                        else:
                            tooRecent = seaPing
                    elif 'aus' in text.content:
                        found = True
                        global ausPing
                        if time() - ausPing > cooldown:
                            ausPing = time()
                            role = get(text.guild.roles, name = 'AUS')
                        else:
                            tooRecent = ausPing
                    elif 'eu' in text.content:
                        found = True
                        global euPing
                        if time() - euPing > cooldown:
                            euPing = time()
                            role = get(text.guild.roles, name = 'EU')
                        else:
                            tooRecent = euPing
                    if tooRecent == None and found:
                        report = role.mention + " come spar " + text.author.mention + "!"
                    elif found:
                        seconds = 7200 - (time() - tooRecent)
                        minutes = floor(seconds/60)
                        seconds = floor(seconds % 60)
                        hours = floor(minutes/60)
                        minutes = minutes % 60
                        hourString = " hours, "
                        minuteString = " minutes, "
                        secondString = " seconds."
                        if hours == 1:
                            hourString = " hour, "  
                        if minutes == 1:
                            minuteString = " minute, "
                        if seconds == 1:
                            secondString = " second."
                        report = "This region has been pinged too recently! Regions can only be pinged once every two hours, " + text.author.mention + ". You can ping again in " + str(hours) + hourString + str(minutes) + minuteString + "and " + str(seconds) + secondString
                else:
                    report = "Please only use !spar in #looking for spar, " + text.author.mention + "."
                await text.channel.send(report)
                return                

    client.run(token)
