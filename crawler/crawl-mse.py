import os
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from datetime import datetime, timedelta
import pandas as pd
import time
from pathlib import Path
import xlrd
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log'),
        logging.StreamHandler()
    ]
)

class MutualFundCrawler:
    def __init__(self, download_dir):
        self.download_dir = download_dir
        self.setup_driver()
        self.first_load = True
        self.downloaded_files = set()  # Keep track of successfully downloaded files

    def setup_driver(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("prefs", {
            "download.default_directory": os.path.abspath(self.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            self.wait = WebDriverWait(self.driver, 20)
        except Exception as e:
            logging.error(f"Failed to initialize WebDriver: {str(e)}")
            raise

    def wait_for_element(self, by, value, timeout=20):
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            logging.error(f"Timeout waiting for element: {value}")
            return None

    def wait_for_clickable(self, by, value, timeout=20):
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            return element
        except TimeoutException:
            logging.error(f"Timeout waiting for clickable element: {value}")
            return None

    def wait_for_download_and_rename(self, target_filename, max_wait=10):
        start_time = time.time()
        while time.time() - start_time < max_wait:
            files = list(Path(self.download_dir).glob("*.xls"))
            logging.info(f"Found files in directory: {[f.name for f in files]}")

            for file in files:
                if "Open - End" in file.name or "Open-End" in file.name:
                    try:
                        target_path = os.path.join(self.download_dir, target_filename)
                        logging.info(f"Attempting to rename {file.name} to {target_filename}")
                        os.rename(file, target_path)
                        self.downloaded_files.add(target_filename)  # Add to tracking set
                        logging.info(f"Successfully renamed file to {target_filename}")
                        return True
                    except Exception as e:
                        logging.error(f"Error renaming file {file.name}: {str(e)}")
                        return False
            time.sleep(0.5)

        logging.error("No matching files found for rename operation")
        return False

    def download_monthly_data(self, start_date, end_date, iteration):
        url = "https://www.mse.mk/F/open-end-investment-funds"
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                if self.first_load:
                    logging.info(f"Accessing URL: {url}")
                    self.driver.get(url)
                    time.sleep(5)
                    self.first_load = False

                start_date_input = self.wait_for_element(By.ID, "FromDate")
                if not start_date_input:
                    raise TimeoutException("Could not find start date input")

                start_date_input.clear()
                formatted_start = start_date.strftime("%m/%d/%Y")
                start_date_input.send_keys(formatted_start)
                logging.info(f"Entered start date: {formatted_start}")

                end_date_input = self.wait_for_element(By.ID, "ToDate")
                if not end_date_input:
                    raise TimeoutException("Could not find end date input")

                end_date_input.clear()
                formatted_end = end_date.strftime("%m/%d/%Y")
                end_date_input.send_keys(formatted_end)
                logging.info(f"Entered end date: {formatted_end}")

                find_button = self.wait_for_element(By.XPATH, "//input[@value='Find']")
                if not find_button:
                    raise TimeoutException("Could not find 'Find' button")

                find_button.click()
                logging.info("Clicked Find button")

                time.sleep(2)

                export_link = self.wait_for_clickable(By.ID, "btnExport")
                if not export_link:
                    raise TimeoutException("Could not find export link")

                target_filename = f"mse-funds-data-{iteration}-{start_date.year}-{start_date.month:02d}.xls"

                self.driver.execute_script("arguments[0].click();", export_link)
                logging.info("Clicked Export link")

                time.sleep(2)

                if self.wait_for_download_and_rename(target_filename):
                    logging.info(f"File successfully renamed to: {target_filename}")
                    return True
                else:
                    raise Exception("Failed to download or rename file")

            except Exception as e:
                retry_count += 1
                logging.error(f"Attempt {retry_count} failed: {str(e)}")
                if retry_count >= max_retries:
                    logging.error(f"Failed after {max_retries} attempts for period {formatted_start} - {formatted_end}")
                    return False
                time.sleep(5)

        return False

    def process_downloads(self):
        all_data = []

        try:
            files = sorted(Path(self.download_dir).glob("mse-funds-data-*.xls"))
            logging.info(f"Found {len(list(files))} files to process")

            for file in files:
                try:
                    logging.info(f"Processing file: {file}")

                    # Read the file content
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Parse HTML content
                    soup = BeautifulSoup(content, 'html.parser')
                    table = soup.find('table')

                    if table:
                        df = pd.read_html(str(table))[0]

                        # Check if the dataframe is empty
                        if df.empty:
                            raise ValueError("Dataframe is empty")

                        all_data.append(df)
                        logging.info(f"Successfully processed file: {file}")
                    else:
                        raise ValueError("No table found in the HTML content")

                except Exception as e:
                    logging.error(f"Error processing file {file}: {str(e)}")

                    # Additional error information
                    with open(file, 'rb') as f:
                        file_start = f.read(50)  # Read first 50 bytes
                    logging.error(f"File starts with: {file_start}")
                    logging.error(f"File size: {os.path.getsize(file)} bytes")

            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)
                combined_df.drop_duplicates(inplace=True)
                return combined_df
            else:
                logging.error("No data was successfully processed")
                return None

        except Exception as e:
            logging.error(f"Error in process_downloads: {str(e)}")
        return None

    def close(self):
        try:
            self.driver.quit()
            logging.info("WebDriver closed successfully")
        except Exception as e:
            logging.error(f"Error closing WebDriver: {str(e)}")

def get_user_action():
    while True:
        action = input("Do you want to (1) crawl and process data or (2) just process downloaded data? Enter 1 or 2: ")
        if action in ['1', '2']:
            return action
        print("Invalid input. Please enter 1 or 2.")

def main():
    try:
        download_dir = os.path.join(os.getcwd(), "fund_data")
        os.makedirs(download_dir, exist_ok=True)
        logging.info(f"Created download directory: {download_dir}")

        action = get_user_action()

        crawler = MutualFundCrawler(download_dir)

        if action == '1':
            # Crawl and process data
            end_date = datetime.now()
            start_date = (end_date - timedelta(days=365*10)).replace(day=1)

            current_date = start_date
            iteration = 1

            while current_date < end_date:
                month_end = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                if month_end > end_date:
                    month_end = end_date

                logging.info(f"-------------------------------------------------------------------------------\n")
                logging.info(f"Processing month: {current_date.strftime('%B %Y')}")
                success = crawler.download_monthly_data(current_date, month_end, iteration)

                if not success:
                    logging.warning(f"Failed to download data for {current_date.strftime('%B %Y')}\n")
                else:
                    logging.info(f"Successfully processed {current_date.strftime('%B %Y')}\n")

                current_date = month_end + timedelta(days=1)
                iteration += 1

        # Process downloaded data (for both actions)
        combined_data = crawler.process_downloads()

        if combined_data is not None:
            output_file = "combined_mutual_fund_data.csv"
            combined_data.to_csv(output_file, index=False, sep='\t')
            logging.info(f"Combined data saved to {output_file}")
        else:
            logging.error("Failed to create combined dataset")

        crawler.close()

    except Exception as e:
        logging.error(f"Main process error: {str(e)}")

if __name__ == "__main__":
    main()