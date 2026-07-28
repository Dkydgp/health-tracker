"""
nutrition_ai.py - Uses an LLM (via OpenRouter) to estimate nutrition
from a plain-text food description.
"""

import os
import json
import re
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")

SYSTEM_PROMPT = """You are a nutrition estimation assistant. Given a plain-text \
description of food someone ate, estimate total calories, protein, carbs, and fat.

Use reasonable portion assumptions if not specified (e.g. "2 eggs" = 2 large eggs).
Be a careful, realistic estimator — not overly precise, just a solid ballpark.

Respond with ONLY valid JSON, no other text, in this exact format:
{"calories": <number>, "protein_g": <number>, "carbs_g": <number>, "fat_g": <number>, "notes": "<short assumption notes>"}

If the input is empty or says nothing was eaten, respond with all zeros.
"""


def _extract_json(text: str) -> dict:
    """Pull JSON out of a model response, tolerating extra text/markdown fences."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def estimate_nutrition(food_description: str) -> dict:
    """
    Takes a food description like "2 boiled eggs, 1 slice toast, black coffee"
    and returns {"calories": ..., "protein_g": ..., "carbs_g": ..., "fat_g": ..., "notes": ...}
    """
    if not food_description or not food_description.strip():
        return {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "notes": "No food logged"}

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": food_description},
            ],
            temperature=0.2,
        )
        raw = response.choices[0].message.content
        result = _extract_json(raw)

        # Normalize/validate expected keys
        return {
            "calories": round(float(result.get("calories", 0))),
            "protein_g": round(float(result.get("protein_g", 0)), 1),
            "carbs_g": round(float(result.get("carbs_g", 0)), 1),
            "fat_g": round(float(result.get("fat_g", 0)), 1),
            "notes": result.get("notes", ""),
        }

    except Exception as e:
        return {
            "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0,
            "notes": f"⚠️ Could not estimate ({str(e)})"
        }


def estimate_full_day(breakfast: str, lunch: str, dinner: str, snacks: str) -> dict:
    """
    Estimates nutrition per meal, then sums totals for the day.
    Returns per-meal breakdowns plus totals.
    """
    meals = {
        "breakfast": breakfast,
        "lunch": lunch,
        "dinner": dinner,
        "snacks": snacks,
    }

    breakdown = {}
    totals = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}

    for meal_name, description in meals.items():
        result = estimate_nutrition(description)
        breakdown[meal_name] = result
        totals["calories"] += result["calories"]
        totals["protein_g"] += result["protein_g"]
        totals["carbs_g"] += result["carbs_g"]
        totals["fat_g"] += result["fat_g"]

    totals["protein_g"] = round(totals["protein_g"], 1)
    totals["carbs_g"] = round(totals["carbs_g"], 1)
    totals["fat_g"] = round(totals["fat_g"], 1)

    return {"breakdown": breakdown, "totals": totals}
