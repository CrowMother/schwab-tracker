# app.py  (streamlit run app.py)
import os, json, secrets, urllib.parse, requests, pkce, streamlit as st

APP_KEY     = os.environ.get("SCHWAB_APP_KEY",    "1OfbUtLXOc8AD3yT4445g69TaEBluw3Z")
APP_SECRET  = os.environ.get("SCHWAB_APP_SECRET", "wGotKFxzabxR4ZWX")
REDIRECT    = os.environ.get("PUBLIC_REDIRECT",   "https://172.0.0.1")

AUTH_URL  = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"

st.set_page_config(page_title="Schwab Link", page_icon="🔗")

# --- 1) detect callback ---
code  = st.query_params.get("code")
state = st.query_params.get("state")

# init session storage
if "oauth_state" not in st.session_state:
    st.session_state.oauth_state = None
if "code_verifier" not in st.session_state:
    st.session_state.code_verifier = None

st.title("🔗 Link Schwab")

if code and state:
    # --- 2) validate state & exchange code for tokens ---
    if state != st.session_state.oauth_state or not st.session_state.code_verifier:
        st.error("State mismatch or session expired. Start again.")
    else:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": st.session_state.code_verifier,
            "client_id": APP_KEY,  # many OAuth servers want this in the body too
        }
        # Basic auth with app key/secret is required by Schwab's token endpoint
        resp = requests.post(TOKEN_URL, data=data, auth=(APP_KEY, APP_SECRET), timeout=30)
        if resp.ok:
            tokens = resp.json()
            with open("tokens.json", "w") as f:
                json.dump(tokens, f, indent=2)
            st.success("Linked! tokens.json written.")
        else:
            st.error(f"Token exchange failed: {resp.status_code} {resp.text}")

    # clear query params so refreshes don’t redo the exchange
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()
else:
    # --- 3) start flow: create PKCE + state, build URL, send user to Schwab ---
    if st.button("Link Schwab"):
        code_verifier, code_challenge = pkce.generate_pkce_pair()
        st.session_state.code_verifier = code_verifier
        st.session_state.oauth_state = secrets.token_urlsafe(16)

        params = {
            "response_type": "code",
            "client_id": APP_KEY,
            "redirect_uri": REDIRECT,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": st.session_state.oauth_state,
        }
        url = AUTH_URL + "?" + urllib.parse.urlencode(params, safe=":/")
        st.link_button("Continue to Schwab", url)

    st.info(f"Callback URL registered with Schwab must be exactly:\n{REDIRECT}")
