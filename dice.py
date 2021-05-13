# Dice roller for Beardless Bot
from random import randint

def roll(message):
    report = "Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100, as well as modifiers. No spaces allowed. Ex: !d4+3"
    command = message.split('!d',1)[1]
    #print(command[0])
    #print(command)
    isTen = False # Because !d10 and !d100 share their first two characters after the split, I was getting errors whenever I ran !d10 without a modifier.
    # This boolean takes care of those errors. The problem arises because both the conditions for rolling a d10 and 2/3 of the conditions for rolling a d100
    # would be met whenever the bot tried to roll a d10; then, when checking if command[2]=="0", I would get an array index out of bounds error, as the
    # length of the command is actually only 2, not 3. However, with the boolean isTen earlier in the line, now it will never check to see if command has that
    # third slot.
    if "-" in command:
        modifier = -1
    else:
        modifier = 1
    if message == '!d2' or message == '!d1':
        report = "Invalid side number. Enter 4, 6, 8, 10, 12, 20, or 100, as well as modifiers. No spaces allowed. Ex: !d4+3"
    else:
        if command[0] == "4":
            if len(command)==1:
                report = randint(1,4)
            elif (command[1]=="+" or command[1] == "-"):
                report = randint(1,4) + modifier*int(command[2:])
        elif command[0] == "6":
            if len(command)==1:
                report = randint(1,6)
            elif (command[1]=="+" or command[1] == "-"):
                report = randint(1,6) + modifier*int(command[2:])
        elif command[0] == "8":
            if len(command)==1:
                report = randint(1,8)
            elif (command[1]=="+" or command[1] == "-"):
                report = randint(1,8) + modifier*int(command[2:])
        elif command[0] == "1" and command[1] == "0":
            if len(command)==2:
                isTen = True
                report = randint(1,10)
            elif (command[2]=="+" or command[2] == "-"):
                isTen = True
                report = randint(1,10) + modifier*int(command[3:])
        elif command[0] == "1" and command[1] == "2":
            if len(command)==2:
                report = randint(1,12)
            elif (command[2]=="+" or command[2] == "-"):
                report = randint(1,12) + modifier*int(command[3:])
        elif command[0] == "2" and command[1] == "0":
            if len(command)==2:
                report = randint(1,20)
            elif (command[2]=="+" or command[2] == "-") :
                report = randint(1,20) + modifier*int(command[3:])
        if isTen == False and command[0] == "1" and command[1] == "0" and command[2] == "0":
            if len(command)==3:
                report = randint(1,100)
            elif (command[3]=="+" or command[3] == "-"):
                report = randint(1,100) + modifier*int(command[4:])
    return report
