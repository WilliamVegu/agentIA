import os
import sys
import ssl
from pathlib import Path

def setup_ssl():
    """
    Enables native Windows Certificate Store trust for Python HTTPS requests,
    resolving CERTIFICATE_VERIFY_FAILED errors behind corporate proxies and firewalls.
    """
    # 1. Enable PEP 543 truststore if available
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass

    # 2. Extract and merge Windows certificates into a custom bundle for tools using OpenSSL/certifi directly
    if sys.platform == "win32":
        try:
            import certifi
            bundle_dir = Path(__file__).resolve().parent / "resources"
            bundle_dir.mkdir(parents=True, exist_ok=True)
            bundle_path = bundle_dir / "ca-bundle.pem"

            # Check if bundle already exists and is recent (> 50KB)
            if not bundle_path.exists() or bundle_path.stat().st_size < 50000:
                win_certs = []
                for store in ("ROOT", "CA", "MY"):
                    try:
                        for cert_bytes, encoding_type, _ in ssl.enum_certificates(store):
                            if encoding_type == "x509_asn":
                                pem = ssl.DER_cert_to_PEM_cert(cert_bytes)
                                win_certs.append(pem)
                    except Exception:
                        pass

                with open(certifi.where(), "r", encoding="utf-8") as f:
                    base_cacert = f.read()

                merged = base_cacert + "\n# Windows System Store Certificates\n" + "\n".join(win_certs)
                with open(bundle_path, "w", encoding="utf-8") as f:
                    f.write(merged)

            bundle_str = str(bundle_path)
            os.environ["SSL_CERT_FILE"] = bundle_str
            os.environ["REQUESTS_CA_BUNDLE"] = bundle_str
            os.environ["CURL_CA_BUNDLE"] = bundle_str
            os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = bundle_str
        except Exception:
            pass

# Automatically execute setup on import
setup_ssl()


def setup_uuid_compat():
    """
    Provides a pure-Python fallback for uuid_utils when the native C/Rust
    extension (_uuid_utils.pyd) is blocked by Windows Application Control (WDAC).
    """
    try:
        import uuid_utils  # noqa: F401
    except (ImportError, OSError):
        import time
        import types
        import uuid

        m = types.ModuleType("uuid_utils")
        m.UUID = uuid.UUID
        m.SafeUUID = uuid.SafeUUID
        m.getnode = uuid.getnode
        m.uuid1 = uuid.uuid1
        m.uuid3 = uuid.uuid3
        m.uuid4 = uuid.uuid4
        m.uuid5 = uuid.uuid5
        m.__version__ = "0.9.0"
        m.NIL = uuid.UUID("00000000-0000-0000-0000-000000000000")
        m.MAX = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        m.NAMESPACE_DNS = uuid.NAMESPACE_DNS
        m.NAMESPACE_OID = uuid.NAMESPACE_OID
        m.NAMESPACE_URL = uuid.NAMESPACE_URL
        m.NAMESPACE_X500 = uuid.NAMESPACE_X500
        m.RESERVED_FUTURE = uuid.RESERVED_FUTURE
        m.RESERVED_MICROSOFT = uuid.RESERVED_MICROSOFT
        m.RESERVED_NCS = uuid.RESERVED_NCS
        m.RFC_4122 = uuid.RFC_4122

        def uuid7(timestamp=None, nanos=None):
            if timestamp is None:
                ms = int(time.time() * 1000)
            else:
                ms = int(timestamp * 1000 + (nanos or 0) // 1_000_000)
            rand_bytes = bytearray(os.urandom(10))
            ts_bytes = ms.to_bytes(6, byteorder="big")
            b6 = (rand_bytes[0] & 0x0F) | 0x70
            b8 = (rand_bytes[2] & 0x3F) | 0x80
            data = ts_bytes + bytes([b6, rand_bytes[1], b8]) + rand_bytes[3:]
            return uuid.UUID(bytes=data)

        def _uuid4_int():
            return uuid.uuid4().int

        def _uuid7_int(timestamp=None, nanos=None):
            return uuid7(timestamp, nanos).int

        m.uuid6 = uuid.uuid1
        m.uuid7 = uuid7
        m.uuid8 = uuid.uuid4
        m._uuid4_int = _uuid4_int
        m._uuid7_int = _uuid7_int
        m.reseed_rng = lambda: None

        compat_m = types.ModuleType("uuid_utils.compat")
        compat_m.uuid7 = uuid7
        compat_m.uuid4 = uuid.uuid4
        compat_m.uuid1 = uuid.uuid1
        compat_m.uuid3 = uuid.uuid3
        compat_m.uuid5 = uuid.uuid5
        compat_m.uuid6 = uuid.uuid1
        compat_m.uuid8 = uuid.uuid4
        compat_m.UUID = uuid.UUID
        compat_m.SafeUUID = uuid.SafeUUID
        compat_m.getnode = uuid.getnode
        compat_m.NIL = m.NIL
        compat_m.MAX = m.MAX
        compat_m.__version__ = m.__version__

        sys.modules["uuid_utils"] = m
        sys.modules["uuid_utils.compat"] = compat_m


setup_uuid_compat()

