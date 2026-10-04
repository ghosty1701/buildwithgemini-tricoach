#!/usr/bin/env python3
"""Seed script for TriCoach Firestore database.

Populates initial exercise catalog and sample activity logs.
"""

from google.cloud import firestore

# Hardcode GCP Project ID explicitly per Agent Platform requirements
PROJECT_ID = "qwiklabs-gcp-02-feeccdad7474"


def seed_database():
    db = firestore.Client(project=PROJECT_ID)
    print(f"Connecting to Firestore for project: {PROJECT_ID}...")

    # Seed Exercise Catalog
    exercises = [
        {
            "id": "pushups",
            "name": "Push-ups",
            "category": "Strength",
            "target_muscles": ["Chest", "Triceps", "Shoulders"],
            "difficulty": "Beginner",
            "description": "Standard push-ups keeping core tight and body straight.",
            "recommended_reps": "3 sets of 10-15 reps",
        },
        {
            "id": "bodyweight_squats",
            "name": "Bodyweight Squats",
            "category": "Strength",
            "target_muscles": ["Quadriceps", "Glutes", "Hamstrings"],
            "difficulty": "Beginner",
            "description": "Squat down until thighs are parallel to the ground.",
            "recommended_reps": "3 sets of 15-20 reps",
        },
        {
            "id": "plank",
            "name": "Forearm Plank",
            "category": "Core",
            "target_muscles": ["Abs", "Obliques", "Lower Back"],
            "difficulty": "Beginner",
            "description": "Hold a rigid forearm plank position maintaining neutral spine.",
            "recommended_reps": "3 sets of 45-60 seconds",
        },
        {
            "id": "dumbbell_bench_press",
            "name": "Dumbbell Bench Press",
            "category": "Strength",
            "target_muscles": ["Chest", "Triceps"],
            "difficulty": "Intermediate",
            "description": "Press dumbbells upwards from chest level while lying on a flat bench.",
            "recommended_reps": "3 sets of 8-12 reps",
        },
        {
            "id": "treadmill_run",
            "name": "Moderate Treadmill Run",
            "category": "Cardio",
            "target_muscles": ["Legs", "Cardiovascular System"],
            "difficulty": "Beginner",
            "description": "Steady-state jogging/running at 60-70% max heart rate.",
            "recommended_reps": "20-30 minutes",
        },
        {
            "id": "dumbbell_rows",
            "name": "Single-Arm Dumbbell Row",
            "category": "Strength",
            "target_muscles": ["Lats", "Biceps", "Upper Back"],
            "difficulty": "Intermediate",
            "description": "Pull dumbbell up to torso with knee and hand supporting on bench.",
            "recommended_reps": "3 sets of 10-12 reps per arm",
        },
    ]

    print("Seeding 'exercises' collection...")
    for ex in exercises:
        doc_ref = db.collection("exercises").document(ex["id"])
        doc_ref.set(ex)
        print(f"  - Added exercise: {ex['name']} ({ex['id']})")

    # Seed Sample Activity Logs (Workouts, Nutrition, Biometrics)
    sample_logs = [
        {
            "id": "log_20261003_workout",
            "date": "2026-10-03",
            "type": "workout",
            "details": {
                "exercise_name": "Bodyweight Squats",
                "sets": 3,
                "reps": 15,
                "weight_lbs": 0,
                "duration_mins": 20,
            },
            "notes": "Felt good, solid form throughout.",
            "created_at": "2026-10-03T18:30:00Z",
        },
        {
            "id": "log_20261003_nutrition",
            "date": "2026-10-03",
            "type": "nutrition",
            "details": {
                "calories": 2150,
                "protein_g": 145,
                "water_ml": 2800,
            },
            "notes": "Hit protein target, drank 2.8L water.",
            "created_at": "2026-10-03T21:00:00Z",
        },
        {
            "id": "log_20261004_biometrics",
            "date": "2026-10-04",
            "type": "biometrics",
            "details": {
                "steps": 8450,
                "resting_heart_rate": 62,
                "spo2_pct": 98,
                "sleep_hours": 7.5,
            },
            "notes": "Good night's rest, pulse ox healthy.",
            "created_at": "2026-10-04T07:30:00Z",
        },
    ]

    print("Seeding 'logs' collection...")
    for log in sample_logs:
        doc_ref = db.collection("logs").document(log["id"])
        doc_ref.set(log)
        print(f"  - Added log: {log['type']} ({log['id']})")

    print("\n✅ Firestore database successfully seeded!")


if __name__ == "__main__":
    seed_database()
