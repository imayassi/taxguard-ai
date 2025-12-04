"""
TaxGuard AI - FastAPI Backend
==============================
Main API server for the tax estimation application.

Security Architecture:
1. Documents are processed through PII redaction BEFORE any LLM calls
2. Tax calculations are done locally in Python - LLM only assists with extraction
3. Original PII is NEVER stored or logged
"""

import os
import json
import base64
import logging
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Local imports
from tax_constants import FilingStatus, PAY_PERIODS_PER_YEAR, get_all_constants_for_llm
from models import (
    UserFinancialProfile,
    PayFrequency,
    TaxResult,
    RedactedDocument,
    DocumentType,
    ProcessingStatus,
    SimulationRequest,
    SimulationResult,
    RecommendationReport,
    PaystubData,
)
from pii_redaction import PIIRedactor, redact_sensitive_data
from tax_simulator import TaxCalculator, TaxSimulator, RecommendationEngine, IncomeProjector
from llm_prompts import (
    PAYSTUB_EXTRACTION_SYSTEM_PROMPT,
    W2_EXTRACTION_SYSTEM_PROMPT,
    DOCUMENT_CLASSIFICATION_PROMPT,
    get_tax_strategy_prompt,
    build_profile_summary,
    build_calculation_summary,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# APPLICATION SETUP
# =============================================================================

# In-memory storage (replace with database in production)
profiles_db: Dict[str, UserFinancialProfile] = {}
documents_db: Dict[str, RedactedDocument] = {}
processing_jobs: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("TaxGuard AI starting up...")
    # Initialize components
    yield
    logger.info("TaxGuard AI shutting down...")


app = FastAPI(
    title="TaxGuard AI",
    description="Privacy-first tax estimation API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# MOCK LLM CLIENT (Replace with actual OpenAI/Anthropic client)
# =============================================================================

class MockLLMClient:
    """
    Mock LLM client for development.
    Replace with actual GPT-5.1 or Claude API client.
    """
    
    async def extract_paystub_data(self, redacted_text: str) -> dict:
        """
        Mock paystub extraction.
        In production, this calls the actual LLM API.
        """
        # This is a mock - in production, call the LLM
        return {
            "document_type": "paystub",
            "extraction_confidence": 0.85,
            "pay_info": {
                "pay_date": None,
                "pay_frequency": "biweekly"
            },
            "current_period": {
                "gross_pay": None,
                "federal_tax": None
            },
            "year_to_date": {
                "gross": None,
                "federal_tax": None
            },
            "inferences": {
                "pay_frequency_inferred": True,
                "pay_frequency_reasoning": "Mock inference"
            }
        }
    
    async def classify_document(self, redacted_text: str) -> dict:
        """Mock document classification."""
        # Simple heuristics for classification
        text_lower = redacted_text.lower()
        
        if "form w-2" in text_lower or "wage and tax statement" in text_lower:
            return {"document_type": "w2", "confidence": 0.9}
        elif "form 1040" in text_lower:
            return {"document_type": "form_1040", "confidence": 0.9}
        elif "ytd" in text_lower or "gross pay" in text_lower or "net pay" in text_lower:
            return {"document_type": "paystub", "confidence": 0.85}
        elif "1099" in text_lower:
            if "nec" in text_lower:
                return {"document_type": "form_1099_nec", "confidence": 0.8}
            elif "int" in text_lower:
                return {"document_type": "form_1099_int", "confidence": 0.8}
            elif "div" in text_lower:
                return {"document_type": "form_1099_div", "confidence": 0.8}
        
        return {"document_type": "unknown", "confidence": 0.3}
    
    async def generate_strategy_analysis(
        self, 
        profile_summary: str, 
        calculation_summary: str
    ) -> str:
        """Mock strategy generation."""
        return """## TAX STRATEGY ANALYSIS

### SITUATION SUMMARY
Based on the projected income and current withholding, you are on track for a moderate tax situation.

### BASIC RECOMMENDATIONS
1. **Maximize 401(k) Contributions** - Increase your contributions to reduce taxable income.
2. **Consider HSA Contributions** - If you have an HSA-eligible plan, maximize contributions.

### ADVANCED RECOMMENDATIONS  
1. **Tax Loss Harvesting** - If you have investment losses, consider harvesting them.

### PRIORITY ACTIONS
1. Review and adjust 401(k) contribution percentage
2. Make HSA contributions before year-end

Note: This is a mock response. In production, this would be generated by GPT-5.1."""


# Global LLM client instance
llm_client = MockLLMClient()


# =============================================================================
# OCR SERVICE (Mock - replace with Tesseract or cloud service)
# =============================================================================

class OCRService:
    """
    OCR service for extracting text from documents.
    In production, use Tesseract, AWS Textract, or Google Document AI.
    """
    
    async def extract_text(self, file_content: bytes, content_type: str) -> str:
        """
        Extract text from uploaded file.
        
        Args:
            file_content: Raw file bytes
            content_type: MIME type (application/pdf, image/png, etc.)
        
        Returns:
            Extracted text
        """
        # In production, integrate with actual OCR
        # For now, return placeholder
        
        if content_type == "application/pdf":
            # Use pdfplumber or similar
            try:
                import pdfplumber
                import io
                
                with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                    text = ""
                    for page in pdf.pages:
                        text += page.extract_text() or ""
                    return text
            except ImportError:
                logger.warning("pdfplumber not installed")
                return "[OCR placeholder - install pdfplumber for PDF support]"
                
        elif content_type.startswith("image/"):
            # Use pytesseract
            try:
                import pytesseract
                from PIL import Image
                import io
                
                image = Image.open(io.BytesIO(file_content))
                return pytesseract.image_to_string(image)
            except ImportError:
                logger.warning("pytesseract not installed")
                return "[OCR placeholder - install pytesseract for image support]"
        
        return "[Unsupported file type]"


ocr_service = OCRService()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateProfileRequest(BaseModel):
    filing_status: str = "single"
    age: Optional[int] = None


class UpdateProfileRequest(BaseModel):
    updates: Dict[str, Any]


class ManualEntryRequest(BaseModel):
    profile_id: str
    data_type: str  # "paystub", "w2", "income", etc.
    data: Dict[str, Any]


class SimulateRequest(BaseModel):
    profile_id: str
    changes: Dict[str, float]
    scenario_name: Optional[str] = "Custom"


class ChatRequest(BaseModel):
    profile_id: str
    message: str


class UploadResponse(BaseModel):
    document_id: str
    status: str
    message: str


class ProfileResponse(BaseModel):
    profile_id: str
    profile: Dict[str, Any]
    tax_result: Optional[Dict[str, Any]] = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_profile(profile_id: str) -> UserFinancialProfile:
    """Get profile or raise 404."""
    if profile_id not in profiles_db:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    return profiles_db[profile_id]


async def process_document_pipeline(
    document_id: str,
    file_content: bytes,
    content_type: str,
    profile_id: str
):
    """
    Complete document processing pipeline.
    
    1. OCR extraction
    2. PII redaction
    3. LLM data extraction
    4. Profile update
    """
    try:
        # Update status
        processing_jobs[document_id] = {
            "status": ProcessingStatus.PROCESSING,
            "started_at": datetime.utcnow()
        }
        
        # Step 1: OCR
        logger.info(f"[{document_id}] Running OCR...")
        raw_text = await ocr_service.extract_text(file_content, content_type)
        
        # Step 2: PII Redaction (THE CRITICAL PRIVACY STEP)
        logger.info(f"[{document_id}] Redacting PII...")
        processing_jobs[document_id]["status"] = ProcessingStatus.REDACTING
        
        redactor = PIIRedactor(use_ner=True)
        redaction_result = redactor.redact_sensitive_data(raw_text)
        
        # Store redacted document (never the original)
        documents_db[document_id] = RedactedDocument(
            document_id=document_id,
            original_filename=processing_jobs[document_id].get("filename", "unknown"),
            document_type=DocumentType.UNKNOWN,
            redacted_text=redaction_result.redacted_text,
            redaction_map=redaction_result.token_map,
            pii_found=list(redaction_result.pii_types_found),
            extraction_confidence=0.0
        )
        
        logger.info(f"[{document_id}] Redacted {redaction_result.redaction_count} PII items")
        
        # Step 3: Document Classification
        logger.info(f"[{document_id}] Classifying document...")
        classification = await llm_client.classify_document(redaction_result.redacted_text)
        doc_type = DocumentType(classification.get("document_type", "unknown"))
        documents_db[document_id].document_type = doc_type
        
        # Step 4: LLM Data Extraction (on REDACTED text only)
        logger.info(f"[{document_id}] Extracting data via LLM...")
        processing_jobs[document_id]["status"] = ProcessingStatus.EXTRACTING
        
        if doc_type == DocumentType.PAYSTUB:
            extracted = await llm_client.extract_paystub_data(redaction_result.redacted_text)
            documents_db[document_id].extraction_confidence = extracted.get("extraction_confidence", 0)
            
            # Update profile with extracted data
            if profile_id in profiles_db:
                profile = profiles_db[profile_id]
                update_profile_from_paystub(profile, extracted)
        
        # Mark complete
        processing_jobs[document_id]["status"] = ProcessingStatus.COMPLETED
        processing_jobs[document_id]["completed_at"] = datetime.utcnow()
        
        logger.info(f"[{document_id}] Processing complete")
        
    except Exception as e:
        logger.error(f"[{document_id}] Processing failed: {e}")
        processing_jobs[document_id]["status"] = ProcessingStatus.FAILED
        processing_jobs[document_id]["error"] = str(e)


def update_profile_from_paystub(profile: UserFinancialProfile, extracted: dict):
    """Update profile with extracted paystub data."""
    
    ytd = extracted.get("year_to_date", {})
    current = extracted.get("current_period", {})
    pay_info = extracted.get("pay_info", {})
    
    # Update YTD values if present
    if ytd.get("gross"):
        profile.ytd_income = ytd["gross"]
    if ytd.get("federal_tax"):
        profile.ytd_federal_withheld = ytd["federal_tax"]
    if ytd.get("state_tax"):
        profile.ytd_state_withheld = ytd["state_tax"]
    if ytd.get("401k"):
        profile.ytd_401k_traditional = ytd["401k"]
    if ytd.get("hsa"):
        profile.ytd_hsa = ytd["hsa"]
    
    # Update pay frequency
    if pay_info.get("pay_frequency"):
        try:
            profile.pay_frequency = PayFrequency(pay_info["pay_frequency"])
        except ValueError:
            pass
    
    # Estimate current pay period from YTD and current period
    if current.get("gross_pay") and ytd.get("gross"):
        estimated_period = int(ytd["gross"] / current["gross_pay"])
        profile.current_pay_period = max(1, estimated_period)
    
    # Trigger projection recalculation
    profile.updated_at = datetime.utcnow()


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """API health check."""
    return {
        "service": "TaxGuard AI",
        "version": "1.0.0",
        "status": "healthy",
        "privacy_mode": "enabled"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "ocr": "ready",
            "pii_redaction": "ready",
            "tax_calculator": "ready",
            "llm_integration": "mock_mode"  # Change when using real LLM
        }
    }


# --- PROFILE ENDPOINTS ---

@app.post("/api/profiles", response_model=ProfileResponse)
async def create_profile(request: CreateProfileRequest):
    """Create a new user profile."""
    
    # Map filing status
    try:
        filing_status = FilingStatus(request.filing_status.lower().replace(" ", "_"))
    except ValueError:
        filing_status = FilingStatus.SINGLE
    
    profile = UserFinancialProfile(
        filing_status=filing_status,
        age=request.age
    )
    
    profiles_db[profile.profile_id] = profile
    
    return ProfileResponse(
        profile_id=profile.profile_id,
        profile=profile.model_dump()
    )


@app.get("/api/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile_endpoint(profile_id: str):
    """Get a profile by ID."""
    profile = get_profile(profile_id)
    
    # Calculate current tax projection
    calculator = TaxCalculator()
    result = calculator.calculate_tax(profile)
    
    return ProfileResponse(
        profile_id=profile_id,
        profile=profile.model_dump(),
        tax_result=result.model_dump()
    )


@app.patch("/api/profiles/{profile_id}")
async def update_profile(profile_id: str, request: UpdateProfileRequest):
    """Update profile fields."""
    profile = get_profile(profile_id)
    
    for key, value in request.updates.items():
        if hasattr(profile, key):
            # Handle special types
            if key == "filing_status":
                try:
                    value = FilingStatus(value)
                except ValueError:
                    continue
            elif key == "pay_frequency":
                try:
                    value = PayFrequency(value)
                except ValueError:
                    continue
            
            setattr(profile, key, value)
    
    # Trigger recalculation
    profile.updated_at = datetime.utcnow()
    profile = profile.model_validate(profile.model_dump())
    profiles_db[profile_id] = profile
    
    return {"status": "updated", "profile_id": profile_id}


# --- DOCUMENT UPLOAD ENDPOINTS ---

@app.post("/api/documents/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    profile_id: str = Form(...)
):
    """
    Upload a document for processing.
    
    The document goes through:
    1. OCR text extraction
    2. PII redaction (the privacy air gap)
    3. LLM data extraction (on redacted text only)
    4. Profile update
    """
    # Validate profile exists
    if profile_id not in profiles_db:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Read file content
    content = await file.read()
    document_id = str(uuid.uuid4())
    
    # Store job info
    processing_jobs[document_id] = {
        "status": ProcessingStatus.PENDING,
        "filename": file.filename,
        "profile_id": profile_id,
        "created_at": datetime.utcnow()
    }
    
    # Process in background
    background_tasks.add_task(
        process_document_pipeline,
        document_id,
        content,
        file.content_type,
        profile_id
    )
    
    return UploadResponse(
        document_id=document_id,
        status="processing",
        message=f"Document {file.filename} queued for processing"
    )


@app.get("/api/documents/{document_id}/status")
async def get_document_status(document_id: str):
    """Get processing status of a document."""
    if document_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Document not found")
    
    job = processing_jobs[document_id]
    response = {
        "document_id": document_id,
        "status": job["status"].value if isinstance(job["status"], ProcessingStatus) else job["status"],
        "filename": job.get("filename"),
    }
    
    if job.get("error"):
        response["error"] = job["error"]
    
    if document_id in documents_db:
        doc = documents_db[document_id]
        response["document_type"] = doc.document_type.value
        response["pii_types_found"] = doc.pii_found
        response["extraction_confidence"] = doc.extraction_confidence
    
    return response


# --- MANUAL DATA ENTRY ---

@app.post("/api/profiles/{profile_id}/manual-entry")
async def manual_entry(profile_id: str, request: ManualEntryRequest):
    """
    Manually enter financial data.
    For users who prefer to type rather than upload.
    """
    profile = get_profile(profile_id)
    data = request.data
    
    if request.data_type == "paystub":
        # Update from manual paystub entry
        if "gross_pay" in data:
            profile.ytd_income = data.get("ytd_gross", data["gross_pay"])
        if "federal_tax" in data:
            profile.ytd_federal_withheld = data.get("ytd_federal_tax", data["federal_tax"])
        if "pay_frequency" in data:
            try:
                profile.pay_frequency = PayFrequency(data["pay_frequency"])
            except ValueError:
                pass
        if "current_period" in data:
            profile.current_pay_period = data["current_period"]
        if "401k" in data:
            profile.ytd_401k_traditional = data.get("ytd_401k", data["401k"])
        if "hsa" in data:
            profile.ytd_hsa = data.get("ytd_hsa", data["hsa"])
    
    elif request.data_type == "income":
        # Update income sources
        for field in ["interest_income", "dividend_income", "capital_gains_long", 
                     "capital_gains_short", "self_employment_income", "other_income"]:
            if field in data:
                setattr(profile, field, data[field])
    
    elif request.data_type == "deductions":
        # Update deductions
        for field in ["mortgage_interest", "state_local_taxes_paid", 
                     "charitable_donations", "medical_expenses"]:
            if field in data:
                setattr(profile, field, data[field])
        if "prefers_itemized" in data:
            profile.prefers_itemized = data["prefers_itemized"]
    
    # Recalculate
    profile.updated_at = datetime.utcnow()
    profile = profile.model_validate(profile.model_dump())
    profiles_db[profile_id] = profile
    
    return {"status": "updated", "profile_id": profile_id}


# --- TAX CALCULATION ---

@app.post("/api/profiles/{profile_id}/calculate")
async def calculate_tax(profile_id: str, include_recommendations: bool = True):
    """
    Calculate tax projection for a profile.
    
    This runs the ACTUAL tax calculation locally in Python.
    The LLM is NOT used for tax math.
    """
    profile = get_profile(profile_id)
    
    calculator = TaxCalculator()
    result = calculator.calculate_tax(profile)
    
    response = {
        "profile_id": profile_id,
        "tax_result": result.model_dump(),
    }
    
    if include_recommendations:
        engine = RecommendationEngine()
        recommendations = engine.generate_recommendations(profile)
        response["recommendations"] = recommendations.model_dump()
    
    return response


# --- SIMULATION ---

@app.post("/api/profiles/{profile_id}/simulate")
async def run_simulation(profile_id: str, request: SimulateRequest):
    """
    Run a what-if simulation.
    
    Example changes:
    - {"extra_401k": 5000} - Add $5k more to 401k
    - {"filing_status": "married_filing_jointly"} - Change filing status
    """
    profile = get_profile(profile_id)
    
    simulator = TaxSimulator(profile)
    result = simulator.run_simulation(request.changes, request.scenario_name or "Custom")
    
    return {
        "scenario_name": result.scenario_name,
        "is_beneficial": result.is_beneficial,
        "tax_difference": result.tax_difference,
        "refund_difference": result.refund_difference,
        "summary": result.summary,
        "baseline": result.baseline.model_dump(),
        "simulated": result.simulated.model_dump(),
    }


@app.post("/api/profiles/{profile_id}/simulate/optimal")
async def find_optimal_scenario(profile_id: str):
    """
    Run simulations to find optimal tax-saving strategies.
    """
    profile = get_profile(profile_id)
    simulator = TaxSimulator(profile)
    
    scenarios = []
    
    # Max 401(k)
    if profile.remaining_401k_room > 0:
        scenarios.append(simulator.find_optimal_401k())
    
    # Max HSA
    if profile.remaining_hsa_room > 0:
        scenarios.append(simulator.find_optimal_hsa())
    
    # Combined
    if profile.remaining_401k_room > 0 or profile.remaining_hsa_room > 0:
        combined_changes = {}
        if profile.remaining_401k_room > 0:
            combined_changes["extra_401k_traditional"] = profile.remaining_401k_room
        if profile.remaining_hsa_room > 0:
            combined_changes["extra_hsa"] = profile.remaining_hsa_room
        
        combined_result = simulator.run_simulation(combined_changes, "Max All Pre-Tax")
        scenarios.append(combined_result)
    
    return {
        "scenarios": [
            {
                "name": s.scenario_name,
                "is_beneficial": s.is_beneficial,
                "tax_difference": s.tax_difference,
                "summary": s.summary,
            }
            for s in scenarios
        ],
        "best_scenario": max(scenarios, key=lambda s: -s.tax_difference).scenario_name if scenarios else None
    }


# --- AI STRATEGY ANALYSIS ---

@app.post("/api/profiles/{profile_id}/strategy")
async def get_strategy_analysis(profile_id: str):
    """
    Get AI-generated tax strategy analysis.
    
    The AI receives:
    1. REDACTED profile summary (no PII)
    2. Pre-calculated tax numbers (from Python, not LLM)
    3. Authoritative tax bracket information
    
    The AI generates natural language recommendations.
    """
    profile = get_profile(profile_id)
    
    # Calculate tax (in Python)
    calculator = TaxCalculator()
    result = calculator.calculate_tax(profile)
    
    # Build summaries for LLM
    profile_data = profile.model_dump()
    profile_data["total_pay_periods"] = PAY_PERIODS_PER_YEAR[profile.pay_frequency.value]
    profile_data["remaining_401k_room"] = profile.remaining_401k_room
    profile_data["remaining_hsa_room"] = profile.remaining_hsa_room
    
    profile_summary = build_profile_summary(profile_data)
    calculation_summary = build_calculation_summary(result.model_dump())
    
    # Get AI analysis
    analysis = await llm_client.generate_strategy_analysis(
        profile_summary,
        calculation_summary
    )
    
    return {
        "profile_id": profile_id,
        "calculation": result.model_dump(),
        "ai_analysis": analysis,
        "generated_at": datetime.utcnow().isoformat(),
        "disclaimer": "This is AI-generated guidance, not professional tax advice."
    }


# --- TAX REFERENCE DATA ---

@app.get("/api/reference/brackets")
async def get_tax_brackets(filing_status: Optional[str] = None):
    """Get 2025 tax bracket information."""
    from tax_constants import TAX_BRACKETS_2025, STANDARD_DEDUCTION_2025
    
    if filing_status:
        try:
            status = FilingStatus(filing_status)
            return {
                "filing_status": status.value,
                "brackets": [
                    {"limit": b[0], "rate": b[1]}
                    for b in TAX_BRACKETS_2025[status]
                ],
                "standard_deduction": STANDARD_DEDUCTION_2025[status]
            }
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid filing status")
    
    # Return all
    return {
        status.value: {
            "brackets": [
                {"limit": b[0] if b[0] != float('inf') else "unlimited", "rate": b[1]}
                for b in brackets
            ],
            "standard_deduction": STANDARD_DEDUCTION_2025[status]
        }
        for status, brackets in TAX_BRACKETS_2025.items()
    }


@app.get("/api/reference/limits")
async def get_contribution_limits():
    """Get 2025 contribution limits."""
    from tax_constants import CONTRIBUTION_LIMITS_2025
    return CONTRIBUTION_LIMITS_2025


# --- ERROR HANDLERS ---

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("DEBUG") else "An error occurred"
        }
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
