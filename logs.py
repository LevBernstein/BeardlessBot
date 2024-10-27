"""Beadless Bot event logging methods."""

from collections.abc import Sequence
from typing import Final

import nextcord

from misc import ProfUrl, bb_embed, content_check, fetch_avatar, truncate_time

# TODO: Implement log thread locked/unlocked
# https://github.com/LevBernstein/BeardlessBot/issues/45

MaxPurgedMsgs: Final[int] = 99


def log_delete_msg(message: nextcord.Message) -> nextcord.Embed:
	assert hasattr(message.channel, "mention")
	prefix = (
		f"**Deleted message sent by {message.author.mention} in "
		f"**{message.channel.mention}\n"
	)
	return bb_embed(
		value=f"{prefix}{content_check(message, len(prefix))}",
		col=0xFF0000,
		showTime=True,
	).set_author(name=message.author, icon_url=fetch_avatar(message.author))


def log_purge(
	msg: nextcord.Message, messages: Sequence[nextcord.Message],
) -> nextcord.Embed:

	def purge_report(msgList: Sequence[nextcord.Message]) -> str:
		return (
			f"{MaxPurgedMsgs}+"
			if len(msgList) > MaxPurgedMsgs
			else str(len(msgList) - 1)
		)

	assert hasattr(msg.channel, "mention")
	return bb_embed(
		"",
		f"Purged {purge_report(messages)} messages in {msg.channel.mention}.",
		0xFF0000,
		showTime=True,
	).set_author(name="Purge!", icon_url=ProfUrl)


def log_edit_msg(
	before: nextcord.Message, after: nextcord.Message,
) -> nextcord.Embed:
	assert hasattr(before.channel, "mention")
	addendum = f"\n[Jump to Message]({after.jump_url})"
	return bb_embed(
		"",
		f"Messaged edited by {before.author.mention}"
		f" in {before.channel.mention}.",
		0xFFFF00,
		showTime=True,
	).set_author(
		name=before.author, icon_url=fetch_avatar(before.author),
	).add_field(
		name="Before:", value=content_check(before, 7), inline=False,
	).add_field(
		name="After:",
		value=f"{content_check(after, len(addendum))}{addendum}",
		inline=False,
	)


def log_clear_reacts(
	message: nextcord.Message, reactions: list[nextcord.Reaction],
) -> nextcord.Embed:
	assert hasattr(message.channel, "mention")
	jumpLink = f"\n[Jump to Message]({message.jump_url})"
	return bb_embed(
		"",
		f"Reactions cleared from message sent by {message.author.mention}"
		f" in {message.channel.mention}.",
		0xFF0000,
		showTime=True,
	).set_author(
		name=message.author, icon_url=fetch_avatar(message.author),
	).add_field(
		name="Message content:",
		value=content_check(message, len(jumpLink)) + jumpLink,
	).add_field(
		name="Reactions:", value=", ".join(str(r) for r in reactions),
	)


def log_delete_channel(channel: nextcord.abc.GuildChannel) -> nextcord.Embed:
	return bb_embed(
		"", f"Channel \"{channel.name}\" deleted.", 0xFF0000, showTime=True,
	).set_author(name="Channel deleted", icon_url=ProfUrl)


def log_create_channel(channel: nextcord.abc.GuildChannel) -> nextcord.Embed:
	return bb_embed(
		"", f"Channel \"{channel.name}\" created.", 0x00FF00, showTime=True,
	).set_author(name="Channel created", icon_url=ProfUrl)


def log_member_join(member: nextcord.Member) -> nextcord.Embed:
	return bb_embed(
		"",
		f"Member {member.mention} joined\nAccount registered"
		f" on {truncate_time(member)}\nID: {member.id}",
		0x0000FF,
		showTime=True,
	).set_author(
		name=f"{member} joined the server", icon_url=fetch_avatar(member),
	)


def log_member_remove(member: nextcord.Member) -> nextcord.Embed:
	emb = bb_embed(
		value=f"Member {member.mention} left\nID: {member.id}",
		col=0xFF0000,
		showTime=True,
	).set_author(
		name=f"{member} left the server", icon_url=fetch_avatar(member),
	)
	if len(member.roles) > 1:
		emb.add_field(
			name="Roles:",
			value=", ".join(role.mention for role in member.roles[:0:-1]),
		)
	return emb


def log_member_nick_change(
	before: nextcord.Member, after: nextcord.Member,
) -> nextcord.Embed:
	return bb_embed(
		"", f"Nickname of {after.mention} changed.", 0xFFFF00, showTime=True,
	).set_author(
		name=after, icon_url=fetch_avatar(after),
	).add_field(
		name="Before:", value=before.nick, inline=False,
	).add_field(name="After:", value=after.nick, inline=False)


def log_member_roles_change(
	before: nextcord.Member, after: nextcord.Member,
) -> nextcord.Embed:
	verb, color = (
		("removed from", 0xFF0000)
		if len(before.roles) > len(after.roles)
		else ("added to", 0x00FF00)
	)
	role = set(after.roles).symmetric_difference(set(before.roles)).pop()
	return bb_embed(
		value=f"Role {role.mention} {verb} {after.mention}.",
		col=color,
		showTime=True,
	).set_author(name=after, icon_url=fetch_avatar(after))


def log_ban(member: nextcord.Member) -> nextcord.Embed:
	return bb_embed(
		value=f"Member {member.mention} banned\n{member.name}",
		col=0xFF0000,
		showTime=True,
	).set_author(
		name="Member banned", icon_url=fetch_avatar(member),
	).set_thumbnail(url=fetch_avatar(member))


def log_unban(member: nextcord.Member) -> nextcord.Embed:
	return bb_embed(
		value=f"Member {member.mention} unbanned\n{member.name}",
		col=0x00FF00,
		showTime=True,
	).set_author(
		name="Member unbanned", icon_url=fetch_avatar(member),
	).set_thumbnail(url=fetch_avatar(member))


def log_mute(
	member: nextcord.Member, message: nextcord.Message, duration: str | None,
) -> nextcord.Embed:
	assert hasattr(message.channel, "mention")
	mid = f" for {duration}" if duration else ""
	return bb_embed(
		"Beardless Bot Mute",
		f"Muted {member.mention}{mid} in {message.channel.mention}.",
		0xFF0000,
		showTime=True,
	).set_author(name=message.author, icon_url=fetch_avatar(message.author))


def log_unmute(
	member: nextcord.Member, author: nextcord.Member,
) -> nextcord.Embed:
	return bb_embed(
		"Beardless Bot Mute",
		f"Unmuted {member.mention}.",
		0x00FF00,
		showTime=True,
	).set_author(name=author, icon_url=fetch_avatar(author))


def log_create_thread(thread: nextcord.Thread) -> nextcord.Embed:
	assert isinstance(thread.parent, nextcord.abc.GuildChannel)
	return bb_embed(
		"",
		f"Thread \"{thread.name}\" created in"
		f" parent channel {thread.parent.mention}.",
		0x00FF00,
		showTime=True,
	).set_author(name="Thread created", icon_url=ProfUrl)


def log_delete_thread(thread: nextcord.Thread) -> nextcord.Embed:
	return bb_embed(
		"", f"Thread \"{thread.name}\" deleted.", 0xFF0000, showTime=True,
	).set_author(name="Thread deleted", icon_url=ProfUrl)


def log_thread_archived(thread: nextcord.Thread) -> nextcord.Embed:
	return bb_embed(
		"", f"Thread \"{thread.name}\" archived.", 0xFFFF00, showTime=True,
	).set_author(name="Thread archived", icon_url=ProfUrl)


def log_thread_unarchived(thread: nextcord.Thread) -> nextcord.Embed:
	return bb_embed(
		"", f"Thread \"{thread.name}\" unarchived.", 0xFFFF00, showTime=True,
	).set_author(name="Thread unarchived", icon_url=ProfUrl)
