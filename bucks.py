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

NoMultiplayerGameMsg = (
	"You do not currently have a multiplayer game of blackjack"
	" going, {}. Type '!blackjack new' to start one."
)

InvalidBetMsg = (
	"Invalid bet. Please choose a number greater than or equal"
	" to 0, or enter \"all\" to bet your whole balance, {}."
)

WinMsg = "You win! Your winnings have been added to your balance"
LoseMsg = "You lose! Your losses have been deducted from your balance"

GameHelpMsg = (
	"Type !hit to deal another card to yourself, "
	"or !stay to stop at your current total."
)


class BlackjackPlayer:
	"""
	BlackjackPlayer instantce.

	Attributes:
		name (Nextcord.User | Nextcord.Member):
			The discord user representing the player
		hand (list[int]): The player's current hand
		bet (int): The player's current bet

	Methods:
		check_bust(): Check if the player has gone over BlackjackGame.Goal.
		perfect(): Check if the user has reached BlackjackGame.Goal

	"""

	def __init__(self, name: nextcord.User | nextcord.Member) -> None:
		"""
		Create a new BlackjackPlayer instance.

		Args:
			name (nextcord.User or Member):
				The discord user representing this player

		"""
		self.name: nextcord.User | nextcord.Member = name
		self.hand: list[int] = []
		# TODO: make BlackjackPlayer.bet's type be 'int | None'
		# and add a phase after owner does '!tablestart' where
		# people make their bets
		# grep for '805746791' when this is changed
		self.bet: int = 10

	def check_bust(self) -> bool:
		"""
		Check if the player has gone over BlackjackGame.Goal.

		Returns:
			bool: Whether the user has gone over BlackjackGame.Goal.

		"""
		return sum(self.hand) > BlackjackGame.Goal

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
		owner (nextcord.User or Member): The user who is owns this game
		players (list[BlackjackPlayer]): The players in the game
		turn_idx (int): an index into players that holds player to play
		multiplayer (bool): Whether this match is multiplayer
		dealerUp (int): The card the dealer is showing face-up
		dealerSum (int): The running count of the dealer's cards
		deck (list): The cards remaining in the deck
		started (bool): Whether the match/round started
		message (str): The report to be sent in the Discord channel

	Methods:
		dealer_draw():
			Draw the dealers cards (at the end of the game).
		_end_round():
			Ends a round after everyone plays their turn.
		deal_to_current_player():
			Deals the player whose turn it is a card.
		card_name(card):
			Gives the human-friendly name of a given card.
		ready_to_start():
			Checks if a multiplayer match is ready to start.
		add_player(player):
			Add a player to multiplayer blackjack match.
		is_turn(player):
			Checks whether it is the turn of a given player.
		deal_top_card():
			Removes the top card from the deck.
		_deal_cards():
			Deal the starting cards to the dealer and all players.
		_start_game_regular():
			Starts a round where the dealer did not blackjack
		_start_game_blackjack():
			Starts a round where the dealer blackjacked.
		_dealer_blackjack_end_round():
			End a round where the dealer blackjacked.
		start_game():
			Deal the user(s) a starting hand of 2 cards.

	"""

	AceVal = 11
	DealerSoftGoal = 17
	FaceVal = 10
	Goal = 21
	CardVals = (2, 3, 4, 5, 6, 7, 8, 9, 10, FaceVal, FaceVal, FaceVal, AceVal)
	NumOfDecksInMatch = 4

	def __init__(
		self,
		owner: nextcord.User | nextcord.Member,
		*,
		multiplayer: bool,
	) -> None:
		"""
		Create a new BlackjackGame instance.

		In order to simulate the dealer standing on DealerSoftGoal, the
		dealer's sum will be incremented by a random card value until
		reaching DealerSoftGoal.

		Args:
			owner (nextcord.User or Member): The user who is owning this game
				in a singleplayer game the owner is also the only player.
				in multiplayer the owner is the one who can start the round.
			multiplayer (bool): Whether to make a multiplayer game

		"""
		self.owner = BlackjackPlayer(owner)
		self.players: list[BlackjackPlayer] = [self.owner]
		self.deck: list[int] = []
		self.deck.extend(BlackjackGame.CardVals * 4 * 4)  # 4 decks
		# TODO: dealerUp should NEVER be None
		# and dealerSum should NEVER be 0
		self.dealerUp: int | None = None
		self.dealerSum: int = 0
		self.started: bool = False
		self.turn_idx = 0
		self.multiplayer = multiplayer  # only multiplayer games can be joined
		if not multiplayer:
			self.message = self.start_game()
		else:
			self.message = "Multiplayer Blackjack game created!\n"

	def dealer_draw(self) -> list[int]:
		"""
		Simulate the dealer drawing cards.

		Will draw cards until dealer is above DealerSoftGoal
		Takes into accounts Ace overflow.

		Returns:
			list[int]: the dealers final hand

		"""
		assert self.dealerUp is not None
		dealer_cards: list[int] = [
			self.dealerUp, self.dealerSum - self.dealerUp,
		]
		while True:
			if self.dealerSum > BlackjackGame.DealerSoftGoal:
				if BlackjackGame.AceVal in dealer_cards:
					self.dealerSum -= 10
					dealer_cards[dealer_cards.index(BlackjackGame.AceVal)] = 1
				else:
					return dealer_cards
			elif self.dealerSum == BlackjackGame.DealerSoftGoal:
				return dealer_cards
			dealt = self.deal_top_card()
			dealer_cards.append(dealt)
			self.dealerSum += dealt

	def _play_dealer_turn(self) -> str:
		# dealer should only draw if there is at least 1 player that stayed
		for p in self.players:
			if not p.perfect() and not p.check_bust():
				if self.multiplayer:
					report = "Round ended, the dealer will now play\n"
				else:
					report = "The dealer will now play\n"
				dealer_cards: list[int] = self.dealer_draw()
				report += "The dealer's cards are {} ".format(
					", ".join(
						BlackjackGame.card_name(card)
						for card in dealer_cards),
				)
				report += f"for a total of {self.dealerSum}.\n"
				return report
		return ""

	def _end_round(self) -> str:
		"""
		End a round where the dealer blackjacked.

		Will draw the dealers cards only if at least one player stayed.

		Returns:
			str: final report

		"""
		assert self.dealerUp is not None
		assert self.dealerSum != 0
		report = self._play_dealer_turn()
		for p in self.players:
			if p.perfect() or p.check_bust():
				# these have already been handled and reported
				continue
			report += f"{p.name.mention}, "
			if sum(p.hand) > self.dealerSum and not p.check_bust():
				report += f"you're closer to {BlackjackGame.Goal} "
				report += (
					f"with a sum of {sum(p.hand)}. {WinMsg}"
				)
				write_money(
					p.name, p.bet, writing=True, adding=True,
				)
			elif sum(p.hand) == self.dealerSum:
				report += (
					f"That ties your sum of {sum(p.hand)}. "
					f"Your bet has been returned, {p.name.mention}."
				)
			elif self.dealerSum > BlackjackGame.Goal:
				report += (
					f"You have a sum of {sum(p.hand)}. "
					f"The dealer busts. {WinMsg}"
				)
				write_money(
					p.name, p.bet, writing=True, adding=True,
				)
			else:
				report += (
					f"That's closer to {BlackjackGame.Goal} "
					f"than your sum of {sum(p.hand)}. {LoseMsg}."
				)
				write_money(
					p.name, -p.bet, writing=True, adding=True,
				)
			if not p.bet:
				report += (
					"Unfortunately, you bet nothing, so this was all pointless."
				)
			report += "\n"  # trust me this is needed
		if not self.multiplayer:
			return report
		self.started = False
		self.dealerUp = None
		self.dealerSum = 0
		for p in self.players:
			p.hand = []
		report += "\nRound ended!"
		return report

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
			# TODO: this can cause us to draw more of a single facecard
			# than would exist in the card pool in a real game.
			# fixing this is not simple
			return "a " + random.choice(
				(str(BlackjackGame.FaceVal), "Jack", "Queen", "King"),
			)
		if card == BlackjackGame.AceVal:
			return "an Ace"
		return "an 8" if card == 8 else ("a " + str(card))  # noqa: PLR2004

	# NOTE: this is currently useless
	# for more info grep for '805746791'
	def ready_to_start(self) -> bool:
		"""
		Check if a multiplayer match is ready to start.

		Returns:
			bool: whether all players have placed a bet.

		"""
		assert self.multiplayer
		return all(player.bet is not None for player in self.players)

	def add_player(self, player: nextcord.User | nextcord.Member) -> None:
		"""
		Add a player to a multiplayer blackjack match.

		Args:
			player (nextcord.User | nextcord.Member): the player to add.

		"""
		assert self.multiplayer
		self.players.append(BlackjackPlayer(player))

	def is_turn(self, player: BlackjackPlayer) -> bool:
		"""
		Check whether it is the turn of a given player.

		Args:
			player (nextcord.User | nextcord.Member): the player to check.

		Returns:
			bool: whether is it the turn of 'player'

		"""
		if self.turn_idx < 0 or self.turn_idx >= len(self.players):
			return False
		return self.players[self.turn_idx] == player

	def deal_top_card(self) -> int:
		"""
		Remove and return the top card from the deck.

		Returns:
			int: The value of the top card of the deck.

		"""
		return self.deck.pop(random.randint(0, len(self.deck) - 1))

	def _deal_cards(self) -> None:
		"""Deal the starting cards to the dealer and all players."""
		self.dealerUp = self.deal_top_card()
		self.dealerSum = self.dealerUp + self.deal_top_card()
		for p in self.players:
			p.hand = []
			p.hand.append(self.deal_top_card())
			p.hand.append(self.deal_top_card())

	def _dealer_blackjack_end_round(self) -> None:
		"""End a round where the dealer blackjacked."""
		assert self.dealerSum == self.Goal
		if self.multiplayer:
			self.turn_idx = len(self.players)

	def _start_game_blackjack(self) -> str:
		"""Play players' turns after the dealer draws blackjacks."""
		message = "The dealer blackjacked!\n"
		for p in self.players:
			message += (
				f"{p.name.mention} your starting hand consists of "
				f"{p.hand[0]} and {p.hand[1]}. "
			)
			if p.perfect():
				message += (
					"You tied with the dealer, your bet is returned.\n"
				)
			else:
				message += (
					"You did not blackjack, you lose.\n"
				)
				write_money(p.name, -p.bet, writing=True, adding=True)
		self._dealer_blackjack_end_round()
		message += "\nRound ended."
		return message

	def _start_game_regular(self) -> str:
		"""
		Start a round where the dealer did not blackjack.

		Deals cards to all players.
		Handles ace overflows and player blackjacks.

		Returns:
			str: human readable report message.

		"""
		message = (
			f"The dealer is showing {self.dealerUp}, "
			"with one card face down.\n"
		)
		append_help: bool = not self.multiplayer
		for p in self.players:
			if p.check_bust():
				if self.multiplayer:
					append_help = True
				p.hand[1] = 1
				message += (
					f"{p.name.mention} your starting hand consists of two Aces."
					" One of them will act as a 1. Your total is 12.\n"
				)
			else:
				message += (
					f"{p.name.mention} your starting hand consists of "
					f"{BlackjackGame.card_name(p.hand[0])} "
					f"and {BlackjackGame.card_name(p.hand[1])}. "
				)
				if p.perfect():
					if not self.multiplayer:
						append_help = False
					elif p == self.players[self.turn_idx]:
						self.advance_turn()
					message += f"You hit {BlackjackGame.Goal}! {WinMsg}.\n"
					write_money(p.name, p.bet, writing=True, adding=True)
				else:
					if self.multiplayer:
						append_help = True
					message += f"Your total is {sum(p.hand)}.\n"
		if append_help:
			if not self.multiplayer:
				message += GameHelpMsg
			else:
				message += (
					f"\n{self.players[self.turn_idx].name.mention} "
					f"it is your turn! {GameHelpMsg}"
				)
		return message

	def start_game(self) -> str:
		"""
		Deal the user(s) a starting hand of 2 cards.

		Returns:
			str: Human readable report.

		"""
		self.turn_idx = 0
		self.started = True
		self._deal_cards()
		if self.dealerSum == BlackjackGame.Goal:
			return self._start_game_blackjack()
		return self._start_game_regular()

	def advance_turn(self) -> None:
		"""
		End current player's turn.

		Skips over all players that blackjacked.
		"""
		while True:
			self.turn_idx += 1
			if self.turn_idx == len(self.players):
				return
			player = self.players[self.turn_idx]
			# you can't bust without ever dealing
			assert not player.check_bust()
			# skip over all players that can't play
			if not player.perfect():
				return

	def round_over(self) -> bool:
		"""
		Check if the round ended.

		Returns:
			bool: if the round ended

		"""
		assert self.turn_idx <= len(self.players)
		return self.turn_idx == len(self.players)

	def deal_current_player(self) -> str:
		"""
		Deal the player whose turn it is a single card.

		Returns:
			str: report

		"""
		assert self.started
		dealt = self.deal_top_card()
		dealt_card = dealt
		player = self.players[self.turn_idx]
		player.hand.append(dealt)
		new_hand = player.hand
		append_help: bool = True
		report = (
			f"{player.name.mention} you were dealt "
			f"{BlackjackGame.card_name(dealt_card)}, "
			"bringing your total to "
		)
		if BlackjackGame.AceVal in player.hand and player.check_bust():
			for i, card in enumerate(player.hand):  # pragma: no branch
				if card == BlackjackGame.AceVal:
					player.hand[i] = 1
					break
			report += (
				f"{sum(new_hand) + 10}. "
				"To avoid busting, your Ace will be treated as a 1. "
				f"Your new total is {sum(new_hand)}. "
			)
		else:
			report += (
				f"{sum(new_hand)}. "
				"Your card values are {}. The dealer is"
				" showing {}, with one card face down."
			).format(", ".join(str(card) for card in new_hand), self.dealerUp)
		if player.check_bust():
			append_help = False
			write_money(
				player.name, -player.bet, writing=True, adding=True,
			)
			self.advance_turn()
			report += " You busted. Game over."
			if not self.round_over():
				report += (
					f"\n{self.players[self.turn_idx].name.mention}, "
					"it is your turn.\n"
				)
		elif player.perfect():
			append_help = False
			write_money(
				player.name, player.bet, writing=True, adding=True,
			)
			report += (
				f" You hit {BlackjackGame.Goal}! "
				f"{WinMsg}, {player.name.mention}.\n"
			)
			self.advance_turn()
		if append_help:
			report += f" {GameHelpMsg}"
		elif self.round_over():
			report += self._end_round()
		return report

	def stay_current_player(self) -> str:
		"""
		Stay the current player.

		if all other players' actions have been exhausted, end the round.

		Returns:
			bool: the round has ended.

		"""
		report = f"{self.players[self.turn_idx].name.mention} you stayed.\n"
		self.advance_turn()
		if self.round_over():
			report += self._end_round()
		else:
			report += (
				f"{self.players[self.turn_idx].name.mention}, "
				"it is not your turn.\n"
			)
		return report

	def get_player(
		self, player: nextcord.User | nextcord.Member,
	) -> BlackjackPlayer | None:
		"""
		Get player by name if in current match.

		Args:
			player (nextcord.User or nextcord.Member): the player to query

		Returns:
			BlackjackPlayer: the player if in match or None.

		"""
		for p in self.players:
			if p.name is player:
				return p
		return None


class MoneyFlags(Enum):
	"""Enum for additional readability in the writeMoney method."""

	NotEnoughBucks = -1
	BalanceUnchanged = 0
	BalanceChanged = 1
	Registered = 2


def write_money(
	member: nextcord.User | nextcord.Member,
	amount: str | int,
	*,
	writing: bool,
	adding: bool,
) -> tuple[MoneyFlags, int]:
	"""
	Check or modify a user's BeardlessBucks balance.

	Args:
		member (nextcord.User or Member): The target user
		amount (str or int): The amount to change member's balance by
		writing (bool): Whether to modify member's balance
		adding (bool): Whether to add to or overwrite member's balance

	Returns:
		tuple[MoneyFlags, int]: A tuple containing:
			MoneyFlags: enum representing the result of calling the method
			int: the current money in the user's bank after the operation

	"""
	assert "," not in member.name
	with Path("resources/money.csv").open("r", encoding="UTF-8") as csv_file:
		for row in csv.reader(csv_file, delimiter=","):
			if str(member.id) == row[0]:  # found member
				if isinstance(amount, str):  # for people betting all
					amount = -int(row[1]) if amount == "-all" else int(row[1])
				new_bank: int = int(row[1]) + amount if adding else amount
				if writing and row[1] != str(new_bank):
					if int(row[1]) + amount < 0:
						return MoneyFlags.NotEnoughBucks, int(row[1])
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
	return MoneyFlags.Registered, 300


def register(target: nextcord.User | nextcord.Member) -> nextcord.Embed:
	"""
	Register a new user for BeardlessBucks.

	Args:
		target (nextcord.User or Member): The user to register

	Returns:
		nextcord.Embed: the report of the target's registration.

	"""
	result, bonus = write_money(target, 300, writing=False, adding=False)
	report = bonus if result == MoneyFlags.Registered else (
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
			report = (
				NewUserMsg.format(msg.author.mention)
				if result == MoneyFlags.Registered
				else "Error!"
			)
	return bb_embed("BeardlessBucks Balance", report)


def reset(target: nextcord.User | nextcord.Member) -> str:
	"""
	Reset a user's Beardless balance to 200.

	Args:
		target (nextcord.User or Member): The user to reset

	Returns:
		str: the report of the target's balance reset.

	"""
	result, _ = write_money(target, 200, writing=True, adding=False)
	if result == MoneyFlags.Registered:
		report = NewUserMsg.format(target.mention)
	else:
		report = f"You have been reset to 200 BeardlessBucks, {target.mention}."
	return report


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
	report = InvalidBetMsg
	assert "," not in author.name
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
		elif isinstance(bet, int) and isinstance(bank, int) and bet > bank:
			report = (
				"You do not have enough BeardlessBucks to bet that much, {}!"
			)
		else:
			if isinstance(bet, int) and not heads:
				bet *= -1
			result = write_money(author, bet, writing=True, adding=True)[0]
			report = f"Heads! {WinMsg}" if heads else f"Tails! {LoseMsg}"
			report += f", {author.mention}.\n"
			if result == MoneyFlags.BalanceUnchanged:
				report += (
					"Or, they would have been, if"
					" you had actually bet anything."
				)
	return report.format(author.mention)


def can_make_bet(
	user: nextcord.User | nextcord.Member,
	bet: str | int,
) -> tuple[bool, str | None]:
	if isinstance(bet, str):
		if bet == "all":
			return True, None
		try:
			bet_num: int = int(bet)
		except ValueError:
			return False, InvalidBetMsg.format(user.mention)
	if bet_num < 0:
		return False, InvalidBetMsg.format(user.mention)

	result, bank = write_money(user, 300, writing=False, adding=False)
	if result == MoneyFlags.Registered:
		return True, NewUserMsg.format(user.name)
	if isinstance(bank, int) and bet_num > bank:
		return False, (
			"You do not have enough BeardlessBucks to "
			f"bet that much, {user.mention}!"
		)

	return True, None


def make_bet(
	author: nextcord.User | nextcord.Member,
	game: BlackjackGame,
	bet: str | int,  # expected to be either "all" or a number
) -> tuple[str, int]:
	report = InvalidBetMsg
	result, bank = write_money(author, 300, writing=False, adding=False)
	if result == MoneyFlags.Registered:
		report = NewUserMsg
	elif isinstance(bet, int) and isinstance(bank, int):
		if bet > bank:
			report = (
				"You do not have enough BeardlessBucks to bet that much, {}!"
			)
		else:
			report = game.message
	elif bet == "all":
		assert bank is not None
		bet = bank
		report = game.message
	return report, int(bet)  # this cast should work


def blackjack(
	author: nextcord.User | nextcord.Member,
	bet: str | int | None,
) -> tuple[str, BlackjackGame | None]:
	"""
	Gamble a certain number of BeardlessBucks on blackjack.

	Args:
		author (nextcord.User or Member): The user who is gambling
		bet (str | int | None): The amount author is wagering.
			if None then a multiplayer game is created & returned

	Returns:
		str: A report of the outcome and how author's balance changed.
		BlackjackGame or None: If there is still a game to play,
			returns the object representing the game of blackjack
			author is playing. Else if game has ended in blackjack, None.

	"""
	game = None
	if bet is None:
		# bet being None means user wants a multiplayer game
		game = BlackjackGame(author, multiplayer=True)
		report = game.message
		return report.format(author.mention), game
	if isinstance(bet, str) and bet != "all":
		try:
			bet = int(bet)
		except ValueError:
			return InvalidBetMsg.format(author.mention), game
	if (
		(isinstance(bet, str) and bet == "all")
		or (isinstance(bet, int) and bet >= 0)
	):
		game = BlackjackGame(author, multiplayer=False)
		report, bet = make_bet(author, game, bet)
		player = game.players[0]
		player.bet = bet
		if player.perfect():
			game = None
	return report.format(author.mention), game


def player_in_game(
	games: list[BlackjackGame], author: nextcord.User | nextcord.Member,
) -> tuple[BlackjackGame, BlackjackPlayer] | None:
	"""
	Check if a user has an active game of Blackjack.

	TODO: convert games list to dict[user_id, BlackJackGame], deprecate this.

	Args:
		games (list[BlackjackGame]): list of active Blackjack games
		author (nextcord.User or Member): The user who is gambling

	Returns:
		tuple[BlackjackGame, BlackjackPlayer] or None: The player associated
		with the discord account and the game they're in if they're in one.
		Else, None.

	"""
	for game in games:
		player = game.get_player(author)
		if player is not None:
			return game, player
	return None
