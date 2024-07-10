import streamlit as st
import pandas as pd
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import random
from datetime import datetime, timedelta
import re
from aiolimiter import AsyncLimiter

User agents list (abbreviated for brevity)
user_agents = [
"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1",
"Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0",
"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36"
]

Set up rate limiter for Jina (20 requests per minute)
jina_rate_limit = AsyncLimiter(20, 60)

def load_users():
return st.secrets["users"]

def login(username, password):
users = load_users()
if username in users and users[username] == password:
return True
return False

def make_header():
return {'User-Agent': random.choice(user_agents)}

async def fetch_jina_data(url, session):
jina_url = f'https://r.jina.ai/{url}'
async with jina_rate_limit:
try:
async with session.get(jina_url, headers={"Accept": "application/json"}) as response:
if response.status == 200:
return await response.json()
else:
print(f"Error fetching {url} from Jina: HTTP {response.status}")
return None
except Exception as e:
print(f"Error fetching {url} from Jina: {str(e)}")
return None

def parse_jina_content(jina_data):
if jina_data and 'data' in jina_data:
content = jina_data['data'].get('content', '')
jina_soup = BeautifulSoup(content, 'html.parser')

    extra_affiliations = extract_affiliations(jina_soup)
    extra_keywords = extract_keywords(jina_soup)
    
    return {
        'extra_affiliations': extra_affiliations,
        'extra_keywords': extra_keywords
    }
return {}
def extract_affiliations(soup):
affiliations = []
aff_elements = soup.find_all('div', class_='affiliations')
for aff in aff_elements:
affiliations.extend([li.text.strip() for li in aff.find_all('li')])
return affiliations

def extract_keywords(soup):
keywords_elem = soup.find('p', class_='keywords')
if keywords_elem:
return keywords_elem.text.replace('Keywords:', '').strip()
return ''

async def extract_by_article(url, semaphore):
async with semaphore:
async with aiohttp.ClientSession(headers=make_header()) as session:
async with session.get(url) as response:
data = await response.text()
soup = BeautifulSoup(data, "lxml")

            def get_text(element):
                return element.text.strip() if element else 'N/A'

            title = get_text(soup.find('h1', {'class': 'heading-title'}))
            
            abstract_div = soup.find('div', {'id': 'abstract'})
            
            # Initialize sections
            background = results = conclusion = keywords = abstract = 'N/A'
            
            if abstract_div:
                abstract_content = abstract_div.find('div', {'class': 'abstract-content selected'})
                if abstract_content:
                    abstract = ' '.join([p.text.strip() for p in abstract_content.find_all('p')])
                    
                    # Parse sections
                    for p in abstract_content.find_all('p'):
                        strong = p.find('strong', class_='sub-title')
                        if strong:
                            section_title = strong.text.strip().lower()
                            content = p.text.replace(strong.text, '').strip()
                            
                            if 'background' in section_title:
                                background = content
                            elif 'results' in section_title:
                                results = content
                            elif 'conclusion' in section_title:
                                conclusion = content
                
                # If structured abstract not found, use the whole abstract as background
                if background == 'N/A' and abstract != 'N/A':
                    background = abstract

            # Extract keywords
            keywords_p = soup.find('p', class_='keywords')
            if keywords_p:
                keywords = keywords_p.text.replace('Keywords:', '').strip()
            else:
                # Fallback: try to find keywords in the abstract
                keyword_match = re.search(r'Keywords?:?\s*(.*?)(?:\.|$)', abstract, re.IGNORECASE | re.DOTALL)
                if keyword_match:
                    keywords = keyword_match.group(1).strip()
            
            # Extract date
            date_elem = soup.find('span', {'class': 'cit'}) or soup.find('time', {'class': 'citation-year'})
            date = get_text(date_elem)
            
            # Extract journal
            journal_elem = soup.find('button', {'id': 'full-view-journal-trigger'}) or soup.find('span', {'class': 'journal-title'})
            journal = get_text(journal_elem)
            
            # Extract DOI
            doi_elem = soup.find('span', {'class': 'citation-doi'})
            doi = get_text(doi_elem).replace('doi:', '').strip()

            # Extract copyright information
            copyright_elem = soup.find('div', class_='copyright-section') or soup.find('p', class_='copyright')
            copyright_text = get_text(copyright_elem)

            # Extract affiliations
            affiliations = {}
            affiliations_div = soup.find('div', {'class': 'affiliations'})
            if affiliations_div:
                for li in affiliations_div.find_all('li'):
                    sup = li.find('sup')
                    if sup:
                        aff_num = sup.text.strip()
                        aff_text = li.text.replace(aff_num, '').strip()
                        affiliations[aff_num] = aff_text

            # Extract authors and match with affiliations
            authors_div = soup.find('div', {'class': 'authors-list'})
            author_affiliations = []
            if authors_div:
                for author in authors_div.find_all('span', {'class': 'authors-list-item'}):
                    name = author.find('a', {'class': 'full-name'})
                    if name:
                        author_name = name.text.strip()
                        author_aff_nums = [sup.text.strip() for sup in author.find_all('sup')]
                        author_affs = [affiliations.get(num, '') for num in author_aff_nums]
                        author_affiliations.append((author_name, '; '.join(author_affs)))

            # Extract PMID
            pmid_elem = soup.find('strong', string='PMID:')
            pmid = pmid_elem.next_sibling.strip() if pmid_elem else 'N/A'

            # Extract publication type
            pub_type_elem = soup.find('span', {'class': 'publication-type'})
            pub_type = get_text(pub_type_elem)

            # Extract MeSH terms
            mesh_terms = []
            mesh_div = soup.find('div', {'class': 'mesh-terms'})
            if mesh_div:
                mesh_terms = [term.text.strip() for term in mesh_div.find_all('li')]

            # Fetch Jina data
            jina_data = await fetch_jina_data(url, session)
            jina_info = parse_jina_content(jina_data)

            return {
                'url': url,
                'title': title,
                'authors': author_affiliations,
                'abstract': abstract,
                'background': background,
                'results': results,
                'conclusion': conclusion,
                'keywords': keywords,
                'date': date,
                'journal': journal,
                'doi': doi,
                'copyright': copyright_text,
                'pmid': pmid,
                'publication_type': pub_type,
                'mesh_terms': mesh_terms,
                'extra_affiliations': '; '.join(jina_info.get('extra_affiliations', [])),
                'extra_keywords': jina_info.get('extra_keywords', '')
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
def parse_author_info(authors):
parsed_authors = []
for index, (author, affiliation) in enumerate(authors):
name_parts = author.split()
if len(name_parts) > 1:
first_name = name_parts[0]
last_name = ' '.join(name_parts[1:])
else:
first_name = author
last_name = ''
email = re.search(r'[\w.-]+@[\w.-]+', affiliation)
email = email.group() if email else None
parsed_authors.append({
'first_name': first_name,
'last_name': last_name,
'affiliation': affiliation,
'email': email,
'order': index + 1
})
return parsed_authors

def main_app():
st.title("Improved PubMed Search App with Comprehensive Data Extraction (including Jina)")

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

    with st.spinner("Searching PubMed and retrieving results (including Jina data)..."):
        df = asyncio.run(scrape_pubmed(query, filters_str, num_pages))
        
        if not df.empty:
            # Store the results in session state
            st.session_state.pubmed_results = df
            
            st.subheader("Raw Search Results (including Jina data)")
            display_df = df.copy()
            display_df['authors'] = display_df['authors'].apply(lambda x: ', '.join([author[0] for author in x]))
            st.dataframe(display_df)
            
            # Parse author information and include abstract sections and Jina data
            all_authors = []
            for _, row in df.iterrows():
                authors = parse_author_info(row['authors'])
                for author in authors:
                    author.update({
                        'article_url': row['url'],
                        'article_title': row['title'],
                        'background': row['background'],
                        'results': row['results'],
                        'conclusion': row['conclusion'],
                        'keywords': row['keywords'],
                        'journal': row['journal'],
                        'date': row['date'],
                        'doi': row['doi'],
                        'pmid': row['pmid'],
                        'publication_type': row['publication_type'],
                        'mesh_terms': ', '.join(row['mesh_terms']),
                        'abstract': row['abstract'],
                        'copyright': row['copyright'],
                        'extra_affiliations': row['extra_affiliations'],
                        'extra_keywords': row['extra_keywords']
                    })
                all_authors.extend(authors)
            
            author_df = pd.DataFrame(all_authors)
            
            # Store the parsed author data in session state
            st.session_state.parsed_author_data = author_df
            
            st.subheader("Parsed Data with All Data Points (including Jina)")
            st.dataframe(author_df)
            
            # Combine results for CSV download
            csv = author_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download comprehensive results as CSV (including Jina data)",
                data=csv,
                file_name="pubmed_comprehensive_results_with_jina.csv",
                mime="text/csv",
            )
            
            # Display basic statistics
            st.subheader("Search Statistics")
            st.write(f"Total articles found: {len(df)}")
            st.write(f"Total authors: {len(author_df)}")
            st.write(f"Unique journals: {df['journal'].nunique()}")
            st.write(f"Date range: {df['date'].min()} to {df['date'].max()}")
            
        else:
            st.error("No results found. Please try a different query or increase the number of pages.")

# Add a section for potential AI model application
if 'pubmed_results' in st.session_state:
    st.subheader("Apply AI Models")
    st.write("You can now apply AI models to the scraped data.")
    # Add your AI model application code here
    # For example:
    # if st.button("Apply AI Model"):
    #     results = apply_ai_model(st.session_state.parsed_author_data)
    #     st.write(results)
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
if name == "main":
main()
