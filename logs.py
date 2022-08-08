# Beadless Bot event logging methods

from typing import List, Optional

import discord

from misc import bbEmbed, prof, truncTime


# TODO: Implement logging for threads, once BB migrates to nextcord

msgMaxLength = "**Message length exceeds 1024 characters.**"


def contCheck(msg: discord.Message) -> str:
	if msg.content:
		if len(msg.content) > 1024:
			return msgMaxLength
		return msg.content
	return "**Embed**"


def logDeleteMsg(msg: discord.Message) -> discord.Embed:
	return bbEmbed(
		"",
		f"**Deleted message sent by {msg.author.mention} in "
		f"**{msg.channel.mention}\n{contCheck(msg)}",
		0xFF0000,
		True
	).set_author(name=msg.author, icon_url=msg.author.avatar_url)


def logPurge(
	msg: discord.Message, msgList: List[discord.Message]
) -> discord.Embed:

	def purgeReport(msgList: List[discord.Message]) -> str:
		return "99+" if len(msgList) > 99 else str(len(msgList) - 1)

	return bbEmbed(
		"",
		f"Purged {purgeReport(msgList)} messages in {msg.channel.mention}.",
		0xFF0000,
		True
	).set_author(name="Purge!", icon_url=prof)


def logEditMsg(
	before: discord.Message, after: discord.Message
) -> discord.Embed:
	return (
		bbEmbed(
			"",
			f"Messaged edited by {before.author.mention}"
			f" in {before.channel.mention}.",
			0xFFFF00,
			True
		)
		.set_author(name=before.author, icon_url=before.author.avatar_url)
		.add_field(name="Before:", value=contCheck(before), inline=False)
		.add_field(
			name="After:",
			value=f"{contCheck(after)}\n[Jump to Message]({after.jump_url})",
			inline=False
		)
	)


def logClearReacts(
	msg: discord.Message, reactions: List[discord.Reaction]
) -> discord.Embed:
	return (
		bbEmbed(
			"",
			f"Reactions cleared from message sent by {msg.author.mention}"
			f" in {msg.channel.mention}.",
			0xFF0000,
			True
		)
		.set_author(name=msg.author, icon_url=msg.author.avatar_url)
		.add_field(
			name="Message content:",
			value=contCheck(msg) + f"\n[Jump to Message]({msg.jump_url})"
		)
		.add_field(
			name="Reactions:", value=", ".join(str(r) for r in reactions)
		)
	)


def logDeleteChannel(channel: discord.abc.GuildChannel) -> discord.Embed:
	return bbEmbed(
		"", f'Channel "{channel.name}" deleted.', 0xFF0000, True
	).set_author(name="Channel deleted", icon_url=prof)


def logCreateChannel(channel: discord.abc.GuildChannel) -> discord.Embed:
	return bbEmbed(
		"", f'Channel "{channel.name}" created.', 0x00FF00, True
	).set_author(name="Channel created", icon_url=prof)


def logMemberJoin(member: discord.Member) -> discord.Embed:
	return bbEmbed(
		"",
		f"Member {member.mention} joined\nAccount registered"
		f" on {truncTime(member)}\nID: {member.id}",
		0x0000FF,
		True
	).set_author(
		name=f"{member} joined the server", icon_url=member.avatar_url
	)


def logMemberRemove(member: discord.Member) -> discord.Embed:
	emb = bbEmbed(
		"", f"Member {member.mention} left\nID: {member.id}", 0xFF0000, True
	).set_author(name=f"{member} left the server", icon_url=member.avatar_url)
	if len(member.roles) > 1:
		emb.add_field(
			name="Roles:",
			value=", ".join(role.mention for role in member.roles[:0:-1])
		)
	return emb


def logMemberNickChange(
	before: discord.Member, after: discord.Member
) -> discord.Embed:
	return (
		bbEmbed("", f"Nickname of {after.mention} changed.", 0xFFFF00, True)
		.set_author(name=after, icon_url=after.avatar_url)
		.add_field(name="Before:", value=before.nick, inline=False)
		.add_field(name="After:", value=after.nick, inline=False)
	)


def logMemberRolesChange(
	before: discord.Member, after: discord.Member
) -> discord.Embed:
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
	).set_author(name=after, icon_url=after.avatar_url)


def logBan(member: discord.Member) -> discord.Embed:
	return (
		bbEmbed(
			"",
			f"Member {member.mention} banned\n{member.name}",
			0xFF0000,
			True
		)
		.set_author(name="Member banned", icon_url=member.avatar_url)
		.set_thumbnail(url=member.avatar_url)
	)


def logUnban(member: discord.Member) -> discord.Embed:
	return (
		bbEmbed(
			"",
			f"Member {member.mention} unbanned\n{member.name}",
			0x00FF00,
			True
		)
		.set_author(name="Member unbanned", icon_url=member.avatar_url)
		.set_thumbnail(url=member.avatar_url)
	)


def logMute(
	member: discord.Member,
	message: discord.Message,
	duration: Optional[str],
	mString: Optional[str],
	mTime: Optional[float]
) -> discord.Embed:
	mid = f" for {duration} {mString}" if mTime else ""
	return bbEmbed(
		"Beardless Bot Mute",
		f"Muted {member.mention}{mid} in {message.channel.mention}.",
		0xFF0000,
		True
	).set_author(name=message.author, icon_url=message.author.avatar_url)


def logUnmute(
	member: discord.Member, author: discord.Member
) -> discord.Embed:
	return bbEmbed(
		"Beardless Bot Mute", f"Unmuted {member.mention}.", 0x00FF00, True
	).set_author(name=author, icon_url=author.avatar_url)
