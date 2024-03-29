from discord import Color, Guild, Permissions, utils
import time
import enum

class Rank:

    class Ordering(enum.Enum):
        FIRST = enum.auto()
        LAST = enum.auto()
        ABSOLUTE = enum.auto()

    def __init__(self, name, color, r, ordering=None) -> None:
        self.name = name
        self.color = color
        self.r = r
        self.ordering = ordering

    def __lt__(self, other):
        match self.ordering:
            case Rank.Ordering.FIRST:
                if other.ordering != Rank.Ordering.FIRST:
                    return True
                return False
            case Rank.Ordering.LAST:
                if other.ordering != Rank.Ordering.LAST:
                    return False
                return False
            case Rank.Ordering.ABSOLUTE:
                if other.ordering == Rank.Ordering.ABSOLUTE:
                    return self.r[0] < other.r[0]
                elif other.ordering == Rank.Ordering.LAST:
                    return True
                elif other.ordering == Rank.Ordering.FIRST:
                    return False

CHALLENGED = Rank('Challenged', Color.from_rgb(255, 255, 255), range(-1, 0), Rank.Ordering.FIRST)
IRON = Rank('Iron', Color.dark_gray(), range(0, 850), Rank.Ordering.ABSOLUTE)
BRONZE = Rank('Bronze', Color.dark_orange(), range(850, 1050), Rank.Ordering.ABSOLUTE)
SILVER = Rank('Silver', Color.light_gray(), range(1050, 1250), Rank.Ordering.ABSOLUTE)
GOLD = Rank('Gold', Color.gold(), range(1250, 1450), Rank.Ordering.ABSOLUTE)
PLATINUM = Rank('Platinum', Color.og_blurple(), range(1450, 1650), Rank.Ordering.ABSOLUTE)
EMERALD = Rank('Emerald', Color.green(), range(1650, 1850), Rank.Ordering.ABSOLUTE)
DIAMOND = Rank('Diamond', Color.blue(), range(1850, 9999999), Rank.Ordering.ABSOLUTE)
CHALLENGER = Rank('Challenger', Color.dark_purple(), range(-1, 0), Rank.Ordering.LAST)
THE_BIG_CHUNGUS = Rank('The Big Chungus', Color.dark_purple(), range(-1, 0), Rank.Ordering.LAST)

ALL_RANKS = [CHALLENGED, IRON, BRONZE, SILVER, GOLD, PLATINUM, EMERALD, DIAMOND, THE_BIG_CHUNGUS]

def map_ranks(mmrs):
    mmrs.sort(key=lambda x: x[1])
    name_to_rank = {}
    ranks_with_ranges = [rank for rank in ALL_RANKS if rank.ordering == Rank.Ordering.ABSOLUTE]
    for name, mmr in mmrs:
        for rank in ranks_with_ranges:
            if int(mmr) in rank.r:
                name_to_rank[name] = rank
                break
    if Rank.Ordering.FIRST in [rank.ordering for rank in ALL_RANKS]:
        name_to_rank[mmrs[0][0]] = next(rank for rank in ALL_RANKS if rank.ordering == Rank.Ordering.FIRST)
    if Rank.Ordering.LAST in [rank.ordering for rank in ALL_RANKS]:
        name_to_rank[mmrs[-1][0]] = next(rank for rank in ALL_RANKS if rank.ordering == Rank.Ordering.LAST)
    return name_to_rank

async def startup(guild: Guild):
    for role in guild.roles:
        if  role.name != 'matchmaking bot' and role.name in [rank.name for rank in ALL_RANKS]:
            await role.delete()
            time.sleep(.05)
    default_role = utils.get(guild.roles, name='@everyone')
    if default_role:
        perms = default_role.permissions
    else:
        perms = Permissions.membership()
    for rank in ALL_RANKS:
        if rank not in guild.roles:
            await guild.create_role(name=rank.name, color=rank.color, hoist=True, mentionable=True, permissions=perms)
            time.sleep(.05)
    first_open = 1
    rank_to_role = {}
    for role in guild.roles:
        for rank in ALL_RANKS:
            if role.name == rank.name:
                rank_to_role[rank] = role
                break
    positions = {}
    for rank in sorted(ALL_RANKS):
        positions[rank_to_role[rank]] = first_open
        first_open +=1
    # bot_role = utils.get(guild.roles, name='matchmaking bot')
    # positions[bot_role] = first_open
    await guild.edit_role_positions(positions)
    
