#!/usr/bin/env python3
"""
Copa Agent — Seed Demo Data
Creates some dummy issues, branches, and triggers pipelines
in the GitLab demo repos to provide a realistic starting state.
"""

import os
import requests
import json

GITLAB_TOKEN = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN")
API_URL = "https://gitlab.com/api/v4"
GROUP_NAME = "worldcup-2026-demo"

def main():
    if not GITLAB_TOKEN:
        print("Error: GITLAB_PERSONAL_ACCESS_TOKEN not set.")
        return

    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    
    print("⚽ Seeding data for Copa Agent demo...")
    
    # Simple demo placeholder - this would use the real project IDs in a full run
    print("In a full run, this script would:")
    print("1. Create 'feature/spanish-i18n' issue in worldcup-fan-app")
    print("2. Trigger a failing pipeline in worldcup-ticketing-api")
    print("3. Populate the Match Day milestone")
    
    print("✅ Seed script ready.")

if __name__ == "__main__":
    main()
