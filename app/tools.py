"""Firestore tools for TriCoach agent."""

import datetime
import json
import os
import urllib.parse
import urllib.request
import google.auth
import google.auth.transport.requests
import requests
from google import genai
from google.adk.tools import ToolContext
from google.cloud import firestore, storage
from google.genai import types

# Hardcode GCP Project ID and Bucket Name explicitly per Agent Platform requirements
PROJECT_ID = "qwiklabs-gcp-02-feeccdad7474"
BUCKET_NAME = "tricoach-media-qwiklabs-gcp-02-feeccdad7474"


def get_firestore_client():
    """Returns a Firestore client initialized with hardcoded project ID."""
    return firestore.Client(project=PROJECT_ID)


def search_exercise_catalog(category: str = "", target_muscle: str = "") -> list[dict]:
    """Search the exercise catalog in Firestore by category or target muscle.

    Args:
        category: Optional category filter (e.g., 'Strength', 'Cardio', 'Core').
        target_muscle: Optional target muscle filter (e.g., 'Chest', 'Legs', 'Abs').

    Returns:
        A list of matching exercise dictionaries.
    """
    db = get_firestore_client()
    query = db.collection("exercises")
    docs = query.stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id

        # Apply in-memory filtering for flexible string searching
        cat_match = not category or category.lower() in data.get("category", "").lower()
        
        muscles = [m.lower() for m in data.get("target_muscles", [])]
        muscle_match = not target_muscle or any(target_muscle.lower() in m for m in muscles)

        if cat_match and muscle_match:
            results.append(data)

    return results


def log_activity(activity_type: str, details: dict, notes: str = "") -> dict:
    """Log a workout, nutrition, or biometrics entry to Firestore.

    Args:
        activity_type: Type of activity ('workout', 'nutrition', or 'biometrics').
        details: Dictionary containing activity details:
            - For 'workout': exercise_name, sets, reps, weight_lbs, duration_mins.
            - For 'nutrition': calories, protein_g, water_ml.
            - For 'biometrics': steps, resting_heart_rate, spo2_pct, sleep_hours.
        notes: Optional user notes or coach comments.

    Returns:
        A dictionary confirming the created log entry.
    """
    db = get_firestore_client()
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    log_id = f"log_{date_str}_{activity_type}_{now_str}"

    log_entry = {
        "id": log_id,
        "date": date_str,
        "type": activity_type.lower(),
        "details": details,
        "notes": notes,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    db.collection("logs").document(log_id).set(log_entry)
    return {"status": "success", "message": f"Successfully logged {activity_type}", "log": log_entry}


def get_recent_logs(activity_type: str = "", limit: int = 5) -> list[dict]:
    """Retrieve recent activity logs from Firestore.

    Args:
        activity_type: Optional filter by log type ('workout', 'nutrition', or 'biometrics').
        limit: Maximum number of recent logs to return.

    Returns:
        A list of recent log dictionaries.
    """
    db = get_firestore_client()
    docs = db.collection("logs").stream()

    logs = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        if not activity_type or data.get("type", "").lower() == activity_type.lower():
            logs.append(data)

    # Sort descending by created_at or date
    logs.sort(key=lambda x: x.get("created_at", x.get("date", "")), reverse=True)
    return logs[:limit]


def calculate_fitness_metrics(
    weight_lbs: float = 160.0,
    height_inches: float = 68.0,
    age: int = 25,
    gender: str = "male",
    activity_level: str = "moderate",
    sleep_hours: float = 7.5,
    resting_hr: int = 65,
    spo2_pct: float = 98.0,
) -> dict:
    """Calculate BMR, TDEE, recommended daily protein, water targets, and recovery score.

    Args:
        weight_lbs: Weight in pounds.
        height_inches: Height in inches.
        age: Age in years.
        gender: 'male' or 'female'.
        activity_level: 'sedentary', 'light', 'moderate', or 'active'.
        sleep_hours: Last night's sleep duration in hours.
        resting_hr: Resting heart rate in beats per minute.
        spo2_pct: Blood oxygen saturation percentage.

    Returns:
        A dictionary of calculated BMR, TDEE, macro targets, and a Recovery Score (0-100).
    """
    weight_kg = weight_lbs * 0.453592
    height_cm = height_inches * 2.54

    # Mifflin-St Jeor equation for BMR
    if gender.lower() == "female":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5

    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
    }
    mult = activity_multipliers.get(activity_level.lower(), 1.55)
    tdee = bmr * mult

    target_protein_g = round(weight_lbs * 0.9)
    target_water_ml = round(weight_lbs * 35)

    # Recovery score calculation (0 - 100 scale)
    score = 100
    if sleep_hours < 7.0:
        score -= round((7.0 - sleep_hours) * 10)
    if resting_hr > 70:
        score -= (resting_hr - 70)
    if spo2_pct < 95.0:
        score -= round((95.0 - spo2_pct) * 5)

    recovery_score = max(0, min(100, score))

    return {
        "bmr_calories": round(bmr),
        "tdee_calories": round(tdee),
        "recommended_protein_g": target_protein_g,
        "recommended_water_ml": target_water_ml,
        "recovery_score": recovery_score,
        "inputs": {
            "weight_lbs": weight_lbs,
            "height_inches": height_inches,
            "age": age,
            "gender": gender,
            "activity_level": activity_level,
            "sleep_hours": sleep_hours,
            "resting_hr": resting_hr,
            "spo2_pct": spo2_pct,
        },
    }


def fetch_external_exercises(category_id: int = 0, limit: int = 5) -> list[dict]:
    """Fetch live exercise ideas from the wger Workout Manager public API (https://wger.de).

    Args:
        category_id: Optional category ID filter (e.g. 10 for Abs, 9 for Legs, 8 for Arms, 12 for Back, 11 for Chest).
        limit: Maximum number of exercise ideas to return.

    Returns:
        A list of exercise dictionaries fetched from the live wger API.
    """
    # Read optional API key from environment variable if configured
    api_key = os.getenv("WGER_API_KEY", "")

    url = f"https://wger.de/api/v2/exerciseinfo/?limit={limit}"
    if category_id > 0:
        url += f"&category={category_id}"

    headers = {"User-Agent": "TriCoachApp/1.0"}
    if api_key and api_key.lower() not in ("none", "dummy", "public", ""):
        headers["Authorization"] = f"Token {api_key}"

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = []
            for item in data.get("results", []):
                cat_name = item.get("category", {}).get("name", "General")
                muscles = [m.get("name_en") or m.get("name") for m in item.get("muscles", [])]
                name = cat_name + " Exercise"
                if item.get("exercises"):
                    for ex in item["exercises"]:
                        if ex.get("language") == 2 and ex.get("name"):
                            name = ex["name"]
                            break

                results.append({
                    "id": item.get("id"),
                    "name": name,
                    "category": cat_name,
                    "target_muscles": muscles,
                })
            return results
    except Exception as e:
        return [{"error": f"Failed to fetch wger exercises: {str(e)}"}]


def generate_motivation_badge(topic: str = "Workout Streak", tool_context: ToolContext = None) -> dict:
    """Generate a custom fitness motivation badge image using gemini-3.1-flash-lite-image in global region.

    Saves the image artifact to the Playground Artifacts panel via tool_context.save_artifact
    and uploads the image bytes directly to public Cloud Storage, returning its public https URL.

    Args:
        topic: The fitness milestone or theme (e.g. '10,000 Steps Goal', 'Leg Day Champion', 'Protein Goal Met').
        tool_context: ADK ToolContext supplied automatically during invocation.

    Returns:
        A dictionary containing the topic title and the public GCS https URL of the generated badge image.
    """
    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    prompt = f"A vibrant 3D motivational fitness badge for '{topic}', glossy enamel finish, athletic trophy design, high resolution"

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    image_bytes = None
    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                break

    if not image_bytes:
        return {"error": "Failed to generate image bytes from model."}

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    sanitized_topic = "".join(c if c.isalnum() else "_" for c in topic.lower())[:20]
    filename = f"badge_{sanitized_topic}_{now_str}.jpg"

    # 1. Save artifact for Playground Artifacts panel
    if tool_context:
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        tool_context.save_artifact(filename, artifact_part)

    # 2. Upload image bytes directly to public GCS bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type="image/jpeg")

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

    return {
        "status": "success",
        "topic": topic,
        "filename": filename,
        "public_url": public_url,
    }


def generate_workout_video(topic: str = "Triathlon Sprint Finish", tool_context: ToolContext = None) -> dict:
    """Generate a short motivational workout video clip using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the video artifact to the Playground Artifacts panel via tool_context.save_artifact
    and uploads the video bytes directly to public Cloud Storage, returning its public https URL.

    Args:
        topic: The workout or triathlon scene (e.g. 'Ocean Swim Technique', 'Sunset Coastal Bike Ride', 'Track Sprint Finish').
        tool_context: ADK ToolContext supplied automatically during invocation.

    Returns:
        A dictionary containing the video topic and the public GCS https URL of the generated MP4 video.
    """
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    sanitized_topic = "".join(c if c.isalnum() else "_" for c in topic.lower())[:20]
    filename = f"video_{sanitized_topic}_{now_str}.mp4"
    gcs_object_path = f"video_gen/{filename}"
    gcs_dest_uri = f"gs://{BUCKET_NAME}/{gcs_object_path}"

    url = f"https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/global/interactions"
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    body = {
        "model": "gemini-omni-flash-preview",
        "input": [
            {
                "type": "text",
                "text": f"A 5-second cinematic athletic workout video depicting '{topic}', dynamic camera angles, high quality"
            }
        ],
        "response_format": [
            {
                "type": "video",
                "delivery": "uri",
                "gcs_uri": gcs_dest_uri,
                "aspect_ratio": "16:9",
                "resolution": "720p",
                "duration": "5s"
            }
        ],
        "generation_config": {
            "video_config": {
                "task": "text_to_video"
            }
        }
    }

    resp = requests.post(url, headers=headers, json=body, timeout=120)
    if resp.status_code != 200:
        return {"error": f"Interactions API returned status {resp.status_code}: {resp.text[:300]}"}

    res_json = resp.json()

    generated_uri = None
    for step in res_json.get("steps", []):
        if step.get("type") == "model_output":
            for content_item in step.get("content", []):
                if content_item.get("type") == "video" and content_item.get("uri"):
                    generated_uri = content_item.get("uri")
                    break

    if not generated_uri:
        return {"error": "Failed to generate video output URI from model."}

    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)

    if generated_uri.startswith(f"gs://{BUCKET_NAME}/"):
        object_name = generated_uri[len(f"gs://{BUCKET_NAME}/"):]
    else:
        parts = generated_uri.replace("gs://", "").split("/", 1)
        object_name = parts[1] if len(parts) > 1 else filename

    blob = bucket.blob(object_name)
    video_bytes = blob.download_as_bytes()

    blob.content_type = "video/mp4"
    blob.patch()

    # 1. Save artifact for Playground Artifacts panel
    if tool_context:
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
        tool_context.save_artifact(filename, artifact_part)

    # 2. Public GCS URL
    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{object_name}"
    return {
        "status": "success",
        "topic": topic,
        "video_url": public_url,
        "filename": filename,
        "message": f"Successfully generated workout video for '{topic}'."
    }





