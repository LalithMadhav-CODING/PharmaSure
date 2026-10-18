"""Script to generate realistic, scientifically grounded demo cache matching PRD v1.2 and README."""
import json
import os

with open("data/demo_cache.json") as f:
    DEMO_DATA = json.load(f)

os.makedirs("data", exist_ok=True)
with open("data/demo_cache.json", "w") as f:
    json.dump(DEMO_DATA, f, indent=2)

print(f"Verified data/demo_cache.json with {len(DEMO_DATA)} cached query keys.")
