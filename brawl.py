# Beardless Bot Brawlhalla methods

from datetime import datetime
from json import dump, load
from random import choice

import discord
import requests
from steam.steamid import from_url

from misc import bbEmbed


badClaim = (
	"Please do !brawlclaim followed by the URL of your steam profile."
	"\nExample: !brawlclaim https://steamcommunity.com/id/beardless"
	"\nAlternatively, you can claim via your Brawlhalla ID, which"
	" you can find in the top right corner of your inventory.\n"
	"Example: !brawlclaim 7032472."
)

badRegion = (
	"Please specify a valid region, {}! Valid regions are US-E, US-W, EU,"
	" AUS, SEA, BRZ, JPN. If you need help, try doing !pins."
)

reqLimit = (
	"I've reached the request limit for the Brawlhalla API."
	" Please wait 15 minutes and try again later."
)

unclaimed = "{} needs to claim their profile first! Do !brawlclaim."

defaultPings = {
	"jpn": 0,
	"brz": 0,
	"us-w": 0,
	"us-e": 0,
	"sea": 0,
	"aus": 0,
	"eu": 0
}


def pingMsg(target: discord.Member, h: int, m: int, s: int) -> str:
	def plural(t):
		return "" if t == 1 else "s"

	return (
		"This region has been pinged too recently! Regions"
		" can only be pinged once every two hours, {}. You can"
		" ping again in {} hour{}, {} minute{}, and {} second{}."
	).format(target, h, plural(h), m, plural(m), s, plural(s))


def randomBrawl(ranType: str, key: str = None) -> discord.Embed:
	if ranType in ("legend", "weapon"):
		if ranType == "legend":
			choices = tuple(
				legend["legend_name_key"].title()
				for legend in fetchLegends()
			)
		else:
			choices = (
				"Sword",
				"Spear",
				"Orb",
				"Cannon",
				"Hammer",
				"Scythe",
				"Greatsword",
				"Bow",
				"Gauntlets",
				"Katars",
				"Blasters",
				"Axe"
			)
		if ranType == "legend" and key:
			return legendInfo(key, choice(choices).lower())
		return bbEmbed(
			"Random " + ranType.title(),
			f"Your {ranType} is {choice(choices)}."
		)
	return bbEmbed(
		"Brawlhalla Randomizer",
		"Please do !random legend or !random weapon."
	)


def claimProfile(discordID: int, brawlID: str):
	with open("resources/claimedProfs.json", "r") as f:
		profs = load(f)
	profs[str(discordID)] = brawlID
	with open("resources/claimedProfs.json", "w") as g:
		dump(profs, g, indent=4)


def fetchBrawlID(discordID: int) -> int:
	with open("resources/claimedProfs.json") as f:
		for key, value in load(f).items():
			if key == str(discordID):
				return value
	return None


def fetchLegends() -> list:
	with open("resources/legends.json") as f:
		return load(f)


def getBrawlID(brawlKey: str, profileURL: str) -> int:
	try:
		steamID = from_url(profileURL)
		if not steamID:
			return None
		r = requests.get(
			"https://api.brawlhalla.com/search?steamid={}&api_key={}"
			.format(steamID, brawlKey)
		)
		return r.json()["brawlhalla_id"]
	except Exception:
		return None


def getLegends(brawlKey: str):
	# run whenever a new legend is released
	with open("resources/legends.json", "w") as f:
		dump(
			requests.get(
				f"https://api.brawlhalla.com/legend/all/?api_key={brawlKey}"
			).json(),
			f,
			indent=4
		)


def legendInfo(brawlKey: str, legendName: str) -> discord.Embed:
	# TODO: add legend images as thumbnail
	if legendName == "hugin":
		legendName = "munin"
	for legend in fetchLegends():
		if legendName in legend["legend_name_key"]:
			r = requests.get(
				"https://api.brawlhalla.com/legend/{}/?api_key={}"
				.format(legend["legend_id"], brawlKey)
			).json()
			# Problematic extra space in 2nd quote for these legends:
			if legendName in ("reno", "teros", "hattori"):
				spaceCheck = -2
			else:
				spaceCheck = -1
			quoteOne = (
				r["bio_quote"]
				+ " *"
				+ (r["bio_quote_about_attrib"])[1:-1]
				+ "*"
			).replace("\\n", " ")
			quoteTwo = (
				r["bio_quote_from"]
				+ " *"
				+ (r["bio_quote_from_attrib"])[1:spaceCheck]
				+ "*"
			).replace("\\n", " ")
			bio = "\n\n".join(
				(
					r["bio_text"].replace("\n", "\n\n"),
					"**Quotes**",
					quoteOne,
					quoteTwo
				)
			)
			# TODO: Use to get legend images:
			# legendLinkName = r["bio_name"].replace(" ", "_")
			return (
				bbEmbed(r["bio_name"] + ", " + r["bio_aka"], bio)
				.add_field(
					name="Weapons",
					value=(r["weapon_one"] + ", " + r["weapon_two"])
					.replace("Fist", "Gauntlet")
					.replace("Pistol", "Blasters")
				)
				.add_field(
					name="Stats",
					value=(
						f"{r['strength']} Str, {r['dexterity']} Dex,"
						f" {r['defense']} Def, {r['speed']} Spd"
					)
				)
			)
	return None


def getRank(target: discord.Member, brawlKey: str) -> discord.Embed:
	# TODO: add rank images as thumbnail, clan below name;
	# download local copies of rank images bc there's no easy format on wiki
	brawlID = fetchBrawlID(target.id)
	if not brawlID:
		return bbEmbed(
			"Beardless Bot Brawlhalla Rank", unclaimed.format(target.mention)
		)
	r = requests.get(
		"https://api.brawlhalla.com/player/{}/ranked?api_key={}"
		.format(brawlID, brawlKey)
	).json()
	if len(r) < 4:
		return bbEmbed(
			"Beardless Bot Brawlhalla Rank",
			"You haven't played ranked yet this season."
		)
	rankColors = {
		"Diamond": 0x3D2399,
		"Platinum": 0x0051B4,
		"Gold": 0xF8D06A,
		"Silver": 0xBBBBBB,
		"Bronze": 0x674B25,
		"Tin": 0x355536
	}
	emb = (
		bbEmbed(f"{r['name']}, {r['region']}")
		.set_footer(text=f"Brawl ID {brawlID}")
		.set_author(name=str(target), icon_url=target.avatar_url)
	)
	if "games" in r:
		winRate = round(r["wins"] / r["games"] * 100, 1)
		embVal = (
			f"**{r['tier']}** ({r['rating']}/{r['peak_rating']} Peak)\n"
			f"{r['wins']} W / {r['games'] - r['wins']} L / {winRate}% winrate"
		)
		if r["legends"]:
			topLegend = None
			for legend in r["legends"]:
				if not topLegend or topLegend[1] < legend["rating"]:
					topLegend = legend["legend_name_key"], legend["rating"]
			if topLegend:
				embVal += (
					f"\nTop Legend: {topLegend[0].title()},"
					f" {topLegend[1]} Elo"
				)
		emb.add_field(name="Ranked 1s", value=embVal)
		for key, value in rankColors.items():
			if key in r["tier"]:
				emb.color = value
				break
	if "2v2" in r:
		twosTeam = None
		for team in r["2v2"]:
			# Find highest-Elo 2s pairing:
			if not twosTeam or twosTeam["rating"] < team["rating"]:
				twosTeam = team
		if twosTeam:
			emb.add_field(
				name="Ranked 2s",
				value=(
					"**{}\n{}** ({} / {} Peak)\n"
					"{} W / {} L / {}% winrate"
				).format(
					twosTeam["teamname"],
					twosTeam["tier"],
					twosTeam["rating"],
					twosTeam["peak_rating"],
					twosTeam["wins"],
					twosTeam["games"] - twosTeam["wins"],
					round(twosTeam["wins"] / twosTeam["games"] * 100, 1)
				)
			)
			if (
				emb.color == discord.Color(0xFFF994)
				or twosTeam["rating"] > r["rating"]
			):
				for key, value in rankColors.items():
					if key in twosTeam["tier"]:
						emb.color = value
						break
	return emb


def getStats(target: discord.Member, brawlKey: str) -> discord.Embed:
	brawlID = fetchBrawlID(target.id)
	if not brawlID:
		return bbEmbed(
			"Beardless Bot Brawlhalla Stats", unclaimed.format(target.mention)
		)
	r = requests.get(
		"https://api.brawlhalla.com/player/{}/stats?api_key={}"
		.format(brawlID, brawlKey)
	).json()
	if len(r) < 4:
		noStats = (
			"This profile doesn't have stats associated with it."
			" Please make sure you've claimed the correct profile."
		)
		return bbEmbed("Beardless Bot Brawlhalla Stats", noStats)
	embVal = (
		f"{r['wins']} Wins / {r['games'] - r['wins']} Losses\n{r['games']}"
		f" Games\n{round(r['wins'] / r['games'] * 100, 1)}% Winrate"
	)
	emb = (
		bbEmbed("Brawlhalla Stats for " + r["name"])
		.set_footer(text=f"Brawl ID {brawlID}")
		.add_field(name="Name", value=r["name"])
		.add_field(name="Overall W/L", value=embVal)
		.set_author(name=str(target), icon_url=target.avatar_url)
	)
	if "legends" in r:
		topUsed = topWinrate = topDPS = topTTK = None
		for legend in r["legends"]:
			if not topUsed or topUsed[1] < legend["xp"]:
				topUsed = legend["legend_name_key"].title(), legend["xp"]
			if legend["games"] and (
				not topWinrate
				or topWinrate[1]
				< round(legend["wins"] / legend["games"] * 100, 1)
			):
				topWinrate = (
					legend["legend_name_key"].title(),
					round(legend["wins"] / legend["games"] * 100, 1)
				)
			if legend["matchtime"] and (
				not topDPS
				or topDPS[1]
				< round(int(legend["damagedealt"]) / legend["matchtime"], 1)
			):
				topDPS = (
					legend["legend_name_key"].title(),
					round(int(legend["damagedealt"]) / legend["matchtime"], 1)
				)
			if legend["kos"] and (
				not topTTK
				or topTTK[1] > round(legend["matchtime"] / legend["kos"], 1)
			):
				topTTK = (
					legend["legend_name_key"].title(),
					round(legend["matchtime"] / legend["kos"], 1)
				)
		if all((topUsed, topWinrate, topDPS, topTTK)):
			emb.add_field(
				name="Legend Stats (20 game min)", value=(
					f"**Most Played:** {topUsed[0]}\n**Highest Winrate:"
					f"** {topWinrate[0]}, {topWinrate[1]}%\n**Highest Avg"
					f" DPS:** {topDPS[0]}, {topDPS[1]}\n**Shortest Avg TTK:"
					f"** {topTTK[0]}, {topTTK[1]}s"
				)
			)
	if "clan" in r:
		emb.add_field(
			name="Clan",
			value=f"{r['clan']['clan_name']}\nClan ID: {r['clan']['clan_id']}"
		)
	return emb


def getClan(target: discord.Member, brawlKey: str) -> discord.Embed:
	brawlID = fetchBrawlID(target.id)
	if not brawlID:
		return bbEmbed(
			"Beardless Bot Brawlhalla Clan", unclaimed.format(target.mention)
		)
	# Takes two API calls: one to get clan ID from player stats,
	# one to get clan from clan ID. As a result, this command is very slow.
	# TODO: Try to find a way around this.
	r = requests.get(
		"https://api.brawlhalla.com/player/{}/stats?api_key={}"
		.format(brawlID, brawlKey)
	).json()
	if "clan" not in r:
		return bbEmbed(
			"Beardless Bot Brawlhalla Clan", "You are not in a clan!"
		)
	r = requests.get(
		"https://api.brawlhalla.com/clan/{}/?api_key={}"
		.format(r["clan"]["clan_id"], brawlKey)
	).json()
	emb = bbEmbed(
		r["clan_name"],
		"**Clan Created:** {}\n**Experience:** {}\n**Members:** {}"
		.format(
			str(datetime.fromtimestamp(r["clan_create_date"]))[:-9],
			r["clan_xp"],
			len(r["clan"])
		)
	).set_footer(text=f"Clan ID {r['clan_id']}")
	for i in range(min(len(r["clan"]), 9)):
		member = r["clan"][i]
		emb.add_field(
			name=member["name"],
			value="{} ({} xp)\nJoined {}"
			.format(
				member["rank"],
				member["xp"],
				str(datetime.fromtimestamp(member["join_date"]))[:-9]
			)
		)
	return emb


def brawlCommands() -> discord.Embed:
	emb = bbEmbed("Beardless Bot Brawlhalla Commands")
	comms = (
		(
			"!brawlclaim",
			"Claims a Brawlhalla account, allowing the other commands.",
		),
		("!brawlrank", "Displays a user's ranked information."),
		("!brawlstats", "Displays a user's general stats."),
		("!brawlclan", "Displays a user's clan information."),
		("!brawllegend", "Displays lore and stats for a legend."),
		(
			"!random legend/weapon",
			"Randomly chooses a legend or weapon for you to play.",
		)
	)
	for commandPair in comms:
		emb.add_field(name=commandPair[0], value=commandPair[1])
	return emb


# TODO implement leaderboard, glory
# See: https://github.com/BrawlDB/gerard3/blob/master/src/utils/glory.js
