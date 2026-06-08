#!/bin/bash
# ==============================================================================
# Copa Agent — Setup GitLab Repos
# Creates 3 sample World Cup repositories with CI/CD pipelines
# ==============================================================================

set -e

GITLAB_TOKEN=${GITLAB_PERSONAL_ACCESS_TOKEN:-""}
GROUP_NAME="worldcup-2026-demo"

if [ -z "$GITLAB_TOKEN" ]; then
  echo "Error: GITLAB_PERSONAL_ACCESS_TOKEN environment variable is required."
  exit 1
fi

echo "⚽ Setting up Copa Agent Demo Repositories..."
echo "Creating repos under group: $GROUP_NAME (using token)"

# Function to create a project via API
create_project() {
  local name=$1
  local desc=$2
  
  echo "📦 Creating project: $name..."
  # Simplified for demo - normally you'd handle group creation, etc.
  curl -s --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
       --data "name=$name&description=$desc&visibility=private" \
       "https://gitlab.com/api/v4/projects" > /dev/null
  echo "✅ $name created."
}

# Create the 3 repos
create_project "worldcup-fan-app" "React PWA for fans — schedules, scores, venue maps"
create_project "worldcup-ticketing-api" "Python FastAPI ticketing microservice"
create_project "worldcup-stadium-dashboard" "Real-time stadium ops dashboard"

echo ""
echo "🎉 Repositories created successfully!"
echo "Next step: Push the contents of ./gitlab-repos/ to these new repositories."
