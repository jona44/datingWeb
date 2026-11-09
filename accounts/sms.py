import logging
import os
import requests
from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class BaseSMSBackend:
    def send_sms(self, phone_number: str, message: str) -> bool:
        raise NotImplementedError("SMS backend must implement send_sms method")


class ConsoleBackend(BaseSMSBackend):
    """
    Development SMS backend that prints the SMS to console and logs it.
    """
    def send_sms(self, phone_number: str, message: str) -> bool:
        separator = "=" * 60
        output = (
            f"\n{separator}\n"
            f"[SMS CONSOLE DISPATCH]\n"
            f"TO: {phone_number}\n"
            f"MESSAGE: {message}\n"
            f"{separator}\n"
        )
        print(output)
        logger.info(f"Console SMS sent to {phone_number}: {message}")
        return True


class TwilioBackend(BaseSMSBackend):
    """
    Twilio SMS integration using REST API.
    """
    def send_sms(self, phone_number: str, message: str) -> bool:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_PHONE_NUMBER")

        if not account_sid or not auth_token or not from_number:
            logger.error("Twilio credentials not configured in environment variables.")
            return False

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        data = {
            "From": from_number,
            "To": phone_number,
            "Body": message,
        }

        try:
            response = requests.post(url, data=data, auth=(account_sid, auth_token), timeout=10)
            if response.status_code in [200, 201]:
                logger.info(f"Twilio SMS dispatched to {phone_number}")
                return True
            else:
                logger.error(f"Twilio SMS failed ({response.status_code}): {response.text}")
                return False
        except Exception as exc:
            logger.exception(f"Error calling Twilio API: {exc}")
            return False


class AfricasTalkingBackend(BaseSMSBackend):
    """
    Africa's Talking SMS integration for East and Southern Africa.
    """
    def send_sms(self, phone_number: str, message: str) -> bool:
        username = os.getenv("AT_USERNAME")
        api_key = os.getenv("AT_API_KEY")
        sender_id = os.getenv("AT_SENDER_ID", "")

        if not username or not api_key:
            logger.error("Africa's Talking credentials not configured in environment variables.")
            return False

        url = "https://api.africastalking.com/version1/messaging"
        if username.lower() == "sandbox":
            url = "https://api.sandbox.africastalking.com/version1/messaging"

        headers = {
            "ApiKey": api_key,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "username": username,
            "to": phone_number,
            "message": message,
        }
        if sender_id:
            data["from"] = sender_id

        try:
            response = requests.post(url, data=data, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                logger.info(f"Africa's Talking SMS dispatched to {phone_number}")
                return True
            else:
                logger.error(f"Africa's Talking SMS failed ({response.status_code}): {response.text}")
                return False
        except Exception as exc:
            logger.exception(f"Error calling Africa's Talking API: {exc}")
            return False


def get_sms_backend() -> BaseSMSBackend:
    backend_path = getattr(settings, "SMS_BACKEND", "accounts.sms.ConsoleBackend")
    try:
        backend_cls = import_string(backend_path)
        return backend_cls()
    except Exception as exc:
        logger.warning(f"Could not load SMS backend '{backend_path}', falling back to ConsoleBackend: {exc}")
        return ConsoleBackend()

