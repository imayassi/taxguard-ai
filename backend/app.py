"""
TaxGuard AI v2 - Streamlined Tax Gap Calculator
================================================
A privacy-first tax estimation app with clean, minimal UX.

Flow:
1. Upload Forms → AI Extraction (GPT-5.1)
2. Tax Gap Analysis (Withholding vs True Liability)
3. Fix It Strategies (Top 10 ranked by impact)
4. What-If Scenarios (free-text life changes)
"""

import sys
import os

# Path setup for Streamlit Cloud
_current_file = os.path.abspath(__file__)
_backend_dir = os.path.dirname(_current_file)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import time
import json
import re

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

# Optional imports
try:
    from advanced_strategies import get_all_advanced_strategies, StrategyCategory
    ADVANCED_STRATEGIES_AVAILABLE = True
except ImportError:
    ADVANCED_STRATEGIES_AVAILABLE = False
    get_all_advanced_strategies = None

try:
    from openai_client import (
        TaxAIClient, get_ai_client, create_anonymized_profile, 
        create_anonymized_tax_result, AIProvider
    )
    OPENAI_CLIENT_AVAILABLE = True
except ImportError:
    OPENAI_CLIENT_AVAILABLE = False
    
    class AIProvider:
        MOCK = "mock"
        OPENAI = "openai"
    
    class MockAIClient:
        is_connected = False
        model = "mock"
        client = None
        def generate_strategies(self, **kwargs):
            from dataclasses import dataclass
            @dataclass
            class MockResponse:
                content: str = "AI features require OpenAI API key."
                success: bool = True
                tokens_used: int = 0
            return MockResponse()
    
    def get_ai_client():
        if 'ai_client' not in st.session_state:
            st.session_state.ai_client = MockAIClient()
        return st.session_state.ai_client
    
    def create_anonymized_profile(profile, num_income_sources=1):
        return {"filing_status": str(profile.filing_status)}
    
    def create_anonymized_tax_result(result):
        return {"gross_income": result.gross_income}


# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="TaxGuard AI - Smart Tax Gap Calculator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =============================================================================
# CUSTOM CSS - CLEAN MINIMAL DESIGN
# =============================================================================

st.markdown("""
<style>
    /* Clean, minimal styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* Header styling */
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
    }
    
    .main-header h1 {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    
    .main-header p {
        opacity: 0.9;
        font-size: 1.1rem;
    }
    
    /* Upload area styling */
    .upload-zone {
        border: 2px dashed #14A66B;
        border-radius: 16px;
        padding: 3rem;
        text-align: center;
        background: #f8fffe;
        margin: 2rem 0;
    }
    
    .upload-zone h2 {
        color: #14A66B;
        margin-bottom: 1rem;
    }
    
    /* Tax gap display */
    .tax-gap-positive {
        background: linear-gradient(135deg, #14A66B 0%, #0D8050 100%);
        color: white;
        padding: 2rem;
        border-radius: 16px;
        text-align: center;
    }
    
    .tax-gap-negative {
        background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
        color: white;
        padding: 2rem;
        border-radius: 16px;
        text-align: center;
    }
    
    .tax-gap-amount {
        font-size: 3rem;
        font-weight: bold;
        margin: 1rem 0;
    }
    
    /* Strategy cards */
    .strategy-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    .strategy-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    }
    
    .strategy-rank {
        background: #14A66B;
        color: white;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        margin-right: 12px;
    }
    
    .strategy-savings {
        color: #14A66B;
        font-size: 1.25rem;
        font-weight: bold;
    }
    
    /* Privacy notice */
    .privacy-notice {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .privacy-notice .icon {
        font-size: 1.5rem;
    }
    
    /* Collapsible sections */
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
    
    /* Progress steps */
    .step-indicator {
        display: flex;
        justify-content: center;
        gap: 2rem;
        margin: 2rem 0;
    }
    
    .step {
        display: flex;
        flex-direction: column;
        align-items: center;
        opacity: 0.5;
    }
    
    .step.active {
        opacity: 1;
    }
    
    .step.completed {
        opacity: 1;
    }
    
    .step-number {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #e0e0e0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        margin-bottom: 8px;
    }
    
    .step.active .step-number,
    .step.completed .step-number {
        background: #14A66B;
        color: white;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Extracted data display */
    .extracted-data {
        background: #f0f9f4;
        border: 1px solid #14A66B;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .extracted-item {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 1px solid #e0e0e0;
    }
    
    .extracted-item:last-child {
        border-bottom: none;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """Initialize all session state variables."""
    if 'step' not in st.session_state:
        st.session_state.step = 1  # 1=Upload, 2=Review, 3=Results
    
    if 'extracted_data' not in st.session_state:
        st.session_state.extracted_data = None
    
    if 'income_sources' not in st.session_state:
        st.session_state.income_sources = []
    
    if 'deductions' not in st.session_state:
        st.session_state.deductions = {
            'mortgage_interest': 0,
            'property_taxes': 0,
            'state_local_taxes': 0,
            'charitable': 0,
            'medical': 0,
            'other': 0,
            'rental_income': 0,
            'rental_mortgage_interest': 0,
            'rental_property_taxes': 0,
            'rental_expenses': 0,
            'business_expenses': 0,
            'student_loan_interest': 0,
            'user_notes': ''
        }
    
    if 'filing_status' not in st.session_state:
        st.session_state.filing_status = FilingStatus.SINGLE
    
    if 'tax_result' not in st.session_state:
        st.session_state.tax_result = None
    
    if 'tax_gap' not in st.session_state:
        st.session_state.tax_gap = None
    
    if 'strategies' not in st.session_state:
        st.session_state.strategies = None
    
    if 'last_year_data' not in st.session_state:
        st.session_state.last_year_data = None

init_session_state()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def fmt_currency(amount: float) -> str:
    """Format number as currency."""
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def calculate_projected_withholding(sources: List[Dict]) -> float:
    """Calculate projected year-end withholding from all sources."""
    total_withheld = 0
    for src in sources:
        # Use abs() to handle negative values from extraction
        ytd_withheld = abs(src.get('ytd_federal_withheld', 0) or 0)
        current_period = src.get('current_pay_period', 24) or 24
        pay_freq = src.get('pay_frequency', 'biweekly') or 'biweekly'
        
        periods_per_year = {
            'weekly': 52, 'biweekly': 26, 'semimonthly': 24, 'monthly': 12
        }.get(pay_freq, 26)
        
        if current_period > 0:
            per_period = ytd_withheld / current_period
            projected = per_period * periods_per_year
        else:
            projected = ytd_withheld
        
        total_withheld += projected
    
    return total_withheld


def calculate_true_liability(sources: List[Dict], deductions: Dict, filing_status: FilingStatus) -> Dict:
    """Calculate true tax liability with standard vs itemized comparison."""
    
    # Calculate total income (use abs to handle any negative values)
    total_income = sum(abs(src.get('projected_annual_income', src.get('ytd_gross', 0)) or 0) for src in sources)
    
    # Add any additional income like rental income
    rental_income = abs(deductions.get('rental_income', 0) or 0)
    total_income += rental_income
    
    # Standard deduction
    standard_ded = STANDARD_DEDUCTION_2025.get(filing_status, 14600)
    
    # Itemized deductions - include ALL possible fields
    mortgage_interest = abs(deductions.get('mortgage_interest', 0) or 0)
    property_taxes = abs(deductions.get('property_taxes', 0) or 0)
    state_local_taxes = abs(deductions.get('state_local_taxes', 0) or 0)
    charitable = abs(deductions.get('charitable', 0) or 0)
    medical = abs(deductions.get('medical', 0) or 0)
    other = abs(deductions.get('other', 0) or 0)
    
    # Rental property deductions (these reduce rental income, but excess can offset other income)
    rental_mortgage = abs(deductions.get('rental_mortgage_interest', 0) or 0)
    rental_property_tax = abs(deductions.get('rental_property_taxes', 0) or 0)
    rental_expenses = abs(deductions.get('rental_expenses', 0) or 0)
    
    # Business expenses (Schedule C)
    business_expenses = abs(deductions.get('business_expenses', 0) or 0)
    
    # Student loan interest (above-the-line, max $2,500)
    student_loan = min(abs(deductions.get('student_loan_interest', 0) or 0), 2500)
    
    # Calculate itemized total
    # Note: Rental expenses offset rental income, not itemized
    itemized_ded = (
        mortgage_interest +
        property_taxes +
        min(state_local_taxes, 10000) +  # SALT cap $10,000
        charitable +
        max(0, medical - total_income * 0.075) +  # 7.5% AGI floor for medical
        other
    )
    
    # Rental property deductions offset rental income
    net_rental_income = max(0, rental_income - rental_mortgage - rental_property_tax - rental_expenses)
    
    # Adjust total income for net rental
    adjusted_income = total_income - rental_income + net_rental_income - student_loan - business_expenses
    adjusted_income = max(0, adjusted_income)
    
    # Choose better deduction
    use_itemized = itemized_ded > standard_ded
    deduction_amount = itemized_ded if use_itemized else standard_ded
    
    # Taxable income
    taxable_income = max(0, adjusted_income - deduction_amount)
    
    # Calculate federal tax using brackets
    brackets = TAX_BRACKETS_2025.get(filing_status, TAX_BRACKETS_2025[FilingStatus.SINGLE])
    federal_tax = 0
    remaining = taxable_income
    
    for i, (threshold, rate) in enumerate(brackets):
        if i == 0:
            prev_threshold = 0
        else:
            prev_threshold = brackets[i-1][0]
        
        bracket_income = min(remaining, threshold - prev_threshold) if threshold else remaining
        federal_tax += bracket_income * rate
        remaining -= bracket_income
        
        if remaining <= 0:
            break
    
    # Get marginal rate
    marginal_rate = 0.10
    for threshold, rate in brackets:
        if threshold is None or taxable_income <= threshold:
            marginal_rate = rate
            break
    
    effective_rate = (federal_tax / total_income * 100) if total_income > 0 else 0
    
    return {
        'gross_income': total_income,
        'adjusted_gross_income': adjusted_income,
        'deduction_type': 'itemized' if use_itemized else 'standard',
        'deduction_amount': deduction_amount,
        'standard_deduction': standard_ded,
        'itemized_deduction': itemized_ded,
        'taxable_income': taxable_income,
        'federal_tax': federal_tax,
        'effective_rate': effective_rate,
        'marginal_rate': marginal_rate,
        'rental_income': rental_income,
        'net_rental_income': net_rental_income,
    }


def extract_with_ai(text: str, doc_type: str) -> Dict:
    """Use GPT-5.1 to extract financial data from document text."""
    ai_client = get_ai_client()
    
    if not ai_client.is_connected or not ai_client.client:
        return None
    
    extraction_prompt = f"""Analyze this {doc_type} document and extract ALL financial information.
The document has had personal information (SSN, names, addresses) removed for privacy.

DOCUMENT TEXT:
{text}

IMPORTANT EXTRACTION RULES:
1. For YTD values, look for "Year to Date", "YTD", "Y-T-D" totals
2. For TOTAL EARNINGS, include: base salary + bonuses + RSUs + stock compensation + commissions + overtime
3. Federal tax withheld should be a POSITIVE number (even if shown as negative on paystub)
4. Pay attention to "Total Gross" or "Gross Earnings" which includes ALL compensation types
5. Look for "Stock", "RSU", "Equity", "Bonus" line items and ADD them to gross

Extract and return in JSON format with POSITIVE numbers:
{{
    "document_type": "{doc_type}",
    "employer_name": "<string or null>",
    "current_gross_pay": <number - THIS PERIOD total including stocks/bonuses>,
    "current_federal_withheld": <POSITIVE number>,
    "current_state_withheld": <number or null>,
    "current_social_security": <number or null>,
    "current_medicare": <number or null>,
    "current_401k": <number or null>,
    "current_net_pay": <number or null>,
    "ytd_gross": <number - YEAR TO DATE total earnings including ALL compensation>,
    "ytd_federal_withheld": <POSITIVE number - total federal tax withheld YTD>,
    "ytd_state_withheld": <number or null>,
    "ytd_social_security": <number or null>,
    "ytd_medicare": <number or null>,
    "ytd_401k": <number or null>,
    "ytd_stock_compensation": <number - RSUs, stock awards, equity if listed separately>,
    "ytd_bonus": <number - bonuses if listed separately>,
    "pay_frequency": "<weekly/biweekly/semimonthly/monthly or null>",
    "pay_period_number": <number or null>,
    "pay_date": "<date string or null>",
    "notes": "<any important observations about the data>"
}}

CRITICAL: All tax withheld values must be POSITIVE. If ytd_gross seems low, check if stock/RSU/bonus is listed separately and ADD it.
Return ONLY valid JSON."""

    try:
        response = ai_client.client.chat.completions.create(
            model=ai_client.model,
            messages=[
                {"role": "system", "content": "You are an expert payroll document parser. Extract ALL compensation including stocks, RSUs, bonuses. Return POSITIVE numbers for taxes withheld."},
                {"role": "user", "content": extraction_prompt}
            ]
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Clean response
        if "```json" in ai_response:
            ai_response = ai_response.split("```json")[1].split("```")[0]
        elif "```" in ai_response:
            ai_response = ai_response.split("```")[1].split("```")[0]
        
        data = json.loads(ai_response)
        
        # Ensure key financial values are positive
        for key in ['ytd_federal_withheld', 'current_federal_withheld', 'ytd_gross', 'current_gross_pay']:
            if key in data and data[key] is not None:
                data[key] = abs(data[key])
        
        # Add stock/bonus to gross if they were extracted separately
        if data.get('ytd_stock_compensation') and data.get('ytd_gross'):
            # Check if stock wasn't already included (simple heuristic)
            stock = abs(data['ytd_stock_compensation'])
            if stock > 1000:  # Significant stock compensation
                data['ytd_gross_base'] = data['ytd_gross']
                data['notes'] = data.get('notes', '') + f" Stock/RSU of ${stock:,.0f} detected."
        
        return data
    except Exception as e:
        st.error(f"AI extraction error: {e}")
        return None


def generate_top_strategies(tax_result: Dict, gap: float, filing_status: FilingStatus) -> List[Dict]:
    """Generate top 10 tax strategies ranked by impact using GPT-5.1."""
    ai_client = get_ai_client()
    
    if not ai_client.is_connected or not ai_client.client:
        # Return mock strategies
        return get_mock_strategies(tax_result, gap)
    
    prompt = f"""Based on this tax situation, provide the TOP 10 tax reduction strategies ranked by HIGHEST IMPACT first.

TAX SITUATION:
- Gross Income: ${tax_result.get('gross_income', 0):,.2f}
- Taxable Income: ${tax_result.get('taxable_income', 0):,.2f}
- Federal Tax Liability: ${tax_result.get('federal_tax', 0):,.2f}
- Current Tax Gap: ${gap:,.2f} ({'owes money' if gap < 0 else 'refund expected'})
- Marginal Rate: {tax_result.get('marginal_rate', 0.22) * 100:.0f}%
- Filing Status: {filing_status.value}
- Deduction Type: {tax_result.get('deduction_type', 'standard')}

Return exactly 10 strategies as JSON array:
[
    {{
        "rank": 1,
        "strategy": "Strategy Name",
        "description": "Brief description of how to implement",
        "estimated_savings": <dollar amount>,
        "difficulty": "easy/medium/hard",
        "deadline": "deadline if applicable or null"
    }},
    ...
]

Strategies should be SPECIFIC and ACTIONABLE with realistic savings estimates.
Consider: retirement contributions, HSA, business deductions, credits, timing strategies, deduction optimization.
Return ONLY the JSON array."""

    try:
        response = ai_client.client.chat.completions.create(
            model=ai_client.model,
            messages=[
                {"role": "system", "content": "You are an expert tax strategist. Provide specific, actionable strategies with accurate savings estimates."},
                {"role": "user", "content": prompt}
            ]
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        if "```json" in ai_response:
            ai_response = ai_response.split("```json")[1].split("```")[0]
        elif "```" in ai_response:
            ai_response = ai_response.split("```")[1].split("```")[0]
        
        strategies = json.loads(ai_response)
        return strategies[:10]  # Ensure max 10
    except Exception as e:
        st.warning(f"Using fallback strategies: {e}")
        return get_mock_strategies(tax_result, gap)


def get_mock_strategies(tax_result: Dict, gap: float) -> List[Dict]:
    """Return mock strategies when AI is unavailable."""
    marginal = tax_result.get('marginal_rate', 0.22)
    
    return [
        {"rank": 1, "strategy": "Maximize 401(k) Contributions", "description": f"Contribute up to ${CONTRIBUTION_LIMITS_2025['401k']:,} to reduce taxable income", "estimated_savings": CONTRIBUTION_LIMITS_2025['401k'] * marginal, "difficulty": "easy", "deadline": "Dec 31"},
        {"rank": 2, "strategy": "Open/Max HSA Account", "description": f"Health Savings Account contributions up to ${CONTRIBUTION_LIMITS_2025['hsa_family']:,} (family)", "estimated_savings": CONTRIBUTION_LIMITS_2025['hsa_family'] * marginal, "difficulty": "easy", "deadline": "Apr 15"},
        {"rank": 3, "strategy": "Traditional IRA Contribution", "description": f"Contribute up to ${CONTRIBUTION_LIMITS_2025['ira']:,} if eligible", "estimated_savings": CONTRIBUTION_LIMITS_2025['ira'] * marginal, "difficulty": "easy", "deadline": "Apr 15"},
        {"rank": 4, "strategy": "Charitable Donations", "description": "Donate appreciated stock to avoid capital gains and get deduction", "estimated_savings": 5000 * marginal, "difficulty": "medium", "deadline": "Dec 31"},
        {"rank": 5, "strategy": "Tax-Loss Harvesting", "description": "Sell losing investments to offset gains", "estimated_savings": 3000 * marginal, "difficulty": "medium", "deadline": "Dec 31"},
        {"rank": 6, "strategy": "Bunch Deductions", "description": "Combine two years of deductions into one to exceed standard deduction", "estimated_savings": 2000, "difficulty": "medium", "deadline": None},
        {"rank": 7, "strategy": "Home Office Deduction", "description": "If self-employed, deduct home office expenses", "estimated_savings": 1500 * marginal, "difficulty": "medium", "deadline": None},
        {"rank": 8, "strategy": "Electric Vehicle Credit", "description": "Purchase qualifying EV for up to $7,500 credit", "estimated_savings": 7500, "difficulty": "hard", "deadline": None},
        {"rank": 9, "strategy": "Energy Efficiency Credits", "description": "Install solar panels, heat pumps, or insulation", "estimated_savings": 3000, "difficulty": "hard", "deadline": None},
        {"rank": 10, "strategy": "Adjust W-4 Withholding", "description": "Update withholding to better match actual liability", "estimated_savings": abs(gap) * 0.03 if gap > 0 else 0, "difficulty": "easy", "deadline": None},
    ]


def analyze_what_if(base_data: Dict, changes_text: str) -> Dict:
    """Use GPT-5.1 to analyze what-if scenarios based on free-text input."""
    ai_client = get_ai_client()
    
    if not ai_client.is_connected or not ai_client.client:
        return {"error": "AI connection required for What-If analysis"}
    
    prompt = f"""Analyze how these life changes would affect this person's tax situation.

CURRENT TAX SITUATION (baseline):
- Gross Income: ${base_data.get('gross_income', 0):,.2f}
- Federal Tax: ${base_data.get('federal_tax', 0):,.2f}
- Filing Status: {base_data.get('filing_status', 'single')}
- Deductions: ${base_data.get('deduction_amount', 0):,.2f}

USER'S PLANNED CHANGES:
{changes_text}

Analyze the tax impact and return JSON:
{{
    "interpreted_changes": [
        {{"change": "description", "tax_impact": "explanation"}}
    ],
    "new_estimated_income": <number>,
    "new_estimated_tax": <number>,
    "tax_difference": <number (positive=more tax, negative=less tax)>,
    "new_credits": [
        {{"credit": "name", "amount": <number>}}
    ],
    "recommendations": ["recommendation 1", "recommendation 2"],
    "summary": "One paragraph summary of overall impact"
}}

Be specific with dollar amounts. Return ONLY valid JSON."""

    try:
        response = ai_client.client.chat.completions.create(
            model=ai_client.model,
            messages=[
                {"role": "system", "content": "You are a tax planning expert. Analyze life changes and their tax implications precisely."},
                {"role": "user", "content": prompt}
            ]
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        if "```json" in ai_response:
            ai_response = ai_response.split("```json")[1].split("```")[0]
        elif "```" in ai_response:
            ai_response = ai_response.split("```")[1].split("```")[0]
        
        return json.loads(ai_response)
    except Exception as e:
        return {"error": str(e)}


def process_deduction_input(text: str) -> Dict:
    """Use GPT-5.1 to parse free-text deduction input."""
    ai_client = get_ai_client()
    
    if not ai_client.is_connected or not ai_client.client:
        return None
    
    prompt = f"""Parse this description of tax-related items. Carefully identify INCOME vs DEDUCTIONS.

USER INPUT:
{text}

IMPORTANT RULES:
- "Rental income" is INCOME, not a deduction
- "Mortgage interest" is a DEDUCTION
- "Property tax" is a DEDUCTION  
- "Rental property expenses/repairs/maintenance" are DEDUCTIONS against rental income
- "Donations/charitable" are DEDUCTIONS
- All values should be POSITIVE numbers

Return JSON with extracted amounts (use 0 if not mentioned):
{{
    "mortgage_interest": <number - primary home mortgage interest>,
    "property_taxes": <number - primary home property taxes>,
    "state_local_taxes": <number - state/local income or sales taxes>,
    "charitable": <number - charitable donations>,
    "medical": <number - medical expenses>,
    "student_loan_interest": <number - student loan interest paid>,
    "business_expenses": <number - self-employment/business expenses>,
    "rental_income": <number - gross rental income received>,
    "rental_mortgage_interest": <number - mortgage interest on rental property>,
    "rental_property_taxes": <number - property taxes on rental property>,
    "rental_expenses": <number - repairs, maintenance, management fees on rental>,
    "other": <number - other deductible expenses>,
    "parsed_items": [
        {{"item": "description", "amount": <number>, "category": "income/deduction"}}
    ],
    "notes": "any clarifying notes"
}}

Return ONLY valid JSON with POSITIVE numbers."""

    try:
        response = ai_client.client.chat.completions.create(
            model=ai_client.model,
            messages=[
                {"role": "system", "content": "You are a tax expert. Parse financial items accurately. Distinguish income from deductions. Return positive numbers."},
                {"role": "user", "content": prompt}
            ]
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        if "```json" in ai_response:
            ai_response = ai_response.split("```json")[1].split("```")[0]
        elif "```" in ai_response:
            ai_response = ai_response.split("```")[1].split("```")[0]
        
        parsed = json.loads(ai_response)
        
        # Ensure all values are positive
        for key in parsed:
            if isinstance(parsed[key], (int, float)) and parsed[key] < 0:
                parsed[key] = abs(parsed[key])
        
        return parsed
    except Exception as e:
        st.error(f"Parsing error: {e}")
        return None


# =============================================================================
# MAIN APP HEADER
# =============================================================================

st.markdown("""
<div class="main-header">
    <h1>🛡️ TaxGuard AI</h1>
    <p>Smart Tax Gap Calculator • Know exactly where you stand</p>
</div>
""", unsafe_allow_html=True)

# Privacy Notice (always visible)
st.markdown("""
<div class="privacy-notice">
    <span class="icon">🔒</span>
    <div>
        <strong>Privacy Protected</strong> • Your personal information (SSN, name, address) is automatically removed before any AI processing. Only anonymized financial data is analyzed.
    </div>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# NAVIGATION TABS
# =============================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📄 Upload & Extract",
    "📊 Tax Gap Analysis", 
    "🎯 Fix It - Strategies",
    "🔮 What-If Scenarios"
])


# =============================================================================
# TAB 1: UPLOAD & EXTRACT
# =============================================================================

with tab1:
    # Check AI status
    ai_client = get_ai_client()
    
    if ai_client.is_connected:
        st.success(f"🟢 **GPT-5.1 Connected** - High-accuracy extraction enabled")
    else:
        st.warning("🔴 **AI Offline** - Add `OPENAI_API_KEY` in Streamlit secrets for AI-powered extraction")
    
    st.markdown("---")
    
    # Main upload area
    st.markdown("### Step 1: Upload Your Tax Documents")
    st.markdown("Upload your paystubs, W-2s, or 1099s. Our AI will extract all the important numbers automatically.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        doc_type = st.selectbox(
            "Document Type",
            ["Pay Stub", "W-2", "1099-NEC", "1099-MISC", "1099-INT", "1099-DIV", "Prior Year 1040"],
            key="doc_type_select"
        )
        
        uploaded_file = st.file_uploader(
            "Drop your file here",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Supported: PDF, PNG, JPG",
            key="main_uploader"
        )
    
    with col2:
        st.markdown("**Supported Documents:**")
        st.markdown("""
        - ✅ Pay Stubs
        - ✅ W-2 Forms
        - ✅ 1099 Forms
        - ✅ Prior Year Returns
        """)
    
    # Process uploaded file
    if uploaded_file:
        st.markdown("---")
        
        process_btn = st.button(
            "🚀 Extract with AI" if ai_client.is_connected else "📝 Process Document",
            type="primary",
            use_container_width=True
        )
        
        if process_btn:
            with st.spinner("Processing document..."):
                # Step 1: Read and OCR
                progress = st.progress(0, "Reading document...")
                file_content = uploaded_file.read()
                
                extracted_text = ""
                try:
                    if uploaded_file.type == "application/pdf":
                        try:
                            import pdfplumber
                            import io
                            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                                for page in pdf.pages:
                                    extracted_text += page.extract_text() or ""
                        except ImportError:
                            st.error("PDF processing requires pdfplumber package")
                    else:
                        try:
                            from PIL import Image
                            import pytesseract
                            import io
                            image = Image.open(io.BytesIO(file_content))
                            extracted_text = pytesseract.image_to_string(image)
                        except ImportError:
                            st.error("Image OCR requires pytesseract package")
                except Exception as e:
                    st.error(f"Error reading document: {e}")
                
                progress.progress(30, "Removing personal information...")
                
                # Step 2: PII Redaction
                if extracted_text:
                    redactor = PIIRedactor(use_ner=False)
                    redaction_result = redactor.redact_sensitive_data(extracted_text)
                    redacted_text = redaction_result.redacted_text
                    pii_count = redaction_result.redaction_count
                    
                    if pii_count > 0:
                        st.info(f"🛡️ Removed {pii_count} personal information items before processing")
                
                progress.progress(60, "Extracting financial data with AI...")
                
                # Step 3: AI Extraction
                extracted_data = None
                if ai_client.is_connected and extracted_text:
                    extracted_data = extract_with_ai(redacted_text, doc_type)
                
                progress.progress(100, "Complete!")
                time.sleep(0.3)
                progress.empty()
                
                if extracted_data:
                    st.session_state.extracted_data = extracted_data
                    st.success("✅ Data extracted successfully!")
                else:
                    st.warning("Could not auto-extract data. Please enter manually below.")
        
        # Show extracted data
        if st.session_state.extracted_data:
            st.markdown("### 📊 Extracted Data")
            
            data = st.session_state.extracted_data
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Current Period:**")
                st.markdown(f"- Gross Pay: **{fmt_currency(data.get('current_gross_pay', 0) or 0)}**")
                st.markdown(f"- Federal Withheld: **{fmt_currency(data.get('current_federal_withheld', 0) or 0)}**")
                st.markdown(f"- 401(k): **{fmt_currency(data.get('current_401k', 0) or 0)}**")
            
            with col2:
                st.markdown("**Year-to-Date:**")
                st.markdown(f"- YTD Gross: **{fmt_currency(data.get('ytd_gross', 0) or 0)}**")
                st.markdown(f"- YTD Federal Withheld: **{fmt_currency(data.get('ytd_federal_withheld', 0) or 0)}**")
                st.markdown(f"- YTD 401(k): **{fmt_currency(data.get('ytd_401k', 0) or 0)}**")
            
            # Add to sources button
            if st.button("➕ Add This Income Source", type="primary"):
                pay_freq = data.get('pay_frequency', 'biweekly') or 'biweekly'
                periods = {'weekly': 52, 'biweekly': 26, 'semimonthly': 24, 'monthly': 12}.get(pay_freq, 26)
                current_period = data.get('pay_period_number', 24) or 24
                ytd_gross = data.get('ytd_gross', 0) or 0
                
                new_source = {
                    'name': data.get('employer_name', f'Source {len(st.session_state.income_sources) + 1}') or f'Source {len(st.session_state.income_sources) + 1}',
                    'doc_type': doc_type,
                    'ytd_gross': ytd_gross,
                    'ytd_federal_withheld': data.get('ytd_federal_withheld', 0) or 0,
                    'ytd_401k': data.get('ytd_401k', 0) or 0,
                    'pay_frequency': pay_freq,
                    'current_pay_period': current_period,
                    'periods_per_year': periods,
                    'projected_annual_income': (ytd_gross / current_period * periods) if current_period > 0 else ytd_gross
                }
                
                st.session_state.income_sources.append(new_source)
                st.session_state.extracted_data = None
                st.success(f"✅ Added! You now have {len(st.session_state.income_sources)} income source(s).")
                st.rerun()
    
    # Show current income sources
    if st.session_state.income_sources:
        st.markdown("---")
        st.markdown("### 📋 Your Income Sources")
        
        total_income = sum(s['projected_annual_income'] for s in st.session_state.income_sources)
        total_withheld = sum(s['ytd_federal_withheld'] for s in st.session_state.income_sources)
        
        for i, src in enumerate(st.session_state.income_sources):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.markdown(f"**{i+1}. {src['name']}** ({src['doc_type']})")
            with col2:
                st.markdown(f"Projected: {fmt_currency(src['projected_annual_income'])}")
            with col3:
                if st.button("🗑️", key=f"del_{i}"):
                    st.session_state.income_sources.pop(i)
                    st.rerun()
        
        st.markdown(f"**Total Projected Income: {fmt_currency(total_income)}**")
        st.markdown(f"**Total YTD Withheld: {fmt_currency(total_withheld)}**")
    
    # Manual entry (collapsed by default)
    st.markdown("---")
    with st.expander("📝 Manual Entry (if not uploading documents)", expanded=not bool(st.session_state.income_sources)):
        st.markdown("Enter your income information manually:")
        
        man_col1, man_col2 = st.columns(2)
        
        with man_col1:
            man_name = st.text_input("Employer/Source Name", key="man_name")
            man_ytd_gross = st.number_input("YTD Gross Income", min_value=0.0, key="man_gross")
            man_ytd_withheld = st.number_input("YTD Federal Tax Withheld", min_value=0.0, key="man_withheld")
        
        with man_col2:
            man_ytd_401k = st.number_input("YTD 401(k) Contributions", min_value=0.0, key="man_401k")
            man_pay_freq = st.selectbox("Pay Frequency", ["biweekly", "weekly", "semimonthly", "monthly"], key="man_freq")
            man_period = st.number_input("Current Pay Period #", min_value=1, max_value=52, value=24, key="man_period")
        
        if st.button("➕ Add Manual Entry", key="add_manual"):
            if man_ytd_gross > 0:
                periods = {'weekly': 52, 'biweekly': 26, 'semimonthly': 24, 'monthly': 12}.get(man_pay_freq, 26)
                
                st.session_state.income_sources.append({
                    'name': man_name or f'Source {len(st.session_state.income_sources) + 1}',
                    'doc_type': 'Manual Entry',
                    'ytd_gross': man_ytd_gross,
                    'ytd_federal_withheld': man_ytd_withheld,
                    'ytd_401k': man_ytd_401k,
                    'pay_frequency': man_pay_freq,
                    'current_pay_period': man_period,
                    'periods_per_year': periods,
                    'projected_annual_income': (man_ytd_gross / man_period * periods) if man_period > 0 else man_ytd_gross
                })
                st.success("✅ Added!")
                st.rerun()


# =============================================================================
# TAB 2: TAX GAP ANALYSIS
# =============================================================================

with tab2:
    if not st.session_state.income_sources:
        st.warning("⬅️ Please add income sources in the **Upload & Extract** tab first.")
    else:
        st.markdown("### Your Tax Gap Analysis")
        st.markdown("See if you're on track for a refund or if you'll owe money.")
        
        # Filing status
        col1, col2 = st.columns([1, 2])
        with col1:
            filing_status = st.selectbox(
                "Filing Status",
                options=[fs for fs in FilingStatus],
                format_func=lambda x: x.value.replace('_', ' ').title(),
                key="filing_status_select"
            )
            st.session_state.filing_status = filing_status
        
        st.markdown("---")
        
        # Deductions Section
        st.markdown("### Step 1: Your Deductions")
        st.markdown("*Our AI will determine if Standard or Itemized is better for you*")
        
        # Free-text deduction input
        deduction_text = st.text_area(
            "Describe your deductions in plain English:",
            placeholder="Example: I paid about $15,000 in mortgage interest, $5,000 in property taxes, and donated $3,000 to charity. I also had $2,000 in medical expenses.",
            key="deduction_freetext",
            height=100
        )
        
        if deduction_text and st.button("🤖 Parse Deductions with AI", key="parse_deductions"):
            with st.spinner("Parsing your deductions..."):
                parsed = process_deduction_input(deduction_text)
                if parsed:
                    st.session_state.deductions.update(parsed)
                    st.session_state.show_parsed = True
                    st.success("✅ Deductions parsed! Review below:")
                    st.rerun()
        
        # Show parsed deductions if just parsed
        if st.session_state.deductions.get('parsed_items') or any(v > 0 for k, v in st.session_state.deductions.items() if isinstance(v, (int, float))):
            with st.expander("📋 **Parsed Deductions (click to review)**", expanded=True):
                st.markdown("**What we found:**")
                
                # Show itemized breakdown
                ded = st.session_state.deductions
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Personal Deductions:**")
                    if ded.get('mortgage_interest', 0) > 0:
                        st.markdown(f"- Mortgage Interest: **{fmt_currency(ded['mortgage_interest'])}**")
                    if ded.get('property_taxes', 0) > 0:
                        st.markdown(f"- Property Taxes: **{fmt_currency(ded['property_taxes'])}**")
                    if ded.get('state_local_taxes', 0) > 0:
                        st.markdown(f"- State/Local Taxes: **{fmt_currency(ded['state_local_taxes'])}**")
                    if ded.get('charitable', 0) > 0:
                        st.markdown(f"- Charitable Donations: **{fmt_currency(ded['charitable'])}**")
                    if ded.get('medical', 0) > 0:
                        st.markdown(f"- Medical Expenses: **{fmt_currency(ded['medical'])}**")
                
                with col2:
                    st.markdown("**Rental/Business:**")
                    if ded.get('rental_income', 0) > 0:
                        st.markdown(f"- Rental Income: **{fmt_currency(ded['rental_income'])}** *(taxable)*")
                    if ded.get('rental_mortgage_interest', 0) > 0:
                        st.markdown(f"- Rental Mortgage: **{fmt_currency(ded['rental_mortgage_interest'])}**")
                    if ded.get('rental_property_taxes', 0) > 0:
                        st.markdown(f"- Rental Property Tax: **{fmt_currency(ded['rental_property_taxes'])}**")
                    if ded.get('rental_expenses', 0) > 0:
                        st.markdown(f"- Rental Expenses: **{fmt_currency(ded['rental_expenses'])}**")
                    if ded.get('business_expenses', 0) > 0:
                        st.markdown(f"- Business Expenses: **{fmt_currency(ded['business_expenses'])}**")
                
                # Calculate totals
                total_itemized = (
                    ded.get('mortgage_interest', 0) +
                    ded.get('property_taxes', 0) +
                    min(ded.get('state_local_taxes', 0), 10000) +
                    ded.get('charitable', 0) +
                    ded.get('medical', 0)
                )
                
                total_rental_deductions = (
                    ded.get('rental_mortgage_interest', 0) +
                    ded.get('rental_property_taxes', 0) +
                    ded.get('rental_expenses', 0)
                )
                
                st.markdown("---")
                st.markdown(f"**📊 Total Itemized Deductions: {fmt_currency(total_itemized)}**")
                if total_rental_deductions > 0:
                    st.markdown(f"**🏠 Rental Property Deductions: {fmt_currency(total_rental_deductions)}** *(offsets rental income)*")
                
                # Compare to standard
                std_ded = STANDARD_DEDUCTION_2025.get(st.session_state.filing_status, 14600)
                if total_itemized > std_ded:
                    st.success(f"✅ Itemizing saves you **{fmt_currency(total_itemized - std_ded)}** vs Standard Deduction!")
                else:
                    st.info(f"📋 Standard Deduction ({fmt_currency(std_ded)}) is still better for you")
                
                if ded.get('notes'):
                    st.caption(f"Note: {ded['notes']}")
        
        # Manual deduction fields (collapsed)
        with st.expander("📝 Or enter deductions manually"):
            st.markdown("**Personal Deductions:**")
            ded_col1, ded_col2 = st.columns(2)
            
            with ded_col1:
                st.session_state.deductions['mortgage_interest'] = st.number_input(
                    "Mortgage Interest", value=float(st.session_state.deductions.get('mortgage_interest', 0) or 0), key="ded_mortgage"
                )
                st.session_state.deductions['property_taxes'] = st.number_input(
                    "Property Taxes", value=float(st.session_state.deductions.get('property_taxes', 0) or 0), key="ded_property"
                )
                st.session_state.deductions['state_local_taxes'] = st.number_input(
                    "State/Local Taxes (max $10k)", value=float(st.session_state.deductions.get('state_local_taxes', 0) or 0), key="ded_salt"
                )
            
            with ded_col2:
                st.session_state.deductions['charitable'] = st.number_input(
                    "Charitable Donations", value=float(st.session_state.deductions.get('charitable', 0) or 0), key="ded_charity"
                )
                st.session_state.deductions['medical'] = st.number_input(
                    "Medical Expenses", value=float(st.session_state.deductions.get('medical', 0) or 0), key="ded_medical"
                )
                st.session_state.deductions['other'] = st.number_input(
                    "Other Deductions", value=float(st.session_state.deductions.get('other', 0) or 0), key="ded_other"
                )
            
            st.markdown("---")
            st.markdown("**Rental Property (if applicable):**")
            rent_col1, rent_col2 = st.columns(2)
            
            with rent_col1:
                st.session_state.deductions['rental_income'] = st.number_input(
                    "Rental Income Received", value=float(st.session_state.deductions.get('rental_income', 0) or 0), key="ded_rental_income"
                )
                st.session_state.deductions['rental_mortgage_interest'] = st.number_input(
                    "Rental Property Mortgage Interest", value=float(st.session_state.deductions.get('rental_mortgage_interest', 0) or 0), key="ded_rental_mortgage"
                )
            
            with rent_col2:
                st.session_state.deductions['rental_property_taxes'] = st.number_input(
                    "Rental Property Taxes", value=float(st.session_state.deductions.get('rental_property_taxes', 0) or 0), key="ded_rental_tax"
                )
                st.session_state.deductions['rental_expenses'] = st.number_input(
                    "Rental Expenses/Repairs", value=float(st.session_state.deductions.get('rental_expenses', 0) or 0), key="ded_rental_exp"
                )
        
        st.markdown("---")
        
        # Calculate button
        if st.button("📊 Calculate My Tax Gap", type="primary", use_container_width=True, key="calc_gap"):
            with st.spinner("Calculating..."):
                # Step A: Projected withholding
                projected_withholding = calculate_projected_withholding(st.session_state.income_sources)
                
                # Step B: True liability
                tax_result = calculate_true_liability(
                    st.session_state.income_sources,
                    st.session_state.deductions,
                    st.session_state.filing_status
                )
                
                # Tax Gap
                tax_gap = projected_withholding - tax_result['federal_tax']
                
                st.session_state.tax_result = tax_result
                st.session_state.tax_gap = tax_gap
                st.session_state.projected_withholding = projected_withholding
        
        # Display results
        if st.session_state.tax_result and st.session_state.tax_gap is not None:
            st.markdown("---")
            st.markdown("### 📊 Results")
            
            tax_result = st.session_state.tax_result
            tax_gap = st.session_state.tax_gap
            projected_withholding = st.session_state.projected_withholding
            
            # Tax Gap Display
            if tax_gap >= 0:
                st.markdown(f"""
                <div class="tax-gap-positive">
                    <div>Expected Refund</div>
                    <div class="tax-gap-amount">{fmt_currency(tax_gap)}</div>
                    <div>You're on track to get money back! 🎉</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="tax-gap-negative">
                    <div>Amount You'll Owe</div>
                    <div class="tax-gap-amount">{fmt_currency(abs(tax_gap))}</div>
                    <div>Check the "Fix It" tab for strategies to reduce this ⚠️</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Breakdown
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Step A: Your Withholding**")
                st.markdown(f"- Projected Year-End Withholding: **{fmt_currency(projected_withholding)}**")
            
            with col2:
                st.markdown("**Step B: True Tax Liability**")
                st.markdown(f"- Gross Income: {fmt_currency(tax_result['gross_income'])}")
                if tax_result.get('rental_income', 0) > 0:
                    st.markdown(f"  - *(includes rental: {fmt_currency(tax_result['rental_income'])})*")
                if tax_result.get('adjusted_gross_income') and tax_result['adjusted_gross_income'] != tax_result['gross_income']:
                    st.markdown(f"- Adjusted Gross Income: {fmt_currency(tax_result['adjusted_gross_income'])}")
                st.markdown(f"- Deduction ({tax_result['deduction_type'].title()}): -{fmt_currency(tax_result['deduction_amount'])}")
                st.markdown(f"- Taxable Income: {fmt_currency(tax_result['taxable_income'])}")
                st.markdown(f"- **Federal Tax: {fmt_currency(tax_result['federal_tax'])}**")
                st.markdown(f"- Effective Rate: {tax_result['effective_rate']:.1f}%")
            
            # Deduction comparison
            st.markdown("---")
            st.markdown("**🔍 Deduction Analysis**")
            
            std = tax_result['standard_deduction']
            itemized = tax_result['itemized_deduction']
            
            if itemized > std:
                st.success(f"✅ **Itemized deductions ({fmt_currency(itemized)})** save you more than Standard ({fmt_currency(std)})")
            else:
                st.info(f"📋 **Standard deduction ({fmt_currency(std)})** is better for you (Itemized would be {fmt_currency(itemized)})")
            
            # Show calculation breakdown
            with st.expander("📊 See detailed calculation"):
                st.markdown(f"""
                **Tax Gap Calculation:**
                - Projected Withholding: {fmt_currency(projected_withholding)}
                - Minus Federal Tax Owed: {fmt_currency(tax_result['federal_tax'])}
                - **= Tax Gap: {fmt_currency(tax_gap)}**
                
                **Itemized Deduction Breakdown:**
                - Mortgage Interest: {fmt_currency(st.session_state.deductions.get('mortgage_interest', 0))}
                - Property Taxes: {fmt_currency(st.session_state.deductions.get('property_taxes', 0))}
                - State/Local (capped at $10k): {fmt_currency(min(st.session_state.deductions.get('state_local_taxes', 0), 10000))}
                - Charitable: {fmt_currency(st.session_state.deductions.get('charitable', 0))}
                - Medical (above 7.5% AGI): {fmt_currency(max(0, st.session_state.deductions.get('medical', 0) - tax_result['gross_income'] * 0.075))}
                - **Total Itemized: {fmt_currency(itemized)}**
                """)


# =============================================================================
# TAB 3: FIX IT - STRATEGIES
# =============================================================================

with tab3:
    if not st.session_state.tax_result:
        st.warning("⬅️ Please complete the **Tax Gap Analysis** first.")
    else:
        tax_gap = st.session_state.tax_gap
        tax_result = st.session_state.tax_result
        
        if tax_gap >= 0:
            st.markdown("### 🎯 Maximize Your Refund")
            st.success(f"You're expecting a **{fmt_currency(tax_gap)}** refund. Here's how to make it even bigger!")
        else:
            st.markdown("### 🎯 Reduce What You Owe")
            st.error(f"You owe **{fmt_currency(abs(tax_gap))}**. Here are strategies to reduce this:")
        
        # Generate strategies button
        if st.button("🚀 Generate Top 10 Strategies", type="primary", use_container_width=True):
            with st.spinner("AI is analyzing your situation..."):
                strategies = generate_top_strategies(
                    tax_result, 
                    tax_gap, 
                    st.session_state.filing_status
                )
                st.session_state.strategies = strategies
        
        # Display strategies
        if st.session_state.strategies:
            st.markdown("---")
            st.markdown("### Top 10 Strategies (Ranked by Impact)")
            
            for strat in st.session_state.strategies:
                rank = strat.get('rank', 0)
                savings = strat.get('estimated_savings', 0)
                difficulty = strat.get('difficulty', 'medium')
                deadline = strat.get('deadline')
                
                difficulty_emoji = {'easy': '🟢', 'medium': '🟡', 'hard': '🔴'}.get(difficulty, '🟡')
                
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    
                    with col1:
                        st.markdown(f"""
                        **#{rank} {strat.get('strategy', 'Strategy')}** {difficulty_emoji}
                        
                        {strat.get('description', '')}
                        
                        {f"⏰ Deadline: {deadline}" if deadline else ""}
                        """)
                    
                    with col2:
                        st.markdown(f"""
                        <div style="text-align: right;">
                            <div style="color: #14A66B; font-size: 1.5rem; font-weight: bold;">
                                {fmt_currency(savings)}
                            </div>
                            <div style="color: #666; font-size: 0.8rem;">potential savings</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("---")
            
            # Total potential savings
            total_savings = sum(s.get('estimated_savings', 0) for s in st.session_state.strategies)
            st.success(f"💰 **Total Potential Savings: {fmt_currency(total_savings)}**")


# =============================================================================
# TAB 4: WHAT-IF SCENARIOS
# =============================================================================

with tab4:
    st.markdown("### 🔮 What-If Tax Scenarios")
    st.markdown("Plan for the future by seeing how life changes would affect your taxes.")
    
    ai_client = get_ai_client()
    
    if not ai_client.is_connected:
        st.warning("🔴 **AI Required** - Add `OPENAI_API_KEY` to use What-If scenarios")
    else:
        # Baseline data
        if st.session_state.tax_result:
            st.markdown("**Using your current tax data as baseline:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Gross Income", fmt_currency(st.session_state.tax_result['gross_income']))
            with col2:
                st.metric("Federal Tax", fmt_currency(st.session_state.tax_result['federal_tax']))
            with col3:
                st.metric("Effective Rate", f"{st.session_state.tax_result['effective_rate']:.1f}%")
        else:
            st.info("Complete the Tax Gap Analysis first for more accurate scenarios, or describe your current situation below.")
        
        st.markdown("---")
        
        # Free-text input for life changes
        st.markdown("### Describe Your Potential Life Changes")
        st.markdown("*Enter any changes you're considering in plain English*")
        
        what_if_text = st.text_area(
            "What changes are you considering?",
            placeholder="""Examples:
• I might get a $15,000 raise next year
• We're planning to have a baby in March
• I'm thinking about buying a house for $400,000
• I might start a side business selling crafts
• I'm considering maxing out my 401(k)
• We might get married in June""",
            height=150,
            key="what_if_input"
        )
        
        if what_if_text and st.button("🔮 Analyze Impact", type="primary", use_container_width=True):
            with st.spinner("AI is analyzing your scenario..."):
                base_data = st.session_state.tax_result or {
                    'gross_income': 75000,
                    'federal_tax': 9000,
                    'filing_status': st.session_state.filing_status.value,
                    'deduction_amount': 14600
                }
                
                result = analyze_what_if(base_data, what_if_text)
                
                if 'error' in result:
                    st.error(f"Analysis error: {result['error']}")
                else:
                    st.markdown("---")
                    st.markdown("### 📊 Impact Analysis")
                    
                    # Summary
                    st.markdown(f"**Summary:** {result.get('summary', 'Analysis complete.')}")
                    
                    st.markdown("---")
                    
                    # Changes interpreted
                    st.markdown("**Changes Analyzed:**")
                    for change in result.get('interpreted_changes', []):
                        st.markdown(f"- **{change.get('change', '')}**: {change.get('tax_impact', '')}")
                    
                    st.markdown("---")
                    
                    # New projections
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        new_income = result.get('new_estimated_income', 0)
                        old_income = base_data.get('gross_income', 0)
                        st.metric(
                            "New Estimated Income",
                            fmt_currency(new_income),
                            fmt_currency(new_income - old_income)
                        )
                    
                    with col2:
                        new_tax = result.get('new_estimated_tax', 0)
                        old_tax = base_data.get('federal_tax', 0)
                        st.metric(
                            "New Federal Tax",
                            fmt_currency(new_tax),
                            fmt_currency(new_tax - old_tax)
                        )
                    
                    with col3:
                        diff = result.get('tax_difference', 0)
                        if diff > 0:
                            st.metric("Tax Impact", f"+{fmt_currency(diff)}", "More tax")
                        else:
                            st.metric("Tax Impact", fmt_currency(diff), "Less tax", delta_color="inverse")
                    
                    # New credits
                    if result.get('new_credits'):
                        st.markdown("---")
                        st.markdown("**New Tax Credits Available:**")
                        for credit in result['new_credits']:
                            st.markdown(f"- **{credit.get('credit', '')}**: {fmt_currency(credit.get('amount', 0))}")
                    
                    # Recommendations
                    if result.get('recommendations'):
                        st.markdown("---")
                        st.markdown("**💡 Recommendations:**")
                        for rec in result['recommendations']:
                            st.markdown(f"- {rec}")


# =============================================================================
# SIDEBAR - MINIMAL
# =============================================================================

with st.sidebar:
    st.markdown("### 🛡️ TaxGuard AI")
    st.markdown("---")
    
    # AI Status
    ai_client = get_ai_client()
    if ai_client.is_connected:
        st.success("🟢 GPT-5.1 Connected")
    else:
        st.error("🔴 AI Offline")
        st.caption("Add OPENAI_API_KEY in Settings")
    
    st.markdown("---")
    
    # Quick stats
    if st.session_state.income_sources:
        st.metric("Income Sources", len(st.session_state.income_sources))
        total = sum(s['projected_annual_income'] for s in st.session_state.income_sources)
        st.metric("Total Income", fmt_currency(total))
    
    if st.session_state.tax_gap is not None:
        if st.session_state.tax_gap >= 0:
            st.metric("Expected Refund", fmt_currency(st.session_state.tax_gap))
        else:
            st.metric("Amount Owed", fmt_currency(abs(st.session_state.tax_gap)))
    
    st.markdown("---")
    
    # Reset button
    if st.button("🔄 Start Over", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    st.markdown("---")
    st.caption("© 2025 TaxGuard AI")
    st.caption("Privacy-First Tax Planning")
