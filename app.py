import streamlit as st
import os
import pandas as pd
from dotenv import load_dotenv
import openai
import io

# --- Load environment variables ---
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
ENV_USERNAME = os.getenv("USERNAME")
ENV_PASSWORD = os.getenv("PASSWORD")

# --- Session state init ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --- Login form ---
def login_form():
    st.title("🔐 KeywordSmart Pro Login")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if username == ENV_USERNAME and password == ENV_PASSWORD:
                st.session_state.logged_in = True
                st.experimental_rerun()
            else:
                st.error("❌ Invalid credentials. Please try again.")

# --- If not logged in, show login ---
if not st.session_state.logged_in:
    login_form()
    st.stop()

# --- Main App ---
st.title("📊 KeywordSmart Pro")
st.markdown("**Generate, cluster, and export ad-ready keywords with AI.**")

# --- Keyword input method ---
keyword_method = st.radio("How do you want to provide keywords?", ("Manual input", "Upload file", "Let GPT suggest keywords"))
keywords = []

# --- Manual input ---
if keyword_method == "Manual input":
    manual_input = st.text_area("Enter keywords (one per line):")
    if manual_input:
        keywords = [k.strip() for k in manual_input.splitlines() if k.strip()]

# --- File upload ---
elif keyword_method == "Upload file":
    uploaded_file = st.file_uploader("Upload a .txt or .csv file with keywords:")
    if uploaded_file:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            keywords = df.iloc[:, 0].dropna().tolist()
        elif uploaded_file.name.endswith(".txt"):
            keywords = [line.decode("utf-8").strip() for line in uploaded_file.readlines() if line.strip()]

# --- GPT keyword suggestion ---
elif keyword_method == "Let GPT suggest keywords":
    st.subheader("📋 GPT Keyword Builder")
    business = st.text_input("What is your business or service?")
    audience = st.text_input("Who is your ideal customer?")
    location = st.text_input("What location do you want to target?", value="New Zealand")

    if business and audience:
        if st.button("🔍 Suggest Keywords with GPT"):
            seed_term = f"{business} for {audience} in {location}"
            with st.spinner("Asking GPT to generate relevant keywords..."):
                gpt_prompt = f"""
Generate a list of 40 high-intent keywords for a business type: {business}, targeting: {audience}, in: {location}.
Include a mix of:
- Commercial terms
- Local terms
- Branded and competitor intent if relevant
Output only the keywords in square brackets, one per line.
"""
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You're a PPC expert helping build a Google Ads campaign."},
                        {"role": "user", "content": gpt_prompt}
                    ]
                )
                raw_keywords = response['choices'][0]['message']['content']
                keywords = [line.strip("[] ") for line in raw_keywords.splitlines() if line.startswith("[")]
                st.success("✅ Keywords generated successfully!")

# --- GPT ad generator ---
def generate_ads_from_keywords(keywords):
    prompt = f"""
You are a Google Ads expert. Based on the list of keywords below, cluster them into logical ad groups and campaigns.

For each group, provide:
- Campaign name
- Ad group name
- Funnel stage (Top, Middle, Bottom)
- Intent type (Informational, Commercial, Navigational, Branded)
- 3 headlines
- 3 descriptions
- Keyword list (with match type)
- 1 negative keyword
- Suggested landing page type

Keywords:
{keywords}
Output in clean Markdown format.
"""
    with st.spinner("Clustering keywords + writing ads..."):
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a Google Ads copywriting assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return response['choices'][0]['message']['content']

# --- Run GPT + download ---
if keywords:
    if st.button("🎯 Generate Campaign Structure"):
        full_output = generate_ads_from_keywords(keywords)
        st.subheader("📦 Generated Campaigns")
        st.markdown(full_output)

        # TXT download
        st.download_button("📄 Download Full Text", full_output, file_name="keywordsmart_output.txt")

        # Parse basic structure to CSV
        sections = full_output.split("---")
        csv_data = []
        for section in sections:
            campaign = adgroup = funnel = intent = negative = landing = ""
            headlines, descriptions, kws = [], [], []

            for line in section.splitlines():
                if line.startswith("Campaign:"): campaign = line.split(":", 1)[1].strip()
                if line.startswith("Ad Group:"): adgroup = line.split(":", 1)[1].strip()
                if line.startswith("Funnel Stage:"): funnel = line.split(":", 1)[1].strip()
                if line.startswith("Intent Type:"): intent = line.split(":", 1)[1].strip()
                if "- [" in line and "]" in line: kws.append(line.split("[")[1].split("]")[0])
                if line.startswith("- Headline"): headlines.append(line.split(":",1)[1].strip())
                if line.startswith("- Description"): descriptions.append(line.split(":",1)[1].strip())
                if line.startswith("Negative Keyword:"): negative = line.split(":",1)[1].strip()
                if line.startswith("Landing Page Suggestion:"): landing = line.split(":",1)[1].strip()

            for kw in kws:
                csv_data.append({
                    "Campaign": campaign,
                    "Ad Group": adgroup,
                    "Funnel Stage": funnel,
                    "Intent Type": intent,
                    "Keyword": kw,
                    "Headline 1": headlines[0] if len(headlines)>0 else "",
                    "Headline 2": headlines[1] if len(headlines)>1 else "",
                    "Headline 3": headlines[2] if len(headlines)>2 else "",
                    "Description 1": descriptions[0] if len(descriptions)>0 else "",
                    "Description 2": descriptions[1] if len(descriptions)>1 else "",
                    "Description 3": descriptions[2] if len(descriptions)>2 else "",
                    "Negative Keyword": negative,
                    "Landing Page Suggestion": landing
                })

        if csv_data:
            df = pd.DataFrame(csv_data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            st.download_button("📥 Download CSV", data=csv_buffer.getvalue(), file_name="keywordsmart_ads.csv", mime="text/csv")
