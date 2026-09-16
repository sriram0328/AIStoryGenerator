import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

# google-genai is the current Google Gen AI Python SDK.
# It reads GEMINI_API_KEY from the environment.
client = genai.Client()

MODEL = "gemini-3.8-flash"


def analyze_image(image_path):
    prompt = """
Analyze this image in detail for a children's story.

Describe:
1. The main elements and their relationships
2. Colors and mood
3. Potential story themes
4. Interesting or unusual details
5. Any relevant cultural/historical context if visible

Be descriptive but concise. Focus on details that can inspire a
fun, child-friendly story for ages 5-8.
"""

    # Current google-genai SDK.
    # The old google-generativeai SDK was causing the API-key
    # authentication error with the new Gemini authorization keys.
    uploaded_file = client.files.upload(file=image_path)

    response = client.models.generate_content(
        model=MODEL,
        contents=[prompt, uploaded_file],
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty image analysis.")

    return response.text


def generate_story(image_description, genre):
    prompt = f"""
Based on this image analysis:

{image_description}

Create a {genre} children's story of approximately 200 words.

Requirements:
1. Playful language suitable for ages 5-8
2. A positive moral lesson
3. Magical/fantasy elements when appropriate for the genre
4. Fun narration suitable for parent-child reading
5. Short, easy-to-read paragraphs
6. Emoji illustrations are allowed
7. Do not include choices or questions for the reader
8. The story should flow continuously from beginning to end
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty story.")

    return response.text
