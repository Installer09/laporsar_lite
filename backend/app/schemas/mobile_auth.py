from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
import re

class OTPRequest(BaseModel):
    name: str
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Clean whitespaces and dashes
        cleaned = re.sub(r"[\s\-+]", "", v)
        # Convert local 08xxx to 628xxx
        if cleaned.startswith("0"):
            cleaned = "62" + cleaned[1:]
        # Validate that it only contains digits and has reasonable length
        if not cleaned.isdigit() or len(cleaned) < 10 or len(cleaned) > 15:
            raise ValueError("Nomor telepon tidak valid. Gunakan format internasional (misal: 628123456789)")
        return cleaned

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Nama lengkap minimal 2 karakter")
        return stripped

class OTPVerify(BaseModel):
    phone_number: str
    otp_code: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-+]", "", v)
        if cleaned.startswith("0"):
            cleaned = "62" + cleaned[1:]
        return cleaned

    @field_validator("otp_code")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped.isdigit() or len(stripped) != 6:
            raise ValueError("Kode OTP harus berupa 6 digit angka")
        return stripped

class MobileContactResponse(BaseModel):
    id: int
    phone_number: str
    name: Optional[str] = None
    source: str
    
    model_config = ConfigDict(from_attributes=True)

class MobileLoginResponse(BaseModel):
    access_token: str
    token_type: str
    contact: MobileContactResponse
