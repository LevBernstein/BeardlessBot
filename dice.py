# Dice roller for Beardless Bot
from random import randint

def roll(message): # takes a string of the format !dn+b and rolls one n-sided die with a modifier of b.
    report = "Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100, as well as modifiers. No spaces allowed. Ex: !d4+3"
    command = message.split('!d',1)[1]
    modifier = -1 if "-" in command else 1
    if message == '!d2' or message == '!d1':
        return report
    if command.startswith("4") or command.startswith("6") or command.startswith("8"):
        report = randint(1,int(command[0])) + modifier*int(command[2:]) if len(command) != 1 and (command[1]=="+" or command[1] == "-") else randint(1,int(command[0]))
    elif command.startswith("100"):
        report = randint(1,100) + modifier*int(command[4:]) if len(command) != 3 and (command[3]=="+" or command[3] == "-") else randint(1,100)
    elif command.startswith("10") or command.startswith("12") or command.startswith("20"):
        report = randint(1,int(command[:2])) + modifier*int(command[3:]) if len(command) != 2 and (command[2]=="+" or command[2] == "-") else randint(1,int(command[:2]))
    return report