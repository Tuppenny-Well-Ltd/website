"""Check that the live site is up and still correctly configured.

Run with `python3 scripts/check_live.py`. Standard library only. Exits non-zero if
anything is wrong, which makes the scheduled GitHub workflow fail and send an email.

Checks: the page loads over HTTPS, plain HTTP and www redirect to the right place,
the link preview image is served, and the HTTPS certificate is not about to expire.
"""

import argparse
import http.client
import socket
import ssl
import sys
import time
from collections.abc import Callable

MIN_CERT_DAYS = 10  # GitHub renews certificates itself, well before they expire
ATTEMPTS = 3  # retry a few times so one network blip does not raise a false alarm


def request(host: str, path: str, *, tls: bool) -> tuple[int, dict[str, str], bytes]:
    """Fetch one URL without following redirects, retrying on network errors."""
    last: Exception | None = None
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(10)
        try:
            conn_class = http.client.HTTPSConnection if tls else http.client.HTTPConnection
            conn = conn_class(host, timeout=15)
            conn.request("GET", path, headers={"User-Agent": "site-check"})
            response = conn.getresponse()
            headers = {k.lower(): v for k, v in response.getheaders()}
            body = response.read(300_000)
            conn.close()
        except (OSError, http.client.HTTPException) as error:
            last = error
        else:
            return response.status, headers, body
    raise ConnectionError(f"{host}{path}: {last}")


def cert_days_left(host: str) -> float:
    context = ssl.create_default_context()  # also verifies the certificate matches the host
    with socket.create_connection((host, 443), timeout=15) as sock:
        with context.wrap_socket(sock, server_hostname=host) as tls:
            expires = ssl.cert_time_to_seconds(tls.getpeercert()["notAfter"])
    return (expires - time.time()) / 86400


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--domain", default="tuppennywell.com")
    parser.add_argument("--image", default="/og-image.png")
    args = parser.parse_args()
    domain = args.domain
    problems: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{': ' + detail if detail and not ok else ''}")
        if not ok:
            problems.append(name)

    def attempt(name: str, test: Callable[[], None]) -> None:
        try:
            test()
        except (OSError, ssl.SSLError, http.client.HTTPException, KeyError) as e:
            check(name, False, str(e))

    def page() -> None:
        status, headers, body = request(domain, "/", tls=True)
        check("https page loads", status == 200 and b"<title>" in body, f"status {status}")
        check("page is html", headers.get("content-type", "").startswith("text/html"))

    def http_redirect() -> None:
        status, headers, _ = request(domain, "/", tls=False)
        want = f"https://{domain}/"
        check("http redirects to https", status in (301, 308) and headers.get("location") == want,
              f"got {status} {headers.get('location')}")

    def www_redirect() -> None:
        status, headers, _ = request(f"www.{domain}", "/", tls=True)
        want = f"https://{domain}/"
        check("www redirects to the main address", status in (301, 308) and headers.get("location") == want,
              f"got {status} {headers.get('location')}")

    def image() -> None:
        status, headers, _ = request(domain, args.image, tls=True)
        check("link preview image is served", status == 200 and headers.get("content-type") == "image/png",
              f"status {status} {headers.get('content-type')}")

    def certificate() -> None:
        days = cert_days_left(domain)
        check(f"certificate valid for {days:.0f} more days", days >= MIN_CERT_DAYS, "renewal looks stuck")

    for name, test in (("https page", page), ("http redirect", http_redirect),
                       ("www redirect", www_redirect), ("preview image", image),
                       ("certificate", certificate)):
        attempt(name, test)

    print("\nAll checks passed." if not problems else f"\n{len(problems)} problem(s): {', '.join(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
