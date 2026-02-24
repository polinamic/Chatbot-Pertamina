import ollama

def generate_response(prompt):

    response = ollama.chat(
        model='llama3:8b',
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response['message']['content']