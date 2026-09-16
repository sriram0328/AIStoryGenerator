import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is not configured in Render Environment."
    )

api_key = api_key.strip()

client = genai.Client(api_key=api_key)

MODEL = "gemini-3.6-flash"


# ============================================================
# GEMINI REQUEST
# ============================================================

def generate_content(contents):
    """
    Send a request to Gemini.

    We intentionally do not perform long manual retries here.
    Render's Gunicorn worker has a request timeout, so sleeping
    during a 503 can kill the worker.
    """

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
        )

        return response

    except errors.ServerError as e:

        # Gemini temporarily unavailable / overloaded.
        if getattr(e, "status_code", None) == 503:

            raise RuntimeError(
                "Gemini is temporarily experiencing high demand. "
                "Please try again in a few seconds."
            ) from e

        raise


# ============================================================
# IMAGE ANALYSIS
# ============================================================

def analyze_image(image_path):

    prompt = """
Analyze this image in detail for a children's story.

Describe:

1. The main elements and their relationships
2. Colors and mood
3. Potential story themes
4. Interesting or unusual details
5. Any relevant cultural or historical context if visible

Be descriptive but concise.

Focus on details that can inspire a fun,
child-friendly story for children ages 5-8.
"""

    # Read image directly.
    # We do NOT use client.files.upload().
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # Determine MIME type.
    extension = os.path.splitext(image_path)[1].lower()

    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }

    mime_type = mime_types.get(extension)

    if not mime_type:
        raise ValueError(
            f"Unsupported image format: {extension}"
        )

    # Create image part.
    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type,
    )

    # Send image to Gemini.
    response = generate_content(
        contents=[
            image_part,
            prompt
        ]
    )

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty image analysis."
        )

    return response.text


# ============================================================
# STORY GENERATION
# ============================================================

def generate_story(image_description, genre):

    prompt = f"""
Based on this image analysis:

{image_description}

Create a {genre} children's story of approximately 200 words.

Requirements:

1. Use playful language suitable for children ages 5-8.
2. Include a positive moral lesson.
3. Include magical or fantasy elements when appropriate
   for the selected genre.
4. Make the story fun for parent-child reading.
5. Use short, easy-to-read paragraphs.
6. Emoji illustrations are allowed.
7. Do not include choices for the reader.
8. Do not ask questions to the reader.
9. Do not stop the story halfway.
10. The story should flow continuously from beginning to end.
11. Give the story a clear and satisfying ending.

Selected genre:
{genre}
"""

    response = generate_content(
        contents=prompt
    )

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty story."
        )

    return response.text
