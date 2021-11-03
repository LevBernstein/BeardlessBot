# Beardless Bot Brawlhalla Commands

from datetime import datetime
from json import dump, load, loads
from random import choice

import discord
import requests
import steam
from steam.steamid import SteamID

from misc import bbEmbed

badClaim = ("Please do !brawlclaim followed by the URL of your steam profile.\nExample: !brawlclaim https://steamcommunity.com/id/beardless\n" +
"Alternatively, you can claim via your Brawlhalla ID, which you can find in the top right corner of your inventory.\nExample: !brawlclaim 7032472.")

badRegion = "Please specify a valid region, {}! Valid regions are US-E, US-W, EU, AUS, SEA, BRZ, JPN. If you need help, try doing !pins."

reqLimit = "I've reached the request limit for the Brawlhalla API. Please wait 15 minutes and try again later."

unclaimed = "{} needs to claim their profile first! Do !brawlclaim."

def pingMsg(target, h, m, s):
	plural = lambda t: "" if t == 1 else "s"
	badPing = ("This region has been pinged too recently! Regions can only be pinged once" +
	" every two hours, {}. You can ping again in {} hour{}, {} minute{}, and {} second{}.")
	return badPing.format(target, h, plural(h), m, plural(m), s, plural(s))

def randomBrawl(ranType):
	try:
		if ranType in ("legend", "weapon"):
			legends = tuple(legend["legend_name_key"].title() for legend in fetchLegends())
			weapons = "Sword", "Spear", "Orb", "Cannon", "Hammer", "Scythe", "Greatsword", "Bow", "Gauntlets", "Katars", "Blasters", "Axe"
			#return bbEmbed("Random " + ranType.title(), "Your {} is {}.".format(ranType, choice(legends if ranType == "legend" else weapons)))
			return bbEmbed("Random " + ranType.title(), f"Your {ranType} is {choice(legends if ranType == 'legend' else weapons)}.")
		else:
			raise Exception
	except:
		return bbEmbed("Brawlhalla Randomizer", "Please do !random legend or !random weapon.")

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
		steamID = steam.steamid.from_url(profileURL)
		if not steamID:
			raise Exception("Invalid Steam profile URL!")
		r = requests.get(f"https://api.brawlhalla.com/search?steamid={steamID}&api_key={brawlKey}")
		return r.json()["brawlhalla_id"]
	except:
		return None

def getLegends(brawlKey):
	# run whenever a new legend is released
	with open("resources/legends.json", "w") as f:
		dump(requests.get(f"https://api.brawlhalla.com/legend/all/?api_key={brawlKey}").json(), f, indent = 4)

def legendInfo(brawlKey, legendName):
	# TODO: add legend images as thumbnail
	if legendName == "hugin":
		legendName = "munin"
	for legend in fetchLegends():
		if legendName in legend["legend_name_key"]:
			r = requests.get(f"https://api.brawlhalla.com/legend/{legend['legend_id']}/?api_key={brawlKey}").json()
			spaceCheck = -2 if legendName in ("reno", "teros", "hattori") else -1 # problematic extra space in 2nd quote for these legends
			quoteOne = (r["bio_quote"] + " *" + (r["bio_quote_about_attrib"])[1:-1] + "*").replace("\\n", " ")
			quoteTwo = (r["bio_quote_from"] + " *" + (r["bio_quote_from_attrib"])[1:spaceCheck] + "*").replace("\\n", " ")
			bio = "\n\n".join((r["bio_text"].replace("\n", "\n\n"), "**Quotes**", quoteOne, quoteTwo))
			#legendLinkName = r["bio_name"].replace(" ", "_") # TODO: use to get legend images
			return (bbEmbed(r["bio_name"] + ", " + r["bio_aka"], bio)
			.add_field(name = "Weapons", value = (r["weapon_one"] + ", " + r["weapon_two"]).replace("Fist", "Gauntlet").replace("Pistol", "Blasters"))
			.add_field(name = "Stats", value = f"{r['strength']} Str, {r['dexterity']} Dex, {r['defense']} Def, {r['speed']} Spd"))
	return None

def getRank(target, brawlKey):
	# TODO: add rank images as thumbnail, clan below name; download local copies of rank images bc there's no easy format on wiki
	brawlID = fetchBrawlID(target.id)
	if not brawlID:
		return unclaimed.format(target.mention)
	r = requests.get(f"https://api.brawlhalla.com/player/{brawlID}/ranked?api_key={brawlKey}").json()
	if len(r) < 4:
		return "You haven't played ranked yet this season."
	rankColors = {"Diamond": 0x3d2399, "Platinum": 0x0051b4, "Gold": 0xf8d06a, "Silver": 0xbbbbbb, "Bronze": 0x674b25, "Tin": 0x355536}
	emb = bbEmbed(f"{r['name']}, {r['region']}").set_footer(text = f"Brawl ID {brawlID}").set_author(name = str(target), icon_url = target.avatar_url)
	if "games" in r:
		winRate = round(r["wins"] / r["games"] * 100, 1)
		embVal = f"**{r['tier']}** ({r['rating']}/{r['peak_rating']} Peak)\n{r['wins']} W / {r['games'] - r['wins']} L / {winRate}% winrate"
		if r["legends"]:
			topLegend = None
			for legend in r["legends"]:
				if not topLegend or topLegend[1] < legend["rating"]:
					topLegend = legend["legend_name_key"], legend["rating"]
			if topLegend:
				embVal += f"\nTop Legend: {topLegend[0].title()}, {topLegend[1]} Elo"
		emb.add_field(name = "Ranked 1s", value = embVal)
		for key, value in rankColors.items():
			if key in r["tier"]:
				emb.color = value
				break
	if "2v2" in r:
		twosTeam = None
		for team in r["2v2"]:
			if not twosTeam or twosTeam["rating"] < team["rating"]: # find highest-Elo 2s pairing
				twosTeam = team
		if twosTeam:
			emb.add_field(name = "Ranked 2s", value = "**{}\n{}** ({} / {} Peak)\n{} W / {} L / {}% winrate"
			.format(twosTeam["teamname"], twosTeam["tier"], twosTeam["rating"], twosTeam["peak_rating"],
			twosTeam["wins"], twosTeam["games"] - twosTeam["wins"], round(twosTeam["wins"] / twosTeam["games"] * 100, 1)))
			if emb.color == discord.Color(0xfff994) or twosTeam["rating"] > r["rating"]:
				for key, value in rankColors.items():
					if key in twosTeam["tier"]:
						emb.color = value
						break
	return emb

def getStats(target, brawlKey):
	# TODO: add clan below name, make this look not terrible
	brawlID = fetchBrawlID(target.id)
	if not brawlID:
		return unclaimed.format(target.mention)
	r = requests.get(f"https://api.brawlhalla.com/player/{brawlID}/stats?api_key={brawlKey}").json()
	if len(r) < 4:
		return "This profile doesn't have stats associated with it. Please make sure you've claimed the correct profile."
	embVal = f"{r['wins']} Wins / {r['games'] - r['wins']} Losses\n{r['games']} Games\n{round(r['wins'] / r['games'] * 100, 1)}% Winrate"
	emb = (bbEmbed("Brawlhalla Stats for " + r["name"]).set_footer(text = f"Brawl ID {brawlID}").add_field(name = "Overall W/L", value = embVal)
	.set_author(name = str(target), icon_url = target.avatar_url).add_field(name = "Name", value = r["name"]))
	if "legends" in r:
		topUsed = topWinrate = topDPS = topTTK = None
		for legend in r["legends"]:
			if not topUsed or topUsed[1] < legend["xp"]:
				topUsed = legend["legend_name_key"].title(), legend["xp"]
			if legend["games"] and (not topWinrate or topWinrate[1] < round(legend["wins"] / legend["games"] * 100, 1)):
				topWinrate = legend["legend_name_key"].title(), round(legend["wins"] / legend["games"] * 100, 1)
			if legend["matchtime"] and (not topDPS or topDPS[1] < round(int(legend["damagedealt"]) / legend["matchtime"], 1)):
				topDPS = legend["legend_name_key"].title(), round(int(legend["damagedealt"]) / legend["matchtime"], 1)
			if legend ["kos"] and (not topTTK or topTTK[1] > round(legend["matchtime"] / legend["kos"], 1)):
				topTTK = legend["legend_name_key"].title(), round(legend["matchtime"] / legend["kos"], 1)
		if all((topUsed, topWinrate, topDPS, topTTK)):
			emb.add_field(value = "**Most Played:** {}\n**Highest Winrate:** {}, {}%\n**Highest Avg DPS:** {}, {}\n**Shortest Avg TTK:** {}, {}s"
			.format(topUsed[0], topWinrate[0], topWinrate[1], topDPS[0], topDPS[1], topTTK[0], topTTK[1]), name = "Legend Stats (20 game min)")
	return emb

def getClan(target, brawlKey):
	brawlID = fetchBrawlID(target.id)
	if not brawlID:
		return unclaimed.format(target.mention)
	# takes two API calls: one to get clan ID from player stats, one to get clan from clan ID
	# as a result, this command is very slow. TODO: Try to find a way around this.
	r = requests.get(f"https://api.brawlhalla.com/player/{brawlID}/stats?api_key={brawlKey}").json()
	if not "clan" in r:
		return "You are not in a clan!"
	r = requests.get(f"https://api.brawlhalla.com/clan/{r['clan']['clan_id']}/?api_key={brawlKey}").json()
	emb = (bbEmbed(r["clan_name"], "**Clan Created:** {}\n**Experience:** {}\n**Members:** {}"
	.format(str(datetime.fromtimestamp(r["clan_create_date"]))[:-9], r["clan_xp"], len(r["clan"]))).set_footer(text = f"Clan ID {r['clan_id']}"))
	for i in range(min(len(r["clan"]), 9)):
		member = r["clan"][i]
		emb.add_field(name = member["name"], value = "{} ({} xp)\nJoined {}"
		.format(member["rank"], member["xp"], str(datetime.fromtimestamp(member["join_date"]))[:-9]))
	return emb

def brawlCommands():
	emb = bbEmbed("Beardless Bot Brawlhalla Commands")
	comms = (("!brawlclaim", "Claims a Brawlhalla account, allowing the other commands."),
		("!brawlrank", "Displays a user's ranked information."),
		("!brawlstats", "Displays a user's general stats."),
		("!brawlclan", "Displays a user's clan information."),
		("!brawllegend", "Displays lore and stats for a legend."),
		("!random legend/weapon", "Randomly chooses a legend or weapon for you to play."))
	for commandPair in comms:
		emb.add_field(name = commandPair[0], value = commandPair[1])
	return emb

# maybe implement brawl ID lookup, leaderboard, glory https://github.com/BrawlDB/gerard3/blob/master/src/utils/glory.js