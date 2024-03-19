import typing
import ranks
import mmr
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import constants
import random
import logging
import time
from utils import get_display_name

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=commands.DefaultHelpCommand(no_category='Commands'))
load_dotenv()
GUILD_ID = int(os.getenv('GUILD_ID'))
if GUILD_ID is None:
    exit(1)

queue_num = 0
queued_users = []
games = []
matchmaking_mode = mmr.MatchmakingType.balanced 

# @bot.command()
# async def sync(_):
#     await bot.tree.sync()

@bot.event
async def on_command_error(ctx, err):
    command = ctx.command
    if command and command.has_error_handler():
        return
    cog = ctx.cog
    if cog and cog.has_error_handler():
        return
    _log = logging.getLogger('discord.ext.bot')
    _log.error('Ignoring exception in command %s', command, exc_info=err)
    await ctx.send_help()

@bot.command(
        help='''joins/leaves the queue
        when 10 are in queue a game is made
        if you are not in the database, queueing adds you to it
        you can also specify roles to queue for
        if you don't specify any roles, you will be queued as fill
        roles: top, jg, mid, bot, sup''')
async def queue(ctx, 
                *args):
    if args:
        for role in args:
            if role not in ['top', 'jg', 'mid', 'bot', 'sup']:
                raise Exception
    mmr.insert_user_if_new(ctx.author.name)
    msg = ''
    global queued_users
    global queue_num
    if ctx.author.name in [user.name for game in games for user in game.blue_team + game.red_team]:
        await ctx.send('you are already in game')
    else:
        if ctx.author.name not in [user[0].name for user in queued_users]:
            queued_users.append((ctx.author, list(args)))
            queue_num += 1
            msg += f"{get_display_name(ctx.author)} ({', '.join(args) if args else 'fill'}) has joined the queue\n"
            user_strs = [get_display_name(user[0]) + f" ({', '.join(user[1]) if user[1] else 'fill'})" for user in queued_users]
            msg += f"{queue_num:2d}/10 currently in queue: {', '.join(user_strs)}"
            await ctx.send(discord.utils.escape_markdown(msg))
            if queue_num >= 10:
                teams = None
                match matchmaking_mode:
                    case mmr.MatchmakingType.balanced:
                        teams = mmr.Matchmaking(queued_users).matchmake(mmr.Matchmaking.balanced)
                    case mmr.MatchmakingType.random:
                        teams = mmr.Matchmaking(queued_users).matchmake(mmr.Matchmaking.random)
                if teams:
                    game = mmr.Game(teams[0][0], teams[1][0], teams[0][1], teams[1][1])
                    games.append(game)

                    queued_users = [user for user in queued_users if user[0] not in game.blue_team + game.red_team]
                    queue_num -= 10
                    await ctx.send(game)
                else:
                    await ctx.send('can\'t matchmake with current roles')
        else:
            queued_users = [user for user in queued_users if user[0] != ctx.author]
            queue_num -= 1
            msg += f'{get_display_name(ctx.author)} has left the queue\n'
            user_strs = [get_display_name(user[0]) + f" ({', '.join(user[1]) if user[1] else 'fill'})" for user in queued_users]
            msg += f"{queue_num:2d}/10 currently in queue: {', '.join(user_strs)}"
            await ctx.send(discord.utils.escape_markdown(msg))

@bot.command(
        help='''displays/changes mode
        if no arguments are given, shows current mode and list of available modes
        if argument is given, switch to that mode''')
async def mode(ctx, 
               mode: typing.Optional[str]=commands.parameter(description=f'mode to switch to\ncan be one of {list(mmr.MatchmakingType.__members__)}')):
    global matchmaking_mode
    if mode:
        try:
            matchmaking_mode = mmr.MatchmakingType[mode]
        except KeyError:
            await ctx.send(f'use a valid mode: {list(mmr.MatchmakingType.__members__)}')
    else:
        await ctx.send(f'available modes: {list(mmr.MatchmakingType.__members__)}\ncurrent mode: {matchmaking_mode.name}')

@bot.command(
        help='''removes all users from the queue''')
async def clear(ctx):
    global queue_num
    queue_num = 0
    queued_users.clear()
    await ctx.send('queue has been cleared')

@bot.command(
        help='''voids current game and removes all users from the queue
        can only be used by someone currently in the game''')
async def reset(ctx):
    global queue_num
    for game in games:
        if ctx.author in game.blue_team + game.red_team:
            games.remove(game)
            break
    queue_num = 0
    queued_users.clear()
    await ctx.send('queue has been reset')

@bot.command(
        help='''generates two random lists of champions''')
async def aram(ctx, 
               number: typing.Optional[int]=commands.parameter(default=15, description='number of champions in each list')):
    if number:
        champs = random.sample(constants.champions, number * 2)
        team1 = champs[:number]
        team2 = champs[number:]
        await ctx.send(f'Blue Team: {team1}\nRed Team: {team2}')

async def give_win(ctx, blue_win):
    user = ctx.author
    for game in games:
        if user in game.blue_team + game.red_team:
            msg = ''
            mmrs = mmr.get_mmrs()
            old_ranks = ranks.map_ranks(mmrs)
            game.update(blue_win)
            games.remove(game)
            mmrs = mmr.get_mmrs()
            bot.dispatch('ranks_changed', [user.name for user in game.blue_team + game.red_team])
            new_ranks = ranks.map_ranks(mmrs)
            for name, rank in new_ranks.items():
                if rank < old_ranks[name]:
                    user = next(user for user in game.blue_team + game.red_team if user.name == name)
                    msg += f'{get_display_name(user)} has been demoted from {old_ranks[name].name} to {rank.name}\n'
                if old_ranks[name] < rank:
                    user = next(user for user in game.blue_team + game.red_team if user.name == name)
                    msg += f'{get_display_name(user)} has been promoted from {old_ranks[name].name} to {rank.name}\n'
            if not msg:
                msg = 'no ranks have changed'
            await ctx.send(discord.utils.escape_markdown(msg))
            break

@bot.command(
        help='''notifies the bot that the blue team has won the current game
        can only be used by someone that was in the game''')
async def blue(ctx):
    await give_win(ctx, 1)

@bot.command(
        help='''notifies the bot that the red team has won the current game
        can only be used by someone that was in the game''')
async def red(ctx):
    await give_win(ctx, 0)

@bot.command(name='mmr',
             help='''gets list of all users sorted by mmr
             if name is provided, gets the user's mmr''')
async def _mmr(ctx, name: typing.Optional[discord.Member]=commands.parameter(description='name of user whose mmr should be returned')):
    if name:
        await ctx.send(f'{mmr.get_mmr(name.name):.0f}')
    else:
        res = mmr.get_mmrs()
        res.sort(key=lambda x: x[1], reverse=True)
        msg = ''
        for i, (username, rating) in enumerate(res):
            if guild := bot.get_guild(GUILD_ID):
                if member := guild.get_member_named(username):
                    msg += f'{i + 1:2d}: {get_display_name(member)} ({rating:.0f})\n'
                else:
                    msg += f'{i + 1:2d}: {username} ({rating:.0f})\n'
            else:
                msg += f'{i + 1:2d}: {username} ({rating:.0f})\n'
        await ctx.send(discord.utils.escape_markdown(msg))

@bot.command(
        help='''returns your record
        if name is provided, gets the user's record''')
async def record(ctx, name: typing.Optional[discord.Member]=commands.parameter(description='name of user whose record should be returned')):
    record = None
    if name:
        record = mmr.get_stats(name.name)
    else:
        record = mmr.get_stats(ctx.author.name)
    await ctx.send(f'{record[0]}W - {record[1]}L')

@bot.command()
async def shrago(ctx):
    with open('shrago.png', 'rb') as pic:
        file = discord.File(pic)
        await ctx.send(file=file)

@bot.command()
async def edboy(ctx):
    with open('edboy.png', 'rb') as pic:
        file = discord.File(pic)
        await ctx.send(file=file)

@bot.command(name='ranks', help='''displays all ranks''')
async def _ranks(ctx):
    msg = ''
    for rank in sorted(ranks.ALL_RANKS, reverse=True):
        match rank.ordering:
            case ranks.Rank.Ordering.ABSOLUTE:
                if rank == ranks.DIAMOND:
                    msg += f'{rank.name} ({rank.r[0]}+)\n'
                else:
                    msg += f'{rank.name} ({rank.r[0]} - {rank.r[-1]})\n'
            case ranks.Rank.Ordering.FIRST:
                msg += f'{rank.name} (lowest mmr)'
            case ranks.Rank.Ordering.LAST:
                msg = f'{rank.name} (highest mmr)\n' + msg
    await ctx.send(msg)

@bot.event
async def on_ready():
    if guild := bot.get_guild(GUILD_ID):
        await ranks.startup(guild)
        mmrs = mmr.get_mmrs()
        for name, rank in ranks.map_ranks(mmrs).items():
            if member := guild.get_member_named(name):
                if role := discord.utils.get(guild.roles, name=rank.name):
                    await member.add_roles(role)
                    time.sleep(.05)

@bot.event
async def on_ranks_changed(names):
    if guild := bot.get_guild(GUILD_ID):
        managed_roles = [role for role in guild.roles if role.name in [rank.name for rank in ranks.ALL_RANKS]]
        for name in names:
            if member:= guild.get_member_named(name):
                await member.remove_roles(*managed_roles)
                time.sleep(.05)
        mmrs = mmr.get_mmrs()
        for name, rank in ranks.map_ranks(mmrs).items():
            if member := guild.get_member_named(name):
                if role := discord.utils.get(guild.roles, name=rank.name):
                    await member.add_roles(role)
                    time.sleep(.05)

if key := os.getenv('API_KEY'):
    bot.run(key)

