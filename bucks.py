import csv
from collections import OrderedDict
from operator import itemgetter

import discord
from discord.utils import find

commaWarn = "Beardless Bot gambling is available to Discord users with a comma in their username. Please remove the comma from your username, {}."

def memSearch(text):
	# method for finding a user based on username and, possibly, discriminator (#1234)
	term = text.content.split(" ", 1)[1].lower()
	semiMatch = looseMatch = None
	for member in text.guild.members:
		if term == str(member).lower():
			return member
		if term == member.name.lower():
			if not "#" in term:
				return member
			semiMatch = member
		if member.nick and term == member.nick.lower() and not semiMatch:
			looseMatch = member
		if not (semiMatch or looseMatch) and term in member.name.lower():
			looseMatch = member
	return semiMatch if semiMatch else looseMatch

def writeMoney(member, amount, writing, adding):
	# "writing" is True if you want to modify money.csv; "adding" is True if you want to add an amount to a member's balance
	if "," in member.name:
		return -1, commaWarn.format(member.mention)
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
			money.write("\r\n{},300,{}".format(member.id, member))
			return 2, None

def register(text):
	result, bonus = writeMoney(text.author, 300, False, False)
	report = "Successfully registered. You now have 300 BeardlessBucks, {}.".format(text.author.mention)
	if result == 0:
		report = "You are already in the system! Hooray! You have {} BeardlessBucks, {}.".format(bonus, text.author.mention)
	elif result == -1:
		report = bonus
	return discord.Embed(title = "BeardlessBucks Registration", description = report, color = 0xfff994)

def balance(text):
	report = ("Invalid user! Please @ a user when you do !balance (or enter their username)," +
	" or do !balance without a target to see your own balance, " + text.author.mention + ".")
	if text.mentions:
		target = text.mentions[0]
	else:
		target = text.author if not text.guild or not " " in text.content else memSearch(text)
	if target:
		result, bonus = writeMoney(target, 300, False, False)
		if result == 0:
			report = "{}'s balance is {} BeardlessBucks.".format(target.mention, bonus)
		elif result == 2:
			report = "Successfully registered. You now have 300 BeardlessBucks, " + target.mention + "."
		else:
			report = bonus if result == -1 else "Error!"
	return discord.Embed(title = "BeardlessBucks Balance", description = report, color = 0xfff994)

def reset(text):
	result, bonus = writeMoney(text.author, 200, True, False)
	report = "You have been reset to 200 BeardlessBucks, " + text.author.mention + "."
	if result == 2:
		report = "Successfully registered. You have 300 BeardlessBucks, " + text.author.mention + "."
	if result == -1:
		report = bonus
	return discord.Embed(title = "BeardlessBucks Reset", description = report, color = 0xfff994)

def leaderboard():
	diction = {}
	emb = discord.Embed(title = "BeardlessBucks Leaderboard", description = "", color = 0xfff994)
	with open('resources/money.csv') as csvfile:
		for row in csv.reader(csvfile, delimiter = ','):
			if int(row[1]): # Don't bother displaying info for people with 0 BeardlessBucks
				diction[(row[2])[:-5]] = int(row[1])
	# Sort by value for each key in diction, which is BeardlessBucks balance
	sortedDict = OrderedDict(sorted(diction.items(), key = itemgetter(1)))
	for i in range(min(len(sortedDict), 10)):
		head, body = sortedDict.popitem()
		emb.add_field(name = (str(i + 1) + ". " + head), value = str(body))
	return emb