import json
from engine.notifier import EmailNotifier

def run_test():
    print("Loading config.json...")
    config = json.load(open("config/config.json"))
    
    print("Initializing EmailNotifier...")
    notifier = EmailNotifier(config)
    
    print("Sending test email to team_emails...")
    success = notifier.send("test_alert", "This is an automated test confirming the new SMTP tracking system works perfectly!")
    
    if success:
        print("\n[SUCCESS] Email sent successfully! Check your inbox.")
    else:
        print("\n[FAILED] Failed to send email. Ensure you have added your 'sender_app_password' in config.json and it is correct.")

if __name__ == "__main__":
    run_test()
