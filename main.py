import os
import requests
from bs4 import BeautifulSoup
import zipfile
import tqdm
import re
import time
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory setup
os.makedirs('./plugins', exist_ok=True)
os.makedirs('./unzipped-plugins', exist_ok=True)


def get_with_retry(url, max_retries=5):
    retries = 0
    while retries < max_retries:
        response = requests.get(url)
        if response.status_code == 200:
            return response
        elif response.status_code == 429:
            wait_time = (2 ** retries) * 5  # Exponential backoff
            logging.warning(f"429 Too Many Requests for URL {url}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            retries += 1
        else:
            response.raise_for_status()
    raise requests.exceptions.RequestException(f"Failed to fetch URL {url} after {max_retries} retries")


def get_plugin_urls(page):
    url = f"https://wordpress.org/plugins/page/{page}/?plugin_business_model=community"
    logging.debug(f"Fetching URL: {url}")
    response = get_with_retry(url)

    soup = BeautifulSoup(response.text, 'html.parser')
    plugin_urls = [a['href'] for h3 in soup.find_all('h3', class_='entry-title')
                   for a in h3.find_all('a', href=True)
                   if a['href'].startswith("https://wordpress.org/plugins/")]
    logging.debug(f"Found {len(plugin_urls)} plugin URLs on page {page}")
    return plugin_urls


def get_download_url(plugin_url):
    logging.debug(f"Fetching plugin page URL: {plugin_url}")
    response = get_with_retry(plugin_url)

    match = re.search(r'https://downloads\.wordpress\.org/plugin/[^"]+\.zip', response.text)
    if match:
        download_url = match.group(0)
        logging.debug(f"Found download URL: {download_url}")
        return download_url
    else:
        logging.warning(f"No download URL found on plugin page {plugin_url}")
    return None


def download_plugin(download_url):
    local_filename = download_url.split('/')[-1]
    local_path = os.path.join('./plugins', local_filename)
    logging.debug(f"Downloading plugin from {download_url} to {local_path}")
    response = get_with_retry(download_url)

    with open(local_path, 'wb') as f:
        f.write(response.content)
    logging.debug(f"Downloaded plugin to {local_path}")
    return local_filename


def unzip_plugin(filename):
    local_path = os.path.join('./plugins', filename)
    unzip_dir = os.path.join('./unzipped-plugins', filename.replace('.zip', ''))
    os.makedirs(unzip_dir, exist_ok=True)
    logging.debug(f"Unzipping {local_path} to {unzip_dir}")
    with zipfile.ZipFile(local_path, 'r') as zip_ref:
        zip_ref.extractall(unzip_dir)
    logging.debug(f"Unzipped plugin to {unzip_dir}")


if __name__ == "__main__":
    logging.info("Processing pages...")
    for page in tqdm.tqdm(range(1, 100), desc="Pages"):
        try:
            plugin_urls = get_plugin_urls(page)
            if not plugin_urls:
                continue

            for plugin_url in plugin_urls:
                try:
                    download_url = get_download_url(plugin_url)
                    if download_url:
                        filename = download_plugin(download_url)
                        if filename:
                            unzip_plugin(filename)
                except Exception as e:
                    logging.error(f"Error processing {plugin_url}: {e}")
                time.sleep(1) 
        except Exception as e:
            logging.error(f"Error on page {page}: {e}")
        time.sleep(2) 
    logging.info("All tasks completed.")
