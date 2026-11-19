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
    response = sb.table("vehicles").select("id,data,created_at").order("created_at", desc=True).execute()
    rows = response.data or []
except Exception as e:
    st.error(f"Tidak dapat membaca data kendaraan: {e}")
    st.warning("Pastikan policy RLS tabel vehicles mengizinkan pengguna authenticated membaca data.")
    st.stop()

cars = []
for row in rows:
    data = dict(row.get("data") or {})
    data["_id"] = row.get("id")
    expense_keys = ["biaya_perbaikan", "biaya_servis", "biaya_pajak_admin", "biaya_lain"]
    data["total_pengeluaran"] = sum(int(data.get(k, 0) or 0) for k in expense_keys)
    data["total_modal"] = int(data.get("harga_beli", data.get("harga", 0)) or 0) + data["total_pengeluaran"]
    cars.append(data)

sold = [x for x in cars if x.get("status") == "Terjual"]
available = [x for x in cars if x.get("status", "Tersedia") == "Tersedia"]
omzet = sum(int(x.get("harga_jual", 0) or 0) for x in sold)
profit = sum(int(x.get("harga_jual", 0) or 0) - int(x["total_modal"]) for x in sold)
total_modal = sum(int(x["total_modal"]) for x in cars)

# Dataset transaksi penjualan, angka tetap numerik untuk perhitungan dan ekspor.
if sold:
    df_raw = pd.DataFrame([{
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
else:
    df_raw = pd.DataFrame(columns=["Mobil", "No. Polisi", "Tanggal Jual", "Harga Beli", "Pengeluaran", "Total Modal", "Harga Jual", "Laba/Rugi", "Pembeli"])

st.title("📊 EKKLESIA MOBIL")
if menu == "Dashboard":
    st.subheader("Dashboard Ringkasan Showroom")
    st.caption("Pantauan cepat stok, penjualan, omzet, dan hasil usaha.")
    a, b, c, d = st.columns(4)
    a.metric("Stok tersedia", len(available))
    b.metric("Unit terjual", len(sold))
    c.metric("Omzet penjualan", rp(omzet))
    d.metric("Laba / Rugi", rp(profit))
    st.divider()
    x, y = st.columns(2)
    with x:
        st.markdown("### Posisi kendaraan")
        st.write(f"**Mobil tersedia:** {len(available)} unit")
        st.write(f"**Mobil terjual:** {len(sold)} unit")
        st.write(f"**Total kendaraan tercatat:** {len(cars)} unit")
    with y:
        st.markdown("### Ringkasan keuangan")
        st.write(f"**Total modal seluruh mobil:** {rp(total_modal)}")
        st.write(f"**Omzet penjualan:** {rp(omzet)}")
        st.write(f"**Laba / rugi penjualan:** {rp(profit)}")
    st.caption("Data diambil langsung dari database AutoLedger. Muat ulang halaman untuk mengambil perubahan terbaru.")

elif menu == "Laporan Penjualan":
    st.subheader("Laporan Penjualan Mobil")
    st.caption("Rincian unit terjual berdasarkan rentang tanggal.")
    if df_raw.empty:
        st.info("Belum ada mobil berstatus Terjual.")
    else:
        dates = pd.to_datetime(df_raw["Tanggal Jual"], errors="coerce")
        valid = dates.dropna()
        if not valid.empty:
            c1, c2 = st.columns(2)
            start = c1.date_input("Dari tanggal", value=valid.min().date(), min_value=valid.min().date(), max_value=valid.max().date(), key="sales_start")
            end = c2.date_input("Sampai tanggal", value=valid.max().date(), min_value=valid.min().date(), max_value=valid.max().date(), key="sales_end")
            if start > end:
                st.error("Tanggal awal tidak boleh melewati tanggal akhir.")
                st.stop()
            filtered_raw = df_raw.loc[(dates.dt.date >= start) & (dates.dt.date <= end)].copy()
        else:
            filtered_raw = df_raw.copy()
            st.caption("Tanggal penjualan belum tersedia/valid pada sebagian data.")
        a, b = st.columns(2)
        a.metric("Jumlah transaksi pada filter", len(filtered_raw))
        b.metric("Omzet pada filter", rp(filtered_raw["Harga Jual"].sum()))
        display = filtered_raw.copy()
        for col in ["Harga Beli", "Pengeluaran", "Total Modal", "Harga Jual", "Laba/Rugi"]:
            display[col] = display[col].apply(rp)
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Unduh laporan penjualan CSV", data=filtered_raw.to_csv(index=False).encode("utf-8-sig"), file_name="laporan_penjualan_ekklesia.csv", mime="text/csv", use_container_width=True)

else:
    st.subheader("Laporan Laba / Rugi")
    st.caption("Perbandingan harga jual dengan total modal setiap kendaraan yang sudah terjual.")
    a, b, c = st.columns(3)
    a.metric("Total omzet", rp(omzet))
    b.metric("Total modal unit terjual", rp(df_raw["Total Modal"].sum() if not df_raw.empty else 0))
    c.metric("Laba / Rugi bersih", rp(profit))
    if not df_raw.empty:
        profit_display = df_raw[["Mobil", "No. Polisi", "Total Modal", "Harga Jual", "Laba/Rugi"]].copy()
        for col in ["Total Modal", "Harga Jual", "Laba/Rugi"]:
            profit_display[col] = profit_display[col].apply(rp)
        st.dataframe(profit_display, use_container_width=True, hide_index=True)
        winners = int((df_raw["Laba/Rugi"] > 0).sum())
        losses = int((df_raw["Laba/Rugi"] < 0).sum())
        breakeven = int((df_raw["Laba/Rugi"] == 0).sum())
        p, q, r = st.columns(3)
        p.metric("Transaksi untung", winners)
        q.metric("Transaksi rugi", losses)
        r.metric("Impas", breakeven)
        st.download_button("⬇️ Unduh laporan laba/rugi CSV", data=df_raw.to_csv(index=False).encode("utf-8-sig"), file_name="laporan_laba_rugi_ekklesia.csv", mime="text/csv", use_container_width=True)
    else:
        st.info("Belum ada data penjualan untuk dihitung laba/ruginya.")

st.divider()
st.caption("EKKLESIA MOBIL · Laporan terpisah yang terhubung ke database AutoLedger.")
