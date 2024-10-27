"""Beadless Bot event logging methods."""

from collections.abc import Sequence
from typing import Final

import nextcord

from misc import ProfUrl, bbEmbed, contCheck, fetchAvatar, truncTime

# TODO: Implement log thread locked/unlocked
# https://github.com/LevBernstein/BeardlessBot/issues/45

MaxPurgedMsgs: Final[int] = 99


def logDeleteMsg(message: nextcord.Message) -> nextcord.Embed:
	assert hasattr(message.channel, "mention")
	prefix = (
		f"**Deleted message sent by {message.author.mention} in "
		f"**{message.channel.mention}\n"
	)
	return bbEmbed(
		value=f"{prefix}{contCheck(message, len(prefix))}",
		col=0xFF0000,
		showTime=True,
	).set_author(name=message.author, icon_url=fetchAvatar(message.author))


def logPurge(
	msg: nextcord.Message, messages: Sequence[nextcord.Message],
) -> nextcord.Embed:

	def purgeReport(msgList: Sequence[nextcord.Message]) -> str:
		return (
			f"{MaxPurgedMsgs}+"
			if len(msgList) > MaxPurgedMsgs
			else str(len(msgList) - 1)
		)

	assert hasattr(msg.channel, "mention")
	return bbEmbed(
		"",
		f"Purged {purgeReport(messages)} messages in {msg.channel.mention}.",
		0xFF0000,
		showTime=True,
	).set_author(name="Purge!", icon_url=ProfUrl)


def logEditMsg(
	before: nextcord.Message, after: nextcord.Message,
) -> nextcord.Embed:
	assert hasattr(before.channel, "mention")
	addendum = f"\n[Jump to Message]({after.jump_url})"
	return bbEmbed(
		"",
		f"Messaged edited by {before.author.mention}"
		f" in {before.channel.mention}.",
		0xFFFF00,
		showTime=True,
	).set_author(
		name=before.author, icon_url=fetchAvatar(before.author),
	).add_field(
		name="Before:", value=contCheck(before, 7), inline=False,
	).add_field(
		name="After:",
		value=f"{contCheck(after, len(addendum))}{addendum}",
		inline=False,
	)


def logClearReacts(
	message: nextcord.Message, reactions: list[nextcord.Reaction],
) -> nextcord.Embed:
	assert hasattr(message.channel, "mention")
	jumpLink = f"\n[Jump to Message]({message.jump_url})"
	return bbEmbed(
		"",
		f"Reactions cleared from message sent by {message.author.mention}"
		f" in {message.channel.mention}.",
		0xFF0000,
		showTime=True,
	).set_author(
		name=message.author, icon_url=fetchAvatar(message.author),
	).add_field(
		name="Message content:",
		value=contCheck(message, len(jumpLink)) + jumpLink,
	).add_field(
		name="Reactions:", value=", ".join(str(r) for r in reactions),
	)


def logDeleteChannel(channel: nextcord.abc.GuildChannel) -> nextcord.Embed:
	return bbEmbed(
		"", f"Channel \"{channel.name}\" deleted.", 0xFF0000, showTime=True,
	).set_author(name="Channel deleted", icon_url=ProfUrl)


def logCreateChannel(channel: nextcord.abc.GuildChannel) -> nextcord.Embed:
	return bbEmbed(
		"", f"Channel \"{channel.name}\" created.", 0x00FF00, showTime=True,
	).set_author(name="Channel created", icon_url=ProfUrl)


def logMemberJoin(member: nextcord.Member) -> nextcord.Embed:
	return bbEmbed(
		"",
		f"Member {member.mention} joined\nAccount registered"
		f" on {truncTime(member)}\nID: {member.id}",
		0x0000FF,
		showTime=True,
	).set_author(
		name=f"{member} joined the server", icon_url=fetchAvatar(member),
	)


def logMemberRemove(member: nextcord.Member) -> nextcord.Embed:
	emb = bbEmbed(
		value=f"Member {member.mention} left\nID: {member.id}",
		col=0xFF0000,
		showTime=True,
	).set_author(
		name=f"{member} left the server", icon_url=fetchAvatar(member),
	)
	if len(member.roles) > 1:
		emb.add_field(
			name="Roles:",
			value=", ".join(role.mention for role in member.roles[:0:-1]),
		)
	return emb


def logMemberNickChange(
	before: nextcord.Member, after: nextcord.Member,
) -> nextcord.Embed:
	return bbEmbed(
		"", f"Nickname of {after.mention} changed.", 0xFFFF00, showTime=True,
	).set_author(
		name=after, icon_url=fetchAvatar(after),
	).add_field(
		name="Before:", value=before.nick, inline=False,
	).add_field(name="After:", value=after.nick, inline=False)


def logMemberRolesChange(
	before: nextcord.Member, after: nextcord.Member,
) -> nextcord.Embed:
	verb, color = (
		("removed from", 0xFF0000)
		if len(before.roles) > len(after.roles)
		else ("added to", 0x00FF00)
	)
	role = set(after.roles).symmetric_difference(set(before.roles)).pop()
	return bbEmbed(
		value=f"Role {role.mention} {verb} {after.mention}.",
		col=color,
		showTime=True,
	).set_author(name=after, icon_url=fetchAvatar(after))


def logBan(member: nextcord.Member) -> nextcord.Embed:
	return bbEmbed(
		value=f"Member {member.mention} banned\n{member.name}",
		col=0xFF0000,
		showTime=True,
	).set_author(
		name="Member banned", icon_url=fetchAvatar(member),
	).set_thumbnail(url=fetchAvatar(member))


def logUnban(member: nextcord.Member) -> nextcord.Embed:
	return bbEmbed(
		value=f"Member {member.mention} unbanned\n{member.name}",
		col=0x00FF00,
		showTime=True,
	).set_author(
		name="Member unbanned", icon_url=fetchAvatar(member),
	).set_thumbnail(url=fetchAvatar(member))


def logMute(
	member: nextcord.Member, message: nextcord.Message, duration: str | None,
) -> nextcord.Embed:
	assert hasattr(message.channel, "mention")
	mid = f" for {duration}" if duration else ""
	return bbEmbed(
		"Beardless Bot Mute",
		f"Muted {member.mention}{mid} in {message.channel.mention}.",
		0xFF0000,
		showTime=True,
	).set_author(name=message.author, icon_url=fetchAvatar(message.author))


def logUnmute(
	member: nextcord.Member, author: nextcord.Member,
) -> nextcord.Embed:
	return bbEmbed(
		"Beardless Bot Mute",
		f"Unmuted {member.mention}.",
		0x00FF00,
		showTime=True,
	).set_author(name=author, icon_url=fetchAvatar(author))


def logCreateThread(thread: nextcord.Thread) -> nextcord.Embed:
	assert isinstance(thread.parent, nextcord.abc.GuildChannel)
	return bbEmbed(
		"",
		f"Thread \"{thread.name}\" created in"
		f" parent channel {thread.parent.mention}.",
		0x00FF00,
		showTime=True,
	).set_author(name="Thread created", icon_url=ProfUrl)


def logDeleteThread(thread: nextcord.Thread) -> nextcord.Embed:
	return bbEmbed(
		"", f"Thread \"{thread.name}\" deleted.", 0xFF0000, showTime=True,
	).set_author(name="Thread deleted", icon_url=ProfUrl)


def logThreadArchived(thread: nextcord.Thread) -> nextcord.Embed:
	return bbEmbed(
		"", f"Thread \"{thread.name}\" archived.", 0xFFFF00, showTime=True,
	).set_author(name="Thread archived", icon_url=ProfUrl)


def logThreadUnarchived(thread: nextcord.Thread) -> nextcord.Embed:
	return bbEmbed(
		"", f"Thread \"{thread.name}\" unarchived.", 0xFFFF00, showTime=True,
	).set_author(name="Thread unarchived", icon_url=ProfUrl)
