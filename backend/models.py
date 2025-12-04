"""
TaxGuard AI - Data Models
=========================
Pydantic models for standardizing financial data from various sources.

These models serve as the contract between:
- OCR/document extraction
- LLM processing
- Tax calculation engine
- Frontend display
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator, computed_field
import uuid

from tax_constants import FilingStatus, PAY_PERIODS_PER_YEAR


# =============================================================================
# ENUMS
# =============================================================================

class DocumentType(str, Enum):
    PAYSTUB = "paystub"
    W2 = "w2"
    FORM_1040 = "form_1040"
    FORM_1099_NEC = "form_1099_nec"
    FORM_1099_INT = "form_1099_int"
    FORM_1099_DIV = "form_1099_div"
    FORM_1099_B = "form_1099_b"
    UNKNOWN = "unknown"


class PayFrequency(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    REDACTING = "redacting"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"


class RecommendationPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RecommendationCategory(str, Enum):
    RETIREMENT = "retirement"
    HEALTHCARE = "healthcare"
    WITHHOLDING = "withholding"
    INVESTMENT = "investment"
    CHARITABLE = "charitable"
    TIMING = "timing"
    BUSINESS = "business"  # New: side business, LLC
    REAL_ESTATE = "real_estate"  # New: rental, depreciation
    EDUCATION = "education"  # New: 529 plans
    ENERGY = "energy"  # New: solar, EV credits
    FAMILY = "family"  # New: hiring family, dependent care
    GENERAL = "general"


# =============================================================================
# INCOME SOURCE MODEL (for multiple jobs/spouses)
# =============================================================================

class IncomeSource(BaseModel):
    """
    Individual income source for supporting multiple jobs, spouse income, 
    1099 work, rental properties, etc.
    """
    source_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str = "Primary Job"
    source_type: str = Field(
        default="w2",
        pattern="^(w2|1099|self_employment|rental|investment|other)$"
    )
    owner: str = Field(
        default="taxpayer",
        pattern="^(taxpayer|spouse)$",
        description="Who earns this income"
    )
    
    # Income details
    ytd_income: float = Field(default=0.0, ge=0)
    pay_frequency: PayFrequency = PayFrequency.BIWEEKLY
    current_pay_period: int = Field(default=1, ge=1)
    last_pay_date: Optional[date] = None
    
    # Withholding for this source
    ytd_federal_withheld: float = Field(default=0.0, ge=0)
    ytd_state_withheld: float = Field(default=0.0, ge=0)
    ytd_social_security: float = Field(default=0.0, ge=0)
    ytd_medicare: float = Field(default=0.0, ge=0)
    
    # Pre-tax deductions for this source
    ytd_401k_traditional: float = Field(default=0.0, ge=0)
    ytd_401k_roth: float = Field(default=0.0, ge=0)
    ytd_hsa: float = Field(default=0.0, ge=0)
    ytd_fsa: float = Field(default=0.0, ge=0)
    
    # Employer match info
    employer_401k_match_percent: float = Field(default=0.0, ge=0, le=100)
    employer_401k_match_limit: float = Field(default=0.0, ge=0)
    
    # For rental income
    rental_expenses: float = Field(default=0.0, ge=0)
    depreciation: float = Field(default=0.0, ge=0)
    mortgage_interest_rental: float = Field(default=0.0, ge=0)
    
    # For self-employment
    business_expenses: float = Field(default=0.0, ge=0)
    home_office_sqft: float = Field(default=0.0, ge=0)
    vehicle_business_miles: float = Field(default=0.0, ge=0)
    
    @computed_field
    @property
    def projected_annual_income(self) -> float:
        """Project annual income based on YTD and pay period."""
        if self.source_type in ["w2", "1099"]:
            total_periods = PAY_PERIODS_PER_YEAR.get(self.pay_frequency.value, 26)
            if self.current_pay_period > 0:
                return (self.ytd_income / self.current_pay_period) * total_periods
        return self.ytd_income
    
    @computed_field
    @property
    def projected_annual_withholding(self) -> float:
        """Project annual federal withholding."""
        if self.source_type == "w2":
            total_periods = PAY_PERIODS_PER_YEAR.get(self.pay_frequency.value, 26)
            if self.current_pay_period > 0:
                return (self.ytd_federal_withheld / self.current_pay_period) * total_periods
        return self.ytd_federal_withheld
    
    @computed_field
    @property
    def net_rental_income(self) -> float:
        """Net rental income after expenses and depreciation."""
        if self.source_type == "rental":
            return max(0, self.ytd_income - self.rental_expenses - self.depreciation - self.mortgage_interest_rental)
        return 0.0
    
    @computed_field
    @property
    def net_self_employment_income(self) -> float:
        """Net self-employment income after expenses."""
        if self.source_type == "self_employment":
            home_office_deduction = self.home_office_sqft * 5  # Simplified method: $5/sqft up to 300 sqft
            vehicle_deduction = self.vehicle_business_miles * 0.67  # 2025 rate estimate
            return max(0, self.ytd_income - self.business_expenses - min(home_office_deduction, 1500) - vehicle_deduction)
        return 0.0


# =============================================================================
# DOCUMENT PROCESSING MODELS
# =============================================================================

class RedactedDocument(BaseModel):
    """
    Represents a document after PII has been stripped.
    This is what gets sent to the LLM - NEVER the original.
    """
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_filename: str
    document_type: DocumentType
    redacted_text: str = Field(description="Text with all PII replaced by tokens")
    redaction_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of tokens to redaction types (NOT original values)"
    )
    pii_found: List[str] = Field(
        default_factory=list,
        description="Types of PII found (e.g., 'SSN', 'NAME'), not the values"
    )
    extraction_confidence: float = Field(
        default=0.0, 
        ge=0.0, 
        le=1.0,
        description="OCR confidence score"
    )
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "abc123",
                "original_filename": "paystub_oct.pdf",
                "document_type": "paystub",
                "redacted_text": "[USER_NAME] earned $5,000.00 gross pay...",
                "redaction_map": {"[USER_NAME]": "PERSON", "[SSN_1]": "SSN"},
                "pii_found": ["SSN", "NAME", "ADDRESS"],
                "extraction_confidence": 0.95
            }
        }


# =============================================================================
# FINANCIAL DATA MODELS
# =============================================================================

class PaystubData(BaseModel):
    """Structured data extracted from a single paystub."""
    
    # Pay period info
    pay_date: Optional[date] = None
    pay_period_start: Optional[date] = None
    pay_period_end: Optional[date] = None
    pay_frequency: Optional[PayFrequency] = None
    
    # Current period earnings
    gross_pay: float = Field(default=0.0, ge=0)
    net_pay: float = Field(default=0.0, ge=0)
    
    # Current period deductions
    federal_tax_withheld: float = Field(default=0.0, ge=0)
    state_tax_withheld: float = Field(default=0.0, ge=0)
    social_security_withheld: float = Field(default=0.0, ge=0)
    medicare_withheld: float = Field(default=0.0, ge=0)
    
    # Pre-tax deductions (current period)
    pre_tax_401k: float = Field(default=0.0, ge=0)
    pre_tax_hsa: float = Field(default=0.0, ge=0)
    pre_tax_fsa: float = Field(default=0.0, ge=0)
    pre_tax_other: float = Field(default=0.0, ge=0)
    
    # Year-to-date totals
    ytd_gross: float = Field(default=0.0, ge=0)
    ytd_federal_tax: float = Field(default=0.0, ge=0)
    ytd_state_tax: float = Field(default=0.0, ge=0)
    ytd_social_security: float = Field(default=0.0, ge=0)
    ytd_medicare: float = Field(default=0.0, ge=0)
    ytd_401k: float = Field(default=0.0, ge=0)
    ytd_hsa: float = Field(default=0.0, ge=0)
    
    # Extraction metadata
    extraction_confidence: float = Field(default=0.0, ge=0, le=1)
    fields_inferred: List[str] = Field(default_factory=list)
    
    @field_validator('pay_frequency', mode='before')
    @classmethod
    def normalize_pay_frequency(cls, v):
        if v is None:
            return None
        if isinstance(v, PayFrequency):
            return v
        v_lower = str(v).lower().replace("-", "").replace("_", "").replace(" ", "")
        mapping = {
            "weekly": PayFrequency.WEEKLY,
            "biweekly": PayFrequency.BIWEEKLY,
            "everyotherweek": PayFrequency.BIWEEKLY,
            "every2weeks": PayFrequency.BIWEEKLY,
            "semimonthly": PayFrequency.SEMIMONTHLY,
            "twiceamonth": PayFrequency.SEMIMONTHLY,
            "monthly": PayFrequency.MONTHLY,
            "quarterly": PayFrequency.QUARTERLY,
            "annually": PayFrequency.ANNUALLY,
            "yearly": PayFrequency.ANNUALLY
        }
        return mapping.get(v_lower, PayFrequency.BIWEEKLY)


class W2Data(BaseModel):
    """Structured data from a W-2 form."""
    
    tax_year: int
    employer_name_token: str = "[EMPLOYER]"  # Redacted
    employer_ein_token: str = "[EIN]"  # Redacted
    
    # Box values
    box_1_wages: float = Field(default=0.0, description="Wages, tips, other compensation")
    box_2_federal_withheld: float = Field(default=0.0, description="Federal income tax withheld")
    box_3_ss_wages: float = Field(default=0.0, description="Social security wages")
    box_4_ss_tax: float = Field(default=0.0, description="Social security tax withheld")
    box_5_medicare_wages: float = Field(default=0.0, description="Medicare wages and tips")
    box_6_medicare_tax: float = Field(default=0.0, description="Medicare tax withheld")
    box_10_dependent_care: float = Field(default=0.0, description="Dependent care benefits")
    box_11_nonqualified_plans: float = Field(default=0.0)
    box_12_codes: Dict[str, float] = Field(default_factory=dict, description="Box 12 code:amount pairs")
    box_13_statutory: bool = False
    box_13_retirement_plan: bool = False
    box_13_third_party_sick: bool = False
    box_14_other: Dict[str, float] = Field(default_factory=dict)
    
    # State info (boxes 15-17)
    state_code: Optional[str] = None
    state_wages: float = Field(default=0.0)
    state_tax_withheld: float = Field(default=0.0)


class Form1040Summary(BaseModel):
    """Key figures from a prior year 1040 for simulation."""
    
    tax_year: int
    filing_status: FilingStatus
    
    # Income
    total_income: float = Field(default=0.0)
    adjusted_gross_income: float = Field(default=0.0)
    taxable_income: float = Field(default=0.0)
    
    # Deductions
    used_standard_deduction: bool = True
    total_deductions: float = Field(default=0.0)
    itemized_breakdown: Optional[Dict[str, float]] = None
    
    # Tax
    total_tax: float = Field(default=0.0)
    total_payments: float = Field(default=0.0)
    refund_or_owed: float = Field(default=0.0)
    
    # Adjustments used
    ira_deduction: float = Field(default=0.0)
    student_loan_interest: float = Field(default=0.0)
    hsa_deduction: float = Field(default=0.0)


# =============================================================================
# USER FINANCIAL PROFILE - CORE MODEL
# =============================================================================

class UserFinancialProfile(BaseModel):
    """
    The standardized profile that unifies data from multiple sources.
    This is the primary data structure used for tax calculations.
    
    Supports multiple income sources (multiple jobs, spouse income, 1099s, rental, etc.)
    """
    
    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Personal Info (no PII - just tax-relevant flags)
    filing_status: FilingStatus = FilingStatus.SINGLE
    age: Optional[int] = Field(default=None, ge=0, le=120)
    spouse_age: Optional[int] = Field(default=None, ge=0, le=120)
    num_dependents: int = Field(default=0, ge=0)
    num_children_under_17: int = Field(default=0, ge=0)
    is_blind: bool = False
    spouse_is_blind: bool = False
    
    # ==========================================================================
    # MULTIPLE INCOME SOURCES - supports spouse, multiple jobs, 1099, rental
    # ==========================================================================
    income_sources: List[IncomeSource] = Field(default_factory=list)
    
    # Legacy single-source fields (for backward compatibility)
    # These will be auto-populated from income_sources if empty
    ytd_income: float = Field(default=0.0, ge=0, description="Year-to-date gross income")
    pay_frequency: PayFrequency = PayFrequency.BIWEEKLY
    current_pay_period: int = Field(default=1, ge=1, description="Which pay period we're in")
    last_pay_date: Optional[date] = None
    
    # Projected figures (calculated)
    projected_annual_income: float = Field(default=0.0, ge=0)
    
    # Other Income (non-employment)
    interest_income: float = Field(default=0.0, ge=0)
    dividend_income: float = Field(default=0.0, ge=0)
    qualified_dividends: float = Field(default=0.0, ge=0)
    capital_gains_short: float = Field(default=0.0, ge=0)
    capital_gains_long: float = Field(default=0.0, ge=0)
    self_employment_income: float = Field(default=0.0, ge=0)
    rental_income: float = Field(default=0.0, ge=0)
    rental_expenses: float = Field(default=0.0, ge=0)
    other_income: float = Field(default=0.0, ge=0)
    
    # Withholding - Current Year
    ytd_federal_withheld: float = Field(default=0.0, ge=0)
    ytd_state_withheld: float = Field(default=0.0, ge=0)
    estimated_payments_made: float = Field(default=0.0, ge=0)
    
    # Retirement Contributions - Current Year (combined for all sources)
    ytd_401k_traditional: float = Field(default=0.0, ge=0)
    ytd_401k_roth: float = Field(default=0.0, ge=0)
    ytd_ira_traditional: float = Field(default=0.0, ge=0)
    ytd_ira_roth: float = Field(default=0.0, ge=0)
    has_workplace_retirement_plan: bool = False
    
    # Health Savings
    ytd_hsa: float = Field(default=0.0, ge=0)
    hsa_coverage_type: Optional[str] = Field(default="individual", pattern="^(individual|family)$")
    hsa_eligible: bool = True
    
    # Deduction Preferences
    prefers_itemized: bool = False
    mortgage_interest: float = Field(default=0.0, ge=0)
    state_local_taxes_paid: float = Field(default=0.0, ge=0)
    charitable_donations: float = Field(default=0.0, ge=0)
    medical_expenses: float = Field(default=0.0, ge=0)
    
    # Business/Side Hustle (for advanced recommendations)
    has_side_business: bool = False
    side_business_income: float = Field(default=0.0, ge=0)
    side_business_expenses: float = Field(default=0.0, ge=0)
    home_office_sqft: float = Field(default=0.0, ge=0)
    business_vehicle_miles: float = Field(default=0.0, ge=0)
    
    # Real Estate (for advanced recommendations)
    owns_rental_property: bool = False
    rental_property_value: float = Field(default=0.0, ge=0)
    interested_in_real_estate: bool = False
    
    # Education
    has_529_plan: bool = False
    education_expenses: float = Field(default=0.0, ge=0)
    student_loan_interest: float = Field(default=0.0, ge=0)
    
    # Energy Credits
    interested_in_solar: bool = False
    interested_in_ev: bool = False
    ev_purchase_planned: bool = False
    
    # Risk tolerance for advanced strategies
    risk_tolerance: str = Field(default="moderate", pattern="^(conservative|moderate|aggressive)$")
    open_to_lifestyle_changes: bool = True
    
    # Calculated standard deduction
    standard_deduction: float = Field(default=0.0, ge=0)
    
    # State
    state_of_residence: Optional[str] = Field(default=None, max_length=2)
    
    # Source tracking
    data_sources: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0, le=1)
    last_document_processed: Optional[str] = None
    
    @model_validator(mode='after')
    def calculate_projections(self):
        """Auto-calculate projected values based on YTD data and income sources."""
        from tax_constants import PAY_PERIODS_PER_YEAR, STANDARD_DEDUCTION_2025
        
        # =======================================================================
        # AGGREGATE INCOME FROM MULTIPLE SOURCES
        # =======================================================================
        if self.income_sources:
            # Sum up YTD income from all sources
            total_ytd_income = sum(s.ytd_income for s in self.income_sources)
            total_ytd_withheld = sum(s.ytd_federal_withheld for s in self.income_sources)
            total_ytd_401k = sum(s.ytd_401k_traditional for s in self.income_sources)
            total_ytd_hsa = sum(s.ytd_hsa for s in self.income_sources)
            
            # Update legacy fields if they're at default
            if self.ytd_income == 0:
                self.ytd_income = total_ytd_income
            if self.ytd_federal_withheld == 0:
                self.ytd_federal_withheld = total_ytd_withheld
            if self.ytd_401k_traditional == 0:
                self.ytd_401k_traditional = total_ytd_401k
            if self.ytd_hsa == 0:
                self.ytd_hsa = total_ytd_hsa
            
            # Calculate projected annual income from all sources
            total_projected = sum(s.projected_annual_income for s in self.income_sources)
            self.projected_annual_income = total_projected
        else:
            # Single source: use legacy calculation
            total_periods = PAY_PERIODS_PER_YEAR.get(self.pay_frequency.value, 26)
            if self.current_pay_period > 0 and self.ytd_income > 0:
                self.projected_annual_income = (self.ytd_income / self.current_pay_period) * total_periods
        
        # Calculate standard deduction
        base_deduction = STANDARD_DEDUCTION_2025.get(self.filing_status, 15000)
        additional = 0
        
        # Add additional deduction for age 65+
        if self.age and self.age >= 65:
            if self.filing_status in [FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD]:
                additional += 1950
            else:
                additional += 1550
        
        if self.spouse_age and self.spouse_age >= 65:
            additional += 1550
        
        # Add for blindness
        if self.is_blind:
            if self.filing_status in [FilingStatus.SINGLE, FilingStatus.HEAD_OF_HOUSEHOLD]:
                additional += 1950
            else:
                additional += 1550
        
        if self.spouse_is_blind:
            additional += 1550
        
        self.standard_deduction = base_deduction + additional
        
        return self
    
    @computed_field
    @property
    def total_ytd_retirement_contributions(self) -> float:
        """Total pre-tax retirement contributions YTD."""
        return self.ytd_401k_traditional + self.ytd_ira_traditional
    
    @computed_field
    @property
    def projected_annual_withholding(self) -> float:
        """
        Project total federal withholding to year-end.
        This is CRITICAL for determining if user will owe or get refund.
        """
        if self.income_sources:
            return sum(s.projected_annual_withholding for s in self.income_sources)
        else:
            # Single source projection
            total_periods = PAY_PERIODS_PER_YEAR.get(self.pay_frequency.value, 26)
            if self.current_pay_period > 0:
                return (self.ytd_federal_withheld / self.current_pay_period) * total_periods
            return self.ytd_federal_withheld
    
    @computed_field
    @property
    def total_income_sources(self) -> int:
        """Number of income sources."""
        return len(self.income_sources) if self.income_sources else 1
    
    @computed_field
    @property
    def taxpayer_income(self) -> float:
        """Total income for primary taxpayer."""
        if self.income_sources:
            return sum(s.projected_annual_income for s in self.income_sources if s.owner == "taxpayer")
        return self.projected_annual_income
    
    @computed_field
    @property
    def spouse_income(self) -> float:
        """Total income for spouse (if married)."""
        if self.income_sources:
            return sum(s.projected_annual_income for s in self.income_sources if s.owner == "spouse")
        return 0.0
    
    @computed_field
    @property
    def has_self_employment(self) -> bool:
        """Check if any income source is self-employment."""
        if self.income_sources:
            return any(s.source_type == "self_employment" for s in self.income_sources)
        return self.self_employment_income > 0 or self.has_side_business
    
    @computed_field
    @property
    def remaining_401k_room(self) -> float:
        """Remaining 401k contribution room for the year."""
        from tax_constants import CONTRIBUTION_LIMITS_2025
        limit = CONTRIBUTION_LIMITS_2025["401k_employee"]
        if self.age and self.age >= 50:
            if self.age >= 60 and self.age <= 63:
                limit += CONTRIBUTION_LIMITS_2025["401k_catch_up_60_to_63"]
            else:
                limit += CONTRIBUTION_LIMITS_2025["401k_catch_up_50_plus"]
        return max(0, limit - self.ytd_401k_traditional)
    
    @computed_field
    @property
    def remaining_hsa_room(self) -> float:
        """Remaining HSA contribution room for the year."""
        from tax_constants import CONTRIBUTION_LIMITS_2025
        if self.hsa_coverage_type == "family":
            limit = CONTRIBUTION_LIMITS_2025["hsa_family"]
        else:
            limit = CONTRIBUTION_LIMITS_2025["hsa_individual"]
        if self.age and self.age >= 55:
            limit += CONTRIBUTION_LIMITS_2025["hsa_catch_up_55_plus"]
        return max(0, limit - self.ytd_hsa)


# =============================================================================
# TAX CALCULATION RESULTS
# =============================================================================

class TaxBracketBreakdown(BaseModel):
    """Details of tax calculation per bracket."""
    bracket_start: float
    bracket_end: float
    rate: float
    income_in_bracket: float
    tax_in_bracket: float


class TaxResult(BaseModel):
    """Complete tax calculation result."""
    
    # Income summary
    gross_income: float
    adjustments: float
    adjusted_gross_income: float
    deduction_type: str = "standard"
    deduction_amount: float
    taxable_income: float
    
    # Tax calculation
    federal_tax: float
    bracket_breakdown: List[TaxBracketBreakdown]
    marginal_rate: float
    effective_rate: float
    
    # Self-employment tax (if applicable)
    self_employment_tax: float = 0.0
    
    # Credits
    child_tax_credit: float = 0.0
    other_credits: float = 0.0
    total_credits: float = 0.0
    
    # Final amounts
    total_tax_liability: float
    total_payments_and_withholding: float
    
    # The key number
    refund_or_owed: float = Field(description="Positive = refund, Negative = owed")
    
    # Metadata
    tax_year: int = 2025
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    is_projection: bool = True


# =============================================================================
# SIMULATION MODELS
# =============================================================================

class SimulationChange(BaseModel):
    """A single change to apply in a simulation."""
    field: str
    value: float
    description: str


class SimulationScenario(BaseModel):
    """A named scenario with multiple changes."""
    name: str
    description: str
    changes: List[SimulationChange]


class SimulationResult(BaseModel):
    """Result of a tax simulation."""
    
    scenario_name: str
    baseline: TaxResult
    simulated: TaxResult
    
    # Differences
    tax_difference: float = Field(description="Negative = savings")
    refund_difference: float
    effective_rate_change: float
    
    # Analysis
    is_beneficial: bool
    summary: str


# =============================================================================
# RECOMMENDATION MODELS
# =============================================================================

class TaxRecommendation(BaseModel):
    """A single tax optimization recommendation."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    priority: RecommendationPriority
    category: RecommendationCategory
    
    title: str
    description: str
    
    # Impact
    potential_tax_savings: float = Field(default=0.0, ge=0)
    implementation_cost: float = Field(default=0.0, ge=0)
    net_benefit: float = Field(default=0.0)
    
    # Action details
    action_required: str
    deadline: Optional[date] = None
    remaining_contribution_room: Optional[float] = None
    
    # Feasibility
    remaining_pay_periods: Optional[int] = None
    per_paycheck_amount: Optional[float] = None
    is_mathematically_feasible: bool = True
    
    # Complexity
    complexity: str = Field(default="basic", pattern="^(basic|intermediate|advanced)$")
    requires_professional: bool = False
    
    # Warnings
    warnings: List[str] = Field(default_factory=list)
    
    @computed_field
    @property
    def roi(self) -> Optional[float]:
        """Return on investment for this recommendation."""
        if self.implementation_cost > 0:
            return (self.potential_tax_savings / self.implementation_cost) * 100
        return None


class RecommendationReport(BaseModel):
    """Complete recommendation report for a user."""
    
    profile_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Summary
    current_projected_owed: float
    optimal_projected_owed: float
    max_potential_savings: float
    
    # Recommendations by category
    basic_recommendations: List[TaxRecommendation]
    advanced_recommendations: List[TaxRecommendation]
    
    # Time constraints
    days_until_year_end: int
    remaining_pay_periods: int
    
    # Actions prioritized by deadline
    immediate_actions: List[TaxRecommendation]
    year_end_actions: List[TaxRecommendation]
    next_year_planning: List[TaxRecommendation]


# =============================================================================
# API REQUEST/RESPONSE MODELS
# =============================================================================

class DocumentUploadRequest(BaseModel):
    """Request to upload a document for processing."""
    filename: str
    content_type: str
    document_type_hint: Optional[DocumentType] = None


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""
    document_id: str
    status: ProcessingStatus
    message: str


class ProfileUpdateRequest(BaseModel):
    """Request to manually update profile fields."""
    updates: Dict[str, Any]


class SimulationRequest(BaseModel):
    """Request to run a tax simulation."""
    profile_id: str
    changes: Dict[str, float]
    scenario_name: Optional[str] = "Custom Simulation"


class CalculationRequest(BaseModel):
    """Request for tax calculation."""
    profile_id: str
    include_recommendations: bool = True


class CalculationResponse(BaseModel):
    """Response with tax calculation and recommendations."""
    profile: UserFinancialProfile
    result: TaxResult
    recommendations: Optional[RecommendationReport] = None
