import csv
from collections import OrderedDict
from operator import itemgetter

import discord
from discord.utils import find

def memSearch(text):
    # method for finding a user based on username and, possibly, discriminator (#1234), if no mention is provided
    term = (text.content.split(" ", 1)[1]).lower()
    semiMatch = looseMatch = None
    for member in text.guild.members:
        if term == str(member).lower():
            return member
        if term == member.name.lower():
            if not "#" in term:
                return member
            semiMatch = member
        if not semiMatch and term in member.name.lower():
            looseMatch = member
    return semiMatch if semiMatch else looseMatch

def writeMoney(member, amount, writing, adding):
    if "," in member.name:
        return -1, "For the sake of safety, Beardless Bot gambling is not usable by Discord users with a comma in their username. Please remove the comma from your username, " + member.mention + "."
    else:
        with open("resources/money.csv") as csvfile:
            for row in csv.reader(csvfile, delimiter = ","):
                if str(member.id) == row[0]: # found member
                    if isinstance(amount, str): # for people betting all
                        amount = int(row[1]) * (-1 if amount == "-all" else 1)
                    if row[1] != str(int(row[1]) + amount if adding else amount) and writing:
                        if int(row[1]) + amount < 0: # don't have enough to bet that much
                            return -2, None
                        newBank = amount if not adding else (int(row[1]) + amount)
                        newLine = ",".join((row[0], str(newBank), str(member)))
                        with open("resources/money.csv", "r") as oldMoney:
                            oldMoney = ''.join([i for i in oldMoney]).replace(",".join(row), newLine)
                            with open("resources/money.csv", "w") as money:
                                money.writelines(oldMoney)
                        return 1, newBank
                    return 0, int(row[1]) # no change in balance
            with open('resources/money.csv', 'a') as money:
                money.write("\r\n" + str(member.id) + ",300," + str(member))
                return 2, None

def register(text):
    result, bonus = writeMoney(text.author, 300, False, False)
    report = "Successfully registered. You now have 300 BeardlessBucks, " + text.author.mention + "."
    if result == 0:
        report = "You are already in the system! Hooray! You have " + str(bonus) + " BeardlessBucks, " + text.author.mention + "."
    elif result == -1:
        report = bonus
    return discord.Embed(title = "BeardlessBucks Registration", description = report, color = 0xfff994)

def balance(text):
    if text.content.lower() in ("!balance", "!bal"):
            target = text.author
    else:
        target = text.mentions[0] if text.mentions else (text.author if not text.guild or not " " in text.content else memSearch(text))
        if not target:
            report = "Invalid user! Please @ a user when you do !balance (or enter their username), or do !balance without a target to see your own balance, " + text.author.mention + "."
    if target:
        result, bonus = writeMoney(target, 300, False, False)
        if result == 0:
            report = ("Your balance is " + str(bonus) + " BeardlessBucks, " + target.mention + ".") if target == text.author else (target.mention + "'s balance is " + str(bonus) + " BeardlessBucks.")
        elif result == 2:
            report = "Successfully registered. You now have 300 BeardlessBucks, " + text.author.mention + "."
        else:
            report = bonus if result == -1 else "Error!"
    return discord.Embed(title = "BeardlessBucks Balance", description = report, color = 0xfff994)

def reset(text):
    result, bonus = writeMoney(text.author, 200, True, False)
    report = "You have been reset to 200 BeardlessBucks, " + text.author.mention + "."
    if result == -1:
        report = bonus
    if report == 2:
        report = "Successfully registered. You have 300 BeardlessBucks, " + text.author.mention + "."
    return discord.Embed(title = "BeardlessBucks Reset", description = report, color = 0xfff994)

def leaderboard():
    diction = {}
    emb = discord.Embed(title = "BeardlessBucks Leaderboard", description = "", color = 0xfff994)
    with open('resources/money.csv') as csvfile:
        for row in csv.reader(csvfile, delimiter = ','):
            if int(row[1]): # Don't bother displaying info for people with 0 BeardlessBucks
                diction[(row[2])[:-5]] = int(row[1])
    sortedDict = OrderedDict(sorted(diction.items(), key = itemgetter(1))) # Sort by value for each key in diction, which is BeardlessBucks balance
    for i in range(min(len(sortedDict), 10)):
        tup = sortedDict.popitem()
        emb.add_field(name = (str(i + 1) + ". " + tup[0]), value = str(tup[1]))
    return emb