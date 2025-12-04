"""
OpenAI GPT-5.1 Integration for TaxGuard AI
==========================================
Provides AI-powered tax strategy generation and personalized advice.

Uses GPT-5.1 (OpenAI's latest frontier model with adaptive reasoning) for:
- Generating personalized tax reduction strategies
- Explaining complex tax concepts
- Analyzing user situations for optimization opportunities

IMPORTANT: All data sent to OpenAI has PII removed via the Privacy Air Gap.
"""

import os
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import streamlit as st

# Try to import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class AIProvider(Enum):
    OPENAI = "openai"
    MOCK = "mock"


@dataclass
class AIResponse:
    """Response from AI model."""
    content: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    success: bool = True
    error: Optional[str] = None


# Tax strategy system prompt
TAX_STRATEGY_SYSTEM_PROMPT = """You are TaxGuard AI, an expert tax advisor assistant. Your role is to analyze anonymized financial data and provide personalized tax reduction strategies.

IMPORTANT GUIDELINES:
1. All data you receive has been anonymized - personal identifiable information has been removed
2. Provide specific, actionable recommendations based on the numbers provided
3. Always explain the "why" behind each strategy
4. Include estimated tax savings when possible
5. Prioritize strategies by potential impact (highest savings first)
6. Note any deadlines or time-sensitive actions
7. Flag strategies that may require professional assistance
8. Be conservative in estimates - under-promise, over-deliver

RESPONSE FORMAT:
- Use clear headers for each strategy
- Include specific dollar amounts when relevant
- Explain eligibility requirements
- Note any risks or limitations
- Provide step-by-step implementation guidance

Remember: You're helping real people reduce their tax burden legally and ethically. Be thorough but accessible."""


TAX_CALCULATION_SYSTEM_PROMPT = """You are a tax calculation assistant. Analyze the provided financial data and calculate potential tax savings from various strategies.

For each strategy, provide:
1. Current tax impact
2. Potential new tax impact after implementing strategy
3. Net savings
4. Implementation steps
5. Any caveats or requirements

Be precise with calculations. Show your work. Use 2025 tax brackets and limits."""


class TaxAIClient:
    """
    AI client for tax strategy generation.
    
    Supports:
    - OpenAI GPT-5.1 (primary) - latest frontier model with adaptive reasoning
    - Mock responses (fallback when no API key)
    """
    
    def __init__(self):
        self.provider = AIProvider.MOCK
        self.client = None
        self.model = "gpt-5.1"  # OpenAI's latest frontier model with adaptive reasoning
        
        # Check for OpenAI API key
        api_key = self._get_api_key()
        
        if api_key and OPENAI_AVAILABLE:
            try:
                self.client = OpenAI(api_key=api_key)
                self.provider = AIProvider.OPENAI
            except Exception as e:
                print(f"Failed to initialize OpenAI client: {e}")
                self.provider = AIProvider.MOCK
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment or Streamlit secrets."""
        # Try Streamlit secrets first (for deployed apps)
        try:
            if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
                return st.secrets['OPENAI_API_KEY']
        except Exception:
            pass
        
        # Fall back to environment variable
        return os.environ.get('OPENAI_API_KEY')
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to real AI provider."""
        return self.provider == AIProvider.OPENAI and self.client is not None
    
    def generate_strategies(
        self,
        anonymized_profile: Dict[str, Any],
        current_tax_result: Dict[str, Any],
        focus_areas: Optional[List[str]] = None
    ) -> AIResponse:
        """
        Generate personalized tax reduction strategies.
        
        Args:
            anonymized_profile: User financial data with PII removed
            current_tax_result: Current tax calculation results
            focus_areas: Optional list of areas to focus on (e.g., ["retirement", "business"])
        
        Returns:
            AIResponse with strategy recommendations
        """
        # Build the prompt
        user_prompt = self._build_strategy_prompt(
            anonymized_profile, 
            current_tax_result, 
            focus_areas
        )
        
        if self.provider == AIProvider.OPENAI:
            return self._call_openai(
                system_prompt=TAX_STRATEGY_SYSTEM_PROMPT,
                user_prompt=user_prompt
            )
        else:
            return self._mock_strategy_response(anonymized_profile, current_tax_result)
    
    def analyze_scenario(
        self,
        scenario_description: str,
        anonymized_profile: Dict[str, Any],
        current_tax_result: Dict[str, Any]
    ) -> AIResponse:
        """
        Analyze a specific tax scenario and provide recommendations.
        
        Args:
            scenario_description: What the user wants to analyze
            anonymized_profile: User financial data with PII removed
            current_tax_result: Current tax calculation results
        
        Returns:
            AIResponse with analysis
        """
        user_prompt = f"""
SCENARIO TO ANALYZE:
{scenario_description}

CURRENT FINANCIAL SITUATION:
{json.dumps(anonymized_profile, indent=2)}

CURRENT TAX CALCULATION:
{json.dumps(current_tax_result, indent=2)}

Please analyze this scenario and provide:
1. How it would affect the tax situation
2. Specific recommendations
3. Potential savings or costs
4. Any risks or considerations
"""
        
        if self.provider == AIProvider.OPENAI:
            return self._call_openai(
                system_prompt=TAX_CALCULATION_SYSTEM_PROMPT,
                user_prompt=user_prompt
            )
        else:
            return self._mock_analysis_response()
    
    def explain_strategy(
        self,
        strategy_name: str,
        anonymized_profile: Dict[str, Any]
    ) -> AIResponse:
        """
        Get a detailed explanation of a specific tax strategy.
        
        Args:
            strategy_name: Name of the strategy to explain
            anonymized_profile: User financial data for context
        
        Returns:
            AIResponse with explanation
        """
        user_prompt = f"""
Please explain the following tax strategy in detail, specifically as it applies to someone in this financial situation:

STRATEGY: {strategy_name}

FINANCIAL CONTEXT:
{json.dumps(anonymized_profile, indent=2)}

Provide:
1. How this strategy works
2. Eligibility requirements
3. Step-by-step implementation
4. Estimated savings for this specific situation
5. Potential pitfalls to avoid
6. Timeline and deadlines
"""
        
        if self.provider == AIProvider.OPENAI:
            return self._call_openai(
                system_prompt=TAX_STRATEGY_SYSTEM_PROMPT,
                user_prompt=user_prompt
            )
        else:
            return self._mock_explanation_response(strategy_name)
    
    def _build_strategy_prompt(
        self,
        profile: Dict[str, Any],
        tax_result: Dict[str, Any],
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """Build the strategy generation prompt."""
        focus_text = ""
        if focus_areas:
            focus_text = f"\n\nFOCUS AREAS (prioritize these): {', '.join(focus_areas)}"
        
        num_sources = profile.get('num_income_sources', 1)
        sources_note = f"(aggregated from {num_sources} income source(s))" if num_sources > 1 else ""
        
        return f"""
ANONYMIZED FINANCIAL PROFILE {sources_note}:
{json.dumps(profile, indent=2)}

CURRENT TAX CALCULATION (based on all income sources combined):
- Total Gross Income: ${tax_result.get('gross_income', 0):,.2f}
- Taxable Income: ${tax_result.get('taxable_income', 0):,.2f}
- Federal Tax: ${tax_result.get('federal_tax', 0):,.2f}
- Total Tax Liability: ${tax_result.get('total_tax_liability', 0):,.2f}
- Effective Tax Rate: {tax_result.get('effective_rate', 0):.1f}%
- Marginal Tax Rate: {tax_result.get('marginal_rate', 0) * 100:.0f}%
- Current Refund/Owed: ${tax_result.get('refund_or_owed', 0):,.2f}
{focus_text}

Based on this financial profile, provide personalized tax reduction strategies. 
Note: Income and withholding amounts represent TOTALS from all the taxpayer's income sources combined.
Prioritize by potential savings. Include specific dollar amounts where possible.
Focus on strategies that can be implemented before year-end if applicable.
"""
    
    def _call_openai(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> AIResponse:
        """Make a call to OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                # No temperature or max_tokens as requested
            )
            
            return AIResponse(
                content=response.choices[0].message.content,
                model=self.model,
                provider="openai",
                tokens_used=response.usage.total_tokens if response.usage else None,
                success=True
            )
        
        except Exception as e:
            return AIResponse(
                content="",
                model=self.model,
                provider="openai",
                success=False,
                error=str(e)
            )
    
    def _mock_strategy_response(
        self,
        profile: Dict[str, Any],
        tax_result: Dict[str, Any]
    ) -> AIResponse:
        """Generate mock response when no API key available."""
        marginal_rate = tax_result.get('marginal_rate', 0.22)
        
        content = f"""## 🎯 Personalized Tax Reduction Strategies

Based on your financial profile, here are the top strategies to reduce your tax liability:

### 1. Maximize Retirement Contributions
**Potential Savings: ${5000 * marginal_rate:,.0f} - ${10000 * marginal_rate:,.0f}**

Your current 401(k) and IRA contributions leave room for optimization. Consider:
- Increasing 401(k) contributions to the maximum ($23,500 for 2025)
- Contributing to a Traditional IRA if eligible ($7,000 limit)
- If self-employed, consider a SEP-IRA (up to $69,000)

### 2. Health Savings Account (HSA)
**Potential Savings: ${3000 * marginal_rate:,.0f}+**

If you have a high-deductible health plan:
- Contribute up to $4,300 (individual) or $8,550 (family)
- Triple tax advantage: deductible, grows tax-free, withdrawals tax-free for medical

### 3. Tax-Loss Harvesting
**Potential Savings: Varies**

Review your investment portfolio for:
- Positions with unrealized losses to offset gains
- Up to $3,000 in losses can offset ordinary income
- Watch the 30-day wash sale rule

### 4. Charitable Giving Strategies
**Potential Savings: ${1000 * marginal_rate:,.0f}+**

Consider:
- Donating appreciated stock (avoid capital gains + get full deduction)
- Bunching donations in one year to exceed standard deduction
- Donor-advised fund for flexibility

---
⚠️ *This is a demo response. Connect your OpenAI API key for personalized AI-powered strategies from GPT-5.1.*
"""
        
        return AIResponse(
            content=content,
            model="mock",
            provider="mock",
            success=True
        )
    
    def _mock_analysis_response(self) -> AIResponse:
        """Mock response for scenario analysis."""
        return AIResponse(
            content="""## Scenario Analysis

This analysis requires the OpenAI GPT-5.1 connection for accurate calculations.

**To enable AI-powered analysis:**
1. Add your OpenAI API key to Streamlit secrets
2. Key name: `OPENAI_API_KEY`
3. Refresh the app

GPT-5.1 will then provide:
- Detailed tax impact calculations
- Personalized recommendations
- Step-by-step implementation guidance
""",
            model="mock",
            provider="mock",
            success=True
        )
    
    def _mock_explanation_response(self, strategy_name: str) -> AIResponse:
        """Mock response for strategy explanations."""
        return AIResponse(
            content=f"""## {strategy_name}

Detailed explanation requires OpenAI GPT-5.1 connection.

**To enable AI-powered explanations:**
Add your `OPENAI_API_KEY` to Streamlit secrets.

GPT-5.1 will provide:
- How this strategy works
- Your specific eligibility
- Step-by-step implementation
- Estimated savings for your situation
""",
            model="mock",
            provider="mock",
            success=True
        )


def get_ai_client() -> TaxAIClient:
    """Get or create the AI client singleton."""
    if 'ai_client' not in st.session_state:
        st.session_state.ai_client = TaxAIClient()
    return st.session_state.ai_client


def create_anonymized_profile(profile, num_income_sources: int = 1) -> Dict[str, Any]:
    """
    Create an anonymized version of the user profile for AI processing.
    
    This removes all PII and keeps only financial data needed for tax analysis.
    All income from multiple sources is already aggregated in the profile.
    """
    return {
        "filing_status": profile.filing_status.value if hasattr(profile.filing_status, 'value') else str(profile.filing_status),
        "age_bracket": "under_50" if profile.age < 50 else "50_to_65" if profile.age < 65 else "65_plus",
        "num_dependents": profile.num_children_under_17,
        "num_income_sources": num_income_sources,  # Number of W-2s, 1099s, etc. combined
        "income": {
            "total_ytd_income": getattr(profile, 'ytd_income', 0),
            "projected_annual_income": getattr(profile, 'projected_annual_income', profile.ytd_income * 2),
            "self_employment_income": getattr(profile, 'self_employment_income', 0),
            "interest_income": getattr(profile, 'interest_income', 0),
            "dividend_income": getattr(profile, 'dividend_income', 0),
            "capital_gains_short": getattr(profile, 'capital_gains_short', 0),
            "capital_gains_long": getattr(profile, 'capital_gains_long', 0),
        },
        "withholding": {
            "total_federal_withheld": getattr(profile, 'ytd_federal_withheld', 0),
            "projected_federal_withheld": getattr(profile, 'projected_annual_withholding', 0),
            "estimated_payments": getattr(profile, 'estimated_payments_made', 0),
        },
        "retirement_contributions": {
            "ytd_401k": getattr(profile, 'ytd_401k_traditional', 0),
            "remaining_401k_room": getattr(profile, 'remaining_401k_room', 0),
            "ytd_ira": getattr(profile, 'ytd_ira_traditional', 0),
            "has_workplace_plan": getattr(profile, 'has_workplace_retirement_plan', True),
        },
        "hsa": {
            "ytd_hsa": getattr(profile, 'ytd_hsa', 0),
            "remaining_hsa_room": getattr(profile, 'remaining_hsa_room', 0),
            "coverage_type": getattr(profile, 'hsa_coverage_type', 'individual'),
        },
        "deductions": {
            "mortgage_interest": getattr(profile, 'mortgage_interest', 0),
            "property_taxes": getattr(profile, 'property_taxes', 0),
            "charitable_contributions": getattr(profile, 'charitable_contributions', 0),
            "medical_expenses": getattr(profile, 'medical_expenses', 0),
        },
        "flags": {
            "has_side_business": getattr(profile, 'has_side_business', False),
            "owns_rental_property": getattr(profile, 'owns_rental_property', False),
            "interested_in_real_estate": getattr(profile, 'interested_in_real_estate', False),
            "interested_in_solar": getattr(profile, 'interested_in_solar', False),
            "interested_in_ev": getattr(profile, 'interested_in_ev', False),
        },
    }


def create_anonymized_tax_result(result) -> Dict[str, Any]:
    """Create an anonymized version of tax results for AI processing."""
    return {
        "gross_income": result.gross_income,
        "adjusted_gross_income": result.adjusted_gross_income,
        "taxable_income": result.taxable_income,
        "federal_tax": result.federal_tax,
        "self_employment_tax": result.self_employment_tax,
        "total_credits": result.total_credits,
        "total_tax_liability": result.total_tax_liability,
        "total_payments_and_withholding": result.total_payments_and_withholding,
        "refund_or_owed": result.refund_or_owed,
        "effective_rate": result.effective_rate,
        "marginal_rate": result.marginal_rate,
        "deduction_type": result.deduction_type,
        "deduction_amount": result.deduction_amount,
    }
