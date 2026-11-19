import streamlit as st
from supabase import create_client
import pandas as pd

st.set_page_config(page_title="Laporan EKKLESIA MOBIL", page_icon="📊", layout="wide")

st.markdown("""
<style>
:root{--forest:#103426;--cream:#f7f4ee;--paper:#fffdfa;--ink:#17231e;--line:#e4ded2}
.stApp{background:var(--cream);color:var(--ink)}
.block-container{max-width:1500px;padding-top:1.5rem;padding-bottom:2rem}
h1,h2,h3{color:var(--ink)}
div[data-testid="stMetric"]{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:1rem}
.stButton>button,.stFormSubmitButton>button,.stDownloadButton>button{background:var(--forest);color:white;border:0;border-radius:9px;min-height:2.6rem}
section[data-testid="stSidebar"]{background:#fffdfa;border-right:1px solid var(--line)}
</style>
""", unsafe_allow_html=True)

try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("Secrets aplikasi belum diisi. Tambahkan SUPABASE_URL dan SUPABASE_KEY pada pengaturan Secrets Streamlit.")
    st.stop()

@st.cache_resource
def get_client():
    return create_client(URL, KEY)

sb = get_client()

def rp(value):
    try:
        return "Rp " + f"{int(value or 0):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp 0"

if "report_user" not in st.session_state:
    st.session_state.report_user = None
if "report_profile" not in st.session_state:
    st.session_state.report_profile = None

if st.session_state.report_user is None:
    st.title("🚗 EKKLESIA MOBIL")
    st.subheader("Login Laporan Showroom")
    with st.form("report_login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Masuk", type="primary", use_container_width=True)
    if submit:
        try:
            auth = sb.auth.sign_in_with_password({"email": email.strip(), "password": password})
            u = auth.user
            if not u:
                st.error("Login gagal. Periksa email dan password.")
            else:
                result = sb.table("profiles").select("id,email,role").eq("id", u.id).maybe_single().execute()
                if not result.data:
                    sb.auth.sign_out()
                    st.error("Akun belum terdaftar di tabel public.profiles.")
                else:
                    st.session_state.report_user = u
                    st.session_state.report_profile = result.data
                    st.rerun()
        except Exception as e:
            st.error(f"Login gagal: {e}")
    st.info("Gunakan akun AutoLedger yang sama. Hak akses data mengikuti kebijakan RLS Supabase.")
    st.stop()

user = st.session_state.report_user
profile = st.session_state.report_profile or {}

with st.sidebar:
    st.markdown("## 🚗 EKKLESIA MOBIL")
    st.caption("PUSAT LAPORAN SHOWROOM")
    st.divider()
    st.markdown("### MENU UTAMA")
    menu = st.radio(
        "Navigasi",
        ["Dashboard", "Laporan Penjualan", "Laporan Laba/Rugi"],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown("### AKUN")
    st.write(profile.get("email") or getattr(user, "email", ""))
    st.caption(f"Role: {profile.get('role', 'staff')}")
    if st.button("Keluar", use_container_width=True):
        try:
            sb.auth.sign_out()
        finally:
            st.session_state.report_user = None
            st.session_state.report_profile = None
            st.rerun()

try:
    rows = sb.table("vehicles").select("id,data,created_at").order("created_at", desc=True).execute().data or []
