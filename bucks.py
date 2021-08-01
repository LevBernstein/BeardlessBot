import csv
from random import choice, randint
from collections import OrderedDict
from operator import itemgetter

import discord

def register(text):
    if ',' in text.author.name:
        report = "For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + "."
    else:
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
                    money.write("\r\n" + str(text.author.id) + ",300," + str(text.author))
    return discord.Embed(title = "Beardless Bucks Registration", description = report, color = 0xfff994)

def balance(text):
    report = ""
    if text.content.lower() == ("!balance") or text.content.lower() == ("!bal"):
        if ',' in text.author.name:
            report = "For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + "."
        target = text.author
    else:
        target = text.mentions[0] if text.mentions else (text.author if not " " in text.content else memSearch(text))
        if not target:
            report = "Invalid user! Please @ a user when you do !balance (or enter their username), or do !balance without a target to see your own balance, " + text.author.mention + "."
    if not report:
        report = "Oops! You aren't in the system! Type \"!register\" to get a starting balance, " + text.author.mention + "." if target == text.author else "Oops! That user isn't in the system! They can type \"!register\" to get a starting balance."
        with open('resources/money.csv') as csvfile:
            reader = csv.reader(csvfile, delimiter = ',')
            for row in reader:
                if str(target.id) == row[0]:
                    report = ("Your balance is " + row[1] + " BeardlessBucks, " + text.author.mention + ".") if target == text.author else (target.mention + "'s balance is " + row[1] + " BeardlessBucks.")
                    break
    return discord.Embed(title = "Beardless Bucks Balance", description = report, color = 0xfff994)

def reset(text):
    report = 'You have been reset to 200 BeardlessBucks, ' + text.author.mention + "."
    if ',' in text.author.name:
        report = "For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + text.author.mention + "."
    else:
        with open('resources/money.csv') as csvfile:
            reader = csv.reader(csvfile, delimiter = ',')
            exist = False
            for row in reader:
                if str(text.author.id) == row[0]:
                    exist = True
                    if row[1] != str(200):
                        oldLine = row[0] + "," + row[1] + "," + row[2]
                        newLine = row[0] + ",200," + str(text.author)
                        with open("resources/money.csv", "r") as oldMoney:
                            oldMoney = ''.join([i for i in oldMoney]).replace(oldLine, newLine)
                            with open("resources/money.csv", "w") as money:
                                money.writelines(oldMoney)
            if not exist:
                report ="Successfully registered. You have 300 BeardlessBucks, " + text.author.mention + "."
                with open('resources/money.csv', 'a') as money:
                    writer = csv.writer(csvfile)
                    money.write("\r\n" + str(text.author.id) + ",300," + str(text.author))
    return discord.Embed(title = "Beardless Bucks Reset", description = report, color = 0xfff994)

def leaderboard():
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
    return emb