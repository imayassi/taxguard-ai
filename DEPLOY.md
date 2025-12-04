# 🚀 Deploying TaxGuard AI to Streamlit Cloud

## Prerequisites

1. **GitHub Account** - Your code must be in a GitHub repository
2. **Streamlit Cloud Account** - Free at [share.streamlit.io](https://share.streamlit.io)

---

## Step 1: Push to GitHub

```bash
# Initialize git (if not already done)
cd taxguard-ai
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - TaxGuard AI"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/taxguard-ai.git
git branch -M main
git push -u origin main
```

---

## Step 2: Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)

2. Click **"New app"** (top right)

3. Fill in the deployment form:
   
   | Field | Value |
   |-------|-------|
   | **Repository** | `YOUR_USERNAME/taxguard-ai` |
   | **Branch** | `main` |
   | **Main file path** | `streamlit_app.py` |
   | **App URL** | `taxguard-ai` (or your choice) |

4. Click **"Deploy!"**

---

## Step 3: Wait for Build

The first deployment takes 3-5 minutes because it needs to:
- Install Python dependencies
- Download the spaCy language model (50MB)
- Build the container

You'll see logs in real-time. Common messages:
```
Installing dependencies from requirements.txt...
Downloading en_core_web_sm-3.7.1...
```

---

## 🔑 API Keys Required?

**None!** TaxGuard AI runs 100% locally:

| Component | API Key? | Notes |
|-----------|----------|-------|
| Tax Calculator | ❌ | Pure Python |
| PII Redaction | ❌ | spaCy + regex |
| Recommendations | ❌ | Rule-based |
| LLM Integration | ❌ | MockLLMClient |

### Optional: Add Real AI

If you want AI-powered explanations, add to `.streamlit/secrets.toml`:

```toml
# Optional - for AI explanations
OPENAI_API_KEY = "sk-..."
# OR
ANTHROPIC_API_KEY = "sk-ant-..."
```

Then uncomment the relevant lines in `backend/requirements.txt`:
```
openai>=1.3.0
# anthropic>=0.7.0
```

---

## 📁 Required Files for Deployment

```
taxguard-ai/
├── streamlit_app.py          # Entry point (REQUIRED)
├── requirements.txt          # Python deps (REQUIRED)
├── packages.txt              # Linux deps (optional)
├── .streamlit/
│   └── config.toml           # Theme config (optional)
└── backend/
    ├── app.py                # Main Streamlit app
    ├── models.py             # Data models
    ├── enhanced_models.py    # Multi-income models
    ├── tax_constants.py      # 2025 tax brackets
    ├── tax_simulator.py      # Calculator engine
    ├── pii_redaction.py      # Privacy protection
    └── advanced_strategies.py # 30+ strategies
```

---

## ⚠️ Troubleshooting

### "ModuleNotFoundError: No module named 'xxx'"

Check that all imports in `backend/app.py` match files that exist.

### "spaCy model not found"

The requirements.txt includes the model URL:
```
https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
```

### App is slow to start

First load takes 10-30 seconds due to spaCy model loading. Subsequent loads are faster.

### "Resource limits exceeded"

Streamlit Cloud free tier has limits:
- 1GB RAM
- 1 CPU core
- Apps sleep after inactivity

Consider upgrading or self-hosting for production use.

---

## 🔄 Updating Your App

After deployment, updates are automatic:

```bash
# Make changes locally
git add .
git commit -m "Updated feature X"
git push
```

Streamlit Cloud detects the push and redeploys automatically (usually < 1 minute).

---

## 🌐 Your App URL

After deployment, your app will be available at:

```
https://YOUR_APP_NAME.streamlit.app
```

Example: `https://taxguard-ai.streamlit.app`

---

## 📊 Alternative Deployment Options

### Docker (Self-hosted)

```bash
cd taxguard-ai
docker-compose up -d
```

App runs at `http://localhost:8501`

### Google Cloud Run

```bash
gcloud run deploy taxguard-ai \
  --source . \
  --platform managed \
  --allow-unauthenticated
```

### Heroku

```bash
heroku create taxguard-ai
git push heroku main
```

---

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] `requirements.txt` at repo root
- [ ] `streamlit_app.py` at repo root
- [ ] spaCy model URL in requirements.txt
- [ ] Streamlit Cloud account connected to GitHub
- [ ] App deployed and accessible

---

## 📞 Support

- **Streamlit Docs**: [docs.streamlit.io](https://docs.streamlit.io)
- **Streamlit Forum**: [discuss.streamlit.io](https://discuss.streamlit.io)
- **TaxGuard Issues**: Open an issue on GitHub
