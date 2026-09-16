import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Use ONLY GEMINI_API_KEY.
# This avoids accidentally picking up a stale GOOGLE_API_KEY.
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. Add your Gemini API key to the environment."
    )

api_key = api_key.strip()

client = genai.Client(api_key=api_key)

MODEL = "gemini-3.8-flash"


def analyze_image(image_path):
    prompt = """
Analyze this image in detail for a children's story.

Describe:
1. The main elements and their relationships
2. Colors and mood
3. Potential story themes
4. Interesting or unusual details
5. Any relevant cultural or historical context if visible

Be descriptive but concise. Focus on details that can inspire a
fun, child-friendly story for ages 5-8.
"""

    # Read the image directly instead of using Gemini Files API.
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # Detect MIME type from the file extension.
    ext = os.path.splitext(image_path)[1].lower()

    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }

    mime_type = mime_types.get(ext, "image/jpeg")

    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type,
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            image_part,
            prompt
        ],
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
