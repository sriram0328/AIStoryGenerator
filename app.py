from flask import Flask, render_template, request, url_for, jsonify, session
from werkzeug.utils import secure_filename
from gtts import gTTS
from PIL import Image
import os
import tempfile
import uuid
from gemini_helper import analyze_image, generate_story  # Assuming these are your helper functions

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

# Configure upload and audio folders
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['AUDIO_FOLDER'] = 'static/audio'
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png'}
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
        image_path=session.get("uploaded_image"),
        story=None,
        genre=None,
        audio_path=None,
        error=None
    )


@app.route("/upload", methods=["POST"])
def upload():
    """Upload only. Story generation does NOT happen here."""
    file = request.files.get("file")

    if not file or file.filename == "":
        return jsonify({"success": False, "error": "Please choose an image to upload."}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": "That file type isn't supported. Please upload a JPG or PNG image."
        }), 400

    # Give every upload a unique filename so one user's file doesn't overwrite another's.
    extension = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(image_path)

    session["uploaded_image"] = filename

    print(f"Image uploaded: {image_path}")

    return jsonify({
        "success": True,
        "filename": filename,
        "image_url": url_for("static", filename=f"uploads/{filename}")
    })


@app.route("/generate", methods=["POST"])
def generate():
    """Generate the story only after the user clicks Create My Story."""
    genre = request.form.get("genre")
    filename = session.get("uploaded_image")

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

    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if not os.path.isfile(image_path):
        session.pop("uploaded_image", None)
        return jsonify({
            "success": False,
            "error": "The uploaded photo could not be found. Please upload it again."
        }), 404

    tmp_path = None

    try:
        # Convert/open the uploaded image for Gemini.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp_path = tmp.name
            image = Image.open(image_path)
            image.load()
            image.save(tmp_path, format="PNG")

        # AI work starts ONLY here, after Generate is clicked.
        analysis = analyze_image(tmp_path)
        story = generate_story(analysis, genre)

        # Generate audio after the story is created.
        audio_filename = f"{os.path.splitext(filename)[0]}_{secure_filename(genre)}.mp3"
        audio_path = os.path.join(app.config["AUDIO_FOLDER"], audio_filename)

        tts = gTTS(text=story, lang="en")
        tts.save(audio_path)

        return jsonify({
            "success": True,
            "story": story,
            "genre": genre,
            "audio_url": url_for("static", filename=f"audio/{audio_filename}"),
            "image_url": url_for("static", filename=f"uploads/{filename}")
        })

    except Exception as e:
        print(f"Story generation failed: {e}")
        return jsonify({
            "success": False,
            "error": "Something went wrong while creating your story. Please try again."
        }), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    app.run(debug=True)
