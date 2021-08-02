# Dice roller for Beardless Bot
from random import randint

import discord

def roll(message): # takes a string of the format !dn+b and rolls one n-sided die with a modifier of b.
    command = message.split('!d', 1)[1]
    modifier = -1 if "-" in command else 1
    sides = (4, 6, 8, 10, 12, 20, 100)
    if command.startswith("4") or command.startswith("6") or command.startswith("8"):
        return randint(1, int(command[0])) + modifier * int(command[2:]) if len(command) != 1 and (command[1] == "+" or command[1] == "-") else randint(1, int(command[0])) if int(command) in sides else None
    elif command.startswith("100"):
        return randint(1, 100) + modifier*int(command[4:]) if len(command) != 3 and (command[3] == "+" or command[3] == "-") else randint(1, 100) if int(command) in sides else None
    elif command.startswith("10") or command.startswith("12") or command.startswith("20"):
        return randint(1, int(command[:2])) + modifier * int(command[3:]) if len(command) != 2 and (command[2] == "+" or command[2] == "-") else randint(1, int(command[:2])) if int(command) in sides else None
    return None

def rollReport(text):
    result = roll(text.content.lower())
    report = "You got " + str(result) + ", " + text.author.mention + "." if result else "Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100, as well as modifiers. No spaces allowed. Ex: !d4+3"
    return discord.Embed(title = "Beardless Bot Dice", description = report, color = 0xfff994)