import ollama


def classify_domain(question):

    prompt = f"""
    Determine if this question is related to IT Support.

    IT Support topics include:
    - wifi
    - printer
    - laptop
    - VPN
    - network
    - login
    - software error

    Answer ONLY with:
    IT
    NON_IT

    Question: {question}
    """

    response = ollama.chat(
        model="llama3:8b",
        messages=[{"role": "user", "content": prompt}]
    )

    return response["message"]["content"].strip()