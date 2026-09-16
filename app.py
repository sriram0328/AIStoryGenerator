from flask import Flask, render_template, request, url_for, jsonify
from werkzeug.utils import secure_filename
from gtts import gTTS
from PIL import Image
import os
import tempfile
import uuid
from gemini_helper import analyze_image, generate_story  # Assuming these are your helper functions

# Initialize Flask app
app = Flask(__name__)

# Configure upload and audio folders
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['AUDIO_FOLDER'] = 'static/audio'
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB upload limit

# Ensure required directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

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


@app.route("/upload", methods=["POST"])
def upload():
    """STEP 1: Save the photo only. No Gemini call happens here."""
    file = request.files.get("file")

    if file is None or not file.filename:
        return jsonify({
            "success": False,
            "error": "No photo was received. Please choose an image."
        }), 400

    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": "Please upload JPG, JPEG, PNG, or WEBP."
        }), 400

    extension = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    try:
        file.save(image_path)

        # Validate that it is actually an image.
        with Image.open(image_path) as image:
            image.verify()

    except Exception as e:
        if os.path.exists(image_path):
            os.remove(image_path)

        print(f"Upload validation failed: {e}")
        return jsonify({
            "success": False,
            "error": "The selected file is not a valid image."
        }), 400

    print(f"PHOTO UPLOADED: {image_path}")

    return jsonify({
        "success": True,
        "filename": filename,
        "image_url": url_for("static", filename=f"uploads/{filename}")
    })


@app.route("/generate", methods=["POST"])
def generate():
    """STEP 2: Generate story only after the user clicks the Generate button."""
    filename = request.form.get("filename", "").strip()
    genre = request.form.get("genre", "").strip()

    if not filename:
        return jsonify({
            "success": False,
            "error": "Please upload a photo first."
        }), 400

    if not genre:
        return jsonify({
            "success": False,
            "error": "Please select a story type."
        }), 400

    # Only allow our generated filenames, preventing path traversal.
    if not re.fullmatch(r"[a-f0-9]{32}\.(jpg|jpeg|png|webp)", filename):
        return jsonify({
            "success": False,
            "error": "Invalid uploaded photo. Please upload it again."
        }), 400

    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if not os.path.isfile(image_path):
        return jsonify({
            "success": False,
            "error": "Uploaded photo was not found. Please upload it again."
        }), 404

    tmp_path = None

    try:
        # Convert the uploaded image to PNG for Gemini.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp_path = tmp.name

            with Image.open(image_path) as image:
                # Handle transparency and different image modes safely.
                if image.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", image.size, "white")
                    background.paste(image, mask=image.getchannel("A"))
                    image = background
                else:
                    image = image.convert("RGB")

                image.save(tmp_path, format="PNG")

        print(f"GENERATING STORY: genre={genre}, image={filename}")

        # Gemini + story generation happens ONLY after Generate is clicked.
        analysis = analyze_image(tmp_path)
        story = generate_story(analysis, genre)

        if not story:
            raise RuntimeError("Gemini returned an empty story.")

        # TTS is optional. If gTTS fails, the story should STILL be shown.
        audio_url = None

        try:
            audio_filename = (
                f"{os.path.splitext(filename)[0]}_{secure_filename(genre)}.mp3"
            )
            audio_path = os.path.join(
                app.config["AUDIO_FOLDER"], audio_filename
            )

            tts = gTTS(text=story, lang="en")
            tts.save(audio_path)

            audio_url = url_for(
                "static",
                filename=f"audio/{audio_filename}"
            )

        except Exception as audio_error:
            print(f"TTS failed (story will still be returned): {audio_error}")

        print("STORY GENERATED SUCCESSFULLY")

        return jsonify({
            "success": True,
            "story": story,
            "genre": genre,
            "audio_url": audio_url,
            "image_url": url_for(
                "static",
                filename=f"uploads/{filename}"
            )
        })

    except Exception as e:
        # IMPORTANT: return the real server error while debugging instead
        # of hiding it behind a generic 500.
        print(f"STORY GENERATION FAILED: {type(e).__name__}: {e}")

        return jsonify({
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.errorhandler(413)
def request_too_large(error):
    return jsonify({
        "success": False,
        "error": "Photo is too large. Maximum upload size is 8 MB."
    }), 413


if __name__ == "__main__":
    app.run(debug=True)
