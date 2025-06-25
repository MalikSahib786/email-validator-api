import requests # Use requests library for HTTP calls
from fastapi import FastAPI, HTTPException, Query
from pydantic import validate_email
from fastapi.middleware.cors import CORSMiddleware

# --- Initialize FastAPI App ---
app = FastAPI(
    title="Free Email Validator API - Unblockable Version",
    description="An API that uses DNS-over-HTTPS to bypass platform network restrictions.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- The Core Validation Logic (Our "Machine") ---

def validate_email_full(email: str):
    """
    Performs a two-stage validation using a public API for DNS checks.
    """
    validation_results = {
        "email": email,
        "is_valid": False,
        "checks": {
            "syntax_valid": False,
            "domain_has_mx_records": False,
        },
        "reason": ""
    }

    # === Stage 1: Syntax Validation (No change) ===
    try:
        local_part, domain = validate_email(email)
        validation_results["checks"]["syntax_valid"] = True
    except ValueError:
        validation_results["reason"] = "Invalid email syntax."
        return validation_results

    # === Stage 2: DNS (MX Record) Validation via DNS-over-HTTPS ===
    # This method will not be blocked by free hosting platforms.
    try:
        # We use Cloudflare's public DNS API
        url = f"https://cloudflare-dns.com/dns-query?name={domain}&type=MX"
        headers = {'accept': 'application/dns-json'}

        # Make the web request
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        data = response.json()

        # Check if the 'Answer' key exists and is not empty
        if data.get("Answer"):
            validation_results["checks"]["domain_has_mx_records"] = True
            validation_results["is_valid"] = True
            validation_results["reason"] = "Email syntax is valid and domain has MX records."
        else:
            validation_results["reason"] = "Domain exists but has no MX records."

    except requests.exceptions.Timeout:
        validation_results["reason"] = "DNS query via API timed out."
    except requests.exceptions.RequestException as e:
        # This will catch other network errors
        validation_results["reason"] = f"Failed to query DNS via API. Error: {e}"

    return validation_results

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Email Validator API! (Unblockable Version)",
    }

@app.get("/validate")
def validate_email_endpoint(email: str = Query(..., description="The email address to validate.")):
    if not email:
        raise HTTPException(status_code=400, detail="Email query parameter is required.")
    result = validate_email_full(email)
    return result
