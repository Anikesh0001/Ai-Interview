"""Natural interviewer phrasing: greetings, acknowledgements and phase transitions.

Choices rotate deterministically so the interviewer never repeats the same line back-to-back.
"""

from __future__ import annotations

from app.ai.prompts.interviewer import persona

ACKS = {
    "positive": {
        "default": ["Okay, that's clear.", "Got it — thanks.", "Makes sense.", "Alright, that helps.", "Understood."],
        "Friendly": [
            "Nice, thanks for walking me through that.",
            "That's helpful context.",
            "Got it, thanks.",
            "Okay, that makes sense.",
        ],
        "Strict": ["Noted.", "Understood.", "Okay.", "Fine."],
    },
    "neutral": {
        "default": ["Okay.", "Thanks.", "Alright.", "I see.", "Okay, noted."],
        "Friendly": ["Thanks for that.", "Okay, thanks.", "Alright, I appreciate it."],
        "Strict": ["Noted.", "Okay.", "Moving on."],
    },
    "deeper": {
        "default": [
            "That's interesting. Let's go one level deeper.",
            "Okay. Let's go a bit deeper on that.",
            "Let's build on that.",
        ],
        "Friendly": ["Interesting — let's dig into that a bit.", "Nice. Let's go one level deeper."],
        "Strict": ["Go deeper.", "Let's test that further."],
    },
    "probe": {
        "default": [
            "I'd like to dig into that a little.",
            "Let me push on that a bit.",
            "Okay, let's unpack that.",
            "I want to make sure I understand.",
        ],
        "Friendly": ["I'd love a bit more detail there.", "Let's unpack that a little."],
        "Strict": ["I need more precision there.", "That's not specific enough yet."],
    },
}

TRANSITIONS = {
    "RESUME": ["Let's talk about your experience.", "I'd like to go through a few things from your background."],
    "PROJECT": ["Let's dig into one of your projects.", "Now I'd like to go deeper on a project you've built."],
    "TECHNICAL": ["Let's switch to some technical questions.", "Now for a few technical questions."],
    "PROBLEM_SOLVING": ["Let's try a scenario.", "I'd like to see how you approach a problem."],
    "BEHAVIORAL": ["Let's move on to how you work with others.", "A few questions about how you work now."],
}


def _pick(options: list[str], index: int) -> str:
    return options[index % len(options)]


def acknowledgement(personality: str, tone: str, index: int) -> str:
    table = ACKS[tone]
    return _pick(table.get(personality, table["default"]), index)


def transition(phase: str, index: int) -> str:
    opts = TRANSITIONS.get(phase)
    return _pick(opts, index) if opts else ""


def greeting(personality: str, role: str, candidate_name: str, total: int, mode: str) -> list[str]:
    p = persona(personality)
    first = candidate_name.split()[0] if candidate_name else ""
    hello = f"Hi{(' ' + first) if first else ''}, thanks for joining. I'm {p['name']}, {p['title']}."
    if personality == "Friendly":
        hello = f"Hi{(' ' + first) if first else ''}! Thanks for making the time. I'm {p['name']}, a {p['title'].lower()} on the team."
    elif personality == "Strict":
        hello = f"Hello{(' ' + first) if first else ''}. I'm {p['name']}, {p['title']}. Let's get started."
    fmt = (
        f"This is a {role} interview with about {total} main questions. We'll cover your background, your "
        "projects and some technical and behavioral topics, and I may ask follow-ups along the way."
    )
    how = (
        "Answer out loud when you're ready; you can review the transcript before submitting."
        if mode == "voice"
        else "Take your time with each answer."
    )
    return [hello, f"{fmt} {how}"]
