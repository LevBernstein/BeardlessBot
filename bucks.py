# Beardless Bot methods that modify resources/money.csv

import csv
from collections import OrderedDict
from operator import itemgetter
from random import choice, randint
from typing import Dict, List, Optional, Tuple, Union

import nextcord

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


class BlackjackGame:
	"""
	Blackjack game instance. New instance created for each game.
	Instances are server-agnostic; only one game allowed per player
	across all servers.

	Attributes:
		cardVals (tuple): Blackjack values for each card
		user (nextcord.User or Member): The user who is playing this game
		bet (int): The number of BeardlessBucks the user is betting
		cards (list): The list of cards the user has been dealt
		dealerUp (int): The card the dealer is showing face-up
		dealerSum (int): The running count of the dealer's cards
		message (str): The report to be sent in the Discord channel

	Methods:
		perfect():
			Checks if the user has reached a Blackjack
		startingHand(debugBlackjack=False, debugDoubleAces=False):
			Deals the user a starting hand of 2 cards
		deal(debug=False):
			Deals the user a card
		checkBust():
			Checks if the user has gone over 21
		stay():
			Determines the game result after ending the game
		cardName(card):
			Gives the human-friendly name of a given card
	"""

	cardVals = (2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11)

	def __init__(
		self,
		user: Union[nextcord.User, nextcord.Member],
		bet: int,
		debug: bool = False
	) -> None:
		"""
		Creates a new BlackjackGame instance. In order to simulate the dealer
		standing on a soft 17, the dealer's sum will be incremented by a random card
		value until reaching 17.

		Args:
			user (nextcord.User or Member): The user who is playing this game
			bet (int): The number of BeardlessBucks the user is betting
			debug (bool): Whether to fix the game for testing
				(default is False)
		"""
		self.user = user
		self.bet = bet
		self.cards = []
		self.dealerUp = randint(2, 11)
		self.dealerSum = self.dealerUp
		while self.dealerSum < 17:
			self.dealerSum += randint(1, 10)
		self.message = self.startingHand(debug)

	def perfect(self) -> bool:
		"""Checks if the user has reached a Blackjack."""
		return sum(self.cards) == 21

	def startingHand(
		self, debugBlackjack: bool = False, debugDoubleAces: bool = False
	) -> str:
		"""
		Deals the user a starting hand of 2 cards.

		Args:
			debugBlackjack (bool): Used to test hitting 21
				(default is False)
			debugDoubleAces(bool): Used to test dealing two Aces
				(default is False)

		Returns:
			str: the message to show the user
		"""
		self.cards.append(choice(BlackjackGame.cardVals))
		self.cards.append(choice(BlackjackGame.cardVals))
		message = (
			f"Your starting hand consists of {BlackjackGame.cardName(self.cards[0])}"
			f" and {BlackjackGame.cardName(self.cards[1])}."
			f" Your total is {sum(self.cards)}. "
		)
		if self.perfect() or debugBlackjack:
			message += f"You hit 21! You win, {self.user.mention}!"
		else:
			message += (
				f"The dealer is showing {self.dealerUp},"
				" with one card face down. "
			)
			if self.checkBust() or debugDoubleAces:
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

	def deal(self, debug: bool = False) -> str:
		"""
		Deals the user a single card.

		Args:
			debug (bool): Used to test hitting 21
				(default is False)

		Returns:
			str: the message to show the user
		"""
		dealt = choice(BlackjackGame.cardVals)
		self.cards.append(dealt)
		self.message = (
			f"You were dealt {BlackjackGame.cardName(dealt)},"
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
		elif self.perfect() or debug:
			self.message += f" You hit 21! You win, {self.user.mention}!"
		else:
			self.message += (
				" Type !hit to deal another card to yourself, or !stay"
				f" to stop at your current total, {self.user.mention}."
			)
		return self.message

	def checkBust(self) -> bool:
		"""Checks if a user has gone over 21. Returns bool."""
		if sum(self.cards) > 21:
			self.bet *= -1
			return True
		return False

	def stay(self) -> int:
		"""Ends the game. Returns int: 1 if user's bal changed, else 0."""
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
		"""Returns the human-friendly name of a card based on int value."""
		if card == 10:
			return "a " + choice(("10", "Jack", "Queen", "King"))
		if card == 11:
			return "an Ace"
		if card == 8:
			return "an 8"
		return "a " + str(card)


def writeMoney(
	member: Union[nextcord.User, nextcord.Member],
	amount: Union[str, int],
	writing: bool,
	adding: bool
) -> Tuple[int, Optional[Union[str, int]]]:
	"""
	Helper method for checking or modifying a user's BeardlessBucks balance.

	Args:
		member (nextcord.User or Member): The target user
		amount (str or int): The amount to change member's balance by
		writing (bool): Whether to modify member's balance
		adding (bool): Whether to add to or overwrite member's balance

	Returns:
		int: the status of calling the method:
			-1 means member's username contains a comma;
			-2 means member doesn't have enough to bet that much;
			0 means member's balance has not been changed;
			1 means it has;
			2 means this call has just registered them.
		str: an additional report, if necessary.
	"""
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
						# Don't have enough to bet that much:
						return -2, None
					newLine = ",".join((row[0], newBank, str(member)))
					result = 1
				else:
					# No change in balance. Rewrites lines anyway, to
					# update stringified version of member
					newLine = ",".join((row[0], row[1], str(member)))
					newBank = int(row[1])
					result = 0
				with open("resources/money.csv", "r") as oldMoney:
					newMoney = (
						"".join([i for i in oldMoney])
						.replace(",".join(row), newLine)
					)
				with open("resources/money.csv", "w") as money:
					money.writelines(newMoney)
				return result, newBank

	with open("resources/money.csv", "a") as money:
		money.write(f"\r\n{member.id},300,{member}")
	return (
		2,
		(
			"Successfully registered. You have 300"
			f" BeardlessBucks, {member.mention}."
		)
	)


def register(target: Union[nextcord.User, nextcord.Member]) -> nextcord.Embed:
	"""
	Register a new user for BeardlessBucks.

	Args:
		target (nextcord.User or Member): The user to register

	Returns:
		nextcord.Embed: the report of the target's registration.
	"""
	result, bonus = writeMoney(target, 300, False, False)
	if result in (-1, 2):
		report = bonus
	else:
		report = (
			"You are already in the system! Hooray! You"
			f" have {bonus} BeardlessBucks, {target.mention}."
		)
	return bbEmbed("BeardlessBucks Registration", report)


def balance(
	target: Union[nextcord.User, nextcord.Member, str],
	msg: nextcord.Message
) -> nextcord.Embed:
	"""
	Checks a user's BeardlessBucks balance.

	Args:
		target (nextcord.User or Member): The user whose balance is to be checked
		msg (nextcord.Message): The message sent that called this command

	Returns:
		nextcord.Embed: the report of the target's balance.
	"""
	report = (
		"Invalid user! Please @ a user when you do !balance"
		" (or enter their username), or do !balance without a"
		f" target to see your own balance, {msg.author.mention}."
	)
	if not isinstance(target, nextcord.User):
		target = memSearch(msg, target)
	if target:
		result, bonus = writeMoney(target, 300, False, False)
		if result == 0:
			report = f"{target.mention}'s balance is {bonus} BeardlessBucks."
		else:
			report = bonus if result in (-1, 2) else "Error!"
	return bbEmbed("BeardlessBucks Balance", report)


def reset(target: Union[nextcord.User, nextcord.Member]) -> nextcord.Embed:
	"""
	Resets a user's Beardless balance to 200.

	Args:
		target (nextcord.User or Member): The user to reset

	Returns:
		nextcord.Embed: the report of the target's balance reset.
	"""
	result, bonus = writeMoney(target, 200, True, False)
	if result in (-1, 2):
		report = bonus
	else:
		report = (
			"You have been reset to 200"
			f" BeardlessBucks, {target.mention}."
		)
	return bbEmbed("BeardlessBucks Reset", report)


def leaderboard(
	target: Union[nextcord.User, nextcord.Member, str] = None,
	msg: nextcord.Message = None
) -> nextcord.Embed:
	"""
	Finds the top min(len(money.csv), 10) users
	by balance in money.csv.
	Runtime = |money.csv| + runtime of sorted(money.csv) + 10
	= O(n) + O(nlogn) + 10 = O(nlogn).

	Args:
		target (nextcord.User or Member): The user calling leaderboard()
			(default is None)

	Returns:
		nextcord.Embed: a summary of the richest users by balance.
			If target is somewhere on the leaderboard, also
			reports target's position and balance.
	"""
	lbDict: Dict[str, int] = {}
	emb = bbEmbed("BeardlessBucks Leaderboard")
	if target and msg and not isinstance(target, nextcord.User):
		target = memSearch(msg, target)
	if target:
		writeMoney(target, 300, False, False)
	with open("resources/money.csv") as csvfile:
		for row in csv.reader(csvfile, delimiter=","):
			lbDict[row[2]] = int(row[1])
	# Sort by value for each key in lbDict, which is BeardlessBucks balance
	sortedDict = OrderedDict(sorted(lbDict.items(), key=itemgetter(1)))
	if target:
		users = list(sortedDict.keys())
		try:
			pos = len(users) - users.index(str(target))
			targetBal = sortedDict[str(target)]
		except ValueError:
			pos = None
	for i in range(min(len(sortedDict), 10)):
		head, body = sortedDict.popitem()
		lastEntry = (i != min(len(sortedDict), 10) - 1)
		emb.add_field(
			name=f"{i + 1}. {head[:-5]}", value=body, inline=lastEntry
		)
	if target and pos:
		emb.add_field(name=f"{target.name}'s position:", value=pos)
		emb.add_field(name=f"{target.name}'s balance:", value=targetBal)
	return emb


def flip(
	author: Union[nextcord.User, nextcord.Member],
	bet: str,
	debug: bool = False
) -> str:
	"""
	Gambles a certain number of BeardlessBucks on a coin toss.

	Args:
		author (nextcord.User or Member): The user who is gambling
		bet (str): The amount author is wagering
		debug (bool): Whether to fix the outcome of the flip.
			Only used for testing in bb_test.py.
			(default is False)

	Returns:
		str: A report of the outcome and how author's balance changed.
	"""
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
	if (isinstance(bet, str) and "all" in bet) or bet >= 0:
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
			if isinstance(bet, int) and (debug or not heads):
				bet *= -1
			result, bonus = writeMoney(author, bet, True, True)
			if result == 2:
				report = newUserMsg
			elif heads or debug:
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


def blackjack(
	author: Union[nextcord.User, nextcord.Member], bet: str
) -> Tuple[str, Union[BlackjackGame, None]]:
	"""
	Gambles a certain number of BeardlessBucks on blackjack.

	Args:
		author (nextcord.User or Member): The user who is gambling
		bet (str): The amount author is wagering

	Returns:
		str: A report of the outcome and how author's balance changed.
		bucks.Instance: If there is still a game to play, returns
			the object representing the game of blackjack
			author is playing.
	"""
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
	if (isinstance(bet, str) and bet == "all") or (bet >= 0):
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
			if bet == "all":
				bet = bank
			game = BlackjackGame(author, bet)
			report = game.message
			if game.perfect():
				writeMoney(author, bet, True, True)
				game = None
	return report.format(author.mention), game


def activeGame(games: List[BlackjackGame], author: nextcord.User) -> bool:
	"""Checks if a user has an active game of Blackjack."""
	return any(author == game.user for game in games)
