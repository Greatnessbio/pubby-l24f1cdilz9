import streamlit as st
import pandas as pd
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import random
from datetime import datetime, timedelta
import re
from aiolimiter import AsyncLimiter

# User agents list (abbreviated for brevity)
user_agents = [
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36"
]

# Set up rate limiter for Jina (20 requests per minute)
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
            'extra_keywords': extra_keywords,
            'jina_content': content
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
            # Fetch PubMed data
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
                    'extra_keywords': jina_info.get('extra_keywords', ''),
                    'jina_content': jina_info.get('jina_content', '')
                }

# The rest of your code (get_pmids, scrape_pubmed, main_app, login_page, main) remains the same...

if __name__ == "__main__":
    main()
