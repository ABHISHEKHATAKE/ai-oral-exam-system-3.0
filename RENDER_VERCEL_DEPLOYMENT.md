# Render & Vercel Deployment Guide

## Overview
This guide covers deploying the AI Oral Examination System with:
- **Backend**: FastAPI on Render
- **Frontend**: React on Vercel
- **Database**: MongoDB Atlas (already deployed)

## Prerequisites
- GitHub account (different account as requested)
- Render account (https://render.com)
- Vercel account (https://vercel.com)
- MongoDB Atlas database (already set up)

## Step 1: Prepare Code for Deployment

### 1.1 Create New GitHub Repository
```bash
# Create new repository on your different GitHub account
# Name: ai-oral-exam-system
# Make it private or public as preferred

# Initialize git if not already done
git init

# Add remote (replace with your new repo URL)
git remote add origin https://github.com/YOUR_NEW_USERNAME/ai-oral-exam-system.git

# Add all files
git add .

# Commit
git commit -m "Initial commit for Render/Vercel deployment"

# Push to new repository
git push -u origin main
```

### 1.2 Verify Files
Ensure these files exist in your repository:
- `render.yaml` (backend config)
- `frontend/vercel.json` (frontend config)
- `Dockerfile.backend` (backend Docker)
- `exam_system/requirements.txt` (Python dependencies)
- `frontend/package.json` (Node dependencies)

## Step 2: Deploy Backend on Render

### 2.1 Connect Repository
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Select the repository you just created

### 2.2 Configure Backend Service
```
Service Name: exam-backend
Runtime: Python 3
Build Command: pip install -r exam_system/requirements.txt
Start Command: cd exam_system && python main.py
```

### 2.3 Set Environment Variables
Add these environment variables in Render:
```
GROQ_API_KEY = your_groq_api_key_here
MONGODB_URL = your_mongodb_atlas_uri_here
SECRET_KEY = generate_a_random_secret_key
ALGORITHM = HS256
ACCESS_TOKEN_EXPIRE_MINUTES = 30
```

### 2.4 Deploy Backend
1. Click "Create Web Service"
2. Wait for deployment to complete
3. Note the backend URL (e.g., `https://exam-backend.onrender.com`)

## Step 3: Deploy Frontend on Vercel

### 3.1 Connect Repository
1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click "New Project"
3. Import your GitHub repository
4. Configure project settings:
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

### 3.2 Set Environment Variables
Add this environment variable in Vercel:
```
VITE_API_URL = https://exam-backend.onrender.com
```
(Replace with your actual Render backend URL)

### 3.3 Deploy Frontend
1. Click "Deploy"
2. Wait for deployment to complete
3. Note the frontend URL (e.g., `https://ai-oral-exam.vercel.app`)

## Step 4: Post-Deployment Configuration

### 4.1 Update CORS (if needed)
In your backend, ensure CORS allows the Vercel domain:
```python
# In exam_system/app/main.py or cors configuration
allowed_origins = [
    "http://localhost:5173",  # dev
    "http://localhost:3000",  # dev
    "https://ai-oral-exam.vercel.app",  # production
]
```

### 4.2 Test the Deployment
1. Visit your Vercel frontend URL
2. Try logging in as a student
3. Test taking an exam in pure voice mode
4. Check that results are saved to MongoDB

## Step 5: Domain Configuration (Optional)

### Custom Domain on Vercel
1. In Vercel project settings
2. Go to "Domains"
3. Add your custom domain
4. Configure DNS records as instructed

### Custom Domain on Render
1. In Render service settings
2. Go to "Settings" → "Custom Domains"
3. Add your custom domain
4. Configure DNS records as instructed

## Troubleshooting

### Backend Issues
- Check Render logs in the dashboard
- Verify environment variables are set correctly
- Test MongoDB connection: `python -c "import pymongo; print('OK')"`

### Frontend Issues
- Check Vercel build logs
- Verify `VITE_API_URL` is correct
- Check browser console for CORS errors

### WebSocket Issues
- Ensure backend URL in frontend includes `wss://` for WebSocket
- Check that WebSocket endpoints are accessible

## Security Notes
- Keep API keys secure in environment variables
- Use HTTPS in production
- Regularly update dependencies
- Monitor for security vulnerabilities

## Cost Estimation
- **Render**: Free tier available, ~$7/month for basic web service
- **Vercel**: Free tier for personal projects, Hobby plan ~$7/month
- **MongoDB Atlas**: Free tier available, M0 cluster free

## Support
- Render Docs: https://docs.render.com/
- Vercel Docs: https://vercel.com/docs
- MongoDB Atlas: https://docs.mongodb.com/atlas/

---

**Deployment Complete!** 🎉

Your AI Oral Examination System is now live on Render + Vercel.