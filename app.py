from flask import Flask, render_template, request, url_for, jsonify
from werkzeug.utils import secure_filename
from gtts import gTTS
from PIL import Image
import os
import tempfile
import uuid
import re

from gemini_helper import analyze_image, generate_story


# ============================================================
# INITIALIZE FLASK
# ============================================================

app = Flask(__name__)

app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["AUDIO_FOLDER"] = "static/audio"

app.config["ALLOWED_EXTENSIONS"] = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}

# Maximum upload size: 8 MB
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


# ============================================================
# CREATE DIRECTORIES
# ============================================================

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["AUDIO_FOLDER"], exist_ok=True)


# ============================================================
# FILE VALIDATION
# ============================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in app.config["ALLOWED_EXTENSIONS"]
    )


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/", methods=["GET"])
def index():

    return render_template(
        "index.html",
        image_path=None,
        story=None,
        genre=None,
        audio_path=None,
        error=None
    )


# ============================================================
# STEP 1 — UPLOAD PHOTO
# ============================================================

@app.route("/upload", methods=["POST"])
def upload():
    """
    Upload and validate the photo.

    IMPORTANT:
    Gemini is NOT called here.

    This allows:
        Upload → show uploaded message → select genre → Generate
    """

    file = request.files.get("file")

    if file is None or not file.filename:

        return jsonify({
            "success": False,
            "error": "No photo was received. Please choose an image."
        }), 400


    # Check extension
    if not allowed_file(file.filename):

        return jsonify({
            "success": False,
            "error": "Please upload JPG, JPEG, PNG, or WEBP."
        }), 400


    extension = file.filename.rsplit(".", 1)[1].lower()

    filename = f"{uuid.uuid4().hex}.{extension}"

    image_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )


    try:

        # Save uploaded image
        file.save(image_path)


        # Validate actual image contents
        with Image.open(image_path) as image:
            image.verify()


    except Exception as e:

        if os.path.exists(image_path):
            os.remove(image_path)

        print(
            f"Upload validation failed: "
            f"{type(e).__name__}: {e}"
        )

        return jsonify({
            "success": False,
            "error": "The selected file is not a valid image."
        }), 400


    print(f"PHOTO UPLOADED: {image_path}")


    return jsonify({
        "success": True,
        "filename": filename,
        "image_url": url_for(
            "static",
            filename=f"uploads/{filename}"
        )
    })


# ============================================================
# STEP 2 — GENERATE STORY
# ============================================================

@app.route("/generate", methods=["POST"])
def generate():
    """
    Generate the story only after the user clicks Generate.
    """

    filename = request.form.get(
        "filename",
        ""
    ).strip()

    genre = request.form.get(
        "genre",
        ""
    ).strip()


    # --------------------------------------------------------
    # Validate filename
    # --------------------------------------------------------

    if not filename:

        return jsonify({
            "success": False,
            "error": "Please upload a photo first."
        }), 400


    # --------------------------------------------------------
    # Validate genre
    # --------------------------------------------------------

    if not genre:

        return jsonify({
            "success": False,
            "error": "Please select a story type."
        }), 400


    # --------------------------------------------------------
    # Security validation
    # --------------------------------------------------------

    if not re.fullmatch(
        r"[a-f0-9]{32}\.(jpg|jpeg|png|webp)",
        filename
    ):

        return jsonify({
            "success": False,
            "error": "Invalid uploaded photo. Please upload it again."
        }), 400


    # --------------------------------------------------------
    # Find uploaded image
    # --------------------------------------------------------

    image_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )


    if not os.path.isfile(image_path):

        return jsonify({
            "success": False,
            "error": "Uploaded photo was not found. Please upload it again."
        }), 404


    tmp_path = None


    try:

        # ====================================================
        # CONVERT IMAGE TO PNG
        # ====================================================

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".png"
        ) as tmp:

            tmp_path = tmp.name


            with Image.open(image_path) as image:

                # Handle transparency
                if image.mode in ("RGBA", "LA"):

                    background = Image.new(
                        "RGB",
                        image.size,
                        "white"
                    )

                    background.paste(
                        image,
                        mask=image.getchannel("A")
                    )

                    image = background

                else:

                    image = image.convert("RGB")


                image.save(
                    tmp_path,
                    format="PNG"
                )


        print(
            f"GENERATING STORY: "
            f"genre={genre}, image={filename}"
        )


        # ====================================================
        # GEMINI — IMAGE ANALYSIS
        # ====================================================

        analysis = analyze_image(tmp_path)


        if not analysis:

            raise RuntimeError(
                "Gemini returned an empty image analysis."
            )


        print("IMAGE ANALYSIS COMPLETED")


        # ====================================================
        # GEMINI — STORY GENERATION
        # ====================================================

        story = generate_story(
            analysis,
            genre
        )


        if not story:

            raise RuntimeError(
                "Gemini returned an empty story."
            )


        print("STORY GENERATED SUCCESSFULLY")


        # ====================================================
        # TEXT TO SPEECH
        # ====================================================

        audio_url = None


        try:

            audio_filename = (
                f"{os.path.splitext(filename)[0]}_"
                f"{secure_filename(genre)}.mp3"
            )


            audio_path = os.path.join(
                app.config["AUDIO_FOLDER"],
                audio_filename
            )


            tts = gTTS(
                text=story,
                lang="en"
            )

            tts.save(audio_path)


            audio_url = url_for(
                "static",
                filename=f"audio/{audio_filename}"
            )


            print("AUDIO GENERATED SUCCESSFULLY")


        except Exception as audio_error:

            # Audio failure should NOT prevent story display.

            print(
                "TTS FAILED "
                f"{type(audio_error).__name__}: "
                f"{audio_error}"
            )


        # ====================================================
        # SUCCESS RESPONSE
        # ====================================================

        return jsonify({

            "success": True,

            "story": story,

            "genre": genre,

            "audio_url": audio_url,

            "image_url": url_for(
                "static",
                filename=f"uploads/{filename}"
            )

        }), 200


    # ========================================================
    # GEMINI TEMPORARY ERROR
    # ========================================================

    except RuntimeError as e:

        error_message = str(e)

        print(
            f"STORY GENERATION ERROR: "
            f"{error_message}"
        )


        # If Gemini is temporarily overloaded,
        # return 503 instead of generic 500.

        if (
            "temporarily" in error_message.lower()
            or "high demand" in error_message.lower()
            or "503" in error_message
            or "UNAVAILABLE" in error_message
        ):

            return jsonify({

                "success": False,

                "error":
                    "Gemini is temporarily busy. "
                    "Please wait a few seconds and try again."

            }), 503


        return jsonify({

            "success": False,

            "error": error_message

        }), 500


    # ========================================================
    # OTHER ERRORS
    # ========================================================

    except Exception as e:

        print(
            f"STORY GENERATION FAILED: "
            f"{type(e).__name__}: {e}"
        )


        return jsonify({

            "success": False,

            "error":
                f"{type(e).__name__}: {str(e)}"

        }), 500


    # ========================================================
    # CLEAN TEMP FILE
    # ========================================================

    finally:

        if (
            tmp_path
            and os.path.exists(tmp_path)
        ):

            try:
                os.remove(tmp_path)
            except Exception:
                pass


# ============================================================
# FILE TOO LARGE
# ============================================================

@app.errorhandler(413)
def request_too_large(error):

    return jsonify({

        "success": False,

        "error":
            "Photo is too large. "
            "Maximum upload size is 8 MB."

    }), 413


# ============================================================
# UNEXPECTED ERRORS
# ============================================================

@app.errorhandler(Exception)
def handle_unexpected_error(error):

    print(
        f"UNHANDLED SERVER ERROR: "
        f"{type(error).__name__}: {error}"
    )


    # API endpoints should ALWAYS return JSON.

    if request.path in (
        "/upload",
        "/generate"
    ):

        return jsonify({

            "success": False,

            "error":
                f"{type(error).__name__}: {str(error)}"

        }), 500


    raise error


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )
