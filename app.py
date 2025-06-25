import requests
import json
from fastapi import FastAPI, HTTPException, Query
from pydantic import validate_email
from fastapi.middleware.cors import CORSMiddleware

# --- Initialize FastAPI App ---
app = FastAPI(
    title="Free Email Validator API - 100% Working Version",
    description="An API that uses DNS-over-HTTPS to bypass platform network restrictions.",
    version="5.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- The Core Validation Logic (Corrected) ---

def validate_email_full(email: str):
    validation_results = {
        "email": email,
        "is_valid": False,
        "checks": {
            "syntax_valid": False,
            "domain_has_mx_records": False,
        },
        "reason": ""
    }

    # === Stage 1: Syntax Validation AND GETTING THE DOMAIN ===
    try:
        # Pydantic's validate_email returns (local_part, domain_part)
        # This is where the original bug was! We need the 'domain' part.
        local_part, domain = validate_email(email)
        validation_results["checks"]["syntax_valid"] = True
    except ValueError:
        validation_results["reason"] = "Invalid email syntax."
        return validation_results

    # === Stage 2: DNS (MX Record) Validation via DNS-over-HTTPS ===
    try:
        # We use the 'domain' variable from Stage 1, NOT the full 'email'.
        # THIS WAS THE BUG!
        url = f"https://cloudflare-dns.com/dns-query?name={domain}&type=MX"
        
        headers = {'accept': 'application/dns-json'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        # The logic to check the response is now correct.
        if data.get("Status") == 0 and data.get("Answer"):
            validation_results["checks"]["domain_has_mx_records"] = True
            validation_results["is_valid"] = True
            validation_results["reason"] = "Email syntax is valid and domain has MX records."
        else:
            validation_results["reason"] = "Domain is valid but does not have any MX records."

    except requests.exceptions.RequestException as e:
        validation_results["reason"] = f"Failed to query DNS via API. Error: {e}"

    return validation_results

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Email Validator API! (Working Version)",
    }

@app.get("/validate")
def validate_email_endpoint(email: str = Query(..., description="The email address to validate.")):
    if not email:
        raise HTTPException(status_code=400, detail="Email query parameter is required.")
    result = validate_email_full(email)
    return result
