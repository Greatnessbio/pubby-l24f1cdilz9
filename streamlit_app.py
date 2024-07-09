def main_app():
    st.title("PubMed Search App with Structured Author Information")

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
                st.session_state.pubmed_results = df
                
                st.subheader("Search Results")
                st.dataframe(df.drop('authors', axis=1))
                
                # Parse author information
                all_authors = []
                for _, row in df.iterrows():
                    authors = parse_author_info(row['authors'])
                    for author in authors:
                        author['article_url'] = row['url']
                        author['article_title'] = row['title']
                    all_authors.extend(authors)
                
                author_df = pd.DataFrame(all_authors)
                
                st.subheader("Structured Author Information")
                st.dataframe(author_df)
                
                # Combine results for CSV download
                combined_df = author_df.merge(df.drop(['authors', 'title'], axis=1), on='article_url')
                csv = combined_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download combined results as CSV",
                    data=csv,
                    file_name="pubmed_results_with_author_info.csv",
                    mime="text/csv",
                )
                
                # Display some statistics
                st.subheader("Search Statistics")
                st.write(f"Total results found: {len(df)}")
                st.write(f"Total authors: {len(author_df)}")
                st.write(f"Most common journal: {df['journal'].mode().values[0]}")
                st.write(f"Date range: {df['date'].min()} to {df['date'].max()}")
            else:
                st.error("No results found. Please try a different query or increase the number of pages.")
