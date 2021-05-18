# Fun facts for Beardless Bot
import csv
from random import choice

def fact():
    facts = []
    with open("resources/facts.txt") as csvfile:
        reader = csv.reader(csvfile, delimiter='\n')
        for row in reader:
            #print(row[0])
            facts.append(row[0])
    return choice(facts)
