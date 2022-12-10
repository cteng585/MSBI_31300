import random
import re
from typing import Tuple


def make_prompt_sentence(
    skill_list: list, start_string: str, end_string: str = "", num_choices: int = 3
) -> Tuple[str, int]:
    """
    write a string about skills the user is experienced in

    :param skill_list: a list of skill strings to randomly select skills from
    :param num_choices: the number of skills that should be randomly sampled from the
        skills list
    :param start_string: the string to start the sentence with
    :param end_string: the string to end the sentence with
    :return: a string summarizing random skills and an int with suggested number of
        skills to use in the next sentence
    """
    if num_choices > len(set(skill_list)):
        num_choices = len(set(skill_list))

    # de-duplicate. random.sample will be deprecated for set so use a list
    formatted_skill_list = [
        re.sub(r"[^a-z0-9^+# ]", "", skill, flags=re.IGNORECASE)
        for skill in skill_list
        if re.sub(r"[^a-z0-9^+# ]", "", skill, flags=re.IGNORECASE)
    ]
    random_skills = random.sample(list(set(formatted_skill_list)), k=num_choices)

    output_string = start_string
    for formatted_skill in random_skills[:-1]:
        output_string += f"{formatted_skill}"
        if len(random_skills) > 2:
            output_string += ", "
        else:
            output_string += " "

    output_string += f"and {random_skills[-1]}"

    if end_string:
        output_string += end_string
    else:
        output_string += "."

    return output_string, num_choices - 1
