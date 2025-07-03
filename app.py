import streamlit as st
import os
import pandas as pd
import openai
import requests

# --- Load Streamlit secrets ---
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
SEMRUSH_API_KEY = st.secrets["SEMRUSH_API_KEY"]

# --- Use OpenAI v1 client ---
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# --- Configure Streamlit page ---
st.set_page_config(page_title="KeywordSmart Pro", page_icon="📊")

# --- Safe rerun ---
def safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

# --- Session state defaults ---
if "business_info" not in st.session_state:
    st.session_state.business_info = {}
if "generated_keywords" not in st.session_state:
    st.session_state.generated_keywords = []
if "ad_groups" not in st.session_state:
    st.session_state.ad_groups = {}
if "setup_complete" not in st.session_state:
    st.session_state.setup_complete = False

# --- SEMrush fetch function ---
def fetch_semrush_keywords(api_key, keyword, database="nz"):
    url = "https://api.semrush.com/"
    params = {
        "type": "phrase_related",
        "key": api_key,
        "phrase": keyword,
        "database": database,
        "display_limit": 20,
        "export_columns": "Ph,Nq,Cp,Kd,Intent"
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        lines = response.text.splitlines()[1:]  # Skip header
        data = [line.split(";") for line in lines]
        df = pd.DataFrame(data, columns=["Keyword", "Volume", "CPC", "Difficulty"])
        return df
    else:
        st.error(f"SEMrush API error: {response.status_code}")
        return pd.DataFrame()

# --- Business setup ---
def ask_business_questions():
    st.title("🧠 KeywordSmart Pro Setup")
    st.write("Let’s get to know your business.")
    with st.form("business_info_form"):
        biz = st.text_input("What is your business?", value=st.session_state.business_info.get("business", ""))
        audience = st.text_input("Who is your target audience?", value=st.session_state.business_info.get("audience", ""))
        location = st.text_input("Where are they located?", value=st.session_state.business_info.get("location", ""))
        submitted = st.form_submit_button("Continue")

    if submitted:
        if biz and audience and location:
            st.session_state.business_info = {
                "business": biz,
                "audience": audience,
                "location": location,
            }
            st.session_state.setup_complete = True
            safe_rerun()
        else:
            st.warning("Please fill out all fields.")

# --- GPT-based SKAG + RSA Ad Copy ---
def cluster_keywords_and_generate_ads(keywords):
    prompt = f"""
You are a Google Ads PPC expert in 2025. Group the following keywords using the SKAG (Single Keyword Ad Group) method. Each ad group should:
- Have a clear name based on a core keyword
- Include close variants only (not loosely related terms)
- Contain no more than 6 tightly matched keywords
- Include 3 Responsive Search Ad headlines and 2 descriptions per group

Output format:

[Ad Group: Core Keyword]
Keywords:
- keyword 1
- keyword 2
...
Headlines:
- Headline 1
- Headline 2
- Headline 3
Descriptions:
- Description 1
- Description 2

Keywords:
{', '.join(keywords)}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"❌ Failed to cluster & generate ads: {e}")
        return None

# --- Keyword Tool ---
def keyword_tool():
    st.title("📊 KeywordSmart Pro")
    st.subheader("Generate, SKAG-cluster, and export ad-ready keywords with AI.")

    method = st.radio("How do you want to provide keywords?", [
        "Manual input",
        "Upload file",
        "Let GPT suggest keywords",
        "Use Semrush Keyword Suggestions"
    ])
    keywords = []

    if method == "Manual input":
        with st.form("manual_form"):
            raw = st.text_area("Enter keywords (one per line):")
            submitted = st.form_submit_button("Submit")
            if submitted:
                keywords = [line.strip() for line in raw.splitlines() if line.strip()]
                st.session_state.generated_keywords = keywords
                safe_rerun()

    elif method == "Upload file":
        with st.form("upload_form"):
            st.markdown("""
            **📥 Upload Instructions**

            Please upload a `.txt` or `.csv` file with **only keywords**:

            ✅ `.txt` → one keyword per line  
            ✅ `.csv` → a single column of keywords (remove extra columns first)

            ⚠️ Remove metrics like search volume, CPC, or competition to avoid errors.
            """)
            file = st.file_uploader("Upload your keyword file", type=["txt", "csv"])
            submitted = st.form_submit_button("Submit")
            if submitted and file:
                try:
                    if file.name.endswith(".txt"):
                        keywords = file.read().decode("utf-8").splitlines()
                    else:
                        df = pd.read_csv(file, encoding="utf-8", usecols=[0])
                        keywords = df.iloc[:, 0].dropna().astype(str).tolist()
                    keywords = [k.strip() for k in keywords if k.strip()]
                    st.session_state.generated_keywords = keywords
                    safe_rerun()
                except Exception as e:
                    st.error(f"❌ Failed to process file: {e}")

    elif method == "Let GPT suggest keywords":
        biz = st.session_state.business_info.get("business", "")
        audience = st.session_state.business_info.get("audience", "")
        location = st.session_state.business_info.get("location", "")
        seed = f"{biz} for {audience} in {location}"

        with st.form("gpt_form"):
            st.write(f"Generate keywords for: **{seed}**")
            submitted = st.form_submit_button("Generate with GPT")
            if submitted:
                with st.spinner("Generating keywords..."):
                    try:
                        prompt = f"Generate 20 high-intent PPC keywords for {seed}. Format each in square brackets like [keyword]."
                        response = client.chat.completions.create(
                            model="gpt-4",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        raw = response.choices[0].message.content
                        keywords = [line.strip("[] ") for line in raw.splitlines() if "[" in line]
                        st.session_state.generated_keywords = keywords
                        safe_rerun()
                    except Exception as e:
                        st.error(f"❌ GPT failed: {e}")

    elif method == "Use Semrush Keyword Suggestions":
        with st.form("semrush_form"):
            seed = st.text_input("Enter a seed keyword (e.g. beard trimmer, accounting software)")
            region = st.selectbox("Choose a region database", ["nz", "us", "uk", "au", "ca"])
            submitted = st.form_submit_button("Fetch Suggestions")

        if submitted and seed:
            with st.spinner("Fetching keyword data from Semrush..."):
                try:
                    df = fetch_semrush_keywords(SEMRUSH_API_KEY, seed, region)
                    if not df.empty:
                        st.markdown("### ✅ Semrush Keyword Suggestions")
                        selected = st.multiselect("Select keywords to use:", df["Keyword"].tolist())
                        if selected:
                            st.session_state.generated_keywords = selected
                            safe_rerun()
                        st.dataframe(df)
                    else:
                        st.warning("No keywords returned.")
                except Exception as e:
                    st.error(f"❌ SEMrush fetch failed: {e}")

    # --- Final keyword output + GPT clustering ---
    final_keywords = st.session_state.get("generated_keywords", [])
    if final_keywords:
        st.markdown("### ✅ Generated Keywords")
        df = pd.DataFrame(final_keywords, columns=["Keyword"])
        st.dataframe(df)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Keywords CSV", data=csv, file_name="keywords.csv", mime="text/csv")

        with st.spinner("🔎 SKAG Clustering & Ad Copy Generation..."):
            ad_output = cluster_keywords_and_generate_ads(final_keywords)
            if ad_output:
                st.markdown("### 🧠 SKAG-Based Ad Groups & Responsive Ads")
                st.text_area("Results:", ad_output, height=500)
                st.download_button("📥 Download Ad Groups", data=ad_output, file_name="ad_groups.txt", mime="text/plain")

# --- Main App Flow ---
if not st.session_state.setup_complete:
    ask_business_questions()
else:
    keyword_tool()
