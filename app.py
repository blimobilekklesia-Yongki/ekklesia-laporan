import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date
import re

st.set_page_config(page_title="Laporan EKKLESIA MOBIL", page_icon="📊", layout="wide")

st.markdown("""
<style>
:root{--forest:#103426;--cream:#f7f4ee;--paper:#fffdfa;--ink:#17231e;--line:#e4ded2}
.stApp{background:var(--cream);color:var(--ink)}
.block-container{max-width:1400px;padding-top:2rem}
h1,h2,h3{color:var(--ink)}
div[data-testid="stMetric"]{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:1rem}
.stButton>button,.stFormSubmitButton>button,.stDownloadButton>button{background:var(--forest);color:white;border-radius:9px}
</style>
""", unsafe_allow_html=True)

st.title("📊 EKKLESIA MOBIL")
st.subheader("Laporan Penjualan dan Laba/Rugi")
st.caption("Halaman laporan online terpisah · Terhubung ke database AutoLedger")

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

def rp(v):
    try:
        return "Rp " + f"{int(v or 0):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp 0"

if "report_user" not in st.session_state:
    st.session_state.report_user = None
if "report_profile" not in st.session_state:
    st.session_state.report_profile = None

if st.session_state.report_user is None:
    st.markdown("### Login admin / karyawan")
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
profile = st.session_state.report_profile
with st.sidebar:
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
except Exception as e:
    st.error(f"Tidak dapat membaca data kendaraan: {e}")
    st.warning("Pastikan policy RLS tabel vehicles mengizinkan pengguna authenticated membaca data.")
    st.stop()

cars = []
for row in rows:
    d = dict(row.get("data") or {})
    d["_id"] = row.get("id")
    d.setdefault("biaya_perbaikan", 0)
    d.setdefault("biaya_servis", 0)
    d.setdefault("biaya_pajak_admin", 0)
    d.setdefault("biaya_lain", 0)
    d["total_pengeluaran"] = sum(int(d.get(k, 0) or 0) for k in
        ["biaya_perbaikan", "biaya_servis", "biaya_pajak_admin", "biaya_lain"])
    d["total_modal"] = int(d.get("harga_beli", d.get("harga", 0)) or 0) + d["total_pengeluaran"]
    cars.append(d)

sold = [x for x in cars if x.get("status") == "Terjual"]
available = [x for x in cars if x.get("status", "Tersedia") == "Tersedia"]

st.markdown("### Ringkasan showroom")
a,b,c,d = st.columns(4)
a.metric("Stok tersedia", len(available))
b.metric("Unit terjual", len(sold))
c.metric("Omzet penjualan", rp(sum(int(x.get("harga_jual", 0) or 0) for x in sold)))
d.metric("Laba/rugi", rp(sum(int(x.get("harga_jual", 0) or 0) - x["total_modal"] for x in sold)))

st.divider()
st.markdown("### Rincian laporan penjualan")
if sold:
    df = pd.DataFrame([{
        "Mobil": x.get("nama", "-"),
        "No. Polisi": x.get("plat", "-"),
        "Tanggal Jual": x.get("tanggal_jual", ""),
        "Harga Beli": int(x.get("harga_beli", x.get("harga", 0)) or 0),
        "Pengeluaran": int(x["total_pengeluaran"]),
        "Total Modal": int(x["total_modal"]),
        "Harga Jual": int(x.get("harga_jual", 0) or 0),
        "Laba/Rugi": int(x.get("harga_jual", 0) or 0) - int(x["total_modal"]),
        "Pembeli": x.get("nama_pembeli", "-"),
    } for x in sold])

    date_values = pd.to_datetime(df["Tanggal Jual"], errors="coerce")
    valid_dates = date_values.dropna()
    if not valid_dates.empty:
        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()
        f1, f2 = st.columns(2)
        start = f1.date_input("Dari tanggal", value=min_date, min_value=min_date, max_value=max_date)
        end = f2.date_input("Sampai tanggal", value=max_date, min_value=min_date, max_value=max_date)
        if start > end:
            st.error("Tanggal awal tidak boleh melewati tanggal akhir.")
            st.stop()
        mask = (date_values.dt.date >= start) & (date_values.dt.date <= end)
        filtered = df.loc[mask].copy()
    else:
        filtered = df.copy()
        st.caption("Tanggal penjualan belum tersedia/valid pada sebagian data.")

    for col in ["Harga Beli", "Pengeluaran", "Total Modal", "Harga Jual", "Laba/Rugi"]:
        filtered[col] = filtered[col].apply(rp)
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Unduh laporan CSV",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name="laporan_autoledger.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.info("Belum ada mobil berstatus Terjual.")

st.caption("Data laporan diambil langsung dari tabel vehicles AutoLedger di Supabase. Perubahan transaksi di AutoLedger akan terlihat saat halaman ini dimuat ulang.")
