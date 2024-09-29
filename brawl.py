"""Beardless Bot Brawlhalla methods"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import httpx
import requests
from bs4 import BeautifulSoup
from nextcord import Colour, Embed, Member, User
from steam.steamid import SteamID  # type: ignore[import-untyped]

from misc import BbColor, TimeZone, bbEmbed, fetchAvatar

BadClaim = (
	"Please do !brawlclaim followed by the URL of your steam profile."
	"\nExample: !brawlclaim https://steamcommunity.com/id/beardless"
	"\nAlternatively, you can claim via your Brawlhalla ID, which"
	" you can find in the top right corner of your inventory.\n"
	"Example: !brawlclaim 7032472."
)

BadRegion = (
	"Please specify a valid region, {}! Valid regions are US-E, US-W, EU,"
	" AUS, SEA, BRZ, JPN, MEA, SAF. If you need help, try doing !pins."
)

RequestLimit = (
	"I've reached the request limit for the Brawlhalla API"
	" or run into an unforeseen error."
	" Please wait 15 minutes and try again later."
)

UnclaimedMsg = "{} needs to claim their profile first! " + BadClaim

ThumbBase = (
	"https://static.wikia.nocookie.net/brawlhalla_gamepedia/images/"
	"{}/Banner_Rank_{}.png/revision/latest/scale-to-width-down/{}"
)

RankedThumbnails = [
	("4/46", "Diamond", "84?cb=20161110140154"),
	("6/6e", "Platinum", "102?cb=20161110140140"),
	("6/69", "Gold", "109?cb=20161110140126"),
	("5/5c", "Silver", "119?cb=20161110140055"),
	("a/a6", "Bronze", "112?cb=20161110140114"),
	("e/e1", "Tin", "112?cb=20161110140036")
]

RankColors = {
	"Diamond": 0x3D2399,
	"Platinum": 0x0051B4,
	"Gold": 0xF8D06A,
	"Silver": 0xBBBBBB,
	"Bronze": 0x674B25,
	"Tin": 0x355536
}

Regions = (
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


def getBrawlData() -> dict[
	str, dict[str, list[dict[str, str | dict[str, str]]]]
]:
	# TODO: unit test
	r = requests.get("https://brawlhalla.com/legends", timeout=10)
	soup = BeautifulSoup(r.content.decode("utf-8"), "html.parser")
	brawlDict = json.loads(
		json.loads(soup.findAll("script")[3].contents[0])["body"]
	)["data"]
	assert isinstance(brawlDict, dict)
	return brawlDict


Data = getBrawlData()


def brawlWinRate(j: dict[str, int]) -> float:
	return round(j["wins"] / j["games"] * 100, 1)


def pingMsg(target: str, h: int, m: int, s: int) -> str:
	def plural(t: int) -> str:
		return "" if t == 1 else "s"

	return (
		"This region has been pinged too recently! Regions can only be pinged"
		f" once every two hours, {target}. You can ping again in {h}"
		f" hour{plural(h)}, {m} minute{plural(m)}, and {s} second{plural(s)}."
	)


async def randomBrawl(ranType: str, brawlKey: str | None = None) -> Embed:
	if ranType == "legend":
		legends = tuple(
			legend["legend_name_key"].title() for legend in fetchLegends()
		)
		if brawlKey:
			emb = await legendInfo(brawlKey, random.choice(legends).lower())
			assert isinstance(emb, Embed)
			return emb
		return bbEmbed(
			"Random Legend", f"Your legend is {random.choice(legends)}."
		)
	if ranType == "weapon":
		weapon = random.choice([i["name"] for i in Data["weapons"]["nodes"]])
		assert isinstance(weapon, str)
		return bbEmbed(
			"Random Weapon", f"Your weapon is {weapon}."
		).set_thumbnail(getWeaponPicture(weapon))
	return bbEmbed(
		"Brawlhalla Randomizer", "Please do !random legend or !random weapon."
	)


def claimProfile(discordId: int, brawlId: int) -> None:
	with Path("resources/claimedProfs.json").open() as f:
		profs = json.load(f)
	profs[str(discordId)] = brawlId
	with Path("resources/claimedProfs.json").open("w") as g:
		json.dump(profs, g, indent=4)


def fetchBrawlId(discordId: int) -> int | None:
	with Path("resources/claimedProfs.json").open() as f:
		for key, value in json.load(f).items():
			if key == str(discordId):
				assert isinstance(value, int)
				return value
	return None


def fetchLegends() -> list[dict[str, str]]:
	with Path("resources/legends.json").open() as f:
		legends = json.load(f)
	assert isinstance(legends, list)
	return legends


async def brawlApiCall(
	route: str, arg: str, brawlKey: str, amp: str = "?"
) -> dict[str, Any] | list[dict[str, str | int]] | None:
	url = f"https://api.brawlhalla.com/{route}{arg}{amp}api_key={brawlKey}"
	async with httpx.AsyncClient(timeout=10) as client:
		r = await client.get(url)
	j = r.json()
	if len(j) == 0:
		return None
	assert isinstance(j, dict | list)
	return j


async def getBrawlId(brawlKey: str, profileUrl: str) -> int | None:
	if (
		not isinstance(profileUrl, str)
		or not (steamId := SteamID.from_url(profileUrl))
	):
		return None
	response = await brawlApiCall("search?steamid=", steamId, brawlKey, "&")
	if not isinstance(response, dict):
		return None
	brawlId = response["brawlhalla_id"]
	assert isinstance(brawlId, int)
	return brawlId


async def getLegends(brawlKey: str) -> None:
	# run whenever a new legend is released
	async with aiofiles.open("resources/legends.json", "w") as f:
		j = await brawlApiCall("legend/", "all/", brawlKey)
		assert isinstance(j, list)
		await f.write(json.dumps(j, indent=4))


def getLegendPicture(legendName: str) -> str:
	# TODO: unit test
	if legendName == "redraptor":
		legendName = "red-raptor"
	legend = [i for i in Data["legends"]["nodes"] if i["slug"] == legendName]
	assert isinstance(legend[0]["legendFields"], dict)
	icon = legend[0]["legendFields"]["icon"]
	assert isinstance(icon, dict)
	return icon["sourceUrl"]


def getWeaponPicture(weaponName: str) -> str:
	# TODO: unit test
	weapon = [i for i in Data["weapons"]["nodes"] if i["name"] == weaponName]
	assert isinstance(weapon[0]["weaponFields"], dict)
	icon = weapon[0]["weaponFields"]["icon"]
	assert isinstance(icon, dict)
	return icon["sourceUrl"]


async def legendInfo(brawlKey: str, legendName: str) -> Embed | None:
	if legendName == "hugin":
		legendName = "munin"
	for legend in fetchLegends():
		assert isinstance(legend["legend_name_key"], str)
		if legendName in legend["legend_name_key"]:
			r = await brawlApiCall(
				"legend/", str(legend["legend_id"]) + "/", brawlKey
			)
			assert isinstance(r, dict)

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
			emb = (
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
						f"{r["strength"]} Str, {r["dexterity"]} Dex,"
						f" {r["defense"]} Def, {r["speed"]} Spd"
					)
				)
			)
			return emb.set_thumbnail(
				url=getLegendPicture(r["legend_name_key"].replace(" ", "-"))
			)
	return None


def getTopLegend(
	legends: list[dict[str, str | int]]
) -> tuple[str, int] | None:
	# TODO: unit test
	topLegend = None
	for legend in legends:
		if not topLegend or topLegend[1] < legend["rating"]:
			assert isinstance(legend["legend_name_key"], str)
			assert isinstance(legend["rating"], int)
			topLegend = legend["legend_name_key"], legend["rating"]
	return topLegend


async def getRank(target: Member | User, brawlKey: str) -> Embed:
	if not (brawlId := fetchBrawlId(target.id)):
		return bbEmbed(
			"Beardless Bot Brawlhalla Rank",
			UnclaimedMsg.format(target.mention)
		)
	r = await brawlApiCall("player/", str(brawlId) + "/ranked", brawlKey)
	assert isinstance(r, dict)
	if len(r) < 4 or (
		("games" in r and r["games"] == 0)
		and ("2v2" in r and len(r["2v2"]) == 0)
	):
		return bbEmbed(
			"Beardless Bot Brawlhalla Rank",
			"You haven't played ranked yet this season."
		).set_footer(text=f"Brawl ID {brawlId}").set_author(
			name=target, icon_url=fetchAvatar(target)
		)
	emb = bbEmbed(f"{r["name"]}, {r["region"]}").set_footer(
		text=f"Brawl ID {brawlId}"
	).set_author(name=target, icon_url=fetchAvatar(target))
	if "games" in r and r["games"] != 0:
		winRate = brawlWinRate(r)
		embVal = (
			f"**{r["tier"]}** ({r["rating"]}/{r["peak_rating"]} Peak)\n"
			f"{r["wins"]} W / {r["games"] - r["wins"]} L / {winRate}% winrate"
		)
		if (topLegend := getTopLegend(r["legends"])) is not None:
			embVal += (
				f"\nTop Legend: {topLegend[0].title()}, {topLegend[1]} Elo"
			)
		emb.add_field(name="Ranked 1s", value=embVal)
		for thumb in RankedThumbnails:
			if thumb[1] in r["tier"]:
				emb.colour = Colour(RankColors[thumb[1]])
				emb.set_thumbnail(ThumbBase.format(*thumb))
				break
	if "2v2" in r and len(r["2v2"]) != 0:
		twosTeam = None
		for team in r["2v2"]:
			# Find highest-Elo 2s pairing
			if not twosTeam or twosTeam["rating"] < team["rating"]:
				twosTeam = team
		if twosTeam:
			emb.add_field(
				name="Ranked 2s",
				value=(
					f"**{twosTeam["teamname"]}\n"
					f"{twosTeam["tier"]}** ({twosTeam["rating"]} /"
					f" {twosTeam["peak_rating"]} Peak)\n{twosTeam["wins"]}"
					f" W / {twosTeam["games"] - twosTeam["wins"]} L /"
					f" {brawlWinRate(twosTeam)}% winrate"
				)
			)
			if (
				(emb.colour and emb.colour.value == BbColor)
				or twosTeam["rating"] > r["rating"]
			):
				# Higher 2s Elo than 1s Elo
				for thumb in RankedThumbnails:
					if thumb[1] in twosTeam["tier"]:
						emb.colour = Colour(RankColors[thumb[1]])
						emb.set_thumbnail(ThumbBase.format(*thumb))
						break
	return emb


def getTopDps(legend: dict[str, str | int]) -> tuple[str, float]:
	# TODO: unit test
	assert isinstance(legend["matchtime"], int)
	assert isinstance(legend["legend_name_key"], str)
	return (
		legend["legend_name_key"].title(),
		round(int(legend["damagedealt"]) / legend["matchtime"], 1)
	)


def getTopTtk(legend: dict[str, str | int]) -> tuple[str, float]:
	# TODO: unit test
	assert isinstance(legend["kos"], int)
	assert isinstance(legend["matchtime"], int)
	assert isinstance(legend["legend_name_key"], str)
	return (
		legend["legend_name_key"].title(),
		round(legend["matchtime"] / legend["kos"], 1)
	)


async def getStats(target: Member | User, brawlKey: str) -> Embed:
	if not (brawlId := fetchBrawlId(target.id)):
		return bbEmbed(
			"Beardless Bot Brawlhalla Stats",
			UnclaimedMsg.format(target.mention)
		)
	r = await brawlApiCall("player/", str(brawlId) + "/stats", brawlKey)
	if r is None or len(r) < 4:
		noStats = (
			"This profile doesn't have stats associated with it."
			" Please make sure you've claimed the correct profile."
		)
		return bbEmbed("Beardless Bot Brawlhalla Stats", noStats)
	assert isinstance(r, dict)
	winLoss = (
		f"{r["wins"]} Wins / {r["games"] - r["wins"]} Losses"
		f"\n{r["games"]} Games\n{brawlWinRate(r)}% Winrate"
	)
	emb = bbEmbed("Brawlhalla Stats for " + r["name"]).set_footer(
		text=f"Brawl ID {brawlId}"
	).add_field(name="Name", value=r["name"]).add_field(
		name="Overall W/L", value=winLoss
	).set_author(name=target, icon_url=fetchAvatar(target))
	if "legends" in r:
		mostUsed: tuple[str, int] | None = None
		topWinrate: tuple[str, float] | None = None
		topDps: tuple[str, float] | None = None
		lowestTtk: tuple[str, float] | None = None
		for legend in r["legends"]:
			if not mostUsed or mostUsed[1] < legend["xp"]:
				mostUsed = (legend["legend_name_key"].title(), legend["xp"])
			if legend["games"] and (
				topWinrate is None or topWinrate[1] < brawlWinRate(legend)
			):
				topWinrate = (
					legend["legend_name_key"].title(), brawlWinRate(legend)
				)
			if legend["matchtime"] and (
				topDps is None or topDps[1] < getTopDps(legend)[1]
			):
				topDps = getTopDps(legend)
			if legend["kos"] and (
				lowestTtk is None or lowestTtk[1] > getTopTtk(legend)[1]
			):
				lowestTtk = getTopTtk(legend)
		if all((mostUsed, topWinrate, topDps, lowestTtk)):
			assert isinstance(mostUsed, tuple)
			assert isinstance(topWinrate, tuple)
			assert isinstance(topDps, tuple)
			assert isinstance(lowestTtk, tuple)
			emb.add_field(
				name="Legend Stats (20 game min)",
				value=(
					f"**Most Played:** {mostUsed[0]}\n**Highest Winrate:"
					f"** {topWinrate[0]}, {topWinrate[1]}%\n**Highest Avg"
					f" DPS:** {topDps[0]}, {topDps[1]}\n**Shortest Avg TTK:"
					f"** {lowestTtk[0]}, {lowestTtk[1]}s"
				)
			)
	if "clan" in r:
		val = r["clan"]["clan_name"] + "\nClan ID " + str(r["clan"]["clan_id"])
		emb.add_field(name="Clan", value=val)
	return emb


async def getClan(target: Member | User, brawlKey: str) -> Embed:
	if not (brawlId := fetchBrawlId(target.id)):
		return bbEmbed(
			"Beardless Bot Brawlhalla Clan",
			UnclaimedMsg.format(target.mention)
		)
	# Takes two API calls: one to get clan ID from player stats,
	# one to get clan from clan ID. As a result, this command is very slow.
	# TODO: Try to find a way around this.
	# https://github.com/LevBernstein/BeardlessBot/issues/14
	r = await brawlApiCall("player/", str(brawlId) + "/stats", brawlKey)
	assert isinstance(r, dict)
	if "clan" not in r:
		return bbEmbed(
			"Beardless Bot Brawlhalla Clan", "You are not in a clan!"
		)
	r = await brawlApiCall("clan/", str(r["clan"]["clan_id"]) + "/", brawlKey)
	assert isinstance(r, dict)
	emb = bbEmbed(
		r["clan_name"],
		"**Clan Created:** {}\n**Experience:** {}\n**Members:** {}".format(
			str(datetime.fromtimestamp(r["clan_create_date"], TimeZone))[:-9],
			r["clan_xp"],
			len(r["clan"])
		)
	).set_footer(text=f"Clan ID {r["clan_id"]}")
	for i in range(min(len(r["clan"]), 9)):
		member = r["clan"][i]
		val = (
			f"{member["rank"]} ({member["xp"]} xp)\nJoined "
			+ str(datetime.fromtimestamp(member["join_date"], TimeZone))[:-9]
		)
		emb.add_field(name=member["name"], value=val)
	return emb


def brawlCommands() -> Embed:
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


# TODO: implement leaderboard, glory
# https://github.com/LevBernstein/BeardlessBot/issues/15
# https://github.com/LevBernstein/BeardlessBot/issues/17
# See: https://github.com/BrawlDB/gerard3/blob/master/src/utils/glory.js
