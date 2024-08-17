"""Beadless Bot event logging methods"""

from typing import List, Optional

import nextcord

from misc import bbEmbed, contCheck, fetchAvatar, prof, truncTime

# TODO: Implement log thread locked/unlocked


def logDeleteMsg(msg: nextcord.Message) -> nextcord.Embed:
	assert isinstance(
		msg.channel, (nextcord.abc.GuildChannel, nextcord.Thread)
	)
	return bbEmbed(
		"",
		f"**Deleted message sent by {msg.author.mention} in "
		f"**{msg.channel.mention}\n{contCheck(msg)}",
		0xFF0000,
		True
	).set_author(name=msg.author, icon_url=fetchAvatar(msg.author))


def logPurge(
	msg: nextcord.Message, msgList: List[nextcord.Message]
) -> nextcord.Embed:

	def purgeReport(msgList: List[nextcord.Message]) -> str:
		return "99+" if len(msgList) > 99 else str(len(msgList) - 1)

	assert isinstance(
		msg.channel, (nextcord.abc.GuildChannel, nextcord.Thread)
	)
	return bbEmbed(
		"",
		f"Purged {purgeReport(msgList)} messages in {msg.channel.mention}.",
		0xFF0000,
		True
	).set_author(name="Purge!", icon_url=prof)


def logEditMsg(
	before: nextcord.Message, after: nextcord.Message
) -> nextcord.Embed:
	assert isinstance(
		before.channel, (nextcord.abc.GuildChannel, nextcord.Thread)
	)
	return (
		bbEmbed(
			"",
			f"Messaged edited by {before.author.mention}"
			f" in {before.channel.mention}.",
			0xFFFF00,
			True
		)
		.set_author(name=before.author, icon_url=fetchAvatar(before.author))
		.add_field(name="Before:", value=contCheck(before), inline=False)
		.add_field(
			name="After:",
			value=f"{contCheck(after)}\n[Jump to Message]({after.jump_url})",
			inline=False
		)
	)


def logClearReacts(
	msg: nextcord.Message, reactions: List[nextcord.Reaction]
) -> nextcord.Embed:
	assert isinstance(
		msg.channel, (nextcord.abc.GuildChannel, nextcord.Thread)
	)
	return (
		bbEmbed(
			"",
			f"Reactions cleared from message sent by {msg.author.mention}"
			f" in {msg.channel.mention}.",
			0xFF0000,
			True
		)
		.set_author(name=msg.author, icon_url=fetchAvatar(msg.author))
		.add_field(
			name="Message content:",
			value=contCheck(msg) + f"\n[Jump to Message]({msg.jump_url})"
		)
		.add_field(
			name="Reactions:", value=", ".join(str(r) for r in reactions)
		)
	)


def logDeleteChannel(channel: nextcord.abc.GuildChannel) -> nextcord.Embed:
	return bbEmbed(
		"", f'Channel "{channel.name}" deleted.', 0xFF0000, True
	).set_author(name="Channel deleted", icon_url=prof)


def logCreateChannel(channel: nextcord.abc.GuildChannel) -> nextcord.Embed:
	return bbEmbed(
		"", f'Channel "{channel.name}" created.', 0x00FF00, True
	).set_author(name="Channel created", icon_url=prof)


def logMemberJoin(member: nextcord.Member) -> nextcord.Embed:
	return bbEmbed(
		"",
		f"Member {member.mention} joined\nAccount registered"
		f" on {truncTime(member)}\nID: {member.id}",
		0x0000FF,
		True
	).set_author(
		name=f"{member} joined the server", icon_url=fetchAvatar(member)
	)


def logMemberRemove(member: nextcord.Member) -> nextcord.Embed:
	emb = bbEmbed(
		"", f"Member {member.mention} left\nID: {member.id}", 0xFF0000, True
	).set_author(name=f"{member} left the server", icon_url=fetchAvatar(member))
	if len(member.roles) > 1:
		emb.add_field(
			name="Roles:",
			value=", ".join(role.mention for role in member.roles[:0:-1])
		)
	return emb


def logMemberNickChange(
	before: nextcord.Member, after: nextcord.Member
) -> nextcord.Embed:
	return (
		bbEmbed("", f"Nickname of {after.mention} changed.", 0xFFFF00, True)
		.set_author(name=after, icon_url=fetchAvatar(after))
		.add_field(name="Before:", value=before.nick, inline=False)
		.add_field(name="After:", value=after.nick, inline=False)
	)


def logMemberRolesChange(
	before: nextcord.Member, after: nextcord.Member
) -> nextcord.Embed:
	if len(before.roles) > len(after.roles):
		roles, others = before.roles, after.roles
		verb, color = "removed from", 0xFF0000
	else:
		roles, others = after.roles, before.roles
		verb, color = "added to", 0x00FF00
	for role in roles:
		if role not in others:
			newRole = role
			break
	return bbEmbed(
		"", f"Role {newRole.mention} {verb} {after.mention}.", color, True
	).set_author(name=after, icon_url=fetchAvatar(after))


def logBan(member: nextcord.Member) -> nextcord.Embed:
	return (
		bbEmbed(
			"",
			f"Member {member.mention} banned\n{member.name}",
			0xFF0000,
			True
		)
		.set_author(name="Member banned", icon_url=fetchAvatar(member))
		.set_thumbnail(url=fetchAvatar(member))
	)


def logUnban(member: nextcord.Member) -> nextcord.Embed:
	return (
		bbEmbed(
			"",
			f"Member {member.mention} unbanned\n{member.name}",
			0x00FF00,
			True
		)
		.set_author(name="Member unbanned", icon_url=fetchAvatar(member))
		.set_thumbnail(url=fetchAvatar(member))
	)


def logMute(
	member: nextcord.Member,
	message: nextcord.Message,
	duration: Optional[str],
	mString: Optional[str],
	mTime: Optional[float]
) -> nextcord.Embed:
	assert isinstance(
		message.channel, (nextcord.abc.GuildChannel, nextcord.Thread)
	)
	mid = f" for {duration} {mString}" if mTime else ""
	return bbEmbed(
		"Beardless Bot Mute",
		f"Muted {member.mention}{mid} in {message.channel.mention}.",
		0xFF0000,
		True
	).set_author(name=message.author, icon_url=fetchAvatar(message.author))


def logUnmute(
	member: nextcord.Member, author: nextcord.Member
) -> nextcord.Embed:
	return bbEmbed(
		"Beardless Bot Mute", f"Unmuted {member.mention}.", 0x00FF00, True
	).set_author(name=author, icon_url=fetchAvatar(author))


def logCreateThread(thread: nextcord.Thread) -> nextcord.Embed:
	assert isinstance(thread.parent, nextcord.abc.GuildChannel)
	emb = bbEmbed(
		"",
		f"Thread \"{thread.name}\" created in"
		f" parent channel {thread.parent.mention}.",
		0x00FF00,
		True
	).set_author(name="Thread created", icon_url=prof)
	return emb


def logDeleteThread(thread: nextcord.Thread) -> nextcord.Embed:
	return bbEmbed(
		"", f"Thread \"{thread.name}\" deleted.", 0xFF0000, True
	).set_author(name="Thread deleted", icon_url=prof)


def logThreadArchived(thread: nextcord.Thread) -> nextcord.Embed:
	return bbEmbed(
		"", f"Thread \"{thread.name}\" archived.", 0xFFFF00, True
	).set_author(name="Thread archived", icon_url=prof)


def logThreadUnarchived(thread: nextcord.Thread) -> nextcord.Embed:
	return bbEmbed(
		"", f"Thread \"{thread.name}\" unarchived.", 0xFFFF00, True
	).set_author(name="Thread unarchived", icon_url=prof)
