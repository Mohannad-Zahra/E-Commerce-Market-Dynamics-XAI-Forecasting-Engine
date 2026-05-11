import os
import resend
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure the API key is picked up
resend.api_key = os.getenv("RESEND_API_KEY")

try:
    print(f"Testing Resend API with Key: {resend.api_key[:5]}...")
    
    # Send a simple test email
    r = resend.Emails.send({
        "from": "Laptop Deal Alerts <onboarding@resend.dev>",
        "to": "hr58g3@gmail.com",
        "subject": "Resend API Test - Recommendation System",
        "html": "<h2>Success!</h2><p>The Resend API integration is working perfectly.</p>"
    })
    
    print(f"Success! Email sent. Resend Response ID: {r.get('id')}")
except Exception as e:
    print(f"Failed to send email. Error: {e}")
