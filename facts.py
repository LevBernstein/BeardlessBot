# Fun facts for Beardless Bot
from random import choice

def fact():
    facts = []
    with open("resources/facts.txt", "r") as f:
        for line in f.read().splitlines():
            facts.append(line)
    return choice(facts)

if __name__ == "__main__":
    print(fact())