import typing
import mmr
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import constants
import random
import logging
from utils import get_display_name

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=commands.DefaultHelpCommand(no_category='Commands'))

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
        if you are not in the database, queueing adds you to it''')
async def queue(ctx):
    mmr.insert_user_if_new(ctx.author.name)
    msg = ''
    global queue_num
    if ctx.author.name in [user.name for game in games for user in game.blue_team + game.red_team]:
        await ctx.send('you are already in game')
    else:
        if ctx.author.name not in [user.name for user in queued_users]:
            queued_users.append(ctx.author)
            queue_num += 1
            msg += f'{get_display_name(ctx.author)} has joined the queue\n'
            msg += f'{queue_num:2d}/10 currently in queue: ' + ', '.join([get_display_name(user) for user in queued_users]) + '\n'
            await ctx.send(discord.utils.escape_markdown(msg))
            if queue_num == 10:
                teams = None
                match matchmaking_mode:
                    case mmr.MatchmakingType.balanced:
                        teams = mmr.Matchmaking(queued_users).matchmake(mmr.Matchmaking.balanced)
                    case mmr.MatchmakingType.random:
                        teams = mmr.Matchmaking(queued_users).matchmake(mmr.Matchmaking.random)
                game = mmr.Game(teams[0][0], teams[1][0], teams[0][1], teams[1][1])
                games.append(game)
                queued_users.clear()
                queue_num = 0
                await ctx.send(game)
        else:
            queued_users.remove(ctx.author)
            queue_num -= 1
            msg += f'{get_display_name(ctx.author)} has left the queue\n'
            msg += f'{queue_num:2d}/10 currently in queue: ' + ', '.join([get_display_name(user) for user in queued_users]) + '\n'
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

#TODO show updates after blue/red command is used
@bot.command(
        help='''notifies the bot that the blue team has won the current game
        can only be used by someone that was in the game''')
async def blue(ctx):
    user = ctx.author
    for game in games:
        if user in game.blue_team + game.red_team:
            game.update(1)
            games.remove(game)
            break

@bot.command(
        help='''notifies the bot that the red team has won the current game
        can only be used by someone that was in the game''')
async def red(ctx):
    user = ctx.author
    for game in games:
        if user in game.blue_team + game.red_team:
            game.update(0)
            games.remove(game)
            break

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
        for i, (name, rating) in enumerate(res):
            msg += f'{i + 1:2d}: {name} ({rating:.0f})\n'
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

load_dotenv()
if key := os.getenv('API_KEY'):
    bot.run(key)

