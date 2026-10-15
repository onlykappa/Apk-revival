"""Verified HTTPS works in both source and frozen distributions."""
import ssl
import urllib.error
import urllib.request
import certifi
from ..util import RevivalError


def tls_context():
    context = ssl.create_default_context()
    # Retain system roots (including local enterprise roots) and add portable roots.
    context.load_verify_locations(cafile=certifi.where())
    return context


def open_url(request, timeout=45):
    try:
        return urllib.request.urlopen(request, timeout=timeout, context=tls_context())
    except urllib.error.URLError as error:
        if isinstance(error.reason, ssl.SSLCertVerificationError):
            raise RevivalError('HTTPS certificate verification failed. Check the Deck date/time and network sign-in. APK Revival keeps certificate verification enabled.') from error
        raise

