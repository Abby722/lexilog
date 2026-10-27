"""lexilog: run with `streamlit run app.py`."""
import streamlit as st

st.set_page_config(page_title="lexilog", page_icon="📖", layout="wide")

pages = st.navigation([
    st.Page("views/dashboard.py", title="Progress", icon=":material/insights:", default=True),
    st.Page("views/capture.py", title="Add a word", icon=":material/add_circle:", url_path="add"),
    st.Page("views/review.py", title="Review", icon=":material/style:"),
    st.Page("views/browse.py", title="Word list", icon=":material/menu_book:"),
    st.Page("views/read_document.py", title="Read a document", icon=":material/description:",
            url_path="read"),
    st.Page("views/import_data.py", title="Import", icon=":material/upload_file:"),
    st.Page("views/settings.py", title="Goals & capture", icon=":material/flag:"),
])
pages.run()
