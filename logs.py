# Beadless Bot Event Logging

import discord

from misc import prof, bbEmbed

# TODO: Implement logging for threads, once BB migrates to nextcord

def logDeleteMsg(text):
	return (bbEmbed("", "**Deleted message sent by {} in **{}\n{}"
	.format(text.author.mention, text.channel.mention, text.content if text.content else "Embed"), 0xff0000)
	.set_author(name = str(text.author), icon_url = text.author.avatar_url))

def logPurge(text, textArr):
	return bbEmbed("", f"Purged {len(textArr) - 1} messages in {text.channel.mention}.", 0xff0000).set_author(name = "Purge!", icon_url = prof)

def logEditMsg(before, after):
	return (bbEmbed("", f"Messaged edited by {before.author.mention} in {before.channel.mention}.", 0xffff00)
	.set_author(name = str(before.author), icon_url = before.author.avatar_url).add_field(name = "Before:", value = before.content, inline = False)
	.add_field(name = "After:", value = f"{after.content}\n[Jump to Message]({after.jump_url})", inline = False))

def logClearReacts(text, reactions):
	return (bbEmbed("", "Reactions cleared from message sent by {} in {}.".format(text.author.mention, text.channel.mention), 0xff0000)
	.set_author(name = str(text.author), icon_url = text.author.avatar_url)
	.add_field(name = "Message content:", value = (text.content if text.content else "Embed") + "\n[Jump to Message]({text.jump_url})")
	.add_field(name = "Reactions:", value = ", ".join(str(react) for react in reactions)))

def logDeleteChannel(channel):
	return bbEmbed("", f"Channel \"{channel.name}\" deleted.", 0xff0000).set_author(name = "Channel deleted", icon_url = prof)

def logCreateChannel(channel):
	return bbEmbed("", f"Channel \"{channel.name}\" created.", 0x00ff00).set_author(name = "Channel created", icon_url = prof)

def logMemberJoin(member):
	return (bbEmbed("", f"Member {member.mention} joined\nAccount registered on {str(member.created_at)[:-7]}\nID: {member.id}",
	0x00ff00).set_author(name = f"{member} joined the server", icon_url = member.avatar_url))

def logMemberRemove(member):
	emb = (bbEmbed("", f"Member {member.mention} left\nID: {member.id}", 0xff0000)
	.set_author(name = f"{member} left the server", icon_url = member.avatar_url))
	if len(member.roles) > 1:
		emb.add_field(name = "Roles:", value = ", ".join(role.mention for role in member.roles[:0:-1]))
	return emb

def logMemberNickChange(before, after):
	return (bbEmbed("", f"Nickname of{after.mention} changed.", 0xffff00).set_author(name = str(after), icon_url = after.avatar_url)
	.add_field(name = "Before:", value = before.nick, inline = False).add_field(name = "After:", value = after.nick, inline = False))

def logMemberRolesChange(before, after):
	newRole = None
	for role in before.roles:
		if role not in after.roles:
			newRole = role
			break
	if not newRole:
		for role in after.roles:
			if role not in before.roles:
				newRole = role
				break
	tup = ("removed from", 0xff0000) if len(before.roles) > len(after.roles) else ("added to", 0x00ff00)
	return bbEmbed("", f"Role {newRole.mention} {tup[0]} {after.mention}.", tup[1]).set_author(name = str(after), icon_url = after.avatar_url)

def logBan(member):
	return (bbEmbed("", f"Member {member.mention} banned\n{member.name}", 0xff0000)
	.set_author(name = "Member banned", icon_url = member.avatar_url).set_thumbnail(url = member.avatar_url))

def logUnban(member):
	return (bbEmbed("", f"Member {member.mention} unbanned\n{member.name}", 0x00ff00)
	.set_author(name = "Member unbanned", icon_url = member.avatar_url).set_thumbnail(url = member.avatar_url))

def logMute(member, message, duration, mString, mTime):
	return (bbEmbed("Beardless Bot Mute",
	"Muted {}{} in {}.".format(member.mention, (f" for {duration} {mString}" if mTime else ""), message.channel.mention), 0xff0000)
	.set_author(name = str(message.author), icon_url = message.author.avatar_url))

def logUnmute(member, author):
	return bbEmbed("Beardless Bot Mute", f"Unmuted {member.mention}.", 0x00ff00).set_author(name = str(author), icon_url = author.avatar_url)