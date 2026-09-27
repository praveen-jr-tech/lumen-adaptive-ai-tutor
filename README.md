# Lumen — AI Learning Companion

An AI-supported study app for practicing concepts, learning from video lessons,
and getting clear feedback in a learner-friendly way.

## How it works

- Pick a subject (fractions, photosynthesis, or grammar included as a demo).
- Answer a question. Each wrong option is tagged with a specific misconception
  (e.g. "adds numerators and denominators without a common base") rather than
  just being marked wrong.
- Lumen shows a targeted explanation for that exact misconception.
- The **Progress** tab tracks mastery per topic and highlights the most
  frequent misconception, with a recommended review.
- The next question is chosen adaptively: if you have a known misconception,
  Lumen weights toward questions that reinforce that specific concept.
- Choose Normal, Medium, or Hard question levels. Built-in subjects include
  questions at all three levels, and each exercise links to a YouTube search
  for its topic.
- Use the AI question creator to generate open-ended questions for any subject
  at the selected level. Learners write answers in their own words, then the AI
  checks the answer and explains the result. Generated subjects last for the
  current app session.
- Use the **YouTube Study** tab to load a video's captions, generate questions
  from the transcript, practice written answers, and ask follow-up questions.
  If captions are unavailable or YouTube blocks access, paste the transcript
  manually.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

## AI features

Choose Google Gemini or OpenAI in the sidebar, enter a key from Google AI
Studio or OpenAI, and use the connection test to verify it. After each answer,
Lumen shows a detailed explanation; when a key is configured, the selected
model can expand that explanation while retaining the tutor's built-in facts.
The AI question creator generates open-ended questions without choices, and the
selected model evaluates learners' written answers. These AI features require
a valid key. Built-in questions and explanations continue to work without one.

The **Ask about this question** chat can answer follow-up questions about the
current exercise. It shares the question and relevant answer guidance with the
selected provider, and explains answers in simple, detailed steps. Chat history
clears when you move to another question or subject.

## Deploying a public demo (Streamlit Community Cloud — free)

1. Push this folder to a public GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**, select this repo, branch `main`, and set the main file
   path to `app.py`.
4. Click **Deploy**. In a minute or two you'll get a public URL like
   `https://your-app-name.streamlit.app` — that's your Demo Application URL.
5. (Optional) If you want the OpenAI enrichment feature to work by default for
   visitors, add your key under the app's **Settings → Secrets** instead of
   asking visitors to paste their own.

## Project structure

```
file/
├── app.py
├── README.md
├── requirements.txt
├── streamlit_config.toml
└── .gitignore
```
