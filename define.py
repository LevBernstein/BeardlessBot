import discord
import requests

def define(msg):
    word = msg.split(' ', 1)[1]
    if " " in word:
        report = "Please only look up individual words."
    else:
        r = requests.get("https://api.dictionaryapi.dev/api/v2/entries/en_US/" + word)
        if r.status_code == 200:
            try:
                emb = discord.Embed(title = word.upper(), description = "Audio: " + r.json()[0]['phonetics'][0]['audio'], color = 0xfff994)
                i = 0
                for entry in r.json():
                    for meaning in entry["meanings"]:
                        for definition in meaning["definitions"]:
                            i += 1
                            emb.add_field(name = "Definition " + str(i) + ":", value = definition["definition"], inline = True)
                return emb
            except:
                report = "Invalid word!"
        else:
            report = "Error!"
    return discord.Embed(title = "Beardless Bot Definitions", description = report, color = 0xfff994)