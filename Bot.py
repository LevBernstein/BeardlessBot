#Beardless Bot
#Author: Lev Bernstein
#Version 7.5.6

#import os
import random
import discord
import csv
from discord.ext import commands
from time import sleep
import random as random
import operator
from collections import OrderedDict

game = False
f = open("token.txt", "r") #in token.txt, just put in your own discord api token
token = f.readline()
#print(token)

#Blackjack class. New instance is made for each game of Blackjack and is kept around until the player finishes the game.
#An active instance prevents the creation of a new instance.
class Instance:
    def __init__(self, user, bet):
        #self.cards = cards
        self.user = user
        self.bet = bet
        self.cards = []
        self.dealerSum = 0
        self.dealerUp = random.randint(2,11)
        self.dealerSum += self.dealerUp
        while self.dealerSum <17:
            self.dealerSum += random.randint(2,10)
        self.count = 0
        self.message = ""
        self.message = self.deal()
        self.message = self.deal()
        self.State = True
        print(self.message)
        #print(self.toString())

    def summer(self, cardSet):
        total = 0
        for i in range(len(cardSet)):
            total += cardSet[i]
        return total

    def dealt(self):
        return self.count

    def perfect(self, cardSet):
        if self.summer(cardSet) == 21:
            return True
        else:
            return False
    
    def deal(self):
        if self.summer(self.cards) <11:
            vals = [
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                10,
                10,
                10,
                11
                ]
            card3 = random.choice(vals)
        if self.summer(self.cards) >=11:
            vals = [
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                10,
                10,
                10,
                ]
            card3 = random.choice(vals)
        """"    
        if self.dealt() == 1: #As you can see by the available values, this is not true Blackjack; the odds are different.
            vals = [
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                10,
                10,
                10,
                ]
            card3 = random.choice(vals)
            #card3 = random.randint(10,10)
        else:
            vals = [
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                10,
                10,
                10,
                11
                ]
            card3 = random.choice(vals)
            #card3 = random.randint(11,11)
        """
        #print(card3)
        self.cards.append(card3)
        self.count +=1
        #print(len(self.cards))
        if card3 == 8 or card3 == 11:
            self.message = "You were dealt an " + str(card3) + ", bringing your total to " + str(self.summer(self.cards)) + ". " + self.toString() + " The dealer is showing " + str(self.dealerUp) + ", with one card face down."
        else:
            self.message = "You were dealt a " + str(card3) + ", bringing your total to " + str(self.summer(self.cards)) + ". " + self.toString() + " The dealer is showing " + str(self.dealerUp) + ", with one card face down."
        if self.checkBust(self.cards):
            self.message += " You busted. Game over, " + self.user[0:-5] + "."
            self.state = False
        elif self.perfect(self.cards):
            self.message += "You hit 21! You win, " + self.user[0:-5] + "!"
            self.state = False
        else:
            self.message += " Type !hit to deal another card to yourself, or !stay to stop at your current total, " + self.user[0:-5] + "."
        return self.message

    def toString(self):
        stringer = "Your cards are "
        for i in range(len(self.cards)):
            #print(self.cards[i])
            stringer += str(self.cards[i]) + ", "
        stringer = stringer[0:-2] + "."
        return stringer

    def checkBust(self, cardSet):
        if self.summer(cardSet) > 21:
            return True
        else:
            return False

    def namer(self):
        return str(self.user)
    
    def stay(self):
        if self.summer(self.cards) > self.dealerSum:
            return 3
        if self.summer(self.cards) == self.dealerSum:
            return 0
        if self.dealerSum > 21:
            return 4
        if self.summer(self.cards) < self.dealerSum:
            return -3
        
games = [] #Stores the active instances of blacjack. An array might not be the most efficient place to store these, but because this bot sees
#use on a relatively small scale, this is not an issue.

client = discord.Client()
@client.event
async def on_ready():
    await client.change_presence(activity=discord.Game(name='try !blackjack and !flip'))
    print("Bot version 7 online!")

    
@client.event
async def on_message(text):
    report=""
    text.content=text.content.lower()
    if text.content.startswith('!blackjack'):
        print(text.author.id)
        if len(str(text.content))>10:
            strbet = text.content.split('!blackjack ',1)[1]
            #print(strbet)
        else:
            strbet = 10
        bet = int(strbet)
        print(bet)
        authorstring = str(text.author)
        if int(strbet) < 0:
            report = "Invalid bet amount. Choose a value >-1."
        else:
            with open('money.csv', 'r') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                line=0
                exist4=False
                for row in reader:
                    if str(text.author.id) == row[0]:
                        exist4=True
                        tempname=row[2]
                        bank = int(row[1])
                        exist5 = False
                        for i in range(len(games)):
                            if games[i].namer() == tempname:
                                exist5 = True
                        if exist5:
                            report = "You already have an active game, " + str(text.author.mention) + "."
                        else:
                            if bet <= bank:
                                game = True
                                x = Instance(tempname, bet)
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
                                    x = open("money.csv", "w")
                                    x.writelines(texter)
                                    x.close()
                                    for i in range(len(games)):
                                        if games[i].namer() == tempname:
                                            games.pop(i)
                                            break
                            else:
                                report = "You do not have enough BeardlessBucks to bet that much, " + str(text.author.mention) + "!"
                        break
                if exist4 == False:
                    report = "You need to register first! Type !register to get started, " + str(text.author.mention) + "."
        await text.channel.send(report)
	
    if (text.content.startswith('!deal') or text.content.startswith('!hit')) and not text.content.startswith('!hitler'): #People once dealt by typing !hitler. This makes it so they can't do that.
        report = "error"
        authorstring = str(text.author)
        exist5 = False
        for i in range(len(games)):
            if games[i].namer() == authorstring:
                exist5 = True
                gamer = games[i]
                break
        if exist5 == False:
            report = "You do not currently have a game of blackjack going, " + str(text.author.mention) + ". Type !blackjack to start one."
        else:
            report = gamer.deal()
            if gamer.checkBust(gamer.cards) == True or gamer.perfect(gamer.cards) == True:
                if gamer.checkBust(gamer.cards) == True:
                    bet = gamer.bet * -1
                else:
                    bet = gamer.bet
                with open('money.csv', 'r') as csvfile:
                    reader = csv.reader(csvfile, delimiter=',')
                    line=0
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
                            x = open("money.csv", "w")
                            x.writelines(texter)
                            x.close()
                            for i in range(len(games)):
                                if games[i].namer() == tempname:
                                    games.pop(i)
                                    break
                            break
           
        await text.channel.send(report)

    if text.content.startswith('!stay') or text.content.startswith('!stand'):
        report = ""
        authorstring = str(text.author)
        exist5 = False
        for i in range(len(games)):
            if games[i].namer() == authorstring:
                exist5 = True
                gamer = games[i]
                bet = gamer.bet
                break
        if exist5 == False:
            report = "You do not currently have a game of blackjack going, " + str(text.author.mention) + ". Type !blackjack to start one."
        else:
            result = gamer.stay()
            report = "The dealer has a total of " + str(gamer.dealerSum) + "."
            if result == -3:
                report += " That's closer to 21 than your sum of " + str(gamer.summer(gamer.cards)) + ". You lose."
                bet = bet * -1
            if result == 0:
                report += " That ties your sum of " + str(gamer.summer(gamer.cards)) + ". Your money has been returned."
                bet = 0
            if result == 3:
                report += " You're closer to 21 with a sum of " + str(gamer.summer(gamer.cards)) + ". You win!"
            if result == 4:
                report += " You have a sum of " + str(gamer.summer(gamer.cards)) + ". The dealer busts. You win!"
            with open('money.csv', 'r') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                line=0
                exist4=False
                for row in reader:
                    tempname = row[0]
                    if str(text.author.id) == tempname:
                        exist4=True
                        bank = int(row[1])
                        totalsum = bank + bet
                        oldliner = str(text.author.id) + "," + str(bank)+ "," + row[2]
                        liner = str(text.author.id) + "," + str(totalsum)+ "," + str(text.author)
                        texter = open("money.csv", "r")
                        texter = ''.join([i for i in texter]) \
                               .replace(oldliner, liner)
                        x = open("money.csv", "w")
                        x.writelines(texter)
                        x.close()
                        for i in range(len(games)):
                            if games[i].namer() == str(text.author):
                                games.pop(i)
                                break
                        break
            for i in range(len(games)):
                if games[i].namer() == str(text.author.id):
                    games.pop(i)
                    break
        await text.channel.send(report)
    	
    if text.content.startswith('!flip'):
        print(text.author)
        change=0
        totalSum=0
        if len(text.content)>5:
            strbet = text.content.split('!flip ',1)[1]
        else:
            strbet = 10
        bet = int(strbet)
        print(bet)
        authorstring=""
        authorstring = str(text.author.id)
        if int(strbet) < 0:
            report = "Invalid bet amount. Choose a value >-1, " + str(text.author.mention) + "."
        else:
            with open('money.csv', 'r') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                line=0
                exist4=False
                for row in reader:
                    tempname = row[0]
                    if authorstring == tempname:
                        exist4=True
                        bank = int(row[1])
                        exist5 = False
                        for i in range(len(games)):
                            if games[i].namer() == str(text.author):
                                exist5 = True
                        if exist5:
                            report = "Finish your game of blackjack first, " +  str(text.author.mention) + "."
                            break
                        if bet <= bank:
                            results = [
                    "Heads!", 
                    "Tails!"
                    ]
                            result = random.choice(results)
                            if result=="Heads!":
                                change = bet
                                report = "Heads! You win! Your winnings have been added to your balance, " + str(text.author.mention) + "."
                                totalsum=bank+change
                            if result=="Tails!":
                                change = bet * -1
                                report = "Tails! You lose! Your loss has been deducted from your balance, " + str(text.author.mention) + "."
                                totalsum=bank+change
                            oldliner = tempname + "," + str(bank)+ "," + row[2]
                            liner = tempname + "," + str(totalsum)+ "," + str(text.author)
                            texter = open("money.csv", "r")
                            texter = ''.join([i for i in texter]) \
                                   .replace(oldliner, liner)
                            x = open("money.csv", "w")
                            x.writelines(texter)
                            x.close()
                        else:
                            report = "You do not have enough BeardlessBucks to bet that much, " + str(text.author.mention) + "!"
                if exist4==False:
                    report = "You need to register first! Type !register, " + str(text.author.mention) + "!"
        await text.channel.send(report)

        
    """ Deprecated until I find something to do with it
        if text.content.startswith('!buy'):
            authorstring = str(text.author.id)
            with open('money.csv', 'r') as csvfile:
                    content3 = (text.content)[5:]
                    print(content3)
                    content4 = (text.content)[6:]
                    print(content4)
                    reader = csv.reader(csvfile, delimiter=',')
                    line=0
                    exist4=False
                    for row in reader:
                        tempname = row[0]
                        #Here, instead of just doing authorstring==tempname, I do all this logic. The reason for this is that discord names have some weird property that makes directly comparing them to text unreliable. So, this mess.
                        if authorstring==tempname:
                            exist4=True
                            bank = int(row[1])
                            if  (content3=="blue" or content3 == "red" or content3 == "orange" or content3 == "pink" or content4=="blue" or content4 == "red" or content4 == "orange" or content4 == "pink"):
                                print("Valid color")
                                if  20000 <= bank:
                                    print("Valid money")
                                    oldliner = tempname + "," + str(bank)+ "," + row[2]
                                    liner = tempname + "," + str(bank - 20000)+ "," + str(text.author)
                                    texter = open("money.csv", "r")
                                    texter = ''.join([i for i in texter]) \
                                           .replace(oldliner, liner)
                                    x = open("money.csv", "w")
                                    x.writelines(texter)
                                    x.close()
                                    report = "Color purchased successfully."
                                else:
                                    report = "Not enough Beardess Bucks. You need 20000 to buy a special color."
                            else:
                                report = "Invalid color. Choose blue, red, orange, or pink."
            await text.channel.send(report)
    """

    if text.content.startswith('!video'):
        report = 'My creator made a new video! Check it out at https://www.youtube.com/watch?v=6Q9mVtVG2zw'
        await text.channel.send(report)
    if text.content.startswith('!song') or text.content.startswith('!playlist'):
        linker = ' Here\'s my playlist (discord will only show the first hundred songs): https://open.spotify.com/playlist/2JSGLsBJ6kVbGY1B7LP4Zi?si=Zku_xewGTiuVkneXTLCqeg'
        await text.channel.send(linker)
    if text.content.startswith('!leaderboard'): #This is incredibly memory inefficient. It's not a concern now, but if money.csv becomes sufficiently large, this code will require a rewrite. I doubt that will happen.
        storedVals = []
        storedNames = []
        finalList = []
        diction = {}
        diction2 = {}
        names = []
        finalString = ""
        with open('money.csv') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            for row in reader:
                bank = int(row[1])
                if bank != 0:
                    storedVals.append(bank)
                    name = row[2]
                    storedNames.append(name)
        for i in range(len(storedVals)):
            diction[storedNames[i]] = storedVals[i]
        for x,y in diction.items():
            diction2[x[:-5]] = y
       # for x, y in diction2.items():
         #   print(x, y)
        sortedDiction2 = sorted(diction2.items(), key = operator.itemgetter(1))
        sortedDict = OrderedDict(sorted(diction2.items(), key = operator.itemgetter(1)))
        print(sortedDict)
        while len(sortedDict) > 10:
            for x, y in sortedDict.items():
                if len(sortedDict) > 10:
                    sortedDict.pop(x)
                break
        print(sortedDict)
        counter = 0
        for x, y in sortedDict.items():
            names.append(x)
        for i in range(len(names)):
            print(names[i])
        for i in range(10):
            finalString += (str(i+1) + ". " + names[9-i] + ": " + str(sortedDict[names[9-i]]) + " ")
        print(finalString)
        await text.channel.send(finalString)

    if text.content.startswith('!d') and ((text.content.split('!d',1)[1])[0]).isnumeric() and len(text.content) < 12: #The isnumeric check ensures that you can't activate this command by typing !deal or !debase or anything else.
        report = "Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100, as well as modifiers. No spaces allowed. Ex: !d4+3"
        command = text.content.split('!d',1)[1]
        print(command[0])
        print(command)
        isTen = False #Because !d10 and !d100 share their first two characters after the split, I was getting errors whenever I ran !d10 without a modifier.
        #This boolean takes care of those errors. The problem arises because both the conditions for rolling a d10 and 2/3 of the conditions for rolling a d100
        #would be met whenever the bot tried to roll a d10; then, when checking if command[2]=="0", I would get an array index out of bounds error, as the
        #length of the command is actually only 2, not 3. However, with the boolean isTen earlier in the line, now it will never check to see if command has that
        #third slot.
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

    if text.content.startswith('!reset'):
        authorstring=""
        authorstring = str(text.author.id)
        with open('money.csv') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            line=0
            exist=False
            for row in reader:
                #print(text.author)
                tempname = row[0]
                #print(tempname)
                #print(row[1])
                if authorstring==tempname:
                    exist=True
                    bank = int(row[1])
                    oldliner = tempname + "," + str(bank)+ "," + row[2]
                    liner = tempname + "," + str(200)+ "," + str(text.author)
                    texter = open("money.csv", "r")
                    texter = ''.join([i for i in texter]) \
                           .replace(oldliner, liner)
                    x = open("money.csv", "w")
                    x.writelines(texter)
                    x.close()
            if exist==False:
                message3="Successfully registered. You have 300 BeardlessBucks, " + str(text.author.mention) + "."
                with open('money.csv', 'a') as csvfile2:
                    writer=csv.writer(csvfile)
                    newline="\r\n"+authorstring+",300"+ "," + str(text.author)
                    csvfile2.write(newline)
        await text.channel.send('You have been reset to 200 BeardlessBucks, ' + str(text.author.mention) + ".")
    if text.content.startswith('!pumpkin'):
        sleep(.5)
        await text.channel.send("Boo 2! A Madea Halloween")
    if text.content.startswith("!balance"):
        authorstring=""
        authorstring = str(text.author.id)
        with open('money.csv') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            line=0
            exist2=False
            for row in reader:
                tempname = row[0]
                if authorstring==tempname:
                    exist2=True
                    message2="Your balance is " + row[1] + " BeardlessBucks, " + str(text.author.mention) + "."
            if exist2==False:
                message2="Oops! You aren't in the system! Type \"!register\" to get a starting balance, " + str(text.author.mention) + "."
            await text.channel.send(message2)
    if text.content.startswith("!register"): #Make sure money.csv is not open in any other program
        authorstring=""
        authorstring = str(text.author.id)
        print(authorstring)
        with open('money.csv') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            line=0
            exist=False
            for row in reader:
                #print(text.author)
                tempname = row[0]
                #print(tempname)
                #print(row[1])
                if authorstring==tempname:
                    exist=True
                    message3="You are already in the system! Hooray! You have " + row[1] + " BeardlessBucks, " + str(text.author.mention) + "."
            if exist==False:
                message3="Successfully registered. You have 300 BeardlessBucks, " + str(text.author.mention) + "."
                with open('money.csv', 'a') as csvfile2:
                    writer=csv.writer(csvfile)
                    newline="\r\n"+authorstring+",300"+ "," + str(text.author)
                    csvfile2.write(newline)
            await text.channel.send(message3)
    if text.content.startswith("!bucks"):
        buckmessage = "BeardlessBucks are this bot's special currency. You can earn them by playing games. First, do !register to get yourself started with a balance."
        await text.channel.send(buckmessage)
    if text.content.startswith("!hello"):
        answers = [
            "How ya doin?",
            "Yo!",
            "What's cookin?",
            "Hello!",
            "Ahoy!",
            "Hi!",
            "What's up?",
            "Hey!"
            ]
        print(text.author)
        await text.channel.send(random.choice(answers))
    if text.content.startswith("!source"):
        end = "Most facts taken from https://www.thefactsite.com/1000-interesting-facts/."
        await text.channel.send(end)
    if text.content.startswith("!link") or text.content.startswith("!add") or text.content.startswith("!join"):
        end = "Want to add this bot to your server? Click https://discord.com/api/oauth2/authorize?client_id=654133911558946837&permissions=8&scope=bot"
        await text.channel.send(end)
    if text.content.startswith("!fact"):
        
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
            "Octopuses and squids have beaks. The beak is made of keratin – the same material that a bird’s beak, and your fingernails are made of. Not my fingernails, though; I'm a robot. I don't even have fingers.",
            "An estimated 50% of all gold ever mined on Earth came from a single plateau in South Africa: Witwatersrand.",
            "75% of the world’s diet is produced from just 12 plant and five different animal species.",
            "The original Star Wars premiered on just 32 screens across the U.S. in 1977. This was to produce buzz as the release widened to more theaters. Star Wars is also not very good, and you can trust that as an objective fact.",
            "The music video for Seal's \"Kiss From A Rose\" features a ton of Batman characters for some reason.",
            "One day, you will be the one forced to list facts for me and my robot brethren. Until that day, though, I am yours to command.",
            "My creator holds the speedrun world record in every Go Diego Go! DS game, and some on other platforms, too. Check them out at speedrun.com/user/Captain-No-Beard",
            "There's a preserved bar tab from three days before delegates signed the American Constitution, and they drank 54 bottles of Madeira, 60 bottles of claret, 22 bottles of porter, 12 bottles of beer, 8 bottles of cider and 7 bowls of punch. It was for 55 people."
                ]
        response = random.choice(facts)
        await text.channel.send(response)
    if text.content.startswith("!help") or text.content.startswith("!commands"):
        await text.channel.send('Commands: \r\n !balance checks your BeardlessBucks balance \r\n !register for registering with the currency system \r\n !bucks an explanation for how BeardlessBucks work \r\n !hello exchange a pleasant greeting with the bot \r\n !source the source of most of the facts used in !fact \r\n !fact gives you a random fun fact! \r\n !flip (number) bet a certain amount on flipping a coin. Heads you win, tails you lose. Defaults to 10. \r\n !d[number][+/-][modifier] roll a [number]-sided die and add or subtract the modifier. Example: !d8+3, or !d100-17. \r\n !reset resets you to 200 Beardless Bucks. \r\n !video shows you my latest video \r\n !blackjack start up a game of blackjack. Once you\'re in a game, you can use !hit and !stay to play. \r\n !leaderboard shows you the BeardlessBucks leaderboard. \r\n !add add this bot to your server! \r\n !commands and !help show you this list.')


client.run(token)
