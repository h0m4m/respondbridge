# Railway Deployment Guide

Complete guide for deploying the Respond.io Webhook Bridge to Railway.

---

## Prerequisites

1. [Railway Account](https://railway.app/) (sign up with GitHub)
2. GitHub repository with your code
3. MongoDB Atlas databases (already configured)

---

## Quick Deploy to Railway

### Option 1: Deploy from GitHub (Recommended)

1. **Push code to GitHub** (instructions below)

2. **Go to Railway**
   - Visit [railway.app](https://railway.app/)
   - Click "Start a New Project"
   - Select "Deploy from GitHub repo"

3. **Select Repository**
   - Choose `h0m4m/respondbridge`
   - Railway will automatically detect it's a Python project

4. **Configure Environment Variables**

   Go to your project → Variables → Add these variables:

   ```
   MONGO_URI=mongodb+srv://h0m4m:Sh1rayuk1cute%21@fasterai.9dwunxp.mongodb.net/?retryWrites=true&w=majority&appName=fasterAI
   DB_NAME=FasterConversations
   VIP_MONGO_URI=mongodb+srv://humammourad:qkAcT0F3QUvGghRU@cluster0.9012cjx.mongodb.net/?retryWrites=true&w=majority&appName=cluster0
   VIP_DB_NAME=VIPConversations
   PORT=8000
   FLASK_ENV=production
   TEST_MODE=false
   ```

5. **Deploy**
   - Railway will automatically build and deploy
   - You'll get a URL like `https://respondbridge-production.up.railway.app`

6. **Enable Public Domain**
   - Go to Settings → Networking → Generate Domain
   - Copy your Railway domain

7. **Update Respond.io Webhooks**
   - Replace ngrok URL with your Railway domain
   - Example: `https://respondbridge-production.up.railway.app/webhook/faster/incoming`

---

## Option 2: Deploy with Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Deploy
railway up
```

---

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGO_URI` | Faster AI MongoDB connection string | `mongodb+srv://...` |
| `DB_NAME` | Faster AI database name | `FasterConversations` |
| `VIP_MONGO_URI` | VIP MongoDB connection string | `mongodb+srv://...` |
| `VIP_DB_NAME` | VIP database name | `VIPConversations` |
| `PORT` | Server port (Railway sets automatically) | `8000` |
| `FLASK_ENV` | Flask environment | `production` |
| `TEST_MODE` | Enable test collections | `false` |

**Note**: Railway automatically sets `PORT` - the app will use Railway's port if available.

---

## Webhook URLs

After deployment, your webhook endpoints will be:

### Faster AI
- **Incoming**: `https://your-app.railway.app/webhook/faster/incoming`
- **Outgoing**: `https://your-app.railway.app/webhook/faster/outgoing`

### VIP
- **Incoming**: `https://your-app.railway.app/webhook/vip/incoming`
- **Outgoing**: `https://your-app.railway.app/webhook/vip/outgoing`

### Utility
- **Health Check**: `https://your-app.railway.app/health`
- **API Info**: `https://your-app.railway.app/`

---

## Monitoring & Logs

### View Logs
1. Go to your Railway project
2. Click on your service
3. Go to "Deployments" tab
4. Click "View Logs"

### Health Check
Visit `https://your-app.railway.app/health` to verify the service is running.

Expected response:
```json
{
  "status": "healthy",
  "test_mode": false,
  "endpoints": {
    "faster_incoming": "/webhook/faster/incoming",
    "faster_outgoing": "/webhook/faster/outgoing",
    "vip_incoming": "/webhook/vip/incoming",
    "vip_outgoing": "/webhook/vip/outgoing"
  }
}
```

---

## Troubleshooting

### Build Fails

**Check Python version:**
- Railway uses Python 3.11 (specified in `runtime.txt`)

**Check dependencies:**
```bash
pip install -r requirements.txt
```

### App Crashes on Start

**Check logs in Railway dashboard**

Common issues:
1. Missing environment variables
2. Invalid MongoDB connection strings
3. Port binding issues (Railway handles this automatically)

### MongoDB Connection Errors

**Verify:**
1. MongoDB Atlas allows connections from all IPs (`0.0.0.0/0`)
2. Connection strings are properly URL-encoded
3. Database users have read/write permissions

**Test connection locally:**
```bash
python -c "from pymongo import MongoClient; print(MongoClient('YOUR_MONGO_URI').server_info())"
```

### Webhooks Not Working

1. **Check Railway URL is public**
   - Settings → Networking → Public Domain should be enabled

2. **Verify webhook URLs in respond.io**
   - Must use Railway domain, not ngrok

3. **Test endpoint manually:**
```bash
curl -X POST https://your-app.railway.app/webhook/faster/incoming \
  -H "Content-Type: application/json" \
  -d '{"contact":{"id":1,"phone":"+1234567890"},"message":{"messageId":123,"timestamp":1234567890000,"message":{"type":"text","text":"test"}},"channel":{"id":1,"name":"Test"},"event_type":"message.received"}'
```

---

## Updating Your App

### Via GitHub (Automatic)

Railway automatically deploys when you push to GitHub:

```bash
git add .
git commit -m "Update webhook handler"
git push origin main
```

Railway will detect the push and redeploy automatically.

### Via Railway CLI

```bash
railway up
```

---

## Scaling & Performance

### Default Configuration
- **Workers**: 4 Gunicorn workers
- **Timeout**: 120 seconds
- **Restart Policy**: On failure (max 10 retries)

### Adjust Workers

Edit `railway.json`:
```json
{
  "deploy": {
    "startCommand": "gunicorn app:app --bind 0.0.0.0:$PORT --workers 8 --timeout 120"
  }
}
```

### Memory & CPU

Railway automatically scales based on your plan. Upgrade plan if needed.

---

## Cost Estimation

Railway Pricing (as of 2024):
- **Hobby Plan**: $5/month (500 hours execution time)
- **Pro Plan**: $20/month (unlimited execution time)

This webhook service is lightweight and should work well on the Hobby plan.

---

## Security Best Practices

1. **Never commit `.env` to Git**
   - Already in `.gitignore`

2. **Use Railway environment variables**
   - Stored securely, not in code

3. **MongoDB IP Whitelist**
   - Allow Railway IPs: `0.0.0.0/0` (Railway uses dynamic IPs)

4. **HTTPS Only**
   - Railway provides HTTPS by default

5. **Webhook Verification**
   - Consider adding webhook signature verification (respond.io may provide this)

---

## Rollback

If a deployment fails:

1. Go to Railway dashboard
2. Click "Deployments"
3. Find previous successful deployment
4. Click "Redeploy"

---

## Support

- **Railway Docs**: https://docs.railway.app/
- **Railway Discord**: https://discord.gg/railway
- **GitHub Issues**: https://github.com/h0m4m/respondbridge/issues
