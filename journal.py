"""Entry point for journal templating script"""
# pylint: disable=C0116,C0103,W0621

from datetime import datetime, timedelta
import platform
import re
import subprocess
import json
import random
from os import path, remove
import argparse
from pandas import read_csv, to_datetime


script_dir = path.dirname(path.abspath(__file__))
reference_dir = "personal/"
stoics_file = "stoics.csv"
stoices_progress_file = "stoic_progress.json"
tarot_file = "tarot.csv"
TAROT_CSV = path.join(script_dir, reference_dir + tarot_file)
TAROT_SKIP_COLUMNS = set({'Group', 'Up', 'Across', 'Down'})
TAROT_COLUMN_MAX_LEN = 30
STOIC_CSV = path.join(script_dir, reference_dir + stoics_file)
STOIC_PROGRESS = path.join(script_dir, reference_dir + stoices_progress_file)
STOIC_CATCHUP_RATE = 2

questions_file = "questions.txt"
QUESTIONS_TXT = path.join(script_dir, reference_dir + questions_file)

global_wordcount_goal = 750
morning_start_hour = 4
afternoon_start_hour = 12
evening_start_hour = 17


parser = argparse.ArgumentParser(description="the command line options for journal.py")
parser.add_argument("-a", "--all", default=False, action='store_true',
                    help="add everything (equivalent: -qts)")
parser.add_argument("-q", "--questions", default=False, action='store_true',
                    help="add questions.txt when creating an entry", )
parser.add_argument("-t", "--tarot", default=False, action='store_true',
                    help="pull a tarot card and insert it into the entry")
parser.add_argument("-s", "--stoic-prompt", default=False, action='store_true',
                    help="add prompts from stoic CSV file")
parser.add_argument("-T", "--test", default=False, action='store_true',
                    help="run in test mode, create file in ~ instead of normal location")
# TODO: add -P for print() only testing
parser.add_argument("-M", "--do-not-move-stoics", default=False, action='store_true',
                    help="move stoic questions below #EveningPages / end of entry")

args = vars(parser.parse_args())

if args['all']:
    args['questions'] = True
    args['tarot'] = True
    args['stoic_prompt'] = True


def stoic_json_get_progress() -> int:
    """ Read progress from JSON file or start from beginning if not found. """
    try:
        with open(STOIC_PROGRESS, 'r', encoding='utf-8') as file:
            progress = json.load(file)
            date = datetime.strptime(progress['updated_on'], '%Y-%m-%d')
            return {"day": progress['day'], "updated_on": date}
    except (FileNotFoundError, KeyError):
        return {"day": 1, "updated_on": datetime(2024, 1, 1)}


def stoic_json_set_progress(progress: dict) -> None:
    """ Save progress if applicable """
    if datetime.now().date() != progress['updated_on'].date():
        new_progress = {
            "day": progress['day'],
            "updated_on": datetime.now().strftime('%Y-%m-%d')
        }
        if args['test']:
            print("json.dump:", new_progress)
            return
        with open(STOIC_PROGRESS, 'w', encoding='utf-8') as file:
            json.dump(new_progress, file)


def get_stoic_entries() -> str:
    """Return the relevant entry from stoics.csv"""
    progress = stoic_json_get_progress()
    current_day = datetime.now().timetuple().tm_yday

    df = read_csv(STOIC_CSV)
    df['Date'] = to_datetime(df['Date'], format='%m/%d', errors='coerce')
    num_entries_to_load = 1
    if progress['day'] < current_day:
        num_entries_to_load = STOIC_CATCHUP_RATE

    result = "\n"
    for x in range(num_entries_to_load):
        day = progress['day'] + x
        entry = {}
        if any(df['Day'] == day):
            entry['date'] = df.loc[df['Day'] == day, 'Date'].iloc[0]
            entry['text'] = df.loc[df['Day'] == day, 'Question'].iloc[0]
        else:
            entry['date'] = ""
            entry['text'] = f"No entry for day {day}."
        result += f"- Daily Stoic Prompt, {entry['date'].strftime('%-m/%d')}:\n{entry['text']}\n"
        result += "\t- Morning:\n\t\t- \n\t- Evening:\n\t\t- \n"
    progress['day'] += num_entries_to_load
    stoic_json_set_progress(progress)
    return result


def pull_tarot_card() -> str:
    df = read_csv(TAROT_CSV, sep=",")
    card = random.choice(df['Card'])
    row = df[df['Card'] == card]
    row = row.squeeze()
    result = "Tarot: "
    skip = TAROT_SKIP_COLUMNS
    for column, value in row.items():
        if not isinstance(value, str) or column in skip:
            continue
        if len(value) > TAROT_COLUMN_MAX_LEN or value == "-" or value[-1] == ".":
            continue
        result += f"{value}, "
    return result[:-2] + "\n"


current_hour = int(datetime.now().strftime("%H"))
is_late_night = current_hour < morning_start_hour
is_morning = morning_start_hour < current_hour < afternoon_start_hour
is_afternoon = afternoon_start_hour < current_hour < evening_start_hour
is_evening = current_hour > evening_start_hour


def get_ia_writer_style_wordcount_from_string(content: str) -> int:
    content = re.sub(r'\- \[.\]', '', content)
    content = re.sub(r'[_:><\/=]', ' ', content)
    content = re.sub(r'[A-Za-z]/[A-Za-z]', ' ', content)
    content = re.sub(r'(\S)—(\S)', '\1 \2', content)
    content = re.sub(r'[&—-]', '', content)
    content = re.sub(r'([0-9])’([a-zA-Z])', r'\1 \2', content)
    content = re.sub(r' […\?]', '…', content)
    content = re.sub(r'(\S)[…](\S)', '\1 \2', content)
    content = re.sub(r'([a-zA-Z0-9])\.([a-zA-Z0-9])', r'\1 \2', content)
    return len(content.split())


def get_ia_writer_style_wordcount_from_entry() -> int:
    """Determine word count, approximating macOS iA Writer word count"""
    file_path = journal_info['entry_file_path']
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    return get_ia_writer_style_wordcount_from_string(content)


ordinal_strings = {
    1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th", 7: "7th", 8: "8th",
    9: "9th", 10: "10th", 11: "11th", 12: "12th", 13: "13th", 14: "14th", 15: "15th",
    16: "16th", 17: "17th", 18: "18th", 19: "19th", 20: "20th", 21: "21st", 22: "22nd",
    23: "23rd", 24: "24th", 25: "25th", 26: "26th", 27: "27th", 28: "28th", 29: "29th",
    30: "30th", 31: "31st"
}


journal_info = {}
if is_late_night:
    journal_info['timestamp_hhmm'] = str(2400 + int(datetime.now().strftime("%H%M")))
else:
    journal_info['timestamp_hhmm'] = datetime.now().strftime("%H%M")


def generate_title(base_date: datetime) -> str:
    """Generates title, format is: "YYYYMMDD Day of the week the DDth of Month"."""
    return base_date.strftime(f"%Y%m%d %A the {ordinal_strings[base_date.day]} of %B")


if is_late_night:
    journal_info['title_now'] = generate_title(datetime.now() - timedelta(days=1))
    weeks_ago_string = generate_title(datetime.now() - timedelta(weeks=8, days=1))
    journal_info['title_now_8_weeks_ago'] = weeks_ago_string
else:
    journal_info['title_now'] = generate_title(datetime.now())
    journal_info['title_now_8_weeks_ago'] = generate_title(datetime.now() - - timedelta(weeks=8))

cur_os = platform.system()
if cur_os == "Darwin":
    path_string = "~/Library/Mobile Documents/27N4MQEA55~pro~writer/Documents/Morning Pages"
    journal_info['path'] = path.expanduser(path_string)
    journal_info['editor_subprocess'] = ["open", "-a", "iA Writer"]
elif cur_os == "Windows":
    journal_info['path'] = path.expanduser("~/iCloudDrive/27N4MQEA55~pro~writer/Morning Pages")
    journal_info['editor_subprocess'] = [r'C:\Program Files\iA Writer\iAWriter.exe']
else:
    raise ValueError("This script only meant for macOS (Darwin) and Windows at this time")


if args['test']:
    journal_info['path'] = path.expanduser("~")
journal_info['entry_file_path'] = journal_info['path'] + "/" + journal_info['title_now'] + ".txt"
journal_info['editor_subprocess'].append(journal_info['entry_file_path'])


def create_morning_content() -> str:
    initial_content = f"""{journal_info['title_now']}\n"""
    initial_content += f"""#MorningPages, started at {journal_info['timestamp_hhmm']}\n"""
    initial_content += "\n\n\nGoal WC: MORNINGWORDCOUNT\n"
    if args['tarot']:
        initial_content += f"{pull_tarot_card()}\n"
    if args['questions']:
        initial_content += get_questions_not_in_entry()
    if args['stoic_prompt']:
        initial_content += get_stoic_entries()
    current_wc = get_ia_writer_style_wordcount_from_string(initial_content)
    goal_wc = current_wc + global_wordcount_goal
    initial_content = initial_content.replace("MORNINGWORDCOUNT", str(goal_wc))
    return initial_content


def create_entry(content: str) -> None:
    if args['test']:
        print(content)
        # return
    with open(journal_info['entry_file_path'], 'w', encoding='utf-8') as file:
        file.write(content)


def open_editor(cmd: list) -> None:
    print(" ".join(cmd[0:-1]) + f" \"{cmd[-1]}\"")
    subprocess.run(cmd, check=False)


def update_entry_with_new_content(new_content, expected_ending, exclusion_re=None) -> None:
    content = ""
    with open(journal_info['entry_file_path'], "r", encoding="utf-8") as file:
        content = file.read()
    if exclusion_re and re.search(exclusion_re, content, flags=re.MULTILINE):
        return
    if not content.endswith("\n\n"):
        content += expected_ending
    content += new_content
    if args['test']:
        print(content)
        # return
    with open(journal_info['entry_file_path'], "w", encoding="utf-8") as file:
        file.write(content)


def get_questions_not_in_entry() -> str:
    content = ""
    question_list = []
    with open(QUESTIONS_TXT, "r", encoding="utf-8") as file:
        for line in file:
            question_list.append(line)
    if path.exists(journal_info['entry_file_path']):
        with open(journal_info['entry_file_path'], "r", encoding='utf-8') as file:
            for line in file:
                if ":" in line:
                    line = line.split(":")[0] + ":\n"
                if line in question_list:
                    question_list.remove(line)
    content = re.sub(r":\n", ": \n", "".join(question_list), flags=re.MULTILINE)
    return content


def get_evening_update_string() -> str:
    content = f"\n#EveningPages, started at {journal_info['timestamp_hhmm']}\n\n\n\n"
    current_wc = get_ia_writer_style_wordcount_from_string(content)
    current_wc += get_ia_writer_style_wordcount_from_entry()
    goal_wordcount = str(current_wc + 750 + 3)
    content += f"Goal WC: {goal_wordcount}"
    return content


def get_content_and_cut_dictionary(file_path, start, end_non_inclusive) -> dict:
    start_pattern = rf"({start}.*?)"
    end_pattern = rf"({end_non_inclusive}.*?)"
    cut_section = []
    content = []
    cutting = False
    with open(file_path, 'r', encoding="utf-8") as file:
        content_list = file.readlines()
    count = 0
    for line in content_list:
        count += 1
        if not cutting and re.match(start_pattern, line):
            print("Cutting at line " + str(count))
            cutting = True
        if re.match(end_pattern, line):
            cutting = False
        if cutting:
            cut_section.append(line)
        else:
            content.append(line)
    return {"content": "".join(content), "cut": "".join(cut_section)}


def move_stoics_to_end():
    cut_section = get_content_and_cut_dictionary(journal_info['entry_file_path'],
                                                 r"^- Daily Stoic Prompt,.*", r"^#EveningPages.*")
    with open(journal_info['entry_file_path'], 'w', encoding="utf-8") as file:
        file.write(cut_section['content'] + "\n\n")
        file.write(cut_section['cut'])


def main() -> None:
    if path.exists(journal_info['entry_file_path']):
        if is_evening or is_late_night:
            update_entry_with_new_content(get_evening_update_string(), "\n", r"^#EveningPages.*")
            if not args['do_not_move_stoics']:
                move_stoics_to_end()
        if args['tarot']:
            update_entry_with_new_content(pull_tarot_card(), "\n", r"^Tarot:.+$")
        if args['questions']:
            update_entry_with_new_content(get_questions_not_in_entry(), "\n")
        if args['stoic_prompt']:
            update_entry_with_new_content(get_stoic_entries(), "\n", r"^- Daily Stoic Prompt,.*")
    else:
        initial_content = create_morning_content()
        create_entry(initial_content)
    if not args['test']:
        open_editor(journal_info['editor_subprocess'])


main()

if args['test']:
    do_delete = False
    if do_delete:
        print("safe to delete file? if not, hit ctrl-C")
        input()
        print("removing " + journal_info['entry_file_path'])
        remove(journal_info['entry_file_path'])
    else:
        if path.exists(journal_info['entry_file_path']):
            print("not deleting " + journal_info['entry_file_path'])
        else:
            print(json.dumps(journal_info, indent=4, sort_keys=True))
