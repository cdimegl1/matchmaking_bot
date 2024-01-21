import sqlite3
import itertools
import random
from enum import IntEnum, auto

db = sqlite3.connect('bot.db')

class MatchmakingType(IntEnum):
    balanced = auto()
    random = auto()

def expected(elo1, elo2):
    return 1 / (1 + 10 ** ((elo2 - elo1) / 400))

def mmr_change(expected, actual, k=100):
    return k * (actual - expected)

class Game:
    def __init__(self, team1_names, team2_names, team1_mmr, team2_mmr):
        self.blue_team = team1_names
        self.red_team = team2_names
        self.blue_mmr = team1_mmr / 5
        self.red_mmr = team2_mmr / 5
        self.expected = expected(team1_mmr, team2_mmr)

    def update(self, actual):
        change = mmr_change(self.expected, actual)
        cur = db.cursor()
        for name in self.blue_team:
            cur.execute('UPDATE mmr SET mmr = mmr + ? WHERE name = ?', (change, name))
            if change > 0:
                cur.execute('UPDATE mmr SET W = W + 1 WHERE name = ?', (name,))
            else:
                cur.execute('UPDATE mmr SET L = L + 1 WHERE name = ?', (name,))
        for name in self.red_team:
            if -change > 0:
                cur.execute('UPDATE mmr SET W = W + 1 WHERE name = ?', (name,))
            else:
                cur.execute('UPDATE mmr SET L = L + 1 WHERE name = ?', (name,))
            cur.execute('UPDATE mmr SET mmr = mmr + ? WHERE name = ?', (-change, name))
        db.commit()

    def __str__(self) -> str:
        res = f'```{"":-^50}\n'
        line = f'Blue Team ({self.blue_mmr:.0f})'
        length = 50 - len(line)
        res += line + f'Red Team ({self.red_mmr:.0f})'.rjust(length) + '\n'
        line = f'{mmr_change(self.expected, 1):+.0f} {mmr_change(self.expected, 0):+.0f}'
        res += line + f'{mmr_change(1 - self.expected, 1):+.0f} {mmr_change(1 - self.expected, 0):+.0f}'.rjust(50 - len(line)) + '\n'
        line = f'{self.expected:.2%}'
        res += line + f'{1 - self.expected:.2%}'.rjust(50 - len(line))
        res += f'\n{"":-^50}\n'
        for blue, red in zip(self.blue_team, self.red_team):
            blue_mmr = get_mmr(blue)
            red_mmr = get_mmr(red)
            line = f'{blue} ({blue_mmr:.0f})'
            length = 50 - len(line)
            red = f'{red} ({red_mmr:.0f})'
            res += line + red.rjust(length) + '\n'
        res += f'{"":-^50}\n```'
        return res

def get_mmr(name):
    cur = db.cursor()
    try:
        return cur.execute('SELECT mmr FROM mmr WHERE name = ?', (name,)).fetchone()[0]
    except:
        return 0

def get_mmrs():
    cur = db.cursor()
    return cur.execute('SELECT name, mmr FROM mmr').fetchall()

def get_stats(name):
    cur = db.cursor()
    return cur.execute('SELECT W, L FROM mmr WHERE name = ?', (name,)).fetchone()

def insert_user_if_new(name):
        cur = db.cursor()
        if not get_mmr(name):
            cur.execute('INSERT INTO mmr (name, mmr) VALUES (?, 1200)', (name,))
            db.commit()

class Matchmaking:
    def __init__(self, names) -> None:
        self.mmrs = {name: get_mmr(name) for name in names}
        self.names = names

    def team_mmr(self, team):
        return sum([self.mmrs[name] for name in team])
        
    def matchmake(self, fun):
        potential_teams = [team for team in itertools.combinations(self.names, 5)]
        blue_team, red_team = fun(potential_teams, self.names, self.mmrs)
        return (list(blue_team), self.team_mmr(blue_team)), (list(red_team), self.team_mmr(red_team))
        
    @staticmethod
    def random(potential_teams, names, _):
        team1 = random.choice(potential_teams)
        team2 = [name for name in names if name not in team1]
        return team1, team2

    @staticmethod
    def balanced(potential_teams, names, mmrs):
        random.shuffle(potential_teams)
        def team_mmr(team):
            return sum([mmrs[name] for name in team])
        def mmr_difference(team):
            return abs(team_mmr(team) - team_mmr([name for name in names if name not in team]))
        team1 = min(potential_teams, key=mmr_difference)
        team2 = [name for name in names if name not in team1]
        return team1, team2

def manual_game(team1, team2, team1_win: bool):
    mmrs = {}
    for name in team1 + team2:
        mmrs[name] = get_mmr(name)

    def team_mmr(team):
        total = 0
        for name in team:
            total += mmrs[name]
        return total / 5

    game = Game(team1, team2, team_mmr(team1), team_mmr(team2))
    game.update(team1_win)

