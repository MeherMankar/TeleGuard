#!/bin/bash

# TeleGuard Koyeb Deployment Script
# Usage: ./deploy/koyeb.sh

set -e

echo "🚀 Deploying TeleGuard to Koyeb..."

# Check if koyeb CLI is installed
if ! command -v koyeb &> /dev/null; then
    echo "❌ Koyeb CLI not found. Install it from: https://www.koyeb.com/docs/cli"
    exit 1
fi

# Check if user is logged in
if ! koyeb organizations list &> /dev/null; then
    echo "❌ Not logged in to Koyeb. Run: koyeb login"
    echo "📖 Visit: https://app.koyeb.com/account/api to get your API token"
    exit 1
fi

# Create secrets if they don't exist
echo "🔐 Setting up secrets..."
koyeb secrets create API_ID --value="$API_ID" --update-if-exists
koyeb secrets create API_HASH --value="$API_HASH" --update-if-exists
koyeb secrets create BOT_TOKEN --value="$BOT_TOKEN" --update-if-exists
koyeb secrets create ADMIN_IDS --value="$ADMIN_IDS" --update-if-exists

# Optional secrets
if [ ! -z "$MONGODB_URI" ]; then
    koyeb secrets create MONGODB_URI --value="$MONGODB_URI" --update-if-exists
fi

if [ ! -z "$GITHUB_TOKEN" ]; then
    koyeb secrets create GITHUB_TOKEN --value="$GITHUB_TOKEN" --update-if-exists
fi

# Deploy the app
echo "📦 Deploying application..."
koyeb app deploy teleguard --git-repository="$(git config --get remote.origin.url)" --git-branch=main

echo "✅ Deployment initiated! Check status at: https://app.koyeb.com/"
echo "📊 Monitor logs with: koyeb logs teleguard-bot"
echo "🔗 Your bot will be available at the provided Koyeb URL"
