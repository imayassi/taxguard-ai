"""
TaxGuard AI - Advanced Tax Strategies Engine
=============================================
Life-changing tax optimization strategies that most people don't know about.

These recommendations go beyond typical "max your 401k" advice to include:
- Business formation strategies
- Real estate opportunities
- Advanced retirement account maneuvers
- Income shifting techniques
- Timing strategies
- Major life decision impacts
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from tax_constants import (
    FilingStatus,
    CONTRIBUTION_LIMITS_2025,
    STANDARD_DEDUCTION_2025,
    get_marginal_rate,
)


# =============================================================================
# STRATEGY CATEGORIES
# =============================================================================

class StrategyCategory(str, Enum):
    BUSINESS_FORMATION = "business_formation"
    REAL_ESTATE = "real_estate"
    RETIREMENT_ADVANCED = "retirement_advanced"
    INCOME_SHIFTING = "income_shifting"
    TIMING_STRATEGIES = "timing_strategies"
    CHARITABLE_ADVANCED = "charitable_advanced"
    FAMILY_STRATEGIES = "family_strategies"
    INVESTMENT_STRATEGIES = "investment_strategies"
    CREDITS_INCENTIVES = "credits_incentives"
    LIFESTYLE_CHANGES = "lifestyle_changes"
    STATE_OPTIMIZATION = "state_optimization"


class StrategyComplexity(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class StrategyTimeframe(str, Enum):
    IMMEDIATE = "immediate"
    YEAR_END = "year_end"
    NEXT_YEAR = "next_year"
    LONG_TERM = "long_term"


@dataclass
class AdvancedStrategy:
    """A single advanced tax strategy recommendation."""
    
    id: str
    title: str
    category: StrategyCategory
    complexity: StrategyComplexity
    timeframe: StrategyTimeframe
    
    summary: str
    detailed_explanation: str
    how_it_works: str
    
    estimated_annual_savings: float = 0.0
    one_time_savings: float = 0.0
    lifetime_savings_potential: float = 0.0
    
    minimum_income: float = 0.0
    maximum_income: float = float('inf')
    requires_business: bool = False
    requires_real_estate: bool = False
    requires_self_employment: bool = False
    
    steps_to_implement: List[str] = field(default_factory=list)
    professionals_needed: List[str] = field(default_factory=list)
    estimated_setup_cost: float = 0.0
    ongoing_costs: float = 0.0
    
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    
    audit_risk_level: int = 1
    is_life_changing: bool = False
    life_change_description: str = ""


def get_all_advanced_strategies() -> List[AdvancedStrategy]:
    """Return the complete library of advanced tax strategies."""
    
    strategies = []
    
    # =========================================================================
    # BUSINESS FORMATION STRATEGIES
    # =========================================================================
    
    strategies.append(AdvancedStrategy(
        id="side_business_schedule_c",
        title="Start a Side Business (Schedule C)",
        category=StrategyCategory.BUSINESS_FORMATION,
        complexity=StrategyComplexity.MODERATE,
        timeframe=StrategyTimeframe.IMMEDIATE,
        summary="Turn a hobby or skill into a legitimate business to unlock massive deductions.",
        detailed_explanation="Starting a side business is one of the most powerful tax strategies. Even a small business creates significant deductions that can offset your W-2 income. Common businesses: consulting, freelancing, e-commerce, content creation, tutoring, photography.",
        how_it_works="1) Start earning ANY income from a legitimate business 2) All business expenses become deductible 3) Business losses can offset W-2 income 4) Opens door to Solo 401k, SEP-IRA 5) Qualifies for 20% QBI deduction",
        estimated_annual_savings=5000,
        is_life_changing=True,
        life_change_description="Becoming a business owner changes your entire tax situation and opens up dozens of new deductions.",
        steps_to_implement=[
            "Identify a monetizable skill or hobby",
            "Register your business (LLC recommended)",
            "Get an EIN from the IRS (free, 5 minutes)",
            "Open a separate business bank account",
            "Track all business expenses",
            "Make some revenue (even $1 makes it legitimate)"
        ],
        professionals_needed=["CPA for tax planning"],
        estimated_setup_cost=500,
        pros=["Unlock home office, vehicle, equipment deductions", "QBI deduction (20% of business income)", "Access to Solo 401(k)", "Business losses offset W-2 income"],
        cons=["Requires legitimate business activity", "Additional bookkeeping", "Self-employment tax on profits"],
        audit_risk_level=2
    ))
    
    strategies.append(AdvancedStrategy(
        id="s_corp_election",
        title="S-Corp Election for SE Tax Savings",
        category=StrategyCategory.BUSINESS_FORMATION,
        complexity=StrategyComplexity.ADVANCED,
        timeframe=StrategyTimeframe.NEXT_YEAR,
        summary="Convert your business to S-Corp to save thousands in self-employment taxes.",
        detailed_explanation="If your business profit exceeds $50k+, an S-Corp election can save significant self-employment taxes. Instead of paying 15.3% SE tax on all profits, you only pay it on a 'reasonable salary' and take the rest as distributions.",
        how_it_works="Form LLC, elect S-Corp (Form 2553), pay yourself reasonable salary (subject to payroll taxes), take remaining profits as distributions (no SE tax!). Example: $100k profit, $50k salary = save ~$7,650 in SE taxes.",
        estimated_annual_savings=7500,
        minimum_income=50000,
        requires_self_employment=True,
        steps_to_implement=["Calculate if S-Corp makes sense ($50k+ profit)", "Form LLC", "File Form 2553 for S-Corp election", "Set up payroll", "Determine reasonable salary"],
        professionals_needed=["CPA", "Payroll service"],
        estimated_setup_cost=1500,
        ongoing_costs=2000,
        pros=["Significant SE tax savings", "Still get QBI deduction", "Flexible profit distributions"],
        cons=["Must pay reasonable salary", "Payroll complexity", "More expensive tax prep"],
        audit_risk_level=3
    ))
    
    strategies.append(AdvancedStrategy(
        id="section_179_vehicle",
        title="Section 179 Vehicle Deduction",
        category=StrategyCategory.BUSINESS_FORMATION,
        complexity=StrategyComplexity.MODERATE,
        timeframe=StrategyTimeframe.YEAR_END,
        summary="Buy a vehicle over 6,000 lbs for business and deduct up to $28,900 (or 100% for heavy trucks).",
        detailed_explanation="Section 179 allows business owners to deduct the full purchase price of qualifying vehicles in Year 1. Vehicles over 6,000 lbs GVWR have generous limits. Popular vehicles: Land Rover, Mercedes G-Wagon, Ford F-250+, Chevy Suburban.",
        how_it_works="1) Purchase vehicle with GVWR over 6,000 lbs 2) Use >50% for business 3) Deduct up to $28,900 in Year 1 for SUVs 4) For trucks/vans over 14,000 lbs: deduct 100%!",
        estimated_annual_savings=10000,
        requires_business=True,
        steps_to_implement=["Verify legitimate business use (>50%)", "Check vehicle GVWR (door sticker)", "Purchase before Dec 31", "Keep detailed mileage log", "Claim Section 179 on Form 4562"],
        professionals_needed=["CPA"],
        pros=["Massive first-year deduction", "Works for new or used", "Combines with bonus depreciation"],
        cons=["Must have business need", "Depreciation recapture if sold", "Vehicle must be >6,000 lbs"],
        audit_risk_level=3,
        is_life_changing=True,
        life_change_description="Can essentially get a significant portion of a luxury vehicle paid for by tax savings."
    ))
    
    strategies.append(AdvancedStrategy(
        id="hire_your_kids",
        title="Hire Your Children in Your Business",
        category=StrategyCategory.FAMILY_STRATEGIES,
        complexity=StrategyComplexity.MODERATE,
        timeframe=StrategyTimeframe.IMMEDIATE,
        summary="Pay your children for legitimate work and shift income to their 0% tax bracket.",
        detailed_explanation="If you own a business, hire your children for legitimate work. Wages are deductible to your business and may be tax-free to your children. For sole proprietorships: children under 18 are exempt from FICA taxes!",
        how_it_works="1) Hire child for legitimate work (filing, cleaning, social media) 2) Pay reasonable wages 3) No FICA for kids under 18 (sole prop) 4) Child can earn up to $14,600 tax-free 5) Child can contribute to Roth IRA!",
        estimated_annual_savings=5000,
        requires_business=True,
        steps_to_implement=["Document job duties appropriate for age", "Pay reasonable wages", "Keep time records", "Issue W-2 or 1099", "Open custodial Roth IRA for child"],
        professionals_needed=["CPA"],
        pros=["Shift income to lower bracket", "No FICA if under 18", "Child can fund Roth IRA", "Teaches work ethic"],
        cons=["Work must be legitimate", "Wages must be reasonable", "If S-Corp, FICA still applies"],
        audit_risk_level=2,
        is_life_changing=True,
        life_change_description="Can fund children's Roth IRAs that will grow tax-free for 50+ years."
    ))
    
    strategies.append(AdvancedStrategy(
        id="augusta_rule",
        title="Augusta Rule (Rent Home to Business)",
        category=StrategyCategory.BUSINESS_FORMATION,
        complexity=StrategyComplexity.MODERATE,
        timeframe=StrategyTimeframe.IMMEDIATE,
        summary="Rent your home to your business for up to 14 days/year—income is tax-free to you.",
        detailed_explanation="Section 280A(g) allows you to rent your home for up to 14 days per year without reporting the income. If you have a business, rent your home for meetings, and the rent is deductible to the business.",
        how_it_works="1) Your business holds meetings/events 2) Rent home to business at fair market rate 3) Deductible to business 4) Tax-free to you (up to 14 days) 5) Example: 14 days × $500/day = $7,000 tax-free",
        estimated_annual_savings=3000,
        requires_business=True,
        steps_to_implement=["Document fair market rental rates", "Keep records of each business event", "Create rental agreement", "Record meeting minutes", "Pay rent from business to personal"],
        professionals_needed=["CPA"],
        pros=["Tax-free income to you", "Deductible to business", "Legal and IRS-approved"],
        cons=["Must have legitimate business purpose", "Rental rate must be reasonable", "Limited to 14 days"],
        audit_risk_level=3
    ))
    
    # =========================================================================
    # REAL ESTATE STRATEGIES
    # =========================================================================
    
    strategies.append(AdvancedStrategy(
        id="rental_property",
        title="Buy Rental Property for Depreciation",
        category=StrategyCategory.REAL_ESTATE,
        complexity=StrategyComplexity.ADVANCED,
        timeframe=StrategyTimeframe.LONG_TERM,
        summary="Generate paper losses through depreciation to offset income while building wealth.",
        detailed_explanation="Real estate is one of the most tax-advantaged investments. You can depreciate the building over 27.5 years, creating paper losses that offset rental income. Example: $300k building = $10,909/year in depreciation.",
        how_it_works="1) Purchase rental property 2) Deduct mortgage interest, taxes, insurance, repairs 3) Depreciate building over 27.5 years 4) Paper 'losses' offset rental income 5) Losses can carry forward until sale",
        estimated_annual_savings=8000,
        lifetime_savings_potential=200000,
        requires_real_estate=True,
        steps_to_implement=["Research real estate markets", "Get pre-approved for investment loan", "Consider house hacking first", "Set up LLC structure", "Consider cost segregation study"],
        professionals_needed=["CPA", "Real Estate Attorney", "Property Manager"],
        estimated_setup_cost=5000,
        pros=["Depreciation creates paper losses", "Mortgage interest deductible", "1031 exchange for tax-free swaps", "Rental income in retirement"],
        cons=["Passive activity loss limitations", "Depreciation recapture on sale", "Property management work"],
        is_life_changing=True,
        life_change_description="Building a rental portfolio can create tax-advantaged passive income for life.",
        audit_risk_level=2
    ))
    
    strategies.append(AdvancedStrategy(
        id="real_estate_professional",
        title="Real Estate Professional Status",
        category=StrategyCategory.REAL_ESTATE,
        complexity=StrategyComplexity.EXPERT,
        timeframe=StrategyTimeframe.LONG_TERM,
        summary="Qualify as Real Estate Professional to deduct rental losses against W-2 income.",
        detailed_explanation="Normally, rental losses are 'passive' and only offset passive income. If you qualify as a Real Estate Professional (750+ hours), losses become non-passive and offset ALL income. This is how high earners show 'losses'.",
        how_it_works="Requirements: 750+ hours/year in real estate, more than half your work time in RE, materially participate in each property. If you qualify, rental losses (including depreciation) offset ALL income types.",
        estimated_annual_savings=30000,
        minimum_income=150000,
        requires_real_estate=True,
        steps_to_implement=["Track ALL real estate hours", "Consider 'real estate spouse' strategy", "Document material participation", "Work with experienced CPA"],
        professionals_needed=["CPA (RE specialist)", "Tax attorney"],
        pros=["Deduct rental losses against W-2", "Significant tax reduction", "Can reduce AGI"],
        cons=["750+ hours is substantial", "Heavily audited", "Meticulous documentation required"],
        audit_risk_level=5,
        is_life_changing=True,
        life_change_description="One spouse as RE Professional can save high-income family $50,000+ annually."
    ))
    
    strategies.append(AdvancedStrategy(
        id="cost_segregation",
        title="Cost Segregation Study",
        category=StrategyCategory.REAL_ESTATE,
        complexity=StrategyComplexity.EXPERT,
        timeframe=StrategyTimeframe.IMMEDIATE,
        summary="Accelerate depreciation on property from 27.5 years to 5-15 years.",
        detailed_explanation="A cost segregation study reclassifies building components (carpet, appliances, parking lots) from 27.5/39 year to 5, 7, or 15 year property. Example: $1M building, 30% reclassified = $180k in Year 1 deductions.",
        how_it_works="1) Engineer analyzes property 2) Reclassifies 20-40% to shorter lives 3) Take bonus depreciation (60%) on short-life assets 4) Massive first-year deductions",
        estimated_annual_savings=50000,
        one_time_savings=100000,
        minimum_income=100000,
        requires_real_estate=True,
        steps_to_implement=["Purchase commercial/rental property ($500k+)", "Hire cost segregation firm", "Receive study ($5-15k)", "Can amend prior years!"],
        professionals_needed=["Cost Segregation Engineer", "CPA"],
        estimated_setup_cost=10000,
        pros=["Massive first-year deductions", "Can look back and amend", "Works for new or existing properties"],
        cons=["Cost of study ($5-15k)", "Recapture on sale", "Best for $500k+ properties"],
        audit_risk_level=2
    ))
    
    # =========================================================================
    # RETIREMENT ADVANCED
    # =========================================================================
    
    strategies.append(AdvancedStrategy(
        id="solo_401k",
        title="Solo 401(k) for Self-Employed",
        category=StrategyCategory.RETIREMENT_ADVANCED,
        complexity=StrategyComplexity.MODERATE,
        timeframe=StrategyTimeframe.YEAR_END,
        summary="Contribute up to $69,000/year to retirement if you have any self-employment income.",
        detailed_explanation="A Solo 401(k) allows self-employed with no employees to contribute as both employee AND employer. Employee: $23,500 + $7,500 catch-up. Employer: 25% of net SE income. Total: $69,000 ($76,500 if 50+).",
        how_it_works="Establish Solo 401(k) by Dec 31, contribute until tax filing deadline. Free at Fidelity, Schwab, Vanguard. Can make Roth contributions. Can take loans from plan.",
        estimated_annual_savings=15000,
        requires_self_employment=True,
        steps_to_implement=["Establish Solo 401(k) by Dec 31", "Calculate max contribution", "Choose Roth vs Traditional mix"],
        pros=["Much higher limits than IRA", "Roth option", "Loan provisions", "Catch-up for 50+"],
        cons=["Must be self-employed with no employees", "Contribution limited by SE income"],
        is_life_changing=True,
        life_change_description="A side hustle plus Solo 401(k) can turbocharge retirement savings.",
        audit_risk_level=1
    ))
    
    strategies.append(AdvancedStrategy(
        id="backdoor_roth",
        title="Backdoor Roth IRA Conversion",
        category=StrategyCategory.RETIREMENT_ADVANCED,
        complexity=StrategyComplexity.MODERATE,
        timeframe=StrategyTimeframe.IMMEDIATE,
        summary="High earners can still contribute to Roth IRA through the 'backdoor' method.",
        detailed_explanation="If income is too high for direct Roth contributions, make non-deductible Traditional IRA contributions and immediately convert to Roth. Legal and IRS-approved. Works at any income level.",
        how_it_works="1) Contribute $7,000 to Traditional IRA (non-deductible) 2) Immediately convert to Roth 3) Pay minimal tax on earnings 4) Future growth is 100% tax-free",
        estimated_annual_savings=2000,
        lifetime_savings_potential=100000,
        minimum_income=150000,
        steps_to_implement=["Check for existing Traditional IRA balances (pro-rata rule!)", "Contribute non-deductible to Traditional", "Convert to Roth within days", "File Form 8606"],
        professionals_needed=["CPA (recommended)"],
        pros=["Roth access at any income", "Tax-free growth forever", "No RMDs"],
        cons=["Pro-rata rule complicates if you have other IRA funds", "Only $7,000/year"],
        audit_risk_level=1
    ))
    
    strategies.append(AdvancedStrategy(
        id="mega_backdoor_roth",
        title="Mega Backdoor Roth (After-Tax 401k)",
        category=StrategyCategory.RETIREMENT_ADVANCED,
        complexity=StrategyComplexity.ADVANCED,
        timeframe=StrategyTimeframe.IMMEDIATE,
        summary="Contribute up to $69,000/year to Roth using after-tax 401(k) contributions.",
        detailed_explanation="If your 401(k) allows after-tax contributions AND in-service conversions, you can contribute up to $69,000/year to Roth accounts. Max regular 401(k), then contribute after-tax and convert to Roth.",
        how_it_works="1) Max regular 401(k) ($23,500) 2) Add employer match 3) Contribute after-tax up to $69k total 4) Convert after-tax to Roth immediately 5) Massive Roth accumulation",
        estimated_annual_savings=10000,
        lifetime_savings_potential=500000,
        minimum_income=200000,
        steps_to_implement=["Check if 401(k) allows after-tax contributions", "Check if in-service conversions allowed", "Set up automatic contributions", "Convert ASAP"],
        professionals_needed=["CPA", "401(k) administrator"],
        pros=["Massive Roth contributions", "Tax-free growth", "Works for high earners"],
        cons=["Not all 401(k)s allow this", "Complex setup"],
        is_life_changing=True,
        life_change_description="Can accumulate $1M+ in tax-free Roth funds over a career.",
        audit_risk_level=1
    ))
    
    # =========================================================================
    # CHARITABLE STRATEGIES
    # =========================================================================
    
    strategies.append(AdvancedStrategy(
        id="donor_advised_fund",
        title="Donor Advised Fund (DAF) Bunching",
        category=StrategyCategory.CHARITABLE_ADVANCED,
        complexity=StrategyComplexity.SIMPLE,
        timeframe=StrategyTimeframe.YEAR_END,
        summary="Bunch multiple years of donations into one year to exceed standard deduction.",
        detailed_explanation="If itemized deductions are close to standard deduction, 'bunch' 3-5 years of donations into one year using a DAF. Itemize that year, standard deduction other years.",
        how_it_works="1) Open DAF (Fidelity, Schwab - free) 2) Contribute 3-5 years of donations 3) Get full deduction THIS year 4) Take standard deduction other years 5) Distribute to charities over time",
        estimated_annual_savings=3000,
        steps_to_implement=["Calculate if bunching makes sense", "Open DAF", "Contribute cash or appreciated stock", "Get immediate deduction", "Distribute later"],
        pros=["Itemize in bunching year", "Contribute appreciated stock", "Investments grow tax-free in DAF"],
        cons=["Must front-load donations", "Money committed to charity"],
        audit_risk_level=1
    ))
    
    strategies.append(AdvancedStrategy(
        id="donate_appreciated_stock",
        title="Donate Appreciated Stock",
        category=StrategyCategory.CHARITABLE_ADVANCED,
        complexity=StrategyComplexity.SIMPLE,
        timeframe=StrategyTimeframe.YEAR_END,
        summary="Donate stock with gains—deduct full value, pay zero capital gains tax.",
        detailed_explanation="Instead of selling stock, paying capital gains, and donating cash—donate the stock directly. You get deduction for FULL value and avoid ALL capital gains tax. Extra benefit: more to charity OR more in your pocket.",
        how_it_works="Stock with $10k gains: Selling = pay $1,500 cap gains, donate $8,500. Donating stock = deduct full value, pay $0 gains. Save $1,500+.",
        estimated_annual_savings=2000,
        steps_to_implement=["Identify appreciated stock held 1+ year", "Contact charity for instructions", "Transfer stock directly (don't sell!)", "Deduct full market value"],
        pros=["Avoid all capital gains tax", "Full FMV deduction", "More efficient than cash"],
        cons=["Stock must be held 1+ year", "Some charities don't accept stock"],
        audit_risk_level=1
    ))
    
    strategies.append(AdvancedStrategy(
        id="qcd",
        title="Qualified Charitable Distribution (QCD)",
        category=StrategyCategory.CHARITABLE_ADVANCED,
        complexity=StrategyComplexity.SIMPLE,
        timeframe=StrategyTimeframe.YEAR_END,
        summary="If 70½+, donate IRA money directly to charity—counts as RMD, not taxable.",
        detailed_explanation="For those 70½+, transfer up to $105,000/year directly from IRA to charity. Counts toward RMD but is NOT included in taxable income. Better than taking RMD and deducting donation.",
        how_it_works="1) Must be 70½+ 2) Direct transfer from IRA to charity 3) Up to $105,000/year 4) Satisfies RMD 5) NOT taxable income",
        estimated_annual_savings=5000,
        steps_to_implement=["Request QCD from IRA custodian", "Check payable to charity (not you)", "Keep acknowledgment", "Report correctly"],
        pros=["Reduces taxable income", "Satisfies RMD", "Keeps AGI low"],
        cons=["Must be 70½+", "Must go directly to charity"],
        audit_risk_level=1
    ))
    
    # =========================================================================
    # CREDITS AND INCENTIVES
    # =========================================================================
    
    strategies.append(AdvancedStrategy(
        id="ev_credit",
        title="Electric Vehicle Tax Credit",
        category=StrategyCategory.CREDITS_INCENTIVES,
        complexity=StrategyComplexity.SIMPLE,
        timeframe=StrategyTimeframe.IMMEDIATE,
        summary="Get up to $7,500 for new EV or $4,000 for used EV.",
        detailed_explanation="New EVs: up to $7,500 credit. Used EVs: up to $4,000. Can transfer to dealer for immediate discount. Must meet income limits ($150k single, $300k married for new).",
        how_it_works="1) Buy qualifying EV 2) Check income limits 3) Transfer to dealer or claim on return",
        estimated_annual_savings=7500,
        one_time_savings=7500,
        maximum_income=300000,
        steps_to_implement=["Check vehicle qualifies (fueleconomy.gov)", "Verify income limits", "Decide dealer transfer or return"],
        pros=["Substantial credit", "Immediate discount option", "Reduces fuel costs"],
        cons=["Income limits", "Price limits", "Not all EVs qualify"],
        audit_risk_level=1
    ))
    
    strategies.append(AdvancedStrategy(
        id="energy_credits",
        title="Home Energy Efficiency Credits",
        category=StrategyCategory.CREDITS_INCENTIVES,
        complexity=StrategyComplexity.SIMPLE,
        timeframe=StrategyTimeframe.IMMEDIATE,
        summary="Get 30% credit for solar, heat pumps, insulation, windows, etc.",
        detailed_explanation="Energy Efficient Home Improvement Credit: 30% of costs, up to $3,200/year. Residential Clean Energy Credit: 30% of solar, battery, geothermal (NO limit!). Heat pumps: 30% up to $2,000. Insulation/windows: 30% up to $1,200.",
        how_it_works="Purchase qualifying improvements, keep receipts, file Form 5695. Solar has no cap!",
        estimated_annual_savings=3000,
        steps_to_implement=["Identify needed improvements", "Verify efficiency requirements", "Keep receipts", "File Form 5695"],
        pros=["Substantial credits", "Reduces energy bills", "Solar has no cap"],
        cons=["Must be primary residence", "Annual limits on some items"],
        audit_risk_level=1
    ))
    
    # =========================================================================
    # STATE OPTIMIZATION
    # =========================================================================
    
    strategies.append(AdvancedStrategy(
        id="no_income_tax_state",
        title="Relocate to No-Income-Tax State",
        category=StrategyCategory.STATE_OPTIMIZATION,
        complexity=StrategyComplexity.ADVANCED,
        timeframe=StrategyTimeframe.LONG_TERM,
        summary="Moving to TX, FL, NV, etc. can save high earners $30,000+ annually.",
        detailed_explanation="Nine states have no income tax: AK, FL, NV, NH, SD, TN, TX, WA, WY. California top rate: 13.3%. If you earn $500k, moving from CA to TX saves ~$66,500/year!",
        how_it_works="Research no-tax states, establish true domicile (license, voter registration, home), be aware of exit rules from CA/NY.",
        estimated_annual_savings=30000,
        minimum_income=250000,
        steps_to_implement=["Research states that fit lifestyle", "Consider cost of living", "Establish true domicile", "Beware CA/NY exit audits"],
        professionals_needed=["Tax attorney (if leaving CA/NY)"],
        pros=["Significant tax savings", "Savings compound", "Remote work makes easier"],
        cons=["Major life disruption", "Different climate/lifestyle", "Exit taxes possible"],
        is_life_changing=True,
        life_change_description="A well-planned move can save $1M+ in taxes over a career for high earners.",
        audit_risk_level=4
    ))
    
    strategies.append(AdvancedStrategy(
        id="timing_strategy",
        title="Strategic Income/Deduction Timing",
        category=StrategyCategory.TIMING_STRATEGIES,
        complexity=StrategyComplexity.MODERATE,
        timeframe=StrategyTimeframe.YEAR_END,
        summary="Shift income and deductions between years to minimize total taxes.",
        detailed_explanation="If you can control income timing (bonuses, freelance) or prepay deductions (property tax, mortgage), strategic timing can keep you in lower brackets.",
        how_it_works="Higher income next year? Accelerate income this year. Lower income next year? Defer income. Bunch deductions. Prepay January mortgage in December.",
        estimated_annual_savings=5000,
        steps_to_implement=["Project income for current and next year", "Identify flexible income", "Identify prepayable deductions", "Model scenarios"],
        professionals_needed=["CPA"],
        pros=["No cost to implement", "Can significantly reduce taxes"],
        cons=["Requires income flexibility", "Tax law changes create uncertainty"],
        audit_risk_level=1
    ))
    
    return strategies


class AdvancedStrategyRecommender:
    """Recommends advanced tax strategies based on user's situation."""
    
    def __init__(self):
        self.strategies = get_all_advanced_strategies()
    
    def get_applicable_strategies(
        self,
        projected_income: float,
        filing_status: FilingStatus,
        has_business: bool = False,
        has_real_estate: bool = False,
        is_self_employed: bool = False,
        age: Optional[int] = None,
        owns_home: bool = False,
        has_children: bool = False,
        marginal_rate: float = 0.22
    ) -> List[AdvancedStrategy]:
        """Get strategies applicable to user's situation."""
        applicable = []
        
        for strategy in self.strategies:
            if projected_income < strategy.minimum_income:
                continue
            if projected_income > strategy.maximum_income:
                continue
            if strategy.requires_business and not has_business:
                if strategy.id != "side_business_schedule_c":
                    continue
            if strategy.requires_real_estate and not has_real_estate:
                continue
            if strategy.requires_self_employment and not is_self_employed:
                if strategy.id not in ["side_business_schedule_c", "solo_401k"]:
                    continue
            if strategy.id == "qcd" and (age is None or age < 70):
                continue
            
            # Estimate savings based on marginal rate
            strategy.estimated_annual_savings = self._estimate_savings(strategy, projected_income, marginal_rate)
            applicable.append(strategy)
        
        applicable.sort(key=lambda s: s.estimated_annual_savings + s.one_time_savings, reverse=True)
        return applicable
    
    def _estimate_savings(self, strategy: AdvancedStrategy, income: float, rate: float) -> float:
        """Estimate savings based on marginal rate."""
        if strategy.id == "side_business_schedule_c":
            return 10000 * rate
        elif strategy.id == "s_corp_election":
            return min((income - 60000) * 0.153 * 0.5, 15000) if income > 100000 else 5000
        elif strategy.id == "section_179_vehicle":
            return 28900 * rate
        elif strategy.id == "hire_your_kids":
            return 14600 * rate + 14600 * 0.153
        elif strategy.id == "solo_401k":
            return min(69000, income * 0.25 + 23500) * rate
        elif strategy.id == "no_income_tax_state":
            return income * 0.10 if income > 250000 else income * 0.05
        return strategy.estimated_annual_savings
    
    def get_life_changing_strategies(self) -> List[AdvancedStrategy]:
        """Get strategies marked as life-changing."""
        return [s for s in self.strategies if s.is_life_changing]
    
    def generate_report(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive strategy report."""
        strategies = self.get_applicable_strategies(
            projected_income=profile_data.get('projected_income', 0),
            filing_status=profile_data.get('filing_status', FilingStatus.SINGLE),
            has_business=profile_data.get('has_business', False),
            has_real_estate=profile_data.get('has_real_estate', False),
            is_self_employed=profile_data.get('is_self_employed', False),
            age=profile_data.get('age'),
            owns_home=profile_data.get('owns_home', False),
            has_children=profile_data.get('has_children', False),
            marginal_rate=profile_data.get('marginal_rate', 0.22)
        )
        
        return {
            "total_strategies": len(strategies),
            "total_potential_savings": sum(s.estimated_annual_savings for s in strategies[:10]),
            "life_changing": [s for s in strategies if s.is_life_changing][:5],
            "immediate_actions": [s for s in strategies if s.timeframe == StrategyTimeframe.IMMEDIATE][:5],
            "top_5": strategies[:5],
            "all_strategies": strategies
        }
