"""KSeF API client — adapted for Home Assistant (no file-based token cache)."""
from __future__ import annotations

import base64
import time
from typing import Any, Iterator, Optional

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_der_x509_certificate

from .models import DateRange, InvoiceMetadata, InvoiceQueryResponse

TEST_BASE_URL = "https://api-test.ksef.mf.gov.pl/v2"
PROD_BASE_URL = "https://api.ksef.mf.gov.pl/v2"


class KSEFError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class KSEFAuthError(KSEFError):
    """Raised when credentials are invalid — triggers HA re-auth flow."""


class KSEFRateLimitError(KSEFError):
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        msg = (
            f"Rate limit exceeded. Retry after {retry_after}s."
            if retry_after
            else "Rate limit exceeded."
        )
        super().__init__(msg, status_code=429)


class KSEFClient:
    def __init__(
        self,
        nip: str,
        ksef_token: str,
        base_url: str = PROD_BASE_URL,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self.nip = nip
        self.ksef_token = ksef_token
        self.base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._access_token = access_token
        self._refresh_token = refresh_token

    # ── token pair (for external persistence) ─────────────────────────

    @property
    def tokens(self) -> dict:
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
        }

    # ── HTTP ───────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        auth: Optional[str] = None,
        json_body: Any = None,
        accept_xml: bool = False,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers: dict = {}
        if auth:
            headers["Authorization"] = f"Bearer {auth}"
        if accept_xml:
            headers["Accept"] = "application/xml"
        resp = self._session.request(
            method, url, headers=headers, json=json_body, timeout=30
        )
        if not resp.ok:
            if resp.status_code == 429:
                try:
                    retry_after = int(resp.headers.get("Retry-After", ""))
                except (ValueError, TypeError):
                    retry_after = None
                raise KSEFRateLimitError(retry_after)
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise KSEFError(
                f"API {resp.status_code} {method} {path}: {body}",
                status_code=resp.status_code,
            )
        return resp

    # ── Public key ─────────────────────────────────────────────────────

    def _fetch_public_key(self):
        resp = self._request("GET", "/security/public-key-certificates")
        for entry in resp.json():
            if "KsefTokenEncryption" in entry.get("usage", []):
                der = base64.b64decode(entry["certificate"])
                cert = load_der_x509_certificate(der)
                return cert.public_key()
        raise KSEFError("No KsefTokenEncryption certificate found.")

    # ── Auth ───────────────────────────────────────────────────────────

    def _get_challenge(self) -> tuple[str, int]:
        resp = self._request(
            "POST",
            "/auth/challenge",
            json_body={"contextIdentifier": {"type": "nip", "value": self.nip}},
        )
        data = resp.json()
        return data["challenge"], int(data["timestampMs"])

    def _encrypt_token(self, timestamp_ms: int) -> str:
        public_key = self._fetch_public_key()
        plaintext = f"{self.ksef_token}|{timestamp_ms}".encode()
        ciphertext = public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(ciphertext).decode()

    def _initiate_token_auth(self, challenge: str, encrypted_token: str) -> tuple[str, str]:
        resp = self._request(
            "POST",
            "/auth/ksef-token",
            json_body={
                "challenge": challenge,
                "contextIdentifier": {"type": "nip", "value": self.nip},
                "encryptedToken": encrypted_token,
            },
        )
        data = resp.json()
        auth_token = data["authenticationToken"]
        if isinstance(auth_token, dict):
            auth_token = auth_token["token"]
        return auth_token, data["referenceNumber"]

    def _poll_auth_status(self, ref: str, auth_token: str, max_wait: int = 30) -> None:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            resp = self._request("GET", f"/auth/{ref}", auth=auth_token)
            data = resp.json()
            status = data.get("status") or {}
            code = (
                data.get("processingCode")
                or data.get("code")
                or status.get("code")
            )
            description = data.get("processingDescription") or status.get("description") or ""
            if code is not None:
                code_int = int(str(code))
                if code_int == 200:
                    return
                if code_int >= 300:
                    raise KSEFAuthError(f"{description} (code {code})")
            time.sleep(1)
        raise KSEFError("Auth polling timed out.")

    @staticmethod
    def _extract_token(value: Any) -> str:
        return value["token"] if isinstance(value, dict) else value

    def _redeem_tokens(self, auth_token: str) -> tuple[str, str]:
        resp = self._request("POST", "/auth/token/redeem", auth=auth_token)
        data = resp.json()
        return self._extract_token(data["accessToken"]), self._extract_token(data["refreshToken"])

    def authenticate(self) -> None:
        challenge, ts_ms = self._get_challenge()
        encrypted = self._encrypt_token(ts_ms)
        auth_token, ref = self._initiate_token_auth(challenge, encrypted)
        self._poll_auth_status(ref, auth_token)
        access, refresh = self._redeem_tokens(auth_token)
        self._access_token = access
        self._refresh_token = refresh

    def _refresh_access_token(self) -> None:
        if not self._refresh_token:
            raise KSEFAuthError("No refresh token — re-authentication required.")
        try:
            resp = self._request("POST", "/auth/token/refresh", auth=self._refresh_token)
            self._access_token = self._extract_token(resp.json()["accessToken"])
        except KSEFError as e:
            if e.status_code == 401:
                raise KSEFAuthError("Refresh token expired — re-authentication required.")
            raise

    def ensure_authenticated(self) -> None:
        if not self._access_token:
            self.authenticate()

    # ── Authenticated requests ─────────────────────────────────────────

    def get(self, path: str, accept_xml: bool = False) -> requests.Response:
        return self._authed_request("GET", path, accept_xml=accept_xml)

    def post(self, path: str, json_body: Any = None) -> requests.Response:
        return self._authed_request("POST", path, json_body=json_body)

    def _authed_request(self, method: str, path: str, **kwargs) -> requests.Response:
        self.ensure_authenticated()
        try:
            return self._request(method, path, auth=self._access_token, **kwargs)
        except KSEFRateLimitError:
            raise
        except KSEFError as e:
            if e.status_code != 401:
                raise
            # Access token expired — try refresh, then fall back to full re-auth
            if self._refresh_token:
                try:
                    self._refresh_access_token()
                    return self._request(method, path, auth=self._access_token, **kwargs)
                except KSEFAuthError:
                    pass  # refresh token also expired, fall back to full re-auth
            self.authenticate()
            return self._request(method, path, auth=self._access_token, **kwargs)

    # ── Invoice queries ────────────────────────────────────────────────

    def list_invoices(
        self,
        subject_type: str,
        date_range: DateRange,
        page_size: int = 100,
        fetch_all: bool = True,
    ) -> list[InvoiceMetadata]:
        return list(self._paginate(subject_type, date_range, page_size, fetch_all))

    def _paginate(
        self,
        subject_type: str,
        date_range: DateRange,
        page_size: int,
        fetch_all: bool,
    ) -> Iterator[InvoiceMetadata]:
        page_offset = 0
        current_range = date_range
        while True:
            path = (
                f"/invoices/query/metadata"
                f"?sortOrder=Asc&pageOffset={page_offset}&pageSize={page_size}"
            )
            resp = self.post(
                path,
                json_body={"subjectType": subject_type, "dateRange": current_range.to_dict()},
            )
            result = InvoiceQueryResponse.from_dict(resp.json())
            yield from result.invoices
            if not result.has_more or not fetch_all:
                break
            if result.is_truncated and result.invoices:
                current_range = DateRange(
                    from_date=result.invoices[-1].issue_date,
                    to_date=date_range.to_date,
                    date_type=date_range.date_type,
                )
                page_offset = 0
            else:
                page_offset += 1
