# Railway Deployment Guide

## Quick Setup:

1. **Go to [Railway.app](https://railway.app)**
2. **Sign up with GitHub**
3. **Click "New Project" → "Deploy from GitHub repo"**
4. **Select your `basic-streamlit-ui` repository**
5. **Railway will auto-detect it's a Python app**

## Environment Variables to Set:

In Railway dashboard, go to your project → Variables tab:

```
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=finallcpreports
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your_n8n_key
N8N_MAIN_WORKFLOW_ID=your_workflow_id
```

## What Railway Will Do:

- ✅ Auto-detect Python app
- ✅ Install dependencies from requirements.txt
- ✅ Run `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- ✅ Give you a public URL like `https://your-app.railway.app`
- ✅ Handle SSL certificates automatically

## After Deployment:

1. **Get your Railway URL** (e.g., `https://ocr-backend-production.railway.app`)
2. **Update Streamlit to use this URL** instead of localhost
3. **Test the endpoints** - they should work from anywhere!

## Benefits:

- 🆓 **Free tier** with $5 monthly credit
- 🚀 **No sleep time** (unlike Render)
- 🔒 **Automatic SSL**
- 🌐 **Global CDN**
- 📊 **Built-in monitoring**
