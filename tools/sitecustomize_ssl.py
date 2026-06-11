"""ocr-compare env patch (written by setup_env.ps1).

OpenSSL 3.6.x in this conda-forge build rejects DER-encoded `cadata`
(SSLError: [ASN1: NOT_ENOUGH_DATA]), which breaks the stdlib's
SSLContext._load_windows_store_certs -> ssl.create_default_context() on
Windows (and with it `import paddleocr`, aiohttp, model downloads, ...).

Workaround: load Windows-store certs one at a time, converted to PEM (which
parses fine), skipping any individually unparsable cert instead of poisoning
the whole bundle. Remove this file once the OpenSSL/cpython regression is
fixed upstream.
"""
import base64
import ssl
import warnings


def _load_windows_store_certs(self, storename, purpose):
    try:
        entries = list(ssl.enum_certificates(storename))
    except PermissionError:
        warnings.warn("unable to enumerate Windows certificate store")
        return
    for cert, encoding, trust in entries:
        if encoding != "x509_asn":
            continue
        if trust is not True and purpose.oid not in trust:
            continue
        b64 = base64.b64encode(cert).decode("ascii")
        pem = ("-----BEGIN CERTIFICATE-----\n"
               + "\n".join(b64[i:i + 64] for i in range(0, len(b64), 64))
               + "\n-----END CERTIFICATE-----\n")
        try:
            self.load_verify_locations(cadata=pem)
        except ssl.SSLError:
            continue  # genuinely malformed store entry: skip, don't poison


ssl.SSLContext._load_windows_store_certs = _load_windows_store_certs
