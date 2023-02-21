# Beardless Bot Brawlhalla methods

from datetime import datetime
from json import dump, load
from random import choice
from typing import Any, Dict, Optional, Tuple

import nextcord
import requests
from steam.steamid import from_url

from misc import bbEmbed, fetchAvatar


badClaim = (
	"Please do !brawlclaim followed by the URL of your steam profile."
	"\nExample: !brawlclaim https://steamcommunity.com/id/beardless"
	"\nAlternatively, you can claim via your Brawlhalla ID, which"
	" you can find in the top right corner of your inventory.\n"
	"Example: !brawlclaim 7032472."
)

badRegion = (
	"Please specify a valid region, {}! Valid regions are US-E, US-W, EU,"
	" AUS, SEA, BRZ, JPN, MEA, SAF. If you need help, try doing !pins."
)

reqLimit = (
	"I've reached the request limit for the Brawlhalla API."
	" Please wait 15 minutes and try again later."
)

unclaimed = "{} needs to claim their profile first! " + badClaim

thumbBase = (
	"https://static.wikia.nocookie.net/brawlhalla_gamepedia/images/"
	"{}/Banner_Rank_{}.png/revision/latest/scale-to-width-down/{}"
)

rankedThumbnails = {
	"Diamond": ("4/46", "Diamond", "84?cb=20161110140154"),
	"Platinum": ("6/6e", "Platinum", "102?cb=20161110140140"),
	"Gold": ("6/69", "Gold", "109?cb=20161110140126"),
	"Silver": ("5/5c", "Silver", "119?cb=20161110140055"),
	"Bronze": ("a/a6", "Bronze", "112?cb=20161110140114"),
	"Tin": ("e/e1", "Tin", "112?cb=20161110140036")
}

rankColors = {
	"Diamond": 0x3D2399,
	"Platinum": 0x0051B4,
	"Gold": 0xF8D06A,
	"Silver": 0xBBBBBB,
	"Bronze": 0x674B25,
	"Tin": 0x355536
}

weapons = (
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
	"Axe",
	"Battle Boots"
)

regions = (
	"jpn",
	"brz",
	"us-w",
	"us-e",
	"sea",
	"aus",
	"eu",
	"mea",
	"saf"
)


def brawlWinRate(j: Dict[str, int]) -> float:
	return round(j["wins"] / j["games"] * 100, 1)


def pingMsg(target: nextcord.Member, h: int, m: int, s: int) -> str:
	def plural(t: int):
		return "" if t == 1 else "s"

	return (
		"This region has been pinged too recently! Regions"
		" can only be pinged once every two hours, {}. You can"
		" ping again in {} hour{}, {} minute{}, and {} second{}."
	).format(target, h, plural(h), m, plural(m), s, plural(s))


def randomBrawl(ranType: str, key: str = None) -> nextcord.Embed:
	if ranType in ("legend", "weapon"):
		if ranType == "legend":
			choices = tuple(
				legend["legend_name_key"].title() for legend in fetchLegends()
			)
			if key:
				return legendInfo(key, choice(choices).lower())
		else:
			choices = weapons
		return bbEmbed(
			"Random " + ranType.title(),
			f"Your {ranType} is {choice(choices)}."
		)
	return bbEmbed(
		"Brawlhalla Randomizer", "Please do !random legend or !random weapon."
	)


def claimProfile(discordID: int, brawlID: int):
	with open("resources/claimedProfs.json", "r") as f:
		profs = load(f)
	profs[str(discordID)] = brawlID
	with open("resources/claimedProfs.json", "w") as g:
		dump(profs, g, indent=4)


def fetchBrawlID(discordID: int) -> Optional[int]:
	with open("resources/claimedProfs.json") as f:
		for key, value in load(f).items():
			if key == str(discordID):
				return value
	return None


def fetchLegends() -> list:
	with open("resources/legends.json") as f:
		return load(f)


def apiCall(route: str, arg: str, key: str, amp: str = "?") -> Dict[str, Any]:
	url = f"https://api.brawlhalla.com/{route}{arg}{amp}api_key={key}"
	return requests.get(url).json()


def getBrawlID(brawlKey: str, profileURL: str) -> Optional[int]:
	try:
		if not (steamID := from_url(profileURL)):
			return None
		r = apiCall("search?steamid=", steamID, brawlKey, "&")
		return r["brawlhalla_id"]
	except TypeError:
		return None


def getLegends(brawlKey: str):
	# run whenever a new legend is released
	with open("resources/legends.json", "w") as f:
		dump(apiCall("legend/", "all/", brawlKey), f, indent=4)


def legendInfo(brawlKey: str, legendName: str) -> Optional[nextcord.Embed]:
	# TODO: add legend images as thumbnail
	if legendName == "hugin":
		legendName = "munin"
	for legend in fetchLegends():
		if legendName in legend["legend_name_key"]:
			r = apiCall("legend/", str(legend["legend_id"]) + "/", brawlKey)

			def cleanQuote(quote: str, attrib: str) -> str:
				return "{}  *{}*".format(
					quote, attrib.replace("\"", "")
				).replace("\\n", " ").replace("* ", "*").replace(" *", "*")

			bio = "\n\n".join((
				r["bio_text"].replace("\n", "\n\n"),
				"**Quotes**",
				cleanQuote(r["bio_quote"], r["bio_quote_about_attrib"]),
				cleanQuote(r["bio_quote_from"], r["bio_quote_from_attrib"])
			))
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


def getRank(target: nextcord.Member, brawlKey: str) -> nextcord.Embed:
	# TODO: add rank images as thumbnail, clan below name;
	# download local copies of rank images bc there's no easy format on wiki
	if not (brawlID := fetchBrawlID(target.id)):
		return bbEmbed(
			"Beardless Bot Brawlhalla Rank", unclaimed.format(target.mention)
		)
	if (
		len(r := apiCall("player/", str(brawlID) + "/ranked", brawlKey)) < 4
		or (
			("games" in r and r["games"] == 0)
			and ("2v2" in r and len(r["2v2"]) == 0)
		)
	):
		return (
			bbEmbed(
				"Beardless Bot Brawlhalla Rank",
				"You haven't played ranked yet this season."
			)
			.set_footer(text=f"Brawl ID {brawlID}")
			.set_author(name=target, icon_url=fetchAvatar(target))
		)
	emb = (
		bbEmbed(f"{r['name']}, {r['region']}")
		.set_footer(text=f"Brawl ID {brawlID}")
		.set_author(name=target, icon_url=fetchAvatar(target))
	)
	if "games" in r and r["games"] != 0:
		winRate = brawlWinRate(r)
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
				emb.set_thumbnail(
					url=thumbBase.format(*rankedThumbnails[key])
				)
				break
	if "2v2" in r and len(r["2v2"]) != 0:
		twosTeam = None
		for team in r["2v2"]:
			# Find highest-Elo 2s pairing:
			if not twosTeam or twosTeam["rating"] < team["rating"]:
				twosTeam = team
		if twosTeam:
			emb.add_field(
				name="Ranked 2s",
				value=(
					f"**{twosTeam['teamname']}\n"
					f"{twosTeam['tier']}** ({twosTeam['rating']} /"
					f" {twosTeam['peak_rating']} Peak)\n{twosTeam['wins']}"
					f" W / {twosTeam['games'] - twosTeam['wins']} L /"
					f" {brawlWinRate(twosTeam)}% winrate"
				)
			)
			if emb.color.value == 0xFFF994 or twosTeam["rating"] > r["rating"]:
				for key, value in rankColors.items():
					if key in twosTeam["tier"]:
						emb.color = value
						emb.set_thumbnail(
							url=thumbBase.format(*rankedThumbnails[key])
						)
						break
	return emb


def getStats(target: nextcord.Member, brawlKey: str) -> nextcord.Embed:

	def getTopDPS(legend: Dict[str, Any]) -> Tuple[str, float]:
		dps = round(int(legend["damagedealt"]) / legend["matchtime"], 1)
		return (legend["legend_name_key"].title(), dps)

	def getTopTTK(legend: Dict[str, Any]) -> Tuple[str, float]:
		ttk = round(legend["matchtime"] / legend["kos"], 1)
		return (legend["legend_name_key"].title(), ttk)

	if not (brawlID := fetchBrawlID(target.id)):
		return bbEmbed(
			"Beardless Bot Brawlhalla Stats", unclaimed.format(target.mention)
		)
	if len(r := apiCall("player/", str(brawlID) + "/stats", brawlKey)) < 4:
		noStats = (
			"This profile doesn't have stats associated with it."
			" Please make sure you've claimed the correct profile."
		)
		return bbEmbed("Beardless Bot Brawlhalla Stats", noStats)
	embVal = (
		f"{r['wins']} Wins / {r['games'] - r['wins']} Losses"
		f"\n{r['games']} Games\n{brawlWinRate(r)}% Winrate"
	)
	emb = (
		bbEmbed("Brawlhalla Stats for " + r["name"])
		.set_footer(text=f"Brawl ID {brawlID}")
		.add_field(name="Name", value=r["name"])
		.add_field(name="Overall W/L", value=embVal)
		.set_author(name=target, icon_url=fetchAvatar(target))
	)
	if "legends" in r:
		topUsed = topWinrate = topDPS = topTTK = None
		for legend in r["legends"]:
			if not topUsed or topUsed[1] < legend["xp"]:
				topUsed = (legend["legend_name_key"].title(), legend["xp"])
			if legend["games"] and (
				topWinrate is None or topWinrate[1] < brawlWinRate(legend)
			):
				topWinrate = (
					legend["legend_name_key"].title(), brawlWinRate(legend)
				)
			if legend["matchtime"] and (
				topDPS is None or topDPS[1] < getTopDPS(legend)[1]
			):
				topDPS = getTopDPS(legend)
			if legend["kos"] and (
				topTTK is None or topTTK[1] > getTopTTK(legend)[1]
			):
				topTTK = getTopTTK(legend)
		if all((topUsed, topWinrate, topDPS, topTTK)):
			emb.add_field(
				name="Legend Stats (20 game min)",
				value=(
					f"**Most Played:** {topUsed[0]}\n**Highest Winrate:"
					f"** {topWinrate[0]}, {topWinrate[1]}%\n**Highest Avg"
					f" DPS:** {topDPS[0]}, {topDPS[1]}\n**Shortest Avg TTK:"
					f"** {topTTK[0]}, {topTTK[1]}s"
				)
			)
	if "clan" in r:
		val = f"{r['clan']['clan_name']}\nClan ID {r['clan']['clan_id']}"
		emb.add_field(name="Clan", value=val)
	return emb


def getClan(target: nextcord.Member, brawlKey: str) -> nextcord.Embed:
	if not (brawlID := fetchBrawlID(target.id)):
		return bbEmbed(
			"Beardless Bot Brawlhalla Clan", unclaimed.format(target.mention)
		)
	# Takes two API calls: one to get clan ID from player stats,
	# one to get clan from clan ID. As a result, this command is very slow.
	# TODO: Try to find a way around this.
	r = apiCall("player/", str(brawlID) + "/stats", brawlKey)
	if "clan" not in r:
		return bbEmbed(
			"Beardless Bot Brawlhalla Clan", "You are not in a clan!"
		)
	r = apiCall("clan/", str(r["clan"]["clan_id"]) + "/", brawlKey)
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
		val = (
			f"{member['rank']} ({member['xp']} xp)\n"
			"Joined " + str(datetime.fromtimestamp(member["join_date"]))[:-9]
		)
		emb.add_field(name=member["name"], value=val)
	return emb


def brawlCommands() -> nextcord.Embed:
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
