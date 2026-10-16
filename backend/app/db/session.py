import os
import contextvars
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import Request, HTTPException, status, Depends

from app.db.base_class import Base

load_dotenv()

# Global tenant context variable
tenant_context = contextvars.ContextVar("tenant_slug", default="pusat")

class TenantPartitionedCache(dict):
    """
    A dictionary subclass that transparently partitions keys by the active tenant_slug
    resolved from the context variable `tenant_context`.
    """
    def _get_active_partition(self) -> dict:
        tenant_slug = tenant_context.get()
        return dict.get(self, tenant_slug, {})

    def get(self, key, default=None):
        # Check if the key is a tenant slug (in outer dict)
        if dict.__contains__(self, key):
            return dict.get(self, key, default)
        partition = self._get_active_partition()
        if key in partition:
            return partition[key]
        # Fallback to global partition
        global_partition = dict.get(self, "global", {})
        return global_partition.get(key, default)

    def __getitem__(self, key):
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        partition = self._get_active_partition()
        if key in partition:
            return partition[key]
        global_partition = dict.get(self, "global", {})
        if key in global_partition:
            return global_partition[key]
        raise KeyError(key)

    def __contains__(self, key):
        # If it's a tenant_slug in the outer dict, return True
        if dict.__contains__(self, key):
            return True
        partition = self._get_active_partition()
        if key in partition:
            return True
        global_partition = dict.get(self, "global", {})
        return key in global_partition

    def items(self):
        partition = self._get_active_partition()
        global_partition = dict.get(self, "global", {})
        merged = {**global_partition, **partition}
        return merged.items()

    def values(self):
        partition = self._get_active_partition()
        global_partition = dict.get(self, "global", {})
        merged = {**global_partition, **partition}
        return merged.values()

    def keys(self):
        partition = self._get_active_partition()
        global_partition = dict.get(self, "global", {})
        merged = {**global_partition, **partition}
        return merged.keys()

    def __iter__(self):
        partition = self._get_active_partition()
        global_partition = dict.get(self, "global", {})
        merged = {**global_partition, **partition}
        return iter(merged)

    def __len__(self):
        partition = self._get_active_partition()
        global_partition = dict.get(self, "global", {})
        merged = {**global_partition, **partition}
        return len(merged)


class TenantPartitionedSet(dict):
    """
    A dictionary subclass that behaves like a set for the active tenant.
    """
    def _get_active_partition(self) -> set:
        tenant_slug = tenant_context.get()
        return dict.get(self, tenant_slug, set())

    def __contains__(self, item):
        if dict.__contains__(self, item):
            return True
        return item in self._get_active_partition()

    def __iter__(self):
        return iter(self._get_active_partition())

    def __len__(self):
        return len(self._get_active_partition())

    def get(self, key, default=None):
        return dict.get(self, key, default)


class MultitenantStatusProxy:
    def __init__(self, values):
        self.values = values

    def __bool__(self):
        tenant_slug = tenant_context.get()
        return bool(self.values.get(tenant_slug, False))

    def __getitem__(self, key):
        return bool(self.values.get(key, False))

    def __setitem__(self, key, value):
        self.values[key] = bool(value)

    def get(self, key, default=False):
        return bool(self.values.get(key, default))

    def clear(self):
        self.values.clear()


class MultitenantServiceMeta(type):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        cls._cache_loaded_dict = {}
        cls._dictionary_cache_inst = TenantPartitionedCache()
        cls._synonym_mappings_inst = TenantPartitionedCache()
        cls._incident_verbs_cache_inst = TenantPartitionedSet()

    @property
    def _cache_loaded(cls):
        return MultitenantStatusProxy(cls._cache_loaded_dict)

    @_cache_loaded.setter
    def _cache_loaded(cls, value):
        if value is False or value is None:
            tenant_slug = tenant_context.get()
            cls._cache_loaded_dict[tenant_slug] = False
        else:
            tenant_slug = tenant_context.get()
            cls._cache_loaded_dict[tenant_slug] = bool(value)

    @property
    def _dictionary_cache(cls):
        return cls._dictionary_cache_inst

    @_dictionary_cache.setter
    def _dictionary_cache(cls, value):
        if not isinstance(cls._dictionary_cache_inst, TenantPartitionedCache):
            cls._dictionary_cache_inst = TenantPartitionedCache()
            
        if isinstance(value, dict) and not isinstance(value, TenantPartitionedCache):
            tenant_slug = tenant_context.get()
            cls._dictionary_cache_inst.clear()
            if value:
                cls._dictionary_cache_inst[tenant_slug] = value
        else:
            cls._dictionary_cache_inst = value

    @property
    def _synonym_mappings(cls):
        return cls._synonym_mappings_inst

    @_synonym_mappings.setter
    def _synonym_mappings(cls, value):
        if not isinstance(cls._synonym_mappings_inst, TenantPartitionedCache):
            cls._synonym_mappings_inst = TenantPartitionedCache()
            
        if isinstance(value, dict) and not isinstance(value, TenantPartitionedCache):
            tenant_slug = tenant_context.get()
            cls._synonym_mappings_inst.clear()
            if value:
                cls._synonym_mappings_inst[tenant_slug] = value
        else:
            cls._synonym_mappings_inst = value

    @property
    def _incident_verbs_cache(cls):
        return cls._incident_verbs_cache_inst

    @_incident_verbs_cache.setter
    def _incident_verbs_cache(cls, value):
        if not isinstance(cls._incident_verbs_cache_inst, TenantPartitionedSet):
            cls._incident_verbs_cache_inst = TenantPartitionedSet()
            
        if isinstance(value, (dict, set)) and not isinstance(value, TenantPartitionedSet):
            tenant_slug = tenant_context.get()
            cls._incident_verbs_cache_inst.clear()
            if value:
                cls._incident_verbs_cache_inst[tenant_slug] = set(value)
        else:
            cls._incident_verbs_cache_inst = value


# Master DB configuration
MASTER_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://laporsar_admin:laporsar_admin@db:5432/laporsar_master")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Flag indicating whether PostgreSQL vector extension is active
HAS_VECTOR_EXTENSION = True

def set_vector_extension_available(status: bool):
    global HAS_VECTOR_EXTENSION
    HAS_VECTOR_EXTENSION = bool(status)

def is_vector_extension_available() -> bool:
    return HAS_VECTOR_EXTENSION

master_engine = create_async_engine(MASTER_DATABASE_URL, echo=False)
MasterSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=master_engine, class_=AsyncSession)
SessionLocal = MasterSessionLocal

# Tenant connection cache
tenant_engines = {}
tenant_sessionmakers = {}

def get_tenant_sessionmaker(db_url: str) -> sessionmaker:
    """Get or create connection engine and sessionmaker for a tenant."""
    # Ensure correct asyncpg prefix
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    
    if db_url not in tenant_sessionmakers:
        engine = create_async_engine(
            db_url,
            pool_pre_ping=True,
            echo=False,
            connect_args={"timeout": 3.0}
        )
        tenant_engines[db_url] = engine
        tenant_sessionmakers[db_url] = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=engine,
            class_=AsyncSession
        )
    return tenant_sessionmakers[db_url]

async def get_master_db():
    """Dependency to get the master database session (for SaaS administration)."""
    async with MasterSessionLocal() as session:
        yield session

async def get_tenant(request: Request, db_master: AsyncSession = Depends(get_master_db)):
    """Resolves the current tenant slug from headers, path, or subdomain and returns the Tenant object."""
    from app.models.master_models import Tenant

    tenant_slug = request.headers.get("X-Tenant-Slug") or request.headers.get("x-tenant-slug")
    
    if not tenant_slug:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                import jwt
                from app.core.config import settings as config_settings
                payload = jwt.decode(token, config_settings.SECRET_KEY, algorithms=[config_settings.ALGORITHM])
                if "tenant_slug" in payload:
                    tenant_slug = payload["tenant_slug"]
            except Exception:
                pass

    if not tenant_slug:
        tenant_slug = request.path_params.get("tenant_slug")
        
    if not tenant_slug:
        host = request.headers.get("host", "").lower()
        # Resolve subdomain. E.g., jakarta.localhost:3000 -> jakarta
        # E.g., surabaya.laporsar.id -> surabaya
        if not any(ignored in host for ignored in ("trycloudflare.com", "pages.dev", "vercel.app", "ngrok")):
            clean_host = host.split(":")[0].strip("[]")
            is_ip = False
            try:
                import ipaddress
                ipaddress.ip_address(clean_host)
                is_ip = True
            except (ValueError, Exception):
                is_ip = False

            if not is_ip:
                parts = host.split(".")
                if len(parts) > 1:
                    first_part = parts[0].split(":")[0]  # Remove port if present
                    if first_part not in ("www", "admin", "localhost", "127", "localhost:3000", "localhost:8000", "laporsar", "api") and not first_part.isdigit():
                        tenant_slug = first_part

    if not tenant_slug:
        path = request.url.path
        clean_path = path.rstrip("/")
        if (
            clean_path.endswith("/api/auth/login") or 
            clean_path.endswith("/auth/login") or 
            clean_path.endswith("/api/auth/me") or 
            clean_path.endswith("/auth/me") or
            "/api/public/" in path or
            "/api/admin/" in path
        ):
            return None
        # Fallback to default 'pusat' tenant
        tenant_slug = "pusat"

    # Clean the slug
    tenant_slug = tenant_slug.lower().strip()

    # Query master DB for active tenant info
    result = await db_master.execute(
        select(Tenant).where(Tenant.slug == tenant_slug, Tenant.is_active == True)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instansi dengan workspace '{tenant_slug}' tidak ditemukan atau sedang tidak aktif."
        )
    return tenant

async def get_db(tenant = Depends(get_tenant)):
    """Dynamic dependency that yields a database session for the resolved tenant."""
    if not tenant:
        yield None
        return
    session_maker = get_tenant_sessionmaker(tenant.db_url)
    async with session_maker() as session:
        session.info["tenant_slug"] = tenant.slug
        # Set context variable for multi-tenant transparent caching
        token = tenant_context.set(tenant.slug)
        try:
            yield session
        finally:
            tenant_context.reset(token)

async def get_redis():
    """Dependency to get Redis client."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
