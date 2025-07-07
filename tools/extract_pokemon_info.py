import re
import csv
import pathlib

def clean_value(value, prefix):
    """Removes a specified prefix and formats the string."""
    return value.replace(prefix, '').replace('_', ' ').title()

def resolve_stat_value(value_str, file_content):
    """Recursively resolves a stat value, handling numbers, conditionals, and macros."""
    value_str = value_str.strip()
    if value_str.isdigit():
        return int(value_str)
    
    if 'P_UPDATED_STATS' in value_str:
        match = re.search(r'\?\s*(\d+)', value_str)
        return int(match.group(1)) if match else 0
        
    macro_name = value_str
    define_pattern = re.compile(fr'#define\s+{macro_name}\s+\(?(.*)\)?')
    define_match = define_pattern.search(file_content)
    
    if define_match:
        return resolve_stat_value(define_match.group(1), file_content)
    return 0

def get_data_block(block_content, file_content):
    """Recursively finds the actual '{...}' data block for a species, following macro definitions."""
    block_content = block_content.strip().lstrip('=').strip()
    if block_content.startswith('{'):
        return block_content

    macro_name_match = re.match(r'([A-Z0-9_]+)', block_content)
    if not macro_name_match:
        return None
    
    macro_name = macro_name_match.group(1)
    define_pattern = re.compile(fr'#define\s+{macro_name}(?:\(.*\))?\s+(.+)', re.DOTALL)
    define_match = define_pattern.search(file_content)

    if define_match:
        new_content = define_match.group(1).strip()
        if new_content == block_content: return None # Avoid infinite loops
        return get_data_block(new_content, file_content)
    return None

def find_top_level_braces(text):
    """A robust helper function to find top-level '{...}' blocks in a string, respecting nesting."""
    blocks = []
    brace_level = 0
    current_block = ""
    in_block = False
    for char in text:
        if char == '{':
            if brace_level == 0:
                in_block = True
            brace_level += 1
        
        if in_block:
            current_block += char
            
        if char == '}':
            brace_level -= 1
            if brace_level == 0 and in_block:
                blocks.append(current_block)
                current_block = ""
                in_block = False
    return blocks

def parse_and_simplify_evolutions(evo_string):
    """Parses the raw evolution data and simplifies it into a readable string."""
    if not evo_string:
        return ""
    
    # Use the robust brace finder to handle nested structures like CONDITIONS
    evolutions = find_top_level_braces(evo_string)
    simplified_evos = []

    for evo in evolutions:
        # Use regex to safely extract the first three parts of an evolution
        main_parts_match = re.match(r'{\s*(\w+)\s*,\s*([\w\d]+)\s*,\s*(\w+)', evo)
        if not main_parts_match:
            continue
        
        method, param, target_species_raw = main_parts_match.groups()
        target_species = target_species_raw.replace('SPECIES_', '').replace('_', ' ').title()

        # Check for conditions in the full evolution string
        if 'CONDITIONS' in evo:
            if 'IF_MIN_FRIENDSHIP' in evo:
                simplified_evos.append(f"{target_species} (Happiness)")
            elif 'IF_HELD_ITEM' in evo and method == 'EVO_LEVEL':
                item_match = re.search(r'ITEM_(\w+)', evo)
                item_name = item_match.group(1).replace('_', ' ').title() if item_match else "Held Item"
                simplified_evos.append(f"{target_species} ({item_name}, Level Up)")
            else:
                simplified_evos.append(target_species)
        # Handle non-conditional evolutions
        else:
            if method == 'EVO_LEVEL' and param != '0':
                simplified_evos.append(f"{target_species} ({param})")
            elif method == 'EVO_ITEM':
                item_name = param.replace('ITEM_', '').replace('_', ' ').title()
                simplified_evos.append(f"{target_species} ({item_name})")
            elif method == 'EVO_TRADE':
                trade_evo = f"{target_species} (Trade)"
                if 'HELD_ITEM' in evo:
                    item_match = re.search(r'ITEM_(\w+)', evo)
                    if item_match:
                        item_name = item_match.group(1).replace('_', ' ').title()
                        trade_evo = f"{target_species} (Trade, {item_name})"
                simplified_evos.append(trade_evo)
            elif method == 'EVO_LEVEL' and param == '0':
                simplified_evos.append(target_species)

    return ", ".join(simplified_evos)

def parse_pokemon_data(input_filename, file_content):
    """Parses a C header file's content for Pokémon data."""
    gen_match = re.search(r'gen_(\d+)', input_filename.name)
    generation = gen_match.group(1) if gen_match else 'Unknown'
    pokemon_data_list = []
    
    stat_names_map = {'HP': 'baseHP', 'Attack': 'baseAttack', 'Defense': 'baseDefense', 'Speed': 'baseSpeed', 'Sp Attack': 'baseSpAttack', 'Sp Defense': 'baseSpDefense'}
    pokemon_blocks = re.split(r'\[(SPECIES_\w+)\]', file_content)
    
    for i in range(1, len(pokemon_blocks), 2):
        species_name_raw = pokemon_blocks[i]
        original_block = pokemon_blocks[i+1]
        data_block = get_data_block(original_block, file_content)
        if not data_block: continue

        name_match = re.search(r'\.speciesName\s*=\s*_\("([^"]+)"\)', data_block)
        name = name_match.group(1) if name_match else ""
        form = ""
        if name:
            base_name_in_enum = name.upper().replace('-', '_').replace(' ', '_').replace("'", "").replace(".", "")
            form_raw = species_name_raw.replace('SPECIES_', '', 1).replace(base_name_in_enum, '', 1)
            form = form_raw.strip('_').replace('_', ' ').title()

        base_stats = {key: resolve_stat_value(m.group(1), file_content) if (m := re.search(fr'\.{c_name}\s*=\s*(.*?),', data_block)) else 0 for key, c_name in stat_names_map.items()}
        bst = sum(base_stats.values())

        types_match = re.search(r'\.types\s*=\s*MON_TYPES\((.*?)\)', data_block)
        type1, type2, types_formatted = '', '', ''
        if types_match:
            types_raw = [t.strip() for t in types_match.group(1).split(',')]
            cleaned_types = [clean_value(t, 'TYPE_') for t in types_raw]
            types_formatted = ', '.join(cleaned_types)
            type1, type2 = (cleaned_types + [''])[:2]

        abilities_content = ""
        if (updated_abilities_match := re.search(r'#if P_UPDATED_ABILITIES.*?\.abilities\s*=\s*\{(.*?)\}.*?#else', data_block, re.DOTALL)):
            abilities_content = updated_abilities_match.group(1)
        elif (regular_abilities_match := re.search(r'\.abilities\s*=\s*\{(.*?)\}', data_block, re.DOTALL)):
            abilities_content = regular_abilities_match.group(1)

        ability1, ability2, hidden_ability, abilities_formatted = '', '', '', ''
        if abilities_content:
            abilities_raw = [a.strip() for a in abilities_content.split(',') if a.strip()]
            cleaned_abilities = [clean_value(a, 'ABILITY_') for a in abilities_raw]
            abilities_formatted = ', '.join(cleaned_abilities)
            ability1, ability2, hidden_ability = (cleaned_abilities + [''] * 3)[:3]

        evo_match = re.search(r'\.evolutions\s*=\s*(EVOLUTION\(.*?\))\s*,', data_block, re.DOTALL)
        evolutions = parse_and_simplify_evolutions(evo_match.group(1)) if evo_match else ""

        pokemon_data_list.append({
            'Name': name, 'Form': form, 'HP': base_stats.get('HP', 0), 'Attack': base_stats.get('Attack', 0),
            'Defense': base_stats.get('Defense', 0), 'Speed': base_stats.get('Speed', 0),
            'Sp Attack': base_stats.get('Sp Attack', 0), 'Sp Defense': base_stats.get('Sp Defense', 0), 'BST': bst,
            'Types': types_formatted, 'Type1': type1, 'Type2': type2, 'Abilities': abilities_formatted,
            'Ability1': ability1, 'Ability2': ability2, 'HiddenAbility': hidden_ability, 'Generation': generation,
            'Evolutions': evolutions
        })
    return pokemon_data_list, generation

def write_to_csv(data, output_filename):
    """Writes a list of Pokémon data to a single CSV file."""
    if not data:
        print("No data to write to CSV.")
        return
    
    headers = ['Name', 'Form', 'HP', 'Attack', 'Defense', 'Speed', 'Sp Attack', 'Sp Defense', 'BST', 'Types', 'Type1', 'Type2', 'Abilities', 'Ability1', 'Ability2', 'HiddenAbility', 'Generation', 'Evolutions']
    try:
        with open(output_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)
        print(f"\n✅ Successfully generated combined data file: '{output_filename}'")
    except IOError:
        print(f"Error: Could not write to the file '{output_filename}'.")

# --- Main Execution ---
if __name__ == "__main__":
    script_dir = pathlib.Path(__file__).parent
    input_dir = script_dir.parent / 'src' / 'data' / 'pokemon' / 'species_info'
    file_pattern = 'gen_*_families.h'
    output_filename = 'pokemon_data_all_gens.csv'
    output_file_path = script_dir / output_filename
    
    all_pokemon_data = []
    files_to_process = sorted(input_dir.glob(file_pattern))

    if not files_to_process:
        print(f"❌ Error: No files found matching '{file_pattern}' in '{input_dir}'")
    else:
        print(f"🔍 Found {len(files_to_process)} files to process in '{input_dir}'")
        for file_path in files_to_process:
            print(f"  -> Processing '{file_path.name}'...")
            try:
                content = file_path.read_text(encoding='utf-8')
                pokemon_data_from_file, _ = parse_pokemon_data(file_path, content)
                if pokemon_data_from_file:
                    all_pokemon_data.extend(pokemon_data_from_file)
            except Exception as e:
                print(f"    ‼️ Could not process file {file_path.name}. Error: {e}")

        if all_pokemon_data:
            write_to_csv(all_pokemon_data, output_file_path)
        else:
            print("No Pokémon data was extracted from any of the files.")