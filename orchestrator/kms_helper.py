import boto3
from botocore.exceptions import ClientError
import base64
import logging
from typing import Optional
from ..models.models import StructuredResult


# ---------------------- KMS HELPER ----------------------
class KMSHelper:
    """
    AWS KMS Helper for encrypting and decrypting sensitive data.
    
    Features:
        - Encrypt and decrypt strings using a given KMS key.
        - Base64 encoding of ciphertext for JSON-friendly storage.
        - Handles None inputs gracefully.
        - Logging for audit/error tracking.
    """

    def __init__(self, key_id: str, region_name: Optional[str] = None):
        self.key_id = key_id
        self.region_name = region_name
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s %(levelname)s %(name)s: %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.kms_client = boto3.client("kms", region_name=self.region_name)

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """
        Encrypt a plaintext string using AWS KMS and return base64 ciphertext.

        Args:
            plaintext: The string to encrypt. Can be None.

        Returns:
            Base64 encoded ciphertext string, or None if input is None.
        """
        if plaintext is None:
            return None
        try:
            response = self.kms_client.encrypt(
                KeyId=self.key_id,
                Plaintext=plaintext.encode("utf-8")
            )
            return base64.b64encode(response["CiphertextBlob"]).decode("utf-8")
        except ClientError as e:
            self.logger.error(f"KMS encryption failed: {e}")
            raise

    def decrypt(self, ciphertext_b64: Optional[str]) -> Optional[str]:
        """
        Decrypt a base64-encoded ciphertext string using AWS KMS.

        Args:
            ciphertext_b64: Base64 encoded ciphertext, or None.

        Returns:
            Decrypted plaintext string, or None if input is None.
        """
        if ciphertext_b64 is None:
            return None
        try:
            ciphertext_blob = base64.b64decode(ciphertext_b64)
            response = self.kms_client.decrypt(CiphertextBlob=ciphertext_blob)
            return response["Plaintext"].decode("utf-8")
        except ClientError as e:
            self.logger.error(f"KMS decryption failed: {e}")
            raise


# ---------------------- ENCRYPTED STRUCTURED RESULT ----------------------
class StructuredResultEncrypted(StructuredResult):
    """
    Extends StructuredResult to automatically encrypt/decrypt member_number and member_name.
    """
    kms_helper: Optional[KMSHelper] = None

    def set_kms_helper(self, kms_helper: KMSHelper) -> None:
        self.kms_helper = kms_helper

    @property
    def encrypted_member_number(self) -> Optional[str]:
        if not self.kms_helper:
            raise RuntimeError("KMSHelper not set")
        return self.kms_helper.encrypt(self.member_number)

    @property
    def encrypted_member_name(self) -> Optional[str]:
        if not self.kms_helper:
            raise RuntimeError("KMSHelper not set")
        return self.kms_helper.encrypt(self.member_name)

    def decrypt_member_number(self, ciphertext: Optional[str]) -> Optional[str]:
        if not self.kms_helper:
            raise RuntimeError("KMSHelper not set")
        return self.kms_helper.decrypt(ciphertext)

    def decrypt_member_name(self, ciphertext: Optional[str]) -> Optional[str]:
        if not self.kms_helper:
            raise RuntimeError("KMSHelper not set")
        return self.kms_helper.decrypt(ciphertext)
