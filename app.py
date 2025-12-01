import streamlit as st
import pandas as pd

# Sayfa Ayarları
st.set_page_config(page_title="Lazer & Abkant Hesaplayıcı", layout="wide")

# --- SOL MENÜ (AYARLAR) ---
st.sidebar.header("⚙️ Birim Fiyat Ayarları")
st.sidebar.info("Buradaki fiyatları piyasaya göre güncelleyebilirsiniz.")

# Malzeme KG Fiyatları (Örnek Dolar/TL bazlı olabilir, burası TL varsayıldı)
dkp_fiyat = st.sidebar.number_input("DKP Sac (TL/kg)", value=30.0)
paslanmaz_fiyat = st.sidebar.number_input("Paslanmaz (TL/kg)", value=120.0)
alu_fiyat = st.sidebar.number_input("Alüminyum (TL/kg)", value=90.0)

st.sidebar.markdown("---")
# İşçilik Fiyatları
lazer_dakika_ucreti = st.sidebar.number_input("Lazer Kesim (TL/dk)", value=15.0)
abkant_bukum_ucreti = st.sidebar.number_input("Büküm Başına Ücret (TL)", value=5.0)
kaynak_saat_ucreti = st.sidebar.number_input("Kaynak İşçiliği (TL/saat)", value=250.0)

# --- ANA SAYFA ---
st.title("🏭 Metal İşleme Teklif Hesaplayıcı")
st.markdown("Malzeme özelliklerini ve işlem detaylarını girerek tahmini maliyet oluşturun.")

# 1. Bölüm: Malzeme Seçimi
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Malzeme Bilgileri")
    malzeme_turu = st.selectbox("Malzeme Türü", ["DKP", "Paslanmaz (304)", "Alüminyum"])
    
    # Malzeme Yoğunlukları (g/cm3)
    yogunluklar = {"DKP": 7.85, "Paslanmaz (304)": 7.9, "Alüminyum": 2.7}
    secilen_yogunluk = yogunluklar[malzeme_turu]
    
    kalinlik = st.number_input("Sac Kalınlığı (mm)", min_value=0.5, value=2.0, step=0.5)
    en = st.number_input("Parça Eni (mm)", value=100.0)
    boy = st.number_input("Parça Boyu (mm)", value=200.0)
    adet = st.number_input("Kaç Adet Üretilecek?", min_value=1, value=1, step=1)

# Ağırlık Hesabı
hacim_mm3 = en * boy * kalinlik
agirlik_kg_tek = (hacim_mm3 * secilen_yogunluk) / 1_000_000 # mm3'ten kg'a çevirim
toplam_agirlik = agirlik_kg_tek * adet

# Malzeme Maliyeti Hesabı
birim_kg_fiyat = 0
if malzeme_turu == "DKP": birim_kg_fiyat = dkp_fiyat
elif malzeme_turu == "Paslanmaz (304)": birim_kg_fiyat = paslanmaz_fiyat
else: birim_kg_fiyat = alu_fiyat

malzeme_maliyeti = toplam_agirlik * birim_kg_fiyat

with col2:
    st.subheader("2. İşlem Bilgileri")
    kesim_uzunlugu = st.number_input("Toplam Kesim Yolu (mm)", value=(en+boy)*2, help="Lazerin toplam gezeceği mesafe")
    delik_sayisi = st.number_input("Patlatma/Delik Sayısı", value=0)
    bukum_sayisi = st.number_input("Büküm Sayısı (Parça Başı)", value=2)
    kaynak_suresi = st.number_input("Kaynak Süresi (Dakika/Parça)", value=0)

# Lazer Süre Tahmini (Basit bir mantık: Kalınlık arttıkça hız düşer)
# Bu formül çok basittir, makinenizin gerçek verilerine göre güncellenebilir.
tahmini_hiz_mm_dk = 10000 / kalinlik # mm/dk (Örnek formül)
kesim_suresi_dk = (kesim_uzunlugu / tahmini_hiz_mm_dk) + (delik_sayisi * 0.05) # her delik 3 saniye ekler
toplam_lazer_maliyeti = kesim_suresi_dk * lazer_dakika_ucreti * adet

# Büküm Maliyeti
toplam_bukum_maliyeti = bukum_sayisi * abkant_bukum_ucreti * adet

# Kaynak Maliyeti
toplam_kaynak_maliyeti = (kaynak_suresi / 60) * kaynak_saat_ucreti * adet

# --- SONUÇ EKRANI ---
st.markdown("---")
st.header("💰 Maliyet Özeti")

toplam_maliyet = malzeme_maliyeti + toplam_lazer_maliyeti + toplam_bukum_maliyeti + toplam_kaynak_maliyeti

c1, c2, c3 = st.columns(3)
c1.metric("Toplam Ağırlık", f"{toplam_agirlik:.2f} kg")
c2.metric("Parça Başı Maliyet", f"{toplam_maliyet / adet:.2f} TL")
c3.metric("TOPLAM TUTAR", f"{toplam_maliyet:.2f} TL", delta_color="inverse")

# Detay Tablosu
st.subheader("Maliyet Dağılımı")
data = {
    "Kalem": ["Malzeme", "Lazer Kesim", "Abkant Büküm", "Kaynak İşçiliği"],
    "Tutar (TL)": [malzeme_maliyeti, toplam_lazer_maliyeti, toplam_bukum_maliyeti, toplam_kaynak_maliyeti]
}
df = pd.DataFrame(data)
st.bar_chart(df.set_index("Kalem"))
st.table(df)

# Kar Marjı Ekleme
st.markdown("---")
kar_orani = st.slider("Kar Marjı (%)", 0, 100, 20)
satis_fiyati = toplam_maliyet * (1 + kar_orani/100)

st.success(f"✅ **Önerilen Satış Fiyatı (%{kar_orani} Kar Dahil): {satis_fiyati:.2f} TL**")
