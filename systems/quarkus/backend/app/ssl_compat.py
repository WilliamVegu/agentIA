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

