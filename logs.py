# Beadless Bot Event Logging

import discord

# TODO: Implement logging for threads, once discord.py updates to include support for them

def logDeleteMsg(text):
    return (discord.Embed(description = "**Deleted message sent by " + text.author.mention + " in **" + text.channel.mention + "\n" + text.content, color = 0xff0000)
    .set_author(name = str(text.author), icon_url = text.author.avatar_url))

def logPurge(text, textArr):
    return (discord.Embed(description = "Purged " + str(len(textArr) - 1) + " messages in " + text.channel.mention + ".", color = 0xff0000)
    .set_author(name = "Purge!", icon_url = "https://cdn.discordapp.com/avatars/654133911558946837/78c6e18d8febb2339b5513134fa76b94.webp?size=1024"))

def logEditMsg(before, after):
    return (discord.Embed(description = "Messaged edited by" + before.author.mention + " in " + before.channel.mention + ".", color = 0xffff00)
    .set_author(name = str(before.author), icon_url = before.author.avatar_url)
    .add_field(name = "Before:", value = before.content, inline = False)
    .add_field(name = "After:", value = after.content + "\n[Jump to Message](" + after.jump_url + ")", inline = False))

def logClearReacts(text, reactions):
    return (discord.Embed(description = "Reactions cleared from message sent by" + text.author.mention + " in " + text.channel.mention + ".", color = 0xff0000)
    .set_author(name = str(text.author), icon_url = text.author.avatar_url)
    .add_field(name = "Message content:", value = text.content)
    .add_field(name = "Reactions:", value = ", ".join(str(reaction) for reaction in reactions)))

def logDeleteChannel(channel):
    return (discord.Embed(description = "Channel \"" + channel.name + "\" deleted.", color = 0xff0000)
    .set_author(name = "Channel deleted", icon_url = "https://cdn.discordapp.com/avatars/654133911558946837/78c6e18d8febb2339b5513134fa76b94.webp?size=1024"))

def logCreateChannel(channel):
    return (discord.Embed(description = "Channel " + channel.name + " created.", color = 0x00ff00)
    .set_author(name = "Channel created", icon_url = "https://cdn.discordapp.com/avatars/654133911558946837/78c6e18d8febb2339b5513134fa76b94.webp?size=1024"))

def logMemberJoin(member):
    return (discord.Embed(description = "Member {} joined\nAccount registered on {}\nID: {}"
    .format(member.mention, str(member.created_at)[:-7], member.id), color = 0x00ff00)
    .set_author(name = str(member) + " joined the server", icon_url = member.avatar_url))

def logMemberRemove(member):
    emb = (discord.Embed(description = "Member " + member.mention + " left\nID: " + str(member.id), color = 0xff0000)
    .set_author(name = str(member) +" left the server", icon_url = member.avatar_url))
    if len(member.roles) > 1:
        emb.add_field(name = "Roles:", value = ", ".join(role.mention for role in member.roles[:0:-1]))
    return emb

def logMemberNickChange(before, after):
    return (discord.Embed(description = "Nickname of" + after.mention + " changed", color = 0xffff00)
    .set_author(name = str(after), icon_url = after.avatar_url)
    .add_field(name = "Before:", value = before.nick, inline = False)
    .add_field(name = "After:", value = after.nick, inline = False))

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
    tup = (" removed from ", 0xff0000) if len(before.roles) > len(after.roles) else (" added to ", 0x00ff00)
    return (discord.Embed(description = "Role " + newRole.mention + tup[0]  + after.mention, color = tup[1])
    .set_author(name = str(after), icon_url = after.avatar_url))

def logBan(member):
    return (discord.Embed(description = "Member " + member.mention + " banned\n" + member.name, color = 0xff0000)
    .set_author(name = "Member banned", icon_url = member.avatar_url).set_thumbnail(url = member.avatar_url))

def logUnban(member):
    return (discord.Embed(description = "Member " + member.mention + " unbanned\n" + member.name, color = 0x00ff00)
    .set_author(name = "Member unbanned", icon_url = member.avatar_url).set_thumbnail(url = member.avatar_url))

def logMute(member, message, duration, mString, mTime):
    return (discord.Embed(title = "Beardless Bot Mute", description = "Muted " + member.mention + ((" for " + duration + mString) if mTime else "") + " in " + message.channel.mention + ".", color = 0xff0000)
    .set_author(name = str(message.author), icon_url = message.author.avatar_url))

def logUnmute(member, author):
    return (discord.Embed(title = "Beardless Bot Mute", description = "Autounmuted " + member.mention + ".", color = 0x00ff00)
    .set_author(name = str(author), icon_url = author.avatar_url))