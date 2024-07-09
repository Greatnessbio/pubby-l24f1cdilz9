import streamlit as st
import pandas as pd
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import random
import time
from datetime import datetime, timedelta

# User agents list (abbreviated for brevity)
user_agents = [
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36"
]

# Function to load users from Streamlit secrets
def load_users():
    return st.secrets["users"]

# Function to handle login
def login(username, password):
    users = load_users()
    if username in users and users[username] == password:
        return True
    return False

def make_header():
    return {'User-Agent': random.choice(user_agents)}

async def extract_by_article(url, semaphore):
    # ... (rest of the function remains unchanged)

async def get_pmids(page, keyword, date_range):
    # ... (rest of the function remains unchanged)

async def scrape_pubmed(keywords, num_pages, date_range):
    # ... (rest of the function remains unchanged)

def analyze_with_openrouter(data, query, openrouter_api_key):
    # ... (rest of the function remains unchanged)

def main_app():
    st.title("Enhanced PubMed Scraper and Analysis App")

    # Search parameters
    col1, col2 = st.columns(2)
    with col1:
        keywords = st.text_input("Enter your PubMed search query (separate multiple keywords with commas):", "")
        num_pages = st.number_input("Number of pages to scrape per keyword (1 page = 10 results)", min_value=1, max_value=100, value=1)
    
    with col2:
        date_range = st.selectbox("Select date range:", 
                                  ["1 Year", "5 Years", "10 Years", "Custom"],
                                  index=1)
        if date_range == "Custom":
            start_date = st.date_input("Start date", datetime.now() - timedelta(days=365))
            end_date = st.date_input("End date", datetime.now())
            custom_range = f"{start_date.strftime('%Y/%m/%d')}-{end_date.strftime('%Y/%m/%d')}"
        else:
            custom_range = None

    # Advanced options
    with st.expander("Advanced Options"):
        include_abstract = st.checkbox("Include abstract", value=True)
        include_affiliations = st.checkbox("Include affiliations", value=True)

    if st.button("Search and Analyze") and keywords:
        keywords_list = [k.strip() for k in keywords.split(',')]
        
        with st.spinner("Scraping PubMed and analyzing results..."):
            date_param = custom_range if date_range == "Custom" else date_range.lower().replace(" ", "")
            df = asyncio.run(scrape_pubmed(keywords_list, num_pages, date_param))
            
            if not df.empty:
                st.subheader("Search Results")
                
                # Filter columns based on user preferences
                columns_to_show = ['title', 'authors', 'date', 'url']
                if include_abstract:
                    columns_to_show.append('abstract')
                if include_affiliations:
                    columns_to_show.append('affiliations')
                
                st.dataframe(df[columns_to_show])
                
                # Download options
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download full results as CSV",
                    data=csv,
                    file_name="pubmed_results.csv",
                    mime="text/csv",
                )
                
                # Generate outreach table
                st.subheader("Outreach Table")
                outreach_df = df[['authors', 'affiliations', 'title']].copy()
                outreach_df['first_name'] = outreach_df['authors'].apply(lambda x: x.split(',')[0].split()[-1] if x != 'NO_AUTHOR' else '')
                outreach_df['last_name'] = outreach_df['authors'].apply(lambda x: x.split(',')[0].split()[0] if x != 'NO_AUTHOR' else '')
                outreach_df['email'] = 'N/A'  # Email extraction would require additional processing
                outreach_df['institution'] = outreach_df['affiliations'].apply(lambda x: x[0] if x else 'N/A')
                outreach_df['title'] = outreach_df['title'].apply(lambda x: x[:100] + '...' if len(x) > 100 else x)
                
                outreach_columns = ['first_name', 'last_name', 'email', 'institution', 'title']
                st.dataframe(outreach_df[outreach_columns])
                
                # Download outreach table
                outreach_csv = outreach_df[outreach_columns].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download outreach table as CSV",
                    data=outreach_csv,
                    file_name="pubmed_outreach.csv",
                    mime="text/csv",
                )
                
                # Here you can add the analysis part using OpenRouter if needed
                # analysis = analyze_with_openrouter(df, keywords, api_keys["openrouter"])
                # if analysis:
                #     st.subheader("Analysis")
                #     st.write(analysis)
            else:
                st.error("No results found. Please try a different query or increase the number of pages.")

def login_page():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if login(username, password):
            st.session_state.logged_in = True
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password")

def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_page()
    else:
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
        else:
            main_app()

if __name__ == "__main__":
    main()
