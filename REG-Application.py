import streamlit as st
import pandas as pd
import numpy as np
import datetime
import requests
import json
import hashlib
from urllib.error import URLError
from streamlit_folium import folium_static
import folium

# Fonction de hachage des données pour détection de changement
def hash_data(df):
    return hashlib.md5(pd.util.hash_pandas_object(df, index=True).values).hexdigest()

# Fonction de lecture depuis Google Sheets
@st.cache_data(ttl=60)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1tHG9eTqzyOkl9HKAWo6RU3voBxCqnotx2_R8sfZ31jQ/export?format=csv"
    try:
        df = pd.read_csv(url)
        df["Date debut collecte"] = pd.to_datetime(df["Date debut collecte"], errors='coerce')
        df["Date fin collecte"] = pd.to_datetime(df["Date fin collecte"], errors='coerce')
        df["Duree_collecte"] = (df["Date fin collecte"] - df["Date debut collecte"]).dt.days
        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {e}")
        return pd.DataFrame()

# Authentification
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.set_page_config(page_title="Suivi Collecte RGE-2", layout="wide")
    st.title("🔐 Authentification requise")
    password = st.text_input("Entrez le mot de passe :", type="password")
    if st.button("Connexion"):
        if password == "RGE2025":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect !")
    st.stop()

# Interface principale
st.set_page_config(page_title="Suivi Collecte RGE-2", layout="wide")
st.title("📊 Suivi de la collecte des données - RGE-2")
data = load_data()

# Onglets horizontaux
tab1, tab2, tab3, tab4 = st.tabs(["📈 Statistiques", "🗺️ Carte", "📋 Suivi des agents", "🤖 Chatbot IA"])

# --- Onglet 1 : Statistiques ---
with tab1:
    st.subheader("📈 Statistiques globales")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Zones recensées", data["Code Zone de recensement"].nunique())
    with col2:
        st.metric("Îlots recensés", data["Numero de l'ilot"].nunique())
    with col3:
        st.metric("Total collectes", len(data))

    st.subheader("📅 Évolution des collectes")
    hist = data["Date debut collecte"].value_counts().sort_index()
    st.bar_chart(hist)

# --- Onglet 2 : Carte ---
with tab2:
    st.subheader("🗺️ Carte des collectes")
    date1 = st.date_input("Date de début", datetime.date(2025, 1, 1), key="carte_dd")
    date2 = st.date_input("Date de fin", datetime.date.today(), key="carte_df")
    agents = ["Tous"] + sorted(data["Nom et prenoms"].dropna().unique())
    selected_agent = st.selectbox("Choisir un agent", agents)

    filtered = data[
        (data["Date debut collecte"] >= pd.to_datetime(date1)) &
        (data["Date fin collecte"] <= pd.to_datetime(date2))
    ]
    if selected_agent != "Tous":
        filtered = filtered[filtered["Nom et prenoms"] == selected_agent]

    filtered["LATITUDE"] = pd.to_numeric(filtered["LATITUDE"], errors="coerce")
    filtered["LONGITUDE"] = pd.to_numeric(filtered["LONGITUDE"], errors="coerce")

    map_data = filtered[["LATITUDE", "LONGITUDE"]].dropna()

    if not map_data.empty:
        st.map(map_data.rename(columns={"LATITUDE": "lat", "LONGITUDE": "lon"}))
    else:
        st.warning("Aucune donnée géographique disponible pour les filtres sélectionnés.")

# --- Onglet 3 : Suivi des agents ---
with tab3:
    st.subheader("📋 Suivi des agents")
    date1 = st.date_input("Date début", datetime.date(2025, 1, 1), key="suivi_dd")
    date2 = st.date_input("Date fin", datetime.date.today(), key="suivi_df")
    seuil = st.number_input("Seuil de collectes minimum", min_value=1, value=10)

    filt = data[
        (data["Date debut collecte"] >= pd.to_datetime(date1)) &
        (data["Date fin collecte"] <= pd.to_datetime(date2))
    ]
    stats = filt.groupby("Nom et prenoms").agg({
        "Duree_collecte": "mean",
        "Date debut collecte": "count"
    }).rename(columns={
        "Duree_collecte": "Durée moyenne (jours)",
        "Date debut collecte": "Total collectes"
    })
    stats = stats[stats["Total collectes"] <= seuil]
    st.dataframe(stats.reset_index())

# --- Onglet 4 : Chatbot IA ---
with tab4:
    st.subheader("🤖 Chatbot IA")
    user_message = st.text_input("Posez une question :")
    if st.button("Envoyer") and user_message:
        try:
            API_KEY = st.secrets["openai"]["api_key"]
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
            data_payload = {
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "Tu es un assistant pour l'analyse des données de collecte."},
                    {"role": "user", "content": user_message}
                ]
            }
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data_payload)
            if response.status_code == 200:
                reply = response.json()["choices"][0]["message"]["content"].strip()
                st.markdown(f"**Vous :** {user_message}")
                st.markdown(f"**Chatbot :** {reply}")
            else:
                st.error("Erreur lors de l'appel à l'API OpenAI.")
        except Exception as e:
            st.error(f"Erreur : {e}")
