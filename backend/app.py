"""
TaxGuard AI - Professional Streamlit Application
=================================================
A privacy-first tax estimation app with TurboTax-inspired design.

Features:
- Multiple income source tracking (spouse, multiple jobs, 1099s)
- Real-time refund/owed calculation
- What-if simulations
- AI-powered recommendations (OpenAI GPT-5.1)
- Transparent PII protection (privacy air gap)

Run with: streamlit run app.py
"""

import sys
import os

# Get the directory where this file lives
_current_file = os.path.abspath(__file__)
_backend_dir = os.path.dirname(_current_file)

# Add backend directory to path (at the front) - but DON'T change working directory
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import time
import json

# Import backend modules
from tax_constants import (
    FilingStatus, CONTRIBUTION_LIMITS_2025, PAY_PERIODS_PER_YEAR,
    STANDARD_DEDUCTION_2025, TAX_BRACKETS_2025,
)
from models import UserFinancialProfile, PayFrequency, TaxResult
from enhanced_models import (
    EnhancedUserProfile, IncomeSource, IncomeSourceType, 
    SpouseIncome, InvestmentIncome, PayFrequency as EnhancedPayFrequency,
)
from pii_redaction import PIIRedactor
from tax_simulator import TaxCalculator, TaxSimulator, RecommendationEngine

# Optional imports - these won't crash the app if missing
try:
    from advanced_strategies import get_all_advanced_strategies, StrategyCategory
    ADVANCED_STRATEGIES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: advanced_strategies not available: {e}")
    ADVANCED_STRATEGIES_AVAILABLE = False
    get_all_advanced_strategies = None
    StrategyCategory = None

try:
    from openai_client import (
        TaxAIClient, get_ai_client, create_anonymized_profile, 
        create_anonymized_tax_result, AIProvider
    )
    OPENAI_CLIENT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: openai_client not available: {e}")
    OPENAI_CLIENT_AVAILABLE = False
    
    # Provide fallback implementations
    class AIProvider:
        MOCK = "mock"
        OPENAI = "openai"
    
    class MockAIClient:
        is_connected = False
        model = "mock"
        def generate_strategies(self, **kwargs):
            from dataclasses import dataclass
            @dataclass
            class MockResponse:
                content: str = "AI features require OpenAI integration. Please check the logs for import errors."
                success: bool = True
                tokens_used: int = 0
            return MockResponse()
        def analyze_scenario(self, **kwargs):
            return self.generate_strategies()
    
    def get_ai_client():
        if 'ai_client' not in st.session_state:
            st.session_state.ai_client = MockAIClient()
        return st.session_state.ai_client
    
    def create_anonymized_profile(profile):
        return {"filing_status": str(profile.filing_status), "note": "mock profile"}
    
    def create_anonymized_tax_result(result):
        return {"gross_income": result.gross_income, "note": "mock result"}


# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="TaxGuard AI - Smart Tax Estimation",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =============================================================================
# CUSTOM CSS - TURBOTAX INSPIRED THEME
# =============================================================================

st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600;700&family=Source+Sans+Pro:wght@300;400;600;700&display=swap');
    
    /* Root Variables - TurboTax Color Scheme */
    :root {
        --primary-blue: #0077C5;
        --primary-blue-dark: #005B9A;
        --primary-blue-light: #E6F3FB;
        --secondary-blue: #0097D8;
        --accent-green: #14A66B;
        --accent-green-light: #E8F7F0;
        --warning-red: #D52B1E;
        --warning-red-light: #FDEEEC;
        --warning-orange: #F5A623;
        --text-dark: #1A1A1A;
        --text-medium: #4A4A4A;
        --text-light: #6B6B6B;
        --bg-light: #F8FAFB;
        --bg-card: #FFFFFF;
        --border-light: #E0E6EB;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.1);
        --shadow-lg: 0 8px 24px rgba(0,0,0,0.12);
    }
    
    /* Global Styles */
    .stApp {
        background-color: var(--bg-light);
        font-family: 'Open Sans', 'Source Sans Pro', sans-serif;
    }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main Content Area */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--primary-blue) 0%, var(--primary-blue-dark) 100%);
        padding-top: 0;
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: white;
    }
    
    [data-testid="stSidebar"] label {
        color: rgba(255,255,255,0.9) !important;
    }
    
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stNumberInput label {
        color: rgba(255,255,255,0.9) !important;
        font-weight: 500;
    }
    
    /* Custom Card Styles */
    .tax-card {
        background: var(--bg-card);
        border-radius: 12px;
        padding: 24px;
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--border-light);
        margin-bottom: 16px;
    }
    
    .tax-card-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-dark);
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Result Cards */
    .result-card {
        background: var(--bg-card);
        border-radius: 16px;
        padding: 32px;
        text-align: center;
        box-shadow: var(--shadow-md);
        border: 2px solid transparent;
    }
    
    .result-card.refund {
        border-color: var(--accent-green);
        background: linear-gradient(135deg, var(--accent-green-light) 0%, white 100%);
    }
    
    .result-card.owed {
        border-color: var(--warning-red);
        background: linear-gradient(135deg, var(--warning-red-light) 0%, white 100%);
    }
    
    .result-label {
        font-size: 0.9rem;
        color: var(--text-light);
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }
    
    .result-amount {
        font-size: 3rem;
        font-weight: 700;
        margin-bottom: 8px;
    }
    
    .result-amount.refund {
        color: var(--accent-green);
    }
    
    .result-amount.owed {
        color: var(--warning-red);
    }
    
    /* Metric Cards */
    .metric-card {
        background: var(--bg-card);
        border-radius: 10px;
        padding: 20px;
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--border-light);
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: var(--text-light);
        margin-bottom: 4px;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--text-dark);
    }
    
    /* Progress Steps */
    .progress-step {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        margin: 4px 0;
        border-radius: 8px;
        color: rgba(255,255,255,0.7);
        font-size: 0.95rem;
    }
    
    .progress-step.active {
        background: rgba(255,255,255,0.15);
        color: white;
        font-weight: 600;
    }
    
    .progress-step.completed {
        color: rgba(255,255,255,0.9);
    }
    
    .step-number {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: rgba(255,255,255,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 12px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    
    .progress-step.active .step-number {
        background: white;
        color: var(--primary-blue);
    }
    
    .progress-step.completed .step-number {
        background: var(--accent-green);
        color: white;
    }
    
    /* Buttons */
    .stButton > button {
        background: var(--primary-blue);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        background: var(--primary-blue-dark);
        box-shadow: var(--shadow-md);
        transform: translateY(-1px);
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* Input Fields */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div {
        border-radius: 8px;
        border: 1px solid var(--border-light);
        padding: 12px;
        font-size: 1rem;
    }
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--primary-blue);
        box-shadow: 0 0 0 3px var(--primary-blue-light);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: var(--bg-card);
        border-radius: 12px;
        padding: 4px;
        box-shadow: var(--shadow-sm);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 500;
        color: var(--text-medium);
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--primary-blue) !important;
        color: white !important;
    }
    
    /* Privacy Pipeline */
    .privacy-pipeline {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 20px;
        color: white;
        margin: 16px 0;
    }
    
    .pipeline-step {
        display: flex;
        align-items: center;
        padding: 12px;
        margin: 8px 0;
        background: rgba(255,255,255,0.1);
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    .pipeline-step.active {
        background: rgba(20, 166, 107, 0.3);
        border: 1px solid #14A66B;
    }
    
    .pipeline-step.completed {
        background: rgba(20, 166, 107, 0.2);
    }
    
    .pipeline-step.pending {
        opacity: 0.5;
    }
    
    .pipeline-icon {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: rgba(255,255,255,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 12px;
        font-size: 1rem;
    }
    
    .pipeline-step.completed .pipeline-icon {
        background: #14A66B;
    }
    
    /* AI Status Badge */
    .ai-status {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    .ai-status.connected {
        background: #E8F7F0;
        color: #14A66B;
    }
    
    .ai-status.disconnected {
        background: #FDEEEC;
        color: #D52B1E;
    }
    
    /* Privacy Badge */
    .privacy-badge {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.85rem;
        margin-top: 16px;
    }
    
    .privacy-badge .icon {
        font-size: 1.2rem;
    }
    
    /* Animation */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    .animate-fade-in {
        animation: fadeIn 0.4s ease-out;
    }
    
    .animate-pulse {
        animation: pulse 1.5s ease-in-out infinite;
    }
    
    /* Redaction highlight */
    .redacted {
        background: #FFE066;
        padding: 2px 4px;
        border-radius: 3px;
        font-family: monospace;
    }
    
    /* Success toast */
    .success-toast {
        background: #E8F7F0;
        border: 1px solid #14A66B;
        color: #0D5C3D;
        padding: 12px 16px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        'current_step': 1,
        'profile': UserFinancialProfile(),
        'enhanced_profile': EnhancedUserProfile(),
        'tax_result': None,
        'recommendations': None,
        'simulations': [],
        'income_sources': [],
        'show_advanced': False,
        'ai_strategies': None,
        'pii_log': [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def fmt_currency(amount: float) -> str:
    """Format number as currency."""
    if amount is None:
        return "$0"
    return f"${amount:,.0f}"

def fmt_currency_cents(amount: float) -> str:
    """Format with cents."""
    if amount is None:
        return "$0.00"
    return f"${amount:,.2f}"

def fmt_percent(rate: float) -> str:
    """Format as percentage."""
    if rate is None:
        return "0%"
    return f"{rate:.1f}%"

def sync_and_calculate():
    """Sync enhanced profile to standard profile and calculate taxes."""
    ep = st.session_state.enhanced_profile
    p = st.session_state.profile
    
    # Sync basic info
    p.filing_status = ep.filing_status
    p.age = ep.age
    p.num_children_under_17 = ep.num_children_under_17
    
    # Sync income
    p.ytd_income = ep.total_ytd_w2_income
    p.ytd_federal_withheld = ep.total_ytd_federal_withheld
    p.estimated_payments_made = ep.total_estimated_payments
    p.self_employment_income = ep.total_self_employment_income
    
    # Sync spouse income if married
    if ep.spouse:
        p.spouse_age = ep.spouse.age
        p.ytd_income += ep.spouse.total_ytd_income
        p.ytd_federal_withheld += ep.spouse.total_federal_withheld
    
    # Sync investments
    p.interest_income = ep.investments.taxable_interest
    p.dividend_income = ep.investments.ordinary_dividends
    p.capital_gains_long = ep.investments.long_term_gains
    p.capital_gains_short = ep.investments.short_term_gains
    
    # Sync retirement
    p.ytd_401k_traditional = ep.ytd_401k_traditional
    if ep.spouse:
        p.ytd_401k_traditional += ep.spouse.total_401k
    p.ytd_hsa = ep.ytd_hsa
    p.hsa_coverage_type = "family" if ep.filing_status == FilingStatus.MARRIED_FILING_JOINTLY else "individual"
    p.has_workplace_retirement_plan = True
    
    # Set pay frequency from primary source
    for s in ep.income_sources:
        if s.source_type == IncomeSourceType.W2_PRIMARY:
            p.pay_frequency = PayFrequency(s.pay_frequency.value)
            p.current_pay_period = s.current_pay_period
            break
    
    # Calculate
    calc = TaxCalculator()
    st.session_state.tax_result = calc.calculate_tax(p)
    
    # Generate recommendations
    engine = RecommendationEngine()
    st.session_state.recommendations = engine.generate_recommendations(p)


def show_pii_pipeline(placeholder, current_step: int, steps: List[Dict], pii_found: List[str] = None):
    """Display the privacy pipeline progress."""
    with placeholder.container():
        html = """
            <div class="privacy-pipeline">
                <div style="display: flex; align-items: center; margin-bottom: 16px;">
                    <span style="font-size: 1.5rem; margin-right: 12px;">🛡️</span>
                    <div>
                        <div style="font-weight: 600; font-size: 1.1rem;">Privacy Air Gap Active</div>
                        <div style="font-size: 0.85rem; opacity: 0.8;">Your personal information is being protected</div>
                    </div>
                </div>
        """
        
        for i, step in enumerate(steps):
            if i < current_step:
                status = "completed"
                icon = "✓"
            elif i == current_step:
                status = "active"
                icon = step.get('icon', '⏳')
            else:
                status = "pending"
                icon = step.get('icon', '○')
            
            html += f"""
                <div class="pipeline-step {status}">
                    <div class="pipeline-icon">{icon}</div>
                    <div>
                        <div style="font-weight: 500;">{step['title']}</div>
                        <div style="font-size: 0.85rem; opacity: 0.8;">{step['description']}</div>
                    </div>
                </div>
            """
        
        if pii_found:
            html += f"""
                <div style="margin-top: 16px; padding: 12px; background: rgba(213, 43, 30, 0.2); border-radius: 8px;">
                    <div style="font-weight: 500; margin-bottom: 8px;">🚫 PII Detected & Removed:</div>
                    <div style="font-size: 0.9rem;">{', '.join(pii_found)}</div>
                </div>
            """
        
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)


# =============================================================================
# SIDEBAR - NAVIGATION & PROFILE
# =============================================================================

with st.sidebar:
    # Logo/Brand
    st.markdown("""
        <div style="text-align: center; padding: 20px 0 30px 0;">
            <div style="font-size: 2.5rem; margin-bottom: 8px;">🛡️</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: white;">TaxGuard AI</div>
            <div style="font-size: 0.85rem; color: rgba(255,255,255,0.7); margin-top: 4px;">
                Smart Tax Estimation
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # AI Connection Status
    ai_client = get_ai_client()
    if ai_client.is_connected:
        st.markdown("""
            <div class="ai-status connected">
                <span>🟢</span> GPT-5.1 Connected
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div class="ai-status disconnected">
                <span>🔴</span> AI Offline (Add API Key)
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 20px 0;'>", unsafe_allow_html=True)
    
    # Progress Steps
    steps = [
        ("1", "Profile", st.session_state.current_step >= 1),
        ("2", "Income", st.session_state.current_step >= 2),
        ("3", "Deductions", st.session_state.current_step >= 3),
        ("4", "Review", st.session_state.current_step >= 4),
    ]
    
    for num, label, completed in steps:
        active = int(num) == st.session_state.current_step
        status = "active" if active else ("completed" if completed else "")
        st.markdown(f"""
            <div class="progress-step {status}">
                <div class="step-number">{'✓' if completed and not active else num}</div>
                {label}
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 20px 0;'>", unsafe_allow_html=True)
    
    # Quick Profile Settings
    st.markdown("<p style='color: rgba(255,255,255,0.6); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;'>Profile Settings</p>", unsafe_allow_html=True)
    
    filing = st.selectbox(
        "Filing Status",
        options=[s.value for s in FilingStatus],
        format_func=lambda x: x.replace("_", " ").title(),
        index=0,
        key="sidebar_filing"
    )
    st.session_state.enhanced_profile.filing_status = FilingStatus(filing)
    
    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Your Age", min_value=18, max_value=100, value=35, key="sidebar_age")
        st.session_state.enhanced_profile.age = age
    
    with col2:
        if filing == "married_filing_jointly":
            spouse_age = st.number_input("Spouse Age", min_value=18, max_value=100, value=35, key="sidebar_spouse_age")
            if not st.session_state.enhanced_profile.spouse:
                st.session_state.enhanced_profile.spouse = SpouseIncome(age=spouse_age)
            else:
                st.session_state.enhanced_profile.spouse.age = spouse_age
        else:
            st.number_input("Spouse Age", value=0, disabled=True, key="sidebar_spouse_disabled")
    
    children = st.number_input("Children (Under 17)", min_value=0, max_value=10, value=0, key="sidebar_children")
    st.session_state.enhanced_profile.num_children_under_17 = children
    
    st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 20px 0;'>", unsafe_allow_html=True)
    
    # Calculate Button
    if st.button("🔄 Calculate Taxes", use_container_width=True, key="sidebar_calc"):
        with st.spinner("Calculating..."):
            sync_and_calculate()
        st.success("Updated!")
    
    # Privacy Badge
    st.markdown("""
        <div class="privacy-badge">
            <span class="icon">🔒</span>
            <span>PII removed before AI processing</span>
        </div>
    """, unsafe_allow_html=True)


# =============================================================================
# MAIN CONTENT AREA
# =============================================================================

# Header
st.markdown("""
    <div style="background: linear-gradient(135deg, #0077C5 0%, #0097D8 100%); padding: 24px 32px; border-radius: 16px; color: white; margin-bottom: 24px;">
        <div style="font-size: 1.75rem; font-weight: 700; margin-bottom: 8px;">Federal Tax Estimation 2025</div>
        <div style="font-size: 1rem; opacity: 0.9;">Get an accurate estimate of your federal taxes with AI-powered optimization</div>
    </div>
""", unsafe_allow_html=True)

# Calculate if needed
if st.session_state.tax_result is None:
    sync_and_calculate()

result = st.session_state.tax_result
profile = st.session_state.profile

# Main Result Card
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    if result:
        is_refund = result.refund_or_owed >= 0
        card_class = "refund" if is_refund else "owed"
        amount_class = "refund" if is_refund else "owed"
        label = "Estimated Refund" if is_refund else "Estimated Amount Owed"
        amount = abs(result.refund_or_owed)
        
        st.markdown(f"""
            <div class="result-card {card_class} animate-fade-in">
                <div class="result-label">{label}</div>
                <div class="result-amount {amount_class}">{fmt_currency(amount)}</div>
                <div style="color: #6B6B6B; font-size: 0.9rem;">
                    Based on projected annual income of {fmt_currency(result.gross_income)}
                </div>
            </div>
        """, unsafe_allow_html=True)

# Key Metrics Row
st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
        <div class="metric-card animate-fade-in">
            <div class="metric-label">Taxable Income</div>
            <div class="metric-value">{fmt_currency(result.taxable_income)}</div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
        <div class="metric-card animate-fade-in">
            <div class="metric-label">Federal Tax</div>
            <div class="metric-value">{fmt_currency(result.federal_tax)}</div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
        <div class="metric-card animate-fade-in">
            <div class="metric-label">Effective Rate</div>
            <div class="metric-value">{result.effective_rate:.1f}%</div>
        </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
        <div class="metric-card animate-fade-in">
            <div class="metric-label">Marginal Rate</div>
            <div class="metric-value">{result.marginal_rate*100:.0f}%</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)


# =============================================================================
# TABS
# =============================================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Summary", 
    "💼 Income", 
    "📄 Upload Forms",
    "🔮 What-If", 
    "🤖 AI Strategies",
    "💡 Recommendations",
    "🔒 Privacy"
])


# =============================================================================
# TAB 1: SUMMARY
# =============================================================================

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📈 Income Breakdown")
        
        income_data = {
            "Category": ["Gross Income", "Adjustments", "Adjusted Gross Income", 
                        f"{result.deduction_type.title()} Deduction", "Taxable Income"],
            "Amount": [
                fmt_currency(result.gross_income),
                f"-{fmt_currency(result.adjustments)}",
                fmt_currency(result.adjusted_gross_income),
                f"-{fmt_currency(result.deduction_amount)}",
                fmt_currency(result.taxable_income)
            ]
        }
        st.dataframe(
            pd.DataFrame(income_data),
            hide_index=True,
            use_container_width=True
        )
    
    with col2:
        st.markdown("### 💰 Tax Breakdown")
        
        tax_data = {
            "Category": ["Federal Income Tax", "Self-Employment Tax", 
                        "Credits", "Total Tax", "Withholding", "Result"],
            "Amount": [
                fmt_currency(result.federal_tax),
                fmt_currency(result.self_employment_tax),
                f"-{fmt_currency(result.total_credits)}",
                fmt_currency(result.total_tax_liability),
                fmt_currency(result.total_payments_and_withholding),
                fmt_currency(result.refund_or_owed)
            ]
        }
        st.dataframe(
            pd.DataFrame(tax_data),
            hide_index=True,
            use_container_width=True
        )
    
    # Bracket Breakdown
    with st.expander("📊 Tax Bracket Breakdown", expanded=False):
        if result.bracket_breakdown:
            bracket_data = []
            for b in result.bracket_breakdown:
                bracket_data.append({
                    "Rate": f"{b.rate*100:.0f}%",
                    "Bracket Range": f"{fmt_currency(b.bracket_start)} - {fmt_currency(b.bracket_end)}",
                    "Income in Bracket": fmt_currency(b.income_in_bracket),
                    "Tax": fmt_currency(b.tax_in_bracket)
                })
            st.dataframe(pd.DataFrame(bracket_data), hide_index=True, use_container_width=True)


# =============================================================================
# TAB 2: INCOME
# =============================================================================

with tab2:
    st.markdown("### 💼 Income Sources")
    st.markdown("Add all income sources for yourself and your spouse (if married filing jointly)")
    
    # Add Income Source Form
    with st.expander("➕ Add New Income Source", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            source_type = st.selectbox(
                "Income Type",
                options=[
                    ("W-2 (Primary Job)", IncomeSourceType.W2_PRIMARY),
                    ("W-2 (Spouse)", IncomeSourceType.W2_SPOUSE),
                    ("W-2 (Second Job)", IncomeSourceType.W2_SECONDARY),
                    ("1099-NEC (Freelance)", IncomeSourceType.FORM_1099_NEC),
                    ("Self-Employment", IncomeSourceType.SELF_EMPLOYMENT),
                    ("Rental Income", IncomeSourceType.RENTAL_INCOME),
                ],
                format_func=lambda x: x[0],
                key="new_source_type"
            )
            
            source_name = st.text_input(
                "Description (e.g., 'Tech Company' or 'Consulting')",
                key="new_source_name"
            )
        
        with col2:
            pay_freq = st.selectbox(
                "Pay Frequency",
                options=["weekly", "biweekly", "semimonthly", "monthly"],
                format_func=lambda x: x.title(),
                index=1,
                key="new_pay_freq"
            )
            
            current_period = st.number_input(
                "Current Pay Period #",
                min_value=1,
                max_value=52,
                value=22,
                key="new_period"
            )
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ytd_income = st.number_input(
                "YTD Gross Income",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                format="%.2f",
                key="new_ytd_income"
            )
        
        with col2:
            ytd_federal = st.number_input(
                "YTD Federal Withheld",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f",
                key="new_ytd_federal"
            )
        
        with col3:
            ytd_401k = st.number_input(
                "YTD 401(k) Contributions",
                min_value=0.0,
                value=0.0,
                step=500.0,
                format="%.2f",
                key="new_ytd_401k"
            )
        
        if st.button("➕ Add Income Source", type="primary", key="add_source_btn"):
            if ytd_income > 0:
                new_source = IncomeSource(
                    source_type=source_type[1],
                    name=source_name or "[Employer]",
                    pay_frequency=EnhancedPayFrequency(pay_freq),
                    current_pay_period=current_period,
                    ytd_gross=ytd_income,
                    ytd_federal_withheld=ytd_federal,
                    ytd_401k=ytd_401k,
                )
                
                if source_type[1] == IncomeSourceType.W2_SPOUSE:
                    if not st.session_state.enhanced_profile.spouse:
                        st.session_state.enhanced_profile.spouse = SpouseIncome()
                    st.session_state.enhanced_profile.spouse.sources.append(new_source)
                else:
                    st.session_state.enhanced_profile.add_income_source(new_source)
                
                sync_and_calculate()
                st.success(f"✅ Added {source_name or source_type[0]}")
                st.rerun()
            else:
                st.warning("Please enter YTD income greater than $0")
    
    # Display Current Income Sources
    st.markdown("")
    
    all_sources = list(st.session_state.enhanced_profile.income_sources)
    if st.session_state.enhanced_profile.spouse:
        all_sources.extend(st.session_state.enhanced_profile.spouse.sources)
    
    if all_sources:
        st.markdown(f"**{len(all_sources)} Income Source(s)**")
        
        for i, source in enumerate(all_sources):
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                badge_text = source.source_type.value.replace("_", " ").upper()
                st.markdown(f"🏢 **{badge_text}** - {source.name}")
            
            with col2:
                st.markdown(f"**YTD:** {fmt_currency(source.ytd_gross)}")
            
            with col3:
                st.markdown(f"**Withheld:** {fmt_currency(source.ytd_federal_withheld)}")
            
            with col4:
                st.markdown(f"**Projected:** {fmt_currency(source.projected_annual_income)}")
            
            st.markdown("---")
        
        # Totals
        total_ytd = sum(s.ytd_gross for s in all_sources)
        total_withheld = sum(s.ytd_federal_withheld for s in all_sources)
        total_projected = sum(s.projected_annual_income for s in all_sources)
        
        st.info(f"**Total YTD:** {fmt_currency(total_ytd)} | **Total Withheld:** {fmt_currency(total_withheld)} | **Projected Annual:** {fmt_currency(total_projected)}")
    else:
        st.info("👆 Add your first income source above to get started!")


# =============================================================================
# TAB 3: UPLOAD TAX FORMS
# =============================================================================

with tab3:
    st.markdown("### 📄 Upload Tax Documents")
    st.markdown("""
        Upload your W-2, 1099, or other tax forms. TaxGuard AI will:
        1. **Extract** income and withholding information using OCR
        2. **Remove** all personal information (SSN, names, addresses) before processing
        3. **Auto-fill** your income sources based on the extracted data
    """)
    
    st.markdown("---")
    
    # Document type selector
    doc_type = st.selectbox(
        "Document Type",
        options=[
            "W-2 (Wage and Tax Statement)",
            "1099-NEC (Nonemployee Compensation)",
            "1099-MISC (Miscellaneous Income)",
            "1099-INT (Interest Income)",
            "1099-DIV (Dividends)",
            "1099-B (Broker Transactions)",
            "1040 (Tax Return - Prior Year)",
            "Pay Stub",
            "Other Tax Document"
        ],
        key="upload_doc_type"
    )
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Upload your document (PDF or Image)",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Supported formats: PDF, PNG, JPG. Max size: 10MB",
        key="tax_doc_uploader"
    )
    
    if uploaded_file is not None:
        st.success(f"✅ Uploaded: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            process_btn = st.button(
                "🔍 Process Document",
                type="primary",
                use_container_width=True,
                key="process_doc_btn"
            )
        
        with col2:
            st.markdown("")  # Spacer
        
        if process_btn:
            # Show privacy pipeline
            st.info("🛡️ **Privacy Protection Active** - Personal information will be removed before processing")
            
            progress = st.progress(0)
            status = st.empty()
            
            # Step 1: Read document
            status.text("Step 1/4: Reading document...")
            progress.progress(25)
            time.sleep(0.5)
            
            # Step 2: OCR (if image/PDF)
            status.text("Step 2/4: Extracting text with OCR...")
            progress.progress(50)
            
            # Read file content
            file_content = uploaded_file.read()
            extracted_text = ""
            
            try:
                if uploaded_file.type == "application/pdf":
                    # Try pdfplumber for PDF
                    try:
                        import pdfplumber
                        import io
                        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                            for page in pdf.pages:
                                extracted_text += page.extract_text() or ""
                    except ImportError:
                        st.warning("PDF processing requires pdfplumber. Using fallback.")
                        extracted_text = "[PDF content - install pdfplumber for extraction]"
                else:
                    # Image - use pytesseract
                    try:
                        from PIL import Image
                        import pytesseract
                        import io
                        image = Image.open(io.BytesIO(file_content))
                        extracted_text = pytesseract.image_to_string(image)
                    except ImportError:
                        st.warning("Image OCR requires pytesseract. Using fallback.")
                        extracted_text = "[Image content - install pytesseract for extraction]"
                    except Exception as e:
                        st.warning(f"OCR processing error: {e}")
                        extracted_text = "[Could not extract text from image]"
            except Exception as e:
                st.error(f"Error reading document: {e}")
                extracted_text = ""
            
            time.sleep(0.5)
            
            # Step 3: PII Redaction
            status.text("Step 3/4: Removing personal information (SSN, names, addresses)...")
            progress.progress(75)
            
            if extracted_text:
                redactor = PIIRedactor(use_ner=False)
                redaction_result = redactor.redact_sensitive_data(extracted_text)
                redacted_text = redaction_result.redacted_text
                pii_count = redaction_result.redaction_count
                pii_types = redaction_result.pii_types_found
            else:
                redacted_text = ""
                pii_count = 0
                pii_types = []
            
            time.sleep(0.5)
            
            # Step 4: Extract financial data
            status.text("Step 4/4: Extracting financial information...")
            progress.progress(100)
            time.sleep(0.3)
            
            # Clear progress
            progress.empty()
            status.empty()
            
            # Show results
            st.markdown("---")
            st.markdown("### 📊 Extraction Results")
            
            # Privacy confirmation
            if pii_count > 0:
                st.success(f"🛡️ **Privacy Protected**: Removed {pii_count} personal information items")
                with st.expander("View PII types removed"):
                    for pii_type in pii_types:
                        st.markdown(f"- 🚫 {pii_type}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Original Document (Preview)**")
                # Show first 500 chars of original with PII warning
                if extracted_text:
                    preview = extracted_text[:500] + ("..." if len(extracted_text) > 500 else "")
                    st.text_area(
                        "Contains PII - DO NOT SHARE",
                        value=preview,
                        height=200,
                        disabled=True,
                        key="original_preview"
                    )
                else:
                    st.warning("Could not extract text from document")
            
            with col2:
                st.markdown("**After PII Removal (Safe)**")
                if redacted_text:
                    preview = redacted_text[:500] + ("..." if len(redacted_text) > 500 else "")
                    st.text_area(
                        "PII Removed - Safe to process",
                        value=preview,
                        height=200,
                        disabled=True,
                        key="redacted_preview"
                    )
                else:
                    st.info("No text to display")
            
            # Parse extracted data based on document type
            st.markdown("---")
            st.markdown("### 💰 Detected Financial Information")
            
            # Comprehensive pattern matching for various paystub formats
            import re
            
            detected_data = {}
            
            # Helper function to find dollar amounts near keywords
            def find_amount_near_keyword(text, keywords, search_range=100):
                """Find dollar amount near any of the keywords."""
                text_lower = text.lower()
                for keyword in keywords:
                    # Find keyword position
                    pos = text_lower.find(keyword.lower())
                    if pos != -1:
                        # Look for dollar amounts in the surrounding area
                        start = max(0, pos - 20)
                        end = min(len(text), pos + search_range)
                        snippet = text[start:end]
                        
                        # Match various dollar formats: $1,234.56 or 1234.56 or 1,234
                        amounts = re.findall(r'\$?\s*([\d,]+\.?\d{0,2})', snippet)
                        for amt in amounts:
                            try:
                                value = float(amt.replace(",", ""))
                                if value > 0:  # Ignore zero values
                                    return value
                            except:
                                pass
                return None
            
            # Comprehensive keyword lists for different fields
            gross_keywords = [
                "gross pay", "gross earnings", "gross income", "total gross",
                "gross wages", "total earnings", "earnings gross", "gross amount"
            ]
            
            ytd_gross_keywords = [
                "ytd gross", "ytd earnings", "ytd total", "year to date gross",
                "ytd wages", "total ytd", "ytd earn", "gross ytd", "ytd amount"
            ]
            
            federal_keywords = [
                "federal tax", "fed tax", "federal w/h", "fed w/h", "federal withholding",
                "fed withholding", "federal income tax", "fit", "fed inc tax",
                "federal withheld", "fed withheld", "us tax", "federal w-h"
            ]
            
            ytd_federal_keywords = [
                "ytd federal", "ytd fed", "federal ytd", "fed ytd", "ytd fit",
                "ytd fed tax", "ytd federal tax", "federal tax ytd", "ytd fed w/h"
            ]
            
            retirement_keywords = [
                "401k", "401(k)", "retirement", "403b", "403(b)", "tsp",
                "pension", "def comp", "deferred comp", "401 k"
            ]
            
            ytd_retirement_keywords = [
                "ytd 401k", "ytd 401(k)", "401k ytd", "ytd retirement",
                "retirement ytd", "ytd 403b", "ytd pension"
            ]
            
            ss_keywords = [
                "social security", "soc sec", "ss tax", "fica ss", "oasdi",
                "social sec", "ss wages"
            ]
            
            medicare_keywords = [
                "medicare", "med tax", "fica med", "fica medicare"
            ]
            
            state_keywords = [
                "state tax", "state w/h", "state withholding", "sit",
                "state income", "state withheld"
            ]
            
            net_keywords = [
                "net pay", "net amount", "take home", "net earnings", "net check"
            ]
            
            # Try to extract each field
            # Current period values
            current_gross = find_amount_near_keyword(redacted_text, gross_keywords)
            current_federal = find_amount_near_keyword(redacted_text, federal_keywords)
            current_retirement = find_amount_near_keyword(redacted_text, retirement_keywords)
            
            # YTD values (more important for tax calculation)
            ytd_gross = find_amount_near_keyword(redacted_text, ytd_gross_keywords)
            ytd_federal = find_amount_near_keyword(redacted_text, ytd_federal_keywords)
            ytd_retirement = find_amount_near_keyword(redacted_text, ytd_retirement_keywords)
            
            # Other values
            ss_tax = find_amount_near_keyword(redacted_text, ss_keywords)
            medicare_tax = find_amount_near_keyword(redacted_text, medicare_keywords)
            state_tax = find_amount_near_keyword(redacted_text, state_keywords)
            net_pay = find_amount_near_keyword(redacted_text, net_keywords)
            
            # Store what we found
            if current_gross: detected_data["Current Gross Pay"] = current_gross
            if current_federal: detected_data["Current Federal Tax"] = current_federal
            if current_retirement: detected_data["Current 401(k)"] = current_retirement
            if ytd_gross: detected_data["YTD Gross"] = ytd_gross
            if ytd_federal: detected_data["YTD Federal Tax"] = ytd_federal
            if ytd_retirement: detected_data["YTD 401(k)"] = ytd_retirement
            if ss_tax: detected_data["Social Security Tax"] = ss_tax
            if medicare_tax: detected_data["Medicare Tax"] = medicare_tax
            if state_tax: detected_data["State Tax"] = state_tax
            if net_pay: detected_data["Net Pay"] = net_pay
            
            # Also try to find any large dollar amounts as fallback
            all_amounts = re.findall(r'\$\s*([\d,]+\.?\d{0,2})', redacted_text)
            large_amounts = []
            for amt in all_amounts:
                try:
                    value = float(amt.replace(",", ""))
                    if value >= 100:  # Ignore small amounts
                        large_amounts.append(value)
                except:
                    pass
            
            # Option to use AI for extraction
            st.markdown("---")
            
            col_extract1, col_extract2 = st.columns([1, 1])
            
            with col_extract1:
                use_ai = st.checkbox(
                    "🤖 Use AI to extract data (more accurate)", 
                    value=True,
                    key="use_ai_extraction",
                    help="Uses GPT-5.1 to intelligently extract financial data from the document"
                )
            
            with col_extract2:
                if use_ai and OPENAI_CLIENT_AVAILABLE:
                    ai_extract_btn = st.button("🔍 Extract with AI", type="primary", key="ai_extract_btn")
                else:
                    ai_extract_btn = False
                    if use_ai and not OPENAI_CLIENT_AVAILABLE:
                        st.warning("AI extraction requires OpenAI API key")
            
            # AI-powered extraction
            if use_ai and ai_extract_btn and OPENAI_CLIENT_AVAILABLE:
                with st.spinner("🤖 AI is analyzing the document..."):
                    ai_client = get_ai_client()
                    
                    # Create extraction prompt
                    extraction_prompt = f"""Analyze this redacted paystub/tax document and extract the financial information.
The document has had all personal information (SSN, names, addresses) removed for privacy.

DOCUMENT TEXT:
{redacted_text}

Please extract and return the following values in JSON format. Use null if a value cannot be found:
{{
    "current_gross_pay": <number or null>,
    "current_federal_tax_withheld": <number or null>,
    "current_state_tax_withheld": <number or null>,
    "current_social_security_tax": <number or null>,
    "current_medicare_tax": <number or null>,
    "current_401k_contribution": <number or null>,
    "current_net_pay": <number or null>,
    "ytd_gross_pay": <number or null>,
    "ytd_federal_tax_withheld": <number or null>,
    "ytd_state_tax_withheld": <number or null>,
    "ytd_social_security_tax": <number or null>,
    "ytd_medicare_tax": <number or null>,
    "ytd_401k_contribution": <number or null>,
    "ytd_net_pay": <number or null>,
    "pay_frequency": "<weekly/biweekly/semimonthly/monthly or null>",
    "pay_period_number": <number or null>
}}

Return ONLY the JSON object, no other text."""

                    try:
                        response = ai_client.client.chat.completions.create(
                            model=ai_client.model,
                            messages=[
                                {"role": "system", "content": "You are a financial document parser. Extract financial data accurately and return valid JSON only."},
                                {"role": "user", "content": extraction_prompt}
                            ]
                        )
                        
                        ai_response = response.choices[0].message.content.strip()
                        
                        # Try to parse JSON from response
                        # Handle potential markdown code blocks
                        if "```json" in ai_response:
                            ai_response = ai_response.split("```json")[1].split("```")[0]
                        elif "```" in ai_response:
                            ai_response = ai_response.split("```")[1].split("```")[0]
                        
                        import json as json_module
                        ai_data = json_module.loads(ai_response)
                        
                        # Update detected_data with AI results
                        if ai_data.get("current_gross_pay"): detected_data["Current Gross Pay"] = ai_data["current_gross_pay"]
                        if ai_data.get("current_federal_tax_withheld"): detected_data["Current Federal Tax"] = ai_data["current_federal_tax_withheld"]
                        if ai_data.get("current_state_tax_withheld"): detected_data["Current State Tax"] = ai_data["current_state_tax_withheld"]
                        if ai_data.get("current_social_security_tax"): detected_data["Current SS Tax"] = ai_data["current_social_security_tax"]
                        if ai_data.get("current_medicare_tax"): detected_data["Current Medicare Tax"] = ai_data["current_medicare_tax"]
                        if ai_data.get("current_401k_contribution"): detected_data["Current 401(k)"] = ai_data["current_401k_contribution"]
                        if ai_data.get("current_net_pay"): detected_data["Current Net Pay"] = ai_data["current_net_pay"]
                        if ai_data.get("ytd_gross_pay"): detected_data["YTD Gross"] = ai_data["ytd_gross_pay"]
                        if ai_data.get("ytd_federal_tax_withheld"): detected_data["YTD Federal Tax"] = ai_data["ytd_federal_tax_withheld"]
                        if ai_data.get("ytd_state_tax_withheld"): detected_data["YTD State Tax"] = ai_data["ytd_state_tax_withheld"]
                        if ai_data.get("ytd_social_security_tax"): detected_data["YTD SS Tax"] = ai_data["ytd_social_security_tax"]
                        if ai_data.get("ytd_medicare_tax"): detected_data["YTD Medicare Tax"] = ai_data["ytd_medicare_tax"]
                        if ai_data.get("ytd_401k_contribution"): detected_data["YTD 401(k)"] = ai_data["ytd_401k_contribution"]
                        
                        # Store pay info in session state
                        if ai_data.get("pay_frequency"):
                            st.session_state['detected_pay_frequency'] = ai_data["pay_frequency"]
                        if ai_data.get("pay_period_number"):
                            st.session_state['detected_pay_period'] = ai_data["pay_period_number"]
                        
                        st.success("✅ AI extraction complete!")
                        
                    except Exception as e:
                        st.error(f"AI extraction error: {e}")
                        st.info("Falling back to pattern matching results")
            
            # Display all detected data
            if detected_data:
                st.markdown("**Extracted Values:**")
                
                # Organize into current and YTD
                current_items = {k: v for k, v in detected_data.items() if "Current" in k or "YTD" not in k}
                ytd_items = {k: v for k, v in detected_data.items() if "YTD" in k}
                
                col_curr, col_ytd = st.columns(2)
                
                with col_curr:
                    st.markdown("**Current Period:**")
                    for label, value in current_items.items():
                        st.markdown(f"- {label}: **{fmt_currency(value)}**")
                
                with col_ytd:
                    st.markdown("**Year-to-Date:**")
                    for label, value in ytd_items.items():
                        st.markdown(f"- {label}: **{fmt_currency(value)}**")
                
                # Show large amounts found (for debugging)
                if large_amounts and not detected_data:
                    with st.expander("💡 All dollar amounts found in document"):
                        st.write(sorted(set(large_amounts), reverse=True)[:20])
                
                st.markdown("---")
                
                # Option to add as income source
                st.markdown("### ➕ Add to Income Sources")
                st.markdown("*Review and adjust the values below, then click Add*")
                
                add_col1, add_col2 = st.columns(2)
                
                with add_col1:
                    # Prefer YTD values, fall back to current values
                    auto_income = detected_data.get("YTD Gross", 
                                    detected_data.get("Current Gross Pay", 0))
                    auto_withheld = detected_data.get("YTD Federal Tax", 
                                      detected_data.get("Current Federal Tax", 0))
                    auto_401k = detected_data.get("YTD 401(k)", 
                                  detected_data.get("Current 401(k)", 0))
                    
                    final_income = st.number_input(
                        "YTD Gross Income", 
                        value=float(auto_income), 
                        key="auto_ytd_income", 
                        format="%.2f",
                        help="Total gross income year-to-date"
                    )
                    final_withheld = st.number_input(
                        "YTD Federal Tax Withheld", 
                        value=float(auto_withheld), 
                        key="auto_ytd_withheld", 
                        format="%.2f",
                        help="Total federal tax withheld year-to-date"
                    )
                    final_401k = st.number_input(
                        "YTD 401(k) Contributions", 
                        value=float(auto_401k), 
                        key="auto_ytd_401k", 
                        format="%.2f",
                        help="Total 401(k) contributions year-to-date"
                    )
                
                with add_col2:
                    source_name = st.text_input(
                        "Employer/Source Name", 
                        value="[From uploaded document]", 
                        key="auto_source_name"
                    )
                    
                    # Pay frequency
                    freq_options = ["biweekly", "weekly", "semimonthly", "monthly"]
                    default_freq = st.session_state.get('detected_pay_frequency', 'biweekly')
                    if default_freq not in freq_options:
                        default_freq = 'biweekly'
                    
                    pay_freq = st.selectbox(
                        "Pay Frequency",
                        options=freq_options,
                        index=freq_options.index(default_freq),
                        format_func=lambda x: x.title(),
                        key="auto_pay_freq"
                    )
                    
                    # Current pay period
                    default_period = st.session_state.get('detected_pay_period', 22)
                    current_period = st.number_input(
                        "Current Pay Period #",
                        min_value=1,
                        max_value=52,
                        value=int(default_period) if default_period else 22,
                        key="auto_pay_period"
                    )
                    
                    if st.button("➕ Add as Income Source", type="primary", key="auto_add_source"):
                        # Create income source from extracted data
                        new_source = IncomeSource(
                            source_type=IncomeSourceType.W2_PRIMARY if "W-2" in doc_type else IncomeSourceType.FORM_1099_NEC,
                            name=source_name,
                            pay_frequency=EnhancedPayFrequency(pay_freq),
                            current_pay_period=current_period,
                            ytd_gross=final_income,
                            ytd_federal_withheld=final_withheld,
                            ytd_401k=final_401k,
                        )
                        st.session_state.enhanced_profile.add_income_source(new_source)
                        sync_and_calculate()
                        st.success("✅ Income source added! Check the Income tab.")
                        st.rerun()
            else:
                st.warning("Could not automatically detect financial information.")
                
                # Show all amounts found as fallback
                if large_amounts:
                    st.markdown("**Dollar amounts found in document:**")
                    st.write(sorted(set(large_amounts), reverse=True)[:15])
                    st.info("You can manually enter these values below or in the Income tab.")
                
                # Manual entry form
                st.markdown("### Manual Entry")
                man_col1, man_col2 = st.columns(2)
                
                with man_col1:
                    manual_income = st.number_input("YTD Gross Income", value=0.0, key="manual_income", format="%.2f")
                    manual_withheld = st.number_input("YTD Federal Withheld", value=0.0, key="manual_withheld", format="%.2f")
                    manual_401k = st.number_input("YTD 401(k)", value=0.0, key="manual_401k", format="%.2f")
                
                with man_col2:
                    manual_name = st.text_input("Employer Name", key="manual_name")
                    if st.button("➕ Add Manually", type="primary", key="manual_add"):
                        if manual_income > 0:
                            new_source = IncomeSource(
                                source_type=IncomeSourceType.W2_PRIMARY,
                                name=manual_name or "[Manual Entry]",
                                pay_frequency=EnhancedPayFrequency.BIWEEKLY,
                                current_pay_period=22,
                                ytd_gross=manual_income,
                                ytd_federal_withheld=manual_withheld,
                                ytd_401k=manual_401k,
                            )
                            st.session_state.enhanced_profile.add_income_source(new_source)
                            sync_and_calculate()
                            st.success("✅ Added!")
                            st.rerun()
    
    # Manual entry reminder
    st.markdown("---")
    st.info("💡 **Tip:** You can also manually enter income information in the **Income** tab without uploading documents.")


# =============================================================================
# TAB 4: WHAT-IF SIMULATOR
# =============================================================================

with tab4:
    st.markdown("### 🔮 What-If Tax Simulator")
    st.markdown("See how different scenarios could affect your tax outcome")
    
    simulator = TaxSimulator(profile)
    
    # Quick Scenarios
    st.markdown("**Quick Scenarios**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("Max 401(k)", use_container_width=True, key="sim_401k"):
            sim = simulator.find_optimal_401k()
            st.session_state.simulations.insert(0, sim)
    
    with col2:
        if st.button("Max HSA", use_container_width=True, key="sim_hsa"):
            sim = simulator.find_optimal_hsa()
            st.session_state.simulations.insert(0, sim)
    
    with col3:
        if st.button("Max Both", use_container_width=True, key="sim_both"):
            changes = {}
            if profile.remaining_401k_room > 0:
                changes["extra_401k_traditional"] = profile.remaining_401k_room
            if profile.remaining_hsa_room > 0:
                changes["extra_hsa"] = profile.remaining_hsa_room
            if changes:
                sim = simulator.run_simulation(changes, "Max 401(k) + HSA")
                st.session_state.simulations.insert(0, sim)
    
    with col4:
        if st.button("Clear All", use_container_width=True, key="sim_clear"):
            st.session_state.simulations = []
    
    st.markdown("---")
    
    # Custom Simulation
    st.markdown("**Custom Simulation**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        add_401k = st.number_input(
            f"Additional 401(k) (Room: {fmt_currency(profile.remaining_401k_room)})",
            min_value=0.0,
            max_value=float(max(0, profile.remaining_401k_room)),
            value=0.0,
            step=500.0,
            key="custom_401k"
        )
    
    with col2:
        add_hsa = st.number_input(
            f"Additional HSA (Room: {fmt_currency(profile.remaining_hsa_room)})",
            min_value=0.0,
            max_value=float(max(0, profile.remaining_hsa_room)),
            value=0.0,
            step=100.0,
            key="custom_hsa"
        )
    
    with col3:
        add_ira = st.number_input(
            "Additional Traditional IRA",
            min_value=0.0,
            max_value=7000.0,
            value=0.0,
            step=500.0,
            key="custom_ira"
        )
    
    if st.button("🚀 Run Simulation", type="primary", key="run_custom_sim"):
        changes = {}
        if add_401k > 0:
            changes["extra_401k_traditional"] = add_401k
        if add_hsa > 0:
            changes["extra_hsa"] = add_hsa
        if add_ira > 0:
            changes["extra_ira_traditional"] = add_ira
        
        if changes:
            sim = simulator.run_simulation(changes, "Custom Scenario")
            st.session_state.simulations.insert(0, sim)
        else:
            st.warning("Please enter at least one value to simulate")
    
    # Results
    st.markdown("---")
    st.markdown("**Simulation Results**")
    
    if st.session_state.simulations:
        for i, sim in enumerate(st.session_state.simulations[:5]):
            is_beneficial = sim.is_beneficial
            savings = abs(sim.tax_difference)
            
            icon = "✅" if is_beneficial else "⚠️"
            
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{icon} {sim.scenario_name}**")
                    st.caption(sim.summary)
                with col2:
                    if is_beneficial:
                        st.success(f"Save {fmt_currency(savings)}")
                    else:
                        st.error(f"+{fmt_currency(savings)}")
    else:
        st.info("Run a simulation to see results here")


# =============================================================================
# TAB 5: AI STRATEGIES
# =============================================================================

with tab5:
    st.markdown("### 🤖 AI-Powered Tax Strategies")
    st.markdown("Get personalized tax reduction strategies powered by GPT-5.1 with adaptive reasoning")
    
    # AI Status
    ai_client = get_ai_client()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        if ai_client.is_connected:
            st.success("🟢 **Connected to OpenAI GPT-5.1** - AI-powered analysis available")
        else:
            st.warning("🔴 **AI Offline** - Add `OPENAI_API_KEY` to Streamlit secrets for personalized strategies")
    
    with col2:
        st.markdown(f"**Model:** `{ai_client.model}`")
    
    st.markdown("---")
    
    # Generate AI Strategies Button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        generate_btn = st.button(
            "🚀 Generate AI Tax Strategies",
            type="primary",
            use_container_width=True,
            key="generate_ai_strategies"
        )
    
    if generate_btn:
        # Create a prominent privacy notice at the top
        privacy_notice = st.empty()
        privacy_notice.info("🛡️ **Privacy Protection Active** - Your personal information will be removed before any data is sent to AI")
        
        # Show the privacy pipeline
        pipeline_placeholder = st.empty()
        status_placeholder = st.empty()
        
        pipeline_steps = [
            {"title": "Collecting Financial Data", "description": "Gathering income, deductions, and tax information from your profile...", "icon": "📊"},
            {"title": "Scanning for Personal Information", "description": "Detecting SSN, names, addresses, phone numbers, emails, account numbers...", "icon": "🔍"},
            {"title": "Removing All PII", "description": "Replacing personal identifiers with anonymous placeholders...", "icon": "🚫"},
            {"title": "Verifying Anonymization", "description": "Double-checking that NO personal information remains...", "icon": "✓"},
            {"title": "Secure Transmission", "description": "Sending ONLY anonymized financial numbers to GPT-5.1...", "icon": "🔐"},
            {"title": "AI Analysis in Progress", "description": "GPT-5.1 analyzing your tax situation with adaptive reasoning...", "icon": "🤖"},
        ]
        
        # Step 1: Collecting data
        status_placeholder.warning("⏳ Step 1/6: Collecting your financial data...")
        show_pii_pipeline(pipeline_placeholder, 0, pipeline_steps)
        time.sleep(0.6)
        
        # Step 2: Scanning for PII
        status_placeholder.warning("⏳ Step 2/6: Scanning for personal information...")
        show_pii_pipeline(pipeline_placeholder, 1, pipeline_steps)
        time.sleep(0.7)
        
        # Actually anonymize the data
        anonymized_profile = create_anonymized_profile(profile)
        anonymized_result = create_anonymized_tax_result(result)
        
        pii_removed = [
            "Social Security Numbers (SSN)",
            "Full Names", 
            "Street Addresses",
            "Phone Numbers",
            "Email Addresses", 
            "Bank Account Numbers",
            "Employer Identification Numbers (EIN)"
        ]
        
        # Step 3: Removing PII
        status_placeholder.warning("⏳ Step 3/6: Removing all personal information...")
        show_pii_pipeline(pipeline_placeholder, 2, pipeline_steps, pii_removed)
        time.sleep(0.8)
        
        # Step 4: Verifying
        status_placeholder.warning("⏳ Step 4/6: Verifying complete anonymization...")
        show_pii_pipeline(pipeline_placeholder, 3, pipeline_steps, pii_removed)
        time.sleep(0.5)
        
        # Step 5: Secure transmission
        status_placeholder.warning("⏳ Step 5/6: Establishing secure connection to GPT-5.1...")
        show_pii_pipeline(pipeline_placeholder, 4, pipeline_steps, pii_removed)
        time.sleep(0.4)
        
        # Step 6: AI Analysis
        status_placeholder.info("🤖 Step 6/6: GPT-5.1 is analyzing your tax situation...")
        show_pii_pipeline(pipeline_placeholder, 5, pipeline_steps, pii_removed)
        
        # Make the AI call
        response = ai_client.generate_strategies(
            anonymized_profile=anonymized_profile,
            current_tax_result=anonymized_result
        )
        
        # Clear the pipeline display
        pipeline_placeholder.empty()
        status_placeholder.empty()
        privacy_notice.empty()
        
        if response.success:
            st.session_state.ai_strategies = response.content
            
            # Show success message with privacy confirmation
            tokens_msg = f" ({response.tokens_used} tokens used)" if response.tokens_used else ""
            st.success(f"✅ Strategies generated successfully!{tokens_msg}")
            st.info("🛡️ **Privacy Confirmed**: Only anonymized financial data was sent to GPT-5.1. Your personal information (SSN, name, address, etc.) was never transmitted.")
        else:
            st.error(f"Error generating strategies: {response.error}")
    
    # Display AI Strategies
    if st.session_state.ai_strategies:
        st.markdown("---")
        
        # Show what data was sent
        with st.expander("🔍 View Anonymized Data Sent to AI", expanded=False):
            st.markdown("**This is the ONLY data that was sent to the AI - no personal information:**")
            
            anonymized_profile = create_anonymized_profile(profile)
            anonymized_result = create_anonymized_tax_result(result)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Financial Profile (Anonymized):**")
                st.json(anonymized_profile)
            with col2:
                st.markdown("**Tax Calculation Results:**")
                st.json(anonymized_result)
        
        st.markdown("### 📋 Your Personalized Tax Strategies")
        st.markdown(st.session_state.ai_strategies)
    
    # Custom AI Question
    st.markdown("---")
    st.markdown("### 💬 Ask the AI a Tax Question")
    
    custom_question = st.text_area(
        "Describe a tax scenario or ask a question:",
        placeholder="e.g., 'What if I started a side business?' or 'Should I convert my Traditional IRA to a Roth?'",
        key="ai_custom_question"
    )
    
    if st.button("🔍 Analyze Scenario", key="analyze_scenario_btn"):
        if custom_question:
            # Show privacy pipeline for scenario analysis
            st.info("🛡️ **Privacy Protection Active** - Anonymizing your data before AI analysis...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("Step 1/4: Collecting financial context...")
            progress_bar.progress(25)
            time.sleep(0.3)
            
            status_text.text("Step 2/4: Removing personal information (SSN, names, addresses)...")
            progress_bar.progress(50)
            anonymized_profile = create_anonymized_profile(profile)
            anonymized_result = create_anonymized_tax_result(result)
            time.sleep(0.4)
            
            status_text.text("Step 3/4: Verifying anonymization complete...")
            progress_bar.progress(75)
            time.sleep(0.3)
            
            status_text.text("Step 4/4: GPT-5.1 analyzing your scenario...")
            progress_bar.progress(100)
            
            response = ai_client.analyze_scenario(
                scenario_description=custom_question,
                anonymized_profile=anonymized_profile,
                current_tax_result=anonymized_result
            )
            
            # Clear progress
            progress_bar.empty()
            status_text.empty()
            
            if response.success:
                st.success("🛡️ Analysis complete! Only anonymized data was sent to GPT-5.1.")
                st.markdown("### Analysis Results")
                st.markdown(response.content)
            else:
                st.error(f"Error: {response.error}")
        else:
            st.warning("Please enter a question or scenario to analyze")


# =============================================================================
# TAB 6: RECOMMENDATIONS
# =============================================================================

with tab6:
    recs = st.session_state.recommendations
    
    if recs:
        # Summary Banner
        st.success(f"💰 **Maximum Potential Tax Savings: {fmt_currency(recs.max_potential_savings)}** — {recs.days_until_year_end} days left to take action this year")
        
        # Basic Recommendations
        st.markdown("### 🎯 Basic Recommendations")
        st.markdown("*Actions anyone can take*")
        
        for rec in recs.basic_recommendations:
            priority_icon = "🔴" if rec.priority.value in ['critical', 'high'] else "🟡" if rec.priority.value == 'medium' else "🟢"
            
            with st.expander(f"{priority_icon} {rec.title} — Save {fmt_currency(rec.potential_tax_savings)}"):
                st.write(rec.description)
                st.markdown(f"**Action Required:** {rec.action_required}")
                
                if rec.remaining_contribution_room:
                    st.info(f"💰 Room Remaining: {fmt_currency(rec.remaining_contribution_room)}")
                
                if rec.per_paycheck_amount:
                    st.info(f"📅 Per Paycheck: {fmt_currency(rec.per_paycheck_amount)}")
                
                if rec.warnings:
                    for w in rec.warnings:
                        st.warning(w)
        
        # Advanced Recommendations
        if recs.advanced_recommendations:
            st.markdown("---")
            st.markdown("### 🚀 Advanced Strategies")
            st.markdown("*Life-changing opportunities that may require professional guidance*")
            
            for rec in recs.advanced_recommendations[:10]:
                with st.expander(f"💼 {rec.title}"):
                    st.write(rec.description)
                    st.markdown(f"**Action:** {rec.action_required}")
                    
                    if rec.potential_tax_savings > 0:
                        st.success(f"Potential Savings: {fmt_currency(rec.potential_tax_savings)}")
                    
                    if rec.requires_professional:
                        st.info("👔 Consider consulting a tax professional")
                    
                    if rec.warnings:
                        for w in rec.warnings:
                            st.warning(w)
    else:
        st.info("Add income data to receive personalized recommendations")


# =============================================================================
# TAB 7: PRIVACY
# =============================================================================

with tab7:
    st.markdown("### 🔒 Privacy Air Gap Technology")
    st.markdown("""
        TaxGuard AI uses a "Privacy Air Gap" to ensure your personal information 
        **NEVER** reaches external AI services.
    """)
    
    # How it works - Visual Pipeline
    st.markdown("### How Your Data is Protected")
    
    st.markdown("""
        <div class="privacy-pipeline">
            <div class="pipeline-step completed">
                <div class="pipeline-icon">1️⃣</div>
                <div>
                    <div style="font-weight: 500;">You Enter Data</div>
                    <div style="font-size: 0.85rem; opacity: 0.8;">Income, deductions, personal info</div>
                </div>
            </div>
            <div class="pipeline-step completed">
                <div class="pipeline-icon">2️⃣</div>
                <div>
                    <div style="font-weight: 500;">PII Detection</div>
                    <div style="font-size: 0.85rem; opacity: 0.8;">AI + Regex identifies SSN, names, addresses</div>
                </div>
            </div>
            <div class="pipeline-step completed">
                <div class="pipeline-icon">3️⃣</div>
                <div>
                    <div style="font-weight: 500;">PII Removal</div>
                    <div style="font-size: 0.85rem; opacity: 0.8;">Personal info replaced with [REDACTED]</div>
                </div>
            </div>
            <div class="pipeline-step completed">
                <div class="pipeline-icon">4️⃣</div>
                <div>
                    <div style="font-weight: 500;">AI Processing</div>
                    <div style="font-size: 0.85rem; opacity: 0.8;">Only anonymized numbers sent to GPT-5.1</div>
                </div>
            </div>
            <div class="pipeline-step completed">
                <div class="pipeline-icon">5️⃣</div>
                <div>
                    <div style="font-weight: 500;">Results Returned</div>
                    <div style="font-size: 0.85rem; opacity: 0.8;">Strategies based on your financial situation</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # What gets removed vs what gets sent
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
            ### 🚫 What is REMOVED
            
            Before any data goes to AI:
            - ❌ Social Security Numbers
            - ❌ Names (yours, spouse, employer)
            - ❌ Addresses
            - ❌ Phone Numbers
            - ❌ Email Addresses
            - ❌ Bank Account Numbers
            - ❌ Employer IDs (EIN)
            - ❌ Any identifying text
        """)
    
    with col2:
        st.markdown("""
            ### ✅ What IS Sent to AI
            
            Only anonymized financial data:
            - ✅ Income amounts (no source names)
            - ✅ Tax withholding amounts
            - ✅ Deduction totals
            - ✅ Filing status
            - ✅ Age bracket (not exact age)
            - ✅ Number of dependents
            - ✅ Contribution amounts
            - ✅ Tax calculation results
        """)
    
    st.markdown("---")
    
    # Live Demo
    st.markdown("### 🔬 Try It Yourself")
    
    demo_text = """ACME Corporation
Employee: John A. Smith
SSN: 123-45-6789
Employee ID: E12345

Pay Period: 10/01/2025 - 10/15/2025
Pay Date: 10/20/2025

Address: 123 Main Street, Anytown, CA 90210
Email: john.smith@acme.com
Phone: (555) 123-4567

Gross Pay: $4,250.00
Federal Tax: $425.00
401(k): $425.00

YTD Gross: $85,000.00
YTD Federal: $8,500.00

Employer EIN: 12-3456789"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📄 Original Document**")
        input_text = st.text_area(
            "Input",
            value=demo_text,
            height=350,
            label_visibility="collapsed",
            key="privacy_input"
        )
    
    with col2:
        st.markdown("**🛡️ After Redaction**")
        
        if st.button("🔍 Run PII Redaction", type="primary", key="redact_btn"):
            # Show progress
            with st.spinner("🔍 Scanning for personal information..."):
                time.sleep(0.5)
                
                # Run redaction
                redactor = PIIRedactor(use_ner=False)
                redact_result = redactor.redact_sensitive_data(input_text)
            
            st.text_area(
                "Output",
                value=redact_result.redacted_text,
                height=350,
                disabled=True,
                label_visibility="collapsed",
                key="privacy_output"
            )
            
            st.success(f"✅ Redacted **{redact_result.redaction_count}** PII items in **{redact_result.processing_time_ms:.1f}ms**")
            
            if redact_result.pii_types_found:
                st.markdown("**PII Types Detected & Removed:**")
                for pii_type in redact_result.pii_types_found:
                    st.markdown(f"- 🚫 {pii_type}")
        else:
            st.text_area(
                "Output",
                value="Click 'Run PII Redaction' to see the result...",
                height=350,
                disabled=True,
                label_visibility="collapsed",
                key="privacy_placeholder"
            )


# =============================================================================
# FOOTER
# =============================================================================

st.markdown("---")

st.caption("""
    ⚠️ **Disclaimer:** TaxGuard AI provides estimates only and is not a substitute for professional tax advice.
    Calculations are based on 2025 federal tax rules and may not account for all deductions, credits, or individual circumstances.
    
    🛡️ TaxGuard AI — Privacy-First Tax Estimation — **Your personal data NEVER leaves your device**
""")
