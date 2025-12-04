"""
TaxGuard AI - Enhanced Data Models
===================================
Extended models supporting:
- Multiple income sources (spouse, multiple jobs, 1099s)
- Multiple paystub tracking
- Proper YTD tax withholding tracking
- Multi-document support
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, computed_field, model_validator
from enum import Enum
import uuid

from tax_constants import (
    FilingStatus, 
    PAY_PERIODS_PER_YEAR, 
    STANDARD_DEDUCTION_2025,
    CONTRIBUTION_LIMITS_2025,
)


# =============================================================================
# ENUMS
# =============================================================================

class IncomeSourceType(str, Enum):
    W2_PRIMARY = "w2_primary"
    W2_SECONDARY = "w2_secondary"
    W2_SPOUSE = "w2_spouse"
    SELF_EMPLOYMENT = "self_employment"
    FORM_1099_NEC = "1099_nec"
    FORM_1099_MISC = "1099_misc"
    FORM_1099_INT = "1099_int"
    FORM_1099_DIV = "1099_div"
    FORM_1099_B = "1099_b"
    RENTAL_INCOME = "rental_income"
    OTHER = "other"


class PayFrequency(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


# =============================================================================
# INCOME SOURCE MODEL
# =============================================================================

class IncomeSource(BaseModel):
    """A single source of income with its own tracking."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_type: IncomeSourceType
    name: str = Field(description="Employer name or description (redacted)")
    
    # Pay information
    pay_frequency: PayFrequency = PayFrequency.BIWEEKLY
    current_pay_period: int = Field(default=1, ge=1)
    last_pay_date: Optional[date] = None
    
    # Current period amounts
    current_gross_pay: float = Field(default=0.0, ge=0)
    current_federal_withheld: float = Field(default=0.0, ge=0)
    current_state_withheld: float = Field(default=0.0, ge=0)
    current_ss_withheld: float = Field(default=0.0, ge=0)
    current_medicare_withheld: float = Field(default=0.0, ge=0)
    
    # Pre-tax deductions (current period)
    current_401k: float = Field(default=0.0, ge=0)
    current_hsa: float = Field(default=0.0, ge=0)
    current_fsa: float = Field(default=0.0, ge=0)
    current_other_pretax: float = Field(default=0.0, ge=0)
    
    # Year-to-date totals
    ytd_gross: float = Field(default=0.0, ge=0)
    ytd_federal_withheld: float = Field(default=0.0, ge=0)
    ytd_state_withheld: float = Field(default=0.0, ge=0)
    ytd_ss_withheld: float = Field(default=0.0, ge=0)
    ytd_medicare_withheld: float = Field(default=0.0, ge=0)
    ytd_401k: float = Field(default=0.0, ge=0)
    ytd_hsa: float = Field(default=0.0, ge=0)
    
    # For 1099 / self-employment
    is_self_employment: bool = False
    estimated_annual_amount: float = Field(default=0.0, ge=0)
    estimated_tax_payments: float = Field(default=0.0, ge=0)
    
    # Metadata
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    paystub_count: int = Field(default=0, ge=0)
    
    @computed_field
    @property
    def projected_annual_income(self) -> float:
        """Project annual income from YTD data."""
        if self.source_type in [IncomeSourceType.FORM_1099_INT, 
                                 IncomeSourceType.FORM_1099_DIV,
                                 IncomeSourceType.FORM_1099_B]:
            return self.estimated_annual_amount
        
        if self.ytd_gross > 0 and self.current_pay_period > 0:
            total_periods = PAY_PERIODS_PER_YEAR.get(self.pay_frequency.value, 26)
            return (self.ytd_gross / self.current_pay_period) * total_periods
        
        return self.estimated_annual_amount or self.ytd_gross
    
    @computed_field
    @property
    def projected_federal_withheld(self) -> float:
        """Project annual federal withholding from YTD data."""
        if self.ytd_federal_withheld > 0 and self.current_pay_period > 0:
            total_periods = PAY_PERIODS_PER_YEAR.get(self.pay_frequency.value, 26)
            return (self.ytd_federal_withheld / self.current_pay_period) * total_periods
        return self.ytd_federal_withheld


class SpouseIncome(BaseModel):
    """Spouse's income information (for married filing jointly)."""
    
    sources: List[IncomeSource] = Field(default_factory=list)
    age: Optional[int] = Field(default=None, ge=0, le=120)
    
    # Spouse's retirement contributions
    ytd_401k: float = Field(default=0.0, ge=0)
    ytd_ira: float = Field(default=0.0, ge=0)
    ytd_hsa: float = Field(default=0.0, ge=0)
    has_workplace_plan: bool = False
    
    @computed_field
    @property
    def total_ytd_income(self) -> float:
        return sum(s.ytd_gross for s in self.sources)
    
    @computed_field
    @property
    def total_projected_income(self) -> float:
        return sum(s.projected_annual_income for s in self.sources)
    
    @computed_field
    @property
    def total_ytd_federal_withheld(self) -> float:
        return sum(s.ytd_federal_withheld for s in self.sources)
    
    @computed_field
    @property
    def total_projected_federal_withheld(self) -> float:
        return sum(s.projected_federal_withheld for s in self.sources)


# =============================================================================
# INVESTMENT INCOME
# =============================================================================

class InvestmentIncome(BaseModel):
    """Investment and passive income details."""
    
    # Interest
    taxable_interest: float = Field(default=0.0, ge=0)
    tax_exempt_interest: float = Field(default=0.0, ge=0)
    
    # Dividends
    ordinary_dividends: float = Field(default=0.0, ge=0)
    qualified_dividends: float = Field(default=0.0, ge=0)
    
    # Capital gains/losses
    short_term_gains: float = Field(default=0.0)  # Can be negative (losses)
    short_term_losses: float = Field(default=0.0, ge=0)
    long_term_gains: float = Field(default=0.0)
    long_term_losses: float = Field(default=0.0, ge=0)
    
    # Carryover losses from prior years
    capital_loss_carryover: float = Field(default=0.0, ge=0)
    
    # Estimated tax payments on investment income
    estimated_payments: float = Field(default=0.0, ge=0)
    
    @computed_field
    @property
    def net_short_term(self) -> float:
        return self.short_term_gains - self.short_term_losses
    
    @computed_field
    @property
    def net_long_term(self) -> float:
        return self.long_term_gains - self.long_term_losses
    
    @computed_field
    @property
    def net_capital_gain_loss(self) -> float:
        net = self.net_short_term + self.net_long_term - self.capital_loss_carryover
        # Capital loss deduction limited to $3,000 per year
        if net < -3000:
            return -3000
        return net


# =============================================================================
# DEDUCTIONS
# =============================================================================

class ItemizedDeductions(BaseModel):
    """Itemized deduction details."""
    
    # State and local taxes (SALT) - capped at $10,000
    state_income_tax: float = Field(default=0.0, ge=0)
    property_tax: float = Field(default=0.0, ge=0)
    
    # Mortgage interest
    mortgage_interest: float = Field(default=0.0, ge=0)
    mortgage_points: float = Field(default=0.0, ge=0)
    
    # Charitable donations
    cash_donations: float = Field(default=0.0, ge=0)
    non_cash_donations: float = Field(default=0.0, ge=0)
    appreciated_stock_donations: float = Field(default=0.0, ge=0)
    
    # Medical expenses
    medical_expenses: float = Field(default=0.0, ge=0)
    
    # Other
    casualty_losses: float = Field(default=0.0, ge=0)
    other_deductions: float = Field(default=0.0, ge=0)
    
    @computed_field
    @property
    def salt_deduction(self) -> float:
        """SALT capped at $10,000."""
        return min(self.state_income_tax + self.property_tax, 10000)
    
    @computed_field
    @property
    def total_charitable(self) -> float:
        return self.cash_donations + self.non_cash_donations + self.appreciated_stock_donations
    
    def calculate_total(self, agi: float) -> float:
        """Calculate total itemized deductions."""
        total = 0.0
        
        # SALT (capped)
        total += self.salt_deduction
        
        # Mortgage interest
        total += self.mortgage_interest + self.mortgage_points
        
        # Charitable (limited to 60% of AGI for cash, 30% for property)
        max_charitable = agi * 0.60
        total += min(self.total_charitable, max_charitable)
        
        # Medical (only amount exceeding 7.5% of AGI)
        medical_threshold = agi * 0.075
        if self.medical_expenses > medical_threshold:
            total += self.medical_expenses - medical_threshold
        
        # Other
        total += self.casualty_losses + self.other_deductions
        
        return total


# =============================================================================
# ENHANCED USER FINANCIAL PROFILE
# =============================================================================

class EnhancedUserProfile(BaseModel):
    """
    Enhanced profile supporting multiple income sources.
    Properly tracks YTD taxes for refund/owed calculation.
    """
    
    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Filing Information
    filing_status: FilingStatus = FilingStatus.SINGLE
    age: Optional[int] = Field(default=None, ge=0, le=120)
    is_blind: bool = False
    
    # =========================================================================
    # MULTIPLE INCOME SOURCES
    # =========================================================================
    
    # Primary income sources (taxpayer)
    income_sources: List[IncomeSource] = Field(default_factory=list)
    
    # Spouse income (if married filing jointly)
    spouse: Optional[SpouseIncome] = None
    
    # Investment income
    investments: InvestmentIncome = Field(default_factory=InvestmentIncome)
    
    # Other income not from above
    other_income: float = Field(default=0.0, ge=0)
    other_income_description: str = ""
    
    # =========================================================================
    # RETIREMENT CONTRIBUTIONS (Combined household)
    # =========================================================================
    
    ytd_401k_traditional: float = Field(default=0.0, ge=0)
    ytd_401k_roth: float = Field(default=0.0, ge=0)
    ytd_ira_traditional: float = Field(default=0.0, ge=0)
    ytd_ira_roth: float = Field(default=0.0, ge=0)
    has_workplace_retirement_plan: bool = False
    
    # =========================================================================
    # HSA
    # =========================================================================
    
    ytd_hsa: float = Field(default=0.0, ge=0)
    hsa_coverage_type: str = Field(default="individual", pattern="^(individual|family)$")
    
    # =========================================================================
    # ESTIMATED TAX PAYMENTS
    # =========================================================================
    
    q1_estimated_payment: float = Field(default=0.0, ge=0)
    q2_estimated_payment: float = Field(default=0.0, ge=0)
    q3_estimated_payment: float = Field(default=0.0, ge=0)
    q4_estimated_payment: float = Field(default=0.0, ge=0)
    
    # =========================================================================
    # DEDUCTIONS
    # =========================================================================
    
    prefers_itemized: bool = False
    itemized_deductions: ItemizedDeductions = Field(default_factory=ItemizedDeductions)
    
    # =========================================================================
    # DEPENDENTS & CREDITS
    # =========================================================================
    
    num_dependents: int = Field(default=0, ge=0)
    num_children_under_17: int = Field(default=0, ge=0)
    num_children_17_to_24_student: int = Field(default=0, ge=0)
    childcare_expenses: float = Field(default=0.0, ge=0)
    education_expenses: float = Field(default=0.0, ge=0)
    
    # =========================================================================
    # BUSINESS OWNERSHIP (for advanced strategies)
    # =========================================================================
    
    owns_business: bool = False
    business_entity_type: Optional[str] = None  # sole_prop, llc, s_corp, c_corp
    business_income: float = Field(default=0.0, ge=0)
    business_expenses: float = Field(default=0.0, ge=0)
    
    # =========================================================================
    # REAL ESTATE (for advanced strategies)
    # =========================================================================
    
    owns_rental_property: bool = False
    rental_income: float = Field(default=0.0, ge=0)
    rental_expenses: float = Field(default=0.0, ge=0)
    rental_depreciation: float = Field(default=0.0, ge=0)
    
    # =========================================================================
    # COMPUTED PROPERTIES - INCOME
    # =========================================================================
    
    @computed_field
    @property
    def total_ytd_w2_income(self) -> float:
        """Total YTD W-2 income from all sources."""
        w2_types = [
            IncomeSourceType.W2_PRIMARY,
            IncomeSourceType.W2_SECONDARY,
            IncomeSourceType.W2_SPOUSE
        ]
        total = sum(
            s.ytd_gross for s in self.income_sources 
            if s.source_type in w2_types
        )
        if self.spouse:
            total += self.spouse.total_ytd_income
        return total
    
    @computed_field
    @property
    def total_projected_w2_income(self) -> float:
        """Projected annual W-2 income from all sources."""
        w2_types = [
            IncomeSourceType.W2_PRIMARY,
            IncomeSourceType.W2_SECONDARY,
            IncomeSourceType.W2_SPOUSE
        ]
        total = sum(
            s.projected_annual_income for s in self.income_sources 
            if s.source_type in w2_types
        )
        if self.spouse:
            total += self.spouse.total_projected_income
        return total
    
    @computed_field
    @property
    def total_self_employment_income(self) -> float:
        """Total self-employment income."""
        se_types = [
            IncomeSourceType.SELF_EMPLOYMENT,
            IncomeSourceType.FORM_1099_NEC
        ]
        return sum(
            s.projected_annual_income for s in self.income_sources 
            if s.source_type in se_types
        ) + self.business_income - self.business_expenses
    
    @computed_field
    @property
    def total_investment_income(self) -> float:
        """Total investment income."""
        return (
            self.investments.taxable_interest +
            self.investments.ordinary_dividends +
            max(0, self.investments.net_capital_gain_loss)  # Only if net gain
        )
    
    @computed_field
    @property
    def total_gross_income(self) -> float:
        """Total projected gross income from all sources."""
        return (
            self.total_projected_w2_income +
            self.total_self_employment_income +
            self.total_investment_income +
            max(0, self.rental_income - self.rental_expenses) +
            self.other_income
        )
    
    # =========================================================================
    # COMPUTED PROPERTIES - WITHHOLDING & PAYMENTS
    # =========================================================================
    
    @computed_field
    @property
    def total_ytd_federal_withheld(self) -> float:
        """Total YTD federal tax withheld from ALL sources."""
        total = sum(s.ytd_federal_withheld for s in self.income_sources)
        if self.spouse:
            total += self.spouse.total_ytd_federal_withheld
        return total
    
    @computed_field
    @property
    def total_projected_federal_withheld(self) -> float:
        """Projected annual federal withholding from ALL sources."""
        total = sum(s.projected_federal_withheld for s in self.income_sources)
        if self.spouse:
            total += self.spouse.total_projected_federal_withheld
        return total
    
    @computed_field
    @property
    def total_estimated_payments(self) -> float:
        """Total estimated tax payments made."""
        return (
            self.q1_estimated_payment +
            self.q2_estimated_payment +
            self.q3_estimated_payment +
            self.q4_estimated_payment +
            self.investments.estimated_payments
        )
    
    @computed_field
    @property
    def total_payments_and_withholding(self) -> float:
        """Total of all withholding and estimated payments."""
        return self.total_projected_federal_withheld + self.total_estimated_payments
    
    # =========================================================================
    # COMPUTED PROPERTIES - DEDUCTIONS & LIMITS
    # =========================================================================
    
    @computed_field
    @property
    def standard_deduction(self) -> float:
        """Calculate standard deduction including age/blind adjustments."""
        base = STANDARD_DEDUCTION_2025.get(self.filing_status, 15000)
        additional = 0
        
        # Age 65+ additional
        if self.age and self.age >= 65:
            if self.filing_status in [FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD]:
                additional += 1950
            else:
                additional += 1550
        
        # Spouse age 65+
        if self.spouse and self.spouse.age and self.spouse.age >= 65:
            additional += 1550
        
        # Blindness
        if self.is_blind:
            if self.filing_status in [FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD]:
                additional += 1950
            else:
                additional += 1550
        
        return base + additional
    
    @computed_field
    @property
    def remaining_401k_room(self) -> float:
        """Remaining 401(k) contribution room."""
        limit = CONTRIBUTION_LIMITS_2025["401k_employee"]
        if self.age and self.age >= 50:
            if 60 <= self.age <= 63:
                limit += CONTRIBUTION_LIMITS_2025["401k_catch_up_60_to_63"]
            else:
                limit += CONTRIBUTION_LIMITS_2025["401k_catch_up_50_plus"]
        
        total_contributed = self.ytd_401k_traditional + self.ytd_401k_roth
        return max(0, limit - total_contributed)
    
    @computed_field
    @property
    def remaining_hsa_room(self) -> float:
        """Remaining HSA contribution room."""
        limit = (CONTRIBUTION_LIMITS_2025["hsa_family"] 
                if self.hsa_coverage_type == "family" 
                else CONTRIBUTION_LIMITS_2025["hsa_individual"])
        if self.age and self.age >= 55:
            limit += CONTRIBUTION_LIMITS_2025["hsa_catch_up_55_plus"]
        return max(0, limit - self.ytd_hsa)
    
    # =========================================================================
    # METHODS
    # =========================================================================
    
    def add_income_source(self, source: IncomeSource):
        """Add a new income source."""
        self.income_sources.append(source)
        self.updated_at = datetime.utcnow()
    
    def update_from_paystub(self, source_id: str, paystub_data: Dict[str, Any]):
        """Update an income source from paystub data."""
        for source in self.income_sources:
            if source.id == source_id:
                for key, value in paystub_data.items():
                    if hasattr(source, key):
                        setattr(source, key, value)
                source.paystub_count += 1
                source.last_updated = datetime.utcnow()
                break
        self.updated_at = datetime.utcnow()
    
    def get_source_by_type(self, source_type: IncomeSourceType) -> Optional[IncomeSource]:
        """Get first income source of a specific type."""
        for source in self.income_sources:
            if source.source_type == source_type:
                return source
        return None
    
    def get_all_sources_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all income sources."""
        summary = []
        for source in self.income_sources:
            summary.append({
                "id": source.id,
                "name": source.name,
                "type": source.source_type.value,
                "ytd_income": source.ytd_gross,
                "projected_annual": source.projected_annual_income,
                "ytd_withheld": source.ytd_federal_withheld,
                "projected_withheld": source.projected_federal_withheld
            })
        
        if self.spouse:
            for source in self.spouse.sources:
                summary.append({
                    "id": source.id,
                    "name": f"Spouse: {source.name}",
                    "type": source.source_type.value,
                    "ytd_income": source.ytd_gross,
                    "projected_annual": source.projected_annual_income,
                    "ytd_withheld": source.ytd_federal_withheld,
                    "projected_withheld": source.projected_federal_withheld
                })
        
        return summary


# =============================================================================
# QUICK PROFILE CREATION
# =============================================================================

def create_simple_profile(
    filing_status: str = "single",
    age: int = 35,
    ytd_income: float = 0,
    ytd_withheld: float = 0,
    pay_frequency: str = "biweekly",
    current_period: int = 1
) -> EnhancedUserProfile:
    """Create a simple profile with one income source."""
    
    profile = EnhancedUserProfile(
        filing_status=FilingStatus(filing_status),
        age=age
    )
    
    primary_source = IncomeSource(
        source_type=IncomeSourceType.W2_PRIMARY,
        name="Primary Employer",
        pay_frequency=PayFrequency(pay_frequency),
        current_pay_period=current_period,
        ytd_gross=ytd_income,
        ytd_federal_withheld=ytd_withheld
    )
    
    profile.add_income_source(primary_source)
    
    return profile


def create_married_profile(
    taxpayer_income: float,
    taxpayer_withheld: float,
    spouse_income: float,
    spouse_withheld: float,
    **kwargs
) -> EnhancedUserProfile:
    """Create a married filing jointly profile with two incomes."""
    
    profile = EnhancedUserProfile(
        filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
        **kwargs
    )
    
    # Taxpayer income
    primary = IncomeSource(
        source_type=IncomeSourceType.W2_PRIMARY,
        name="Primary Employer",
        ytd_gross=taxpayer_income,
        ytd_federal_withheld=taxpayer_withheld,
        pay_frequency=PayFrequency.BIWEEKLY,
        current_pay_period=kwargs.get('current_period', 20)
    )
    profile.add_income_source(primary)
    
    # Spouse income
    spouse_source = IncomeSource(
        source_type=IncomeSourceType.W2_SPOUSE,
        name="Spouse Employer",
        ytd_gross=spouse_income,
        ytd_federal_withheld=spouse_withheld,
        pay_frequency=PayFrequency.BIWEEKLY,
        current_pay_period=kwargs.get('current_period', 20)
    )
    
    profile.spouse = SpouseIncome(
        sources=[spouse_source],
        age=kwargs.get('spouse_age')
    )
    
    return profile
