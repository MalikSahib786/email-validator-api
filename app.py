import dns.resolver
import smtplib
from fastapi import FastAPI, HTTPException, Query
from pydantic import validate_email
from fastapi.middleware.cors import CORSMiddleware # // NEW: Import the CORS middleware

# --- Initialize FastAPI App ---
app = FastAPI(
    title="Free Email Validator API",
    description="An API to validate email addresses using Syntax, DNS, and SMTP checks.",
    version="1.0.0",
)

# // NEW: Add the CORS Middleware configuration
# This block allows your browser-based website to talk to this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (websites)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# --- The Core Validation Logic (Our "Machine") ---
# (The rest of your code remains exactly the same)

def validate_email_full(email: str):
    """
    Performs a three-stage validation of an email address.
    """
    validation_results = {
        "email": email,
        "is_valid": False,
        "checks": {
            "syntax_valid": False,
            "domain_has_mx": False,
            "mailbox_exists": "unchecked",
        },
        "reason": ""
    }
    try:
        local_part, domain = validate_email(email)
        validation_results["checks"]["syntax_valid"] = True
    except ValueError:
        validation_results["reason"] = "Invalid email syntax."
        return validation_results
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        if mx_records:
            validation_results["checks"]["domain_has_mx"] = True
            mail_exchange = str(mx_records[0].exchange)
        else:
            validation_results["reason"] = "Domain does not have MX records."
            return validation_results
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        validation_results["reason"] = "Could not resolve domain or find MX records."
        return validation_results
    try:
        with smtplib.SMTP(mail_exchange, timeout=10) as server:
            server.set_debuglevel(0)
            server.helo('example.com')
            server.mail('test@example.com')
            code, message = server.rcpt(email)
            if code == 250:
                validation_results["checks"]["mailbox_exists"] = True
                validation_results["is_valid"] = True
                validation_results["reason"] = "Email appears to be valid and deliverable."
            elif code == 550:
                validation_results["checks"]["mailbox_exists"] = False
                validation_results["reason"] = "Mailbox does not exist (SMTP check)."
            else:
                validation_results["checks"]["mailbox_exists"] = "undetermined"
                validation_results["reason"] = f"SMTP check was inconclusive (Code: {code}). This could be a catch-all address."
                validation_results["is_valid"] = True
    except Exception as e:
        validation_results["checks"]["mailbox_exists"] = "undetermined"
        validation_results["reason"] = "SMTP check failed (could be a firewall or temporary server issue)."
        validation_results["is_valid"] = True
    return validation_results

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Email Validator API!",
        "usage": "Go to /validate?email=your_email@example.com to use the API."
    }

@app.get("/validate")
def validate_email_endpoint(email: str = Query(..., description="The email address to validate.")):
    if not email:
        raise HTTPException(status_code=400, detail="Email query parameter is required.")
    result = validate_email_full(email)
    return result
