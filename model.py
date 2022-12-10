import os
import re
import random
import warnings

import en_core_web_lg
from charset_normalizer import from_bytes
from spacy.training import Example
from spacy.util import compounding, minibatch

import jsonl_skill_parser


def decode_text(encoded_text: bytes) -> str:
    """
    helper function to detect the encoding of a string and decode to default
    string encoding

    :param encoded_text: the byte string to decode
    :return: the decoded byte string
    """
    return str(from_bytes(encoded_text).best())


class InputFile:
    """
    base class for different files
    """

    def __init__(self, file_path):
        self.__file_path = file_path

    @property
    def file_path(self):
        return self.__file_path


class SkillFile(InputFile):
    """
    a file containing skills data that will be used to create a training set
    """

    def __init__(self, file_path: str):
        """
        :param file_path: file path of a file containing skills data
        """
        super().__init__(file_path)
        self.__skills_list = self.parse_skills()
        self.__training_skills = None

    @property
    def skills_list(self):
        return self.__skills_list

    @property
    def training_skills(self):
        return self.__training_skills

    @training_skills.setter
    def training_skills(self, value):
        self.__training_skills = value

    def parse_skills(self) -> list:
        """
        read skill data from a file in. acceptable file formats are JSON Lines and raw text
        formatting specifications provided in README

        :return:
        """
        if re.search(r"\.jsonl$", self.file_path):
            skills_objs = jsonl_skill_parser.get_skill_text(self.file_path, "pattern")
            skills_list = jsonl_skill_parser.parse_jsonl_skills(skills_objs)

        elif re.search(r"\.txt$", self.file_path):
            with open(self.file_path, "rb") as infile:
                skills_list = [
                    decode_text(skill).strip().lower() for skill in infile.readlines()
                ]

        else:
            raise ValueError("Skill file is not formatted correctly")

        return list(set(skills_list))

    def length_split(self, proportions: tuple = (0.45, 0.30, 0.25)):
        """
        split the skills data based on how many "words" are in the skill (e.g. "Python"
        has one word whereas "database management" has two words)

        :param proportions: the weighting for the split
        :return:
        """
        # split the skills on how many words are in the skill name
        length_dict = {"one_word": [], "two_word": [], "multi_word": []}

        for skill in self.skills_list:
            if len(skill.split()) == 1:
                length_dict["one_word"].append(skill)
            elif len(skill.split()) == 2:
                length_dict["two_word"].append(skill)
            elif len(skill.split()) >= 3:
                length_dict["multi_word"].append(skill)

        # do an uneven split on skills depending on how many words are in the skill name to avoid bias
        # (ameliorate effect of spaCy training on using length of a token as a significant feature format
        # entity recognition)
        total_num_skills = sum([len(value) for value in length_dict.values()])
        [random.shuffle(length_dict[key]) for key in length_dict.keys()]

        one_word_proportion, two_word_proportion, multi_word_proportion = proportions

        train_one_word_skills = length_dict["one_word"][
            : round(one_word_proportion * total_num_skills)
        ]
        train_two_word_skills = length_dict["two_word"][
            : round(two_word_proportion * total_num_skills)
        ]
        train_multi_word_skills = length_dict["multi_word"][
            : round(multi_word_proportion * total_num_skills)
        ]
        training_skills = (
            train_one_word_skills + train_two_word_skills + train_multi_word_skills
        )

        print("1-worded skill entities: ", len(train_one_word_skills))
        print("2-worded skill entities: ", len(train_two_word_skills))
        print("3-or-more-worded skill entities: ", len(train_multi_word_skills))

        self.training_skills = training_skills


class SentenceTemplate(InputFile):
    """
    templates that are used to generate testing/training data sets
    """

    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.__templates = self.import_templates()

    @property
    def templates(self):
        return self.__templates

    @templates.setter
    def templates(self, value):
        self.__templates = value

    def import_templates(self):
        """
        import the templates that are used to generate the training/test data
        :return:
        """
        sentence_templates = []
        with open(self.file_path, "rb") as infile:
            for line in decode_text(infile.read()).splitlines():
                sentence_templates.append(line.strip())

        return sentence_templates

    def test_train_split(self, skill_list: list, sentence_limit: int = 100):
        """
        helper function to distribute skill sentence cases

        :param skill_list: the list of skills
        :param sentence_limit: soft cap on number of sentences to generate for
            training data
        :return:
        """

        def add_case(test_data, training_data, num_placeholders, skill_case):
            if num_placeholders == 1:
                if len(training_data["one_skill_sentences"]) < sentence_limit:
                    training_data["one_skill_sentences"].append(skill_case)
                else:
                    test_data["one_skill_sentences"].append(skill_case)
            elif num_placeholders == 2:
                if len(training_data["two_skill_sentences"]) < sentence_limit:
                    training_data["two_skill_sentences"].append(skill_case)
                else:
                    test_data["two_skill_sentences"].append(skill_case)
            elif num_placeholders == 3:
                if len(training_data["three_skill_sentences"]) < sentence_limit:
                    training_data["three_skill_sentences"].append(skill_case)
                else:
                    test_data["three_skill_sentences"].append(skill_case)

        # initialize training data store
        training_data = {
            "one_skill_sentences": [],
            "two_skill_sentences": [],
            "three_skill_sentences": [],
        }

        # initialize test data store
        test_data = {
            "one_skill_sentences": [],
            "two_skill_sentences": [],
            "three_skill_sentences": [],
        }

        # placeholder from sentence templates to replace with a skill from the scraped skill set
        skill_placeholder_pattern = "{}"

        # shuffle the data before starting
        random.shuffle(skill_list)

        # the count that helps us decide when to break from the for loop
        skill_entity_count = len(skill_list) - 1

        # start the while loop, ensure we don't get an index out of bounds error
        # since skill templates can use up to 3 skills
        while skill_entity_count >= 2:
            entities = []

            # pick a random skill template
            sentence_template = self.templates[
                random.randint(0, len(self.templates) - 1)
            ]
            num_skill_inserts = len(
                re.findall(skill_placeholder_pattern, sentence_template)
            )

            # for each brace, replace with a skill entity from the shuffled skill data
            sentence_to_fill = sentence_template

            # loop over all the skill placeholders in the template and replace with a random skill
            placeholder_remaining = re.search(
                skill_placeholder_pattern, sentence_to_fill
            )
            while placeholder_remaining:
                random_skill = skill_list[skill_entity_count]
                skill_entity_count -= 1

                # replace only one pattern at a time, so use .replace instead of re.sub
                sentence_to_fill = sentence_to_fill.replace(
                    skill_placeholder_pattern, random_skill, 1
                )

                # get the start and stop indices of the inserted skill
                skill_length = len(random_skill)
                replace_start_idx = placeholder_remaining.span()[0]
                replace_stop_idx = skill_length + placeholder_remaining.span()[0]

                # create a SKILL annotation for the inserted skill
                entities.append((replace_start_idx, replace_stop_idx, "SKILL"))

                placeholder_remaining = re.search(
                    skill_placeholder_pattern, sentence_to_fill
                )

            # append the sentence and the position of the entities to the correct dictionary and array
            skill_case = (sentence_to_fill, {"entities": entities})
            add_case(test_data, training_data, num_skill_inserts, skill_case)

        return test_data, training_data


class RevisionData(InputFile):
    """
    data that is used to prevent the spaCy model from forgetting how to classify
    previously known entities
    (see here: https://explosion.ai/blog/pseudo-rehearsal-catastrophic-forgetting)
    """

    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.__text = None
        self.__revisions = None

    @property
    def text(self):
        return self.__text

    @text.setter
    def text(self, value):
        self.__text = value

    @property
    def revisions(self):
        return self.__revisions

    @revisions.setter
    def revisions(self, value):
        self.__revisions = value

    def import_text(self, start: float = 0.1, stop: float = 0.1):
        """
        import the revision data (text)

        :param start: proportion of text to skip before getting to the "start" of
            the text that will be used as revision data
        :param stop: proportion of text left before finishing import of revision data
            (e.g. 0.1 means 10% of the text will be left behind to remove unhelpful
            things like an index or references)
        :return:
        """
        with open(self.file_path, "rb") as infile:
            raw_text = " ".join(
                [line for line in decode_text(infile.read()).splitlines() if line]
            )

        start_idx = round(len(raw_text) * start)
        stop_idx = round(len(raw_text) * (1 - stop))

        self.text = raw_text[start_idx:stop_idx]

    def test_train_split(self):
        """
        helper function to add and keep tracking of what entities have been added to testing/training data sets

        :return:
        """

        def add_revision(entities, entity_counter, data_set):
            for _, _, entity_label in entities:
                if entity_label in entity_counter.keys():
                    entity_counter[entity_label] += 1
                else:
                    entity_counter[entity_label] = 1
                data_set.append(revision)

        # create a test/train split for revision data
        # aggregate the testing/training data
        revision_training_data = []
        revision_testing_data = []

        # keep a counter of the number of entities being aggregated to keep the test/training data
        # from being too lopsided
        soft_entity_limit = 100

        revision_testing_entity_counter = dict()
        revision_training_entity_counter = dict()

        random.shuffle(self.revisions)
        for revision in self.revisions:
            entities = revision[1]["entities"]

            append_to_training = 0
            for _, _, entity_label in entities:
                if (
                    entity_label in revision_training_entity_counter
                    and revision_training_entity_counter[entity_label]
                    >= soft_entity_limit
                ):
                    append_to_training -= 1
                else:
                    append_to_training += 1

            if append_to_training >= 0:
                add_revision(
                    entities, revision_training_entity_counter, revision_training_data
                )
            else:
                add_revision(
                    entities, revision_testing_entity_counter, revision_testing_data
                )

        print(f"Revision Testing Data: {revision_testing_entity_counter}")
        print(f"Revision Training Data: {revision_training_entity_counter}")

        return revision_testing_data, revision_training_data


class NLP:
    """
    a wrapper for the spaCy NLP object that contains various other helpful methods like
    saving the model to disk, getting and filtering training input, and updating the
    entity recognition component of the NLP pipe
    """

    def __init__(self):
        self.nlp = en_core_web_lg.load()

    def get_sentences(
        self,
        text,
        max_length: int = 1000000,
        max_sentences: int = 50000,
        trim_end: bool = True,
    ):
        # prevent IndexError from trying to select text that's out of bounds
        if max_length > len(text):
            max_length = len(text)

        # possible memory errors if length of text is over 1000000 so hard cap the text length
        doc = self.nlp(text[:max_length])

        sentences = []
        for idx, sentence in enumerate(doc.sents):
            # only get 50000 sentences for runtime considerations
            if idx == max_sentences:
                break
            sentences.append(sentence.text)

        # trim the last sentence since it's likely incomplete
        if trim_end:
            sentences = sentences[:-1]

        return sentences

    def filter_sentences(
        self,
        sentences: list,
        min_size: int = 40,
        max_size: int = 120,
        batch_size: int = 30,
    ) -> list:
        """
        filter sentences based on size

        :param sentences: sentences to filter on size
        :param min_size: minimum acceptable sentence size
        :param max_size: maximum acceptable sentence size
        :param batch_size: batch size to use when processing sentences
        :return: a list of filtered sentences
        """
        filtered_sentences = []
        for doc in self.nlp.pipe(
            sentences, batch_size=batch_size, disable=["tagger", "ner", "lemmatizer"]
        ):
            for sentence in doc.sents:
                if min_size < len(sentence.text) < max_size:
                    # sentences might have excessive whitespace from formatting; remove that whitespace
                    filtered_sentences.append(
                        " ".join(re.split(r"\s+", sentence.text, flags=re.UNICODE))
                    )

        return filtered_sentences

    def predict_entities(self, sentences: list) -> list:
        """
        use the existing spaCy model to predict the entities, then append them to revision. the tagger,
        parser, and lemmatizer components of the pipeline aren't necessary for the entity recognition task

        :param sentences: the sentences to run the spaCy model on
        :return:
        """

        revisions = []
        for doc in self.nlp.pipe(
            sentences, batch_size=50, disable=["tagger", "parser", "lemmatizer"]
        ):
            # don't append sentences that have no entities
            if len(doc.ents) > 0:
                revisions.append(
                    (
                        doc.text,
                        {
                            "entities": [
                                (e.start_char, e.end_char, e.label_) for e in doc.ents
                            ]
                        },
                    )
                )

        return revisions

    def update_entity_recognition(self, training_data: list, iterations: int = 30):
        """
        update spaCy model entity recognition with Skills data gathered from the training data

        :param training_data: the data to train the spaCy model with
        :param iterations: how many training iterations (too high could over fit)
        :return:
        """
        # add the "SKILL" entity to the Named Entity Recognition component of the spaCy pipeline
        named_entity_component = self.nlp.get_pipe("ner")
        named_entity_component.add_label("SKILL")

        # disable components of pipeline that should NOT be changed during the training process
        pipe_exceptions = ["ner", "trf_wordpiecer", "trf_tok2vec"]
        unaffected_pipes = [
            pipe for pipe in self.nlp.pipe_names if pipe not in pipe_exceptions
        ]

        # since the Named Entity Recognition component comes pre-trained from spaCy, use this to optimize
        # training with new examples
        optimizer = self.nlp.resume_training()

        with self.nlp.disable_pipes(*unaffected_pipes), warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="spacy")

            # increase batch size as pipeline iterates over training data
            # see the below link for rationale:
            # https://machinelearningmastery.com/gentle-introduction-mini-batch-gradient-descent-configure-batch-size/
            sizes = compounding(1.0, 4.0, 1.001)

            # make training data into Example objects to update the Named Entity Recognition component with
            examples = []
            for text, annotations in training_data:
                try:
                    examples.append(
                        Example.from_dict(self.nlp.make_doc(text), annotations)
                    )
                except ValueError:
                    print(text)

            for training_iteration in range(iterations):
                # use minibatches to avoid local minima when training the model
                # see here for reference:
                # https://datascience.stackexchange.com/questions/16807/why-mini-batch-size-is-better-than-one-single-batch-with-all-training-data
                random.shuffle(examples)
                minibatches = minibatch(examples, size=sizes)
                losses = {}

                for batch in minibatches:
                    self.nlp.update(batch, sgd=optimizer, drop=0.35, losses=losses)

                print(f"Losses ({training_iteration + 1}/{iterations})", losses)


def main():
    skill_file = SkillFile("resources/scraped_skills.txt")
    skill_file.length_split()

    sentence_templates = SentenceTemplate("skill_sentence_templates.txt")
    test_skill_data, train_skill_data = sentence_templates.test_train_split(
        skill_file.skills_list
    )

    revision_data = RevisionData("resources/teddy_roosevelt_autobiography.txt")
    revision_data.import_text()

    nlp = NLP()
    revision_sentences = nlp.get_sentences(revision_data.text)
    revision_sentences_trimmed = nlp.filter_sentences(revision_sentences)
    revision_data.revisions = nlp.predict_entities(revision_sentences_trimmed)

    test_revision_data, train_revision_data = revision_data.test_train_split()

    combined_training_data = [
        sentence for value in train_skill_data.values() for sentence in value
    ] + train_revision_data

    nlp.update_entity_recognition(combined_training_data)
