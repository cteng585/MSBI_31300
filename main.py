import json
import random
import time

import typer

import model
import prompt
import resume_parser
import skill_scraper

ENV_RESOURCES = "resources/"


def main(
    resume_path: str = typer.Argument(
        ..., help="path to resume. resume must be in PDF form"
    ),
    company_name: str = typer.Argument(..., help="company to submit CV to. wrap multiword companies in quotes"),
    role_name: str = typer.Argument(..., help="role at company to submit CV for. wrap multiword roles in quotes"),
    job_query: list[str] = typer.Option(
        ...,
        help=(
            "job tags applicable to the position of interest. multiple job terms can be used; "
            "prepend each term with a --job_query flag. wrap each job term in quotes"
        ),
    ),
    recipient_role: str = typer.Option(
        "", help="role of person at company receiving CV"
    ),
    linkedin_scraper: bool = typer.Option(
        False,
        "--linkedin_scraper",
        help="flag to scrape LinkedIn for job relevant profiles  [default: False]",
    ),
    credentials: str = typer.Option(
        "",
        help=(
            "LinkedIn scraper argument. path to a credentials JSON. expected keys are 'email' and 'password' in "
            "plain text with corresponding values in plain text (yes this is unsecure, sue me). MUST BE PROVIDED "
            "IF ATTEMPTING TO SCRAPE LINKEDIN"
        ),
    ),
    num_pages: int = typer.Option(
        5,
        help="LinkedIn scraper option. number of Google pagination actions to attempt",
    ),
    restart: bool = typer.Option(
        False,
        "--restart",
        help=(
            "LinkedIn scraper option. attempt to restart a previous run with user_profiles and/or "
            "scraped_skills files.  [default: False]"
        ),
    ),
    full_automation: bool = typer.Option(
        False,
        "--full-automation",
        help=(
            "LinkedIn scraper option. prompt the user when an unforeseen state occurs "
            "(bot detection from LinkedIn and Google).  [default: False]"
        ),
    ),
):

    # -------------------------
    # | resume parser section |
    # -------------------------

    # turn the read in resume into a Python string (PDF format)
    resume_string = resume_parser.resume_parser(resume_path)

    # -----------------------
    # | web scraper section |
    # -----------------------

    # only use this part if the user wants to scrape additional, job relevant skills from
    # LinkedIn. time intensive and runs the risk of being flagged by bot detection
    if linkedin_scraper:
        scraper_driver = skill_scraper.initialize_web_scraper()
        try:
            with open(credentials, "r") as infile:
                credentials = json.load(infile)
        except FileNotFoundError:
            raise FileNotFoundError(
                "Could not find a credentials file containing LinkedIn"
            )
        except NameError:
            raise FileNotFoundError(
                "No credentials file was provided, but made to try to scrape LinkedIn"
            )

        skill_scraper.linkedin_login(scraper_driver, credentials)
        if not restart:
            user_profiles = skill_scraper.get_user_profiles(
                scraper_driver, job_query, full_automation, num_pages
            )
            all_relevant_skills = set()
        else:
            try:
                with open(ENV_RESOURCES + "user_profiles.txt", "r") as infile:
                    user_profiles = infile.readlines()
            except FileNotFoundError:
                raise FileNotFoundError("No user profiles record")

            try:
                with open(ENV_RESOURCES + "scraped_skills.txt", "r") as infile:
                    scraped_skills = infile.readlines()
                all_relevant_skills = set([skill.strip() for skill in scraped_skills])
            except FileNotFoundError:
                print("No file with previously scraped skills found, starting fresh")
                all_relevant_skills = set()

        # keep track of the profiles that have already been scraped
        scraped_profiles = []

        for user_profile in user_profiles:
            try:
                with open(ENV_RESOURCES + "scraped_skills.txt", "a+") as outfile:
                    time.sleep(random.choice(range(10)))
                    scraped_skills = skill_scraper.scrape_skills(
                        scraper_driver, user_profile
                    )

                    # only keep track of skills that haven't been seen before
                    new_skills = scraped_skills - all_relevant_skills

                    # dump scraped skills after every profile in case of exception
                    outfile.write("\n".join(new_skills))
                    if new_skills:
                        outfile.write("\n")
                    all_relevant_skills = all_relevant_skills.union(scraped_skills)
                    scraped_profiles.append(user_profile)

            except IndexError:
                continue

            finally:
                # dump profiles that haven't been scraped yet to reduce next restart's runtime in case of error
                skipped_profiles = list(set(user_profiles) - set(scraped_profiles))
                with open(ENV_RESOURCES + "user_profiles.txt", "w") as outfile:
                    outfile.write("".join(skipped_profiles))

    # -------------------------------------
    # |   spaCy model training section    |
    # -------------------------------------

    # generate test/train data from the scraped skills test file
    if not linkedin_scraper:
        print("Using previously generated resources/scraped_skills.txt file")
    skill_file = model.SkillFile(ENV_RESOURCES + "scraped_skills.txt")
    skill_file.length_split()

    # use a set sentence templates to randomly fill with skills and generate test/train
    # data
    sentence_templates = model.SentenceTemplate(
        ENV_RESOURCES + "skill_sentence_templates.txt"
    )
    test_skill_data, train_skill_data = sentence_templates.test_train_split(
        skill_file.skills_list
    )

    # generate revision data to train on to try to prevent catastrophic forgetting
    # problem
    revision_data = model.RevisionData(
        ENV_RESOURCES + "teddy_roosevelt_autobiography.txt"
    )
    revision_data.import_text()

    # generate the model, update it with skills, and evaluate it
    nlp = model.NLP()
    revision_sentences = nlp.get_sentences(revision_data.text)
    revision_sentences_trimmed = nlp.filter_sentences(revision_sentences)
    revision_data.revisions = nlp.predict_entities(revision_sentences_trimmed)

    test_revision_data, train_revision_data = revision_data.test_train_split()

    combined_training_data = [
        sentence for value in train_skill_data.values() for sentence in value
    ] + train_revision_data

    nlp.update_entity_recognition(combined_training_data, iterations=30)

    # get the skills from the resume
    # see if result from lower casing the resume string helps since training data
    # was lower case
    doc_1 = nlp.nlp(resume_string)
    user_name = None

    skills_list = []
    for entity in doc_1.ents:
        if entity.label_ == "SKILL" and len(entity.text.split(" ")) <= 2:
            skills_list.append(entity.text)
        if not user_name and entity.label_ == "PERSON" and entity.text:
            user_name = entity.text

    user_name_input = input(
        (
            f"The name to be used in the cover letter was found to be {user_name}. If this is correct, "
            "don't add any input and press ok/continue. Otherwise enter the correct name: "
        )
    )
    if user_name_input:
        user_name = user_name_input

    # -------------------
    # | prompt writing  |
    # -------------------

    skills_string_start = "I am experienced in "
    skills_string, choices_left = prompt.make_prompt_sentence(
        skills_list, skills_string_start
    )

    motivation_string_start = (
        "I am excited about this role because it will let me leverage my abilities in "
    )
    motivation_string_end = " to create impactful solutions."
    motivation_string, num_choices_left = prompt.make_prompt_sentence(
        skills_list,
        motivation_string_start,
        motivation_string_end,
        num_choices=choices_left,
    )

    field_of_interest = random.sample(list(set(job_query)), k=1)
    passion_string = f"I am passionate about solving problems at the intersection of {field_of_interest[0]} and social good."

    if recipient_role:
        imperative_statement = (
            f"Write a cover letter to {recipient_role} from {user_name} for a "
            f"{role_name} job at {company_name}."
        )
    else:
        imperative_statement = (
            f"Write a cover letter to {company_name} from {user_name} for a "
            f"{role_name} job at {company_name}."
        )

    gpt_prompt = " ".join([skills_string, motivation_string, passion_string])

    with open("auto_generated_prompt.txt", "w") as outfile:
        outfile.write(
            "\n".join(
                [
                    (
                        "# USE THE FOLLOWING AUTOGENERATED PROMPT AS A SUBMISSION TO GPT-3 OR CHATGPT TO GET YOUR "
                        "COVER LETTER\n"
                    ),
                    imperative_statement,
                    gpt_prompt,
                ]
            )
        )


if __name__ == "__main__":
    typer.run(main)
