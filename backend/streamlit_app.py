"""
TaxGuard AI - Streamlit Frontend
=================================
Privacy-first tax estimation application.

Features:
- Multiple income sources (spouse, multiple jobs, 1099s)
- Proper YTD tracking for refund/owed calculation  
- Advanced tax strategies (business formation, Section 179, etc.)
- What-if simulations
- PII redaction demo

Run with: streamlit run streamlit_app.py
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Optional, List, Dict, Any

# Import backend modules
from tax_constants import FilingStatus, CONTRIBUTION_LIMITS_2025, PAY_PERIODS_PER_YEAR
from models import UserFinancialProfile, PayFrequency, TaxResult
from enhanced_models import (
    EnhancedUserProfile, IncomeSource, IncomeSourceType, SpouseIncome,
    InvestmentIncome, PayFrequency as EnhancedPayFrequency,
)
from pii_redaction import PIIRedactor, redact_sensitive_data
from tax_simulator import TaxCalculator, TaxSimulator, RecommendationEngine
from advanced_strategies import get_all_strategies, StrategyCategory, StrategyComplexity


# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(page_title="TaxGuard AI", page_icon="🛡️", layout="wide")


# =============================================================================
# SESSION STATE
# =============================================================================

if 'profile' not in st.session_state:
    st.session_state.profile = UserFinancialProfile()
if 'enhanced_profile' not in st.session_state:
    st.session_state.enhanced_profile = EnhancedUserProfile()
if 'tax_result' not in st.session_state:
    st.session_state.tax_result = None
if 'recommendations' not in st.session_state:
    st.session_state.recommendations = None
if 'simulations' not in st.session_state:
    st.session_state.simulations = []


# =============================================================================
# HELPERS
# =============================================================================

def fmt(amount): 
    return f"${amount:,.2f}" if amount else "-"

def sync_and_calculate():
    """Sync enhanced profile to regular profile and calculate taxes."""
    ep = st.session_state.enhanced_profile
    p = st.session_state.profile
    
    p.filing_status = ep.filing_status
    p.age = ep.age
    p.ytd_income = ep.total_ytd_w2_income
    p.ytd_federal_withheld = ep.total_ytd_federal_withheld
    p.estimated_payments_made = ep.total_estimated_payments
    p.self_employment_income = ep.total_self_employment_income
    p.interest_income = ep.investments.taxable_interest
    p.dividend_income = ep.investments.ordinary_dividends
    p.capital_gains_long = ep.investments.long_term_gains
    p.capital_gains_short = ep.investments.short_term_gains
    p.ytd_401k_traditional = ep.ytd_401k_traditional
    p.ytd_hsa = ep.ytd_hsa
    p.num_children_under_17 = ep.num_children_under_17
    
    for s in ep.income_sources:
        if s.source_type == IncomeSourceType.W2_PRIMARY:
            p.pay_frequency = PayFrequency(s.pay_frequency.value)
            p.current_pay_period = s.current_pay_period
            break
    
    calc = TaxCalculator()
    st.session_state.tax_result = calc.calculate_tax(p)
    
    engine = RecommendationEngine()
    st.session_state.recommendations = engine.generate_recommendations(p)


# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.title("🛡️ TaxGuard AI")
    st.caption("Privacy-First Tax Estimation")
    st.divider()
    
    filing = st.selectbox("Filing Status", [s.value for s in FilingStatus],
                          format_func=lambda x: x.replace("_", " ").title())
    st.session_state.enhanced_profile.filing_status = FilingStatus(filing)
    
    age = st.number_input("Your Age", 18, 100, 35)
    st.session_state.enhanced_profile.age = age
    
    if filing == "married_filing_jointly":
        spouse_age = st.number_input("Spouse Age", 18, 100, 35)
        if st.session_state.enhanced_profile.spouse:
            st.session_state.enhanced_profile.spouse.age = spouse_age
    
    children = st.number_input("Children Under 17", 0, 20, 0)
    st.session_state.enhanced_profile.num_children_under_17 = children
    
    st.divider()
    if st.button("🔄 Recalculate", use_container_width=True):
        sync_and_calculate()
        st.success("Done!")


# =============================================================================
# TABS
# =============================================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Dashboard", "📄 Income", "🔮 What-If", 
    "💡 Tips", "🚀 Advanced", "🔒 Privacy"
])

# ---- TAB 1: DASHBOARD ----
with tab1:
    st.header("Tax Dashboard")
    
    if not st.session_state.tax_result:
        sync_and_calculate()
    
    r = st.session_state.tax_result
    ep = st.session_state.enhanced_profile
    
    if r:
        # Main result
        if r.refund_or_owed >= 0:
            st.success(f"### 🎉 Projected Refund: {fmt(r.refund_or_owed)}")
        else:
            st.error(f"### ⚠️ Projected Owed: {fmt(abs(r.refund_or_owed))}")
        
        st.divider()
        
        # Key metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Projected Income", fmt(r.gross_income))
        c2.metric("Taxable Income", fmt(r.taxable_income))
        c3.metric("Total Tax", fmt(r.total_tax_liability))
        c4.metric("Withholding + Est.", fmt(r.total_payments_and_withholding))
        
        st.divider()
        
        # YTD Tracking
        st.subheader("📊 YTD Tracking")
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**Income**")
            st.write(f"• YTD W-2 Income: {fmt(ep.total_ytd_w2_income)}")
            st.write(f"• Projected Annual: {fmt(ep.total_projected_w2_income)}")
            st.write(f"• Self-Employment: {fmt(ep.total_self_employment_income)}")
        
        with c2:
            st.markdown("**Taxes Paid**")
            st.write(f"• YTD Withheld: {fmt(ep.total_ytd_federal_withheld)}")
            st.write(f"• Projected Withheld: {fmt(ep.total_projected_federal_withheld)}")
            st.write(f"• Est. Payments: {fmt(ep.total_estimated_payments)}")
        
        # Rates
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Effective Rate", f"{r.effective_rate:.1f}%")
        c2.metric("Marginal Rate", f"{r.marginal_rate*100:.0f}%")
        c3.metric("401k Room Left", fmt(st.session_state.profile.remaining_401k_room))
        c4.metric("HSA Room Left", fmt(st.session_state.profile.remaining_hsa_room))


# ---- TAB 2: INCOME SOURCES ----
with tab2:
    st.header("📄 Income Sources")
    st.caption("Add multiple income sources: your job(s), spouse, 1099s")
    
    # Show existing
    sources = st.session_state.enhanced_profile.get_all_sources_summary()
    if sources:
        df = pd.DataFrame(sources)
        for c in ['ytd_income', 'projected_annual', 'ytd_withheld', 'projected_withheld']:
            df[c] = df[c].apply(lambda x: fmt(x))
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.divider()
    st.subheader("➕ Add Income Source")
    
    types = [
        ("W-2: Primary Job", IncomeSourceType.W2_PRIMARY),
        ("W-2: Second Job", IncomeSourceType.W2_SECONDARY),
        ("W-2: Spouse Job", IncomeSourceType.W2_SPOUSE),
        ("1099-NEC: Freelance", IncomeSourceType.FORM_1099_NEC),
        ("Self-Employment", IncomeSourceType.SELF_EMPLOYMENT),
    ]
    
    stype = st.selectbox("Type", types, format_func=lambda x: x[0])
    sname = st.text_input("Name", placeholder="e.g., 'Tech Corp'")
    
    is_w2 = stype[1] in [IncomeSourceType.W2_PRIMARY, IncomeSourceType.W2_SECONDARY, IncomeSourceType.W2_SPOUSE]
    
    c1, c2 = st.columns(2)
    if is_w2:
        with c1:
            freq = st.selectbox("Pay Frequency", [p.value for p in EnhancedPayFrequency], index=1)
            period = st.number_input("Pay Period #", 1, 52, 20)
            ytd = st.number_input("YTD Gross", 0.0, step=1000.0)
        with c2:
            fed = st.number_input("YTD Federal Withheld", 0.0, step=100.0)
            state = st.number_input("YTD State Withheld", 0.0, step=100.0)
            k401 = st.number_input("YTD 401(k)", 0.0, step=500.0)
    else:
        with c1:
            est_amt = st.number_input("Est. Annual Amount", 0.0, step=1000.0)
        with c2:
            est_pay = st.number_input("Est. Tax Payments", 0.0, step=100.0)
    
    if st.button("➕ Add", type="primary"):
        src = IncomeSource(
            source_type=stype[1],
            name=sname or "Unnamed",
            pay_frequency=EnhancedPayFrequency(freq) if is_w2 else EnhancedPayFrequency.MONTHLY,
            current_pay_period=period if is_w2 else 1,
            ytd_gross=ytd if is_w2 else 0,
            ytd_federal_withheld=fed if is_w2 else 0,
            ytd_state_withheld=state if is_w2 else 0,
            ytd_401k=k401 if is_w2 else 0,
            estimated_annual_amount=est_amt if not is_w2 else 0,
            estimated_tax_payments=est_pay if not is_w2 else 0,
            is_self_employment=stype[1] in [IncomeSourceType.SELF_EMPLOYMENT, IncomeSourceType.FORM_1099_NEC]
        )
        
        if stype[1] == IncomeSourceType.W2_SPOUSE:
            if not st.session_state.enhanced_profile.spouse:
                st.session_state.enhanced_profile.spouse = SpouseIncome()
            st.session_state.enhanced_profile.spouse.sources.append(src)
        else:
            st.session_state.enhanced_profile.add_income_source(src)
        
        sync_and_calculate()
        st.success(f"Added {sname}")
        st.rerun()
    
    st.divider()
    st.subheader("📅 Estimated Payments")
    c1, c2, c3, c4 = st.columns(4)
    q1 = c1.number_input("Q1", 0.0, value=float(st.session_state.enhanced_profile.q1_estimated_payment))
    q2 = c2.number_input("Q2", 0.0, value=float(st.session_state.enhanced_profile.q2_estimated_payment))
    q3 = c3.number_input("Q3", 0.0, value=float(st.session_state.enhanced_profile.q3_estimated_payment))
    q4 = c4.number_input("Q4", 0.0, value=float(st.session_state.enhanced_profile.q4_estimated_payment))
    
    if st.button("💾 Save Payments"):
        ep = st.session_state.enhanced_profile
        ep.q1_estimated_payment = q1
        ep.q2_estimated_payment = q2
        ep.q3_estimated_payment = q3
        ep.q4_estimated_payment = q4
        sync_and_calculate()
        st.success("Saved!")


# ---- TAB 3: WHAT-IF ----
with tab3:
    st.header("🔮 What-If Simulator")
    
    sim = TaxSimulator(st.session_state.profile)
    
    c1, c2, c3 = st.columns(3)
    if c1.button("Max 401(k)", use_container_width=True):
        r = sim.find_optimal_401k()
        st.session_state.simulations.insert(0, r)
    if c2.button("Max HSA", use_container_width=True):
        r = sim.find_optimal_hsa()
        st.session_state.simulations.insert(0, r)
    if c3.button("Max All", use_container_width=True):
        ch = {}
        if st.session_state.profile.remaining_401k_room > 0:
            ch["extra_401k_traditional"] = st.session_state.profile.remaining_401k_room
        if st.session_state.profile.remaining_hsa_room > 0:
            ch["extra_hsa"] = st.session_state.profile.remaining_hsa_room
        if ch:
            r = sim.run_simulation(ch, "Max All")
            st.session_state.simulations.insert(0, r)
    
    st.divider()
    c1, c2 = st.columns(2)
    add_401k = c1.number_input("Add 401(k)", 0.0, float(st.session_state.profile.remaining_401k_room))
    add_hsa = c2.number_input("Add HSA", 0.0, float(st.session_state.profile.remaining_hsa_room))
    
    if st.button("Run Custom"):
        ch = {}
        if add_401k: ch["extra_401k_traditional"] = add_401k
        if add_hsa: ch["extra_hsa"] = add_hsa
        if ch:
            r = sim.run_simulation(ch, "Custom")
            st.session_state.simulations.insert(0, r)
    
    if st.session_state.simulations:
        st.subheader("Results")
        for s in st.session_state.simulations[:5]:
            color = "green" if s.is_beneficial else "red"
            st.markdown(f"**{s.scenario_name}**: :{color}[{fmt(s.tax_difference)}]")


# ---- TAB 4: BASIC TIPS ----
with tab4:
    st.header("💡 Basic Recommendations")
    
    rec = st.session_state.recommendations
    if rec and rec.basic_recommendations:
        st.metric("Max Savings", fmt(rec.max_potential_savings))
        st.divider()
        for r in rec.basic_recommendations:
            with st.expander(f"{'🔴' if r.priority.value=='high' else '🟡'} {r.title} - {fmt(r.potential_tax_savings)}"):
                st.write(r.description)
                st.write(f"**Action:** {r.action_required}")
    else:
        st.info("Add income data to get recommendations.")


# ---- TAB 5: ADVANCED STRATEGIES ----
with tab5:
    st.header("🚀 Advanced Tax Strategies")
    st.warning("⚠️ May require professional help and lifestyle changes.")
    
    strats = get_all_strategies()
    cat = st.selectbox("Category", ["All"] + [c.value.replace("_"," ").title() for c in StrategyCategory])
    
    if cat != "All":
        enum = StrategyCategory(cat.lower().replace(" ","_"))
        strats = [s for s in strats if s.category == enum]
    
    for s in strats:
        badge = {"moderate":"🟢", "advanced":"🟡", "expert":"🔴"}.get(s.complexity.value, "")
        with st.expander(f"{badge} {s.name} | Min: {fmt(s.min_income)}"):
            st.write(s.description.strip())
            st.success(f"**Savings:** {s.potential_savings}")
            st.markdown("**How it works:**")
            st.write(s.how_it_works.strip())
            st.markdown("**Steps:**")
            for i, step in enumerate(s.steps, 1):
                st.write(f"{i}. {step}")
            if s.risks:
                st.warning("⚠️ Risks: " + "; ".join(s.risks[:2]))


# ---- TAB 6: PRIVACY DEMO ----
with tab6:
    st.header("🔒 PII Redaction Demo")
    
    demo = """Employee: John Smith
SSN: 123-45-6789
Gross Pay: $4,250.00
YTD: $85,000.00
Email: john@acme.com"""
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Original")
        txt = st.text_area("Input", demo, height=200)
    with c2:
        st.subheader("Redacted")
        if st.button("🔍 Redact"):
            r = PIIRedactor(use_ner=False)
            res = r.redact_sensitive_data(txt)
            st.text_area("Output", res.redacted_text, height=200)
            st.success(f"Removed {res.redaction_count} PII items")


# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.caption("⚠️ Estimates only. Consult a tax professional for advice.")
