import re

# Simple RegEx patterns for common PII and sensitive tokens
PII_PATTERNS = {
    # Match standard 16-digit credit cards with optional dashes/spaces
    "CREDIT_CARD": r'\b(?:\d[ -]*?){13,16}\b',
    # Match standard email addresses
    "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    # Match hypothetical DrorPay API keys
    "API_KEY": r'\b(?:dp_live_|dp_test_)[a-zA-Z0-9]{24,}\b'
}

def redact_pii(text: str) -> str:
    """
    Scans the input text for PII (Credit Cards, Emails, API Keys)
    and replaces them with generic placeholders to prevent leaking
    sensitive data to the LLM or Vector Database.
    """
    redacted_text = text
    
    for pii_type, pattern in PII_PATTERNS.items():
        placeholder = f"[REDACTED_{pii_type}]"
        redacted_text = re.sub(pattern, placeholder, redacted_text)
        
    return redacted_text
