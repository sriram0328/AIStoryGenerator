import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is not configured in the environment."
    )

api_key = api_key.strip()

# Explicitly use GEMINI_API_KEY.
client = genai.Client(api_key=api_key)

# More established/available Flash model.
MODEL = "gemini-2.5-flash"


# ============================================================
# GEMINI REQUEST WITH RETRY
# ============================================================

def generate_with_retry(contents, max_retries=3):
    """
    Send a request to Gemini.

    Automatically retries temporary 503/unavailable errors.
    """

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
            )

            return response

        except Exception as e:

            error_message = str(e)

            # Retry temporary Gemini overload errors.
            if "503" in error_message or "UNAVAILABLE" in error_message:

                if attempt < max_retries - 1:
                    wait_time = 3 * (attempt + 1)

                    print(
                        f"Gemini temporarily unavailable. "
                        f"Retrying in {wait_time} seconds..."
                    )

                    time.sleep(wait_time)
                    continue

            # Any other error, or exhausted retries.
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

    # --------------------------------------------------------
    # Read image directly.
    # We intentionally DO NOT use client.files.upload().
    # --------------------------------------------------------

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # --------------------------------------------------------
    # Determine image MIME type.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Create image part from bytes.
    # --------------------------------------------------------

    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type,
    )

    # --------------------------------------------------------
    # Send image + prompt to Gemini.
    # --------------------------------------------------------

    response = generate_with_retry(
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

    # --------------------------------------------------------
    # Generate story.
    # --------------------------------------------------------

    response = generate_with_retry(
        contents=prompt
    )

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty story."
        )

    return response.text
