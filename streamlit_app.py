import streamlit as st
import pandas as pd
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import random
from datetime import datetime, timedelta

# User agents list (abbreviated for brevity)
user_agents = [
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36"
]

def load_users():
    return st.secrets["users"]

def login(username, password):
    users = load_users()
    if username in users and users[username] == password:
        return True
    return False

def make_header():
    return {'User-Agent': random.choice(user_agents)}

async def extract_by_article(url, semaphore):
    async with semaphore:
        async with aiohttp.ClientSession(headers=make_header()) as session:
            async with session.get(url) as response:
                data = await response.text()
                soup = BeautifulSoup(data, "lxml")
                
                title = soup.find('meta', {'name': 'citation_title'})
                title = title['content'].strip('[]') if title else 'NO_TITLE'
                
                abstract_div = soup.find('div', {'class': 'abstract-content selected'})
                abstract = ' '.join([p.text.strip() for p in abstract_div.find_all('p')]) if abstract_div else 'NO_ABSTRACT'
                
                authors_div = soup.find('div', {'class': 'authors-list'})
                authors = ', '.join([a.text for a in authors_div.find_all('a', {'class': 'full-name'})]) if authors_div else 'NO_AUTHOR'
                
                date = soup.find('time', {'class': 'citation-year'})
                date = date.text if date else 'NO_DATE'
                
                journal = soup.find('button', {'id': 'full-view-journal-trigger'})
                journal = journal.text.strip() if journal else 'NO_JOURNAL'
                
                doi = soup.find('span', {'class': 'citation-doi'})
                doi = doi.text.strip().replace('doi:', '') if doi else 'NO_DOI'

                return {
                    'url': url,
                    'title': title,
                    'authors': authors,
                    'abstract': abstract,
                    'date': date,
                    'journal': journal,
                    'doi': doi
                }

async def get_pmids(page, query, filters):
    base_url = 'https://pubmed.ncbi.nlm.nih.gov/'
    params = f'term={query}&{filters}&page={page}'
    url = f'{base_url}?{params}'
    
    async with aiohttp.ClientSession(headers=make_header()) as session:
        async with session.get(url) as response:
            data = await response.text()
            soup = BeautifulSoup(data, "lxml")
            pmids = soup.find('meta', {'name': 'log_displayeduids'})
            if pmids:
                return [f"{base_url}{pmid}" for pmid in pmids['content'].split(',')]
            return []

async def scrape_pubmed(query, filters, num_pages):
    semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
    all_urls = []
    for page in range(1, num_pages + 1):
        urls = await get_pmids(page, query, filters)
        all_urls.extend(urls)
    
    tasks = [extract_by_article(url, semaphore) for url in all_urls]
    results = await asyncio.gather(*tasks)
    return pd.DataFrame(results)

def main_app():
    st.title("Enhanced PubMed Search App")

    # Search parameters
    query = st.text_input("Enter your PubMed search query:", "")
    num_pages = st.number_input("Number of pages to scrape (1 page = 10 results)", min_value=1, max_value=100, value=1)

    # Advanced search options
    with st.expander("Advanced Search Options"):
        col1, col2 = st.columns(2)
        
        with col1:
            date_range = st.selectbox("Publication Date:", 
                                      ["Any Time", "Last Year", "Last 5 Years", "Last 10 Years", "Custom Range"])
            if date_range == "Custom Range":
                start_date = st.date_input("Start Date", datetime.now() - timedelta(days=365))
                end_date = st.date_input("End Date", datetime.now())
            
            article_type = st.multiselect("Article Type:", 
                                          ["Journal Article", "Clinical Trial", "Meta-Analysis", "Randomized Controlled Trial", "Review"])
        
        with col2:
            language = st.selectbox("Language:", ["Any", "English", "French", "German", "Spanish", "Chinese"])
            
            sort_by = st.selectbox("Sort Results By:", 
                                   ["Most Recent", "Best Match", "Most Cited", "Recently Added"])

    if st.button("Search PubMed") and query:
        # Construct filters
        filters = []
        
        if date_range != "Any Time":
            if date_range == "Last Year":
                filters.append("dates.1-year")
            elif date_range == "Last 5 Years":
                filters.append("dates.5-years")
            elif date_range == "Last 10 Years":
                filters.append("dates.10-years")
            elif date_range == "Custom Range":
                date_filter = f"custom_date_range={start_date.strftime('%Y/%m/%d')}-{end_date.strftime('%Y/%m/%d')}"
                filters.append(date_filter)
        
        if article_type:
            type_filters = [f"article_type.{t.lower().replace(' ', '-')}" for t in article_type]
            filters.extend(type_filters)
        
        if language != "Any":
            filters.append(f"language.{language.lower()}")
        
        if sort_by == "Most Recent":
            filters.append("sort=date")
        elif sort_by == "Best Match":
            filters.append("sort=relevance")
        elif sort_by == "Most Cited":
            filters.append("sort=citation")
        elif sort_by == "Recently Added":
            filters.append("sort=pubdate")

        filters_str = "&".join(filters)

        with st.spinner("Searching PubMed and retrieving results..."):
            df = asyncio.run(scrape_pubmed(query, filters_str, num_pages))
            
            if not df.empty:
                st.subheader("Search Results")
                st.dataframe(df)
                
                # Download options
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download results as CSV",
                    data=csv,
                    file_name="pubmed_results.csv",
                    mime="text/csv",
                )
                
                # Display some statistics
                st.subheader("Search Statistics")
                st.write(f"Total results found: {len(df)}")
                st.write(f"Most common journal: {df['journal'].mode().values[0]}")
                st.write(f"Date range: {df['date'].min()} to {df['date'].max()}")
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
