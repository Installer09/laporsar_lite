from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional
from html import escape
from datetime import datetime

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
    id: int
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
    photo_url: Optional[str] = None

    @field_validator("name")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v)

class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not v or not v.strip():
            raise ValueError("Password tidak boleh kosong")
        return v.strip()

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    photo_url: Optional[str] = None

    @field_validator("name")
    @classmethod
    def sanitize(cls, v): return sanitize_html(v) if v else v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if v is not None and v.strip() == "":
            return None
        return v.strip() if v is not None else None

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    model_config = ConfigDict(from_attributes=True)

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

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

