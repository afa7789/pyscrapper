from scraper import MarketRoxoScraper

def log_message(message):
    """Simple callback function to print log messages"""
    print(f"[LOG] {message}")

def main():
    # Initialize the scraper with our logging function
    scraper = MarketRoxoScraper(log_callback=log_message)
    
    # Define search keywords
    keywords = ["bicicleta spinning","spinning","bike spinning","bicicleta indoor"]
    
    filename = "trechos_html/debug_page_1.html"  # Local HTML file to test

    # Execute the scraping
    results = scraper._extract_ads_tested(filename, keywords)
    
    # Display results
    print("\nSearch Results:")
    print(f"Found {len(results)} matching ads:")
    
    for i, ad in enumerate(results, 1):
        print(f"\n{i}. {ad['title']}")
        print(f"   URL: {ad['url']}")

    # results_non_extracted = scraper._non_extracted_ads_tested(filename, keywords)
    # print("\nNon-matching Ads:")
    # print(f"Found {len(results_non_extracted)} non-matching ads:")
    # for i, ad in enumerate(results_non_extracted, 1):
    #     print(f"\n{i}. {ad['title']}")
    #     print(f"   URL: {ad['url']}")
    
    # Test the extract_ads_tested method with a local file (optional)
    # If you have a saved HTML file, uncomment the following lines:
    # print("\nTesting with saved HTML file:")
    # test_results = scraper._extract_ads_tested("debug_page_1.html", keywords)
    # print(f"Found {len(test_results)} ads in test file")

if __name__ == "__main__":
    main()

