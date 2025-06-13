import streamlit as st

from deepwiki_client import export_full_wiki

st.set_page_config(page_title="DeepWiki-Open POC", layout="wide")
st.title("🕵️ DeepWiki-Open – local FastAPI backend")

repo = st.text_input("GitHub/GitLab repo URL")
if st.button("Generate Wiki") and repo:
    with st.spinner("DeepWiki is working…"):
        wiki_dir = export_full_wiki(repo)  # ← one call only
    st.success(f"Done! Wiki in {wiki_dir}")

    pages = sorted(p.relative_to(wiki_dir) for p in wiki_dir.rglob("*.md"))
    sel = st.selectbox("Page", pages)
    st.markdown((wiki_dir / sel).read_text(), unsafe_allow_html=True)
