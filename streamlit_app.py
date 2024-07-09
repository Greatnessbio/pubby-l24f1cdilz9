import streamlit as st
import requests
import pandas as pd
import json
import base64
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import random
import time

# Function to load API keys from Streamlit secrets
def load_api_keys():
    try:
        return {
            "openrouter": st.secrets["secrets"]["openrouter_api_key"],
        }
    except KeyError as e:
        st.error(f"{e} API key not found in secrets.toml. Please add it.")
        return None

# Function to load users from Streamlit secrets
def load_users():
    return st.secrets["users"]

# Function to handle login
def login(username, password):
    users = load_users()
    if username in users and users[username] == password:
        return True
    return False

# User agents list (abbreviated for brevity)
user_agents = [
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36"
]

def make_header():
    return {'User-Agent': random.choice(user_agents)}

async def extract_by_article(url, semaphore):
    async with semaphore:
        async with aiohttp.ClientSession(headers=make_header()) as session:
            async with session.get(url) as response:
                data = await response.text()
                soup = BeautifulSoup(data, "lxml")
                
                try:
                    title = soup.find('meta', {'name': 'citation_title'})['content'].strip('[]')
                except:
                    title = 'NO_TITLE'
                
                try:
                    abstract_raw = soup.find('div', {'class': 'abstract-content selected'}).find_all('p')
                    abstract = ' '.join([paragraph.text.strip() for paragraph in abstract_raw])
                except:
                    abstract = 'NO_ABSTRACT'
                
                try:
                    authors = ', '.join([author.text for author in soup.find('div', {'class': 'authors-list'}).find_all('a', {'class': 'full-name'})])
                except:
                    authors = 'NO_AUTHOR'
                
                try:
                    date = soup.find('time', {'class': 'citation-year'}).text
                except:
                    date = 'NO_DATE'

                return {
                    'url': url,
                    'title': title,
                    'authors': authors,
                    'abstract': abstract,
                    'date': date
                }

async def get_pmids(page, keyword):
    page_url = f'https://pubmed.ncbi.nlm.nih.gov/?term={keyword}&page={page}'
    async with aiohttp.ClientSession(headers=make_header()) as session:
        async with session.get(page_url) as response:
            data = await response.text()
            soup = BeautifulSoup(data, "lxml")
            pmids = soup.find('meta', {'name': 'log_displayeduids'})['content']
            return [f"https://pubmed.ncbi.nlm.nih.gov/{pmid}" for pmid in pmids.split(',')]

async def scrape_pubmed(keywords, num_pages=1):
    semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
    all_urls = []
    for keyword in keywords:
        for page in range(1, num_pages + 1):
            urls = await get_pmids(page, keyword)
            all_urls.extend(urls)
    
    tasks = [extract_by_article(url, semaphore) for url in all_urls]
    results = await asyncio.gather(*tasks)
    return pd.DataFrame(results)

def analyze_with_openrouter(data, query, openrouter_api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Analyze the following PubMed search results for the query: {query}
    
    Data:
    {data.to_json(orient='records')}
    
    Provide a summary of the key findings, trends, and insights from these articles.
    Also, suggest potential areas for further research based on these results.
    """
    
    payload = {
        "model": "anthropic/claude-3-sonnet-20240229",
        "messages": [
            {"role": "system", "content": "You are a research assistant tasked with analyzing PubMed search results."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.RequestException as e:
        st.error(f"OpenRouter API request failed: {e}")
    return None

def get_csv_download_link(df, filename="pubmed_results.csv"):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV</a>'
    return href

def main_app():
    st.title("PubMed Scraper and Analysis App")

    api_keys = load_api_keys()
    if not api_keys:
        return

    query = st.text_input("Enter your PubMed search query:")
    num_pages = st.number_input("Number of pages to scrape (1 page = 10 results)", min_value=1, max_value=10, value=1)

    if st.button("Search and Analyze") and query:
        with st.spinner("Scraping PubMed and analyzing results..."):
            df = asyncio.run(scrape_pubmed([query], num_pages))
            
            if not df.empty:
                st.subheader("Search Results")
                st.dataframe(df)
                
                st.markdown(get_csv_download_link(df), unsafe_allow_html=True)
                
                analysis = analyze_with_openrouter(df, query, api_keys["openrouter"])
                if analysis:
                    st.subheader("Analysis")
                    st.write(analysis)
            else:
                st.error("No results found. Please try a different query.")

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

def display():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_page()
    else:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
        else:
            main_app()

if __name__ == "__main__":
    display()
