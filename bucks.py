# Beardless Bot methods that modify resources/money.csv

import csv
from collections import OrderedDict
from operator import itemgetter
from random import choice, randint

import discord

from misc import bbEmbed, memSearch


commaWarn = (
	"Beardless Bot gambling is available to Discord"
	" users with a comma in their username. Please"
	" remove the comma from your username, {}."
)

buckMsg = (
	"BeardlessBucks are this bot's special currency."
	" You can earn them by playing games. First, do"
	" !register to get yourself started with a balance."
)

newUserMsg = (
	"You were not registered for BeardlessBucks gambling, so I have"
	" automatically registered you. You now have 300 BeardlessBucks, {}."
)

finMsg = "Please finish your game of blackjack first, {}."

noGameMsg = (
	"You do not currently have a game of blackjack"
	" going, {}. Type !blackjack to start one."
)

# Blackjack class. New Instance is made for each game of Blackjack
# and is kept around until the player finishes the game.
# An active Instance for a given user prevents the creation of a new
# Instance. Instances are server-agnostic.


class Instance:

	cardVals = (2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11)

	def __init__(self, user: discord.User, bet: int, fix: bool = False):
		self.user = user
		self.bet = bet
		self.cards = []
		self.dealerUp = randint(2, 11)
		self.dealerSum = self.dealerUp
		while self.dealerSum < 17:
			self.dealerSum += randint(1, 10)
		self.message = self.startingHand(fix)

	def perfect(self) -> bool:
		return sum(self.cards) == 21

	def startingHand(
		self, fixBlackjack: bool = False, fixDoubleAces: bool = False
	) -> str:
		self.cards.append(choice(Instance.cardVals))
		self.cards.append(choice(Instance.cardVals))
		message = (
			"Your starting hand consists of {} and {}. Your total is {}. "
		).format(
			self.cardName(self.cards[0]),
			self.cardName(self.cards[1]),
			sum(self.cards)
		)
		if self.perfect() or fixBlackjack:
			# "fixBlackjack" used to test being dealt a blackjack
			message += f"You hit 21! You win, {self.user.mention}!"
		else:
			message += (
				f"The dealer is showing {self.dealerUp},"
				" with one card face down. "
			)
			if self.checkBust() or fixDoubleAces:
				# Case only fires if you're dealt two aces or testing this
				self.cards[1] = 1
				self.bet *= -1
				message = (
					"Your starting hand consists of two Aces."
					" One of them will act as a 1. Your total is 12. "
				)
			message += (
				"Type !hit to deal another card to yourself, or !stay"
				f" to stop at your current total, {self.user.mention}."
			)
		return message

	def deal(self, fix: bool = False) -> str:
		dealt = choice(Instance.cardVals)
		self.cards.append(dealt)
		self.message = (
			f"You were dealt {self.cardName(dealt)},"
			f" bringing your total to {sum(self.cards)}. "
		)
		if 11 in self.cards and self.checkBust():
			for i in range(len(self.cards)):
				if self.cards[i] == 11:
					self.cards[i] = 1
					self.bet *= -1
					break
			self.message += (
				"To avoid busting, your Ace will be treated as a 1."
				f" Your new total is {sum(self.cards)}. "
			)
		self.message += (
			"Your card values are {}. The dealer is"
			" showing {}, with one card face down."
		).format(", ".join(str(card) for card in self.cards), self.dealerUp)
		if self.checkBust():
			self.message += f" You busted. Game over, {self.user.mention}."
		elif self.perfect() or fix:  # "fix" used to test this line
			self.message += f" You hit 21! You win, {self.user.mention}!"
		else:
			self.message += (
				" Type !hit to deal another card to yourself, or !stay"
				f" to stop at your current total, {self.user.mention}."
			)
		return self.message

	def checkBust(self) -> bool:
		if sum(self.cards) > 21:
			self.bet *= -1
			return True
		return False

	def stay(self) -> int:
		change = 1
		self.message = "The dealer has a total of {}."
		if sum(self.cards) > self.dealerSum and not self.checkBust():
			self.message += (
				" You're closer to 21 with a sum of {}. You win!"
				" Your winnings have been added to your balance, {}."
			)
		elif sum(self.cards) == self.dealerSum:
			change = 0
			self.message += (
				" That ties your sum of {}. Your bet has been returned, {}."
			)
		elif self.dealerSum > 21:
			self.message += (
				" You have a sum of {}. The dealer busts. You win!"
				" Your winnings have been added to your balance, {}."
			)
		else:
			self.message += (
				" That's closer to 21 than your sum of {}. You lose."
				" Your loss has been deducted from your balance, {}."
			)
			self.bet *= -1
		self.message = self.message.format(
			self.dealerSum, sum(self.cards), self.user.mention
		)
		if not self.bet:
			self.message += (
				" Unfortunately, you bet nothing, so this was all pointless."
			)
		return change

	@staticmethod
	def cardName(card: int) -> str:
		if card == 10:
			return "a " + choice(("10", "Jack", "Queen", "King"))
		if card == 11:
			return "an Ace"
		if card == 8:
			return "an 8"
		return "a " + str(card)


# BeardlessBucks modifying/referencing methods:
# writeMoney() is the helper method for checking or
# modifying a given user's balance.
# register() is used for signing up a new user
# to the BeardlessBucks system.
# balance() is essentially a more user-friendly wrapper for
# writeMoney's balance lookup
# reset() is used for resetting a given user to 200 BeardlessBucks.
# leaderboard() finds the top min(len(money.csv), 10)
# users by balance in O(nlogn) time.
# flip() gambles a certain number of BeardlessBucks
# on a coin toss (randint(0,1)).


def writeMoney(
	member: discord.User, amount, writing: bool, adding: bool
) -> tuple:
	# "writing" is True if you want to modify money.csv;
	# "adding" is True if you want to add an amount to a member's balance
	if "," in member.name:
		return -1, commaWarn.format(member.mention)
	with open("resources/money.csv") as csvfile:
		for row in csv.reader(csvfile, delimiter=","):
			if str(member.id) == row[0]:  # found member
				if isinstance(amount, str):  # for people betting all
					amount = -int(row[1]) if amount == "-all" else int(row[1])
				newBank = str(int(row[1]) + amount if adding else amount)
				if writing and row[1] != newBank:
					if int(row[1]) + amount < 0:
						# Don't have enough to bet that much
						return -2, None
					newLine = ",".join((row[0], newBank, str(member)))
					with open("resources/money.csv", "r") as oldMoney:
						oldMoney = (
							"".join([i for i in oldMoney])
							.replace(",".join(row), newLine)
						)
						with open("resources/money.csv", "w") as money:
							money.writelines(oldMoney)
					return 1, newBank
				return 0, int(row[1])  # no change in balance
		with open("resources/money.csv", "a") as money:
			money.write(f"\r\n{member.id},300,{member}")
		return (
			2,
			(
				"Successfully registered. You have 300"
				f" BeardlessBucks, {member.mention}."
			)
		)


def register(target: discord.User) -> discord.Embed:
	result, bonus = writeMoney(target, 300, False, False)
	report = (
		"You are already in the system! Hooray! You"
		f" have {bonus} BeardlessBucks, {target.mention}."
	)
	if result in (-1, 2):
		report = bonus
	return bbEmbed("BeardlessBucks Registration", report)


def balance(target: discord.Member, msg: discord.Message) -> discord.Embed:
	report = (
		"Invalid user! Please @ a user when you do !balance "
		"(or enter their username), or do !balance without a target"
		f" to see your own balance, {msg.author.mention}."
	)
	if not isinstance(target, discord.User):
		target = memSearch(msg, target)
	if target:
		result, bonus = writeMoney(target, 300, False, False)
		if result == 0:
			report = f"{target.mention}'s balance is {bonus} BeardlessBucks."
		else:
			report = bonus if result in (-1, 2) else "Error!"
	return bbEmbed("BeardlessBucks Balance", report)


def reset(target: discord.User) -> discord.Embed:
	result, bonus = writeMoney(target, 200, True, False)
	report = f"You have been reset to 200 BeardlessBucks, {target.mention}."
	if result in (-1, 2):
		report = bonus
	return bbEmbed("BeardlessBucks Reset", report)


def leaderboard(target: discord.User = None) -> discord.Embed:
	# Runtime = 2 * |money.csv| + runtime of sorted(money.csv) + 10
	# = 2 * O(n) + O(nlogn) + 10 = O(nlogn)
	diction = {}
	emb = bbEmbed("BeardlessBucks Leaderboard")
	with open("resources/money.csv") as csvfile:
		for row in csv.reader(csvfile, delimiter=","):
			if int(row[1]):
				# Don't display info for people with 0 BeardlessBucks
				diction[(row[2])[:-5]] = int(row[1])
	# Sort by value for each key in diction, which is BeardlessBucks balance
	sortedDict = OrderedDict(sorted(diction.items(), key=itemgetter(1)))
	if target:
		try:
			users = list(sortedDict.keys())
			pos = len(users) - users.index(target.name)
		except ValueError:
			pos = None
	for i in range(min(len(sortedDict), 10)):
		head, body = sortedDict.popitem()
		emb.add_field(
			name=(str(i + 1) + ". " + head),
			value=str(body),
			inline=(i != min(len(sortedDict), 10) - 1)
		)
	if target and pos:
		emb.add_field(name=f"{target.name}'s position:", value=str(pos))
		emb.add_field(
			name=f"{target.name}'s balance:",
			value=str(sortedDict[target.name])
		)
	return emb


def flip(author: discord.user, bet: str, fix: bool = False) -> str:
	heads = randint(0, 1)
	report = (
		"Invalid bet. Please choose a number greater than or equal"
		" to 0, or enter \"all\" to bet your whole balance, {}."
	)
	if bet == "all":
		if not heads:
			bet = "-all"
	else:
		try:
			bet = int(bet)
		except ValueError:
			bet = -1
	if (isinstance(bet, str) and "all" in bet) or (
		isinstance(bet, int) and bet >= 0
	):
		result, bank = writeMoney(author, 300, False, False)
		if result == 2:
			report = (
				"You were not registered for BeardlessBucks gambling, so"
				" I registered you. You now have 300 BeardlessBucks, {}."
			)
		elif result == -1:
			report = bank
		elif isinstance(bet, int) and bet > bank:
			report = (
				"You do not have enough BeardlessBucks to bet that much, {}!"
			)
		else:
			if isinstance(bet, int) and (fix or not heads):
				# Fix just used to help test
				bet *= -1
			result, bonus = writeMoney(author, bet, True, True)
			if result == 2:
				report = newUserMsg
			elif heads or fix:
				report = (
					"Heads! You win! Your winnings have"
					" been added to your balance, {}."
				)
			else:
				report = (
					"Tails! You lose! Your losses have been"
					" deducted from your balance, {}."
				)
			if result == 0:
				report += (
					" Or, they would have been, if"
					" you had actually bet anything."
				)
	return report.format(author.mention)


def blackjack(author: discord.User, bet: str) -> str:
	game = None
	report = (
		"Invalid bet. Please choose a number greater than or equal"
		" to 0, or enter \"all\" to bet your whole balance, {}."
	)
	if bet != "all":
		try:
			bet = int(bet)
		except ValueError:
			bet = -1
	if (isinstance(bet, str) and bet == "all") or (
		isinstance(bet, int) and bet >= 0
	):
		result, bank = writeMoney(author, 300, False, False)
		if result == 2:
			report = (
				"You were not registered for BeardlessBucks gambling, so"
				" I registered you. You now have 300 BeardlessBucks, {}."
			)
		elif result == -1:
			report = bank
		elif not (
			isinstance(bet, str)
			or (isinstance(bet, int) and result == 0 and bet <= bank)
		):
			report = (
				"You do not have enough BeardlessBucks to bet that much, {}!"
			)
		else:
			if bet == "all":
				bet = bank
			game = Instance(author, bet)
			report = game.message
			if game.perfect():
				writeMoney(author, bet, True, True)
				game = None
	return report.format(author.mention), game
