import streamlit as st
import os
import pandas as pd
from dotenv import load_dotenv
import openai
import io

# --- Load environment variables ---
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Login Protection ---
def login():
    st.title("🔐 KeywordSmart Pro Login")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if username == os.getenv("USERNAME") and password == os.getenv("PASSWORD"):
                st.session_state.logged_in = True
            else:
                st.error("❌ Invalid credentials.")

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    login()
    st.stop()

# --- App UI ---
st.title("📊 KeywordSmart Pro")
st.markdown("**Generate, cluster, and export ad-ready keywords with AI.**")

keyword_method = st.radio("How do you want to provide keywords?", ("Manual input", "Upload file", "Let GPT suggest keywords"))

keywords = []

# --- Manual Input ---
if keyword_method == "Manual input":
    manual_input = st.text_area("Enter keywords (one per line):")
    if manual_input:
        keywords = [k.strip() for k in manual_input.splitlines() if k.strip()]

# --- Upload File ---
elif keyword_method == "Upload file":
    uploaded_file = st.file_uploader("Upload a .txt or .csv file with keywords:")
    if uploaded_file:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            keywords = df.iloc[:, 0].dropna().tolist()
        elif uploaded_file.name.endswith(".txt"):
            keywords = [line.decode("utf-8").strip() for line in uploaded_file.readlines() if line.strip()]

# --- GPT Suggestion ---
elif keyword_method == "Let GPT suggest keywords":
    with st.container():
        st.subheader("📋 GPT Keyword Builder")
        business = st.text_input("What is your business or service? (e.g., SEO agency, dog groomer)")
        audience = st.text_input("Who is your ideal customer? (e.g., NZ business owners, dog owners)")
        location = st.text_input("What location do you want to target?", value="New Zealand")

        if business and audience:
            seed_term = f"{business} for {audience} in {location}"
            if st.button("🔍 Suggest Keywords with GPT"):
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

# --- GPT Ad Generation ---
def generate_ads_from_keywords(keywords):
    cluster_prompt = f"""
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
                {"role": "user", "content": cluster_prompt}
            ]
        )
        return response['choices'][0]['message']['content']

# --- Display Output ---
if keywords:
    if st.button("🎯 Generate Campaign Structure"):
        full_output = generate_ads_from_keywords(keywords)
        st.subheader("📦 Generated Campaigns")
        st.markdown(full_output)

        # TXT Download
        st.download_button("📄 Download Full Text", full_output, file_name="keywordsmart_output.txt")

        # --- Parse Markdown to CSV ---
        sections = full_output.split("---")
        csv_data = []
        for section in sections:
            campaign = adgroup = funnel = intent = negative = landing = ""
            headlines = []
            descriptions = []
            kws = []

            lines = section.splitlines()
            for line in lines:
                if line.startswith("Campaign:"): campaign = line.split(":",1)[1].strip()
                if line.startswith("Ad Group:"): adgroup = line.split(":",1)[1].strip()
                if line.startswith("Funnel Stage:"): funnel = line.split(":",1)[1].strip()
                if line.startswith("Intent Type:"): intent = line.split(":",1)[1].strip()
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

        # CSV Download
        if csv_data:
            df = pd.DataFrame(csv_data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            st.download_button("📥 Download CSV", data=csv_buffer.getvalue(), file_name="keywordsmart_ads.csv", mime="text/csv")
