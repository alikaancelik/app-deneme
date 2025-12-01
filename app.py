import streamlit as st
import pandas as pd
from github import Github
import io
from datetime import datetime
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="ÖZÇELİK ENDÜSTRİ", layout="wide", page_icon="🏭")

# --- GITHUB BAĞLANTISI ---
def get_github_repo():
    token = st.secrets["github"]["token"]
    repo_name = st.secrets["github"]["repo_name"]
    g = Github(token)
    return g.get_repo(repo_name)

def read_data(filename):
    """GitHub'dan veriyi okur, yoksa boş oluşturur"""
    try:
        repo = get_github_repo()
        contents = repo.get_contents(filename)
        return pd.read_csv(io.StringIO(contents.decoded_content.decode()))
    except:
        # Dosya yoksa boş şablonlar
        if filename == "musteriler.csv": 
            return pd.DataFrame(columns=["Firma Adı", "Yetkili", "Telefon", "Adres"])
        elif filename == "siparisler.csv": 
            return pd.DataFrame(columns=["Tarih", "Müşteri", "İş Adı", "Tutar", "Detay"])
        elif filename == "ayarlar.csv":
            return pd.DataFrame([{"Ayar": "dolar_kuru", "Deger": 34.50}, {"Ayar": "kar_orani", "Deger": 25.0}, {"Ayar": "kdv_durum", "Deger": "Evet"}, {"Ayar": "lazer_dk", "Deger": 25.0}])
        elif filename == "malzemeler.csv":
            return pd.DataFrame([{"Malzeme": "Siyah Sac", "Fiyat": 0.85, "Birim": "USD", "Yogunluk": 7.85}])
        return pd.DataFrame()

def save_data(filename, df):
    """Veriyi GitHub'a kaydeder"""
    repo = get_github_repo()
    content = df.to_csv(index=False)
    try:
        contents = repo.get_contents(filename)
        repo.update_file(contents.path, "Veri Guncelleme", content, contents.sha)
    except:
        repo.create_file(filename, "Yeni Dosya", content)

# --- AYARLARI YÜKLE ---
if 'ayarlar_cache' not in st.session_state:
    st.session_state.ayarlar_cache = read_data("ayarlar.csv")
    st.session_state.malzeme_cache = read_data("malzemeler.csv")

# Değişkenleri al
df_ayar = st.session_state.ayarlar_cache
try:
    DOLAR = float(df_ayar.loc[df_ayar['Ayar']=='dolar_kuru', 'Deger'].values[0])
    KAR = float(df_ayar.loc[df_ayar['Ayar']=='kar_orani', 'Deger'].values[0])
    KDV_DURUM = str(df_ayar.loc[df_ayar['Ayar']=='kdv_durum', 'Deger'].values[0])
    LAZER_DK = float(df_ayar.loc[df_ayar['Ayar']=='lazer_dk', 'Deger'].values[0])
except:
    DOLAR, KAR, KDV_DURUM, LAZER_DK = 34.50, 25.0, "Evet", 25.0

# Session State
if 'sepet' not in st.session_state: st.session_state.sepet = []

# --- ARAYÜZ ---
with st.sidebar:
    st.title("🏭 ÖZÇELİK ENDÜSTRİ")
    menu = st.radio("Menü", ["Hesaplama & Teklif", "Müşteri Yönetimi", "Ayarlar"])
    st.divider()
    st.info(f"💲 Dolar: **{DOLAR}** | Kâr: **%{KAR}**")

# ==========================================
# 1. HESAPLAMA VE TEKLİF SAYFASI
# ==========================================
if menu == "Hesaplama & Teklif":
    st.header("📝 Teklif Masası")
    
    # Müşteri Verilerini Çek
    df_mus = read_data("musteriler.csv")
    kayitli_isimler = df_mus["Firma Adı"].tolist() if not df_mus.empty else []
    
    # Seçim Kutusu
    mod_secimi = st.radio("İşlem Türü:", ["⚡ Hızlı İşlem (Yeni/Kayıtsız)", "📂 Kayıtlı Müşteri"], horizontal=True)
    
    aktif_musteri_adi = ""
    
    if mod_secimi == "📂 Kayıtlı Müşteri":
        if not kayitli_isimler:
            st.warning("Hiç kayıtlı müşteri yok. Hızlı işlem yapın.")
        else:
            aktif_musteri_adi = st.selectbox("Müşteri Seç:", kayitli_isimler)
            
    else: # Hızlı İşlem
        c1, c2 = st.columns([2, 1])
        girilen_isim = c1.text_input("Müşteri İsmi (Boş bırakırsan otomatik atanır):")
        if not girilen_isim:
            # Otomatik İsim Mantığı (İsimsiz Müşteri 1, 2...)
            mevcut_isimsizler = [x for x in kayitli_isimler if "İsimsiz Müşteri" in str(x)]
            siradaki_no = len(mevcut_isimsizler) + 1
            aktif_musteri_adi = f"İsimsiz Müşteri {siradaki_no}"
            c2.info(f"Otomatik Ad: {aktif_musteri_adi}")
        else:
            aktif_musteri_adi = girilen_isim

    st.divider()
    
    # MANUEL GİRİŞ
    st.subheader("🛠️ Parça Ekle")
    with st.form("parca_ekle"):
        c1, c2, c3 = st.columns(3)
        malz_list = st.session_state.malzeme_cache["Malzeme"].tolist()
        m_malz = c1.selectbox("Malzeme", malz_list)
        m_kal = c2.number_input("Kalınlık (mm)", value=2.0)
        m_adet = c3.number_input("Adet", value=1, min_value=1)
        
        c4, c5, c6 = st.columns(3)
        m_birim = c4.radio("Birim", ["mm", "cm", "m"], horizontal=True)
        m_en = c5.number_input("En", value=0.0)
        m_boy = c6.number_input("Boy", value=0.0)
        
        c7, c8 = st.columns(2)
        m_sure = c7.number_input("Kesim (dk)", value=0.0)
        m_bukum = c8.number_input("Büküm", value=0)
        
        if st.form_submit_button("Listeye Ekle"):
            carpan = 1000 if m_birim == "m" else (10 if m_birim == "cm" else 1)
            st.session_state.sepet.append({
                "Malzeme": m_malz, "K": m_kal, "En": m_en*carpan, "Boy": m_boy*carpan,
                "Adet": m_adet, "Süre": m_sure, "Büküm": m_bukum, "Sil": False
            })
            st.rerun()

    # SEPET TABLOSU
    if st.session_state.sepet:
        st.markdown("### 🛒 Sepet")
        df_sepet = pd.DataFrame(st.session_state.sepet)
        
        # Düzenlenebilir Tablo
        edited_df = st.data_editor(
            df_sepet,
            column_config={
                "Sil": st.column_config.CheckboxColumn("Sil?", width="small"),
                "Adet": st.column_config.NumberColumn("Adet", min_value=1),
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Silme Butonu
        if st.button("🗑️ Seçili Satırları Sil"):
            yeni_liste = [row for row in edited_df.to_dict('records') if not row.get("Sil")]
            st.session_state.sepet = yeni_liste
            st.rerun()
            
        st.divider()
        
        # HESAPLA BUTONU
        if st.button("💰 FİYAT HESAPLA", type="primary"):
            guncel_liste = [row for row in edited_df.to_dict('records') if not row.get("Sil")]
            if not guncel_liste:
                st.error("Liste boş!")
            else:
                total_tl = 0
                total_kg = 0
                df_malz_db = st.session_state.malzeme_cache
                
                for item in guncel_liste:
                    # Malzeme Fiyatını Bul
                    m_row = df_malz_db[df_malz_db["Malzeme"] == item["Malzeme"]].iloc[0]
                    fiyat = float(m_row["Fiyat"])
                    if m_row["Birim"] == "USD": fiyat *= DOLAR
                    
                    # Hesapla
                    hacim = item["En"] * item["Boy"] * item["K"]
                    kg = (hacim * float(m_row["Yogunluk"])) / 1_000_000 * item["Adet"]
                    
                    malz_tutar = kg * fiyat
                    iscilik = (item["Süre"] * item["Adet"] * LAZER_DK) + (item["Büküm"] * item["Adet"] * 15)
                    total_tl += malz_tutar + iscilik
                    total_kg += kg
                
                # Kar ve KDV
                satis = total_tl * (1 + KAR/100)
                kdv = satis * 0.20 if KDV_DURUM == "Evet" else 0
                genel_toplam = satis + kdv
                
                # Gösterim
                c1, c2, c3 = st.columns(3)
                c1.metric("Toplam Ağırlık", f"{total_kg:.2f} kg")
                c2.metric("Maliyet", f"{total_tl:.2f} TL")
                c3.metric("TEKLİF FİYATI", f"{genel_toplam:,.2f} TL")
                
                st.markdown("---")
                
                # KAYIT VE TEMİZLEME ALANI
                col_save, col_clear = st.columns([2, 1])
                
                not_alani = st.text_input("Sipariş Notu:", placeholder="İşin detayı...")
                
                with col_save:
                    if st.button("✅ MÜŞTERİYE KAYDET"):
                        with st.spinner("Kaydediliyor..."):
                            # 1. Siparişi Kaydet
                            df_sip = read_data("siparisler.csv")
                            yeni_sip = pd.DataFrame([{
                                "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "Müşteri": aktif_musteri_adi,
                                "İş Adı": not_alani or "Genel Sipariş",
                                "Tutar": round(genel_toplam, 2),
                                "Detay": f"{len(guncel_liste)} parça, {total_kg:.1f}kg"
                            }])
                            save_data("siparisler.csv", pd.concat([df_sip, yeni_sip], ignore_index=True))
                            
                            # 2. Eğer Müşteri Yeni İse Müşteri Listesine de Ekle (BU KISIM ÖNEMLİ)
                            df_mus_guncel = read_data("musteriler.csv")
                            if aktif_musteri_adi not in df_mus_guncel["Firma Adı"].values:
                                yeni_mus = pd.DataFrame([{
                                    "Firma Adı": aktif_musteri_adi,
                                    "Yetkili": "-",
                                    "Telefon": "-",
                                    "Adres": "-"
                                }])
                                save_data("musteriler.csv", pd.concat([df_mus_guncel, yeni_mus], ignore_index=True))
                            
                            st.success(f"{aktif_musteri_adi} adına başarıyla kaydedildi!")
                            st.session_state.sepet = [] # Sepeti temizle
                            time.sleep(2)
                            st.rerun()
                            
                with col_clear:
                    if st.button("🗑️ TEMİZLE (Sıfırla)"):
                        st.session_state.sepet = []
                        st.rerun()

# ==========================================
# 2. MÜŞTERİ YÖNETİMİ
# ==========================================
elif menu == "Müşteri Yönetimi":
    st.header("👥 Müşteri ve Sipariş Yönetimi")
    
    tab1, tab2 = st.tabs(["📋 Geçmiş & Detay", "➕ Yeni Firma Ekle"])
    
    with tab1:
        # Verileri oku
        df_mus = read_data("musteriler.csv")
        df_sip = read_data("siparisler.csv")
        
        if df_mus.empty:
            st.warning("Kayıtlı müşteri yok.")
        else:
            # Müşteri Seçimi
            isimler = sorted(df_mus["Firma Adı"].unique().tolist())
            secilen = st.selectbox("İncelemek istediğiniz müşteriyi seçin:", isimler)
            
            # Detaylar
            st.divider()
            col_info, col_table = st.columns([1, 2])
            
            with col_info:
                st.subheader("Firma Bilgisi")
                bilgi = df_mus[df_mus["Firma Adı"] == secilen].iloc[0]
                st.write(f"**Firma:** {bilgi['Firma Adı']}")
                st.write(f"**Yetkili:** {bilgi['Yetkili']}")
                st.write(f"**Tel:** {bilgi['Telefon']}")
                
                if st.button("⚠️ Bu Müşteriyi Sil"):
                    # Müşteriyi sil
                    df_mus = df_mus[df_mus["Firma Adı"] != secilen]
                    save_data("musteriler.csv", df_mus)
                    # Siparişlerini de silmek istersen:
                    # df_sip = df_sip[df_sip["Müşteri"] != secilen]
                    # save_data("siparisler.csv", df_sip)
                    st.success("Silindi!")
                    st.rerun()

            with col_table:
                st.subheader("Sipariş Geçmişi")
                if not df_sip.empty:
                    siparisler = df_sip[df_sip["Müşteri"] == secilen]
                    if not siparisler.empty:
                        st.dataframe(siparisler, use_container_width=True)
                        st.info(f"Toplam Ciro: {siparisler['Tutar'].sum():,.2f} TL")
                    else:
                        st.info("Bu müşteriye ait sipariş yok.")
                else:
                    st.info("Sistemde hiç sipariş yok.")

    with tab2:
        with st.form("yeni_ekle"):
            f = st.text_input("Firma Adı (Zorunlu)")
            y = st.text_input("Yetkili")
            t = st.text_input("Telefon")
            a = st.text_input("Adres")
            if st.form_submit_button("Kaydet"):
                if f:
                    df_m = read_data("musteriler.csv")
                    if f in df_m["Firma Adı"].values:
                        st.error("Bu isimde firma zaten var.")
                    else:
                        yeni = pd.DataFrame([{"Firma Adı": f, "Yetkili": y, "Telefon": t, "Adres": a}])
                        save_data("musteriler.csv", pd.concat([df_m, yeni], ignore_index=True))
                        st.success("Kaydedildi!")
                        st.rerun()
                else:
                    st.error("Firma adı girin.")

# ==========================================
# 3. AYARLAR
# ==========================================
elif menu == "Ayarlar":
    st.header("⚙️ Ayarlar")
    
    t1, t2 = st.tabs(["Genel", "Malzemeler"])
    
    with t1:
        c1, c2 = st.columns(2)
        yd = c1.number_input("Dolar", value=DOLAR)
        yk = c2.number_input("Kâr (%)", value=KAR)
        yl = c1.number_input("Lazer (TL/dk)", value=LAZER_DK)
        
        if st.button("Ayarları Güncelle"):
            df_a = st.session_state.ayarlar_cache
            df_a.loc[df_a['Ayar']=='dolar_kuru', 'Deger'] = yd
            df_a.loc[df_a['Ayar']=='kar_orani', 'Deger'] = yk
            df_a.loc[df_a['Ayar']=='lazer_dk', 'Deger'] = yl
            save_data("ayarlar.csv", df_a)
            st.session_state.ayarlar_cache = df_a
            st.success("Kaydedildi!")
            st.rerun()
            
    with t2:
        df_malz = st.session_state.malzeme_cache
        edited_m = st.data_editor(df_malz, num_rows="dynamic", use_container_width=True)
        if st.button("Malzemeleri Kaydet"):
            save_data("malzemeler.csv", edited_m)
            st.session_state.malzeme_cache = edited_m
            st.success("Kaydedildi!")
