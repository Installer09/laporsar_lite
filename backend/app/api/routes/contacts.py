from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, desc
from pydantic import BaseModel, ConfigDict, Field, field_validator
from html import escape
import csv
import io
import re
from datetime import datetime

from app.db.session import get_db
from app.models.contact import Contact
from app.core.security import verify_jwt, verify_admin, verify_operator_or_admin
from app.core.rate_limiter import sanitize_csv_cell

router = APIRouter(dependencies=[Depends(verify_operator_or_admin)])

class ContactBase(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    phone_number: str = Field(..., min_length=8, max_length=50, pattern=r"^\+?[0-9\-\s]+$")
    source: Optional[str] = Field("manual", max_length=50)
    notes: Optional[str] = None
    last_location: Optional[str] = Field(None, max_length=255)

    @field_validator("name", "notes", "last_location")
    @classmethod
    def sanitize_contact_fields(cls, v):
        if v is None:
            return v
        return escape(v.strip()) if isinstance(v, str) else v

class ContactCreate(ContactBase):
    pass

class ContactUpdate(ContactBase):
    phone_number: Optional[str] = Field(None, min_length=8, max_length=50, pattern=r"^\+?[0-9\-\s]+$")

class ContactResponse(ContactBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

@router.get("", response_model=List[ContactResponse])
async def get_contacts(
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    query = select(Contact).order_by(desc(Contact.created_at))
    if search:
        query = query.where(
            or_(
                Contact.name.ilike(f"%{search}%"),
                Contact.phone_number.ilike(f"%{search}%")
            )
        )
    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/export")
async def export_contacts(db: AsyncSession = Depends(get_db)):
    """Export contacts as a CSV file compatible with Excel."""
    query = select(Contact).order_by(Contact.name.asc())
    result = await db.execute(query)
    contacts = result.scalars().all()

    output = io.StringIO()
    # Write BOM for Excel UTF-8 compatibility
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';', lineterminator='\n')
    
    # Headers
    writer.writerow(["Nama", "Nomor Telepon", "Sumber", "Catatan", "Lokasi Terakhir"])
    
    for contact in contacts:
        writer.writerow([
            sanitize_csv_cell(contact.name),
            sanitize_csv_cell(contact.phone_number),
            sanitize_csv_cell(contact.source or "manual"),
            sanitize_csv_cell(contact.notes),
            sanitize_csv_cell(contact.last_location)
        ])
        
    csv_data = output.getvalue()
    output.close()
    
    filename = f"sarbot_contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_data.encode('utf-8-sig'),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

@router.post("/import")
async def import_contacts(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Import contacts from an uploaded CSV file."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File harus berformat .csv")
        
    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8-sig")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file: {str(e)}")
        
    # Auto-detect delimiter
    first_line = content_str.split("\n")[0] if content_str else ""
    delimiter = ";" if ";" in first_line else ","
    
    reader = csv.reader(io.StringIO(content_str), delimiter=delimiter)
    
    # Read headers
    try:
        headers = next(reader)
    except StopIteration:
        raise HTTPException(status_code=400, detail="File CSV kosong")
        
    # Standardize headers to find positions
    header_map = {
        "name": ["nama", "name", "nama lengkap", "fullname"],
        "phone_number": ["nomor telepon", "phone number", "nomor", "phone", "no", "no telp", "telepon"],
        "source": ["sumber", "source"],
        "notes": ["catatan", "notes", "keterangan", "note"],
        "last_location": ["lokasi terakhir", "last location", "lokasi", "location"]
    }
    
    pos = {}
    for i, h in enumerate(headers):
        h_clean = h.strip().lower()
        for field, synonyms in header_map.items():
            if h_clean in synonyms:
                pos[field] = i
                break
                
    if "phone_number" not in pos:
        raise HTTPException(
            status_code=400, 
            detail="Kolom 'Nomor Telepon' atau 'Phone Number' tidak ditemukan dalam file CSV"
        )
        
    created_count = 0
    updated_count = 0
    failed_rows = []
    
    for row_idx, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
            
        def get_val(field):
            if field in pos and pos[field] < len(row):
                return row[pos[field]].strip()
            return None
            
        name = get_val("name")
        phone_number = get_val("phone_number")
        source = get_val("source") or "manual"
        notes = get_val("notes")
        last_location = get_val("last_location")
        
        if not phone_number:
            failed_rows.append({"row": row_idx, "reason": "Nomor telepon kosong"})
            continue
            
        phone_cleaned = re.sub(r"[^\+0-9\-\s]", "", phone_number)
        if len(phone_cleaned) < 5:
            failed_rows.append({"row": row_idx, "reason": f"Nomor telepon tidak valid: '{phone_number}'"})
            continue
            
        try:
            result = await db.execute(select(Contact).where(Contact.phone_number == phone_cleaned))
            db_contact = result.scalar_one_or_none()
            
            if db_contact:
                if name is not None:
                    db_contact.name = name
                db_contact.source = source
                if notes is not None:
                    db_contact.notes = notes
                if last_location is not None:
                    db_contact.last_location = last_location
                updated_count += 1
            else:
                new_contact = Contact(
                    name=name,
                    phone_number=phone_cleaned,
                    source=source,
                    notes=notes,
                    last_location=last_location
                )
                db.add(new_contact)
                created_count += 1
        except Exception as e:
            failed_rows.append({"row": row_idx, "reason": f"Error database: {str(e)}"})
            
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan transaksi ke database: {str(e)}")
        
    return {
        "status": "success",
        "created": created_count,
        "updated": updated_count,
        "failed_count": len(failed_rows),
        "failed_details": failed_rows
    }

@router.post("", response_model=ContactResponse)
async def create_contact(contact: ContactCreate, db: AsyncSession = Depends(get_db)):
    # Check duplicate
    result = await db.execute(select(Contact).where(Contact.phone_number == contact.phone_number))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Phone number already exists")
        
    new_contact = Contact(**contact.model_dump())
    db.add(new_contact)
    await db.commit()
    await db.refresh(new_contact)
    return new_contact

@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(contact_id: int, contact_update: ContactUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    db_contact = result.scalar_one_or_none()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    update_data = contact_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_contact, key, value)
        
    await db.commit()
    await db.refresh(db_contact)
    return db_contact

@router.delete("/{contact_id}", dependencies=[Depends(verify_admin)])
async def delete_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    db_contact = result.scalar_one_or_none()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    await db.delete(db_contact)
    await db.commit()
    return {"status": "success", "message": "Contact deleted"}
