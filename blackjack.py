from random import choice, randint

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
		self.vals = (2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11)
		self.message = self.startingHand()
	
	def perfect(self):
		return sum(self.cards) == 21
	
	def startingHand(self):
		self.cards.append(choice(self.vals))
		self.cards.append(choice(self.vals))
		message = ("Your starting hand consists of {} and {}. Your total is {}. "
		.format(self.cardName(self.cards[0]), self.cardName(self.cards[1]), sum(self.cards)))
		if self.perfect():
			message += "You hit 21! You win, " + self.user.mention + "!"
		else:
			message += "The dealer is showing {}, with one card face down. ".format(self.dealerUp)
			if self.checkBust():# Case only fires if you're dealt two aces
				self.cards[1] = 1
				self.bet *= -1
				message = "Your starting hand consists of two Aces. One of them will act as a 1. Your total is 12. "
			message += "Type !hit to deal another card to yourself, or !stay to stop at your current total, " + self.user.mention + "."
		return message
	
	def cardName(self, card):
		if card == 10:
			return "a " + choice(("10", "Jack", "Queen", "King"))
		if card == 11:
			return "an Ace"
		if card == 8:
			return "an 8"
		return "a " + str(card)
	
	def deal(self):
		dealt = choice(self.vals)
		self.cards.append(dealt)
		self.message = "You were dealt {}, bringing your total to {}. ".format(self.cardName(dealt), sum(self.cards))
		if 11 in self.cards and self.checkBust():
			for i in range(len(self.cards)):
				if self.cards[i] == 11:
					self.cards[i] = 1
					self.bet *= -1
					break
			self.message = "You were dealt an Ace, which will be treated as a 1. Your new total is {}.".format(sum(self.cards))
		self.message += ("Your card values are {}. The dealer is showing {}, with one card face down."
		.format(", ".join(str(card) for card in self.cards), self.dealerUp))
		if self.checkBust():
			self.message += " You busted. Game over, " + self.user.mention + "."
		elif self.perfect():
			self.message += " You hit 21! You win, " + self.user.mention + "!"
		else:
			self.message += " Type !hit to deal another card to yourself, or !stay to stop at your current total, " + self.user.mention+ "."
	
	def checkBust(self):
		if sum(self.cards) > 21:
			self.bet *= -1
			return True
		return False
	
	def getUser(self):
		return self.user
	
	def stay(self):
		change = 1
		self.message = "The dealer has a total of {}."
		if sum(self.cards) > self.dealerSum and not self.checkBust():
			self.message += " You're closer to 21 with a sum of {}. You win! Your winnings have been added to your balance, {}."
		elif sum(self.cards) == self.dealerSum:
			change = 0
			self.message += " That ties your sum of {}. Your bet has been returned, {}."
		elif self.dealerSum > 21:
			self.message += " You have a sum of {}. The dealer busts. You win! Your winnings have been added to your balance, {}."
		else:
			self.message += " That's closer to 21 than your sum of {}. You lose. Your loss has been deducted from your balance, {}."
			self.bet *= -1
		self.message = self.message.format(self.dealerSum, sum(self.cards), self.user.mention)
		if not self.bet:
			self.message += " Unfortunately, you bet nothing, so this was all pointless."
		return change