# Beardless Bot Brawlhalla Commands
import json

from random import choice

import discord
import requests
import steam

from steam.steamid import SteamID

def randomBrawl(msg):
    try:
        ranType = msg.split(' ', 1)[1]
        if ranType in ("legend", "weapon"):
            legends = tuple(legend["legend_name_key"].title() for legend in fetchLegends())
            weapons = ("Sword", "Spear", "Orb", "Cannon", "Hammer", "Scythe", "Greatsword", "Bow", "Gauntlets", "Katars", "Blasters", "Axe")
            return discord.Embed(title = "Random " + ranType.title(), description = "Your {} is {}.".format(ranType, choice(legends if ranType == "legend" else weapons)), color = 0xfff994)
        else:
            return discord.Embed(title = "Invalid random!", description = "Please do !random legend or !random weapon.", color = 0xfff994)
    except:
        return discord.Embed(title = "Brawlhalla Randomizer", description = "Please do !random legend or !random weapon to get a random legend or weapon.", color = 0xfff994)

def getBrawlID(key, profileURL):
    try:
        if not profileURL.startswith("https://steamcommunity.com"):
            raise Exception
        steamID = steam.steamid.from_url(profileURL)
        r = requests.get("https://api.brawlhalla.com/search?steamid={}&api_key={}".format(steamID, key))
        return r.json()["brawlhalla_id"]
    except:
        return None

def legendInfo(key, legendName):
    # see: https://github.com/BrawlDB/gerard3/blob/master/src/commands/bhInfo.js#L124 for formatting
    for legend in fetchLegends():
        if legendName in legend["legend_name_key"]:
            return requests.get("https://api.brawlhalla.com/legend/{}/?api_key={}".format(legend["legend_id"], key)).json()
    return "Invalid legend!"

def claimProfile(key, discordID, brawlID):
    with open("resources/claimedProfs.json", "r") as f:
        profs = json.load(f)
    profs[str(discordID)] = brawlID
    with open("resources/claimedProfs.json", "w") as g:
        json.dump(profs, g, indent = 4)

def fetchBrawlID(discordID):
    with open("resources/claimedProfs.json") as f:
        for key, value in json.load(f).items():
            if key == str(discordID):
                return value
    return None

def getRank(target, brawlKey):
    brawlID = fetchBrawlID(target.id)
    if not brawlID:
        return None
    r = requests.get("https://api.brawlhalla.com/player/{}/ranked?api_key={}".format(brawlID, brawlKey)).json()
    if len(r) < 5:
        return -1
    emb = discord.Embed(title = "{}'s Brawlhalla Rank".format(target.name), description = "Brawlhalla id: {}".format(brawlID), color = 0xfff994)
    emb.add_field(name = "Brawlhalla name", value = r["name"])
    if r["games"]:
        emb.add_field(name = "1s ELO", value = "Current ELO: {}\nPeak ELO: {}".format(r["rating"], r["peak_rating"]))
        emb.add_field(name = "Tier", value = r["tier"])
        emb.add_field(name = "W/L", value = "{} wins, {} losses\n{}% winrate".format(r["wins"], r["games"] - r["wins"], round(r["wins"]/r["games"] * 100, 1)))
    topLegend = None
    if r["legends"]:
        for legend in r["legends"]:
            if not topLegend or topLegend[1] < legend["rating"]:
                topLegend = (legend["legend_name_key"], legend["rating"])
    if topLegend:
        emb.add_field(name = "Top Legend", value = topLegend[0].title() + "\n" + str(topLegend[1]) + " ELO")
    twosTeam = None
    if r["2v2"]:
        for team in r["2v2"]:
            if not twosTeam or twosTeam[1] < team["rating"]:
                twosTeam = (team["teamname"], team["rating"], team["peak_rating"])
    if twosTeam:
        emb.add_field(name = "Top 2s Team: " + twosTeam[0], value = "Current ELO: {}\nPeak ELO: {}".format(twosTeam[1], twosTeam[2]))
    return emb

def getStats(discordID, brawlKey):
    brawlID = fetchBrawlID(discordID)
    if not brawlID:
        return "You need to do !claim first!"
    r = requests.get("https://api.brawlhalla.com/player/{}/stats?api_key={}".format(brawlID, brawlKey))
    return r.json()

def getClan(discordID, brawlKey):
    brawlID = fetchBrawlID(discordID)
    if not brawlID:
        return "You need to do !claim first!"
    r = requests.get("https://api.brawlhalla.com/player/{}/stats?api_key={}".format(brawlID, brawlKey))
    clanID = r.json()["clan"]["clan_id"]
    r = requests.get("https://api.brawlhalla.com/clan/{}/?api_key={}".format(clanID, brawlKey))
    return r.json()

def getLegends(brawlKey):
    r = requests.get("https://api.brawlhalla.com/legend/all/?api_key={}".format(brawlKey))
    with open("resources/legends.json", "w") as f:
        json.dump(r.json(), f, indent = 4)

def fetchLegends():
    with open("resources/legends.json") as f:
        return json.load(f)

#maybe implement leaderboard; glory https://github.com/BrawlDB/gerard3/blob/master/src/utils/glory.js

if __name__ == "__main__":
    try:
        with open("resources/brawlhallaKey.txt", "r") as f: # in brawlhallaKey.txt, paste in your own Brawlhalla API key
            brawlKey = f.readline()
    except Exception as err:
        print(err)
        brawlKey = "Invalid API key!"
        
    #print(legendInfo(brawlKey, "thor"))
    #print(getBrawlID(brawlKey, "https://steamcommunity.com/profiles/76561198347389883/"))
    #claimProfile(brawlKey, 196354892208537600, 7032472)
    #claimProfile(brawlKey, 195467081137782786, getBrawlID(brawlKey, "https://steamcommunity.com/id/SharkySharkinson/"))
    #print(fetchBrawlID(196354892208537600))
    #print(getRank(196354892208537600, brawlKey))
    #print(getStats(196354892208537600, brawlKey))
    #print(getClan(196354892208537600, brawlKey))
    getLegends(brawlKey)