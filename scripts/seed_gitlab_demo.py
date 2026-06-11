"""
One-time setup script: creates the three Copa Agent demo projects under the
authenticated GitLab user's namespace and seeds `worldcup-ticketing-api` with
the planted TOKEN_EXPIRY_SECONDS bug — mirroring backend/services/gitlab_tools.py
SIMULATION world so the live agent run produces the same triage->fix->MR story.

Usage:
    python scripts/seed_gitlab_demo.py
Reads GITLAB_PERSONAL_ACCESS_TOKEN / GITLAB_API_URL from .env.
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "")
API_URL = os.getenv("GITLAB_API_URL", "https://gitlab.com/api/v4")
HEADERS = {"PRIVATE-TOKEN": TOKEN}

PROJECTS = [
    ("worldcup-fan-app", "React PWA — schedules, scores, venue maps"),
    ("worldcup-ticketing-api", "Python FastAPI ticketing microservice"),
    ("worldcup-stadium-dashboard", "Real-time stadium ops dashboard"),
]

APP_MAIN_PY = '''"""Ticketing API -- World Cup 2026"""
from fastapi import FastAPI

app = FastAPI(title="World Cup Ticketing API")

# --- Constants ---
TOKEN_EXPIRY_SECONDS = 360  # BUG: Should be 3600 (1 hour), typo causes tokens to expire in 6 minutes
MAX_TICKETS_PER_USER = 4
TICKET_CATEGORIES = ["Category 1", "Category 2", "Category 3", "Category 4"]


@app.get("/")
def root():
    return {"service": "worldcup-ticketing-api", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}
'''

TEST_AUTH_PY = '''from app.main import TOKEN_EXPIRY_SECONDS, MAX_TICKETS_PER_USER, TICKET_CATEGORIES, root, health

EXPECTED_TOKEN_EXPIRY = 3600


def test_token_expiry_constant():
    assert TOKEN_EXPIRY_SECONDS == EXPECTED_TOKEN_EXPIRY, (
        f"Expected token expiry {EXPECTED_TOKEN_EXPIRY}, got {TOKEN_EXPIRY_SECONDS}. "
        f"Tokens expiring too quickly will lock fans out at venue entry gates."
    )


def test_max_tickets_per_user():
    assert MAX_TICKETS_PER_USER == 4


def test_ticket_categories_exist():
    assert len(TICKET_CATEGORIES) == 4


def test_token_expiry_is_positive():
    assert TOKEN_EXPIRY_SECONDS > 0


def test_token_expiry_is_int():
    assert isinstance(TOKEN_EXPIRY_SECONDS, int)


def test_token_expiry_not_zero():
    assert TOKEN_EXPIRY_SECONDS != 0


def test_health_endpoint():
    assert health() == {"status": "healthy"}


def test_root_endpoint():
    assert root()["service"] == "worldcup-ticketing-api"
'''

REQUIREMENTS_TXT = "fastapi\nuvicorn\npytest\nhttpx\n"

GITLAB_CI_YML = '''stages:
  - build
  - test

build:
  stage: build
  image: python:3.11-slim
  script:
    - pip install -r requirements.txt
    - python -c "import app.main"

unit_test:
  stage: test
  image: python:3.11-slim
  script:
    - pip install -r requirements.txt
    - pytest tests/ -v --tb=short
'''


def create_project(name, description):
    resp = requests.post(
        f"{API_URL}/projects",
        headers=HEADERS,
        json={"name": name, "description": description, "visibility": "public", "initialize_with_readme": True},
    )
    if resp.status_code == 201:
        proj = resp.json()
        print(f"  created: {proj['path_with_namespace']} (id={proj['id']})")
        return proj
    if resp.status_code == 400 and "has already been taken" in resp.text:
        # already exists -- look it up
        me = requests.get(f"{API_URL}/user", headers=HEADERS).json()
        lookup = requests.get(
            f"{API_URL}/projects/{me['username']}%2F{name}", headers=HEADERS
        )
        if lookup.status_code == 200:
            proj = lookup.json()
            print(f"  exists:  {proj['path_with_namespace']} (id={proj['id']})")
            return proj
    print(f"  FAILED to create {name}: {resp.status_code} {resp.text[:300]}")
    return None


def commit_files(project_id, files: dict, message: str):
    actions = [
        {"action": "create", "file_path": path, "content": content}
        for path, content in files.items()
    ]
    resp = requests.post(
        f"{API_URL}/projects/{project_id}/repository/commits",
        headers=HEADERS,
        json={"branch": "main", "commit_message": message, "actions": actions},
    )
    if resp.status_code == 201:
        print(f"  seeded {len(files)} files (commit {resp.json()['short_id']})")
    else:
        print(f"  FAILED to seed files: {resp.status_code} {resp.text[:400]}")


def main():
    if not TOKEN or TOKEN.startswith("glpat-xxxx"):
        print("No real GITLAB_PERSONAL_ACCESS_TOKEN found in .env -- aborting.")
        sys.exit(1)

    me = requests.get(f"{API_URL}/user", headers=HEADERS).json()
    print(f"Authenticated as: {me['username']}\n")

    print("Creating projects...")
    created = {}
    for name, desc in PROJECTS:
        proj = create_project(name, desc)
        if proj:
            created[name] = proj

    ticketing = created.get("worldcup-ticketing-api")
    if ticketing:
        print("\nSeeding worldcup-ticketing-api with the planted bug...")
        # check if app/main.py already exists (idempotency)
        check = requests.get(
            f"{API_URL}/projects/{ticketing['id']}/repository/files/app%2Fmain.py?ref=main",
            headers=HEADERS,
        )
        if check.status_code == 200:
            print("  already seeded (app/main.py exists) -- skipping commit")
        else:
            commit_files(
                ticketing["id"],
                {
                    "requirements.txt": REQUIREMENTS_TXT,
                    "app/__init__.py": "",
                    "app/main.py": APP_MAIN_PY,
                    "tests/__init__.py": "",
                    "tests/test_auth.py": TEST_AUTH_PY,
                    ".gitlab-ci.yml": GITLAB_CI_YML,
                },
                "seed: ticketing API with TOKEN_EXPIRY_SECONDS bug (planted for Copa Agent demo)",
            )

    print(f"\nDone. Set GITLAB_GROUP_PATH={me['username']} in your .env")


if __name__ == "__main__":
    main()
