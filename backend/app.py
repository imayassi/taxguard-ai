"""
TaxGuard AI - Professional Streamlit Application
=================================================
A privacy-first tax estimation app with TurboTax-inspired design.

Features:
- Multiple income source tracking (spouse, multiple jobs, 1099s)
- Real-time refund/owed calculation
- What-if simulations
- AI-powered recommendations
- PII protection (privacy air gap)

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import time

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
from advanced_strategies import get_all_strategies, StrategyCategory


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
    
    /* Secondary Button */
    .secondary-btn > button {
        background: transparent !important;
        color: var(--primary-blue) !important;
        border: 2px solid var(--primary-blue) !important;
    }
    
    .secondary-btn > button:hover {
        background: var(--primary-blue-light) !important;
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
    
    /* Expander */
    .streamlit-expanderHeader {
        background: var(--bg-card);
        border-radius: 8px;
        border: 1px solid var(--border-light);
        font-weight: 600;
    }
    
    /* Recommendation Cards */
    .rec-card {
        background: var(--bg-card);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
        border-left: 4px solid var(--primary-blue);
        box-shadow: var(--shadow-sm);
    }
    
    .rec-card.high-priority {
        border-left-color: var(--warning-red);
    }
    
    .rec-card.medium-priority {
        border-left-color: #F5A623;
    }
    
    .rec-card.low-priority {
        border-left-color: var(--accent-green);
    }
    
    .rec-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-dark);
        margin-bottom: 8px;
    }
    
    .rec-savings {
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--accent-green);
    }
    
    /* Divider */
    hr {
        border: none;
        height: 1px;
        background: var(--border-light);
        margin: 24px 0;
    }
    
    /* Income Source Card */
    .income-source {
        background: var(--bg-card);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
        border: 1px solid var(--border-light);
        position: relative;
    }
    
    .income-source-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    
    .source-type-badge {
        background: var(--primary-blue-light);
        color: var(--primary-blue);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    /* Header Banner */
    .header-banner {
        background: linear-gradient(135deg, var(--primary-blue) 0%, var(--secondary-blue) 100%);
        padding: 24px 32px;
        border-radius: 16px;
        color: white;
        margin-bottom: 24px;
    }
    
    .header-title {
        font-size: 1.75rem;
        font-weight: 700;
        margin-bottom: 8px;
    }
    
    .header-subtitle {
        font-size: 1rem;
        opacity: 0.9;
    }
    
    /* Stats Row */
    .stats-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    
    /* Animation */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .animate-fade-in {
        animation: fadeIn 0.4s ease-out;
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
    
    /* Toast/Alert */
    .success-toast {
        background: var(--accent-green-light);
        border: 1px solid var(--accent-green);
        color: var(--accent-green);
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
    
    st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 0 0 20px 0;'>", unsafe_allow_html=True)
    
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
            <span>Your data never leaves your device</span>
        </div>
    """, unsafe_allow_html=True)


# =============================================================================
# MAIN CONTENT AREA
# =============================================================================

# Header
st.markdown("""
    <div class="header-banner animate-fade-in">
        <div class="header-title">Federal Tax Estimation 2025</div>
        <div class="header-subtitle">Get an accurate estimate of your federal taxes with our smart calculator</div>
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
                <div style="color: var(--text-light); font-size: 0.9rem;">
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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Summary", 
    "💼 Income", 
    "🔮 What-If", 
    "💡 Recommendations",
    "🔒 Privacy"
])


# =============================================================================
# TAB 1: SUMMARY
# =============================================================================

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
            <div class="tax-card">
                <div class="tax-card-header">📈 Income Breakdown</div>
            </div>
        """, unsafe_allow_html=True)
        
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
        st.markdown("""
            <div class="tax-card">
                <div class="tax-card-header">💰 Tax Breakdown</div>
            </div>
        """, unsafe_allow_html=True)
        
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
    st.markdown("""
        <div class="tax-card">
            <div class="tax-card-header">💼 Income Sources</div>
            <p style="color: var(--text-light); margin-bottom: 20px;">
                Add all income sources for yourself and your spouse (if married filing jointly)
            </p>
        </div>
    """, unsafe_allow_html=True)
    
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
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
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
    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    
    all_sources = list(st.session_state.enhanced_profile.income_sources)
    if st.session_state.enhanced_profile.spouse:
        all_sources.extend(st.session_state.enhanced_profile.spouse.sources)
    
    if all_sources:
        st.markdown(f"**{len(all_sources)} Income Source(s)**")
        
        for i, source in enumerate(all_sources):
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                badge_text = source.source_type.value.replace("_", " ").upper()
                st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="source-type-badge">{badge_text}</span>
                        <span style="font-weight: 500;">{source.name}</span>
                    </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"**YTD:** {fmt_currency(source.ytd_gross)}")
            
            with col3:
                st.markdown(f"**Withheld:** {fmt_currency(source.ytd_federal_withheld)}")
            
            with col4:
                st.markdown(f"**Projected:** {fmt_currency(source.projected_annual_income)}")
            
            st.markdown("<hr style='margin: 8px 0; opacity: 0.3;'>", unsafe_allow_html=True)
        
        # Totals
        total_ytd = sum(s.ytd_gross for s in all_sources)
        total_withheld = sum(s.ytd_federal_withheld for s in all_sources)
        total_projected = sum(s.projected_annual_income for s in all_sources)
        
        st.markdown(f"""
            <div style="background: var(--primary-blue-light); padding: 16px; border-radius: 8px; margin-top: 16px;">
                <div style="display: flex; justify-content: space-between;">
                    <div><strong>Total YTD Income:</strong> {fmt_currency(total_ytd)}</div>
                    <div><strong>Total Withheld:</strong> {fmt_currency(total_withheld)}</div>
                    <div><strong>Projected Annual:</strong> {fmt_currency(total_projected)}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("👆 Add your first income source above to get started!")


# =============================================================================
# TAB 3: WHAT-IF SIMULATOR
# =============================================================================

with tab3:
    st.markdown("""
        <div class="tax-card">
            <div class="tax-card-header">🔮 What-If Tax Simulator</div>
            <p style="color: var(--text-light);">
                See how different scenarios could affect your tax outcome
            </p>
        </div>
    """, unsafe_allow_html=True)
    
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
    
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Custom Simulation
    st.markdown("**Custom Simulation**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        add_401k = st.number_input(
            f"Additional 401(k) (Room: {fmt_currency(profile.remaining_401k_room)})",
            min_value=0.0,
            max_value=float(profile.remaining_401k_room),
            value=0.0,
            step=500.0,
            key="custom_401k"
        )
    
    with col2:
        add_hsa = st.number_input(
            f"Additional HSA (Room: {fmt_currency(profile.remaining_hsa_room)})",
            min_value=0.0,
            max_value=float(profile.remaining_hsa_room),
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
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("**Simulation Results**")
    
    if st.session_state.simulations:
        for i, sim in enumerate(st.session_state.simulations[:5]):
            is_beneficial = sim.is_beneficial
            savings = abs(sim.tax_difference)
            
            icon = "✅" if is_beneficial else "⚠️"
            color = "var(--accent-green)" if is_beneficial else "var(--warning-red)"
            
            st.markdown(f"""
                <div class="rec-card {'low-priority' if is_beneficial else 'high-priority'}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div class="rec-title">{icon} {sim.scenario_name}</div>
                            <div style="color: var(--text-light); font-size: 0.9rem;">
                                {sim.summary}
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 0.85rem; color: var(--text-light);">
                                {'Tax Savings' if is_beneficial else 'Tax Increase'}
                            </div>
                            <div class="rec-savings" style="color: {color};">
                                {fmt_currency(savings)}
                            </div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Run a simulation to see results here")


# =============================================================================
# TAB 4: RECOMMENDATIONS
# =============================================================================

with tab4:
    recs = st.session_state.recommendations
    
    if recs:
        # Summary Banner
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, var(--accent-green) 0%, #0A8F5C 100%); 
                        color: white; padding: 24px; border-radius: 12px; margin-bottom: 24px;">
                <div style="font-size: 0.9rem; opacity: 0.9; margin-bottom: 8px;">
                    Maximum Potential Tax Savings
                </div>
                <div style="font-size: 2.5rem; font-weight: 700;">
                    {fmt_currency(recs.max_potential_savings)}
                </div>
                <div style="font-size: 0.9rem; opacity: 0.9; margin-top: 8px;">
                    {recs.days_until_year_end} days left to take action this year
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Basic Recommendations
        st.markdown("### 🎯 Basic Recommendations")
        st.markdown("*Actions anyone can take*")
        
        for rec in recs.basic_recommendations:
            priority_class = {
                "critical": "high-priority",
                "high": "high-priority", 
                "medium": "medium-priority",
                "low": "low-priority"
            }.get(rec.priority.value, "")
            
            with st.expander(f"{'🔴' if rec.priority.value in ['critical', 'high'] else '🟡' if rec.priority.value == 'medium' else '🟢'} {rec.title} — Save {fmt_currency(rec.potential_tax_savings)}"):
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
            st.markdown("<hr>", unsafe_allow_html=True)
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
# TAB 5: PRIVACY DEMO
# =============================================================================

with tab5:
    st.markdown("""
        <div class="tax-card">
            <div class="tax-card-header">🔒 PII Protection Demo</div>
            <p style="color: var(--text-light);">
                TaxGuard AI uses a "Privacy Air Gap" to ensure your personal information 
                never reaches external AI services.
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # How it works
    st.markdown("""
        ### How It Works
        
        1. **Upload** - You upload your paystub or tax document
        2. **Redact** - Our system automatically detects and removes all PII
        3. **Analyze** - Only anonymized financial data is processed
        4. **Calculate** - Tax calculations happen 100% locally in Python
    """)
    
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Live Demo
    st.markdown("### Try It Yourself")
    
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
        
        if st.button("🔍 Redact PII", type="primary", key="redact_btn"):
            redactor = PIIRedactor(use_ner=False)
            result = redactor.redact_sensitive_data(input_text)
            
            st.text_area(
                "Output",
                value=result.redacted_text,
                height=350,
                disabled=True,
                label_visibility="collapsed",
                key="privacy_output"
            )
            
            st.markdown(f"""
                <div class="success-toast">
                    ✅ Redacted {result.redaction_count} PII items in {result.processing_time_ms:.1f}ms
                </div>
            """, unsafe_allow_html=True)
            
            if result.pii_types_found:
                st.markdown("**PII Types Detected:**")
                for pii_type in result.pii_types_found:
                    st.markdown(f"- {pii_type}")
        else:
            st.text_area(
                "Output",
                value="Click 'Redact PII' to see the result...",
                height=350,
                disabled=True,
                label_visibility="collapsed",
                key="privacy_placeholder"
            )
    
    # Security Features
    st.markdown("<hr>", unsafe_allow_html=True)
    
    st.markdown("### 🔐 Security Features")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
            **SSN Detection**
            
            Catches multiple formats:
            - 123-45-6789
            - 123 45 6789
            - 9-digit sequences
        """)
    
    with col2:
        st.markdown("""
            **Contact Info**
            
            Removes:
            - Email addresses
            - Phone numbers
            - Physical addresses
        """)
    
    with col3:
        st.markdown("""
            **Financial Data**
            
            Preserves:
            - Dollar amounts
            - Tax figures
            - YTD totals
        """)


# =============================================================================
# FOOTER
# =============================================================================

st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""
    <div style="text-align: center; color: var(--text-light); font-size: 0.85rem; padding: 20px;">
        <p>
            <strong>⚠️ Disclaimer:</strong> TaxGuard AI provides estimates only and is not a substitute for professional tax advice.
            Calculations are based on 2025 federal tax rules and may not account for all deductions, credits, or individual circumstances.
        </p>
        <p style="margin-top: 12px;">
            🛡️ TaxGuard AI — Privacy-First Tax Estimation — Your data never leaves your device
        </p>
    </div>
""", unsafe_allow_html=True)
