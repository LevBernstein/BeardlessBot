"""Beardless Bot Brawlhalla methods."""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import httpx
from bs4 import BeautifulSoup
from nextcord import Colour, Embed, Member, User
from steam import steamid  # type:ignore[import-untyped]

from misc import BbColor, Ok, TimeZone, bb_embed, fetch_avatar

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
	("e/e1", "Tin", "112?cb=20161110140036"),
]

RankColors = {
	"Diamond": 0x3D2399,
	"Platinum": 0x0051B4,
	"Gold": 0xF8D06A,
	"Silver": 0xBBBBBB,
	"Bronze": 0x674B25,
	"Tin": 0x355536,
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
	"saf",
)


def get_brawl_data() -> dict[
	str, dict[str, list[dict[str, str | dict[str, str | dict[str, str]]]]],
]:
	r = httpx.get("https://www.brawlhalla.com/legends", timeout=10)
	soup = BeautifulSoup(r.content.decode("utf-8"), "html.parser")
	brawl_dict = json.loads(
		json.loads(soup.find_all("script")[3].contents[0])["body"],
	)["data"]
	assert isinstance(brawl_dict, dict)
	return brawl_dict


Data = get_brawl_data()


def brawl_win_rate(j: dict[str, str | int]) -> float:
	assert isinstance(j["wins"], int)
	assert isinstance(j["games"], int)
	return round(j["wins"] / j["games"] * 100, 1)


def ping_msg(target: str, h: int, m: int, s: int) -> str:
	def plural(t: int) -> str:
		return "" if t == 1 else "s"

	return (
		"This region has been pinged too recently! Regions can only be pinged"
		f" once every two hours, {target}. You can ping again in {h}"
		f" hour{plural(h)}, {m} minute{plural(m)}, and {s} second{plural(s)}."
	)


async def random_brawl(ran_type: str, brawl_key: str | None = None) -> Embed:
	if ran_type == "legend":
		legends = tuple(
			legend["legend_name_key"].title() for legend in fetch_legends()
		)
		if brawl_key:
			emb = await legend_info(brawl_key, random.choice(legends).lower())
			assert isinstance(emb, Embed)
			return emb
		return bb_embed(
			"Random Legend", f"Your legend is {random.choice(legends)}.",
		)
	if ran_type == "weapon":
		weapon = random.choice([i["name"] for i in Data["weapons"]["nodes"]])
		assert isinstance(weapon, str)
		return bb_embed(
			"Random Weapon", f"Your weapon is {weapon}.",
		).set_thumbnail(get_weapon_picture(weapon))
	return bb_embed(
		"Brawlhalla Randomizer", "Please do !random legend or !random weapon.",
	)


def claim_profile(user_id: int, brawl_id: int) -> None:
	with Path("resources/claimedProfs.json").open("r", encoding="UTF-8") as f:
		profs = json.load(f)
	profs[str(user_id)] = brawl_id
	with Path("resources/claimedProfs.json").open("w", encoding="UTF-8") as g:
		json.dump(profs, g, indent=4)


def fetch_brawl_id(user_id: int) -> int | None:
	with Path("resources/claimedProfs.json").open("r", encoding="UTF-8") as f:
		for key, value in json.load(f).items():
			if key == str(user_id):
				assert isinstance(value, int)
				return value
	return None


def fetch_legends() -> list[dict[str, str]]:
	with Path("resources/legends.json").open("r", encoding="UTF-8") as f:
		legends = json.load(f)
	assert isinstance(legends, list)
	return legends


async def brawl_api_call(
	route: str, arg: str | int, brawl_key: str, amp: str = "?",
) -> dict[str, Any] | list[dict[str, str | int]]:
	url = f"https://api.brawlhalla.com/{route}{arg}{amp}api_key={brawl_key}"
	async with httpx.AsyncClient(timeout=10) as client:
		r = await client.get(url)
	if r.status_code != Ok:
		raise httpx.RequestError("Request failed with " + str(r.status_code))
	j = r.json()
	assert isinstance(j, dict | list)
	return j


async def get_brawl_id(brawl_key: str, url: str) -> int | None:
	if (
		not isinstance(url, str)
		or not (steam_id := steamid.from_url(url))  # type:ignore[no-untyped-call]
	):
		return None
	response = await brawl_api_call(
		"search?steamid=", steam_id, brawl_key, "&",
	)
	if not isinstance(response, dict):
		return None
	brawl_id = response["brawlhalla_id"]
	assert isinstance(brawl_id, int)
	return brawl_id


async def pull_legends(brawl_key: str) -> None:
	# run whenever a new legend is released
	async with aiofiles.open(
		"resources/legends.json", "w", encoding="UTF-8",
	) as f:
		j = await brawl_api_call("legend/", "all/", brawl_key)
		assert isinstance(j, list)
		await f.write(json.dumps(j, indent=4))


def get_legend_picture(legend_name: str) -> str:
	# TODO: unit test
	# https://github.com/LevBernstein/BeardlessBot/issues/47
	if legend_name == "redraptor":
		legend_name = "red-raptor"
	legend = [i for i in Data["legends"]["nodes"] if i["slug"] == legend_name]
	assert isinstance(legend[0]["legendFields"], dict)
	icon = legend[0]["legendFields"]["icon"]
	assert isinstance(icon, dict)
	return icon["sourceUrl"]


def get_weapon_picture(weapon_name: str) -> str:
	weapon = [i for i in Data["weapons"]["nodes"] if i["name"] == weapon_name]
	assert isinstance(weapon[0]["weaponFields"], dict)
	icon = weapon[0]["weaponFields"]["icon"]
	assert isinstance(icon, dict)
	return icon["sourceUrl"]


async def legend_info(brawl_key: str, legend_name: str) -> Embed | None:
	if legend_name == "hugin":
		legend_name = "munin"
	for legend in fetch_legends():
		assert isinstance(legend["legend_name_key"], str)
		if legend_name in legend["legend_name_key"]:
			r = await brawl_api_call(
				"legend/", str(legend["legend_id"]) + "/", brawl_key,
			)
			assert isinstance(r, dict)

			def clean_quote(quote: str, attrib: str) -> str:
				return "{}  *{}*".format(
					quote, attrib.replace("\"", ""),
				).replace("\\n", " ").replace("* ", "*").replace(" *", "*")

			bio = "\n\n".join((
				r["bio_text"].replace("\n", "\n\n"),
				"**Quotes**",
				clean_quote(r["bio_quote"], r["bio_quote_about_attrib"]),
				clean_quote(r["bio_quote_from"], r["bio_quote_from_attrib"]),
			))
			emb = (
				bb_embed(r["bio_name"] + ", " + r["bio_aka"], bio)
				.add_field(
					name="Weapons",
					value=(r["weapon_one"] + ", " + r["weapon_two"])
					.replace("Fist", "Gauntlet")
					.replace("Pistol", "Blasters"),
				)
				.add_field(
					name="Stats",
					value=(
						f"{r["strength"]} Str, {r["dexterity"]} Dex,"
						f" {r["defense"]} Def, {r["speed"]} Spd"
					),
				)
			)
			return emb.set_thumbnail(
				url=get_legend_picture(r["legend_name_key"].replace(" ", "-")),
			)
	return None


def get_top_legend(
	legends: list[dict[str, str | int]],
) -> tuple[str, int] | None:
	# TODO: unit test
	# https://github.com/LevBernstein/BeardlessBot/issues/47
	top_legend = None
	for legend in legends:
		assert isinstance(legend["rating"], int)
		rating: int = legend["rating"]
		if not top_legend or top_legend[1] < rating:
			assert isinstance(legend["legend_name_key"], str)
			top_legend = legend["legend_name_key"], rating
	return top_legend


def get_ones_rank(emb: Embed, r: dict[str, Any]) -> Embed:
	# TODO: unit test
	# https://github.com/LevBernstein/BeardlessBot/issues/47
	emb_val = (
		f"**{r["tier"]}** ({r["rating"]}/{r["peak_rating"]} Peak)\n{r["wins"]}"
		f" W / {r["games"] - r["wins"]} L / {brawl_win_rate(r)}% winrate"
	)
	if (top_legend := get_top_legend(r["legends"])) is not None:
		emb_val += (
			f"\nTop Legend: {top_legend[0].title()}, {top_legend[1]} Elo"
		)
	emb.add_field(name="Ranked 1s", value=emb_val)
	for thumb in RankedThumbnails:
		if thumb[1] in r["tier"]:
			emb.colour = Colour(RankColors[thumb[1]])
			emb.set_thumbnail(ThumbBase.format(*thumb))
			break
	return emb


def get_twos_rank(emb: Embed, r: dict[str, Any]) -> Embed:
	# TODO: unit test
	# https://github.com/LevBernstein/BeardlessBot/issues/47
	# Should be called after getOnesRank, not before
	peak_team = None
	for team in r["2v2"]:
		# Find highest-Elo 2s pairing
		if not peak_team or peak_team["rating"] < team["rating"]:
			peak_team = team
	if peak_team:
		emb.add_field(
			name="Ranked 2s",
			value=(
				f"**{peak_team["teamname"]}\n"
				f"{peak_team["tier"]}** ({peak_team["rating"]} /"
				f" {peak_team["peak_rating"]} Peak)\n{peak_team["wins"]}"
				f" W / {peak_team["games"] - peak_team["wins"]} L /"
				f" {brawl_win_rate(peak_team)}% winrate"
			),
		)
		if (
			(emb.colour and emb.colour.value == BbColor)
			or peak_team["rating"] > r["rating"]
		):
			# Higher 2s Elo than 1s Elo
			for thumb in RankedThumbnails:
				if thumb[1] in peak_team["tier"]:
					emb.colour = Colour(RankColors[thumb[1]])
					emb.set_thumbnail(ThumbBase.format(*thumb))
					break
	return emb


async def get_rank(target: Member | User, brawl_key: str) -> Embed:
	if not (brawl_id := fetch_brawl_id(target.id)):
		return bb_embed(
			"Beardless Bot Brawlhalla Rank",
			UnclaimedMsg.format(target.mention),
		)
	r = await brawl_api_call("player/", str(brawl_id) + "/ranked", brawl_key)
	assert isinstance(r, dict)
	if not r or (
		("games" in r and r["games"] == 0)
		and ("2v2" in r and len(r["2v2"]) == 0)
	):
		return bb_embed(
			"Beardless Bot Brawlhalla Rank",
			"You haven't played ranked yet this season.",
		).set_footer(text=f"Brawl ID {brawl_id}").set_author(
			name=target.name, icon_url=fetch_avatar(target),
		)
	emb = bb_embed(f"{r["name"]}, {r["region"]}").set_footer(
		text=f"Brawl ID {brawl_id}",
	).set_author(name=target.name, icon_url=fetch_avatar(target))
	if "games" in r and r["games"] != 0:
		emb = get_ones_rank(emb, r)
	if "2v2" in r and len(r["2v2"]) != 0:
		emb = get_twos_rank(emb, r)
	return emb


def get_top_dps(legend: dict[str, str | int]) -> tuple[str, float]:
	# TODO: unit test
	# https://github.com/LevBernstein/BeardlessBot/issues/47
	assert isinstance(legend["matchtime"], int)
	assert isinstance(legend["legend_name_key"], str)
	return (
		legend["legend_name_key"].title(),
		round(int(legend["damagedealt"]) / legend["matchtime"], 1),
	)


def get_top_ttk(legend: dict[str, str | int]) -> tuple[str, float]:
	# TODO: unit test
	# https://github.com/LevBernstein/BeardlessBot/issues/47
	assert isinstance(legend["kos"], int)
	assert isinstance(legend["matchtime"], int)
	assert isinstance(legend["legend_name_key"], str)
	return (
		legend["legend_name_key"].title(),
		round(legend["matchtime"] / legend["kos"], 1),
	)


def get_top_legend_stats(
	legends: list[dict[str, str | int]],
) -> tuple[tuple[str, float | int] | None, ...]:
	# TODO: unit test
	# https://github.com/LevBernstein/BeardlessBot/issues/47
	most_used: tuple[str, int] | None = None
	top_winrate: tuple[str, float] | None = None
	top_dps: tuple[str, float] | None = None
	lowest_ttk: tuple[str, float] | None = None
	for legend in legends:
		assert isinstance(legend["xp"], int)
		assert isinstance(legend["legend_name_key"], str)
		if not most_used or most_used[1] < legend["xp"]:
			most_used = (legend["legend_name_key"].title(), legend["xp"])
		if legend["games"] and (
			top_winrate is None
			or top_winrate[1] < brawl_win_rate(legend)
		):
			top_winrate = (
				legend["legend_name_key"].title(), brawl_win_rate(legend),
			)
		if legend["matchtime"] and (
			top_dps is None or top_dps[1] < get_top_dps(legend)[1]
		):
			top_dps = get_top_dps(legend)
		if legend["kos"] and (
			lowest_ttk is None or lowest_ttk[1] > get_top_ttk(legend)[1]
		):
			lowest_ttk = get_top_ttk(legend)
	return most_used, top_winrate, top_dps, lowest_ttk


async def get_stats(target: Member | User, brawl_key: str) -> Embed:
	if not (brawl_id := fetch_brawl_id(target.id)):
		return bb_embed(
			"Beardless Bot Brawlhalla Stats",
			UnclaimedMsg.format(target.mention),
		)
	if not (r := await brawl_api_call(
		"player/", str(brawl_id) + "/stats", brawl_key,
	)):
		no_stats = (
			"This profile doesn't have stats associated with it."
			" Please make sure you've claimed the correct profile."
		)
		return bb_embed("Beardless Bot Brawlhalla Stats", no_stats)
	assert isinstance(r, dict)
	win_loss = (
		f"{r["wins"]} Wins / {r["games"] - r["wins"]} Losses"
		f"\n{r["games"]} Games\n{brawl_win_rate(r)}% Winrate"
	)
	emb = bb_embed("Brawlhalla Stats for " + r["name"]).set_footer(
		text=f"Brawl ID {brawl_id}",
	).add_field(name="Name", value=r["name"]).add_field(
		name="Overall W/L", value=win_loss,
	).set_author(name=target.name, icon_url=fetch_avatar(target))
	if "legends" in r:
		most_used, top_winrate, top_dps, lowest_ttk = get_top_legend_stats(
			r["legends"],
		)
		if all((most_used, top_winrate, top_dps, lowest_ttk)):
			assert isinstance(most_used, tuple)
			assert isinstance(top_winrate, tuple)
			assert isinstance(top_dps, tuple)
			assert isinstance(lowest_ttk, tuple)
			emb.add_field(
				name="Legend Stats (20 game min)",
				value=(
					f"**Most Played:** {most_used[0]}\n**Highest Winrate:"
					f"** {top_winrate[0]}, {top_winrate[1]}%\n**Highest Avg"
					f" DPS:** {top_dps[0]}, {top_dps[1]}\n**Shortest Avg TTK:"
					f"** {lowest_ttk[0]}, {lowest_ttk[1]}s"
				),
			)
	if "clan" in r:
		val = f"{r["clan"]["clan_name"]}\nClan ID {r["clan"]["clan_id"]}"
		emb.add_field(name="Clan", value=val)
	return emb


async def get_clan(target: Member | User, brawl_key: str) -> Embed:
	if not (brawl_id := fetch_brawl_id(target.id)):
		return bb_embed(
			"Beardless Bot Brawlhalla Clan",
			UnclaimedMsg.format(target.mention),
		)
	# Takes two API calls: one to get clan ID from player stats,
	# one to get clan from clan ID. As a result, this command is very slow.
	# TODO: Try to find a way around this.
	# https://github.com/LevBernstein/BeardlessBot/issues/14
	r = await brawl_api_call("player/", str(brawl_id) + "/stats", brawl_key)
	assert isinstance(r, dict)
	if "clan" not in r:
		return bb_embed(
			"Beardless Bot Brawlhalla Clan", "You are not in a clan!",
		)
	r = await brawl_api_call(
		"clan/", str(r["clan"]["clan_id"]) + "/", brawl_key,
	)
	assert isinstance(r, dict)
	emb = bb_embed(
		r["clan_name"],
		"**Clan Created:** {}\n**Experience:** {}\n**Members:** {}".format(
			str(datetime.fromtimestamp(r["clan_create_date"], TimeZone))[:-9],
			r["clan_xp"],
			len(r["clan"]),
		),
	).set_footer(text=f"Clan ID {r["clan_id"]}")
	for i in range(min(len(r["clan"]), 9)):
		member = r["clan"][i]
		val = (
			f"{member["rank"]} ({member["xp"]} xp)\nJoined "
			+ str(datetime.fromtimestamp(member["join_date"], TimeZone))[:-9]
		)
		emb.add_field(name=member["name"], value=val)
	return emb


def brawl_commands() -> Embed:
	emb = bb_embed("Beardless Bot Brawlhalla Commands")
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
		),
	)
	for command, description in comms:
		emb.add_field(name=command, value=description)
	return emb


# TODO: implement leaderboard, glory
# https://github.com/LevBernstein/BeardlessBot/issues/15
# https://github.com/LevBernstein/BeardlessBot/issues/17
# See: https://github.com/BrawlDB/gerard3/blob/master/src/utils/glory.js
