import dns.resolver
import smtplib
from fastapi import FastAPI, HTTPException, Query
from pydantic import validate_email

# --- Initialize FastAPI App ---
app = FastAPI(
    title="Free Email Validator API",
    description="An API to validate email addresses using Syntax, DNS, and SMTP checks.",
    version="1.0.0",
)

# --- The Core Validation Logic (Our "Machine") ---

def validate_email_full(email: str):
    """
    Performs a three-stage validation of an email address.
    """
    # Create a dictionary to hold our results
    validation_results = {
        "email": email,
        "is_valid": False,
        "checks": {
            "syntax_valid": False,
            "domain_has_mx": False,
            "mailbox_exists": "unchecked",  # Can be: true, false, or undetermined
        },
        "reason": ""
    }

    # === Stage 1: Syntax Validation ===
    try:
        # Pydantic's validate_email is excellent and strict.
        # It returns a tuple of (local_part, domain_part) if valid.
        local_part, domain = validate_email(email)
        validation_results["checks"]["syntax_valid"] = True
    except ValueError:
        validation_results["reason"] = "Invalid email syntax."
        return validation_results

    # === Stage 2: DNS (MX Record) Validation ===
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        if mx_records:
            validation_results["checks"]["domain_has_mx"] = True
            # Get the first mail exchange server address
            mail_exchange = str(mx_records[0].exchange)
        else:
            validation_results["reason"] = "Domain does not have MX records."
            return validation_results
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        validation_results["reason"] = "Could not resolve domain or find MX records."
        return validation_results

    # === Stage 3: SMTP Mailbox Validation ===
    # **IMPORTANT CAVEAT**: This check can be unreliable and may be blocked
    # by free hosting providers like Hugging Face Spaces.
    try:
        # Connect to the mail server (port 25 is standard for SMTP)
        with smtplib.SMTP(mail_exchange, timeout=10) as server:
            server.set_debuglevel(0)  # Set to 1 to see the full conversation
            server.helo('example.com')  # Identify ourselves
            server.mail('test@example.com')  # Set the sender
            
            # The crucial part: ask the server if the recipient exists
            # A status code of 250 means the user exists.
            # A code of 550 means the user does not exist.
            code, message = server.rcpt(email)
            
            if code == 250:
                validation_results["checks"]["mailbox_exists"] = True
                validation_results["is_valid"] = True # This is our highest confidence level
                validation_results["reason"] = "Email appears to be valid and deliverable."
            elif code == 550:
                validation_results["checks"]["mailbox_exists"] = False
                validation_results["reason"] = "Mailbox does not exist (SMTP check)."
            else:
                # Catch-all servers or other issues
                validation_results["checks"]["mailbox_exists"] = "undetermined"
                validation_results["reason"] = f"SMTP check was inconclusive (Code: {code}). This could be a catch-all address."
                # We can still consider it "valid" if the syntax/DNS passed
                validation_results["is_valid"] = True 

    except Exception as e:
        # Many things can go wrong: timeouts, connection refused (port 25 blocked), etc.
        validation_results["checks"]["mailbox_exists"] = "undetermined"
        validation_results["reason"] = "SMTP check failed (could be a firewall or temporary server issue)."
        # If syntax and DNS passed, we can still say it's "valid" with lower confidence.
        validation_results["is_valid"] = True

    return validation_results


# --- API Endpoints ---

@app.get("/")
def read_root():
    """ A simple root endpoint to show that the API is running. """
    return {
        "message": "Welcome to the Email Validator API!",
        "usage": "Go to /validate?email=your_email@example.com to use the API."
    }

@app.get("/validate")
def validate_email_endpoint(email: str = Query(..., description="The email address to validate.")):
    """
    Validates a single email address using syntax, DNS (MX), and SMTP checks.
    """
    if not email:
        raise HTTPException(status_code=400, detail="Email query parameter is required.")
    
    result = validate_email_full(email)
    return result
