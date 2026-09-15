import os
import sys
import ssl
from pathlib import Path

def setup_ssl():
    """
    Enables native Windows Certificate Store trust for Python HTTPS requests,
    resolving CERTIFICATE_VERIFY_FAILED errors behind corporate proxies and firewalls.
    """
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            import certifi
            backend_bundle = Path(__file__).resolve().parent.parent / "backend" / "app" / "resources" / "ca-bundle.pem"
            if backend_bundle.exists():
                bundle_str = str(backend_bundle)
                os.environ["SSL_CERT_FILE"] = bundle_str
                os.environ["REQUESTS_CA_BUNDLE"] = bundle_str
                os.environ["CURL_CA_BUNDLE"] = bundle_str
        except Exception:
            pass

setup_ssl()

