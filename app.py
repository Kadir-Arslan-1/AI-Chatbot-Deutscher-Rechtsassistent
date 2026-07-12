import streamlit as st
import re
from pathlib import Path

from main import get_llm_manager
from main import get_pinecone_manager

llm_manager = get_llm_manager()
pinecone_manager = get_pinecone_manager()


# Avatars für chatbot:
user_svg = Path("streamlit_files/images/user_avatar.svg").read_text()
assistant_svg = Path("streamlit_files/images/ai_avatar.svg").read_text()
AVATARS = {"user": user_svg, "assistant": assistant_svg}

# Images:
page_icon = "streamlit_files/images/page_icon.ico"
logo_kadir_arslan = "streamlit_files/images/logo.png"
logo_deutsches_recht = Path("streamlit_files/images/page_logo.svg").read_text()


# Text-Formatter
def format_legal_text(raw_text: str) -> str:
    clean_text = re.sub(r'### TEIL \d+:\s*', '### ', raw_text)
    # Den "Hinweis" isolieren und in HTML verpacken (ohne den Rest zu zerstören)
    # Text extrahieren, Sternchen entfernen und Leerzeichen am Rand abschneiden
    def wrap_hinweis(match):
        hinweis_text = match.group(1).replace('*', '').strip()
        return f'<div class="legal-disclaimer">{hinweis_text}</div>'

    clean_text = re.sub(r'(?i)\*?(Hinweis:.*?)(?=\n\n|\Z)', wrap_hinweis, clean_text, flags=re.DOTALL)

    return clean_text


# Seiten-Konfiguration
st.set_page_config(
    page_title="Deutscher Rechtsassistent",
    page_icon=page_icon,
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS für das elegante, juristische Design
with open("streamlit_files/styles/main.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)



# Sidebar Aufbau
with st.sidebar:
    left, center, right = st.columns([1, 3, 1])

    with center:
        st.image(logo_kadir_arslan, width="content")

    st.markdown("---")

    st.markdown(
        """
        <h3 style='text-align: center; color: #04275a; font-family: sans-serif;'>German Legal Assistant</h3>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        Das ist Ihr KI-gestützter Berater für das **deutsche Rechtssystem**.
        \nPräzise, verlässlich und basierend auf aktuellen Gesetzen und Urteilen.
        \nSie können ihm jede Frage zum deutschen Recht stellen.
        """
    )

    st.markdown("""
    <div style=" font-size: 0.65rem;">
    <p style="font-size: 0.95rem; font-weight: 600; margin-bottom: 15px; margin-top: 15px;">
    Eigenschaften:
    </p>
    <p style="margin-bottom: 14px; font-size: 0.85rem;">🔹 Durchsucht die wichtigsten Gesetzesbücher, um relevante Gesetzestexte zu finden.</p>
    <p style="margin-bottom: 14px; font-size: 0.85rem;">🔹 Recherchiert und analysiert rund 3.000 hochwertige Gerichtsurteile zum Thema.</p>
    <p style="margin-bottom: 14px; font-size: 0.85rem;">🔹 Untersucht die Bekanntmachungen, Mitteillungen und Berichte aus offiziellen Quellen.</p>
    <p style="margin-bottom: 14px; font-size: 0.85rem;">🔹 Wertet die Ergebnisse aus und strukturiert die Antwort.</p>
    <p style="margin-bottom: 0; font-size: 0.85rem;">🔹 Gibt Sie die Empfehlungen heraus.</p>
    </div>
    """, unsafe_allow_html=True)

    # st.caption("Created for the German Citizens")

    st.markdown("---")


    # Lädt die Seite sofort neu und löscht die UI-Historie
    if st.button("🗑️ Neuen Chat beginnen", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


    # Footer:
    with open("streamlit_files/components/footer.html", "r", encoding="utf-8") as f:
        st.markdown(f.read(), unsafe_allow_html=True)


# Hauptbereich (Chat UI)

st.markdown(f"""
        <div style="display:flex; align-items:center;">
            {logo_deutsches_recht}
            <h1 style="margin:0;">Deutscher Rechtsassistent</h1>
        </div>
    """, unsafe_allow_html=True)

st.markdown("Stellen Sie Ihre juristische Frage. Das System analysiert deutsche Gesetze und Rechtsprechung.")
st.markdown("<br>", unsafe_allow_html=True)



# Chat-Historie initialisieren
if "messages" not in st.session_state:
    st.session_state.messages = []

# Historie beim Neuladen der Seite anzeigen
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=AVATARS[message["role"]]):
        st.markdown(message["content"], unsafe_allow_html=True)
        if "laws" in message and message["laws"]:
            with st.expander("⚖️ Zitierte Gesetze"):
                for law in message["laws"]:
                    st.markdown(f"- **{law}**", unsafe_allow_html=True)


# Nutzereingabe verarbeiten
if user_input := st.chat_input("Ihre Frage..."):

    # Wenn in messages noch nichts drin steht, ist es die erste:
    is_first_msg = len(st.session_state.messages) == 0

    # Nachricht des Nutzers anzeigen und speichern
    st.chat_message("user", avatar=AVATARS["user"]).markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Lade-Animation während das RAG-System arbeitet
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner("Ich analysiere Gesetze und Rechtsprechung..."):
            # llm_manager
            response_obj = llm_manager.ask_question(user_input, pinecone_manager, is_first_message=is_first_msg)
            raw_answer = response_obj.explanation
            cited_laws = response_obj.cited_laws

            # Final Text formatieren:
            final_answer = format_legal_text(raw_answer)

            # Antwort anzeigen
            st.markdown(final_answer, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Gesetze einklappbar anzeigen
            if cited_laws:
                with st.expander("⚖️ Zitierte Gesetze"):
                    for law in cited_laws:
                        st.markdown(f"- **{law}**", unsafe_allow_html=True)


    # KI-Antwort in der Historie speichern
    st.session_state.messages.append({
        "role": "assistant",
        "content": final_answer,
        "laws": cited_laws
    })
