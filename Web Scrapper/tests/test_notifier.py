import unittest
from unittest.mock import patch, MagicMock
from engine.notifier import EmailNotifier

def make_config():
    return {
        "developer_id": "test_dev",
        "smtp": {
            "host": "smtp.test.com",
            "port": 587,
            "sender_email": "sender@test.com",
            "sender_app_password": "fake_password",
            "team_emails": ["team1@test.com", "team2@test.com"]
        }
    }

class TestEmailNotifier(unittest.TestCase):
    def test_dry_run_when_no_password(self):
        config = make_config()
        config["smtp"]["sender_app_password"] = ""
        notifier = EmailNotifier(config)
        
        result = notifier.send("test_event", "test message")
        self.assertFalse(result)

    def test_dry_run_when_no_team_emails(self):
        config = make_config()
        config["smtp"]["team_emails"] = []
        notifier = EmailNotifier(config)
        
        result = notifier.send("test_event", "test message")
        self.assertFalse(result)

    @patch("smtplib.SMTP")
    def test_successful_dispatch(self, mock_smtp_class):
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server
        
        notifier = EmailNotifier(make_config())
        result = notifier.send("test_event", "test message")
        
        self.assertTrue(result)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("sender@test.com", "fake_password")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()
        
    @patch("smtplib.SMTP")
    def test_smtp_error_returns_false(self, mock_smtp_class):
        import smtplib
        mock_server = MagicMock()
        mock_server.send_message.side_effect = smtplib.SMTPException("Test error")
        mock_smtp_class.return_value = mock_server
        
        notifier = EmailNotifier(make_config())
        result = notifier.send("test_event", "test message")
        
        self.assertFalse(result)

    @patch.object(EmailNotifier, "send", return_value=True)
    def test_convenience_methods(self, mock_send):
        notifier = EmailNotifier(make_config())
        
        notifier.notify_scrape_failure("2b", "error")
        mock_send.assert_called_with(
            "scrape_failed",
            "Scraping failed for '2b': error",
            extra={"retailer_id": "2b", "retailer_name": "2b"},
        )
        
        notifier.notify_upload_failure("2b", 1, 3, "fail")
        self.assertEqual(mock_send.call_count, 2)
        
if __name__ == "__main__":
    unittest.main()
