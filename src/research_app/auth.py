"""Username/password gate with HMAC-signed cookie for persistent sessions.

Credentials read from env vars APP_USERNAME and APP_PASSWORD on the Cloud Run
service. Cookie signed with APP_COOKIE_SECRET (defaults to APP_PASSWORD) so
changing the password invalidates all existing cookies.

Update credentials via:
    gcloud run services update research-app --region=asia-southeast1 \\
        --project=vn-market-platform-staging \\
        --update-env-vars=APP_USERNAME=...,APP_PASSWORD=...
"""

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta

import extra_streamlit_components as stx
import streamlit as st

from research_app.components.theme import apply_theme

_COOKIE_NAME = "vnmarket_auth"
_COOKIE_DAYS = 30


def _expected_token(user: str, password: str, secret: str) -> str:
    """HMAC-SHA256 of username, keyed by secret. Stable per (user, password)."""
    key = (secret or password).encode("utf-8")
    msg = user.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


@st.cache_resource
def _cookie_manager() -> stx.CookieManager:
    # cache_resource so the manager survives Streamlit reruns; multiple
    # instances on one page break cookie reads.
    return stx.CookieManager(key="auth_cookie_manager")


def require_login() -> None:
    """Block page render until correct username + password entered.

    On success, set a 30-day signed cookie so the browser stays logged in
    across tab close / restart. Subsequent loads check the cookie and skip the
    form silently.
    """
    if st.session_state.get("authenticated"):
        return

    expected_user = os.environ.get("APP_USERNAME", "")
    expected_pass = os.environ.get("APP_PASSWORD", "")
    if not expected_user or not expected_pass:
        st.error("Auth not configured. Set APP_USERNAME and APP_PASSWORD on the Cloud Run service.")
        st.stop()
    secret = os.environ.get("APP_COOKIE_SECRET", expected_pass)

    cookies = _cookie_manager()
    expected = _expected_token(expected_user, expected_pass, secret)
    saved_token = cookies.get(_COOKIE_NAME)
    if saved_token and hmac.compare_digest(saved_token, expected):
        st.session_state["authenticated"] = True
        return

    apply_theme()
    st.markdown(
        """<div class="vm-login-wrap">
            <div style="font-size:2.4rem; line-height:1; margin-bottom:.4rem;">📈</div>
            <h2>VN Market Research</h2>
            <p>Vietnam equities — daily, ticks, L2, factors.</p>
        </div>""",
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 2, 1])
    with mid, st.form("login", clear_on_submit=False):
        user = st.text_input("Email", placeholder="you@example.com")
        pwd = st.text_input("Password", type="password", placeholder="••••••••")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        if user == expected_user and pwd == expected_pass:
            st.session_state["authenticated"] = True
            cookies.set(
                _COOKIE_NAME,
                expected,
                expires_at=datetime.now(UTC) + timedelta(days=_COOKIE_DAYS),
                key="set_auth_cookie",
            )
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()
