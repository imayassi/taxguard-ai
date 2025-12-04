# TaxGuard AI

**Privacy-First Tax Estimation & Planning Application**

A full-stack web application that helps users estimate their federal tax liability, run what-if simulations, and receive AI-powered recommendations—all while ensuring their sensitive financial data never leaves their control.

## 🚀 NEW: OpenAI GPT-5.1 Integration

TaxGuard AI now features **live AI-powered tax strategy generation** using OpenAI's GPT-5.1 model with adaptive reasoning:

- **Personalized Strategies**: AI analyzes your anonymized financial data to generate custom tax reduction strategies
- **Transparent Privacy Pipeline**: Watch in real-time as your PII is removed before any data reaches the AI
- **Adaptive Reasoning**: GPT-5.1 intelligently allocates compute based on task complexity
- **No API Key Required**: Core features work without AI; add OpenAI key for enhanced strategies

### Adding Your OpenAI API Key

**For Streamlit Cloud:**
1. Go to your app's settings → Secrets
2. Add: `OPENAI_API_KEY = "sk-..."`

**For Local Development:**
```bash
export OPENAI_API_KEY="sk-..."
```

![Architecture](docs/architecture.png)

## 🔐 Security Architecture

**TaxGuard AI implements a "PII Air Gap"** - a critical privacy layer that ensures no personally identifiable information (SSN, names, addresses) ever reaches external AI services.

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER UPLOAD                               │
│                    (PDF/Image of Paystub)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STAGE 1: LOCAL OCR                           │
│              (Tesseract / pdfplumber - runs locally)            │
│                                                                 │
│   "John Smith, SSN: 123-45-6789, Gross Pay: $5,250.00..."      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│               STAGE 2: PII REDACTION (AIR GAP)                  │
│                    (Regex + spaCy NER)                          │
│                                                                 │
│   "[USER_NAME], SSN: [SSN_1], Gross Pay: $5,250.00..."         │
│                                                                 │
│   ⚠️  ORIGINAL PII IS NEVER STORED OR LOGGED                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 STAGE 3: LLM PROCESSING                         │
│              (Only REDACTED text sent to AI)                    │
│                                                                 │
│   AI extracts: { "ytd_gross": 42000, "pay_frequency": "..." }  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              STAGE 4: LOCAL TAX CALCULATION                     │
│         (Python - hardcoded 2025 brackets, NO LLM)             │
│                                                                 │
│   Tax calculations are NEVER delegated to the AI               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              STAGE 5: AI RECOMMENDATIONS                        │
│        (AI receives numbers only, generates advice)             │
│                                                                 │
│   "Based on your $4,000 projected liability..."                │
└─────────────────────────────────────────────────────────────────┘
```

## ✨ Features

### 📄 Document Processing
- Upload paystubs (PDF or images)
- Upload W-2 forms
- Upload prior year 1040s for comparison
- Manual data entry option

### 🧮 Tax Calculation
- Accurate 2025 federal tax brackets (hardcoded, not AI-generated)
- Standard vs. itemized deduction comparison
- Child tax credit calculation
- Self-employment tax support
- Effective and marginal rate display

### 🔮 What-If Simulations
- "What if I contribute more to my 401(k)?"
- "What if I max out my HSA?"
- "What if I change my filing status?"
- Compare multiple scenarios side-by-side

### 💡 AI-Powered Recommendations
- Basic strategies (401k, HSA, IRA)
- Advanced strategies (tax-loss harvesting)
- Time-constrained analysis (remaining pay periods)
- Prioritized action list

## 🚀 Quick Start

### Option 1: Deploy to Streamlit Cloud (Recommended)

1. **Push to GitHub:**
```bash
git init
git add .
git commit -m "TaxGuard AI"
git remote add origin https://github.com/YOUR_USERNAME/taxguard-ai.git
git push -u origin main
```

2. **Deploy on Streamlit Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Click "Create app"
   - Select your repository
   - Set main file path: `streamlit_app.py`
   - Click "Deploy"

3. **Add OpenAI API Key (Optional):**
   - Go to App Settings → Secrets
   - Add: `OPENAI_API_KEY = "sk-..."`

Your app will be live at `https://your-app.streamlit.app` in minutes!

### Option 2: Run Locally

### Prerequisites
- Python 3.10+
- Tesseract OCR (for image processing)

### Installation

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model for NER
python -m spacy download en_core_web_sm
```

### Run the Professional Streamlit App

```bash
cd backend
streamlit run app.py
```

The app will open at `http://localhost:8501` with a TurboTax-inspired UI.

### Run the Jupyter Notebook (for testing/development)

```bash
cd backend
jupyter notebook taxguard_testing.ipynb
```

### Run the FastAPI Backend (optional, for API access)

```bash
cd backend
uvicorn main:app --reload --port 8000
```

API docs at `http://localhost:8000/docs`

## 📁 Project Structure

```
taxguard-ai/
├── streamlit_app.py            # 🆕 Streamlit Cloud entry point
├── requirements.txt            # Root-level dependencies
├── packages.txt                # Linux dependencies (tesseract)
├── .streamlit/
│   └── config.toml             # Theme config (TurboTax colors)
├── backend/
│   ├── app.py                  # 🆕 Professional Streamlit UI (TurboTax-style)
│   ├── openai_client.py        # 🆕 GPT-4.1 integration
│   ├── main.py                 # FastAPI application (API mode)
│   ├── streamlit_app.py        # Simple Streamlit UI (legacy)
│   ├── taxguard_testing.ipynb  # Jupyter notebook for testing
│   ├── tax_constants.py        # 2025 tax brackets & limits
│   ├── models.py               # Pydantic data models
│   ├── enhanced_models.py      # Multiple income source models
│   ├── pii_redaction.py        # PII detection & redaction
│   ├── tax_simulator.py        # Tax calculation engine
│   ├── advanced_strategies.py  # 30+ life-changing tax strategies
│   ├── llm_prompts.py          # LLM system prompts
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile
│
├── tests/
│   └── test_backend.py         # Comprehensive test suite
│
├── docker-compose.yml
└── README.md
```

## 🔑 Key Components

### 1. Tax Constants (`tax_constants.py`)

Hardcoded 2025 federal tax data:
- Tax brackets for all filing statuses
- Standard deductions
- Contribution limits (401k, IRA, HSA)
- Child tax credit parameters

**Why hardcoded?** The AI should NEVER guess tax brackets. These values are authoritative.

### 2. PII Redaction (`pii_redaction.py`)

Two-stage privacy protection:

```python
# Stage 1: Regex patterns for structured PII
- SSN: \d{3}-\d{2}-\d{4}
- EIN: \d{2}-\d{7}
- Phone numbers
- Email addresses

# Stage 2: NER for unstructured PII
- PERSON entities (names)
- ORG entities (employers)
```

### 3. Data Models (`models.py`)

Core Pydantic models:

```python
class UserFinancialProfile(BaseModel):
    filing_status: FilingStatus
    ytd_income: float
    pay_frequency: PayFrequency
    projected_annual_income: float  # Auto-calculated
    standard_deduction: float       # Auto-calculated
    # ... 30+ fields
```

### 4. Tax Simulator (`tax_simulator.py`)

What-if analysis engine:

```python
simulator = TaxSimulator(profile)
result = simulator.run_simulation({'extra_401k': 5000})
# Returns: tax_difference, is_beneficial, summary
```

### 5. LLM Prompts (`llm_prompts.py`)

Carefully crafted prompts that:
- Force JSON-only output for data extraction
- Provide authoritative tax brackets to prevent hallucination
- Separate data extraction from strategy generation

## 🔌 API Reference

### Profiles

```http
POST   /api/profiles              # Create new profile
GET    /api/profiles/{id}         # Get profile with tax calculation
PATCH  /api/profiles/{id}         # Update profile fields
```

### Documents

```http
POST   /api/documents/upload      # Upload document for processing
GET    /api/documents/{id}/status # Check processing status
```

### Calculations

```http
POST   /api/profiles/{id}/calculate         # Calculate tax
POST   /api/profiles/{id}/simulate          # Run what-if simulation
POST   /api/profiles/{id}/simulate/optimal  # Find optimal strategies
POST   /api/profiles/{id}/strategy          # Get AI recommendations
```

### Reference Data

```http
GET    /api/reference/brackets    # Get tax brackets
GET    /api/reference/limits      # Get contribution limits
```

## 🧪 Testing

```bash
cd tests
pytest test_backend.py -v
```

Test coverage includes:
- Tax bracket calculations
- PII redaction patterns
- Data model validation
- Simulation accuracy
- Recommendation generation

## 🛡️ Security Considerations

1. **PII Never Stored**: Original PII values are discarded immediately after redaction
2. **Token Map**: Only stores `{token: pii_type}`, never `{token: actual_value}`
3. **Local OCR**: Document processing happens on your server
4. **LLM Isolation**: AI only sees redacted, anonymized text
5. **Tax Math Local**: All calculations use Python, not LLM inference

## 📊 2025 Tax Reference

### Single Filer Brackets
| Income Range | Rate |
|--------------|------|
| $0 - $11,925 | 10% |
| $11,926 - $48,475 | 12% |
| $48,476 - $103,350 | 22% |
| $103,351 - $197,300 | 24% |
| $197,301 - $250,525 | 32% |
| $250,526 - $626,350 | 35% |
| Over $626,350 | 37% |

### Contribution Limits
| Account | 2025 Limit |
|---------|------------|
| 401(k) | $23,500 |
| 401(k) Catch-up (50+) | +$7,500 |
| Traditional IRA | $7,000 |
| HSA (Individual) | $4,300 |
| HSA (Family) | $8,550 |

## 🔄 LLM Integration

The application uses a mock LLM client by default. To integrate with a real provider:

```python
# In main.py, replace MockLLMClient with:

import openai

class OpenAIClient:
    async def extract_paystub_data(self, redacted_text: str) -> dict:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": PAYSTUB_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": redacted_text}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
```

## ⚠️ Disclaimer

TaxGuard AI provides **estimates only** and is not a substitute for professional tax advice. The calculations are based on federal tax rules and may not account for:
- State and local taxes
- All possible deductions and credits
- Individual circumstances
- Tax law changes after development

**Always consult a qualified tax professional for your specific situation.**

## 📝 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md first.

---

Built with ❤️ for privacy-conscious taxpayers
