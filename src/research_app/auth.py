"""Username/password gate with HMAC-signed cookie for persistent sessions.

Reads cookies via Streamlit's native `st.context.cookies` (no iframe component,
no CachedWidgetWarning). Writes via a tiny inline `<script>` so the cookie
lands on the parent document at path `/`.

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

import streamlit as st
import streamlit.components.v1 as components

from research_app.components.theme import apply_theme

_COOKIE_NAME = "vnmarket_auth"
_COOKIE_DAYS = 30


def _expected_token(user: str, password: str, secret: str) -> str:
    """HMAC-SHA256 of username, keyed by secret. Stable per (user, password)."""
    key = (secret or password).encode("utf-8")
    msg = user.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _write_cookie_and_reload(name: str, value: str, days: int) -> None:
    """Write a cookie via inline JS, then reload the parent page.

    The cookie is set on `window.parent.document` so it lives at path=/ on the
    app's origin (not on the components-iframe sub-document). We reload the
    parent immediately afterward so the next render sees the new cookie via
    `st.context.cookies`. NOT calling st.rerun() is intentional — that would
    tear down the iframe before its script executes.
    """
    components.html(
        f"""<script>
            (function() {{
                const exp = new Date();
                exp.setTime(exp.getTime() + {days} * 86400 * 1000);
                const doc = (window.parent && window.parent.document) || document;
                doc.cookie = "{name}={value}; expires=" + exp.toUTCString()
                    + "; path=/; SameSite=Lax; Secure";
                if (window.parent) window.parent.location.reload();
                else location.reload();
            }})();
        </script>""",
        height=0,
    )


def require_login() -> None:
    """Block page render until correct username + password entered.

    On success, write a 30-day signed cookie so the browser stays logged in
    across tab close / restart. Subsequent loads read the cookie via
    `st.context.cookies` and skip the form silently.
    """
    if st.session_state.get("authenticated"):
        return

    expected_user = os.environ.get("APP_USERNAME", "")
    expected_pass = os.environ.get("APP_PASSWORD", "")
    if not expected_user or not expected_pass:
        st.error("Auth not configured. Set APP_USERNAME and APP_PASSWORD on the Cloud Run service.")
        st.stop()
    secret = os.environ.get("APP_COOKIE_SECRET", expected_pass)
    expected = _expected_token(expected_user, expected_pass, secret)

    saved = st.context.cookies.get(_COOKIE_NAME)
    if saved and hmac.compare_digest(saved, expected):
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
            # JS sets the cookie + reloads the parent. After reload, the
            # cookie is present and st.context.cookies restores auth on the
            # very first render — no second login prompt.
            _write_cookie_and_reload(_COOKIE_NAME, expected, _COOKIE_DAYS)
            st.info("Signing you in...")
            st.stop()
        else:
            st.error("Invalid username or password.")
    st.stop()
