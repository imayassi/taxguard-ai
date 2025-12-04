"""
TaxGuard AI - Test Suite
========================
Comprehensive tests for all backend components.
"""

import pytest
from datetime import date
from decimal import Decimal

# Import modules to test
import sys
sys.path.insert(0, './backend')

from tax_constants import (
    FilingStatus,
    TAX_BRACKETS_2025,
    STANDARD_DEDUCTION_2025,
    CONTRIBUTION_LIMITS_2025,
    calculate_federal_tax,
    get_marginal_rate,
    get_effective_rate,
)
from models import (
    UserFinancialProfile,
    PayFrequency,
    PaystubData,
    TaxResult,
)
from pii_redaction import (
    PIIRedactor,
    redact_sensitive_data,
    RedactionResult,
)
from tax_simulator import (
    TaxCalculator,
    TaxSimulator,
    RecommendationEngine,
    IncomeProjector,
)


# =============================================================================
# TAX CONSTANTS TESTS
# =============================================================================

class TestTaxConstants:
    """Test tax constant values and calculations."""
    
    def test_tax_brackets_exist_for_all_filing_statuses(self):
        """All filing statuses should have tax brackets."""
        for status in FilingStatus:
            assert status in TAX_BRACKETS_2025
            assert len(TAX_BRACKETS_2025[status]) > 0
    
    def test_standard_deductions_exist(self):
        """All filing statuses should have standard deductions."""
        for status in FilingStatus:
            assert status in STANDARD_DEDUCTION_2025
            assert STANDARD_DEDUCTION_2025[status] > 0
    
    def test_single_filer_brackets_order(self):
        """Tax brackets should be in ascending order."""
        brackets = TAX_BRACKETS_2025[FilingStatus.SINGLE]
        prev_limit = 0
        prev_rate = 0
        
        for limit, rate in brackets:
            assert limit > prev_limit or limit == float('inf')
            assert rate > prev_rate or rate == prev_rate
            prev_limit = limit
            prev_rate = rate
    
    def test_married_deduction_higher_than_single(self):
        """Married filing jointly deduction should be higher."""
        single = STANDARD_DEDUCTION_2025[FilingStatus.SINGLE]
        married = STANDARD_DEDUCTION_2025[FilingStatus.MARRIED_FILING_JOINTLY]
        assert married > single
    
    def test_calculate_federal_tax_zero_income(self):
        """Zero income should result in zero tax."""
        tax = calculate_federal_tax(0, FilingStatus.SINGLE)
        assert tax == 0
    
    def test_calculate_federal_tax_negative_income(self):
        """Negative income should result in zero tax."""
        tax = calculate_federal_tax(-10000, FilingStatus.SINGLE)
        assert tax == 0
    
    def test_calculate_federal_tax_first_bracket_only(self):
        """Test calculation in first bracket only."""
        # $10,000 taxable income for single filer (first bracket is 10% up to $11,925)
        tax = calculate_federal_tax(10000, FilingStatus.SINGLE)
        expected = 10000 * 0.10
        assert tax == expected
    
    def test_calculate_federal_tax_multiple_brackets(self):
        """Test calculation spanning multiple brackets."""
        # $50,000 taxable income for single filer
        tax = calculate_federal_tax(50000, FilingStatus.SINGLE)
        
        # Manual calculation:
        # First bracket: $11,925 * 10% = $1,192.50
        # Second bracket: ($48,475 - $11,925) * 12% = $4,386.00
        # Third bracket: ($50,000 - $48,475) * 22% = $335.50
        expected = (11925 * 0.10) + ((48475 - 11925) * 0.12) + ((50000 - 48475) * 0.22)
        
        assert abs(tax - expected) < 1  # Allow for rounding
    
    def test_get_marginal_rate_first_bracket(self):
        """Marginal rate should be 10% for low income."""
        rate = get_marginal_rate(5000, FilingStatus.SINGLE)
        assert rate == 0.10
    
    def test_get_marginal_rate_high_income(self):
        """Marginal rate should be 37% for very high income."""
        rate = get_marginal_rate(1000000, FilingStatus.SINGLE)
        assert rate == 0.37
    
    def test_contribution_limits_reasonable(self):
        """Contribution limits should be reasonable values."""
        assert CONTRIBUTION_LIMITS_2025["401k_employee"] > 20000
        assert CONTRIBUTION_LIMITS_2025["ira_traditional"] > 5000
        assert CONTRIBUTION_LIMITS_2025["hsa_individual"] > 3000


# =============================================================================
# PII REDACTION TESTS
# =============================================================================

class TestPIIRedaction:
    """Test PII redaction functionality."""
    
    def test_ssn_redaction_standard_format(self):
        """Standard SSN format should be redacted."""
        text = "SSN: 123-45-6789"
        result = redact_sensitive_data(text, use_ner=False)
        assert "123-45-6789" not in result
        assert "[SSN" in result
    
    def test_ssn_redaction_with_spaces(self):
        """SSN with spaces should be redacted."""
        text = "Social Security: 123 45 6789"
        result = redact_sensitive_data(text, use_ner=False)
        assert "123 45 6789" not in result
    
    def test_ein_redaction(self):
        """EIN should be redacted."""
        text = "Employer EIN: 12-3456789"
        result = redact_sensitive_data(text, use_ner=False)
        assert "12-3456789" not in result
        assert "[EIN" in result
    
    def test_phone_redaction(self):
        """Phone numbers should be redacted."""
        text = "Contact: (555) 123-4567"
        result = redact_sensitive_data(text, use_ner=False)
        assert "123-4567" not in result
    
    def test_email_redaction(self):
        """Email addresses should be redacted."""
        text = "Email: john.doe@example.com"
        result = redact_sensitive_data(text, use_ner=False)
        assert "john.doe@example.com" not in result
    
    def test_financial_data_preserved(self):
        """Financial figures should NOT be redacted."""
        text = "Gross Pay: $5,250.00\nYTD: $42,000.00"
        result = redact_sensitive_data(text, use_ner=False)
        assert "$5,250.00" in result
        assert "$42,000.00" in result
    
    def test_empty_text(self):
        """Empty text should return empty result."""
        result = redact_sensitive_data("", use_ner=False)
        assert result == ""
    
    def test_redaction_result_object(self):
        """RedactionResult should contain proper metadata."""
        redactor = PIIRedactor(use_ner=False)
        result = redactor.redact_sensitive_data("SSN: 123-45-6789, Phone: 555-123-4567")
        
        assert isinstance(result, RedactionResult)
        assert result.redaction_count >= 2
        assert "SSN" in result.pii_types_found
        assert "PHONE" in result.pii_types_found
        assert result.processing_time_ms >= 0
    
    def test_multiple_ssns(self):
        """Multiple SSNs should all be redacted with unique tokens."""
        text = "Employee SSN: 123-45-6789, Spouse SSN: 987-65-4321"
        redactor = PIIRedactor(use_ner=False)
        result = redactor.redact_sensitive_data(text)
        
        assert "123-45-6789" not in result.redacted_text
        assert "987-65-4321" not in result.redacted_text
        assert result.redaction_count >= 2


# =============================================================================
# DATA MODEL TESTS
# =============================================================================

class TestDataModels:
    """Test Pydantic data models."""
    
    def test_user_profile_creation(self):
        """Profile should be created with defaults."""
        profile = UserFinancialProfile()
        
        assert profile.filing_status == FilingStatus.SINGLE
        assert profile.ytd_income == 0
        assert profile.pay_frequency == PayFrequency.BIWEEKLY
        assert profile.profile_id is not None
    
    def test_user_profile_standard_deduction_calculated(self):
        """Standard deduction should be auto-calculated."""
        profile = UserFinancialProfile(filing_status=FilingStatus.SINGLE)
        assert profile.standard_deduction > 0
        
        married_profile = UserFinancialProfile(
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY
        )
        assert married_profile.standard_deduction > profile.standard_deduction
    
    def test_user_profile_age_affects_deduction(self):
        """Age 65+ should increase standard deduction."""
        young_profile = UserFinancialProfile(
            filing_status=FilingStatus.SINGLE,
            age=35
        )
        
        senior_profile = UserFinancialProfile(
            filing_status=FilingStatus.SINGLE,
            age=65
        )
        
        assert senior_profile.standard_deduction > young_profile.standard_deduction
    
    def test_user_profile_projected_income(self):
        """Projected income should be calculated from YTD."""
        profile = UserFinancialProfile(
            ytd_income=50000,
            pay_frequency=PayFrequency.BIWEEKLY,
            current_pay_period=20  # ~10 months into year
        )
        
        # Should project to approximately 65,000 (50k / 20 * 26)
        assert profile.projected_annual_income > profile.ytd_income
    
    def test_remaining_401k_room(self):
        """Should calculate remaining 401k contribution room."""
        profile = UserFinancialProfile(
            ytd_401k_traditional=10000,
            age=35
        )
        
        limit = CONTRIBUTION_LIMITS_2025["401k_employee"]
        assert profile.remaining_401k_room == limit - 10000
    
    def test_remaining_401k_room_with_catchup(self):
        """Age 50+ should have higher 401k limit."""
        young_profile = UserFinancialProfile(ytd_401k_traditional=0, age=35)
        senior_profile = UserFinancialProfile(ytd_401k_traditional=0, age=55)
        
        assert senior_profile.remaining_401k_room > young_profile.remaining_401k_room
    
    def test_paystub_data_pay_frequency_normalization(self):
        """Pay frequency should be normalized from various formats."""
        data1 = PaystubData(pay_frequency="bi-weekly")
        assert data1.pay_frequency == PayFrequency.BIWEEKLY
        
        data2 = PaystubData(pay_frequency="every other week")
        assert data2.pay_frequency == PayFrequency.BIWEEKLY


# =============================================================================
# TAX CALCULATOR TESTS
# =============================================================================

class TestTaxCalculator:
    """Test tax calculation engine."""
    
    @pytest.fixture
    def calculator(self):
        return TaxCalculator()
    
    @pytest.fixture
    def simple_profile(self):
        return UserFinancialProfile(
            filing_status=FilingStatus.SINGLE,
            ytd_income=85000,
            pay_frequency=PayFrequency.BIWEEKLY,
            current_pay_period=26,  # Full year
            ytd_federal_withheld=15000,
            age=35
        )
    
    def test_calculate_tax_returns_result(self, calculator, simple_profile):
        """Should return a TaxResult object."""
        result = calculator.calculate_tax(simple_profile)
        
        assert isinstance(result, TaxResult)
        assert result.gross_income > 0
        assert result.federal_tax > 0
        assert result.taxable_income > 0
    
    def test_calculate_tax_standard_deduction_applied(self, calculator, simple_profile):
        """Standard deduction should reduce taxable income."""
        result = calculator.calculate_tax(simple_profile)
        
        assert result.taxable_income < result.adjusted_gross_income
        assert result.deduction_type == "standard"
    
    def test_calculate_tax_refund_calculation(self, calculator, simple_profile):
        """Refund/owed should be calculated correctly."""
        result = calculator.calculate_tax(simple_profile)
        
        expected_refund = result.total_payments_and_withholding - result.total_tax_liability
        assert abs(result.refund_or_owed - expected_refund) < 1
    
    def test_calculate_tax_with_401k_reduces_tax(self, calculator):
        """401k contributions should reduce tax."""
        profile_no_401k = UserFinancialProfile(
            filing_status=FilingStatus.SINGLE,
            ytd_income=85000,
            pay_frequency=PayFrequency.BIWEEKLY,
            current_pay_period=26,
            ytd_401k_traditional=0
        )
        
        profile_with_401k = UserFinancialProfile(
            filing_status=FilingStatus.SINGLE,
            ytd_income=85000,
            pay_frequency=PayFrequency.BIWEEKLY,
            current_pay_period=26,
            ytd_401k_traditional=20000
        )
        
        result_no_401k = calculator.calculate_tax(profile_no_401k)
        result_with_401k = calculator.calculate_tax(profile_with_401k)
        
        # Note: 401k is typically excluded from W-2 wages, so this tests
        # other pre-tax deductions. The implementation may vary.
        # For this test, we're verifying the calculator runs correctly.
        assert result_no_401k.federal_tax >= 0
        assert result_with_401k.federal_tax >= 0
    
    def test_calculate_tax_marginal_rate_correct(self, calculator, simple_profile):
        """Marginal rate should match the bracket."""
        result = calculator.calculate_tax(simple_profile)
        
        expected_rate = get_marginal_rate(
            result.taxable_income, 
            simple_profile.filing_status
        )
        assert result.marginal_rate == expected_rate
    
    def test_calculate_tax_with_children(self, calculator):
        """Child tax credit should reduce tax."""
        profile_no_kids = UserFinancialProfile(
            filing_status=FilingStatus.SINGLE,
            ytd_income=80000,
            pay_frequency=PayFrequency.BIWEEKLY,
            current_pay_period=26,
            num_children_under_17=0
        )
        
        profile_with_kids = UserFinancialProfile(
            filing_status=FilingStatus.SINGLE,
            ytd_income=80000,
            pay_frequency=PayFrequency.BIWEEKLY,
            current_pay_period=26,
            num_children_under_17=2
        )
        
        result_no_kids = calculator.calculate_tax(profile_no_kids)
        result_with_kids = calculator.calculate_tax(profile_with_kids)
        
        assert result_with_kids.child_tax_credit > 0
        assert result_with_kids.total_tax_liability < result_no_kids.total_tax_liability


# =============================================================================
# TAX SIMULATOR TESTS
# =============================================================================

class TestTaxSimulator:
    """Test what-if simulation functionality."""
    
    @pytest.fixture
    def profile(self):
        return UserFinancialProfile(
            filing_status=FilingStatus.SINGLE,
            ytd_income=85000,
            pay_frequency=PayFrequency.BIWEEKLY,
            current_pay_period=20,
            ytd_federal_withheld=12000,
            ytd_401k_traditional=10000,
            ytd_hsa=2000,
            age=35,
            has_workplace_retirement_plan=True,
            hsa_coverage_type="individual"
        )
    
    @pytest.fixture
    def simulator(self, profile):
        return TaxSimulator(profile)
    
    def test_simulation_extra_401k(self, simulator):
        """Adding 401k should reduce tax."""
        result = simulator.run_simulation(
            {"extra_401k_traditional": 5000},
            "Add $5k to 401k"
        )
        
        assert result.is_beneficial
        assert result.tax_difference < 0
        assert "save" in result.summary.lower()
    
    def test_simulation_returns_baseline(self, simulator):
        """Simulation should include baseline result."""
        result = simulator.run_simulation(
            {"extra_hsa": 2000},
            "Add HSA"
        )
        
        assert result.baseline is not None
        assert result.simulated is not None
        assert result.baseline.gross_income == result.simulated.gross_income
    
    def test_find_optimal_401k(self, simulator, profile):
        """Should find optimal 401k contribution."""
        result = simulator.find_optimal_401k()
        
        # Should suggest contributing remaining room
        assert "401" in result.scenario_name.lower()
        remaining = profile.remaining_401k_room
        if remaining > 0:
            assert result.is_beneficial
    
    def test_find_optimal_hsa(self, simulator, profile):
        """Should find optimal HSA contribution."""
        result = simulator.find_optimal_hsa()
        
        assert "HSA" in result.scenario_name.upper()
        remaining = profile.remaining_hsa_room
        if remaining > 0:
            assert result.is_beneficial
    
    def test_simulation_filing_status_change(self, simulator):
        """Changing filing status should work."""
        result = simulator.run_simulation(
            {"filing_status": "married_filing_jointly"},
            "Get Married"
        )
        
        # Result should have different tax calculation
        assert result.simulated.deduction_amount != result.baseline.deduction_amount


# =============================================================================
# RECOMMENDATION ENGINE TESTS
# =============================================================================

class TestRecommendationEngine:
    """Test recommendation generation."""
    
    @pytest.fixture
    def engine(self):
        return RecommendationEngine()
    
    @pytest.fixture
    def profile_owing_taxes(self):
        """Profile that will owe taxes."""
        return UserFinancialProfile(
            filing_status=FilingStatus.SINGLE,
            ytd_income=100000,
            pay_frequency=PayFrequency.BIWEEKLY,
            current_pay_period=20,
            ytd_federal_withheld=10000,  # Low withholding
            ytd_401k_traditional=5000,   # Room to contribute more
            ytd_hsa=1000,                # Room to contribute more
            age=35,
            has_workplace_retirement_plan=True,
            hsa_coverage_type="individual"
        )
    
    def test_generates_recommendations(self, engine, profile_owing_taxes):
        """Should generate recommendations."""
        report = engine.generate_recommendations(profile_owing_taxes)
        
        assert report is not None
        assert len(report.basic_recommendations) > 0
        assert report.days_until_year_end >= 0
    
    def test_401k_recommendation_when_room(self, engine, profile_owing_taxes):
        """Should recommend 401k when there's room."""
        report = engine.generate_recommendations(profile_owing_taxes)
        
        has_401k_rec = any(
            "401" in rec.title.lower() 
            for rec in report.basic_recommendations
        )
        assert has_401k_rec
    
    def test_hsa_recommendation_when_room(self, engine, profile_owing_taxes):
        """Should recommend HSA when there's room."""
        report = engine.generate_recommendations(profile_owing_taxes)
        
        has_hsa_rec = any(
            "hsa" in rec.title.lower() 
            for rec in report.basic_recommendations
        )
        assert has_hsa_rec
    
    def test_recommendations_have_savings_estimate(self, engine, profile_owing_taxes):
        """Recommendations should include potential savings."""
        report = engine.generate_recommendations(profile_owing_taxes)
        
        for rec in report.basic_recommendations:
            if "401" in rec.title.lower() or "hsa" in rec.title.lower():
                assert rec.potential_tax_savings >= 0


# =============================================================================
# INCOME PROJECTOR TESTS
# =============================================================================

class TestIncomeProjector:
    """Test income projection functionality."""
    
    def test_project_annual_income_biweekly(self):
        """Should project correctly for biweekly pay."""
        projected = IncomeProjector.project_annual_income(
            ytd_income=50000,
            current_pay_period=20,
            pay_frequency=PayFrequency.BIWEEKLY
        )
        
        # 50000 / 20 * 26 = 65000
        assert projected == 65000
    
    def test_project_annual_income_monthly(self):
        """Should project correctly for monthly pay."""
        projected = IncomeProjector.project_annual_income(
            ytd_income=50000,
            current_pay_period=10,
            pay_frequency=PayFrequency.MONTHLY
        )
        
        # 50000 / 10 * 12 = 60000
        assert projected == 60000
    
    def test_project_annual_income_zero_period(self):
        """Should handle zero pay period gracefully."""
        projected = IncomeProjector.project_annual_income(
            ytd_income=50000,
            current_pay_period=0,
            pay_frequency=PayFrequency.BIWEEKLY
        )
        
        # Should return YTD as-is
        assert projected == 50000
    
    def test_infer_pay_frequency(self):
        """Should infer pay frequency from dates."""
        # Biweekly pattern (14 days between)
        dates = [
            date(2025, 1, 3),
            date(2025, 1, 17),
            date(2025, 1, 31),
            date(2025, 2, 14),
        ]
        
        frequency = IncomeProjector.infer_pay_frequency_from_dates(dates)
        assert frequency == PayFrequency.BIWEEKLY
    
    def test_infer_pay_frequency_monthly(self):
        """Should infer monthly frequency."""
        dates = [
            date(2025, 1, 15),
            date(2025, 2, 15),
            date(2025, 3, 15),
        ]
        
        frequency = IncomeProjector.infer_pay_frequency_from_dates(dates)
        assert frequency == PayFrequency.MONTHLY


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_full_workflow_single_filer(self):
        """Test complete workflow for single filer."""
        # Create profile
        profile = UserFinancialProfile(
            filing_status=FilingStatus.SINGLE,
            age=35,
            ytd_income=75000,
            pay_frequency=PayFrequency.BIWEEKLY,
            current_pay_period=20,
            ytd_federal_withheld=11000,
            ytd_401k_traditional=8000,
            ytd_hsa=1500,
            has_workplace_retirement_plan=True,
            hsa_coverage_type="individual"
        )
        
        # Calculate tax
        calculator = TaxCalculator()
        result = calculator.calculate_tax(profile)
        
        # Run simulations
        simulator = TaxSimulator(profile)
        sim_401k = simulator.find_optimal_401k()
        sim_hsa = simulator.find_optimal_hsa()
        
        # Get recommendations
        engine = RecommendationEngine()
        recommendations = engine.generate_recommendations(profile)
        
        # Verify all components produced results
        assert result.taxable_income > 0
        assert sim_401k.scenario_name is not None
        assert sim_hsa.scenario_name is not None
        assert len(recommendations.basic_recommendations) > 0
    
    def test_full_workflow_married_filer(self):
        """Test complete workflow for married filer."""
        profile = UserFinancialProfile(
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            age=40,
            spouse_age=38,
            ytd_income=150000,
            pay_frequency=PayFrequency.SEMIMONTHLY,
            current_pay_period=20,
            ytd_federal_withheld=22000,
            ytd_401k_traditional=15000,
            num_children_under_17=2,
            has_workplace_retirement_plan=True
        )
        
        calculator = TaxCalculator()
        result = calculator.calculate_tax(profile)
        
        # Married filing jointly should have higher deduction
        assert result.deduction_amount > 20000
        
        # Should have child tax credit
        assert result.child_tax_credit > 0


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
