"""
TaxGuard AI - Tax Simulator
============================
Core tax calculation and simulation engine.

This module performs all tax math locally - the LLM is NOT used for calculations.
The LLM only helps with:
1. Extracting data from documents
2. Generating natural language recommendations

All bracket lookups, tax math, and projections happen here with hardcoded values.
"""

import copy
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from tax_constants import (
    FilingStatus,
    TAX_BRACKETS_2025,
    STANDARD_DEDUCTION_2025,
    CONTRIBUTION_LIMITS_2025,
    PAY_PERIODS_PER_YEAR,
    CHILD_TAX_CREDIT_2025,
    calculate_federal_tax,
    get_marginal_rate,
    get_effective_rate
)
from models import (
    UserFinancialProfile,
    PayFrequency,
    TaxResult,
    TaxBracketBreakdown,
    SimulationResult,
    TaxRecommendation,
    RecommendationReport,
    RecommendationPriority,
    RecommendationCategory
)


# =============================================================================
# TAX CALCULATION ENGINE
# =============================================================================

class TaxCalculator:
    """
    Core tax calculation engine.
    All calculations use hardcoded 2025 values - NO LLM involvement.
    """
    
    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year
        self.current_date = date.today()
    
    def calculate_tax(self, profile: UserFinancialProfile) -> TaxResult:
        """
        Calculate complete tax liability from a user profile.
        
        This is the authoritative calculation - results from here
        should be used, not LLM estimates.
        """
        # Step 1: Calculate total gross income
        gross_income = self._calculate_gross_income(profile)
        
        # Step 2: Calculate adjustments (above-the-line deductions)
        adjustments = self._calculate_adjustments(profile)
        
        # Step 3: AGI
        agi = max(0, gross_income - adjustments)
        
        # Step 4: Determine deduction (standard vs itemized)
        standard_deduction = profile.standard_deduction
        itemized_deduction = self._calculate_itemized_deductions(profile)
        
        if profile.prefers_itemized and itemized_deduction > standard_deduction:
            deduction_type = "itemized"
            deduction_amount = itemized_deduction
        else:
            deduction_type = "standard"
            deduction_amount = standard_deduction
        
        # Step 5: Taxable income
        taxable_income = max(0, agi - deduction_amount)
        
        # Step 6: Calculate federal tax with bracket breakdown
        federal_tax, bracket_breakdown = self._calculate_tax_with_breakdown(
            taxable_income, 
            profile.filing_status
        )
        
        # Step 7: Self-employment tax (if applicable)
        se_tax = self._calculate_self_employment_tax(profile)
        
        # Step 8: Credits
        child_credit = self._calculate_child_tax_credit(profile, agi)
        other_credits = 0.0  # Placeholder for other credits
        total_credits = child_credit + other_credits
        
        # Step 9: Total tax liability
        total_tax = max(0, federal_tax + se_tax - total_credits)
        
        # Step 10: Total payments (PROJECTED to year-end)
        # Use the profile's projected_annual_withholding which handles multiple income sources
        if hasattr(profile, 'projected_annual_withholding') and profile.projected_annual_withholding > 0:
            # Use the computed property that aggregates from all income sources
            total_payments = profile.projected_annual_withholding + profile.estimated_payments_made
        else:
            # Fallback: project from YTD using current pay period
            total_payments = profile.ytd_federal_withheld + profile.estimated_payments_made
            
            if profile.current_pay_period > 0:
                total_periods = PAY_PERIODS_PER_YEAR[profile.pay_frequency.value]
                payment_projection_factor = total_periods / profile.current_pay_period
                total_payments = (profile.ytd_federal_withheld * payment_projection_factor) + profile.estimated_payments_made
        
        # Step 11: Refund or owed
        refund_or_owed = total_payments - total_tax
        
        # Get rates
        marginal_rate = get_marginal_rate(taxable_income, profile.filing_status)
        effective_rate = get_effective_rate(taxable_income, profile.filing_status)
        
        return TaxResult(
            gross_income=round(gross_income, 2),
            adjustments=round(adjustments, 2),
            adjusted_gross_income=round(agi, 2),
            deduction_type=deduction_type,
            deduction_amount=round(deduction_amount, 2),
            taxable_income=round(taxable_income, 2),
            federal_tax=round(federal_tax, 2),
            bracket_breakdown=bracket_breakdown,
            marginal_rate=marginal_rate,
            effective_rate=effective_rate,
            self_employment_tax=round(se_tax, 2),
            child_tax_credit=round(child_credit, 2),
            other_credits=round(other_credits, 2),
            total_credits=round(total_credits, 2),
            total_tax_liability=round(total_tax, 2),
            total_payments_and_withholding=round(total_payments, 2),
            refund_or_owed=round(refund_or_owed, 2),
            tax_year=self.tax_year,
            is_projection=True
        )
    
    def _calculate_gross_income(self, profile: UserFinancialProfile) -> float:
        """Calculate total gross income (projected to year-end)."""
        # Project wage income to full year
        if profile.projected_annual_income > 0:
            wage_income = profile.projected_annual_income
        elif profile.ytd_income > 0 and profile.current_pay_period > 0:
            total_periods = PAY_PERIODS_PER_YEAR[profile.pay_frequency.value]
            wage_income = (profile.ytd_income / profile.current_pay_period) * total_periods
        else:
            wage_income = profile.ytd_income
        
        # Add other income
        total_income = (
            wage_income +
            profile.interest_income +
            profile.dividend_income +
            profile.capital_gains_short +
            profile.capital_gains_long +
            profile.self_employment_income +
            profile.other_income
        )
        
        return total_income
    
    def _calculate_adjustments(self, profile: UserFinancialProfile) -> float:
        """Calculate above-the-line deductions."""
        adjustments = 0.0
        
        # Traditional 401(k) - already excluded from W-2 wages
        # So we don't add it here (it's a payroll deduction, not an adjustment)
        
        # Traditional IRA (subject to income limits)
        ira_limit = CONTRIBUTION_LIMITS_2025["ira_traditional"]
        if profile.age and profile.age >= 50:
            ira_limit += CONTRIBUTION_LIMITS_2025["ira_catch_up_50_plus"]
        
        ira_deduction = min(profile.ytd_ira_traditional, ira_limit)
        
        # If covered by workplace plan, may be limited
        if profile.has_workplace_retirement_plan:
            # Simplified phase-out (full implementation would check income)
            agi_estimate = self._calculate_gross_income(profile)
            if profile.filing_status == FilingStatus.SINGLE and agi_estimate > 89000:
                ira_deduction = 0  # Fully phased out
            elif profile.filing_status == FilingStatus.MARRIED_FILING_JOINTLY and agi_estimate > 146000:
                ira_deduction = 0
        
        adjustments += ira_deduction
        
        # HSA contributions
        hsa_limit = (CONTRIBUTION_LIMITS_2025["hsa_family"] 
                    if profile.hsa_coverage_type == "family" 
                    else CONTRIBUTION_LIMITS_2025["hsa_individual"])
        if profile.age and profile.age >= 55:
            hsa_limit += CONTRIBUTION_LIMITS_2025["hsa_catch_up_55_plus"]
        
        adjustments += min(profile.ytd_hsa, hsa_limit)
        
        # Self-employment tax deduction (half of SE tax)
        if profile.self_employment_income > 0:
            se_income = profile.self_employment_income * 0.9235
            se_tax = se_income * 0.153
            adjustments += se_tax / 2
        
        return adjustments
    
    def _calculate_itemized_deductions(self, profile: UserFinancialProfile) -> float:
        """Calculate itemized deductions."""
        itemized = 0.0
        
        # State and local taxes (SALT) - capped at $10,000
        salt = min(profile.state_local_taxes_paid, 10000)
        itemized += salt
        
        # Mortgage interest
        itemized += profile.mortgage_interest
        
        # Charitable donations (limited to 60% of AGI for cash)
        itemized += profile.charitable_donations
        
        # Medical expenses (only amount exceeding 7.5% of AGI)
        agi = self._calculate_gross_income(profile) - self._calculate_adjustments(profile)
        medical_threshold = agi * 0.075
        medical_deductible = max(0, profile.medical_expenses - medical_threshold)
        itemized += medical_deductible
        
        return itemized
    
    def _calculate_tax_with_breakdown(
        self, 
        taxable_income: float, 
        filing_status: FilingStatus
    ) -> Tuple[float, List[TaxBracketBreakdown]]:
        """Calculate tax with detailed bracket breakdown."""
        if taxable_income <= 0:
            return 0.0, []
        
        brackets = TAX_BRACKETS_2025[filing_status]
        total_tax = 0.0
        breakdown = []
        remaining_income = taxable_income
        prev_limit = 0
        
        for limit, rate in brackets:
            bracket_size = limit - prev_limit if limit != float('inf') else remaining_income
            taxable_in_bracket = min(remaining_income, bracket_size)
            
            if taxable_in_bracket <= 0:
                break
            
            tax_in_bracket = taxable_in_bracket * rate
            total_tax += tax_in_bracket
            
            breakdown.append(TaxBracketBreakdown(
                bracket_start=prev_limit,
                bracket_end=limit if limit != float('inf') else prev_limit + taxable_in_bracket,
                rate=rate,
                income_in_bracket=round(taxable_in_bracket, 2),
                tax_in_bracket=round(tax_in_bracket, 2)
            ))
            
            remaining_income -= taxable_in_bracket
            prev_limit = limit
            
            if remaining_income <= 0:
                break
        
        return round(total_tax, 2), breakdown
    
    def _calculate_self_employment_tax(self, profile: UserFinancialProfile) -> float:
        """Calculate self-employment tax (Social Security + Medicare)."""
        if profile.self_employment_income <= 0:
            return 0.0
        
        # Net SE income (92.35% of gross)
        net_se = profile.self_employment_income * 0.9235
        
        # Social Security portion (6.2% * 2 = 12.4%) - up to wage base
        ss_wage_base = CONTRIBUTION_LIMITS_2025["social_security_wage_base"]
        ss_taxable = min(net_se, ss_wage_base)
        ss_tax = ss_taxable * 0.124
        
        # Medicare portion (1.45% * 2 = 2.9%)
        medicare_tax = net_se * 0.029
        
        # Additional Medicare tax for high earners
        threshold = (CONTRIBUTION_LIMITS_2025["medicare_additional_threshold_married"]
                    if profile.filing_status == FilingStatus.MARRIED_FILING_JOINTLY
                    else CONTRIBUTION_LIMITS_2025["medicare_additional_threshold_single"])
        
        if net_se > threshold:
            medicare_tax += (net_se - threshold) * CONTRIBUTION_LIMITS_2025["medicare_additional_rate"]
        
        return ss_tax + medicare_tax
    
    def _calculate_child_tax_credit(self, profile: UserFinancialProfile, agi: float) -> float:
        """Calculate child tax credit."""
        if profile.num_children_under_17 <= 0:
            return 0.0
        
        credit_per_child = CHILD_TAX_CREDIT_2025["amount_per_child"]
        total_credit = profile.num_children_under_17 * credit_per_child
        
        # Phase-out
        threshold = (CHILD_TAX_CREDIT_2025["phase_out_threshold_married"]
                    if profile.filing_status == FilingStatus.MARRIED_FILING_JOINTLY
                    else CHILD_TAX_CREDIT_2025["phase_out_threshold_single"])
        
        if agi > threshold:
            reduction_units = (agi - threshold) // 1000
            reduction = reduction_units * CHILD_TAX_CREDIT_2025["phase_out_rate"]
            total_credit = max(0, total_credit - reduction)
        
        return total_credit


# =============================================================================
# TAX SIMULATOR (What-If Scenarios)
# =============================================================================

class TaxSimulator:
    """
    Run what-if tax simulations.
    
    Example:
        simulator = TaxSimulator(profile)
        result = simulator.run_simulation({'extra_401k': 5000})
    """
    
    def __init__(self, profile: Optional[UserFinancialProfile] = None):
        self.profile = profile
        self.calculator = TaxCalculator()
    
    def set_profile(self, profile: UserFinancialProfile):
        """Set the baseline profile for simulations."""
        self.profile = profile
    
    def run_simulation(
        self, 
        changes: Dict[str, Any],
        scenario_name: str = "Custom Simulation"
    ) -> SimulationResult:
        """
        Run a single simulation with specified changes.
        
        Args:
            changes: Dictionary of field changes to apply.
                    Supports special keys like 'extra_401k', 'extra_hsa'
                    which add to existing values.
            scenario_name: Name for this scenario
            
        Returns:
            SimulationResult comparing baseline to simulated
        """
        if self.profile is None:
            raise ValueError("No profile set. Call set_profile() first.")
        
        # Calculate baseline
        baseline_result = self.calculator.calculate_tax(self.profile)
        
        # Create modified profile
        modified_profile = self._apply_changes(self.profile, changes)
        
        # Calculate with changes
        simulated_result = self.calculator.calculate_tax(modified_profile)
        
        # Calculate differences
        tax_diff = simulated_result.total_tax_liability - baseline_result.total_tax_liability
        refund_diff = simulated_result.refund_or_owed - baseline_result.refund_or_owed
        rate_diff = simulated_result.effective_rate - baseline_result.effective_rate
        
        # Determine if beneficial
        is_beneficial = tax_diff < 0 or refund_diff > 0
        
        # Generate summary
        if is_beneficial:
            summary = f"This change would save you ${abs(tax_diff):,.2f} in taxes."
        else:
            summary = f"This change would increase your taxes by ${abs(tax_diff):,.2f}."
        
        return SimulationResult(
            scenario_name=scenario_name,
            baseline=baseline_result,
            simulated=simulated_result,
            tax_difference=round(tax_diff, 2),
            refund_difference=round(refund_diff, 2),
            effective_rate_change=round(rate_diff, 2),
            is_beneficial=is_beneficial,
            summary=summary
        )
    
    def _apply_changes(
        self, 
        profile: UserFinancialProfile, 
        changes: Dict[str, Any]
    ) -> UserFinancialProfile:
        """Apply changes to create a modified profile."""
        # Deep copy to avoid modifying original
        modified = profile.model_copy(deep=True)
        
        for key, value in changes.items():
            # Handle "extra_" prefix (additive changes)
            if key.startswith('extra_'):
                actual_field = key.replace('extra_', 'ytd_')
                if hasattr(modified, actual_field):
                    current_value = getattr(modified, actual_field)
                    setattr(modified, actual_field, current_value + value)
                continue
            
            # Handle filing status specially
            if key == 'filing_status':
                if isinstance(value, str):
                    modified.filing_status = FilingStatus(value)
                else:
                    modified.filing_status = value
                continue
            
            # Handle pay frequency specially
            if key == 'pay_frequency':
                if isinstance(value, str):
                    modified.pay_frequency = PayFrequency(value)
                else:
                    modified.pay_frequency = value
                continue
            
            # Direct field assignment
            if hasattr(modified, key):
                setattr(modified, key, value)
        
        # Recalculate projections
        modified = modified.model_validate(modified.model_dump())
        
        return modified
    
    def run_multiple_simulations(
        self, 
        scenarios: List[Dict[str, Any]]
    ) -> List[SimulationResult]:
        """
        Run multiple simulations and return all results.
        
        Args:
            scenarios: List of dicts with 'name' and 'changes' keys
            
        Returns:
            List of SimulationResults
        """
        results = []
        
        for scenario in scenarios:
            name = scenario.get('name', 'Unnamed')
            changes = scenario.get('changes', {})
            result = self.run_simulation(changes, name)
            results.append(result)
        
        return results
    
    def find_optimal_401k(self) -> SimulationResult:
        """Find the tax impact of maxing out 401(k)."""
        max_401k = CONTRIBUTION_LIMITS_2025["401k_employee"]
        if self.profile.age and self.profile.age >= 50:
            if self.profile.age >= 60 and self.profile.age <= 63:
                max_401k += CONTRIBUTION_LIMITS_2025["401k_catch_up_60_to_63"]
            else:
                max_401k += CONTRIBUTION_LIMITS_2025["401k_catch_up_50_plus"]
        
        additional_needed = max(0, max_401k - self.profile.ytd_401k_traditional)
        
        return self.run_simulation(
            {'extra_401k_traditional': additional_needed},
            f"Max 401(k) (+${additional_needed:,.0f})"
        )
    
    def find_optimal_hsa(self) -> SimulationResult:
        """Find the tax impact of maxing out HSA."""
        max_hsa = (CONTRIBUTION_LIMITS_2025["hsa_family"]
                  if self.profile.hsa_coverage_type == "family"
                  else CONTRIBUTION_LIMITS_2025["hsa_individual"])
        
        if self.profile.age and self.profile.age >= 55:
            max_hsa += CONTRIBUTION_LIMITS_2025["hsa_catch_up_55_plus"]
        
        additional_needed = max(0, max_hsa - self.profile.ytd_hsa)
        
        return self.run_simulation(
            {'extra_hsa': additional_needed},
            f"Max HSA (+${additional_needed:,.0f})"
        )


# =============================================================================
# RECOMMENDATION ENGINE
# =============================================================================

class RecommendationEngine:
    """
    Generate tax optimization recommendations.
    Uses calculation results to suggest actions.
    """
    
    def __init__(self):
        self.current_date = date.today()
        self.calculator = TaxCalculator()
        self.simulator = TaxSimulator()
    
    def generate_recommendations(
        self, 
        profile: UserFinancialProfile
    ) -> RecommendationReport:
        """
        Generate complete recommendation report.
        """
        self.simulator.set_profile(profile)
        
        # Calculate current projection
        current_result = self.calculator.calculate_tax(profile)
        
        # Time calculations
        year_end = date(self.current_date.year, 12, 31)
        days_remaining = (year_end - self.current_date).days
        
        total_periods = PAY_PERIODS_PER_YEAR[profile.pay_frequency.value]
        remaining_periods = max(0, total_periods - profile.current_pay_period)
        
        basic_recs = []
        advanced_recs = []
        
        # Check if owing taxes
        is_owing = current_result.refund_or_owed < 0
        amount_owed = abs(current_result.refund_or_owed) if is_owing else 0
        
        # === BASIC RECOMMENDATIONS ===
        
        # 1. 401(k) Optimization
        if profile.remaining_401k_room > 0:
            sim_401k = self.simulator.find_optimal_401k()
            potential_savings = abs(sim_401k.tax_difference) if sim_401k.is_beneficial else 0
            
            per_paycheck = profile.remaining_401k_room / remaining_periods if remaining_periods > 0 else 0
            is_feasible = per_paycheck < (profile.ytd_income / profile.current_pay_period) * 0.9 if profile.current_pay_period > 0 else True
            
            basic_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH if is_owing else RecommendationPriority.MEDIUM,
                category=RecommendationCategory.RETIREMENT,
                title="Maximize 401(k) Contributions",
                description=f"You have ${profile.remaining_401k_room:,.0f} of 401(k) contribution room remaining. "
                           f"Increasing contributions reduces your taxable income dollar-for-dollar.",
                potential_tax_savings=potential_savings,
                implementation_cost=profile.remaining_401k_room,
                net_benefit=potential_savings,
                action_required="Contact HR/payroll to increase your 401(k) contribution percentage.",
                deadline=year_end,
                remaining_contribution_room=profile.remaining_401k_room,
                remaining_pay_periods=remaining_periods,
                per_paycheck_amount=round(per_paycheck, 2),
                is_mathematically_feasible=is_feasible,
                complexity="basic",
                requires_professional=False
            ))
        
        # 2. HSA Optimization
        if profile.remaining_hsa_room > 0:
            sim_hsa = self.simulator.find_optimal_hsa()
            potential_savings = abs(sim_hsa.tax_difference) if sim_hsa.is_beneficial else 0
            
            basic_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.HEALTHCARE,
                title="Maximize HSA Contributions",
                description=f"You have ${profile.remaining_hsa_room:,.0f} of HSA contribution room. "
                           f"HSA contributions are triple tax-advantaged: tax-deductible, grow tax-free, "
                           f"and withdrawals for medical expenses are tax-free.",
                potential_tax_savings=potential_savings,
                implementation_cost=profile.remaining_hsa_room,
                net_benefit=potential_savings,
                action_required="Increase payroll HSA deduction or make a direct contribution to your HSA.",
                deadline=date(self.current_date.year + 1, 4, 15),  # Can contribute until tax filing
                remaining_contribution_room=profile.remaining_hsa_room,
                complexity="basic",
                requires_professional=False
            ))
        
        # 3. Traditional IRA
        ira_limit = CONTRIBUTION_LIMITS_2025["ira_traditional"]
        if profile.age and profile.age >= 50:
            ira_limit += CONTRIBUTION_LIMITS_2025["ira_catch_up_50_plus"]
        
        ira_room = max(0, ira_limit - profile.ytd_ira_traditional)
        if ira_room > 0 and not profile.has_workplace_retirement_plan:
            sim_ira = self.simulator.run_simulation({'extra_ira_traditional': ira_room}, "Max IRA")
            potential_savings = abs(sim_ira.tax_difference) if sim_ira.is_beneficial else 0
            
            basic_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.RETIREMENT,
                title="Consider Traditional IRA Contribution",
                description=f"You can contribute up to ${ira_room:,.0f} to a Traditional IRA. "
                           f"Since you don't have a workplace retirement plan, your contribution "
                           f"is fully deductible regardless of income.",
                potential_tax_savings=potential_savings,
                implementation_cost=ira_room,
                action_required="Open or contribute to a Traditional IRA at a brokerage.",
                deadline=date(self.current_date.year + 1, 4, 15),
                remaining_contribution_room=ira_room,
                complexity="basic",
                requires_professional=False
            ))
        
        # 4. Charitable Donations
        if profile.prefers_itemized or profile.charitable_donations > 0:
            basic_recs.append(TaxRecommendation(
                priority=RecommendationPriority.LOW,
                category=RecommendationCategory.CHARITABLE,
                title="Year-End Charitable Giving",
                description="If you itemize deductions, charitable donations before Dec 31 "
                           "reduce your taxable income. Consider donating appreciated securities "
                           "to avoid capital gains tax.",
                potential_tax_savings=current_result.marginal_rate * 1000,  # Est. for $1000 donation
                action_required="Make donations to qualified 501(c)(3) organizations before year-end.",
                deadline=year_end,
                complexity="basic",
                requires_professional=False
            ))
        
        # === ADVANCED RECOMMENDATIONS ===
        # These are "life-changing" strategies that can significantly reduce taxes
        
        # 1. Tax Loss Harvesting (if capital gains)
        if profile.capital_gains_long > 0 or profile.capital_gains_short > 0:
            total_gains = profile.capital_gains_long + profile.capital_gains_short
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.INVESTMENT,
                title="Tax Loss Harvesting",
                description=f"You have ${total_gains:,.0f} in capital gains. Review your portfolio "
                           f"for positions with losses that could offset these gains. You can also "
                           f"deduct up to $3,000 in net losses against ordinary income.",
                potential_tax_savings=min(total_gains, 3000) * current_result.marginal_rate + 
                                     total_gains * 0.15,  # Rough estimate
                action_required="Review investment portfolio for loss positions. Sell before Dec 31.",
                deadline=year_end,
                complexity="advanced",
                requires_professional=True,
                warnings=["Watch out for wash sale rules (30 days before/after)"]
            ))
        
        # 2. Estimated Tax Payments (if owing a lot)
        if is_owing and amount_owed > 1000:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.WITHHOLDING,
                title="Make Estimated Tax Payment",
                description=f"You're projected to owe ${amount_owed:,.0f}. To avoid underpayment "
                           f"penalties, consider making an estimated tax payment (Form 1040-ES) "
                           f"before January 15.",
                potential_tax_savings=0,  # Doesn't save tax, avoids penalty
                action_required="Make estimated payment via IRS Direct Pay or EFTPS.",
                deadline=date(self.current_date.year + 1, 1, 15),
                complexity="intermediate",
                requires_professional=False,
                warnings=["Underpayment penalty may apply if you owe >$1,000"]
            ))
        
        # 3. Adjust W-4 Withholding
        if is_owing or current_result.refund_or_owed > 5000:
            priority = RecommendationPriority.MEDIUM
            if is_owing:
                desc = f"You're projected to owe ${amount_owed:,.0f}. Adjust your W-4 to increase withholding."
            else:
                desc = f"You're getting a large refund (${current_result.refund_or_owed:,.0f}). "\
                       "Consider reducing withholding to increase take-home pay."
            
            advanced_recs.append(TaxRecommendation(
                priority=priority,
                category=RecommendationCategory.WITHHOLDING,
                title="Adjust W-4 Withholding",
                description=desc,
                action_required="Submit a new W-4 to your employer. Use the IRS Tax Withholding Estimator.",
                complexity="intermediate",
                requires_professional=False
            ))
        
        # =======================================================================
        # LIFE-CHANGING TAX STRATEGIES
        # =======================================================================
        
        # 4. START A SIDE BUSINESS (Schedule C)
        if profile.open_to_lifestyle_changes and not profile.has_side_business:
            marginal = current_result.marginal_rate
            potential_deductions = 5000  # Conservative estimate of business deductions
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.BUSINESS,
                title="🚀 Start a Side Business",
                description="Starting a legitimate side business (consulting, freelancing, selling products) "
                           "opens up MASSIVE tax deductions: home office ($1,500 simplified or actual costs), "
                           "business equipment (Section 179), health insurance premiums, retirement plans "
                           "(SEP-IRA up to $69,000), business travel, professional development, and more. "
                           "Even a small business that breaks even can generate thousands in deductions.",
                potential_tax_savings=potential_deductions * marginal,
                action_required="Identify a skill or hobby you can monetize. Register a business (LLC optional). "
                               "Keep meticulous records of income and expenses.",
                complexity="advanced",
                requires_professional=True,
                warnings=[
                    "Must have genuine profit motive (not a hobby)",
                    "Keep separate business bank account",
                    "May need to pay quarterly estimated taxes"
                ]
            ))
        
        # 5. SECTION 179 VEHICLE DEDUCTION
        if profile.has_side_business or profile.self_employment_income > 0:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.BUSINESS,
                title="🚗 Section 179 Vehicle Deduction",
                description="If you have a business, you can deduct up to $31,300 (2025) for a vehicle "
                           "used for business. For SUVs over 6,000 lbs GVWR (like Ford F-150, Chevy Tahoe, "
                           "Tesla Model X), you can potentially deduct the ENTIRE cost in year one using "
                           "Section 179 + bonus depreciation. A $60,000 vehicle at 22% tax rate = $13,200+ savings!",
                potential_tax_savings=31300 * current_result.marginal_rate,
                action_required="Document business use percentage. Consider vehicles over 6,000 lbs GVWR. "
                               "Purchase and place in service before Dec 31.",
                deadline=year_end,
                complexity="advanced",
                requires_professional=True,
                warnings=[
                    "Must document business use (mileage log or percentage)",
                    "Personal use portion is not deductible",
                    "May trigger depreciation recapture if sold"
                ]
            ))
        
        # 6. HOME OFFICE DEDUCTION
        if (profile.has_side_business or profile.self_employment_income > 0) and profile.home_office_sqft == 0:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.BUSINESS,
                title="🏠 Home Office Deduction",
                description="If you use part of your home regularly and exclusively for business, "
                           "you can deduct $5/sqft (up to 300 sqft = $1,500) using the simplified method, "
                           "OR calculate actual expenses (mortgage interest, utilities, insurance, repairs) "
                           "proportional to your office space. This can also enable deductions for "
                           "commuting to client sites.",
                potential_tax_savings=1500 * current_result.marginal_rate,
                action_required="Designate a dedicated workspace. Track home expenses. "
                               "Take photos documenting the space.",
                complexity="intermediate",
                requires_professional=False,
                warnings=["Space must be used EXCLUSIVELY for business", "May affect home sale exclusion"]
            ))
        
        # 7. RENTAL PROPERTY INVESTING
        if profile.interested_in_real_estate and not profile.owns_rental_property:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.REAL_ESTATE,
                title="🏘️ Invest in Rental Real Estate",
                description="Rental properties offer incredible tax benefits: depreciation deductions "
                           "(~3.6% of building value per year), mortgage interest deduction, repairs, "
                           "property management fees, travel to the property, and more. A $300,000 rental "
                           "could generate $8,000-10,000 in annual depreciation alone - a 'paper loss' "
                           "that offsets other income while the property appreciates.",
                potential_tax_savings=8000 * current_result.marginal_rate,
                action_required="Research rental markets. Get pre-approved for investment property financing. "
                               "Consider turnkey rental providers if you want hands-off investing.",
                complexity="advanced",
                requires_professional=True,
                warnings=[
                    "Passive activity loss rules may limit deductions",
                    "Requires active management or property manager",
                    "Depreciation recapture on sale"
                ]
            ))
        
        # 8. REAL ESTATE PROFESSIONAL STATUS
        if profile.owns_rental_property and current_result.gross_income > 150000:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.REAL_ESTATE,
                title="🏆 Real Estate Professional Status",
                description="If you or your spouse spends 750+ hours per year in real estate AND more time "
                           "in real estate than any other job, you can qualify as a 'Real Estate Professional.' "
                           "This allows rental losses to offset W-2/ordinary income without limits. "
                           "Combined with cost segregation, this can create MASSIVE tax deductions.",
                potential_tax_savings=25000 * current_result.marginal_rate,  # Example
                action_required="Track ALL time spent on real estate activities meticulously. "
                               "Consider if spouse can qualify if you can't.",
                complexity="advanced",
                requires_professional=True,
                warnings=[
                    "IRS scrutinizes this heavily - keep detailed time logs",
                    "Must be 'material participant' in each property",
                    "Consider cost segregation study for acceleration"
                ]
            ))
        
        # 9. DONOR-ADVISED FUND (Bunching Donations)
        if current_result.gross_income > 100000:
            std_ded = profile.standard_deduction
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.CHARITABLE,
                title="🎁 Donor-Advised Fund (Bunching Strategy)",
                description=f"Instead of donating $5,000/year, consider 'bunching' 3-5 years of donations "
                           f"into a single year via a Donor-Advised Fund (DAF). This pushes you over the "
                           f"${std_ded:,.0f} standard deduction threshold to itemize in that year, then "
                           f"take the standard deduction in other years. You get an immediate tax deduction "
                           f"but can distribute to charities over time.",
                potential_tax_savings=10000 * current_result.marginal_rate,  # 3-5 years bunched
                action_required="Open a DAF at Fidelity, Schwab, or Vanguard (no minimums at Fidelity). "
                               "Contribute cash or appreciated securities before Dec 31.",
                deadline=year_end,
                complexity="intermediate",
                requires_professional=False,
                warnings=["Contributions are irrevocable", "DAF fees vary by provider"]
            ))
        
        # 10. DONATE APPRECIATED STOCK
        if profile.capital_gains_long > 5000:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.CHARITABLE,
                title="📈 Donate Appreciated Stock Instead of Cash",
                description="If you're planning to donate anyway, donate appreciated stock held over 1 year "
                           "instead of cash. You get a deduction for the FULL market value AND avoid "
                           "capital gains tax. If you want to keep the position, donate the stock and "
                           "immediately repurchase (no wash sale rule for donations).",
                potential_tax_savings=profile.capital_gains_long * 0.15 + 
                                     profile.capital_gains_long * current_result.marginal_rate,
                action_required="Identify highly-appreciated positions. Contact charity about stock donations. "
                               "Complete transfer before Dec 31.",
                deadline=year_end,
                complexity="intermediate",
                requires_professional=False
            ))
        
        # 11. BACKDOOR ROTH IRA
        if current_result.gross_income > 150000:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.RETIREMENT,
                title="🚪 Backdoor Roth IRA",
                description="Even if your income is too high for direct Roth contributions, you can still "
                           "contribute to a Roth IRA via the 'backdoor' method: contribute to a non-deductible "
                           "Traditional IRA, then immediately convert to Roth. You pay no tax on conversion "
                           "(since it was after-tax money), and all future growth is tax-free forever.",
                potential_tax_savings=0,  # Tax-free growth, not immediate savings
                action_required="1) Contribute $7,000 to Traditional IRA (non-deductible). "
                               "2) Wait a few days. 3) Convert to Roth. File Form 8606.",
                deadline=date(self.current_date.year + 1, 4, 15),
                complexity="intermediate",
                requires_professional=False,
                warnings=["Pro-rata rule applies if you have existing Traditional IRA balances"]
            ))
        
        # 12. MEGA BACKDOOR ROTH
        if current_result.gross_income > 150000 and profile.has_workplace_retirement_plan:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.RETIREMENT,
                title="💰 Mega Backdoor Roth (Up to $69,000)",
                description="If your 401(k) plan allows after-tax contributions AND in-plan Roth conversions "
                           "or in-service distributions, you can contribute up to $69,000 total to your 401(k) "
                           "in 2025, then convert the after-tax portion to Roth. This is the ONLY way to get "
                           "$69,000/year into Roth accounts.",
                potential_tax_savings=0,  # Tax-free growth benefit
                action_required="Check if your plan allows after-tax contributions. Contact HR/plan administrator.",
                complexity="advanced",
                requires_professional=True,
                warnings=["Not all plans allow this", "Must convert quickly to avoid taxable gains"]
            ))
        
        # 13. SOLAR PANEL CREDIT
        if profile.interested_in_solar:
            solar_cost = 25000  # Average installation
            credit = solar_cost * 0.30  # 30% federal credit through 2032
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.ENERGY,
                title="☀️ Solar Panel Tax Credit (30%)",
                description="Install solar panels and receive a 30% federal tax credit through 2032. "
                           f"A typical ${solar_cost:,} installation = ${credit:,} tax credit! "
                           "Unlike deductions, credits reduce your tax bill dollar-for-dollar. "
                           "Many states offer additional incentives.",
                potential_tax_savings=credit,
                action_required="Get quotes from multiple solar installers. Check state/local incentives. "
                               "Install before Dec 31 for this year's credit.",
                deadline=year_end,
                complexity="intermediate",
                requires_professional=False,
                warnings=["Must have enough tax liability to use credit (can carry forward)"]
            ))
        
        # 14. ELECTRIC VEHICLE CREDIT
        if profile.interested_in_ev or profile.ev_purchase_planned:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.ENERGY,
                title="⚡ Electric Vehicle Tax Credit ($7,500)",
                description="Purchase a qualifying new electric vehicle and receive up to $7,500 federal tax "
                           "credit. Used EVs may qualify for up to $4,000. Income limits apply. "
                           "The credit can be taken at point of sale as a discount starting 2024.",
                potential_tax_savings=7500,
                action_required="Check vehicle eligibility on IRS website. Verify income limits. "
                               "Consider taking credit at dealer vs tax return.",
                deadline=year_end,
                complexity="basic",
                requires_professional=False,
                warnings=[
                    "Income limits: $150k single, $300k married",
                    "Price caps: $55k sedans, $80k SUVs/trucks",
                    "Must be new battery (not previously claimed)"
                ]
            ))
        
        # 15. HIRE YOUR KIDS
        if profile.has_side_business and profile.num_children_under_17 > 0:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.FAMILY,
                title="👨‍👩‍👧 Hire Your Children",
                description="If you have a sole proprietorship or single-member LLC, you can hire your "
                           "children (any age for simple tasks, 7+ for most work). Pay them up to the "
                           "standard deduction ($15,000 in 2025) - it's deductible to you, and they pay "
                           "ZERO income tax. Kids under 18 are also exempt from FICA taxes! "
                           "They can then contribute to a Roth IRA for tax-free growth.",
                potential_tax_savings=15000 * current_result.marginal_rate * profile.num_children_under_17,
                action_required="Document legitimate work performed. Pay reasonable wages. "
                               "Keep timesheets. Pay via check (not cash).",
                complexity="intermediate",
                requires_professional=True,
                warnings=[
                    "Work must be legitimate and age-appropriate",
                    "Wages must be reasonable for the work",
                    "Business must be sole proprietorship for FICA exemption"
                ]
            ))
        
        # 16. QUALIFIED BUSINESS INCOME (QBI) DEDUCTION
        if profile.self_employment_income > 0 or profile.has_side_business:
            qbi = profile.self_employment_income if profile.self_employment_income > 0 else 20000
            qbi_deduction = qbi * 0.20
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.BUSINESS,
                title="📊 Qualified Business Income (QBI) Deduction",
                description="As a self-employed person or business owner, you may qualify for the 20% QBI "
                           f"deduction. This means 20% of your net business income (${qbi_deduction:,.0f}) "
                           "is deducted from your taxable income. It's like getting a 20% discount on taxes!",
                potential_tax_savings=qbi_deduction * current_result.marginal_rate,
                action_required="Ensure you're tracking all business income and expenses. "
                               "The deduction is automatic on your return if you qualify.",
                complexity="intermediate",
                requires_professional=False,
                warnings=[
                    "Income limits for certain service businesses",
                    "May be limited by wages paid or property owned"
                ]
            ))
        
        # 17. HEALTH INSURANCE DEDUCTION (Self-Employed)
        if profile.self_employment_income > 0 and not profile.has_workplace_retirement_plan:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.HEALTHCARE,
                title="🏥 Self-Employed Health Insurance Deduction",
                description="If you're self-employed and not eligible for employer health coverage, "
                           "you can deduct 100% of health insurance premiums for yourself, spouse, "
                           "and dependents as an above-the-line deduction. A family plan costing "
                           "$15,000/year = $15,000 deduction!",
                potential_tax_savings=15000 * current_result.marginal_rate,
                action_required="Keep records of premium payments. Deduct on Schedule 1, not Schedule C.",
                complexity="basic",
                requires_professional=False
            ))
        
        # 18. SEP-IRA (Self-Employed)
        if profile.self_employment_income > 0 and profile.self_employment_income > 30000:
            se_income = profile.self_employment_income
            sep_limit = min(69000, se_income * 0.25)
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.RETIREMENT,
                title="💼 SEP-IRA (Up to $69,000)",
                description=f"As self-employed, you can contribute up to 25% of net self-employment income "
                           f"(max $69,000) to a SEP-IRA. With ${se_income:,.0f} in self-employment income, "
                           f"you could contribute up to ${sep_limit:,.0f}! This is MUCH more than 401(k) "
                           f"limits and can be opened and funded until your tax filing deadline.",
                potential_tax_savings=sep_limit * current_result.marginal_rate,
                action_required="Open a SEP-IRA at any brokerage (Fidelity, Schwab, Vanguard). "
                               "Can contribute until April 15 (or Oct 15 with extension).",
                deadline=date(self.current_date.year + 1, 4, 15),
                complexity="intermediate",
                requires_professional=False,
                warnings=["If you have employees, must contribute equal % for them too"]
            ))
        
        # 19. I-BONDS (Tax-Deferred Interest)
        if current_result.gross_income > 75000:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.LOW,
                category=RecommendationCategory.INVESTMENT,
                title="📈 I-Bonds (Tax-Advantaged Savings)",
                description="Series I Savings Bonds offer inflation-protected returns with TAX-DEFERRED "
                           "interest (up to 30 years). The interest is exempt from state/local tax, and "
                           "you can defer federal tax until redemption. If used for education, it may be "
                           "completely tax-free! Limit: $10,000/person/year.",
                potential_tax_savings=500 * current_result.marginal_rate,  # On $10k at 5%
                action_required="Purchase at TreasuryDirect.gov. Can buy $10,000 per person, "
                               "plus $5,000 with tax refund.",
                complexity="basic",
                requires_professional=False,
                warnings=["1-year minimum hold", "Lose 3 months interest if redeemed before 5 years"]
            ))
        
        # 20. 529 PLAN CONTRIBUTION
        if profile.num_dependents > 0 and not profile.has_529_plan:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.EDUCATION,
                title="🎓 529 Education Savings Plan",
                description="529 plans offer tax-free growth for education expenses. Many states offer "
                           "state tax deductions for contributions. Starting in 2024, unused 529 funds "
                           "can be rolled to a Roth IRA (up to $35,000 lifetime). It's like a Roth IRA "
                           "for education with potential state tax benefits!",
                potential_tax_savings=2000,  # Varies by state
                action_required="Open a 529 in your state (or any state with good investments). "
                               "Name child as beneficiary. Can change beneficiaries later.",
                complexity="basic",
                requires_professional=False,
                warnings=["State deductions vary", "Non-qualified withdrawals have penalties"]
            ))
        
        # 21. MARRIAGE TIMING STRATEGY
        if profile.filing_status == FilingStatus.SINGLE and profile.open_to_lifestyle_changes:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.LOW,
                category=RecommendationCategory.FAMILY,
                title="💒 Marriage Timing Strategy",
                description="If you're planning to get married, consider the tax implications. "
                           "The 'marriage bonus' benefits couples where one spouse earns significantly more. "
                           "The 'marriage penalty' affects couples with similar incomes. Getting married "
                           "on Dec 31 vs Jan 1 changes your ENTIRE year's filing status!",
                potential_tax_savings=3000,  # Varies widely
                action_required="Compare tax liability as single vs married filing jointly. "
                               "Time the wedding date strategically if significant difference.",
                complexity="intermediate",
                requires_professional=True,
                warnings=["Marriage penalty may apply if incomes are similar"]
            ))
        
        # 22. INCOME DEFERRAL (Timing Strategy)
        if current_result.gross_income > 100000 and days_remaining < 60:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.TIMING,
                title="⏰ Defer Income to Next Year",
                description="If you expect lower income next year (job change, retirement, sabbatical), "
                           "consider deferring year-end bonuses, contract payments, or business income "
                           "to January. This shifts income to a potentially lower tax bracket year.",
                potential_tax_savings=5000 * (current_result.marginal_rate - 0.22),
                action_required="Request bonus payment in January. Delay invoicing clients. "
                               "Defer capital gains realization.",
                deadline=year_end,
                complexity="intermediate",
                requires_professional=False,
                warnings=["Don't let tax tail wag the economic dog", "AMT may apply"]
            ))
        
        # 23. ACCELERATE DEDUCTIONS (Timing Strategy)
        if current_result.gross_income > 100000 and days_remaining < 60:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.TIMING,
                title="⚡ Accelerate Deductions to This Year",
                description="If you expect higher income next year, pull deductions into this year: "
                           "prepay property taxes, make January mortgage payment in December, "
                           "stock up on business supplies, prepay insurance premiums, "
                           "make charitable contributions before Dec 31.",
                potential_tax_savings=2000 * current_result.marginal_rate,
                action_required="Make extra mortgage payment. Prepay property taxes. "
                               "Purchase business supplies. Donate to charity.",
                deadline=year_end,
                complexity="basic",
                requires_professional=False,
                warnings=["SALT deduction capped at $10,000"]
            ))
        
        # 24. SOLO 401(K) VS SEP-IRA
        if profile.self_employment_income > 0 and profile.self_employment_income < 50000:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.RETIREMENT,
                title="🎯 Solo 401(k) (Better Than SEP for Lower Income)",
                description="For self-employed with income under ~$200k, a Solo 401(k) allows HIGHER "
                           "contributions than SEP-IRA. You can contribute both as employee ($23,500) "
                           "AND employer (25% of net SE income). Plus you can take loans from it "
                           "and make Roth contributions. Must open by Dec 31!",
                potential_tax_savings=23500 * current_result.marginal_rate,
                action_required="Open Solo 401(k) at Fidelity/Schwab by Dec 31. "
                               "Can fund until April 15 (or Oct 15 with extension).",
                deadline=year_end,
                complexity="intermediate",
                requires_professional=False,
                warnings=["Plan must be established by Dec 31", "Only for self-employed with no employees"]
            ))
        
        # 25. COST SEGREGATION STUDY
        if profile.owns_rental_property and profile.rental_property_value > 200000:
            property_value = profile.rental_property_value
            potential_first_year_deduction = property_value * 0.15  # Rough estimate
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.REAL_ESTATE,
                title="🔬 Cost Segregation Study",
                description=f"A cost segregation study reclassifies parts of your rental property "
                           f"(appliances, carpets, landscaping, etc.) from 27.5-year to 5/7/15-year "
                           f"depreciation. Combined with bonus depreciation, you could accelerate "
                           f"${potential_first_year_deduction:,.0f}+ in deductions to year one!",
                potential_tax_savings=potential_first_year_deduction * current_result.marginal_rate,
                implementation_cost=3000,  # Cost of study
                action_required="Hire a cost segregation specialist. Works for properties bought this year "
                               "OR retroactively for prior years.",
                complexity="advanced",
                requires_professional=True,
                warnings=["Depreciation recapture on sale", "May trigger AMT for some taxpayers"]
            ))
        
        # 26. SHORT-TERM RENTAL LOOPHOLE (STR)
        if profile.interested_in_real_estate and current_result.gross_income > 150000:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.HIGH,
                category=RecommendationCategory.REAL_ESTATE,
                title="🏠 Short-Term Rental Tax Loophole",
                description="Short-term rentals (avg stay <7 days) with 'material participation' "
                           "(100+ hours and more than anyone else) are NOT subject to passive activity "
                           "limits. Combined with cost segregation, you can generate MASSIVE losses "
                           "that offset W-2 income. A $400k property could create $100k+ in year-one losses!",
                potential_tax_savings=30000,  # Conservative
                action_required="Purchase property in good STR market. Materially participate (100+ hrs). "
                               "Get cost segregation study. Keep detailed time logs.",
                complexity="advanced",
                requires_professional=True,
                warnings=[
                    "Must materially participate (track ALL time)",
                    "Some cities restrict STRs",
                    "Significant management required"
                ]
            ))
        
        # 27. HSA AS STEALTH RETIREMENT ACCOUNT
        if profile.remaining_hsa_room > 0 and profile.age and profile.age < 55:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.RETIREMENT,
                title="🏦 HSA: The Ultimate Retirement Account",
                description="HSA is the ONLY triple-tax-advantaged account: contributions are deductible, "
                           "growth is tax-free, AND withdrawals for medical expenses are tax-free. "
                           "Pro tip: Pay medical expenses out-of-pocket, let HSA grow, and reimburse "
                           "yourself decades later (no deadline!). After age 65, withdrawals for any "
                           "purpose are penalty-free (just taxed like Traditional IRA).",
                potential_tax_savings=profile.remaining_hsa_room * current_result.marginal_rate,
                action_required="Max out HSA. Invest it (don't leave as cash). Pay medical expenses "
                               "out-of-pocket and save receipts. Reimburse yourself later.",
                deadline=date(self.current_date.year + 1, 4, 15),
                complexity="intermediate",
                requires_professional=False,
                warnings=["Must have HDHP insurance to contribute", "Keep receipts forever"]
            ))
        
        # 28. OPPORTUNITY ZONE INVESTING
        if profile.capital_gains_long > 50000 or profile.capital_gains_short > 50000:
            total_gains = profile.capital_gains_long + profile.capital_gains_short
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.INVESTMENT,
                title="🌆 Opportunity Zone Investment",
                description=f"You have ${total_gains:,.0f} in capital gains. By investing gains in a "
                           "Qualified Opportunity Zone Fund within 180 days of sale, you can: "
                           "1) DEFER the original gain until 2026, 2) REDUCE the gain by 10% if held 5+ years, "
                           "3) PAY ZERO TAX on appreciation if held 10+ years!",
                potential_tax_savings=total_gains * 0.15 + (total_gains * 0.5) * 0.20,  # Rough estimate
                action_required="Find Qualified Opportunity Zone Funds. Invest within 180 days of "
                               "realizing capital gains. Hold for 10+ years for max benefit.",
                complexity="advanced",
                requires_professional=True,
                warnings=[
                    "Must invest within 180 days of gain",
                    "Some benefits reduced after 2026",
                    "OZ investments can be risky"
                ]
            ))
        
        # 29. INSTALLMENT SALE
        if profile.capital_gains_long > 100000:
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.INVESTMENT,
                title="📅 Installment Sale (Spread Gains Over Years)",
                description="If selling appreciated property or business, structure as an installment sale "
                           "to spread gains over multiple years. This can keep you in lower tax brackets "
                           "each year instead of paying all gains in one year at the highest bracket.",
                potential_tax_savings=profile.capital_gains_long * 0.05,  # Bracket savings estimate
                action_required="Structure sale with payments over multiple years. "
                               "Report on Form 6252.",
                complexity="advanced",
                requires_professional=True,
                warnings=["Interest must be charged on deferred payments", "Risk of buyer default"]
            ))
        
        # 30. CHARITABLE REMAINDER TRUST
        if current_result.gross_income > 250000 and (profile.capital_gains_long > 100000 or profile.age and profile.age > 55):
            advanced_recs.append(TaxRecommendation(
                priority=RecommendationPriority.LOW,
                category=RecommendationCategory.CHARITABLE,
                title="🎗️ Charitable Remainder Trust (CRT)",
                description="Transfer appreciated assets to a CRT: get an immediate charitable deduction, "
                           "avoid capital gains tax, receive income for life or a term of years, and "
                           "the remainder goes to charity. Great for highly-appreciated assets you want "
                           "to sell without the tax hit.",
                potential_tax_savings=profile.capital_gains_long * 0.23 if profile.capital_gains_long else 25000,
                implementation_cost=5000,  # Legal setup
                action_required="Consult estate planning attorney. Determine CRT type (CRAT vs CRUT). "
                               "Select charity and income beneficiaries.",
                complexity="advanced",
                requires_professional=True,
                warnings=["Irrevocable - cannot undo", "Complex annual filings required", "Legal fees $2k-5k"]
            ))
        
        # Calculate max savings
        max_savings = sum(r.potential_tax_savings for r in basic_recs + advanced_recs)
        
        # Optimal projection (if all basic recs implemented)
        combined_changes = {}
        if profile.remaining_401k_room > 0:
            combined_changes['extra_401k_traditional'] = profile.remaining_401k_room
        if profile.remaining_hsa_room > 0:
            combined_changes['extra_hsa'] = profile.remaining_hsa_room
        
        if combined_changes:
            optimal_sim = self.simulator.run_simulation(combined_changes, "Optimal")
            optimal_owed = optimal_sim.simulated.refund_or_owed
        else:
            optimal_owed = current_result.refund_or_owed
        
        # Categorize by timing
        immediate = [r for r in basic_recs + advanced_recs 
                    if r.deadline and r.deadline <= date(self.current_date.year, 12, 31)]
        year_end = [r for r in basic_recs + advanced_recs 
                   if r.deadline and r.deadline > date(self.current_date.year, 12, 31)]
        next_year = [r for r in basic_recs + advanced_recs if not r.deadline]
        
        return RecommendationReport(
            profile_id=profile.profile_id,
            current_projected_owed=round(-current_result.refund_or_owed if is_owing else 0, 2),
            optimal_projected_owed=round(-optimal_owed if optimal_owed < 0 else 0, 2),
            max_potential_savings=round(max_savings, 2),
            basic_recommendations=basic_recs,
            advanced_recommendations=advanced_recs,
            days_until_year_end=days_remaining,
            remaining_pay_periods=remaining_periods,
            immediate_actions=immediate,
            year_end_actions=year_end,
            next_year_planning=next_year
        )


# =============================================================================
# INCOME PROJECTOR
# =============================================================================

class IncomeProjector:
    """
    Project annual income from partial-year data.
    """
    
    @staticmethod
    def project_annual_income(
        ytd_income: float,
        current_pay_period: int,
        pay_frequency: PayFrequency
    ) -> float:
        """
        Project annual income from YTD data.
        """
        total_periods = PAY_PERIODS_PER_YEAR[pay_frequency.value]
        if current_pay_period <= 0:
            return ytd_income
        
        return (ytd_income / current_pay_period) * total_periods
    
    @staticmethod
    def calculate_remaining_periods(
        current_date: date,
        pay_frequency: PayFrequency
    ) -> int:
        """
        Calculate remaining pay periods in the year.
        """
        year_end = date(current_date.year, 12, 31)
        days_remaining = (year_end - current_date).days
        
        days_per_period = {
            PayFrequency.WEEKLY: 7,
            PayFrequency.BIWEEKLY: 14,
            PayFrequency.SEMIMONTHLY: 15,
            PayFrequency.MONTHLY: 30,
        }
        
        period_days = days_per_period.get(pay_frequency, 14)
        return days_remaining // period_days
    
    @staticmethod
    def infer_pay_frequency_from_dates(pay_dates: List[date]) -> Optional[PayFrequency]:
        """
        Infer pay frequency from a list of pay dates.
        """
        if len(pay_dates) < 2:
            return None
        
        # Sort dates
        sorted_dates = sorted(pay_dates)
        
        # Calculate average gap
        gaps = []
        for i in range(1, len(sorted_dates)):
            gap = (sorted_dates[i] - sorted_dates[i-1]).days
            gaps.append(gap)
        
        avg_gap = sum(gaps) / len(gaps)
        
        # Determine frequency based on average gap
        if 5 <= avg_gap <= 9:
            return PayFrequency.WEEKLY
        elif 12 <= avg_gap <= 16:
            return PayFrequency.BIWEEKLY
        elif 13 <= avg_gap <= 17:
            return PayFrequency.SEMIMONTHLY
        elif 28 <= avg_gap <= 32:
            return PayFrequency.MONTHLY
        else:
            return PayFrequency.BIWEEKLY  # Default


# =============================================================================
# DEMO / TESTING
# =============================================================================

def demo():
    """Demonstrate the tax simulator."""
    
    print("=" * 60)
    print("TAX SIMULATOR DEMO")
    print("=" * 60)
    
    # Create a sample profile
    profile = UserFinancialProfile(
        filing_status=FilingStatus.SINGLE,
        age=35,
        ytd_income=85000,
        pay_frequency=PayFrequency.BIWEEKLY,
        current_pay_period=20,  # ~10 months into year
        ytd_federal_withheld=12000,
        ytd_401k_traditional=10000,
        ytd_hsa=2000,
        has_workplace_retirement_plan=True,
        hsa_coverage_type="individual"
    )
    
    print("\n--- PROFILE ---")
    print(f"Filing Status: {profile.filing_status.value}")
    print(f"YTD Income: ${profile.ytd_income:,.2f}")
    print(f"Projected Annual: ${profile.projected_annual_income:,.2f}")
    print(f"YTD 401(k): ${profile.ytd_401k_traditional:,.2f}")
    print(f"Remaining 401(k) Room: ${profile.remaining_401k_room:,.2f}")
    
    # Calculate tax
    calculator = TaxCalculator()
    result = calculator.calculate_tax(profile)
    
    print("\n--- TAX CALCULATION ---")
    print(f"Gross Income: ${result.gross_income:,.2f}")
    print(f"AGI: ${result.adjusted_gross_income:,.2f}")
    print(f"Taxable Income: ${result.taxable_income:,.2f}")
    print(f"Federal Tax: ${result.federal_tax:,.2f}")
    print(f"Total Tax: ${result.total_tax_liability:,.2f}")
    print(f"Total Withholding: ${result.total_payments_and_withholding:,.2f}")
    print(f"Refund/Owed: ${result.refund_or_owed:,.2f}")
    print(f"Effective Rate: {result.effective_rate:.1f}%")
    print(f"Marginal Rate: {result.marginal_rate*100:.0f}%")
    
    # Run simulation
    simulator = TaxSimulator(profile)
    sim_result = simulator.find_optimal_401k()
    
    print("\n--- SIMULATION: Max 401(k) ---")
    print(f"Additional 401(k): ${profile.remaining_401k_room:,.2f}")
    print(f"Tax Difference: ${sim_result.tax_difference:,.2f}")
    print(f"Is Beneficial: {sim_result.is_beneficial}")
    print(f"Summary: {sim_result.summary}")
    
    # Generate recommendations
    engine = RecommendationEngine()
    report = engine.generate_recommendations(profile)
    
    print("\n--- RECOMMENDATIONS ---")
    print(f"Days until year-end: {report.days_until_year_end}")
    print(f"Max potential savings: ${report.max_potential_savings:,.2f}")
    
    print("\nBasic Recommendations:")
    for rec in report.basic_recommendations[:3]:
        print(f"  - {rec.title}: ${rec.potential_tax_savings:,.2f} potential savings")
    
    print("\nAdvanced Recommendations:")
    for rec in report.advanced_recommendations[:2]:
        print(f"  - {rec.title}")


if __name__ == "__main__":
    demo()
