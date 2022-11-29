import multiprocessing
import json


def get_skill_text(file_path: str, skill_dict_key: str) -> list:
    skills_objs = []
    with open(file_path, "r") as infile:
        for obj in infile:
            skills_dict = json.loads(obj)
            skills_objs.append(tuple(skills_dict[skill_dict_key]))

    return skills_objs


def parse_skills_pattern(*args):
    text_elements = []
    for pattern_dict in args:
        for key in pattern_dict.keys():
            text_elements.append(pattern_dict[key])
    if len(text_elements) == 1:
        return text_elements[0]
    else:
        return " ".join(text_elements)


def parse_jsonl_skills(skills_objs):
    skills_list = []
    with multiprocessing.Pool() as pool:
        for skill in pool.starmap(
            parse_skills_pattern, skills_objs
        ):
            skills_list.append(skill.strip().lower())

    return skills_list