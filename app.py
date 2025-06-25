import requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import validate_email, EmailStr
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Email Validator - The Working One",
    version="6.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def validate_email_full(email: str):
    response = {
        "email": email,
        "is_valid": False,
        "checks": {"syntax_valid": False, "domain_has_mx_records": False},
        "reason": "Validation not started."
    }

    # === Stage 1: Syntax Validation ===
    try:
        validated_email: EmailStr = validate_email(email)[1]
        domain = validated_email.split('@')[1]
        response["checks"]["syntax_valid"] = True
    except (ValueError, IndexError):
        response["reason"] = "Invalid email syntax."
        return response

    # === Stage 2: DNS MX Record Validation via DNS-over-HTTPS ===
    try:
        url = f"https://cloudflare-dns.com/dns-query?name={domain}&type=MX"
        headers = {'accept': 'application/dns-json'}
        api_response = requests.get(url, headers=headers, timeout=10)
        api_response.raise_for_status()
        data = api_response.json()

        # The most robust check possible:
        # 1. Check if the response status is 0 (NOERROR)
        # 2. Check if the "Answer" key exists in the response
        # 3. Check if the list associated with "Answer" is not empty
        if data.get("Status") == 0 and "Answer" in data and len(data["Answer"]) > 0:
            response["checks"]["domain_has_mx_records"] = True
            response["is_valid"] = True
            response["reason"] = "Email syntax is valid and domain has MX records."
        else:
            response["reason"] = "The domain is valid but does not have any MX records."

    except requests.exceptions.RequestException as e:
        response["reason"] = f"Network error when checking domain: {e}"

    return response

@app.get("/")
def read_root():
    return {"message": "Welcome to the final, working Email Validator API!"}

@app.get("/validate")
def validate_email_endpoint(email: str = Query(..., description="The email address to validate.")):
    if not email:
        raise HTTPException(status_code=400, detail="Email query parameter is required.")
    return validate_email_full(email)
