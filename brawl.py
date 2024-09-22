"""Beardless Bot Brawlhalla methods"""

from datetime import datetime
from json import dump, dumps, load, loads
from pathlib import Path
from random import choice
from typing import Any

import aiofiles
import httpx
import requests
from bs4 import BeautifulSoup
from nextcord import Colour, Embed, Member
from steam.steamid import SteamID  # type: ignore[import-untyped]

from misc import BbColor, bbEmbed, fetchAvatar

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
	brawlDict = loads(
		loads(soup.findAll("script")[3].contents[0])["body"]
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


async def randomBrawl(ranType: str, key: str | None = None) -> Embed:
	if ranType in {"legend", "weapon"}:
		if ranType == "legend":
			legends = tuple(
				legend["legend_name_key"].title() for legend in fetchLegends()
			)
			if key:
				emb = await legendInfo(key, choice(legends).lower())
				assert isinstance(emb, Embed)
				return emb
			return bbEmbed(
				"Random Legend", f"Your legend is {choice(legends)}."
			)
		weapon = choice([i["name"] for i in Data["weapons"]["nodes"]])
		assert isinstance(weapon, str)
		return bbEmbed(
			"Random Weapon", f"Your weapon is {weapon}."
		).set_thumbnail(getWeaponPicture(weapon))
	return bbEmbed(
		"Brawlhalla Randomizer", "Please do !random legend or !random weapon."
	)


def claimProfile(discordId: int, brawlId: int) -> None:
	with Path("resources/claimedProfs.json").open() as f:
		profs = load(f)
	profs[str(discordId)] = brawlId
	with Path("resources/claimedProfs.json").open("w") as g:
		dump(profs, g, indent=4)


def fetchBrawlId(discordId: int) -> int | None:
	with Path("resources/claimedProfs.json").open() as f:
		for key, value in load(f).items():
			if key == str(discordId):
				assert isinstance(value, int)
				return value
	return None


def fetchLegends() -> list[dict[str, str]]:
	with Path("resources/legends.json").open() as f:
		legends = load(f)
	assert isinstance(legends, list)
	return legends


async def brawlApiCall(
	route: str, arg: str, key: str, amp: str = "?"
) -> dict[str, Any] | list[dict[str, str | int]] | None:
	url = f"https://api.brawlhalla.com/{route}{arg}{amp}api_key={key}"
	async with httpx.AsyncClient() as client:
		r = await client.get(url, timeout=10)
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
		await f.write(dumps(j, indent=4))


def getLegendPicture(legendName: str) -> str:
	# TODO: unit test
	if legendName == "redraptor":
		legendName = "red-raptor"
	legend = [i for i in Data["legends"]["nodes"] if i["slug"] == legendName]
	icon = legend[0]["legendFields"]["icon"]  # type: ignore[index]
	assert isinstance(icon, dict)
	return icon["sourceUrl"]


def getWeaponPicture(weaponName: str) -> str:
	# TODO: unit test
	weapon = [i for i in Data["weapons"]["nodes"] if i["name"] == weaponName]
	icon = weapon[0]["weaponFields"]["icon"]  # type: ignore[index]
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
						f"{r['strength']} Str, {r['dexterity']} Dex,"
						f" {r['defense']} Def, {r['speed']} Spd"
					)
				)
			)
			return emb.set_thumbnail(
				url=getLegendPicture(r["legend_name_key"].replace(" ", "-"))
			)
	return None


async def getRank(target: Member, brawlKey: str) -> Embed:
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
	emb = bbEmbed(f"{r['name']}, {r['region']}").set_footer(
		text=f"Brawl ID {brawlId}"
	).set_author(name=target, icon_url=fetchAvatar(target))
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
		for thumb in RankedThumbnails:
			if thumb[1] in r["tier"]:
				emb.colour = Colour(RankColors[thumb[1]])
				emb.set_thumbnail(ThumbBase.format(*thumb))
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
			if (
				(emb.colour and emb.colour.value == BbColor)
				or twosTeam["rating"] > r["rating"]
			):
				for thumb in RankedThumbnails:
					if thumb[1] in twosTeam["tier"]:
						emb.colour = Colour(RankColors[thumb[1]])
						emb.set_thumbnail(ThumbBase.format(*thumb))
						break
	return emb


async def getStats(target: Member, brawlKey: str) -> Embed:

	def getTopDps(legend: dict[str, Any]) -> tuple[str, float]:
		dps = round(int(legend["damagedealt"]) / legend["matchtime"], 1)
		return (legend["legend_name_key"].title(), dps)

	def getTopTtk(legend: dict[str, Any]) -> tuple[str, float]:
		ttk = round(legend["matchtime"] / legend["kos"], 1)
		return (legend["legend_name_key"].title(), ttk)

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
		f"{r['wins']} Wins / {r['games'] - r['wins']} Losses"
		f"\n{r['games']} Games\n{brawlWinRate(r)}% Winrate"
	)
	emb = bbEmbed("Brawlhalla Stats for " + r["name"]).set_footer(
		text=f"Brawl ID {brawlId}"
	).add_field(name="Name", value=r["name"]).add_field(
		name="Overall W/L", value=winLoss
	).set_author(name=target, icon_url=fetchAvatar(target))
	if "legends" in r:
		topUsed = topWinrate = topDps = topTtk = None
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
				topDps is None or topDps[1] < getTopDps(legend)[1]
			):
				topDps = getTopDps(legend)
			if legend["kos"] and (
				topTtk is None or topTtk[1] > getTopTtk(legend)[1]
			):
				topTtk = getTopTtk(legend)
		if all((topUsed, topWinrate, topDps, topTtk)):
			assert isinstance(topUsed, tuple)
			assert isinstance(topWinrate, tuple)
			assert isinstance(topDps, tuple)
			assert isinstance(topTtk, tuple)
			emb.add_field(
				name="Legend Stats (20 game min)",
				value=(
					f"**Most Played:** {topUsed[0]}\n**Highest Winrate:"
					f"** {topWinrate[0]}, {topWinrate[1]}%\n**Highest Avg"
					f" DPS:** {topDps[0]}, {topDps[1]}\n**Shortest Avg TTK:"
					f"** {topTtk[0]}, {topTtk[1]}s"
				)
			)
	if "clan" in r:
		val = r["clan"]["clan_name"] + "\nClan ID " + str(r["clan"]["clan_id"])
		emb.add_field(name="Clan", value=val)
	return emb


async def getClan(target: Member, brawlKey: str) -> Embed:
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
			str(datetime.fromtimestamp(r["clan_create_date"]))[:-9],
			r["clan_xp"],
			len(r["clan"])
		)
	).set_footer(text=f"Clan ID {r['clan_id']}")
	for i in range(min(len(r["clan"]), 9)):
		member = r["clan"][i]
		val = (
			f"{member['rank']} ({member['xp']} xp)\nJoined "
			+ str(datetime.fromtimestamp(member["join_date"]))[:-9]
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
