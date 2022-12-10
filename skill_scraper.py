import json
import random
import re
import time

import typer

from parsel import Selector

import selenium.webdriver.chrome.webdriver
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ENV_RESOURCES = "resources/"


def initialize_web_scraper() -> selenium.webdriver.chrome.webdriver.WebDriver:
    """
    Initialize an instance of the selenium webdriver
    """
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options=chrome_options)

    return driver


def linkedin_login(
    driver: selenium.webdriver.chrome.webdriver.WebDriver, credentials: dict
):
    """
    Log in to LinkedIn with the selenium webdriver instance, since skills information
    isn't available in the public view.

    :param driver: the selenium webdriver instance
    :param credentials: the credentials that will be used to log in (username/password)
    :return:
    """
    # need to log in to LinkedIn since skills aren't available in the public view
    driver.get("https://www.linkedin.com/")

    # wait until relevant website elements are visible before trying to interact further
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_all_elements_located((By.CLASS_NAME, "input__input"))
        )
    except TimeoutException:
        pass

    # login with LinkedIn credentials
    username_input = driver.find_element(By.CLASS_NAME, "input__input")
    username_input.send_keys(credentials["email"])
    # wait to not get banned by bot detection
    time.sleep(random.choice(range(7)))
    password_input = driver.find_element(By.ID, "session_password")
    password_input.send_keys(credentials["password"])
    # wait again to not get banned
    time.sleep(random.choice(range(7)))

    # clicking on the login button
    log_in_button = driver.find_element(By.CLASS_NAME, "sign-in-form__submit-button")
    log_in_button.click()
    time.sleep(random.choice(range(7)))

    # if asked for verification wait for human intervention
    if not re.search(r"^https://www.linkedin.com/feed/", driver.current_url):
        input(f"LinkedIn verification step detected. Waiting for human input...")

    return


def get_user_profiles(
    driver: selenium.webdriver.chrome.webdriver.WebDriver,
    job_query: list[str],
    full_automation: bool,
    num_pages: int = 10,
) -> list[str]:
    """
    Use Google to get LinkedIn profiles related to a particular type of job
    (e.g. Data Science)

    :param driver: the selenium webdriver instance
    :param job_query: a list of strings containing the types of jobs to look for
    :param full_automation: whether the instance should wait for a human to deal with
        bot detection. If False, will wait ~2 hours after scraping every 5 pages of
        results to try to get around Google's advanced query flagging system. Otherwise,
        will scrape as many pages as quickly as possible and rely on a human to do the
        bot detection test
    :param num_pages: how many pages of Google search results to scrape
    :return:
    """
    # look for profiles related to the job type
    driver.get("https://www.google.com")

    # wait for search box to become interactable
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_all_elements_located((By.NAME, "q"))
        )
    except TimeoutException:
        pass

    # quote the specific terms we want to find related to our job and find relevant profiles on Google
    quoted_query = [f"\"{search_term}\"" for search_term in job_query]
    search_query = " AND ".join(["site:linkedin.com/in/"] + quoted_query)

    print(f"Looking for jobs on LinkedIn with the query {search_query}")

    search_box = driver.find_element(By.NAME, "q")
    search_box.send_keys(search_query)
    search_box.send_keys(Keys.ENTER)

    # get the LinkedIn URLs for each profile on each Google search result page
    all_profile_urls = []
    for page in range(num_pages):
        try:
            # Google advanced searches are rate limited
            if full_automation and page % 5 == 0:
                time.sleep(7200)

            # manually handle bot detection
            while re.search(r"google.com/sorry/", driver.current_url):
                input(f"Google bot detection page. Waiting for user input...")

            # wait for user profile URLs to appear before getting them
            try:
                WebDriverWait(driver, 10).until(
                    EC.visibility_of_all_elements_located(
                        (By.XPATH, '//div[@class="yuRUbf"]/a[@href]')
                    )
                )
            except TimeoutException:
                pass

            linkedin_users_urls_list = driver.find_elements(
                By.XPATH, '//div[@class="yuRUbf"]/a[@href]'
            )
            [
                all_profile_urls.append(profile.get_attribute("href"))
                for profile in linkedin_users_urls_list
                if re.search(
                    r"linkedin.com", profile.get_attribute("href"), flags=re.IGNORECASE
                )
            ]

            time.sleep(random.choice(range(12)))

            next_page_button = driver.find_element(By.ID, "pnnext")
            next_page_button.click()

        # save user profiles if bot detection can't be handled
        except TimeoutException as error:
            raise error

        finally:
            with open(ENV_RESOURCES + "user_profile_urls.txt", "a+") as outfile:
                outfile.write("\n".join(all_profile_urls))

    return all_profile_urls


def scrape_skills(
    driver: selenium.webdriver.chrome.webdriver.WebDriver, profile_url
) -> set[str]:
    """
    Get the skills from a particular LinkedIn profile

    :param driver: the selenium webdriver instance
    :param profile_url: a scraped LinkedIn profile URL
    :return:
    """
    # navigate to the LinkedIn profile
    formatted_profile_url = profile_url.strip().removesuffix("/")
    driver.get(formatted_profile_url)
    time.sleep(10)

    # handle if LinkedIn detects selenium webdriver
    standardized_profile_url = re.sub(
        r"(?<=https://).*(?=\.linkedin)", "www", formatted_profile_url
    )
    try:
        standardized_profile_url = re.search(
            r"https://www\.linkedin\.com/in/[A-Za-z0-9-]+",
            standardized_profile_url,
            flags=re.IGNORECASE,
        ).group(0)
    except AttributeError:
        print(f"Profile {formatted_profile_url} has an unexpected format. Skipping...")
        return set()

    compiled_profile_regex = re.compile(
        fr"{standardized_profile_url}|{formatted_profile_url}", flags=re.IGNORECASE
    )
    discovered_profile_url = re.search(
        compiled_profile_regex, driver.current_url.removesuffix("/")
    )
    while not discovered_profile_url:
        discovered_profile_url = re.search(
            compiled_profile_regex, driver.current_url.removesuffix("/")
        )
        input(f"LinkedIn verification step detected. Waiting for human input...")

    # find the url to get to the skills page and navigate there
    profile_selector = Selector(text=driver.page_source)
    skills_url_pattern = re.compile(
        "(?<=href=\")https://[a-z]{2,3}\.linkedin\.com/.*/details/skills\?.*(?=\">)",
        flags=re.IGNORECASE,
    )
    skills_page_url = profile_selector.xpath(
        "//div[@class='pvs-list__footer-wrapper']/div[@class]/a[@class][@href][@target]"
    ).re(skills_url_pattern)

    if skills_page_url:
        driver.get(skills_page_url[0])
    else:
        raise IndexError("No skill card found")

    # get the skills listed in the profile
    skills_text_pattern = re.compile(
        fr"(?<=<span aria-hidden=\"true\"><!---->).*(?=<!----></span>)"
    )
    skills_selector = Selector(text=driver.page_source)
    skills_list = skills_selector.xpath(
        "//span[@class='mr1 hoverable-link-text t-bold']/span[@aria-hidden='true']"
    ).re(skills_text_pattern)

    return set(skills_list)


def main(
    num_pages: int = typer.Argument(
        5, help="number of Google pagination actions to attempt"
    ),
    credentials: str = typer.Option(
        None, help="a JSON containing credentials to log into LinkedIn with"
    ),
    full_automation: bool = typer.Option(
        False,
        help="prompt the user when an unforeseen state occurs (bot detection from LinkedIn and Google)",
    ),
    restart: bool = typer.Option(
        False,
        help="attempt to restart a previous run with user_profiles and/or scraped_skills files",
    ),
    job_query: list[str] = typer.Option(
        None,
        help=(
            "job terms to search for. multiple job terms can be used as part of the search query; "
            "prepend each term with a --job_query flag"
        ),
    ),
):

    if not job_query and not restart:
        raise ValueError(
            "At least one job query term needs to be provided if starting from scratch"
        )

    if not credentials:
        credentials = "credentials.json"

    driver = initialize_web_scraper()
    try:
        with open(credentials, "r") as infile:
            credentials = json.load(infile)
    except FileNotFoundError:
        raise FileNotFoundError("Could not find a credentials file containing LinkedIn")

    linkedin_login(driver, credentials)

    if not restart:
        user_profiles = get_user_profiles(driver, job_query, full_automation, num_pages)
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
                scraped_skills = scrape_skills(driver, user_profile)

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

    return
