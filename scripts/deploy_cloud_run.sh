#!/bin/bash
# ==============================================================================
# Copa Agent — Deploy to Cloud Run
# Builds and deploys the backend API and frontend dashboard
# ==============================================================================

set -e

PROJECT_ID=${GCP_PROJECT_ID:-"copa-agent-2026"}
REGION=${GCP_LOCATION:-"us-central1"}
SERVICE_NAME="copa-agent"

echo "🚀 Deploying Copa Agent to Google Cloud Run..."
echo "Project: $PROJECT_ID | Region: $REGION"

# Set project
gcloud config set project $PROJECT_ID

# Deploy using source (Cloud Build pack)
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="GITLAB_PERSONAL_ACCESS_TOKEN=${GITLAB_PERSONAL_ACCESS_TOKEN},AGENT_ID=${AGENT_ID},GCP_PROJECT_ID=${PROJECT_ID}"

echo ""
echo "✅ Deployment complete!"
echo "Visit the Cloud Run URL to access the Copa Agent dashboard."
