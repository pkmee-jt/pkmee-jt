#!/usr/bin/env python3
import os
import json

SOURCE = "src/data/trainers.party"
# SOURCE = "trainers.party"
# SOURCE = "~\decomps\pkmee-jt\src\data\trainers.party"

MASTERSHEET = "mastersheet.md"
CALC_SETS = "gen9.js"

class Pokemon:
    def __init__(self):
        self.nickname = None
        self.species = None
        self.level = None
        self.ability = None
        self.gender = None
        self.item = None
        self.nature = None
        self.ivs = None
        self.teraType = None
        self.status = None
        self.index = None
        self.moves = []


class Trainer:
    def __init__(self):
        self.name = None
        self.party = []


def write_to_file(content, file):
    with open(file, 'a') as file:
        file.write(str(content) + '\n')


def get_mon_suffix(mon):
    if mon.status is not None and mon.teraType is None:
        return f'{mon.ability}|{mon.nature}|{mon.status}'
    elif mon.status is None and mon.teraType is not None:
        return f'{mon.ability}|{mon.nature}|{mon.teraType}'
    if mon.status is not None and mon.teraType is not None:
        return f'{mon.ability}|{mon.nature}|{mon.teraType}|{mon.status}'
    else:
        return f'{mon.ability}|{mon.nature}'


def generate_mastersheet(trainers):
    str = ""
    for trainer in trainers:
        str += '## ' + trainer.name + '\n'
        for mon in trainer.party:
            suffix = get_mon_suffix(mon)
            str += f'{mon.species} Lv.{mon.level} @{mon.item}: {', '.join(mon.moves)} [{suffix}]  \n'
        str += '\n'
    return str


def generate_cals_sets(trainers):
    data = {}
    for trainer in trainers:
        trainer_name = trainer.name
        trainer_name = {}
        for mon in trainer.party:
            species = mon.species
            if species not in data:
                data[species] = {}
            data[species].update({trainer.name: {"level": mon.level, \
                                                 "ivs": mon.ivs, \
                                                 "item": mon.item, \
                                                 "ability": mon.ability, \
                                                 "nature": mon.nature, \
                                                 "teraType": mon.teraType, \
                                                 "status": mon.status, \
                                                 "moves": mon.moves, \
                                                 "index": mon.index}})

    return "var SETDEX_SV =" + json.dumps(data)


def parse_parties(parties):
    trainer_parties = []
    trainer = None
    pokemon = None
    trainer_name = None
    trainer_class = None

    prev_line = None
    parsing_mon = False
    mon_index = 0

    for line in parties:
        if "REGULAR TRAINERS END" in line:
            break

        if "Name" in line:
            trainer_name = line.split(':')[1].strip()
        elif "Class" in line:
            trainer_class = line.split(':')[1].strip()
            trainer = Trainer()
            trainer.name = trainer_class + " " + trainer_name
        elif "=== TRAINER_" in line and prev_line == '\n':
            trainer_parties.append(trainer)
        elif "=== TRAINER_" not in line and prev_line == '\n':
            parsing_mon = True
            pokemon = Pokemon()
            parts = line.split('@')
            pokemon.species = parts[0].strip()

            if len(parts) > 1: # Check if there's a second part (i.e., an item)
                pokemon.item = parts[1].strip()
            else:
                pokemon.item = None # Assign None if no item is present
        if parsing_mon:
            if line == "\n":
                parsing_mon = False
                pokemon.index = mon_index
                mon_index += 1
                trainer.party.append(pokemon)
            elif "Ability:" in line:
                pokemon.ability = line.split(':')[1].strip()
            elif "Level:" in line:
                pokemon.level = line.split(':')[1].strip()
            elif "Tera Type:" in line:
                pokemon.teraType = line.split(':')[1].strip()
            elif "Status:" in line:
                pokemon.status = line.split(':')[1].strip()
            elif "Nature:" in line:
                pokemon.nature = line.split(':')[1].strip()
            elif "IVs:" in line:
                pokemon.ivs = line.split(':')[1].strip()
                ivs_str = []
                for i in pokemon.ivs.split(" / "):
                    ivs_str.append(i.split(" ")[0].strip())
                ivs = {"hp": int(ivs_str[0]),
                       "at": int(ivs_str[1]),
                       "df": int(ivs_str[2]),
                       "sa": int(ivs_str[3]),
                       "sd": int(ivs_str[4]),
                       "sp": int(ivs_str[5]),}
                pokemon.ivs = ivs
            elif "- " in line:
                pokemon.moves.append(line[1:].strip())

        prev_line = line

    return trainer_parties


def delete_file(file):
    if os.path.exists(file):
        os.remove(file)


def get_party_contents():
    with open(SOURCE, 'r') as file:
        return file.readlines()


if __name__ == "__main__":
    parsed_trainers = parse_parties(get_party_contents())

    delete_file(MASTERSHEET)
    write_to_file(generate_mastersheet(parsed_trainers), MASTERSHEET)

    delete_file(CALC_SETS)
    write_to_file(generate_cals_sets(parsed_trainers), CALC_SETS)
