# Fun facts for Beardless Bot
from random import choice

def fact():
    with open("resources/facts.txt", "r") as f:
        return choice(f.read().splitlines())

if __name__ == "__main__":
    print(fact())