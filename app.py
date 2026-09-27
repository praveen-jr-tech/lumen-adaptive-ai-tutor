"""
Lumen — AI Learning Companion
A Streamlit app for guided practice, open-ended AI questions, and learning from
YouTube video transcripts.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Deploy free at https://share.streamlit.io by pointing it at this repo.
"""

import json
import random
import re
from collections import Counter
from urllib.parse import parse_qs, quote_plus, urlparse

import streamlit as st

# Optional: only used if the user supplies an API key in the sidebar.
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from google import genai
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_TRANSCRIPTS_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPTS_AVAILABLE = False


# ----------------------------------------------------------------------
# Content bank: each topic has questions, and each wrong option is tagged
# with a *specific* misconception + a targeted explanation. This is the
# core of Lumen's "diagnose why, not just what" approach.
# ----------------------------------------------------------------------
TOPICS = {
    "Math — Fractions": {
        "questions": [
            {
                "prompt": "What is 1/2 + 1/3?",
                "options": {
                    "5/6": {
                        "correct": True,
                        "explanation": (
                            "To add fractions, first make the denominators the same. "
                            "The common denominator is 6: 1/2 becomes 3/6 and 1/3 "
                            "becomes 2/6. Add the numerators, 3 + 2 = 5, and keep "
                            "the denominator 6, giving 5/6."
                        ),
                    },
                    "2/5": {
                        "misconception": "adds_numerators_and_denominators",
                        "explanation": (
                            "A common mix-up is adding the top and bottom numbers "
                            "separately (1+1=2, 2+3=5). Fractions need a common "
                            "denominator before you can add them: 1/2 = 3/6 and "
                            "1/3 = 2/6, so 3/6 + 2/6 = 5/6."
                        ),
                    },
                    "1/5": {
                        "misconception": "adds_numerators_only",
                        "explanation": (
                            "It's easy to focus on the top numbers first. Before "
                            "adding, make the denominators match: 1/2 = 3/6 and "
                            "1/3 = 2/6. Then add 3 + 2 to get 5/6."
                        ),
                    },
                    "2/6": {
                        "misconception": "finds_common_denominator_incorrectly",
                        "explanation": (
                            "Good thinking to look for a common denominator of 6. "
                            "The next step is to change each numerator too: 1/2 "
                            "becomes 3/6 and 1/3 becomes 2/6. Then 3/6 + 2/6 = 5/6."
                        ),
                    },
                },
            },
            {
                "prompt": "Which fraction is equivalent to 2/4?",
                "options": {
                    "1/2": {
                        "correct": True,
                        "explanation": (
                            "Equivalent fractions have the same value. Divide both "
                            "the numerator and denominator of 2/4 by 2: 2 ÷ 2 = 1 "
                            "and 4 ÷ 2 = 2. So 2/4 simplifies to 1/2."
                        ),
                    },
                    "2/8": {
                        "misconception": "multiplies_only_denominator",
                        "explanation": (
                            "A useful rule for equivalent fractions is to do the same "
                            "operation to the top and bottom. Divide both parts of "
                            "2/4 by 2: the numerator becomes 1 and the denominator "
                            "becomes 2, so the answer is 1/2."
                        ),
                    },
                    "4/2": {
                        "misconception": "flips_numerator_denominator",
                        "explanation": (
                            "Switching the top and bottom changes the fraction's value: "
                            "4/2 = 2, while 2/4 = 0.5. To make an equivalent fraction, "
                            "divide both 2 and 4 by 2. That gives 1/2."
                        ),
                    },
                },
            },
            {
                "prompt": "What is 3/4 of 8?",
                "options": {
                    "6": {
                        "correct": True,
                        "explanation": (
                            "To find 3/4 of 8, split 8 into 4 equal groups. Each "
                            "group has 2, because 8 ÷ 4 = 2. Take 3 groups: "
                            "2 × 3 = 6."
                        ),
                    },
                    "2.66": {
                        "misconception": "divides_by_wrong_number",
                        "explanation": (
                            "\"3/4 of 8\" means multiply: 8 × 3/4. First divide 8 by the "
                            "denominator (4) to get 2, then multiply by the numerator "
                            "(3): 2 × 3 = 6."
                        ),
                    },
                    "24": {
                        "misconception": "multiplies_by_numerator_only",
                        "explanation": (
                            "Remember to use both parts of the fraction. First divide "
                            "8 by the denominator, 4, to get 2. Then multiply by the "
                            "numerator, 3: 2 × 3 = 6."
                        ),
                    },
                },
            },
            {
                "prompt": "Which fraction is greater: 5/8 or 2/3?",
                "difficulty": "Medium",
                "options": {
                    "2/3": {
                        "correct": True,
                        "explanation": (
                            "Use a common denominator of 24. The fractions become "
                            "5/8 = 15/24 and 2/3 = 16/24. Since 16/24 is greater "
                            "than 15/24, 2/3 is greater."
                        ),
                    },
                    "5/8": {
                        "misconception": "compares_denominators_without_conversion",
                        "explanation": (
                            "The denominators differ, so compare equivalent fractions "
                            "with a common denominator. 5/8 = 15/24 and 2/3 = 16/24, "
                            "so 2/3 is slightly greater."
                        ),
                    },
                    "They are equal": {
                        "misconception": "assumes_similar_size_from_values",
                        "explanation": (
                            "Convert both to twenty-fourths: 5/8 is 15/24, while "
                            "2/3 is 16/24. They are close, but 2/3 is greater."
                        ),
                    },
                },
            },
            {
                "prompt": "What is 2/3 + 3/5?",
                "difficulty": "Higher",
                "options": {
                    "19/15": {
                        "correct": True,
                        "explanation": (
                            "The least common denominator of 3 and 5 is 15. "
                            "Convert 2/3 to 10/15 and 3/5 to 9/15. Add the "
                            "numerators: 10 + 9 = 19, so the answer is 19/15, "
                            "or 1 4/15 as a mixed number."
                        ),
                    },
                    "5/8": {
                        "misconception": "adds_numerators_and_denominators",
                        "explanation": (
                            "A common mix-up is adding the tops and bottoms directly. "
                            "First use a common denominator of 15: 2/3 = 10/15 and "
                            "3/5 = 9/15. Then add to get 19/15."
                        ),
                    },
                    "19/8": {
                        "misconception": "adds_denominators_after_conversion",
                        "explanation": (
                            "Once denominators match, keep that shared denominator. "
                            "Here both fractions become fifteenths, so add 10 + 9 "
                            "and keep 15 to get 19/15."
                        ),
                    },
                },
            },
            {
                "prompt": "A recipe uses 3/4 cup of flour per batch. How much flour is needed for 3 batches?",
                "difficulty": "Higher",
                "options": {
                    "2 1/4 cups": {
                        "correct": True,
                        "explanation": (
                            "Multiply the amount for one batch by 3: 3 × 3/4 = 9/4. "
                            "Since 9/4 is 2 wholes and 1/4 left over, the total is "
                            "2 1/4 cups."
                        ),
                    },
                    "1 1/4 cups": {
                        "misconception": "multiplies_only_denominator",
                        "explanation": (
                            "For 3 batches, multiply 3 by the whole fraction: "
                            "3 × 3/4 = 9/4. Convert 9/4 to a mixed number to get "
                            "2 1/4 cups."
                        ),
                    },
                    "9/12 cup": {
                        "misconception": "multiplies_denominator_instead_of_numerator",
                        "explanation": (
                            "When multiplying a fraction by a whole number, multiply "
                            "the numerator: 3 × 3/4 = 9/4. That is 2 1/4 cups."
                        ),
                    },
                },
            },
        ],
        "remediation": (
            "**Core idea:** fractions can only be added or compared once they share a "
            "common denominator, and whatever operation you apply to the denominator "
            "must also be applied to the numerator to keep the value equivalent."
        ),
    },
    "Science — Photosynthesis": {
        "questions": [
            {
                "prompt": "What does a plant take IN during photosynthesis?",
                "options": {
                    "Carbon dioxide and water": {
                        "correct": True,
                        "explanation": (
                            "Plants take in carbon dioxide from the air and water "
                            "through their roots. Using energy from sunlight, they "
                            "combine these ingredients to make glucose, a kind of "
                            "sugar they use for food."
                        ),
                    },
                    "Oxygen and water": {
                        "misconception": "confuses_input_output_gas",
                        "explanation": (
                            "It's easy to mix up the gases going in and coming out. "
                            "Plants take in carbon dioxide from the air and water "
                            "from the soil. They release oxygen after photosynthesis."
                        ),
                    },
                    "Glucose and sunlight": {
                        "misconception": "confuses_input_with_product",
                        "explanation": (
                            "You're right that sunlight is involved as an energy source. "
                            "Glucose is the sugar the plant makes; the materials it "
                            "takes in are carbon dioxide and water."
                        ),
                    },
                },
            },
            {
                "prompt": "What does photosynthesis produce as a byproduct, released into the air?",
                "options": {
                    "Oxygen": {
                        "correct": True,
                        "explanation": (
                            "During photosynthesis, plants use carbon dioxide and "
                            "water to make glucose. Oxygen is produced too and is "
                            "released into the air, which is why it is called a "
                            "byproduct."
                        ),
                    },
                    "Carbon dioxide": {
                        "misconception": "confuses_input_output_gas",
                        "explanation": (
                            "A handy way to remember the gases is: carbon dioxide goes "
                            "in, and oxygen comes out. Carbon dioxide is an input; "
                            "oxygen is the gas released into the air."
                        ),
                    },
                    "Nitrogen": {
                        "misconception": "unrelated_gas_confusion",
                        "explanation": (
                            "Nitrogen is important in other parts of plant growth, but "
                            "it isn't the gas released by photosynthesis. The released "
                            "byproduct is oxygen."
                        ),
                    },
                },
            },
            {
                "prompt": "Where in the plant cell does photosynthesis mainly happen?",
                "options": {
                    "Chloroplast": {
                        "correct": True,
                        "explanation": (
                            "Photosynthesis mainly happens in chloroplasts. They "
                            "contain chlorophyll, the green pigment that captures "
                            "light energy. The plant uses that energy to make sugar "
                            "from carbon dioxide and water."
                        ),
                    },
                    "Mitochondria": {
                        "misconception": "confuses_photosynthesis_respiration_organelle",
                        "explanation": (
                            "These two cell parts have different jobs: mitochondria help "
                            "release energy from glucose, while chloroplasts capture "
                            "light for photosynthesis. Chloroplasts contain chlorophyll."
                        ),
                    },
                    "Nucleus": {
                        "misconception": "generic_organelle_confusion",
                        "explanation": (
                            "The nucleus stores DNA and helps direct cell activities. "
                            "Photosynthesis happens in chloroplasts, where chlorophyll "
                            "captures sunlight."
                        ),
                    },
                },
            },
            {
                "prompt": "Why do plants need light during photosynthesis?",
                "difficulty": "Medium",
                "options": {
                    "It provides energy to make glucose": {
                        "correct": True,
                        "explanation": (
                            "Light supplies the energy that helps a plant turn water "
                            "and carbon dioxide into glucose. The plant stores and "
                            "uses glucose as food."
                        ),
                    },
                    "It provides carbon atoms": {
                        "misconception": "confuses_light_with_matter_input",
                        "explanation": (
                            "Light supplies energy, not the carbon atoms. The carbon "
                            "comes from carbon dioxide taken in from the air."
                        ),
                    },
                    "It replaces water": {
                        "misconception": "confuses_energy_and_material_inputs",
                        "explanation": (
                            "Light is an energy source, while water is a material the "
                            "plant takes in. Photosynthesis needs both."
                        ),
                    },
                },
            },
            {
                "prompt": "Which equation best summarizes photosynthesis?",
                "difficulty": "Higher",
                "options": {
                    "6CO2 + 6H2O + light → C6H12O6 + 6O2": {
                        "correct": True,
                        "explanation": (
                            "Photosynthesis uses carbon dioxide and water, powered by "
                            "light, to make glucose and oxygen. The balanced equation "
                            "shows six molecules of carbon dioxide and six of water "
                            "forming one glucose molecule and six oxygen molecules."
                        ),
                    },
                    "C6H12O6 + 6O2 → 6CO2 + 6H2O + light": {
                        "misconception": "reverses_photosynthesis_equation",
                        "explanation": (
                            "That direction describes the inputs and products backwards. "
                            "Photosynthesis takes in carbon dioxide, water, and light, "
                            "then makes glucose and oxygen."
                        ),
                    },
                    "6O2 + light → 6CO2 + 6H2O": {
                        "misconception": "confuses_inputs_and_products",
                        "explanation": (
                            "Plants take in carbon dioxide and water, then produce "
                            "glucose and oxygen using light energy."
                        ),
                    },
                },
            },
            {
                "prompt": "A plant has water and carbon dioxide but is kept in darkness. Which photosynthesis requirement is missing?",
                "difficulty": "Higher",
                "options": {
                    "Light energy": {
                        "correct": True,
                        "explanation": (
                            "Water and carbon dioxide are the raw materials, but "
                            "photosynthesis also needs light energy. Light powers the "
                            "reactions that let the plant make glucose."
                        ),
                    },
                    "Oxygen as a raw material": {
                        "misconception": "confuses_input_output_gas",
                        "explanation": (
                            "Oxygen is mainly released as a product of photosynthesis. "
                            "The missing requirement in darkness is light energy."
                        ),
                    },
                    "Soil": {
                        "misconception": "confuses_growth_needs_with_reaction_inputs",
                        "explanation": (
                            "Soil supports the plant and supplies minerals, but it is "
                            "not the missing energy source. The missing requirement is light."
                        ),
                    },
                },
            },
        ],
        "remediation": (
            "**Core idea:** photosynthesis takes in carbon dioxide + water + sunlight, "
            "and produces glucose + oxygen. It's easy to mix up which gas goes in and "
            "which comes out — try remembering 'CO2 In, O2 Out.'"
        ),
    },
    "Grammar — Subject-Verb Agreement": {
        "questions": [
            {
                "prompt": "Choose the correct sentence:",
                "options": {
                    "The team of players is ready.": {
                        "correct": True,
                        "explanation": (
                            "The subject is 'team,' which is a singular group noun. "
                            "The phrase 'of players' describes the team but does not "
                            "change the subject. A singular subject takes 'is': "
                            "'The team is ready.'"
                        ),
                    },
                    "The team of players are ready.": {
                        "misconception": "agrees_with_nearest_noun",
                        "explanation": (
                            "A useful trick is to find the main subject first. Here, "
                            "'team' is singular; 'of players' only describes the team. "
                            "So the singular verb is 'is': 'The team is ready.'"
                        ),
                    },
                },
            },
            {
                "prompt": "Choose the correct sentence:",
                "options": {
                    "Neither of the answers is correct.": {
                        "correct": True,
                        "explanation": (
                            "'Neither' means not one and is treated as singular in "
                            "this sentence. The phrase 'of the answers' does not "
                            "change the subject. Use the singular verb 'is': "
                            "'Neither is correct.'"
                        ),
                    },
                    "Neither of the answers are correct.": {
                        "misconception": "agrees_with_nearest_noun",
                        "explanation": (
                            "Look for the subject rather than the closest noun. "
                            "'Neither' is singular here, even though 'answers' is plural, "
                            "so it takes 'is': 'Neither is correct.'"
                        ),
                    },
                },
            },
            {
                "prompt": "Choose the correct sentence:",
                "options": {
                    "Each of the students has a book.": {
                        "correct": True,
                        "explanation": (
                            "'Each' talks about the students one at a time, so it is "
                            "singular. The subject is 'each,' not the nearby plural "
                            "word 'students.' Singular 'each' takes 'has': "
                            "'Each has a book.'"
                        ),
                    },
                    "Each of the students have a book.": {
                        "misconception": "agrees_with_nearest_noun",
                        "explanation": (
                            "'Each' considers the students one at a time, so it is "
                            "singular and takes 'has.' The nearby word 'students' "
                            "doesn't change the subject."
                        ),
                    },
                },
            },
            {
                "prompt": "Choose the correct sentence: The bouquet of roses ___ on the table.",
                "difficulty": "Medium",
                "options": {
                    "is": {
                        "correct": True,
                        "explanation": (
                            "The main subject is 'bouquet,' which is singular. 'Of roses' "
                            "describes the bouquet but does not make the subject plural, "
                            "so use 'is.'"
                        ),
                    },
                    "are": {
                        "misconception": "agrees_with_nearest_noun",
                        "explanation": (
                            "The verb agrees with the main subject 'bouquet,' not the "
                            "nearby plural noun 'roses.' Since bouquet is singular, use 'is.'"
                        ),
                    },
                    "were": {
                        "misconception": "uses_plural_past_verb",
                        "explanation": (
                            "The sentence describes the present, and its subject "
                            "'bouquet' is singular. The matching verb is 'is.'"
                        ),
                    },
                },
            },
            {
                "prompt": "Choose the correct verb: Neither the teacher nor the students ___ ready.",
                "difficulty": "Higher",
                "options": {
                    "are": {
                        "correct": True,
                        "explanation": (
                            "With 'neither...nor,' the verb commonly agrees with the "
                            "nearest subject. 'Students' is plural and closest to the "
                            "blank, so the verb is 'are.'"
                        ),
                    },
                    "is": {
                        "misconception": "agrees_with_first_subject",
                        "explanation": (
                            "In this 'neither...nor' sentence, check the subject nearest "
                            "the verb. 'Students' is plural, so use 'are.'"
                        ),
                    },
                    "was": {
                        "misconception": "uses_past_tense",
                        "explanation": (
                            "The sentence describes the present, so use a present-tense "
                            "verb. The nearer subject 'students' is plural, making 'are' "
                            "the best choice."
                        ),
                    },
                },
            },
            {
                "prompt": "Choose the correct sentence.",
                "difficulty": "Higher",
                "options": {
                    "There are several reasons for the change.": {
                        "correct": True,
                        "explanation": (
                            "In a sentence beginning with 'there,' the real subject "
                            "comes after the verb. 'Reasons' is plural, so the verb "
                            "should also be plural: 'There are several reasons.'"
                        ),
                    },
                    "There is several reasons for the change.": {
                        "misconception": "agrees_with_there_instead_of_subject",
                        "explanation": (
                            "'There' is not the subject here. Find the noun after the "
                            "verb: 'reasons' is plural, so use 'are.'"
                        ),
                    },
                    "There was several reasons for the change.": {
                        "misconception": "subject_verb_number_mismatch",
                        "explanation": (
                            "'Reasons' is plural, so the verb needs to be plural too. "
                            "For the present-tense sentence, use 'There are several reasons.'"
                        ),
                    },
                },
            },
        ],
        "remediation": (
            "**Core idea:** the verb must agree with the true subject of the sentence, "
            "not just whichever noun happens to sit closest to it. Words like "
            "'each', 'neither', and 'every' are always singular."
        ),
    },
}


# ----------------------------------------------------------------------
# Session state setup — this is Lumen's "student profile" that persists
# across questions within a session (the core of the adaptive loop).
# ----------------------------------------------------------------------
def get_topics():
    topics = dict(TOPICS)
    for topic, custom_topic in st.session_state.custom_topics.items():
        if topic in topics:
            topics[topic] = {
                "questions": topics[topic]["questions"] + custom_topic["questions"],
                "remediation": custom_topic.get("remediation", topics[topic]["remediation"]),
            }
        else:
            topics[topic] = custom_topic
    return topics


def question_difficulty(question: dict) -> str:
    difficulty = question.get("difficulty", "Normal")
    return "Hard" if difficulty == "Higher" else difficulty


def init_state():
    if "custom_topics" not in st.session_state:
        st.session_state.custom_topics = {}
    topics = get_topics()
    if "profile" not in st.session_state:
        st.session_state.profile = {
            topic: {"correct": 0, "total": 0, "misconceptions": Counter()}
            for topic in topics
        }
    for topic in topics:
        st.session_state.profile.setdefault(
            topic, {"correct": 0, "total": 0, "misconceptions": Counter()}
        )
    if "current_topic" not in st.session_state:
        st.session_state.current_topic = next(iter(topics))
    if "current_difficulty" not in st.session_state:
        st.session_state.current_difficulty = "Normal"
    if "current_q_idx" not in st.session_state:
        questions = topics[st.session_state.current_topic]["questions"]
        eligible = [
            index for index, question in enumerate(questions)
            if question_difficulty(question) == st.session_state.current_difficulty
        ]
        st.session_state.current_q_idx = random.choice(eligible or range(len(questions)))
    if "question_history" not in st.session_state:
        st.session_state.question_history = [
            (st.session_state.current_topic, st.session_state.current_q_idx)
        ]
    if "history_position" not in st.session_state:
        st.session_state.history_position = 0
    if "question_results" not in st.session_state:
        st.session_state.question_results = {}
    if "answered" not in st.session_state:
        st.session_state.answered = False
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "answer_error" not in st.session_state:
        st.session_state.answer_error = None
    if "question_chat_history" not in st.session_state:
        st.session_state.question_chat_history = []
    if "youtube_study" not in st.session_state:
        st.session_state.youtube_study = {
            "video_url": "",
            "video_id": "",
            "transcript": "",
            "questions": [],
            "question_index": 0,
            "results": {},
            "chat": [],
            "input_generation": 0,
        }


def pick_next_question(
    topic: str,
    previous_index: int | None = None,
    difficulty: str = "Normal",
):
    """Adaptive step: if the student has a known misconception on this topic,
    weight toward questions that reinforce the concept they struggle with.
    Otherwise pick randomly. This keeps the demo simple but genuinely adaptive."""
    questions = get_topics()[topic]["questions"]
    profile = st.session_state.profile[topic]
    matching = [
        i for i, question in enumerate(questions)
        if question_difficulty(question) == difficulty
    ] or list(range(len(questions)))
    available = [i for i in matching if i != previous_index] or matching
    if profile["misconceptions"]:
        weakest = profile["misconceptions"].most_common(1)[0][0]
        weighted = [
            i for i in available
            for q in [questions[i]]
            if any(
                opt.get("misconception") == weakest
                for opt in q.get("options", {}).values()
            )
        ]
        if weighted:
            return random.choice(weighted)
    return random.choice(available) if available else random.randrange(len(questions))


def request_ai(
    message: str,
    api_key: str,
    provider: str,
    max_tokens: int = 150,
) -> tuple[str | None, str | None]:
    if not api_key:
        return None, f"Enter a {provider} API key first."
    try:
        if provider == "Google Gemini":
            if not GOOGLE_GENAI_AVAILABLE:
                return None, "The Google GenAI package is unavailable. Install requirements.txt and restart the app."
            client = genai.Client(api_key=api_key)
            response = client.interactions.create(
                model="gemini-3.8-flash",
                input=message,
            )
            content = response.output_text
        else:
            if not OPENAI_AVAILABLE:
                return None, "The OpenAI package is unavailable. Install requirements.txt and restart the app."
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Follow the user's instruction.",
                    },
                    {"role": "user", "content": message},
                ],
                max_tokens=max_tokens,
                temperature=0.6,
            )
            content = response.choices[0].message.content
        if not content:
            return None, f"{provider} returned an empty response."
        return content.strip(), None
    except Exception as error:
        details = str(error).replace(api_key, "[redacted]").strip()
        return None, f"{type(error).__name__}: {details or 'The request failed.'}"


def parse_ai_json(response: str) -> dict:
    text = response.strip()
    if text.startswith("```"):
        text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("```"))
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("The AI response was not a JSON object.")
    return parsed


def generate_open_question(
    topic: str,
    difficulty: str,
    api_key: str,
    provider: str,
) -> tuple[dict | None, str | None]:
    prompt = (
        "Create exactly one original, open-ended practice question for the learner. "
        "Do not create multiple-choice options, lettered answers, or answer choices. "
        "Return only a JSON object with string fields: question, expected_answer, "
        "and explanation. Make the question appropriate for the given level, and "
        "make the explanation clear and easy to understand.\n"
        f"Subject: {topic}\nLevel: {difficulty}"
    )
    response, error = request_ai(prompt, api_key, provider, max_tokens=600)
    if error:
        return None, error
    try:
        question = parse_ai_json(response)
        fields = ("question", "expected_answer", "explanation")
        if any(not isinstance(question.get(field), str) or not question[field].strip() for field in fields):
            return None, "The AI response was missing a question, answer, or explanation. Try again."
        return {
            "prompt": question["question"].strip(),
            "expected_answer": question["expected_answer"].strip(),
            "explanation": question["explanation"].strip(),
            "difficulty": difficulty,
            "open_ended": True,
        }, None
    except (json.JSONDecodeError, ValueError):
        return None, "The AI response was not in the expected format. Try generating again."


def evaluate_open_answer(
    question: dict,
    student_answer: str,
    api_key: str,
    provider: str,
) -> tuple[dict | None, str | None]:
    prompt = (
        "Evaluate a learner's short answer fairly. Accept equivalent wording and "
        "correct reasoning; do not require an exact match. Be warm and encouraging. "
        "Return only a JSON object with boolean field is_correct and string fields "
        "feedback and explanation. Feedback should briefly say what was done well "
        "or what to reconsider. Explanation should teach the answer in simple steps.\n"
        f"Question: {question['prompt']}\n"
        f"Expected answer: {question['expected_answer']}\n"
        f"Teaching explanation: {question['explanation']}\n"
        f"Learner's answer: {student_answer}"
    )
    response, error = request_ai(prompt, api_key, provider, max_tokens=600)
    if error:
        return None, error
    try:
        result = parse_ai_json(response)
        if not isinstance(result.get("is_correct"), bool):
            return None, "The AI response did not include a valid correctness result."
        for field in ("feedback", "explanation"):
            if not isinstance(result.get(field), str) or not result[field].strip():
                return None, "The AI response was missing feedback. Please try again."
        return result, None
    except (json.JSONDecodeError, ValueError):
        return None, "The AI response was not in the expected format. Please try again."


def extract_youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().split(":")[0]
    video_id = None
    if parsed.scheme not in {"http", "https"}:
        return None
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/")[0]
    elif (
        host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "youtube-nocookie.com"
        or host.endswith(".youtube-nocookie.com")
    ):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif parsed.path.startswith(("/embed/", "/shorts/", "/live/")):
            video_id = parsed.path.split("/")[2]
    return video_id if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) else None


def fetch_youtube_transcript(url: str, language_code: str) -> tuple[str | None, str | None, str | None]:
    video_id = extract_youtube_video_id(url)
    if not video_id:
        return None, None, "Enter a valid YouTube video URL."
    if not YOUTUBE_TRANSCRIPTS_AVAILABLE:
        return None, None, "Transcript support is not installed. Install requirements.txt and restart the app."
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=[language_code])
        text = " ".join(segment.text for segment in transcript).strip()
        if not text:
            return None, video_id, "No captions were found. Paste a transcript below instead."
        return text, video_id, None
    except Exception as error:
        return (
            None,
            video_id,
            f"Could not fetch captions ({type(error).__name__}). The video may have captions disabled, "
            "or YouTube may be blocking this connection. Paste the transcript below instead.",
        )


def generate_video_questions(
    transcript: str,
    subject: str,
    difficulty: str,
    count: int,
    api_key: str,
    provider: str,
) -> tuple[list[dict] | None, str | None]:
    transcript_limit = 24000
    if len(transcript) > transcript_limit:
        half_limit = transcript_limit // 2
        transcript = (
            transcript[:half_limit]
            + "\n[Middle of transcript omitted for length]\n"
            + transcript[-half_limit:]
        )
    prompt = (
        f"Create exactly {count} open-ended learner practice questions from this video transcript. "
        "Do not make multiple-choice questions or provide answer options. Questions must be "
        "answerable from the transcript. Return only a JSON object with a 'questions' array; "
        "each item must contain string fields 'question', 'expected_answer', and 'explanation'. "
        "Use clear, simple explanations and the requested difficulty.\n"
        f"Subject: {subject}\nDifficulty: {difficulty}\n"
        f"Transcript:\n{transcript}"
    )
    response, error = request_ai(prompt, api_key, provider, max_tokens=1800)
    if error:
        return None, error
    try:
        data = parse_ai_json(response)
        items = data.get("questions")
        if not isinstance(items, list) or not items:
            return None, "The AI did not return any questions. Try again."
        questions = []
        for item in items[:count]:
            fields = ("question", "expected_answer", "explanation")
            if not isinstance(item, dict) or any(
                not isinstance(item.get(field), str) or not item[field].strip()
                for field in fields
            ):
                return None, "The AI returned an incomplete question. Try generating again."
            questions.append({
                "prompt": item["question"].strip(),
                "expected_answer": item["expected_answer"].strip(),
                "explanation": item["explanation"].strip(),
                "difficulty": difficulty,
                "open_ended": True,
            })
        return questions, None
    except (json.JSONDecodeError, ValueError):
        return None, "The AI response was not in the expected format. Try generating again."


def ai_enrich_explanation(base_explanation: str, api_key: str, provider: str) -> tuple[str, str | None]:
    """Expand a built-in explanation while keeping the tutor's facts intact."""
    if not api_key:
        return base_explanation, None
    prompt = (
        "Explain this answer clearly and in detail for a student. Be warm and "
        "encouraging, acknowledge that trying matters, and describe mistakes as "
        "common and fixable. Use simple language and step-by-step reasoning. "
        "Keep all factual content the same and do not invent facts:\n\n"
        f"{base_explanation}"
    )
    enriched, error = request_ai(prompt, api_key, provider, max_tokens=400)
    return (enriched, None) if enriched else (base_explanation, error)


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------
st.set_page_config(page_title="🧠✨ Lumen — AI Learning Companion", page_icon="🧠", layout="centered")
init_state()

with st.sidebar:
    st.markdown("## 🧠✨ Lumen")
    st.caption("AI Learning Companion")
    st.divider()
    if st.session_state.get("custom_topic_notice"):
        st.success(st.session_state.pop("custom_topic_notice"))
    difficulty_choice = st.selectbox(
        "Question level",
        ["Normal", "Medium", "Hard"],
        key="difficulty_selector",
    )
    if difficulty_choice != st.session_state.current_difficulty:
        st.session_state.current_difficulty = difficulty_choice
        st.session_state.current_q_idx = pick_next_question(
            st.session_state.current_topic,
            difficulty=difficulty_choice,
        )
        st.session_state.question_history = [
            (st.session_state.current_topic, st.session_state.current_q_idx)
        ]
        st.session_state.history_position = 0
        st.session_state.question_results = {}
        st.session_state.answered = False
        st.session_state.last_result = None
        st.session_state.answer_error = None
        st.session_state.question_chat_history = []
        st.rerun()
    if st.session_state.get("pending_practice_question"):
        pending_topic, pending_index = st.session_state.pop("pending_practice_question")
        st.session_state.topic_selector = pending_topic
        st.session_state.current_topic = pending_topic
        st.session_state.current_q_idx = pending_index
        st.session_state.question_history = [(pending_topic, pending_index)]
        st.session_state.history_position = 0
        st.session_state.question_results = {}
        st.session_state.answered = False
        st.session_state.last_result = None
        st.session_state.answer_error = None
        st.session_state.question_chat_history = []
    topic_choice = st.selectbox("Subject", list(get_topics()), key="topic_selector")
    if topic_choice != st.session_state.current_topic:
        st.session_state.current_topic = topic_choice
        st.session_state.current_q_idx = pick_next_question(
            topic_choice, difficulty=st.session_state.current_difficulty
        )
        st.session_state.question_history = [(topic_choice, st.session_state.current_q_idx)]
        st.session_state.history_position = 0
        st.session_state.question_results = {}
        st.session_state.answered = False
        st.session_state.last_result = None
        st.session_state.answer_error = None
        st.session_state.question_chat_history = []
        st.rerun()

    st.divider()
    st.caption("Choose an AI provider for detailed answer feedback and question chat. Built-in explanations are always available.")
    provider = st.selectbox("AI provider", ["Google Gemini", "OpenAI"])
    key_label = "Google AI Studio API key" if provider == "Google Gemini" else "OpenAI API key"
    api_key = st.text_input(key_label, type="password").strip()
    if st.button(f"Test {provider} connection"):
        test_reply, test_error = request_ai("Reply with exactly: connected", api_key, provider)
        if test_error:
            st.error(f"{provider} connection failed: {test_error}")
        else:
            st.success(f"{provider} connection works: {test_reply}")

    with st.expander("Create AI practice questions"):
        st.caption("AI writes open-ended questions only. Learners answer in their own words; no multiple-choice options are created.")
        with st.form("generate_open_questions_form", clear_on_submit=True):
            generated_subject = st.text_input("Subject", value=topic_choice)
            question_count = st.number_input(
                "Number of questions", min_value=1, max_value=5, value=2
            )
            generate_questions = st.form_submit_button("Generate and start practicing")

        if generate_questions:
            subject_name = generated_subject.strip()
            if not subject_name:
                st.error("Enter a subject name first.")
            elif not api_key:
                st.error(f"Enter your {key_label} before generating questions.")
            else:
                all_topics = get_topics()
                first_generated_index = len(all_topics.get(subject_name, {}).get("questions", []))
                generated = []
                generation_error = None
                with st.spinner("🧠💭 Creating open-ended questions..."):
                    for _ in range(int(question_count)):
                        question, generation_error = generate_open_question(
                            subject_name,
                            st.session_state.current_difficulty,
                            api_key,
                            provider,
                        )
                        if generation_error:
                            break
                        generated.append(question)

                if generated:
                    custom_topic = st.session_state.custom_topics.setdefault(
                        subject_name,
                        {
                            "questions": [],
                            "remediation": "Review each explanation and ask Lumen follow-up questions.",
                        },
                    )
                    custom_topic["questions"].extend(generated)
                    st.session_state.profile.setdefault(
                        subject_name,
                        {"correct": 0, "total": 0, "misconceptions": Counter()},
                    )
                    st.session_state.pending_practice_question = (
                        subject_name, first_generated_index
                    )
                    st.session_state.custom_topic_notice = (
                        f"Generated {len(generated)} open-ended question(s) for {subject_name}."
                    )
                    st.rerun()
                elif generation_error:
                    st.error(f"Could not generate a question: {generation_error}")

    st.divider()
    if st.button("Reset my progress"):
        for key in [
            "profile",
            "current_topic",
            "current_q_idx",
            "question_history",
            "history_position",
            "question_results",
            "answered",
            "last_result",
            "answer_error",
            "question_chat_history",
        ]:
            st.session_state.pop(key, None)
        st.rerun()

tab_tutor, tab_video, tab_progress = st.tabs(
    ["📘 Tutor", "🎬 YouTube Study", "📊 Your Progress"]
)

# ------------------------- TUTOR TAB -------------------------
with tab_tutor:
    topic = st.session_state.current_topic
    topic_questions = get_topics()[topic]["questions"]
    q = topic_questions[st.session_state.current_q_idx]

    st.subheader(topic)
    displayed_difficulty = question_difficulty(q)
    if displayed_difficulty != st.session_state.current_difficulty:
        st.info(
            f"This subject has no {st.session_state.current_difficulty} questions yet; "
            f"showing a {displayed_difficulty} question instead."
        )
    st.caption(f"{displayed_difficulty} level")
    st.write(q["prompt"])
    youtube_url = (
        "https://www.youtube.com/results?search_query="
        + quote_plus(f"{topic} {q['prompt']} explained")
    )
    st.link_button("▶ Find a YouTube explanation", youtube_url)

    history_position = st.session_state.history_position
    saved_attempt = st.session_state.question_results.get(history_position, {})
    saved_choice = saved_attempt.get("choice")
    is_open_ended = q.get("open_ended", False)
    if is_open_ended:
        choice = st.text_area(
            "Write your answer:",
            value=saved_choice or "",
            key=f"written_answer_{topic}_{history_position}_{st.session_state.current_q_idx}",
        )
    else:
        options = list(q["options"].keys())
        choice_index = options.index(saved_choice) if saved_choice in options else None
        choice = st.radio(
            "Your answer:",
            options,
            index=choice_index,
            key=f"radio_{topic}_{history_position}_{st.session_state.current_q_idx}",
        )

    has_forward_question = history_position < len(st.session_state.question_history) - 1
    has_previous_question = history_position > 0
    button_columns = st.columns(3 if has_previous_question else 2)
    previous_q = False
    if has_previous_question:
        with button_columns[0]:
            previous_q = st.button("← Previous question")
        submit_column, next_column = button_columns[1:]
    else:
        submit_column, next_column = button_columns
    with submit_column:
        submit = st.button(
            "Submit answer",
            disabled=st.session_state.answered or (is_open_ended and not choice.strip()),
        )
    with next_column:
        next_q = st.button(
            "Next question →",
            disabled=not st.session_state.answered and not has_forward_question,
        )

    if submit and choice is not None:
        st.session_state.answered = True
        profile = st.session_state.profile[topic]
        st.session_state.answer_error = None
        if is_open_ended:
            evaluation, evaluation_error = evaluate_open_answer(
                q, choice.strip(), api_key, provider
            )
            if evaluation_error:
                st.session_state.answered = False
                st.session_state.answer_error = evaluation_error
                st.rerun()
            profile["total"] += 1
            if evaluation["is_correct"]:
                profile["correct"] += 1
            st.session_state.last_result = {
                "correct": evaluation["is_correct"],
                "feedback": evaluation["feedback"],
                "explanation": evaluation["explanation"],
            }
        else:
            detail = q["options"][choice]
            profile["total"] += 1
            if detail.get("correct"):
                profile["correct"] += 1
                explanation, api_error = ai_enrich_explanation(
                    detail["explanation"], api_key, provider
                )
                st.session_state.last_result = {
                    "correct": True,
                    "explanation": explanation,
                    "api_error": api_error,
                }
            else:
                misconception = detail["misconception"]
                profile["misconceptions"][misconception] += 1
                base_explanation = detail["explanation"]
                explanation, api_error = ai_enrich_explanation(base_explanation, api_key, provider)
                st.session_state.last_result = {
                    "correct": False,
                    "explanation": explanation,
                    "misconception": misconception,
                    "api_error": api_error,
                }
        st.session_state.question_results[history_position] = {
            "answered": True,
            "choice": choice,
            "result": st.session_state.last_result,
        }
        st.rerun()

    if st.session_state.answered and st.session_state.last_result:
        result = st.session_state.last_result
        if result["correct"]:
            st.success("✅ Correct! Nice work.")
            if result.get("feedback"):
                st.markdown(result["feedback"])
            st.info(result["explanation"])
            if result.get("api_error"):
                st.caption(f"AI detail unavailable; showing the built-in explanation. {result['api_error']}")
        else:
            st.warning("Good effort! You're practicing, and that's how learning happens. Let's work through this idea together:")
            if result.get("feedback"):
                st.markdown(result["feedback"])
            st.info(result["explanation"])
            if result.get("misconception"):
                st.caption(f"Misconception tagged: `{result['misconception']}`")
            if result.get("api_error"):
                st.caption(f"AI rephrasing failed; showing the built-in explanation. {result['api_error']}")

    if st.session_state.answer_error:
        st.error(f"Could not check that answer: {st.session_state.answer_error}")

    if previous_q or next_q:
        if previous_q:
            st.session_state.history_position -= 1
        elif has_forward_question:
            st.session_state.history_position += 1
        else:
            next_index = pick_next_question(
                topic,
                st.session_state.current_q_idx,
                st.session_state.current_difficulty,
            )
            st.session_state.question_history.append((topic, next_index))
            st.session_state.history_position += 1

        next_topic, next_index = st.session_state.question_history[
            st.session_state.history_position
        ]
        st.session_state.current_topic = next_topic
        st.session_state.current_q_idx = next_index
        saved_result = st.session_state.question_results.get(
            st.session_state.history_position
        )
        st.session_state.answered = bool(saved_result and saved_result["answered"])
        st.session_state.last_result = saved_result["result"] if saved_result else None
        st.session_state.answer_error = None
        st.session_state.question_chat_history = []
        st.rerun()

    st.subheader("Ask about this question")
    chat_history = st.session_state.question_chat_history
    for chat_message in chat_history:
        with st.chat_message(chat_message["role"]):
            st.markdown(chat_message["content"])

    if not api_key:
        st.caption(f"Enter your {key_label} in the sidebar to ask follow-up questions.")

    chat_prompt = st.chat_input(
        "Ask anything about this exercise...",
        key=f"question_chat_{topic}_{st.session_state.current_q_idx}",
        disabled=not api_key,
    )
    if chat_prompt:
        chat_history.append({"role": "user", "content": chat_prompt})
        if is_open_ended:
            option_context = [
                f"Expected answer: {q['expected_answer']}",
                f"Teaching explanation: {q['explanation']}",
            ]
        else:
            option_context = []
            for option, detail in q["options"].items():
                status = "correct answer" if detail.get("correct") else "incorrect choice"
                notes = [status]
                if detail.get("misconception"):
                    notes.append(f"misconception: {detail['misconception'].replace('_', ' ')}")
                if detail.get("explanation"):
                    notes.append(f"tutor note: {detail['explanation']}")
                option_context.append(f"- {option} ({'; '.join(notes)})")

        prior_messages = "\n".join(
            f"{'Student' if message['role'] == 'user' else 'Tutor'}: {message['content']}"
            for message in chat_history[:-1]
        ) or "No earlier messages."
        prompt = (
            "You are Lumen, a patient and encouraging tutor. Answer the student's "
            "question about the exercise below. Give a detailed explanation using "
            "simple language and clear steps; define unfamiliar terms and use a "
            "short example when useful. Stay accurate and connect the answer to "
            "the current exercise.\n\n"
            f"Subject: {topic}\n"
            f"Exercise: {q['prompt']}\n"
            "Choices and tutor notes:\n"
            f"{chr(10).join(option_context)}\n\n"
            f"Earlier conversation:\n{prior_messages}\n\n"
            f"Student's question: {chat_prompt}"
        )
        with st.spinner("🧠💭 Lumen is thinking..."):
            answer, chat_error = request_ai(prompt, api_key, provider, max_tokens=800)
        if answer:
            chat_history.append({"role": "assistant", "content": answer})
        else:
            chat_history.append({
                "role": "assistant",
                "content": f"I couldn't get an answer from {provider}. {chat_error}",
            })
        st.rerun()

# ------------------------- PROGRESS TAB -------------------------
with tab_progress:
    st.subheader("Your Learning Profile")
    st.caption("Lumen tracks not just right vs. wrong, but *which* misconception is behind each mistake.")

    any_data = False
    for topic, profile in st.session_state.profile.items():
        if profile["total"] == 0:
            continue
        any_data = True
        mastery = profile["correct"] / profile["total"]
        st.markdown(f"**{topic}**")
        st.progress(mastery, text=f"{profile['correct']}/{profile['total']} correct ({mastery:.0%} mastery)")
        if profile["misconceptions"]:
            top = profile["misconceptions"].most_common(3)
            st.caption("Most common misconceptions: " + ", ".join(f"`{m}` ×{c}" for m, c in top))
            with st.expander(f"Recommended review for {topic}"):
                st.markdown(get_topics()[topic]["remediation"])
        st.divider()

    if not any_data:
        st.info("Answer a few questions in the Tutor tab to build your learning profile.")

# ------------------------- YOUTUBE STUDY TAB -------------------------
with tab_video:
    study = st.session_state.youtube_study
    st.subheader("Study from a YouTube video")
    st.caption(
        "Load captions from a video link, generate open-ended practice questions, "
        "and ask the tutor about the video's content."
    )

    video_url = st.text_input(
        "YouTube video link",
        value=study["video_url"],
        key=f"youtube_video_url_input_{study.get('input_generation', 0)}",
        placeholder="https://www.youtube.com/watch?v=...",
    )
    language_choice = st.selectbox(
        "Caption language",
        ["English (en)", "Spanish (es)", "French (fr)", "Hindi (hi)", "Portuguese (pt)"],
        key="youtube_caption_language",
    )
    language_code = language_choice.rsplit("(", 1)[-1].rstrip(")")
    fetch_captions = st.button("Fetch video captions")
    pasted_transcript = st.text_area(
        "Transcript text (optional fallback)",
        key=f"youtube_manual_transcript_{study.get('input_generation', 0)}",
        placeholder="Paste the video's captions or transcript if automatic captions cannot be loaded.",
        height=120,
    )
    use_pasted_transcript = st.button("Use pasted transcript")

    if fetch_captions:
        with st.spinner("Fetching YouTube captions..."):
            transcript, video_id, transcript_error = fetch_youtube_transcript(
                video_url, language_code
            )
        if transcript_error:
            st.error(transcript_error)
        else:
            study.update({
                "video_url": video_url.strip(),
                "video_id": video_id,
                "transcript": transcript,
                "questions": [],
                "question_index": 0,
                "results": {},
                "chat": [],
            })
            st.rerun()

    if use_pasted_transcript:
        if not pasted_transcript.strip():
            st.error("Paste transcript text before loading it.")
        else:
            study.update({
                "video_url": video_url.strip(),
                "video_id": extract_youtube_video_id(video_url) or "",
                "transcript": pasted_transcript.strip(),
                "questions": [],
                "question_index": 0,
                "results": {},
                "chat": [],
            })
            st.rerun()

    if study["transcript"]:
        st.success(f"Transcript ready: {len(study['transcript'].split())} words.")
        if st.button("Clear video and start over"):
            st.session_state.youtube_study = {
                "video_url": "",
                "video_id": "",
                "transcript": "",
                "questions": [],
                "question_index": 0,
                "results": {},
                "chat": [],
                "input_generation": study.get("input_generation", 0) + 1,
            }
            st.rerun()
        if study["video_url"]:
            st.link_button("Open this video on YouTube", study["video_url"])
        with st.expander("View loaded transcript"):
            st.text(study["transcript"][:12000])
            if len(study["transcript"]) > 12000:
                st.caption("Preview shortened; study features use the transcript content.")

        st.markdown("#### Generate practice")
        video_subject = st.text_input(
            "Video topic or subject",
            value=study.get("subject", "") or topic_choice,
            key="youtube_study_subject",
        )
        video_question_count = st.number_input(
            "Questions from this video",
            min_value=1,
            max_value=5,
            value=3,
            key="youtube_question_count",
        )
        if st.button("Generate questions from video"):
            if not api_key:
                st.error(f"Enter your {key_label} in the sidebar to generate questions.")
            elif not video_subject.strip():
                st.error("Enter the video topic first.")
            else:
                with st.spinner("🧠💭 Creating questions from the transcript..."):
                    generated, generation_error = generate_video_questions(
                        study["transcript"],
                        video_subject.strip(),
                        st.session_state.current_difficulty,
                        int(video_question_count),
                        api_key,
                        provider,
                    )
                if generation_error:
                    st.error(f"Could not create questions: {generation_error}")
                else:
                    study["subject"] = video_subject.strip()
                    study["questions"] = generated
                    study["question_index"] = 0
                    study["results"] = {}
                    study["chat"] = []
                    st.rerun()

        if study["questions"]:
            question_index = study["question_index"]
            video_question = study["questions"][question_index]
            result = study["results"].get(question_index)
            st.markdown("#### Practice questions")
            st.caption(
                f"Question {question_index + 1} of {len(study['questions'])} · "
                f"{video_question['difficulty']} level"
            )
            st.write(video_question["prompt"])
            answer_key = f"youtube_answer_{study['video_id'] or 'manual'}_{question_index}"
            with st.form("youtube_practice_answer_form"):
                video_answer = st.text_area(
                    "Your answer",
                    value=result.get("answer", "") if result else "",
                    key=answer_key,
                    disabled=bool(result),
                )
                check_video_answer = st.form_submit_button(
                    "Check answer",
                    disabled=bool(result) or not video_answer.strip(),
                )
            if check_video_answer:
                if not api_key:
                    st.error(f"Enter your {key_label} in the sidebar to check answers.")
                else:
                    evaluation, evaluation_error = evaluate_open_answer(
                        video_question, video_answer.strip(), api_key, provider
                    )
                    if evaluation_error:
                        st.error(f"Could not check your answer: {evaluation_error}")
                    else:
                        study["results"][question_index] = {
                            **evaluation,
                            "answer": video_answer.strip(),
                        }
                        st.rerun()

            if result:
                if result["is_correct"]:
                    st.success("Correct! Nice work.")
                else:
                    st.warning("Good try. Let's learn from this answer:")
                st.markdown(result["feedback"])
                st.info(result["explanation"])

            previous_column, next_column = st.columns(2)
            with previous_column:
                if st.button(
                    "← Previous video question",
                    disabled=question_index == 0,
                ):
                    study["question_index"] -= 1
                    st.rerun()
            with next_column:
                if st.button(
                    "Next video question →",
                    disabled=question_index >= len(study["questions"]) - 1,
                ):
                    study["question_index"] += 1
                    st.rerun()

        st.markdown("#### Ask about this video")
        for message in study["chat"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        with st.form("youtube_video_question_form", clear_on_submit=True):
            learner_question = st.text_input("Ask a question about the video")
            ask_video = st.form_submit_button("Ask the tutor")
        if ask_video:
            if not api_key:
                st.error(f"Enter your {key_label} in the sidebar to ask about the video.")
            elif learner_question.strip():
                study["chat"].append({
                    "role": "user",
                    "content": learner_question.strip(),
                })
                prior_chat = "\n".join(
                    f"{message['role']}: {message['content']}"
                    for message in study["chat"][:-1]
                ) or "No earlier conversation."
                transcript_context = study["transcript"][:24000]
                prompt = (
                    "You are Lumen, a patient tutor. Answer using the video transcript "
                    "as your source. Explain in clear, learner-friendly detail. If the "
                    "transcript does not contain enough information, say so rather "
                    "than inventing details.\n\n"
                    f"Video topic: {study.get('subject', 'YouTube video')}\n"
                    f"Transcript:\n{transcript_context}\n\n"
                    f"Earlier conversation:\n{prior_chat}\n\n"
                    f"Learner's question: {learner_question.strip()}"
                )
                with st.spinner("🧠💭 Lumen is thinking..."):
                    answer, chat_error = request_ai(
                        prompt, api_key, provider, max_tokens=800
                    )
                study["chat"].append({
                    "role": "assistant",
                    "content": answer if answer else f"I couldn't answer from the video. {chat_error}",
                })
                st.rerun()
