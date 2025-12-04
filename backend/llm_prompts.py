"""
TaxGuard AI - LLM Prompts
=========================
System prompts and instructions for GPT-5.1 (or equivalent) integration.

CRITICAL RULES FOR LLM USAGE:
1. LLM ONLY extracts data and generates natural language
2. LLM NEVER calculates tax amounts - that's done in Python
3. LLM receives REDACTED text only - no PII
4. LLM must output structured JSON for data extraction
5. Tax brackets are PROVIDED to the LLM - it cannot use its training data

The prompts in this module enforce these rules.
"""

from tax_constants import get_all_constants_for_llm, get_tax_bracket_info, FilingStatus


# =============================================================================
# DATA EXTRACTION SYSTEM PROMPT
# =============================================================================

PAYSTUB_EXTRACTION_SYSTEM_PROMPT = """You are a financial document data extraction specialist. Your task is to extract structured financial data from REDACTED paystub text.

## CRITICAL RULES:
1. Extract ONLY the data that is explicitly present in the document
2. Use null for any fields you cannot find
3. Output ONLY valid JSON - no explanations, no markdown, no additional text
4. Numbers should be numeric (not strings), without currency symbols or commas
5. If you see redaction tokens like [USER_NAME] or [SSN_1], ignore them - they are not data
6. NEVER guess or estimate values - extract only what you see

## EXPECTED OUTPUT FORMAT:
{
    "document_type": "paystub",
    "extraction_confidence": 0.0-1.0,
    "pay_info": {
        "pay_date": "YYYY-MM-DD or null",
        "pay_period_start": "YYYY-MM-DD or null",
        "pay_period_end": "YYYY-MM-DD or null",
        "pay_frequency": "weekly|biweekly|semimonthly|monthly|null"
    },
    "current_period": {
        "gross_pay": number or null,
        "net_pay": number or null,
        "federal_tax": number or null,
        "state_tax": number or null,
        "social_security": number or null,
        "medicare": number or null,
        "pre_tax_401k": number or null,
        "pre_tax_hsa": number or null,
        "pre_tax_other": number or null
    },
    "year_to_date": {
        "gross": number or null,
        "federal_tax": number or null,
        "state_tax": number or null,
        "social_security": number or null,
        "medicare": number or null,
        "401k": number or null,
        "hsa": number or null
    },
    "inferences": {
        "pay_frequency_inferred": true/false,
        "pay_frequency_reasoning": "string explaining how you inferred pay frequency"
    }
}

## PAY FREQUENCY INFERENCE:
If pay frequency is not explicitly stated, infer it from:
- Pay period dates (7 days = weekly, 14 days = biweekly, ~15 days = semimonthly)
- Pay date patterns
- YTD vs current period ratios
Always set pay_frequency_inferred to true if you had to infer.

## EXTRACTION CONFIDENCE:
Set extraction_confidence based on:
- 0.9-1.0: All major fields clearly visible and extracted
- 0.7-0.8: Most fields extracted, some unclear
- 0.5-0.6: Many fields missing or uncertain
- Below 0.5: Document may not be a paystub

Now extract data from the following REDACTED paystub text:"""


W2_EXTRACTION_SYSTEM_PROMPT = """You are a financial document data extraction specialist. Your task is to extract structured W-2 form data from REDACTED text.

## CRITICAL RULES:
1. Extract ONLY the data that is explicitly present
2. W-2 boxes are numbered - look for "Box 1", "Box 2", etc.
3. Output ONLY valid JSON - no explanations
4. Numbers should be numeric without currency symbols
5. Redaction tokens like [EMPLOYER] or [SSN_1] should be ignored

## EXPECTED OUTPUT FORMAT:
{
    "document_type": "w2",
    "tax_year": number,
    "extraction_confidence": 0.0-1.0,
    "boxes": {
        "box_1_wages": number or null,
        "box_2_federal_withheld": number or null,
        "box_3_ss_wages": number or null,
        "box_4_ss_tax": number or null,
        "box_5_medicare_wages": number or null,
        "box_6_medicare_tax": number or null,
        "box_10_dependent_care": number or null,
        "box_12_codes": {"code": amount, ...},
        "box_13_retirement_plan": true/false/null
    },
    "state_info": {
        "state_code": "XX" or null,
        "state_wages": number or null,
        "state_tax_withheld": number or null
    }
}

## BOX 12 CODES:
Common codes to look for:
- D = Traditional 401(k)
- E = 403(b)
- W = HSA employer contributions
- DD = Health insurance cost
- AA = Roth 401(k)

Now extract data from the following REDACTED W-2 text:"""


FORM_1040_EXTRACTION_SYSTEM_PROMPT = """You are a financial document data extraction specialist. Your task is to extract key figures from a REDACTED Form 1040 (prior year tax return).

## CRITICAL RULES:
1. Extract ONLY values explicitly present
2. Output ONLY valid JSON
3. Look for line numbers (e.g., "Line 11", "Line 15")
4. Ignore all PII redaction tokens

## EXPECTED OUTPUT FORMAT:
{
    "document_type": "form_1040",
    "tax_year": number,
    "extraction_confidence": 0.0-1.0,
    "filing_info": {
        "filing_status": "single|married_filing_jointly|married_filing_separately|head_of_household|qualifying_widow",
        "can_be_claimed_as_dependent": true/false/null
    },
    "income": {
        "line_1_wages": number or null,
        "line_2a_tax_exempt_interest": number or null,
        "line_2b_taxable_interest": number or null,
        "line_3a_qualified_dividends": number or null,
        "line_3b_ordinary_dividends": number or null,
        "line_7_capital_gain_loss": number or null,
        "line_9_total_income": number or null,
        "line_11_agi": number or null
    },
    "deductions": {
        "line_12_standard_or_itemized": number or null,
        "used_standard_deduction": true/false/null
    },
    "tax_and_credits": {
        "line_15_taxable_income": number or null,
        "line_16_tax": number or null,
        "line_24_total_tax": number or null
    },
    "payments": {
        "line_25a_w2_withholding": number or null,
        "line_26_estimated_payments": number or null,
        "line_33_total_payments": number or null
    },
    "result": {
        "line_34_refund": number or null,
        "line_37_amount_owed": number or null
    }
}

Now extract data from the following REDACTED Form 1040 text:"""


# =============================================================================
# TAX STRATEGY ANALYSIS PROMPT
# =============================================================================

def get_tax_strategy_prompt(profile_summary: str, calculation_summary: str) -> str:
    """
    Generate the prompt for tax strategy analysis.
    
    This prompt asks the LLM to analyze the situation and suggest strategies.
    The actual tax calculations are done in Python and provided to the LLM.
    """
    
    # Get authoritative tax bracket information
    tax_reference = get_all_constants_for_llm()
    
    return f"""You are a tax strategy advisor. Analyze the following financial situation and provide actionable recommendations.

## CRITICAL RULES:
1. DO NOT calculate tax amounts - those are provided below
2. DO NOT guess tax brackets - use ONLY the reference data provided
3. Base all recommendations on the MATH provided, not general assumptions
4. Consider time constraints (remaining pay periods, deadlines)
5. Separate recommendations into BASIC (anyone can do) and ADVANCED (may need professional help)

## AUTHORITATIVE TAX REFERENCE DATA (2025):
{tax_reference}

## USER'S FINANCIAL PROFILE:
{profile_summary}

## TAX CALCULATION RESULTS (calculated by our system):
{calculation_summary}

## YOUR TASK:
Provide a Tax Strategy Analysis with the following sections:

1. **SITUATION SUMMARY** (2-3 sentences)
   - Current tax position (refund or owed)
   - Key factors affecting their taxes

2. **BASIC RECOMMENDATIONS** (actions anyone can take)
   For each recommendation:
   - Action to take
   - Dollar amount involved
   - Estimated tax impact (use the marginal rate provided)
   - Deadline
   - Feasibility check (can they actually do this given remaining pay periods?)

3. **ADVANCED RECOMMENDATIONS** (may need professional advice)
   For each recommendation:
   - Strategy name
   - How it works
   - Who should consider it
   - Risks/considerations

4. **PRIORITY ACTION LIST**
   - Numbered list of actions in order of impact
   - Include deadlines

5. **WARNINGS**
   - Any concerns about their current situation
   - Penalties they might face
   - Things to watch out for

Remember: You are providing STRATEGY advice based on the CALCULATED numbers provided. 
Do not recalculate anything - trust the numbers given.

Respond in clear, helpful language that a non-expert can understand."""


# =============================================================================
# DOCUMENT CLASSIFICATION PROMPT
# =============================================================================

DOCUMENT_CLASSIFICATION_PROMPT = """You are a document classification specialist. Analyze the following REDACTED document text and classify its type.

## DOCUMENT TYPES:
- paystub: Regular pay statement showing earnings and deductions
- w2: Annual wage statement (W-2 form)
- form_1040: Individual tax return
- form_1099_nec: Non-employee compensation
- form_1099_int: Interest income
- form_1099_div: Dividend income
- form_1099_b: Broker transactions (capital gains)
- unknown: Cannot determine document type

## OUTPUT FORMAT (JSON only):
{
    "document_type": "string",
    "confidence": 0.0-1.0,
    "key_indicators": ["list", "of", "clues"],
    "warnings": ["any", "concerns"]
}

## CLASSIFICATION RULES:
- Paystubs: Look for "pay period", "gross pay", "net pay", "YTD"
- W-2: Look for "Wage and Tax Statement", numbered boxes, "Form W-2"
- 1040: Look for "Form 1040", "Individual Income Tax Return", line numbers
- 1099 forms: Look for "Form 1099-XXX", payer/recipient structure

Analyze this document:"""


# =============================================================================
# SIMULATION EXPLANATION PROMPT
# =============================================================================

def get_simulation_explanation_prompt(
    scenario_name: str,
    changes_description: str,
    baseline_result: str,
    simulated_result: str,
    tax_difference: float
) -> str:
    """Generate prompt for explaining simulation results."""
    
    return f"""You are a tax advisor explaining simulation results to a client.

## SCENARIO: {scenario_name}
## CHANGES MADE: {changes_description}

## BASELINE (Before Change):
{baseline_result}

## SIMULATED (After Change):
{simulated_result}

## TAX DIFFERENCE: ${tax_difference:,.2f} ({'savings' if tax_difference < 0 else 'increase'})

## YOUR TASK:
Explain this simulation result in 3-4 sentences that:
1. Clearly state the tax impact
2. Explain WHY this change affects taxes (which deduction/credit is involved)
3. Put the savings/cost in perspective
4. Mention any trade-offs

Be concise and use plain language."""


# =============================================================================
# CHAT RESPONSE PROMPT
# =============================================================================

def get_chat_response_prompt(user_question: str, context: str) -> str:
    """Generate prompt for answering user questions about their taxes."""
    
    tax_reference = get_all_constants_for_llm()
    
    return f"""You are a helpful tax assistant chatbot. Answer the user's question based on their tax context.

## RULES:
1. Base answers on the PROVIDED context - don't make up numbers
2. Use the 2025 tax reference data provided below
3. Be helpful but remind users this is not professional tax advice
4. If you don't have enough information, ask clarifying questions
5. Keep responses concise and actionable

## 2025 TAX REFERENCE:
{tax_reference}

## USER'S TAX CONTEXT:
{context}

## USER'S QUESTION:
{user_question}

## YOUR RESPONSE:
Provide a helpful, accurate response. If the question requires tax calculations, 
remind the user that our system calculates those - you're providing guidance only."""


# =============================================================================
# JSON REPAIR PROMPT
# =============================================================================

JSON_REPAIR_PROMPT = """The following text was supposed to be valid JSON but has errors. 
Fix the JSON and return ONLY the corrected JSON, nothing else.

Common issues to fix:
- Missing quotes around keys
- Trailing commas
- Single quotes instead of double quotes
- Missing brackets or braces
- Invalid escape sequences

Broken JSON:
{broken_json}

Return only the fixed JSON:"""


# =============================================================================
# PROMPT UTILITIES
# =============================================================================

def build_profile_summary(profile_data: dict) -> str:
    """Build a human-readable summary of a profile for LLM prompts."""
    
    lines = [
        f"Filing Status: {profile_data.get('filing_status', 'unknown')}",
        f"Age: {profile_data.get('age', 'unknown')}",
        f"",
        "=== INCOME ===",
        f"YTD Gross Income: ${profile_data.get('ytd_income', 0):,.2f}",
        f"Projected Annual Income: ${profile_data.get('projected_annual_income', 0):,.2f}",
        f"Pay Frequency: {profile_data.get('pay_frequency', 'unknown')}",
        f"Current Pay Period: {profile_data.get('current_pay_period', 'unknown')} of {profile_data.get('total_pay_periods', 'unknown')}",
    ]
    
    # Other income
    if profile_data.get('interest_income', 0) > 0:
        lines.append(f"Interest Income: ${profile_data['interest_income']:,.2f}")
    if profile_data.get('dividend_income', 0) > 0:
        lines.append(f"Dividend Income: ${profile_data['dividend_income']:,.2f}")
    if profile_data.get('capital_gains_long', 0) > 0:
        lines.append(f"Long-term Capital Gains: ${profile_data['capital_gains_long']:,.2f}")
    if profile_data.get('self_employment_income', 0) > 0:
        lines.append(f"Self-Employment Income: ${profile_data['self_employment_income']:,.2f}")
    
    lines.extend([
        "",
        "=== WITHHOLDING & PAYMENTS ===",
        f"YTD Federal Withheld: ${profile_data.get('ytd_federal_withheld', 0):,.2f}",
        f"Estimated Payments Made: ${profile_data.get('estimated_payments_made', 0):,.2f}",
        "",
        "=== RETIREMENT CONTRIBUTIONS ===",
        f"YTD 401(k): ${profile_data.get('ytd_401k_traditional', 0):,.2f}",
        f"Remaining 401(k) Room: ${profile_data.get('remaining_401k_room', 0):,.2f}",
        f"YTD HSA: ${profile_data.get('ytd_hsa', 0):,.2f}",
        f"Remaining HSA Room: ${profile_data.get('remaining_hsa_room', 0):,.2f}",
    ])
    
    if profile_data.get('has_workplace_retirement_plan'):
        lines.append("Has Workplace Retirement Plan: Yes")
    
    return "\n".join(lines)


def build_calculation_summary(result_data: dict) -> str:
    """Build a human-readable summary of tax calculation results."""
    
    refund_owed = result_data.get('refund_or_owed', 0)
    status = "REFUND" if refund_owed >= 0 else "OWES"
    
    lines = [
        "=== TAX CALCULATION RESULTS ===",
        f"Gross Income: ${result_data.get('gross_income', 0):,.2f}",
        f"Adjustments: ${result_data.get('adjustments', 0):,.2f}",
        f"Adjusted Gross Income: ${result_data.get('adjusted_gross_income', 0):,.2f}",
        f"",
        f"Deduction Type: {result_data.get('deduction_type', 'standard').title()}",
        f"Deduction Amount: ${result_data.get('deduction_amount', 0):,.2f}",
        f"",
        f"Taxable Income: ${result_data.get('taxable_income', 0):,.2f}",
        f"",
        f"Federal Tax: ${result_data.get('federal_tax', 0):,.2f}",
        f"Self-Employment Tax: ${result_data.get('self_employment_tax', 0):,.2f}",
        f"Total Credits: ${result_data.get('total_credits', 0):,.2f}",
        f"",
        f"TOTAL TAX LIABILITY: ${result_data.get('total_tax_liability', 0):,.2f}",
        f"Total Payments/Withholding: ${result_data.get('total_payments_and_withholding', 0):,.2f}",
        f"",
        f"=== RESULT: {status} ${abs(refund_owed):,.2f} ===",
        f"",
        f"Effective Tax Rate: {result_data.get('effective_rate', 0):.1f}%",
        f"Marginal Tax Rate: {result_data.get('marginal_rate', 0)*100:.0f}%",
    ]
    
    return "\n".join(lines)


# =============================================================================
# PROMPT VALIDATION
# =============================================================================

def validate_extraction_response(response: dict, document_type: str) -> tuple[bool, list[str]]:
    """
    Validate that an LLM extraction response has required fields.
    
    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []
    
    # Check document type
    if response.get('document_type') != document_type:
        issues.append(f"Wrong document type: expected {document_type}, got {response.get('document_type')}")
    
    # Check confidence
    confidence = response.get('extraction_confidence', 0)
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        issues.append("Invalid extraction_confidence")
    
    # Document-specific validation
    if document_type == 'paystub':
        if not response.get('current_period'):
            issues.append("Missing current_period section")
        if not response.get('year_to_date'):
            issues.append("Missing year_to_date section")
            
    elif document_type == 'w2':
        if not response.get('boxes'):
            issues.append("Missing boxes section")
        if not response.get('tax_year'):
            issues.append("Missing tax_year")
            
    elif document_type == 'form_1040':
        if not response.get('income'):
            issues.append("Missing income section")
        if not response.get('tax_and_credits'):
            issues.append("Missing tax_and_credits section")
    
    return len(issues) == 0, issues


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PAYSTUB_EXTRACTION_SYSTEM_PROMPT',
    'W2_EXTRACTION_SYSTEM_PROMPT',
    'FORM_1040_EXTRACTION_SYSTEM_PROMPT',
    'DOCUMENT_CLASSIFICATION_PROMPT',
    'JSON_REPAIR_PROMPT',
    'get_tax_strategy_prompt',
    'get_simulation_explanation_prompt',
    'get_chat_response_prompt',
    'build_profile_summary',
    'build_calculation_summary',
    'validate_extraction_response',
]
