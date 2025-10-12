"""Beardless Bot methods that modify resources/money.csv."""

import csv
import random
from collections import OrderedDict
from enum import Enum
from operator import itemgetter
from pathlib import Path

import nextcord

from misc import bb_embed, member_search

CommaWarn = (
	"Beardless Bot gambling is available to Discord"
	" users with a comma in their username. Please"
	" remove the comma from your username, {}."
)

NewUserMsg = (
	"You were not registered for BeardlessBucks gambling, so I have"
	" automatically registered you. You now have 300 BeardlessBucks, {}."
)

FinMsg = "Please finish your game of blackjack first, {}."

NoGameMsg = (
	"You do not currently have a game of blackjack"
	" going, {}. Type !blackjack to start one."
)


class BlackjackGame:
	"""
	Blackjack game instance.

	New instance created for each game. Instances are server-agnostic; only
	one game allowed per player across all servers.

	Attributes:
		AceVal (int): The high value of an Ace
		DealerSoftGoal (int): The soft sum up to which the dealer will hit
		FaceVal (int): The value of a face card (J Q K)
		Goal (int): The desired score
		CardVals (tuple[int, ...]): Blackjack values for each card
		user (nextcord.User or Member): The user who is playing this game
		bet (int): The number of BeardlessBucks the user is betting
		cards (list): The list of cards the user has been dealt
		dealerUp (int): The card the dealer is showing face-up
		dealerSum (int): The running count of the dealer's cards
		message (str): The report to be sent in the Discord channel

	Methods:
		perfect():
			Checks if the user has reached a Blackjack
		startingHand(debug_blackjack=False, debug_double_aces=False):
			Deals the user a starting hand of 2 cards
		deal():
			Deals the user a card
		checkBust():
			Checks if the user has gone over Goal
		stay():
			Determines the game result after ending the game
		cardName(card):
			Gives the human-friendly name of a given card

	"""

	# TODO: Make the deck consist of 52 cards, with dealing a card popping it

	AceVal = 11
	DealerSoftGoal = 17
	FaceVal = 10
	Goal = 21
	CardVals = (2, 3, 4, 5, 6, 7, 8, 9, 10, FaceVal, FaceVal, FaceVal, AceVal)

	def __init__(
		self,
		user: nextcord.User | nextcord.Member,
		bet: int,
	) -> None:
		"""
		Create a new BlackjackGame instance.

		In order to simulate the dealer standing on DealerSoftGoal, the
		dealer's sum will be incremented by a random card value until
		reaching DealerSoftGoal.

		Args:
			user (nextcord.User or Member): The user who is playing this game
			bet (int): The number of BeardlessBucks the user is betting

		"""
		self.user = user
		self.bet = bet
		self.hand: list[int] = []
		self.dealerUp = random.randint(2, BlackjackGame.AceVal)
		self.dealerSum = self.dealerUp
		while self.dealerSum < BlackjackGame.DealerSoftGoal:
			self.dealerSum += random.randint(1, BlackjackGame.FaceVal)
		self.message = self.starting_hand()

	@staticmethod
	def card_name(card: int) -> str:
		"""
		Return the human-friendly name of a card based on int value.

		Args:
			card (int): The card whose name should be rendered

		Returns:
			str: A human-friendly card name.

		"""
		if card == BlackjackGame.FaceVal:
			return "a " + random.choice(
				(str(BlackjackGame.FaceVal), "Jack", "Queen", "King"),
			)
		if card == BlackjackGame.AceVal:
			return "an Ace"
		return "an 8" if card == 8 else ("a " + str(card))  # noqa: PLR2004

	def perfect(self) -> bool:
		"""
		Check if the user has reached Goal, and therefore gotten Blackjack.

		In the actual game of Blackjack, getting Blackjack requires hitting
		21 with just your first two cards; for the sake of simplicity, use
		this method for checking if the user has reached Goal at all.

		Returns:
			bool: Whether the user has gotten Blackjack.

		"""
		return sum(self.hand) == BlackjackGame.Goal

	def starting_hand(
		self,
		*,
		debug_blackjack: bool = False,
		debug_double_aces: bool = False,
	) -> str:
		"""
		Deal the user a starting hand of 2 cards.

		Args:
			debug_blackjack (bool): Used to test hitting Goal
				(default is False)
			debug_double_aces (bool): Used to test dealing two Aces
				(default is False)

		Returns:
			str: The message to show the user.

		"""
		self.hand.append(random.choice(BlackjackGame.CardVals))
		self.hand.append(random.choice(BlackjackGame.CardVals))
		message = (
			"Your starting hand consists of"
			f" {BlackjackGame.card_name(self.hand[0])}"
			f" and {BlackjackGame.card_name(self.hand[1])}."
			f" Your total is {sum(self.hand)}. "
		)
		if (self.perfect() or debug_blackjack) and not debug_double_aces:
			message += (
				f"You hit {BlackjackGame.Goal}! You win, {self.user.mention}!"
			)
		else:
			message += (
				f"The dealer is showing {self.dealerUp},"
				" with one card face down. "
			)
			if self.check_bust() or debug_double_aces:
				self.hand[1] = 1
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

	def deal(self) -> str:
		"""
		Deal the user a single card.

		Returns:
			str: The message to show the user.

		"""
		dealt = random.choice(BlackjackGame.CardVals)
		self.hand.append(dealt)
		self.message = (
			f"You were dealt {BlackjackGame.card_name(dealt)},"
			f" bringing your total to {sum(self.hand)}. "
		)
		if BlackjackGame.AceVal in self.hand and self.check_bust():
			for i, card in enumerate(self.hand):
				if card == BlackjackGame.AceVal:
					self.hand[i] = 1
					self.bet *= -1
					break
			self.message += (
				"To avoid busting, your Ace will be treated as a 1."
				f" Your new total is {sum(self.hand)}. "
			)
		self.message += (
			"Your card values are {}. The dealer is"
			" showing {}, with one card face down."
		).format(", ".join(str(card) for card in self.hand), self.dealerUp)
		if self.check_bust():
			self.message += f" You busted. Game over, {self.user.mention}."
		elif self.perfect():
			self.message += (
				f" You hit {BlackjackGame.Goal}! You win, {self.user.mention}!"
			)
		else:
			self.message += (
				" Type !hit to deal another card to yourself, or !stay"
				f" to stop at your current total, {self.user.mention}."
			)
		return self.message

	def check_bust(self) -> bool:
		"""
		Check if a user has gone over Goal.

		If so, invert their bet to facilitate subtracting it from their total.

		Returns:
			bool: Whether the user has gone over Goal.

		"""
		if sum(self.hand) > BlackjackGame.Goal:
			self.bet *= -1
			return True
		return False

	def stay(self) -> int:
		"""
		End the game.

		Returns:
			int: 1 if user's balance changed; else, 0.

		"""
		change = 1
		self.message = "The dealer has a total of {}."
		if sum(self.hand) > self.dealerSum and not self.check_bust():
			self.message += f" You're closer to {BlackjackGame.Goal}"
			self.message += (
				" with a sum of {}. You win!  Your winnings"
				" have been added to your balance, {}."
			)
		elif sum(self.hand) == self.dealerSum:
			change = 0
			self.message += (
				" That ties your sum of {}. Your bet has been returned, {}."
			)
		elif self.dealerSum > BlackjackGame.Goal:
			self.message += (
				" You have a sum of {}. The dealer busts. You win!"
				" Your winnings have been added to your balance, {}."
			)
		else:
			self.message += f" That's closer to {BlackjackGame.Goal}"
			self.message += (
				" than your sum of {}. You lose. Your loss"
				" has been deducted from your balance, {}."
			)
			self.bet *= -1
		self.message = self.message.format(
			self.dealerSum, sum(self.hand), self.user.mention,
		)
		if not self.bet:
			self.message += (
				" Unfortunately, you bet nothing, so this was all pointless."
			)
		return change


class MoneyFlags(Enum):
	"""Enum for additional readability in the writeMoney method."""

	NotEnoughBucks = -2
	CommaInUsername = -1
	BalanceUnchanged = 0
	BalanceChanged = 1
	Registered = 2


def write_money(
	member: nextcord.User | nextcord.Member,
	amount: str | int,
	*,
	writing: bool,
	adding: bool,
) -> tuple[MoneyFlags, str | int | None]:
	"""
	Check or modify a user's BeardlessBucks balance.

	Args:
		member (nextcord.User or Member): The target user
		amount (str or int): The amount to change member's balance by
		writing (bool): Whether to modify member's balance
		adding (bool): Whether to add to or overwrite member's balance

	Returns:
		tuple[MoneyFlags, str | int | None]: A tuple containing:
			MoneyFlags: enum representing the result of calling the method
			str or int or None: an additional report, if necessary.

	"""
	if "," in member.name:
		return MoneyFlags.CommaInUsername, CommaWarn.format(member.mention)
	with Path("resources/money.csv").open("r", encoding="UTF-8") as csv_file:
		for row in csv.reader(csv_file, delimiter=","):
			if str(member.id) == row[0]:  # found member
				if isinstance(amount, str):  # for people betting all
					amount = -int(row[1]) if amount == "-all" else int(row[1])
				new_bank: str | int = str(
					int(row[1]) + amount if adding else amount,
				)
				if writing and row[1] != new_bank:
					if int(row[1]) + amount < 0:
						return MoneyFlags.NotEnoughBucks, None
					new_line = ",".join((row[0], str(new_bank), str(member)))
					result = MoneyFlags.BalanceChanged
				else:
					# No change in balance. Rewrites lines anyway, to
					# update stringified version of member
					new_line = ",".join((row[0], row[1], str(member)))
					new_bank = int(row[1])
					result = MoneyFlags.BalanceUnchanged
				with Path("resources/money.csv").open(
					"r", encoding="UTF-8",
				) as f:
					money = "".join(list(f)).replace(",".join(row), new_line)
				with Path("resources/money.csv").open(
					"w", encoding="UTF-8",
				) as f:
					f.writelines(money)
				return result, new_bank

	with Path("resources/money.csv").open("a", encoding="UTF-8") as f:
		f.write(f"\r\n{member.id},300,{member}")
	return (
		MoneyFlags.Registered,
		(
			"Successfully registered. You have 300"
			f" BeardlessBucks, {member.mention}."
		),
	)


def register(target: nextcord.User | nextcord.Member) -> nextcord.Embed:
	"""
	Register a new user for BeardlessBucks.

	Args:
		target (nextcord.User or Member): The user to register

	Returns:
		nextcord.Embed: the report of the target's registration.

	"""
	result, bonus = write_money(target, 300, writing=False, adding=False)
	report = bonus if result in {
		MoneyFlags.CommaInUsername, MoneyFlags.Registered,
	} else (
		"You are already in the system! Hooray! You"
		f" have {bonus} BeardlessBucks, {target.mention}."
	)
	assert isinstance(report, str)
	return bb_embed("BeardlessBucks Registration", report)


def balance(
	target: nextcord.User | nextcord.Member | str,
	msg: nextcord.Message,
) -> nextcord.Embed:
	"""
	Check a user's BeardlessBucks balance.

	Args:
		target (nextcord.User or Member or str): The user whose balance is
			to be checked
		msg (nextcord.Message): The message sent that called this command

	Returns:
		nextcord.Embed: the report of the target's balance.

	"""
	report = (
		"Invalid user! Please @ a user when you do !balance"
		" (or enter their username), or do !balance without a"
		f" target to see your own balance, {msg.author.mention}."
	)
	bal_target = (
		member_search(msg, target) if isinstance(target, str) else target
	)
	if bal_target and not isinstance(bal_target, str):
		result, bonus = write_money(
			bal_target, 300, writing=False, adding=False,
		)
		if result == MoneyFlags.BalanceUnchanged:
			report = (
				f"{bal_target.mention}'s balance is {bonus} BeardlessBucks."
			)
		else:
			report = str(bonus) if result in {
				MoneyFlags.CommaInUsername, MoneyFlags.Registered,
			} else "Error!"
	return bb_embed("BeardlessBucks Balance", report)


def reset(target: nextcord.User | nextcord.Member) -> nextcord.Embed:
	"""
	Reset a user's Beardless balance to 200.

	Args:
		target (nextcord.User or Member): The user to reset

	Returns:
		nextcord.Embed: the report of the target's balance reset.

	"""
	result, bonus = write_money(target, 200, writing=True, adding=False)
	report = bonus if result in {
		MoneyFlags.CommaInUsername, MoneyFlags.Registered,
	} else f"You have been reset to 200 BeardlessBucks, {target.mention}."
	assert isinstance(report, str)
	return bb_embed("BeardlessBucks Reset", report)


def leaderboard(
	target: nextcord.User | nextcord.Member | str | None = None,
	msg: nextcord.Message | None = None,
) -> nextcord.Embed:
	"""
	Find the top min(len(money.csv), 10) users by balance in money.csv.

	Runtime = |money.csv| + runtime of sorted(money.csv) + 10
	= O(n) + O(nlog(n)) + 10 = O(nlog(n)).

	Args:
		target (nextcord.User or Member or str or None): The user invoking
			leaderboard() (default is None)
		msg (nextcord.Message or None): the message invoking
			leaderboard(); always present when invoking in server,
			sometimes absent in testing (default is None)

	Returns:
		nextcord.Embed: a summary of the richest users by balance.
			If target is somewhere on the leaderboard, also
			reports target's position and balance.

	"""
	emb = bb_embed("BeardlessBucks Leaderboard")
	if (msg and isinstance(target, str)):
		target = member_search(msg, target)
	if target and isinstance(target, nextcord.User | nextcord.Member):
		write_money(target, 300, writing=False, adding=False)
	with Path("resources/money.csv").open("r", encoding="UTF-8") as csv_file:
		lb_dict = {
			row[2]: int(row[1]) for row in csv.reader(csv_file, delimiter=",")
		}
	# Sort by value for each key in lbDict, which is BeardlessBucks balance
	sorted_dict = OrderedDict(sorted(lb_dict.items(), key=itemgetter(1)))
	pos = target_balance = None
	if target:
		users = list(sorted_dict.keys())
		try:
			pos = len(users) - users.index(str(target))
		except ValueError:
			pos = None
		else:
			target_balance = sorted_dict[str(target)]
	for i in range(min(len(sorted_dict), 10)):
		head, body = sorted_dict.popitem()
		last_entry: bool = (
			i != min(len(sorted_dict), 10) - 1
		)
		emb.add_field(
			name=f"{i + 1}. {head.split("#")[0]}",
			value=str(body),
			inline=last_entry,
		)
	if target and pos:
		assert not isinstance(target, str)
		emb.add_field(name=f"{target.name}'s position:", value=str(pos))
		emb.add_field(
			name=f"{target.name}'s balance:", value=str(target_balance),
		)
	return emb


def flip(author: nextcord.User | nextcord.Member, bet: str | int) -> str:
	"""
	Gamble a certain number of BeardlessBucks on a coin toss.

	Args:
		author (nextcord.User or Member): The user who is gambling
		bet (str): The amount author is wagering

	Returns:
		str: A report of the outcome and how author's balance changed.

	"""
	heads = random.randint(0, 1)
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
	if (
		(isinstance(bet, str) and "all" in bet)
		or (isinstance(bet, int) and bet >= 0)
	):
		result, bank = write_money(author, 300, writing=False, adding=False)
		if result == MoneyFlags.Registered:
			report = NewUserMsg
		elif result == MoneyFlags.CommaInUsername:
			assert isinstance(bank, str)
			report = bank
		elif isinstance(bet, int) and isinstance(bank, int) and bet > bank:
			report = (
				"You do not have enough BeardlessBucks to bet that much, {}!"
			)
		else:
			if isinstance(bet, int) and not heads:
				bet *= -1
			result = write_money(author, bet, writing=True, adding=True)[0]
			report = (
				"Heads! You win! Your winnings have"
				" been added to your balance, {}."
			) if heads else (
				"Tails! You lose! Your losses have been"
				" deducted from your balance, {}."
			)
			if result == MoneyFlags.BalanceUnchanged:
				report += (
					" Or, they would have been, if"
					" you had actually bet anything."
				)
	return report.format(author.mention)


def blackjack(
	author: nextcord.User | nextcord.Member, bet: str | int,
) -> tuple[str, BlackjackGame | None]:
	"""
	Gamble a certain number of BeardlessBucks on blackjack.

	Args:
		author (nextcord.User or Member): The user who is gambling
		bet (str): The amount author is wagering

	Returns:
		str: A report of the outcome and how author's balance changed.
		BlackjackGame or None: If there is still a game to play,
			returns the object representing the game of blackjack
			author is playing. Else, None.

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
	if (
		(isinstance(bet, str) and bet == "all")
		or (isinstance(bet, int) and bet >= 0)
	):
		result, bank = write_money(author, 300, writing=False, adding=False)
		if result == MoneyFlags.Registered:
			report = NewUserMsg
		elif result == MoneyFlags.CommaInUsername:
			assert isinstance(bank, str)
			report = bank
		elif isinstance(bet, int) and isinstance(bank, int) and bet > bank:
			report = (
				"You do not have enough BeardlessBucks to bet that much, {}!"
			)
		else:
			if bet == "all":
				assert bank is not None
				bet = bank
			game = BlackjackGame(author, int(bet))
			report = game.message
			if game.perfect():
				write_money(author, bet, writing=True, adding=True)
				game = None
	return report.format(author.mention), game


def active_game(
	games: list[BlackjackGame], author: nextcord.User | nextcord.Member,
) -> BlackjackGame | None:
	"""
	Check if a user has an active game of Blackjack.

	Args:
		games (list[BlackjackGame]): list of active Blackjack games
		author (nextcord.User or Member): The user who is gambling

	Returns:
		BlackjackGame or None: The user's current Blackjack game,
			if one exists. Else, None.

	"""
	game = [g for g in games if g.user == author]
	return game[0] if game else None
