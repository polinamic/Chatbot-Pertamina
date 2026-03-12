import ollama


def detect_failure(message):

    prompt = f"""
    Analyze the user's message.

    Determine the user's state:

    SOLVED → problem already fixed
    NEED_HELP → still troubleshooting
    ESCALATE → user still cannot solve the problem

    Message:
    {message}

    Answer only:
    SOLVED / NEED_HELP / ESCALATE
    """

    response = ollama.chat(
        model="llama3:8b",
        messages=[{"role": "user", "content": prompt}]
    )

    return response["message"]["content"].strip()