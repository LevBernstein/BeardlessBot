# Dice roller for Beardless Bot
from random import randint

def roll(message):
    report = "Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100, as well as modifiers. No spaces allowed. Ex: !d4+3"
    command = message.split('!d',1)[1]
    #print(command[0])
    #print(command)
    if "-" in command:
        modifier = -1
    else:
        modifier = 1
    if message == '!d2' or message == '!d1':
        return report
    if command.startswith("4"):
        if len(command)==1:
            report = randint(1,4)
        elif (command[1]=="+" or command[1] == "-"):
            report = randint(1,4) + modifier*int(command[2:])
    elif command.startswith("6"):
        if len(command)==1:
            report = randint(1,6)
        elif (command[1]=="+" or command[1] == "-"):
            report = randint(1,6) + modifier*int(command[2:])
    elif command.startswith("8"):
        if len(command)==1:
            report = randint(1,8)
        elif (command[1]=="+" or command[1] == "-"):
            report = randint(1,8) + modifier*int(command[2:])
    elif command.startswith("100"):
        if len(command)==3:
            report = randint(1,100)
        elif (command[3]=="+" or command[3] == "-"):
            report = randint(1,100) + modifier*int(command[4:])
    elif command.startswith("10"):
        if len(command)==2:
            report = randint(1,10)
        elif (command[2]=="+" or command[2] == "-"):
            report = randint(1,10) + modifier*int(command[3:])
    elif command.startswith("12"):
        if len(command)==2:
            report = randint(1,12)
        elif (command[2]=="+" or command[2] == "-"):
            report = randint(1,12) + modifier*int(command[3:])
    elif command.startswith("20"):
        if len(command)==2:
            report = randint(1,20)
        elif (command[2]=="+" or command[2] == "-") :
            report = randint(1,20) + modifier*int(command[3:])
    return report
