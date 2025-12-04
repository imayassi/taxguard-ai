"""
TaxGuard AI - Tax Constants
============================
Hardcoded 2025 Federal Tax Brackets and Limits.

CRITICAL: These are the ONLY source of truth for tax calculations.
The LLM must reference these values - never hallucinate brackets.

Last Updated: 2025 Tax Year (Projected based on IRS announcements)
"""

from enum import Enum
from typing import Dict, List, Tuple

# =============================================================================
# FILING STATUS ENUM
# =============================================================================

class FilingStatus(str, Enum):
    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_WIDOW = "qualifying_widow"


# =============================================================================
# 2025 FEDERAL TAX BRACKETS (Projected)
# Format: List of (upper_limit, marginal_rate) tuples
# The last tuple uses float('inf') for unlimited income
# =============================================================================

TAX_BRACKETS_2025: Dict[FilingStatus, List[Tuple[float, float]]] = {
    FilingStatus.SINGLE: [
        (11925, 0.10),      # 10% on first $11,925
        (48475, 0.12),      # 12% on $11,926 to $48,475
        (103350, 0.22),     # 22% on $48,476 to $103,350
        (197300, 0.24),     # 24% on $103,351 to $197,300
        (250525, 0.32),     # 32% on $197,301 to $250,525
        (626350, 0.35),     # 35% on $250,526 to $626,350
        (float('inf'), 0.37) # 37% on over $626,350
    ],
    FilingStatus.MARRIED_FILING_JOINTLY: [
        (23850, 0.10),
        (96950, 0.12),
        (206700, 0.22),
        (394600, 0.24),
        (501050, 0.32),
        (751600, 0.35),
        (float('inf'), 0.37)
    ],
    FilingStatus.MARRIED_FILING_SEPARATELY: [
        (11925, 0.10),
        (48475, 0.12),
        (103350, 0.22),
        (197300, 0.24),
        (250525, 0.32),
        (375800, 0.35),
        (float('inf'), 0.37)
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (17000, 0.10),
        (64850, 0.12),
        (103350, 0.22),
        (197300, 0.24),
        (250500, 0.32),
        (626350, 0.35),
        (float('inf'), 0.37)
    ],
    FilingStatus.QUALIFYING_WIDOW: [
        (23850, 0.10),
        (96950, 0.12),
        (206700, 0.22),
        (394600, 0.24),
        (501050, 0.32),
        (751600, 0.35),
        (float('inf'), 0.37)
    ]
}


# =============================================================================
# 2025 STANDARD DEDUCTIONS
# =============================================================================

STANDARD_DEDUCTION_2025: Dict[FilingStatus, float] = {
    FilingStatus.SINGLE: 15000,
    FilingStatus.MARRIED_FILING_JOINTLY: 30000,
    FilingStatus.MARRIED_FILING_SEPARATELY: 15000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 22500,
    FilingStatus.QUALIFYING_WIDOW: 30000
}

# Additional deduction for age 65+ or blind (per qualifying condition)
ADDITIONAL_STANDARD_DEDUCTION_2025 = {
    "single_or_hoh": 1950,  # Per condition for Single/HOH
    "married": 1550         # Per condition for Married
}


# =============================================================================
# 2025 CONTRIBUTION LIMITS
# =============================================================================

CONTRIBUTION_LIMITS_2025 = {
    # Retirement
    "401k_employee": 23500,
    "401k_catch_up_50_plus": 7500,
    "401k_catch_up_60_to_63": 11250,  # New "super catch-up"
    "ira_traditional": 7000,
    "ira_catch_up_50_plus": 1000,
    
    # Health Savings
    "hsa_individual": 4300,
    "hsa_family": 8550,
    "hsa_catch_up_55_plus": 1000,
    
    # Flexible Spending
    "fsa_health": 3300,
    "fsa_dependent_care": 5000,
    
    # Social Security
    "social_security_wage_base": 176100,
    "social_security_tax_rate": 0.062,
    "medicare_tax_rate": 0.0145,
    "medicare_additional_threshold_single": 200000,
    "medicare_additional_threshold_married": 250000,
    "medicare_additional_rate": 0.009
}


# =============================================================================
# IRA INCOME PHASE-OUT LIMITS (2025 Projected)
# =============================================================================

IRA_PHASE_OUT_2025 = {
    FilingStatus.SINGLE: {
        "covered_by_workplace_plan": {
            "phase_out_start": 79000,
            "phase_out_end": 89000
        },
        "not_covered": None  # No phase-out if not covered
    },
    FilingStatus.MARRIED_FILING_JOINTLY: {
        "both_covered": {
            "phase_out_start": 126000,
            "phase_out_end": 146000
        },
        "one_covered_contributing_spouse": {
            "phase_out_start": 126000,
            "phase_out_end": 146000
        },
        "one_covered_non_contributing_spouse": {
            "phase_out_start": 236000,
            "phase_out_end": 246000
        }
    }
}


# =============================================================================
# ROTH IRA CONTRIBUTION LIMITS (2025)
# =============================================================================

ROTH_IRA_PHASE_OUT_2025 = {
    FilingStatus.SINGLE: {
        "phase_out_start": 150000,
        "phase_out_end": 165000
    },
    FilingStatus.MARRIED_FILING_JOINTLY: {
        "phase_out_start": 236000,
        "phase_out_end": 246000
    },
    FilingStatus.MARRIED_FILING_SEPARATELY: {
        "phase_out_start": 0,
        "phase_out_end": 10000
    }
}


# =============================================================================
# PAY FREQUENCY CONSTANTS
# =============================================================================

PAY_PERIODS_PER_YEAR = {
    "weekly": 52,
    "biweekly": 26,
    "bi-weekly": 26,
    "semi-monthly": 24,
    "semimonthly": 24,
    "monthly": 12,
    "quarterly": 4,
    "annually": 1
}


# =============================================================================
# CHILD TAX CREDIT (2025)
# =============================================================================

CHILD_TAX_CREDIT_2025 = {
    "amount_per_child": 2000,
    "refundable_portion": 1700,  # Additional Child Tax Credit
    "phase_out_threshold_single": 200000,
    "phase_out_threshold_married": 400000,
    "phase_out_rate": 50,  # $50 reduction per $1000 over threshold
    "qualifying_age": 17  # Under 17
}


# =============================================================================
# CAPITAL GAINS TAX RATES (2025)
# =============================================================================

CAPITAL_GAINS_RATES_2025 = {
    FilingStatus.SINGLE: [
        (47025, 0.00),    # 0% up to $47,025
        (518900, 0.15),   # 15% from $47,026 to $518,900
        (float('inf'), 0.20)  # 20% over $518,900
    ],
    FilingStatus.MARRIED_FILING_JOINTLY: [
        (94050, 0.00),
        (583750, 0.15),
        (float('inf'), 0.20)
    ]
}

# Net Investment Income Tax (NIIT)
NIIT_THRESHOLD = {
    FilingStatus.SINGLE: 200000,
    FilingStatus.MARRIED_FILING_JOINTLY: 250000,
    FilingStatus.MARRIED_FILING_SEPARATELY: 125000
}
NIIT_RATE = 0.038


# =============================================================================
# STATE TAX DEFAULTS (for common states)
# =============================================================================

STATE_TAX_RATES = {
    "CA": {"type": "progressive", "max_rate": 0.133},
    "NY": {"type": "progressive", "max_rate": 0.109},
    "TX": {"type": "none", "max_rate": 0.0},
    "FL": {"type": "none", "max_rate": 0.0},
    "WA": {"type": "none", "max_rate": 0.0},
    "IL": {"type": "flat", "max_rate": 0.0495},
    "PA": {"type": "flat", "max_rate": 0.0307}
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tax_bracket_info(filing_status: FilingStatus) -> str:
    """
    Return a formatted string of tax brackets for the given filing status.
    This is used to provide the LLM with accurate bracket information.
    """
    brackets = TAX_BRACKETS_2025[filing_status]
    lines = [f"2025 Federal Tax Brackets for {filing_status.value.replace('_', ' ').title()}:"]
    prev_limit = 0
    
    for limit, rate in brackets:
        if limit == float('inf'):
            lines.append(f"  Over ${prev_limit:,}: {rate*100:.0f}%")
        else:
            lines.append(f"  ${prev_limit:,} to ${limit:,}: {rate*100:.0f}%")
            prev_limit = limit
    
    return "\n".join(lines)


def calculate_federal_tax(taxable_income: float, filing_status: FilingStatus) -> float:
    """
    Calculate federal income tax using the 2025 brackets.
    This is the AUTHORITATIVE calculation - not the LLM.
    
    Args:
        taxable_income: Income after deductions
        filing_status: Filing status enum
        
    Returns:
        Total federal income tax owed
    """
    if taxable_income <= 0:
        return 0.0
    
    brackets = TAX_BRACKETS_2025[filing_status]
    total_tax = 0.0
    remaining_income = taxable_income
    prev_limit = 0
    
    for limit, rate in brackets:
        bracket_size = limit - prev_limit if limit != float('inf') else remaining_income
        taxable_in_bracket = min(remaining_income, bracket_size)
        
        if taxable_in_bracket <= 0:
            break
            
        total_tax += taxable_in_bracket * rate
        remaining_income -= taxable_in_bracket
        prev_limit = limit
        
        if remaining_income <= 0:
            break
    
    return round(total_tax, 2)


def get_marginal_rate(taxable_income: float, filing_status: FilingStatus) -> float:
    """Get the marginal tax rate for a given income level."""
    brackets = TAX_BRACKETS_2025[filing_status]
    
    for limit, rate in brackets:
        if taxable_income <= limit:
            return rate
    
    return brackets[-1][1]  # Return highest rate


def get_effective_rate(taxable_income: float, filing_status: FilingStatus) -> float:
    """Calculate the effective tax rate."""
    if taxable_income <= 0:
        return 0.0
    
    tax = calculate_federal_tax(taxable_income, filing_status)
    return round((tax / taxable_income) * 100, 2)


# =============================================================================
# EXPORT CONSTANTS FOR LLM PROMPTS
# =============================================================================

def get_all_constants_for_llm() -> str:
    """
    Generate a comprehensive string of all tax constants for inclusion
    in LLM system prompts. This ensures the AI never hallucinates values.
    """
    output = []
    output.append("=" * 60)
    output.append("AUTHORITATIVE 2025 TAX REFERENCE DATA")
    output.append("Use ONLY these values - do not estimate or guess.")
    output.append("=" * 60)
    
    output.append("\n--- STANDARD DEDUCTIONS ---")
    for status, amount in STANDARD_DEDUCTION_2025.items():
        output.append(f"{status.value}: ${amount:,}")
    
    output.append("\n--- CONTRIBUTION LIMITS ---")
    for key, value in CONTRIBUTION_LIMITS_2025.items():
        output.append(f"{key}: ${value:,}")
    
    output.append("\n--- TAX BRACKETS ---")
    for status in [FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY]:
        output.append(f"\n{get_tax_bracket_info(status)}")
    
    return "\n".join(output)
