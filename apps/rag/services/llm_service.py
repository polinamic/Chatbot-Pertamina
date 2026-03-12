import ollama


MODEL_NAME = "llama3:8b"


def ask_llm(question):

    system_prompt = """
Anda adalah AI IT Support perusahaan.

Tugas:
- Membantu user memperbaiki masalah IT
- Berikan solusi troubleshooting
- Gunakan Bahasa Indonesia
- Gunakan langkah sederhana
- Jangan menyarankan IT Support kecuali user meminta
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        options={
            "temperature": 0.3,
            "num_predict": 200
        }
    )

    return response["message"]["content"]