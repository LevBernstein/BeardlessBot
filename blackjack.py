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
        message = "Your starting hand consists of " + self.cardName(self.cards[0]) + " and " + self.cardName(self.cards[1]) + ". Your total is " + str(sum(self.cards)) + ". "
        if self.perfect():
            message += "You hit 21! You win, " + self.user.mention + "!"
        else:
            message += "The dealer is showing " + str(self.dealerUp) + ", with one card face down. Type !hit to deal another card to yourself, or !stay to stop at your current total, " + self.user.mention + "."
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
        card = choice(self.vals)
        self.cards.append(card)
        self.message = "You were dealt " + self.cardName(card) + ", bringing your total to " + str(sum(self.cards)) + ". " 
        if 11 in self.cards and self.checkBust():
            for i in range(len(self.cards)):
                if self.cards[i] == 11:
                    self.cards[i] = 1
                    break
            self.message += "Because you would have busted, your Ace has been changed from an 11 to 1 . Your new total is " + str(sum(self.cards)) + ". "
        self.message += "Your card values are " + ", ".join(str(card) for card in self.cards) + ". The dealer is showing " + str(self.dealerUp) + ", with one card face down."
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
        if sum(self.cards) > self.dealerSum and not self.checkBust():
            return 3
        if sum(self.cards) == self.dealerSum:
            return 0
        return 4 if self.dealerSum > 21 else -3