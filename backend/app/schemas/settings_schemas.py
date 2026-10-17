from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional
from html import escape
from datetime import datetime
import re

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^(\+62|62|0)8[1-9][0-9]{7,11}$")
ALLOWED_USER_ROLES = {"Super Admin", "Admin", "Operator", "User"}

def validate_strong_password(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Kata sandi tidak boleh kosong")
    v = v.strip()
    if len(v) < 8:
        raise ValueError("Kata sandi minimal harus 8 karakter")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Kata sandi harus mengandung minimal 1 huruf kapital (A-Z)")
    if not re.search(r"[a-z]", v):
        raise ValueError("Kata sandi harus mengandung minimal 1 huruf kecil (a-z)")
    if not re.search(r"[0-9]", v):
        raise ValueError("Kata sandi harus mengandung minimal 1 angka (0-9)")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=~`]", v):
        raise ValueError("Kata sandi harus mengandung minimal 1 simbol / karakter khusus")
    return v

def sanitize_html(v):
    if v is None:
        return v
    return escape(v.strip()) if isinstance(v, str) else v


class SystemSettingBase(BaseModel):
    key: str
    value: str | None = None

    @field_validator("value")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v)

class SystemSettingResponse(SystemSettingBase):
    id: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)

class SystemSettingsBulkUpdate(BaseModel):
    settings: List[SystemSettingBase]

class LocationBase(BaseModel):
    name: str
    type: str
    lat: float
    lng: float
    address: str | None = None
    unsur: str | None = None
    alut: str | None = None
    icon: str | None = None

    @field_validator("name", "address", "icon")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v)

class LocationCreate(LocationBase):
    pass

class LocationResponse(LocationBase):
    id: int
    tenant_name: Optional[str] = None
    tenant_slug: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ClassificationBase(BaseModel):
    category: str
    keywords: str
    sop_document_id: Optional[int] = None

    @field_validator("category", "keywords")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v)

class ClassificationCreate(ClassificationBase):
    pass

class ClassificationResponse(ClassificationBase):
    id: int
    is_global: bool = False
    model_config = ConfigDict(from_attributes=True)

class UserBase(BaseModel):
    name: str
    email: str
    role: str
    phone: Optional[str] = None
    nip: Optional[str] = None
    jabatan: Optional[str] = None
    photo_url: Optional[str] = None

    @field_validator("name", "nip", "jabatan")
    @classmethod
    def sanitize(cls, v):
        return sanitize_html(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if not v or not EMAIL_REGEX.match(v.strip()):
            raise ValueError("Format email tidak valid (contoh: nama@domain.id)")
        return v.strip().lower()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v is not None and v.strip():
            clean_phone = re.sub(r"[\s\-]", "", v.strip())
            if not PHONE_REGEX.match(clean_phone):
                raise ValueError("Nomor telepon tidak valid. Gunakan format nomor seluler Indonesia (contoh: 08123456789 atau +628123456789)")
            return clean_phone
        return None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        role_clean = v.strip()
        if role_clean not in ALLOWED_USER_ROLES:
            raise ValueError(f"Role '{v}' tidak diizinkan. Pilih salah satu dari: {', '.join(sorted(ALLOWED_USER_ROLES))}")
        return role_clean

class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        return validate_strong_password(v)

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    nip: Optional[str] = None
    jabatan: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    photo_url: Optional[str] = None

    @field_validator("name", "nip", "jabatan")
    @classmethod
    def sanitize(cls, v):
        return sanitize_html(v) if v else v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v is not None and v.strip():
            if not EMAIL_REGEX.match(v.strip()):
                raise ValueError("Format email tidak valid (contoh: nama@domain.id)")
            return v.strip().lower()
        return None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v is not None and v.strip():
            clean_phone = re.sub(r"[\s\-]", "", v.strip())
            if not PHONE_REGEX.match(clean_phone):
                raise ValueError("Nomor telepon tidak valid. Gunakan format nomor seluler Indonesia (contoh: 08123456789 atau +628123456789)")
            return clean_phone
        return None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v is not None and v.strip():
            role_clean = v.strip()
            if role_clean not in ALLOWED_USER_ROLES:
                raise ValueError(f"Role '{v}' tidak diizinkan. Pilih salah satu dari: {', '.join(sorted(ALLOWED_USER_ROLES))}")
            return role_clean
        return None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if v is not None and v.strip():
            return validate_strong_password(v)
        return None

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    model_config = ConfigDict(from_attributes=True)

class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if not v or not EMAIL_REGEX.match(v.strip()):
            raise ValueError("Format email tidak valid (contoh: nama@domain.id)")
        return v.strip().lower()

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        return validate_strong_password(v)

class FormatVariableBase(BaseModel):
    key: str
    description: str
    group: str
    value: Optional[str] = None

    @field_validator("description", "value")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v)

class FormatVariableCreate(FormatVariableBase):
    pass

class FormatVariableResponse(FormatVariableBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class WidgetIntegrationRequestCreate(BaseModel):
    partner_name: str
    website_url: str
    official_email: str
    official_phone: str

    @field_validator("partner_name", "website_url", "official_email", "official_phone")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v)


class WidgetIntegrationRequestResponse(BaseModel):
    id: int
    partner_name: str
    website_url: str
    official_email: str
    official_phone: str
    api_key: Optional[str] = None
    status: str
    created_at: datetime
    verified_at: Optional[datetime] = None
    verified_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class WidgetIntegrationRequestAdminCreate(BaseModel):
    partner_name: str
    website_url: str
    official_email: str
    official_phone: str
    status: str = "APPROVED"

    @field_validator("partner_name", "website_url", "official_email", "official_phone")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v)


class WidgetIntegrationRequestUpdate(BaseModel):
    partner_name: Optional[str] = None
    website_url: Optional[str] = None
    official_email: Optional[str] = None
    official_phone: Optional[str] = None
    status: Optional[str] = None

    @field_validator("partner_name", "website_url", "official_email", "official_phone")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v)

