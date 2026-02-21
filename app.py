import os
import uuid
import base64
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
RESULTS_DIR = os.path.join(app.static_folder, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
MIME_MAP = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
MIME_TO_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def file_to_part(file_storage):
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    return types.Part.from_bytes(data=file_storage.read(), mime_type=MIME_MAP[ext])


def load_image_file(directory, image_id):
    """Find an image by numeric ID in a directory. Returns (filepath, ext) or (None, None)."""
    for ext in ("jpg", "jpeg", "png", "webp"):
        path = os.path.join(directory, f"{image_id}.{ext}")
        if os.path.isfile(path):
            return path, ext
    return None, None


def path_to_part(filepath, ext):
    with open(filepath, "rb") as f:
        return types.Part.from_bytes(data=f.read(), mime_type=MIME_MAP[ext])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY is not set. Add it to your .env file."}), 500

    person_file = request.files.get("person_image")
    outfit_files = request.files.getlist("outfit_images")

    if not person_file:
        return jsonify({"error": "A person image is required."}), 400
    if not outfit_files:
        return jsonify({"error": "At least one outfit piece image is required."}), 400
    if len(outfit_files) > 13:
        return jsonify({"error": "You can upload up to 13 outfit pieces (14 images total with your photo)."}), 400

    all_files = [person_file] + outfit_files
    for f in all_files:
        if not allowed_file(f.filename):
            return jsonify({"error": f"Invalid file type: {f.filename}. Only PNG, JPG, JPEG, and WEBP are allowed."}), 400

    person_part = file_to_part(person_file)
    outfit_parts = [file_to_part(f) for f in outfit_files]

    n = len(outfit_files)
    prompt = (
        f"You will be given {n + 1} images.\n\n"

        "IMAGE 1 (PRIMARY SUBJECT / IDENTITY REFERENCE — LOCKED):\n"
        "This image contains the real person who must appear in the final output.\n"
        "Treat Image 1 as IDENTITY-LOCKED and BODY-LOCKED.\n"
        "Preserve exactly: face, skin tone, body shape, body proportions, hair, hands, legs, posture, and pose.\n"
        "Do NOT change the person's identity or physical appearance in any way.\n"
        "Do NOT change camera angle, framing, or background unless absolutely necessary for realism.\n\n"

        f"IMAGES 2 THROUGH {n + 1} (GARMENT SOURCES ONLY — NOT SUBJECTS):\n"
        "Each of these images contains one clothing item or accessory to use (e.g., top, pants, shoes, jacket, hat, bag).\n"
        "These images may include flat-lays, hanger shots, or clothing worn by placeholder models.\n"
        "IMPORTANT: If a person/model appears in any of these images, they are ONLY a mannequin/placeholder.\n"
        "Extract ONLY the clothing/accessory item(s). Ignore and discard the placeholder person's face, skin, hair, body shape, pose, and all body parts.\n"
        "Do NOT transfer any human attributes from Images 2..N into the final image.\n\n"

        "TASK:\n"
        "Dress the person from Image 1 in ALL clothing/accessory items extracted from Images 2..N, combining them into one cohesive outfit.\n"
        "The final image must be a single photorealistic photo of the ORIGINAL person from Image 1 wearing the extracted outfit.\n\n"

        "STRICT RULES (MUST FOLLOW):\n"
        "1) Identity Preservation (Highest Priority): Image 1 person is immutable except for clothing changes.\n"
        "2) Garment-Only Extraction: Use only garments/accessories from Images 2..N; never use any body/face/hair features from those images.\n"
        "3) No Placeholder Transfer: Do not copy or blend placeholder model pose, limbs, skin tone, body shape, or facial structure.\n"
        "4) Fit & Drape Realistically: Adjust garments to the Image 1 person's exact body proportions and pose.\n"
        "5) Preserve Garment Details: Keep original fabric texture, pattern, color, stitching, logos, trims, and silhouette.\n"
        "6) Correct Layering: Place items in realistic order (e.g., shirt under jacket, shoes on feet, hat on head).\n"
        "7) Lighting Consistency: Match the lighting/shadows of Image 1.\n"
        "8) Background Preservation: Keep Image 1 background unless minor adjustments are needed for realism.\n"
        "9) No Hallucinated Body Changes: Do not slim, widen, reshape, re-pose, beautify, age, or otherwise alter the Image 1 person.\n"
        "10) If any garment image is ambiguous or occluded, prioritize preserving the Image 1 person unchanged and apply only the clearly visible garment details.\n\n"

        "OUTPUT:\n"
        "Return one photorealistic image of the Image 1 person wearing the complete outfit assembled from Images 2..N."
    )

    contents = [prompt, person_part] + outfit_parts

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        image_bytes = None
        result_text = None
        mime = "image/png"

        for part in response.parts:
            if part.text is not None:
                result_text = part.text
            elif part.inline_data is not None:
                image_bytes = part.inline_data.data
                mime = part.inline_data.mime_type or "image/png"

        if not image_bytes:
            return jsonify({
                "error": "The model did not return an image. Try a different prompt.",
                "model_text": result_text,
            }), 422

        ext = MIME_TO_EXT.get(mime, "png")
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(RESULTS_DIR, filename)

        raw = image_bytes if isinstance(image_bytes, bytes) else base64.b64decode(image_bytes)
        with open(filepath, "wb") as f:
            f.write(raw)

        return jsonify({
            "image_url": f"/static/results/{filename}",
            "download_url": f"/download/{filename}",
            "model_text": result_text,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(RESULTS_DIR, filename, as_attachment=True)


@app.route("/image/<int:image_id>")
def get_image(image_id):
    for ext in ("jpg", "jpeg", "png", "webp"):
        filepath = os.path.join(IMAGES_DIR, f"{image_id}.{ext}")
        if os.path.isfile(filepath):
            return send_from_directory(IMAGES_DIR, f"{image_id}.{ext}")
    return jsonify({"error": f"Image {image_id} not found."}), 404


@app.route("/tryon", methods=["POST"])
def tryon():
    """
    Generate a try-on image from a model_id and a list of image_ids.

    JSON body:
        {
            "model_id": 123,
            "image_ids": [15187, 39386, 39988]
        }

    Returns the generated image as a file download.
    """
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY is not set."}), 500

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON with model_id and image_ids."}), 400

    model_id = data.get("model_id")
    image_ids = data.get("image_ids", [])

    if model_id is None:
        return jsonify({"error": "model_id is required."}), 400
    if not image_ids or not isinstance(image_ids, list):
        return jsonify({"error": "image_ids must be a non-empty list."}), 400
    if len(image_ids) > 13:
        return jsonify({"error": "You can provide up to 13 outfit image_ids."}), 400

    model_path, model_ext = load_image_file(MODELS_DIR, model_id)
    if not model_path:
        return jsonify({"error": f"Model image {model_id} not found in models folder."}), 404

    person_part = path_to_part(model_path, model_ext)

    outfit_parts = []
    for img_id in image_ids:
        img_path, img_ext = load_image_file(IMAGES_DIR, img_id)
        if not img_path:
            return jsonify({"error": f"Outfit image {img_id} not found in images folder."}), 404
        outfit_parts.append(path_to_part(img_path, img_ext))

    n = len(image_ids)
    prompt = (
        f"You will be given {n + 1} images.\n\n"

        "IMAGE 1 (PRIMARY SUBJECT / IDENTITY REFERENCE — LOCKED):\n"
        "This image contains the real person who must appear in the final output.\n"
        "Treat Image 1 as IDENTITY-LOCKED and BODY-LOCKED.\n"
        "Preserve exactly: face, skin tone, body shape, body proportions, hair, hands, legs, posture, and pose.\n"
        "Do NOT change the person's identity or physical appearance in any way.\n"
        "Do NOT change camera angle, framing, or background unless absolutely necessary for realism.\n\n"

        f"IMAGES 2 THROUGH {n + 1} (GARMENT SOURCES ONLY — NOT SUBJECTS):\n"
        "Each of these images contains one clothing item or accessory to use (e.g., top, pants, shoes, jacket, hat, bag).\n"
        "These images may include flat-lays, hanger shots, or clothing worn by placeholder models.\n"
        "IMPORTANT: If a person/model appears in any of these images, they are ONLY a mannequin/placeholder.\n"
        "Extract ONLY the clothing/accessory item(s). Ignore and discard the placeholder person's face, skin, hair, body shape, pose, and all body parts.\n"
        "Do NOT transfer any human attributes from Images 2..N into the final image.\n\n"

        "TASK:\n"
        "Dress the person from Image 1 in ALL clothing/accessory items extracted from Images 2..N, combining them into one cohesive outfit.\n"
        "The final image must be a single photorealistic photo of the ORIGINAL person from Image 1 wearing the extracted outfit.\n\n"

        "STRICT RULES (MUST FOLLOW):\n"
        "1) Identity Preservation (Highest Priority): Image 1 person is immutable except for clothing changes.\n"
        "2) Garment-Only Extraction: Use only garments/accessories from Images 2..N; never use any body/face/hair features from those images.\n"
        "3) No Placeholder Transfer: Do not copy or blend placeholder model pose, limbs, skin tone, body shape, or facial structure.\n"
        "4) Fit & Drape Realistically: Adjust garments to the Image 1 person's exact body proportions and pose.\n"
        "5) Preserve Garment Details: Keep original fabric texture, pattern, color, stitching, logos, trims, and silhouette.\n"
        "6) Correct Layering: Place items in realistic order (e.g., shirt under jacket, shoes on feet, hat on head).\n"
        "7) Lighting Consistency: Match the lighting/shadows of Image 1.\n"
        "8) Background Preservation: Keep Image 1 background unless minor adjustments are needed for realism.\n"
        "9) No Hallucinated Body Changes: Do not slim, widen, reshape, re-pose, beautify, age, or otherwise alter the Image 1 person.\n"
        "10) If any garment image is ambiguous or occluded, prioritize preserving the Image 1 person unchanged and apply only the clearly visible garment details.\n\n"

        "OUTPUT:\n"
        "Return one photorealistic image of the Image 1 person wearing the complete outfit assembled from Images 2..N."
    )

    contents = [prompt, person_part] + outfit_parts

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        image_bytes = None
        result_text = None
        mime = "image/png"

        for part in response.parts:
            if part.text is not None:
                result_text = part.text
            elif part.inline_data is not None:
                image_bytes = part.inline_data.data
                mime = part.inline_data.mime_type or "image/png"

        if not image_bytes:
            return jsonify({
                "error": "The model did not return an image.",
                "model_text": result_text,
            }), 422

        ext = MIME_TO_EXT.get(mime, "png")
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(RESULTS_DIR, filename)

        raw = image_bytes if isinstance(image_bytes, bytes) else base64.b64decode(image_bytes)
        with open(filepath, "wb") as f:
            f.write(raw)

        if request.args.get("raw") == "1":
            return send_file(filepath, mimetype=mime)

        return jsonify({
            "image_url": f"/static/results/{filename}",
            "download_url": f"/download/{filename}",
            "model_text": result_text,
            "model_id": model_id,
            "image_ids": image_ids,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    app.run(debug=True, port=5002)
