
import logging
from src.crawler import NuriCrawler
from src.storage import Storage

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger("Main")
    logger.info("Starting Nuri G2B Crawler")
    
    crawler = NuriCrawler()
    try:
        crawler.run()
    except Exception as e:
        logger.error(f"Crawler failed: {e}", exc_info=True)
    finally:
        logger.info(f"Crawling finished. Collected {len(crawler.results)} items.")
        Storage.save_csv(crawler.results, "data/results.csv")
        Storage.save_json(crawler.results, "data/results.json")

if __name__ == "__main__":
    main()
