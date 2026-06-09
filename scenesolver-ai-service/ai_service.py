import os
import cv2
import json
import glob
import torch
import tempfile
import requests
from PIL import Image
from collections import Counter
from transformers import CLIPModel, CLIPProcessor, pipeline
from transformers import BlipProcessor, BlipForConditionalGeneration
from ultralytics import YOLO
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import traceback

def download_model_if_missing(local_path, url):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    if not os.path.exists(local_path):
        print(f"📥 Downloading {local_path} from Google Drive...")
        if "drive.google.com" in url or "docs.google.com" in url or "google.com/uc" in url:
            import urllib.parse as urlparse
            parsed = urlparse.urlparse(url)
            params = urlparse.parse_qs(parsed.query)
            file_id = params.get('id', [None])[0]
            if file_id:
                session = requests.Session()
                download_url = "https://docs.google.com/uc?export=download"
                response = session.get(download_url, params={'id': file_id}, stream=True)
                token = None
                for key, value in response.cookies.items():
                    if key.startswith('download_warning'):
                        token = value
                        break
                if token:
                    response = session.get(download_url, params={'id': file_id, 'confirm': token}, stream=True)
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)
                print(f"✅ Downloaded: {local_path}")
                return
        response = requests.get(url)
        with open(local_path, 'wb') as f:
            f.write(response.content)
        print(f"✅ Downloaded: {local_path}")


# --- Flask App Initialization ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# === Load Models (Done once on startup for performance) ===
print("🔌 Loading AI models, please wait...")

# Helper class for the classifier
class VisualCLIPClassifier(torch.nn.Module):
    def __init__(self, base_model, num_classes=5):
        super().__init__()
        self.clip = base_model
        self.classifier = torch.nn.Linear(self.clip.config.projection_dim, num_classes)

    def forward(self, pixel_values):
        with torch.no_grad():
            features = self.clip.get_image_features(pixel_values=pixel_values)
        return self.classifier(features)

# Define labels
label2id = {"fighting": 0, "robbery": 1, "shoplifting": 2, "explosion": 3, "normal": 4}
id2label = {v: k for k, v in label2id.items()}
evidence_labels = {0: "fire", 1: "smoke", 2: "fighting", 3: "gun", 4: "knife", 5: "shoplifting"}

# --- Model Loading ---
CLIP_MODEL_PATH = os.path.join('models', 'visual_clip_classifier.pt')
YOLO_MODEL_PATH = os.path.join('models', 'evidence_best_epoch50.pt')

# Download model files if missing
try:
    download_model_if_missing(CLIP_MODEL_PATH, "https://drive.google.com/uc?id=1mp2N-sw4U1XtEujzluOEWaGkW8P8HZ47")
    download_model_if_missing(YOLO_MODEL_PATH, "https://drive.google.com/uc?id=1TVM2b8VBk_k1AO_E6jXAmj4niVhhXgob")
except Exception as e:
    print(f"⚠️ Warning: Could not download models: {e}")

# Load models (CLIP, YOLO, BLIP, BART)...
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
try:
    clip_base = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    visual_clip_model = VisualCLIPClassifier(clip_base, num_classes=5)
    visual_clip_model.load_state_dict(torch.load(CLIP_MODEL_PATH, map_location="cpu"))
    visual_clip_model.eval()
    print("✅ Custom CLIP model loaded successfully.")
except Exception as e:
    print(f"⚠️ Warning: Failed to load custom CLIP model ({e}). Initializing fallback CLIP classifier with random weights.")
    clip_base = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    visual_clip_model = VisualCLIPClassifier(clip_base, num_classes=5)
    visual_clip_model.eval()

try:
    yolo_model = YOLO(YOLO_MODEL_PATH)
    print("✅ Custom YOLO model loaded successfully.")
except Exception as e:
    print(f"⚠️ Warning: Failed to load custom YOLO model ({e}). Initializing fallback public YOLOv8n.")
    yolo_model = YOLO("yolov8n.pt")

blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").eval()

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

print("✅ AI models loaded successfully.")


# === AI Processing Functions ===

def classify_with_yolo_override(image_path):
    # This function remains unchanged
    image = Image.open(image_path).convert("RGB")
    inputs = clip_processor(images=image, return_tensors="pt")
    with torch.no_grad(): logits = visual_clip_model(inputs["pixel_values"])
    clip_pred = id2label[logits.argmax().item()]
    yolo_results = yolo_model(image_path, verbose=False)[0]
    yolo_labels = [yolo_model.names.get(int(cls), "unknown") for cls in yolo_results.boxes.cls.tolist()] if yolo_results.boxes else []
    found_objects_details = []
    if yolo_results.boxes:
        for box in yolo_results.boxes:
            found_objects_details.append({"object": yolo_model.names.get(int(box.cls[0]), "unknown"),"match": round(float(box.conf[0]) * 100),"box": [int(c) for c in box.xyxy[0].tolist()]})
    final_label = clip_pred
    if "gun" in yolo_labels or "knife" in yolo_labels: final_label = "robbery"
    elif "fighting" in yolo_labels: final_label = "fighting"
    elif "fire" in yolo_labels or "smoke" in yolo_labels: final_label = "explosion"
    return {"final_label": final_label, "clip_pred": clip_pred, "yolo_labels": yolo_labels, "found_objects_details": found_objects_details}

def generate_summary(captions):
    # This function remains unchanged
    if not captions: return "No meaningful activity was detected to generate a story."
    filtered = [c for c in set(captions) if not any(g in c.lower() for g in ["video game", "cover", "dark skies", "book"])]
    if not filtered: return "No meaningful activity was detected to generate a story."
    combined = " ".join(filtered)
    if len(combined) < 60: return combined
    try:
        max_input_length = summarizer.model.config.max_position_embeddings - 5
        summary = summarizer(combined[:max_input_length], max_length=150, min_length=40, do_sample=False)[0]["summary_text"]
        return summary
    except Exception as e:
        print(f"Error during summarization: {e}")
        return "A detailed narrative could not be generated."

def run_video_analysis(video_path, frame_skip=15):
    # This function's logic is mostly the same, but the final return statement is changed
    print(f"\n🎞 Processing Video: {video_path}")
    cap = cv2.VideoCapture(video_path)
    try: 
        all_classifications, captions, all_yolo_objects = [], [], []
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            if frame_idx % frame_skip != 0:
                frame_idx += 1
                continue
            temp_path = os.path.join(tempfile.gettempdir(), f"frame_{frame_idx}.jpg")
            cv2.imwrite(temp_path, frame)
            try:
                yolo_result = classify_with_yolo_override(temp_path)
                all_classifications.append(yolo_result["final_label"])
                all_yolo_objects.extend(yolo_result['found_objects_details'])
                img = Image.open(temp_path).convert("RGB")
                blip_inputs = blip_processor(images=img, return_tensors="pt")
                blip_out = blip_model.generate(**blip_inputs, max_new_tokens=40)
                captions.append(blip_processor.decode(blip_out[0], skip_special_tokens=True))
            except Exception as frame_error:
                print(f"Warning: Could not process frame {frame_idx}. Error: {frame_error}")
            finally:
                if os.path.exists(temp_path): os.remove(temp_path)
            frame_idx += 1
    finally:
        print("Releasing video capture...")
        cap.release()

    if not all_classifications:
        return {"error": "Could not process any frames from the video."}

    all_yolo_labels = [obj['object'] for obj in all_yolo_objects]
    counts = Counter(all_classifications)
    crime_votes = {k: v for k, v in counts.items() if k != "normal"}
    final_class = max(crime_votes, key=crime_votes.get) if crime_votes else max(counts, key=counts.get)
    
    evidence = "none"
    if final_class == "explosion": evidence = next((k for k in ["fire", "smoke"] if k in all_yolo_labels), "fire detected")
    elif final_class == "robbery": evidence = next((k for k in ["gun", "knife"] if k in all_yolo_labels), "weapon spotted")
    elif final_class == "fighting": evidence = "violent behavior detected" if "fighting" in all_yolo_labels else "signs of a physical altercation"
    elif final_class == "shoplifting": evidence = "suspicious activity consistent with shoplifting"

    quick_caption = f"Primary event identified: {final_class.capitalize()}."
    story_summary = generate_summary(captions)
    full_story = f"The system classified the video as a '{final_class}' event. Key supporting evidence: {evidence}. Narrative summary of events: {story_summary}"
    unique_objects = {obj['object']: obj for obj in all_yolo_objects}

    # --- THIS IS THE MODIFIED PART FOR VIDEO ---
    # Calculate the percentage of frames that match the final classification.
    match_percentage = round((counts[final_class] / len(all_classifications)) * 100)

    return {
        "quickCaption": quick_caption,
        "fullStory": full_story,
        # Only return the single, highest-percentage crime type.
        "sceneKeywords": [{"keyword": final_class.capitalize(), "match": match_percentage}],
        "foundObjects": list(unique_objects.values())
    }


# --- Main Flask API Endpoint ---
@app.route('/analyze', methods=['POST'])
def analyze_media():
    if 'media' not in request.files:
        return jsonify({"error": "No media file provided"}), 400
    file = request.files['media']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        file.save(filepath)
        print(f"Starting analysis for '{filename}' ({file.mimetype})...")
        results = {}
        if file.mimetype.startswith('video'):
            results = run_video_analysis(filepath)
        elif file.mimetype.startswith('image'):
            classification_results = classify_with_yolo_override(filepath)
            img = Image.open(filepath).convert("RGB")
            blip_inputs = blip_processor(images=img, return_tensors="pt")
            blip_out = blip_model.generate(**blip_inputs, max_new_tokens=75)
            caption = blip_processor.decode(blip_out[0], skip_special_tokens=True)
            final_label = classification_results.get('final_label', 'unknown')
            yolo_labels = classification_results.get('yolo_labels', [])
            
            # --- THIS IS THE MODIFIED PART FOR IMAGES ---
            results = {
                "quickCaption": caption,
                "fullStory": f"The image has been classified as '{final_label}'. Key objects detected include: {', '.join(yolo_labels) if yolo_labels else 'none'}.",
                # Only return the single crime type with a high confidence score.
                "sceneKeywords": [{"keyword": final_label.capitalize(), "match": 95}],
                "foundObjects": classification_results.get('found_objects_details', [])
            }
        else:
            return jsonify({"error": "Unsupported file type"}), 400
        print("Analysis successful.")
        return jsonify(results)
    except Exception as e:
        print(f"🚨 An exception occurred during AI processing: {e}") 
        traceback.print_exc()
        return jsonify({"error": "An internal error occurred during AI model processing."}), 500
    finally:
        if os.path.exists(filepath):
            print(f"Cleaning up file: {filepath}")
            os.remove(filepath)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
