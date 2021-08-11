# Beardless Bot Brawlhalla Commands

from json import dump, load
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
            return discord.Embed(title = "Random " + ranType.title(), description = "Your {} is {}."
            .format(ranType, choice(legends if ranType == "legend" else weapons)), color = 0xfff994)
        else:
            raise Exception
    except:
        return discord.Embed(title = "Brawlhalla Randomizer", description = "Please do !random legend or !random weapon.", color = 0xfff994)

def claimProfile(discordID, brawlID):
    with open("resources/claimedProfs.json", "r") as f:
        profs = load(f)
    profs[str(discordID)] = brawlID
    with open("resources/claimedProfs.json", "w") as g:
        dump(profs, g, indent = 4)

def fetchBrawlID(discordID):
    with open("resources/claimedProfs.json") as f:
        for key, value in load(f).items():
            if key == str(discordID):
                return value
    return None

def fetchLegends():
    with open("resources/legends.json") as f:
        return load(f)

def getBrawlID(brawlKey, profileURL):
    try:
        if not profileURL.startswith("https://steamcommunity.com"):
            return None
        steamID = steam.steamid.from_url(profileURL)
        r = requests.get("https://api.brawlhalla.com/search?steamid={}&api_key={}".format(steamID, brawlKey))
        return r.json()["brawlhalla_id"]
    except:
        return None

def getLegends(brawlKey):
    r = requests.get("https://api.brawlhalla.com/legend/all/?api_key={}".format(brawlKey))
    with open("resources/legends.json", "w") as f:
        dump(r.json(), f, indent = 4)

def legendInfo(brawlKey, legendName):
    # see https://github.com/BrawlDB/gerard3/blob/master/src/commands/bhInfo.js#L124 for formatting
    for legend in fetchLegends():
        if legendName in legend["legend_name_key"]:
            return requests.get("https://api.brawlhalla.com/legend/{}/?api_key={}"
            .format(legend["legend_id"], brawlKey)).json()
    return "Invalid legend!"

def getRank(target, brawlKey):
    brawlID = fetchBrawlID(target.id)
    if not brawlID:
        return None
    r = requests.get("https://api.brawlhalla.com/player/{}/ranked?api_key={}".format(brawlID, brawlKey)).json()
    if len(r) < 4:
        return -1
    rankColors = {"Diamond": 0x3d2399, "Platinum": 0x0051b4, "Gold": 0xf8d06a, "Silver": 0xbbbbbb, "Bronze": 0x674b25, "Tin": 0x355536}
    emb = (discord.Embed(title = "{}, {}".format(r["name"], r["region"]), color = 0xfff994)
    .set_footer(text = "Brawl ID {}".format(brawlID)).set_author(name = str(target), icon_url = target.avatar_url))
    if r["games"]:
        embVal = "**{}** ({}/{} Peak)\n{} W / {} L / {}% winrate".format(r["tier"], r["rating"], 
        r["peak_rating"], r["wins"], r["games"] - r["wins"], round(r["wins"]/r["games"] * 100, 1))
        if r["legends"]:
            topLegend = None
            for legend in r["legends"]:
                if not topLegend or topLegend[1] < legend["rating"]:
                    topLegend = (legend["legend_name_key"], legend["rating"])
            if topLegend:
                embVal += "\nTop Legend: {}, {} ELO".format(topLegend[0].title(), topLegend[1])
        emb.add_field(name = "Ranked 1s", value = embVal)
        if emb.color == discord.Color(0xfff994):
            for key, value in rankColors.items():
                if key in r["tier"]:
                    emb.color = value
                    break
    twosTeam = None
    if r["2v2"]:
        for team in r["2v2"]:
            if not twosTeam or twosTeam["rating"] < team["rating"]:
                twosTeam = team
    if twosTeam:
        emb.add_field(name = "Ranked 2s", value = "**{}\n{}** ({} / {} Peak)\n{} W / {} L / {}% winrate"
        .format(twosTeam["teamname"], twosTeam["tier"], twosTeam["rating"], twosTeam["peak_rating"],
        twosTeam["wins"], twosTeam["games"] - twosTeam["wins"], round(twosTeam["wins"]/twosTeam["games"] * 100, 1)))
        if emb.color == discord.Color(0xfff994):
            for key, value in rankColors.items():
                if key in twosTeam["tier"]:
                    emb.color = value
                    break
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
    # takes two API calls: one to get clan ID from player stats, one to get clan from clan ID
    r = requests.get("https://api.brawlhalla.com/player/{}/stats?api_key={}".format(brawlID, brawlKey))
    clanID = r.json()["clan"]["clan_id"]
    r = requests.get("https://api.brawlhalla.com/clan/{}/?api_key={}".format(clanID, brawlKey))
    return r.json()

# maybe implement leaderboard; glory https://github.com/BrawlDB/gerard3/blob/master/src/utils/glory.js

if __name__ == "__main__":
    try:
        with open("resources/brawlhallaKey.txt", "r") as f:
            brawlKey = f.readline()
    except Exception as err:
        print(err)
        brawlKey = None
    
    #print(legendInfo(brawlKey, "thor"))
    #print(getBrawlID(brawlKey, "https://steamcommunity.com/profiles/76561198347389883/"))
    #claimProfile(196354892208537600, 7032472)
    #claimProfile(195467081137782786, getBrawlID(brawlKey, "https://steamcommunity.com/id/SharkySharkinson/"))
    #print(fetchBrawlID(196354892208537600))
    #print(getRank(196354892208537600, brawlKey))
    #print(getStats(196354892208537600, brawlKey))
    #print(getClan(196354892208537600, brawlKey))
    getLegends(brawlKey)