import dns.resolver
import smtplib
from fastapi import FastAPI, HTTPException, Query
from pydantic import validate_email
from fastapi.middleware.cors import CORSMiddleware

# --- Initialize FastAPI App ---
app = FastAPI(
    title="Free Email Validator API",
    description="An API to validate email addresses using Syntax, DNS, and SMTP checks.",
    version="1.0.0",
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
        
    # --- MODIFICATION START ---
    # We will now use a specific, public DNS resolver to bypass platform limitations.
    try:
        # Create a resolver object
        resolver = dns.resolver.Resolver()
        # Point it to public DNS servers (Google and Cloudflare)
        resolver.nameservers = ['8.8.8.8', '1.1.1.1'] 
        
        # Use our custom resolver instead of the default one
        mx_records = resolver.resolve(domain, 'MX')
    # --- MODIFICATION END ---
        
        if mx_records:
            validation_results["checks"]["domain_has_mx"] = True
            mail_exchange = str(mx_records[0].exchange)
        else:
            validation_results["reason"] = "Domain does not have MX records (checked with public DNS)."
            return validation_results
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.exception.Timeout):
        validation_results["reason"] = "Could not resolve domain or find MX records using public DNS."
        return validation_results

    # The SMTP check part remains the same. It may still fail due to port 25 being blocked.
    # But the DNS check, which was our main problem, should now work.
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
        validation_results["reason"] = "SMTP check failed (likely a firewall blocking port 25)."
        # If syntax and DNS passed, we still consider it valid.
        if validation_results["checks"]["domain_has_mx"]:
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
