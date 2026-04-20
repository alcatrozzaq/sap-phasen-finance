import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pandas as pd
import json

# 1. KONEKSI FIREBASE (Versi Cloud / Aman)
if not firebase_admin._apps:
    key_dict = json.loads(st.secrets["firebase_key"])
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# 2. FUNGSI DATABASE
def get_data(collection):
    docs = db.collection(collection).stream()
    data = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        data.append(d)
    return pd.DataFrame(data)

# 3. CONFIG INTERFACE
st.set_page_config(page_title="Studio 3D SAP Professional", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'menu' not in st.session_state:
    st.session_state['menu'] = "Dashboard"

# LOGIN SYSTEM
if not st.session_state['logged_in']:
    st.title("🔐 Studio Finance System - V2 Pro")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if st.button("Login", use_container_width=True):
        user_ref = db.collection("users").document(email).get()
        if user_ref.exists:
            user_data = user_ref.to_dict()
            if user_data.get('password') == password:
                st.session_state['logged_in'] = True
                st.session_state['user'] = email
                st.session_state['role'] = user_data.get('role')
                st.rerun()
        st.error("Email atau Password salah!")
else:
    # 4. SIDEBAR & NAVIGASI
    st.sidebar.title(f"👤 {st.session_state['user']}")
    role = st.session_state['role']
    
    if st.sidebar.button("📊 Dashboard & Analisis", use_container_width=True): st.session_state['menu'] = "Dashboard"
    if st.sidebar.button("📁 Manajemen Proyek", use_container_width=True): st.session_state['menu'] = "Kelola Proyek"
    if st.sidebar.button("💰 Catat Keuangan", use_container_width=True): st.session_state['menu'] = "Catat Keuangan"
    if role == "Admin":
        if st.sidebar.button("👥 Kelola User", use_container_width=True): st.session_state['menu'] = "Kelola User"
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

    menu = st.session_state['menu']
    
    # --- MENU 1: DASHBOARD & ANALISIS ---
    if menu == "Dashboard":
        st.header("📊 Dashboard & Analisis Keuangan")
        
        df_trans = get_data("transactions")
        
        if not df_trans.empty:
            df_trans['tanggal_dt'] = pd.to_datetime(df_trans['tanggal'])
            df_trans['Bulan'] = df_trans['tanggal_dt'].dt.strftime('%B %Y')
            
            st.sidebar.subheader("📅 Filter Laporan")
            list_bulan = ["Semua Waktu"] + sorted(df_trans['Bulan'].unique().tolist(), reverse=True)
            pilih_bulan = st.sidebar.radio("Pilih Periode", list_bulan)

            if pilih_bulan != "Semua Waktu":
                df_filtered = df_trans[df_trans['Bulan'] == pilih_bulan]
            else:
                df_filtered = df_trans

            masuk = df_filtered[df_filtered['jenis'] == 'Masuk']['jumlah'].sum()
            keluar = df_filtered[df_filtered['jenis'] == 'Keluar']['jumlah'].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Pemasukan Periode Ini", f"Rp {masuk:,.0f}")
            col2.metric("Pengeluaran Periode Ini", f"Rp {keluar:,.0f}")
            col3.metric("Saldo Bersih", f"Rp {masuk-keluar:,.0f}")

            st.markdown("---")
            st.subheader("📈 Analisis Keuntungan per Proyek")
            df_p_profit = df_trans.groupby('proyek_terkait').apply(lambda x: pd.Series({
                'Total Masuk': x[x['jenis'] == 'Masuk']['jumlah'].sum(),
                'Total Keluar': x[x['jenis'] == 'Keluar']['jumlah'].sum(),
                'Profit/Margin': x[x['jenis'] == 'Masuk']['jumlah'].sum() - x[x['jenis'] == 'Keluar']['jumlah'].sum()
            })).reset_index()
            st.table(df_p_profit)

            st.markdown("---")
            st.subheader("📜 Riwayat Transaksi Lengkap")
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Unduh Laporan (CSV)", data=csv, file_name=f'laporan_{pilih_bulan}.csv', mime='text/csv')
            
            search = st.text_input("Cari transaksi...")
            if search:
                df_show = df_filtered[df_filtered.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
            else:
                df_show = df_filtered

            for i, row in df_show.sort_values(by='tanggal', ascending=False).iterrows():
                with st.expander(f"🕒 {row['tanggal']} | {row['jenis']} | Rp {row['jumlah']:,.0f} - {row['kategori_detail']}"):
                    st.write(f"**Admin:** {row['user']} | **Kategori:** {row['kategori_utama']} | **Proyek:** {row['proyek_terkait']}")
                    if st.button("🗑️ Hapus Transaksi Ini", key=f"del_tr_{row['id']}"):
                        db.collection("transactions").document(row['id']).delete()
                        st.success("Transaksi dihapus!")
                        st.rerun()
        else:
            st.info("Belum ada riwayat transaksi.")

    # --- MENU 2: MANAJEMEN PROYEK ---
    elif menu == "Kelola Proyek":
        st.header("📁 Manajemen Proyek")
        tab1, tab2 = st.tabs(["Daftar Proyek", "➕ Tambah Proyek Baru"])
        
        with tab1:
            df_p = get_data("projects")
            if not df_p.empty:
                for index, row in df_p.iterrows():
                    with st.expander(f"📂 {row['nama']} - {row.get('status', 'Berjalan')}"):
                        st.write(f"**Klien:** {row['klien']} | **Total Kontrak:** Rp {row['total']:,.0f}")
                        if st.button("🗑️ Hapus Proyek", key=f"del_p_{row['id']}"):
                            db.collection("projects").document(row['id']).delete()
                            st.rerun()
            else:
                st.info("Belum ada proyek.")

        with tab2:
            st.subheader("Input Proyek Baru")
            with st.form("new_project", clear_on_submit=True):
                n_nama = st.text_input("Nama Proyek")
                n_klien = st.text_input("Klien")
                n_total = st.number_input("Total Kontrak (Rp)", min_value=0)
                n_dl = st.date_input("Deadline")
                n_auto = st.checkbox("Catat langsung sebagai Pemasukan di Keuangan?", value=True)
                
                if st.form_submit_button("Simpan Proyek"):
                    if n_nama:
                        db.collection("projects").add({
                            "nama": n_nama, "klien": n_klien, "total": n_total, 
                            "deadline": str(n_dl), "status": "Berjalan"
                        })
                        if n_auto:
                            db.collection("transactions").add({
                                "user": st.session_state['user'],
                                "tanggal": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "jenis": "Masuk", "kategori_utama": "Proyek",
                                "proyek_terkait": n_nama, "jumlah": n_total,
                                "status_bayar": "Belum Lunas", "kategori_detail": f"Auto-Entry: Kontrak Proyek {n_nama}"
                            })
                        st.success(f"Proyek {n_nama} disimpan!")
                        st.rerun()

    # --- MENU 3: CATAT KEUANGAN ---
    elif menu == "Catat Keuangan":
        st.header("💰 Catat Transaksi Keuangan")
        df_proyek = get_data("projects")
        daftar_proyek = ["Bukan untuk Proyek"]
        if not df_proyek.empty:
            daftar_proyek += df_proyek['nama'].tolist()

        with st.form("form_trans", clear_on_submit=True):
            t_jenis = st.radio("Jenis Kas", ["Masuk", "Keluar"], horizontal=True)
            t_kat_utama = st.radio("Kategori", ["Proyek", "Operasional"], horizontal=True)
            t_proyek = "N/A"
            if t_kat_utama == "Proyek":
                st.markdown("**Pilih Proyek:**")
                t_proyek = st.radio("Daftar Proyek", daftar_proyek, label_visibility="collapsed")
            t_jumlah = st.number_input("Nominal (Rp)", min_value=0)
            t_status = st.radio("Status Bayar", ["Lunas", "DP", "Belum Lunas"], horizontal=True)
            t_detail = st.text_input("Keterangan Detail")
            
            if st.form_submit_button("Simpan Transaksi"):
                db.collection("transactions").add({
                    "user": st.session_state['user'],
                    "tanggal": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "jenis": t_jenis, "kategori_utama": t_kat_utama,
                    "proyek_terkait": t_proyek, "jumlah": t_jumlah,
                    "status_bayar": t_status, "kategori_detail": t_detail
                })
                st.success("Berhasil dicatat!")

    # --- MENU 4: KELOLA USER ---
    elif menu == "Kelola User":
        st.header("👥 Manajemen Tim")
        
        tab_u1, tab_u2 = st.tabs(["Daftar & Hapus Tim", "➕ Tambah Tim Baru"])
        
        with tab_u2:
            with st.form("add_user", clear_on_submit=True):
                u_mail = st.text_input("Email Baru")
                u_pass = st.text_input("Password", type="password")
                u_role = st.radio("Role", ["Staff", "Admin"], horizontal=True)
                if st.form_submit_button("Daftarkan"):
                    if u_mail and u_pass:
                        db.collection("users").document(u_mail).set({"password": u_pass, "role": u_role})
                        st.success(f"User {u_mail} ditambahkan!")
                        st.rerun()
                    else:
                        st.error("Isi semua data!")

        with tab_u1:
            df_u = get_data("users")
            if not df_u.empty:
                for idx, u_row in df_u.iterrows():
                    # Jangan biarkan admin menghapus dirinya sendiri agar tidak terkunci
                    is_self = u_row['id'] == st.session_state['user']
                    
                    with st.expander(f"👤 {u_row['id']} ({u_row['role']}) {' (Anda)' if is_self else ''}"):
                        st.write(f"**Email:** {u_row['id']}")
                        st.write(f"**Role:** {u_row['role']}")
                        
                        if not is_self:
                            if st.button(f"🗑️ Hapus Akses {u_row['id']}", key=f"del_u_{u_row['id']}"):
                                db.collection("users").document(u_row['id']).delete()
                                st.warning(f"User {u_row['id']} telah dihapus.")
                                st.rerun()
                        else:
                            st.info("Anda tidak bisa menghapus akun sendiri.")
            else:
                st.info("Tidak ada user terdaftar.")