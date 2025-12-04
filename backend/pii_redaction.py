"""
TaxGuard AI - PII Redaction Module
===================================
CRITICAL PRIVACY LAYER

This module creates the "PII Air Gap" - ensuring no personally identifiable
information ever reaches external LLM providers.

Pipeline:
1. Raw text from OCR
2. Regex patterns catch structured PII (SSN, EIN, phone, etc.)
3. NER catches unstructured PII (names, addresses)
4. All PII replaced with tokens
5. Only redacted text sent to LLM

SECURITY NOTE: Original PII values are NEVER stored in the redaction map.
We only store the TYPE of PII found, not the values themselves.
"""

import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# PII PATTERNS - Regex for structured data
# =============================================================================

PII_PATTERNS = {
    # Social Security Numbers (various formats)
    "SSN": [
        r'\b\d{3}-\d{2}-\d{4}\b',           # 123-45-6789
        r'\b\d{3}\s\d{2}\s\d{4}\b',         # 123 45 6789
        r'\b\d{9}\b(?=\s|$|[,.])',          # 123456789 (9 consecutive digits)
        r'\bSSN[:\s#]*\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',  # SSN: 123-45-6789
        r'\bSocial Security[:\s#]*\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
    ],
    
    # Employer Identification Numbers
    "EIN": [
        r'\b\d{2}-\d{7}\b',                 # 12-3456789
        r'\bEIN[:\s#]*\d{2}[-\s]?\d{7}\b',  # EIN: 12-3456789
        r'\bFederal\s*ID[:\s#]*\d{2}[-\s]?\d{7}\b',
    ],
    
    # Phone Numbers
    "PHONE": [
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # 123-456-7890
        r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',      # (123) 456-7890
        r'\b1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # 1-123-456-7890
    ],
    
    # Email Addresses
    "EMAIL": [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    ],
    
    # Bank Account Numbers (basic patterns)
    "BANK_ACCOUNT": [
        r'\b(?:account|acct)[:\s#]*\d{8,17}\b',
        r'\bRouting[:\s#]*\d{9}\b',
    ],
    
    # Street Addresses (simplified)
    "ADDRESS": [
        r'\b\d{1,5}\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Circle|Cir|Place|Pl)\.?\s*(?:#\s*\d+|(?:Apt|Suite|Unit|Ste|#)\s*\d+[\w]?)?\b',
    ],
    
    # Dates of Birth (when labeled)
    "DOB": [
        r'\b(?:DOB|Date\s*of\s*Birth|Birth\s*Date)[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b(?:DOB|Date\s*of\s*Birth|Birth\s*Date)[:\s]*\w+\s+\d{1,2},?\s+\d{4}\b',
    ],
    
    # Driver's License Numbers (state-specific patterns would go here)
    "DRIVERS_LICENSE": [
        r'\b(?:DL|Driver\'?s?\s*License)[:\s#]*[A-Z]?\d{5,12}\b',
    ],
    
    # IP Addresses
    "IP_ADDRESS": [
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    ],
}


# =============================================================================
# REDACTION CLASS
# =============================================================================

@dataclass
class RedactionResult:
    """Result of the PII redaction process."""
    
    original_length: int
    redacted_text: str
    redacted_length: int
    pii_types_found: Set[str] = field(default_factory=set)
    redaction_count: int = 0
    token_map: Dict[str, str] = field(default_factory=dict)  # token -> pii_type (NOT value)
    processing_time_ms: float = 0.0
    warnings: List[str] = field(default_factory=list)
    
    @property
    def was_modified(self) -> bool:
        return self.redaction_count > 0


class PIIRedactor:
    """
    Main PII redaction engine.
    
    SECURITY: This class NEVER stores original PII values.
    The token_map only stores: {token: pii_type}
    """
    
    def __init__(self, use_ner: bool = True):
        """
        Initialize the redactor.
        
        Args:
            use_ner: Whether to use NER for name detection.
                    Set to False if spaCy is not available.
        """
        self.use_ner = use_ner
        self._nlp = None
        self._counters: Dict[str, int] = {}
        
        if use_ner:
            self._load_ner_model()
    
    def _load_ner_model(self):
        """Load spaCy NER model."""
        try:
            import spacy
            
            # Try to load the model
            try:
                self._nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy NER model: en_core_web_sm")
            except OSError:
                # Model not installed, try to download
                logger.warning("spaCy model not found. Attempting download...")
                import subprocess
                subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], 
                             capture_output=True)
                self._nlp = spacy.load("en_core_web_sm")
                
        except ImportError:
            logger.warning("spaCy not installed. NER-based redaction disabled.")
            self.use_ner = False
        except Exception as e:
            logger.warning(f"Could not load spaCy: {e}. NER-based redaction disabled.")
            self.use_ner = False
    
    def _get_token(self, pii_type: str) -> str:
        """Generate a unique token for a PII type."""
        count = self._counters.get(pii_type, 0) + 1
        self._counters[pii_type] = count
        return f"[{pii_type}_{count}]"
    
    def _redact_with_regex(self, text: str, token_map: Dict[str, str]) -> Tuple[str, Set[str]]:
        """
        Apply regex-based redaction.
        
        Returns:
            Tuple of (redacted_text, set of pii types found)
        """
        pii_found = set()
        redacted = text
        
        for pii_type, patterns in PII_PATTERNS.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, redacted, re.IGNORECASE))
                
                # Process matches in reverse order to maintain string positions
                for match in reversed(matches):
                    token = self._get_token(pii_type)
                    token_map[token] = pii_type
                    
                    # Replace the match with the token
                    redacted = redacted[:match.start()] + token + redacted[match.end():]
                    pii_found.add(pii_type)
        
        return redacted, pii_found
    
    def _redact_with_ner(self, text: str, token_map: Dict[str, str]) -> Tuple[str, Set[str]]:
        """
        Apply NER-based redaction for names and organizations.
        
        Returns:
            Tuple of (redacted_text, set of pii types found)
        """
        if not self._nlp:
            return text, set()
        
        pii_found = set()
        
        # Process with spaCy
        doc = self._nlp(text)
        
        # Collect entities to redact (in reverse order for safe replacement)
        entities_to_redact = []
        
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                entities_to_redact.append((ent.start_char, ent.end_char, "USER_NAME"))
            elif ent.label_ == "ORG":
                # Only redact if it looks like an employer name
                # Skip common non-PII orgs (IRS, Social Security Admin, etc.)
                org_text = ent.text.lower()
                skip_orgs = {'irs', 'internal revenue service', 'social security', 
                            'medicare', 'department of', 'state of'}
                if not any(skip in org_text for skip in skip_orgs):
                    entities_to_redact.append((ent.start_char, ent.end_char, "EMPLOYER"))
            elif ent.label_ == "GPE":
                # Geo-political entities (cities, states, countries)
                # Only redact if it's likely part of an address
                pass  # Address patterns handled by regex
        
        # Sort by position (descending) for safe replacement
        entities_to_redact.sort(key=lambda x: x[0], reverse=True)
        
        redacted = text
        for start, end, pii_type in entities_to_redact:
            token = self._get_token(pii_type)
            token_map[token] = pii_type
            redacted = redacted[:start] + token + redacted[end:]
            pii_found.add(pii_type)
        
        return redacted, pii_found
    
    def _additional_sanitization(self, text: str) -> str:
        """
        Additional sanitization passes for edge cases.
        """
        # Remove any remaining sequences that look like account numbers
        text = re.sub(r'\b\d{10,}\b', '[ACCOUNT_NUMBER]', text)
        
        # Remove any remaining sequences that look like credit cards (16 digits)
        text = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD_NUMBER]', text)
        
        return text
    
    def redact_sensitive_data(self, raw_text: str) -> RedactionResult:
        """
        Main method: Redact all sensitive PII from text.
        
        This creates the "PII Air Gap" - the returned text is safe
        to send to external LLM providers.
        
        Args:
            raw_text: Original text from OCR/document extraction
            
        Returns:
            RedactionResult with redacted text and metadata
        """
        import time
        start_time = time.time()
        
        # Reset counters for this document
        self._counters = {}
        token_map: Dict[str, str] = {}
        pii_found: Set[str] = set()
        warnings: List[str] = []
        
        if not raw_text or not raw_text.strip():
            return RedactionResult(
                original_length=0,
                redacted_text="",
                redacted_length=0,
                warnings=["Empty input text"]
            )
        
        # Step 1: Regex-based redaction (catches structured PII)
        redacted_text, regex_pii = self._redact_with_regex(raw_text, token_map)
        pii_found.update(regex_pii)
        
        # Step 2: NER-based redaction (catches names, organizations)
        if self.use_ner:
            redacted_text, ner_pii = self._redact_with_ner(redacted_text, token_map)
            pii_found.update(ner_pii)
        else:
            warnings.append("NER disabled - name detection may be incomplete")
        
        # Step 3: Additional sanitization
        redacted_text = self._additional_sanitization(redacted_text)
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        # Log summary
        if pii_found:
            logger.info(f"Redacted PII types: {pii_found}. Total redactions: {len(token_map)}")
        
        return RedactionResult(
            original_length=len(raw_text),
            redacted_text=redacted_text,
            redacted_length=len(redacted_text),
            pii_types_found=pii_found,
            redaction_count=len(token_map),
            token_map=token_map,
            processing_time_ms=processing_time,
            warnings=warnings
        )
    
    def validate_no_pii_leakage(self, text: str) -> Tuple[bool, List[str]]:
        """
        Validate that text contains no apparent PII.
        Use this as a final check before sending to LLM.
        
        Returns:
            Tuple of (is_safe, list of potential issues)
        """
        issues = []
        
        # Check for SSN patterns
        if re.search(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', text):
            issues.append("Potential SSN pattern detected")
        
        # Check for email patterns (unless they're redacted tokens)
        if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
            if "[EMAIL" not in text:
                issues.append("Potential email address detected")
        
        # Check for EIN patterns
        if re.search(r'\b\d{2}-\d{7}\b', text):
            issues.append("Potential EIN pattern detected")
        
        # Check for 9+ consecutive digits (potential account numbers)
        if re.search(r'\b\d{9,}\b', text):
            issues.append("Long numeric sequence detected (potential account/SSN)")
        
        is_safe = len(issues) == 0
        return is_safe, issues


# =============================================================================
# CONVENIENCE FUNCTION (for direct import)
# =============================================================================

def redact_sensitive_data(raw_text: str, use_ner: bool = True) -> str:
    """
    Convenience function to redact PII from text.
    
    Args:
        raw_text: Original text containing potential PII
        use_ner: Whether to use NER for name detection
        
    Returns:
        Redacted text safe for LLM processing
    """
    redactor = PIIRedactor(use_ner=use_ner)
    result = redactor.redact_sensitive_data(raw_text)
    return result.redacted_text


# =============================================================================
# SPECIALIZED REDACTORS FOR SPECIFIC DOCUMENT TYPES
# =============================================================================

class PaystubRedactor(PIIRedactor):
    """
    Specialized redactor for paystubs.
    Preserves financial data while redacting identity info.
    """
    
    def redact_sensitive_data(self, raw_text: str) -> RedactionResult:
        """
        Redact PII from paystub while preserving financial figures.
        """
        # First, run standard redaction
        result = super().redact_sensitive_data(raw_text)
        
        # Paystubs often have employee IDs that look numeric
        # But we want to preserve dollar amounts
        # The regex patterns should already handle this by looking for
        # specific PII formats rather than all numbers
        
        return result


class W2Redactor(PIIRedactor):
    """
    Specialized redactor for W-2 forms.
    Knows the structure of W-2 and redacts appropriately.
    """
    
    def redact_sensitive_data(self, raw_text: str) -> RedactionResult:
        """
        Redact PII from W-2 while preserving box values.
        """
        # W-2 specific patterns
        w2_patterns = {
            "EMPLOYEE_SSN": [
                r'(?:Employee\'?s?\s*)?(?:social\s*security\s*)?(?:number|SSN|#)[:\s]*(\d{3}[-\s]?\d{2}[-\s]?\d{4})',
            ],
            "EMPLOYER_EIN": [
                r'(?:Employer\'?s?\s*)?(?:identification\s*)?(?:number|EIN|#)[:\s]*(\d{2}[-\s]?\d{7})',
            ],
            "CONTROL_NUMBER": [
                r'[Cc]ontrol\s*[Nn]umber[:\s]*([A-Za-z0-9]+)',
            ]
        }
        
        # Add W-2 specific patterns temporarily
        original_patterns = PII_PATTERNS.copy()
        PII_PATTERNS.update(w2_patterns)
        
        try:
            result = super().redact_sensitive_data(raw_text)
        finally:
            # Restore original patterns
            PII_PATTERNS.clear()
            PII_PATTERNS.update(original_patterns)
        
        return result


# =============================================================================
# TESTING / DEMO
# =============================================================================

def demo():
    """Demonstrate the redaction module."""
    
    sample_text = """
    ACME Corporation
    Employee: John A. Smith
    SSN: 123-45-6789
    Employee ID: E12345
    
    Pay Period: 10/01/2025 - 10/15/2025
    Pay Date: 10/20/2025
    
    Address: 123 Main Street, Apt 4B, Anytown, CA 90210
    Email: john.smith@acme.com
    Phone: (555) 123-4567
    
    Gross Pay: $4,250.00
    Federal Tax: $425.00
    State Tax: $212.50
    Social Security: $263.50
    Medicare: $61.63
    401(k): $425.00
    
    YTD Gross: $85,000.00
    YTD Federal: $8,500.00
    
    Employer EIN: 12-3456789
    """
    
    print("=" * 60)
    print("PII REDACTION DEMO")
    print("=" * 60)
    
    # Initialize redactor (NER may not be available)
    redactor = PIIRedactor(use_ner=True)
    
    # Perform redaction
    result = redactor.redact_sensitive_data(sample_text)
    
    print("\n--- ORIGINAL TEXT ---")
    print(sample_text[:200] + "...")
    
    print("\n--- REDACTED TEXT ---")
    print(result.redacted_text)
    
    print("\n--- REDACTION SUMMARY ---")
    print(f"Original length: {result.original_length}")
    print(f"Redacted length: {result.redacted_length}")
    print(f"PII types found: {result.pii_types_found}")
    print(f"Total redactions: {result.redaction_count}")
    print(f"Processing time: {result.processing_time_ms:.2f}ms")
    
    print("\n--- TOKEN MAP (types only, no values) ---")
    for token, pii_type in result.token_map.items():
        print(f"  {token}: {pii_type}")
    
    # Validate
    is_safe, issues = redactor.validate_no_pii_leakage(result.redacted_text)
    print(f"\n--- VALIDATION ---")
    print(f"Safe for LLM: {is_safe}")
    if issues:
        print(f"Issues: {issues}")


if __name__ == "__main__":
    demo()
