from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

from django.test import TestCase

from accounts.models import User
from core.encryption import encrypt_value
from smtp_servers.imap_sent import save_message_to_sent_folder
from smtp_servers.models import SmtpServer


class ImapSentCopyTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="SecurePass123!",
            username="owner",
            is_verified=True,
        )
        self.smtp_server = SmtpServer.objects.create(
            owner=self.user,
            name="Test SMTP",
            host="mail.example.com",
            port=465,
            username="info@example.com",
            password_encrypted=encrypt_value("secret"),
            encryption=SmtpServer.Encryption.SSL,
            from_email="info@example.com",
            is_active=True,
            save_copy_to_sent=True,
            imap_port=993,
        )
        self.message = MIMEMultipart("alternative")
        self.message["Subject"] = "Hello"
        self.message["From"] = "info@example.com"
        self.message["To"] = "user@gmail.com"
        self.message.attach(MIMEText("Hi", "plain", "utf-8"))

    @patch("smtp_servers.imap_sent.imaplib.IMAP4_SSL")
    def test_save_message_to_sent_folder_appends_copy(self, mock_imap_cls):
        mail = MagicMock()
        mail.list.return_value = ("OK", [b'(\\HasNoChildren) "." INBOX.Sent'])
        mail.append.return_value = ("OK", [b"APPENDUID 1 1"])
        mock_imap_cls.return_value = mail

        result = save_message_to_sent_folder(
            smtp_server=self.smtp_server,
            message=self.message,
        )

        self.assertTrue(result)
        mail.login.assert_called_once_with("info@example.com", "secret")
        mail.append.assert_called_once()
        args = mail.append.call_args[0]
        self.assertEqual(args[0], "INBOX.Sent")
        self.assertEqual(args[1], "\\Seen")

    def test_skips_when_disabled(self):
        self.smtp_server.save_copy_to_sent = False
        self.smtp_server.save()

        result = save_message_to_sent_folder(
            smtp_server=self.smtp_server,
            message=self.message,
        )

        self.assertFalse(result)
