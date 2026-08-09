import os
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from fastmcp.server.auth.providers.azure import AzureProvider
from key_value.aio.stores.redis import RedisStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from cryptography.fernet import Fernet


# Production setup with encrypted persistent token storage
auth_provider = AzureProvider(
    client_id=os.environ["AZURE_CLIENT_ID"],
    client_secret=os.environ["AZURE_CLIENT_SECRET"],
    tenant_id=os.environ["AZURE_TENANT_ID"],
    base_url=os.environ["ZAPI_BASE_URL"],
    required_scopes=["access_as_user"],

    # Production token management
    jwt_signing_key=os.environ["JWT_SIGNING_KEY"],
    client_storage=FernetEncryptionWrapper(
        key_value=RedisStore(
            host=os.environ["AZURE_REDIS_HOST"],
            port=10000,
            password=os.environ["AZURE_REDIS_KEY"],
        ),
        fernet=Fernet(os.environ["STORAGE_ENCRYPTION_KEY"])
    )
)

mcp = FastMCP(
    name="za-pharma-intelligence",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    ),
    auth=auth_provider
)

...