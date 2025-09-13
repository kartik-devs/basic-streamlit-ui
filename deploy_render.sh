#!/bin/bash

echo "🚀 Deploying OCR App to Render..."

# Check if render CLI is installed
if ! command -v render &> /dev/null; then
    echo "❌ Render CLI not found. Please install it first:"
    echo "   npm install -g @render/cli"
    echo "   or visit: https://render.com/docs/cli"
    exit 1
fi

# Login to Render (if not already logged in)
echo "🔐 Checking Render authentication..."
render auth whoami || {
    echo "Please login to Render:"
    render auth login
}

# Deploy using render.yaml
echo "📦 Deploying services from render.yaml..."
render deploy

echo "✅ Deployment initiated! Check your Render dashboard for progress."
echo "🌐 Your app will be available at:"
echo "   Backend: https://ocr-backend.onrender.com"
echo "   Frontend: https://ocr-frontend.onrender.com"
