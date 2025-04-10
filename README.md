# Final Project
---
## 1. Describes the project. If you are doing a predefined project choice, explain how you implemented that specific choice. This description should match what you submitted as your project proposal. (4 points)

- Project idea: Scrape skills related to a specific job interest, and train a language 
model to recognize those skills and identify them in a resume context. Then generate
a prompt to be submitted to GPT-3 or ChatGPT to have those language models create a
cover letter.
---
## 2. Explains in a few sentences why you selected this project, and if you learned what you had hoped to learn by doing this project (from your proposal). Explain. (4 points)

- Interest: Natural Language Processing is an incredibly versatile tool that’s used for everything from ordinary text parsing to categorizing functional genomic regions in gene sequence data. The flexibility and utility of NLP is something that I want to learn to utilize, and using it to generate a relatively standardized text output. 
- What I learned: I gained familiarity with the data types/formats that are commonly used in the NLP space. Learned how to use spaCy and NLTK Python libraries. I also became more familiar with common complications in the space of generating testing/training data.
---
## 3. What you would do differently if you were to have an opportunity to redo this project and why. (4 points)

1. Instead of designing my own training loop, I probably would've taken advantage of the
config based training that spaCy v3.0 suggests using now. I used the old method because
I wanted to gain additional familiarity with OOP and also see how the industry standard of
OOP appears to 3rd party developers. 

2. I would also create a much more robust training set. Currently, the "trained" model is very
bad at distinguishing the barriers between skills. For example, if there is a list of skills in
the resume separated by bullet points, spaCy tries to interpret the entire bulleted list as a
single entity.
---
## 4. How to run your project. (4 points)
- Step 0: install java 7 or 7+ runtime for tika if java isn't already installed (try `java --version`) (one of the dependencies) [instructions here](https://docs.oracle.com/javase/7/docs/webnotes/install/mac/mac-jdk.html)
- Step 1: install poetry if not already on system (follow the instructions here: [poetry docs](https://python-poetry.org/docs/)
- Step 2: initialize a `pyproject.toml` file with `poetry init`
- Step 3: install dependencies with `poetry install`

Please see the `--help` option for `main.py` for detailed instructions on use (including use of LinkedIn scraper). 
**Following steps will be basic usage steps using the pre-generated skills file**) 
- Step 4: parse resume and generate autogenerated prompt
`python cv_prompt_generator.py [PATH_TO_RESUME] [COMPANY_TO_SUBMIT_TO] [ROLE_APPLYING_TO] --job-query [PHRASE_RELATED_TO_JOB] --job-query [PHRASE_RELATED_TO_JOB]`

Example: `python cv_prompt_generator.py Resume.pdf 23andMe Bioinformatician --job-query "Data Science" --job-query "Bioinformatics"`
---
## 5. Was the project challenging in the way you expected? What did you overcome? (4 points)
Project was incredibly challenging. Some of the problems I encountered were:
- Getting a skills data set. Initial idea was to use LinkedIn API but investment needed was too high. Eventually decided to combine scraping LinkedIn with using JobZilla's JSONL
- Populating an appropriate training data set. Using an idea from the blog on NER, I used sentence templates which I filled with scraped skills
- Parsing a PDF into a Python string. Tried multiple different non-standard library solutions until I discovered Tika which is easy to start up and implement.
---
## 6. Cited sources, appropriate acknowledgements. Explain how each source applied to your project. (5 points)
- [spaCy Documentation](https://spacy.io/): Helped me figure out how to build and train a NLP model. Special interest given to Language Processing Pipelines page for telling me what each component of the spaCy model did.
- [Blog on Named Entity Recognition](https://ner.pythonhumanities.com/03_02_train_spacy_ner_model.html): Helped me understand the concept of Named Entity Recognition (NER)
- [Blog on Catastrophic Forgetting](https://explosion.ai/blog/pseudo-rehearsal-catastrophic-forgetting): Blog detailing the catastrophic forgetting problem and how the solution is easier than one might think
- [Blog on Selenium and Scraping LinkedIn](https://medium.com/featurepreneur/how-to-build-a-web-scraper-for-linkedin-using-selenium-and-beautifulsoup-94ab717d69a0): Blog that got me started on using Selenium. I did not end up using BeautifulSoup
---
