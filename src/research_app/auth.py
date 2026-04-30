"""Simple username/password gate for the Streamlit app.

Credentials read from env vars APP_USERNAME and APP_PASSWORD (set on the
Cloud Run service). Update them via:
    gcloud run services update research-app --region=asia-southeast1 \\
        --project=vn-market-platform-staging \\
        --update-env-vars=APP_USERNAME=...,APP_PASSWORD=...
"""

import os

import streamlit as st


def require_login() -> None:
    """Block page render until correct username + password entered.

    Stops the script (st.stop) until the user is authenticated. Stores result
    in st.session_state.authenticated so subsequent reruns / pages skip the form.
    """
    if st.session_state.get("authenticated"):
        return

    expected_user = os.environ.get("APP_USERNAME", "")
    expected_pass = os.environ.get("APP_PASSWORD", "")
    if not expected_user or not expected_pass:
        st.error("Auth not configured. Set APP_USERNAME and APP_PASSWORD on the Cloud Run service.")
        st.stop()

    st.title("VN Market Research")
    st.markdown("Sign in to continue.")
    with st.form("login"):
        user = st.text_input("Username (email)")
        pwd = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        if user == expected_user and pwd == expected_pass:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()
