import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=chrome_options)

driver.get('https://www.nanumticket.or.kr/pe/detail.html?p_marking=4&p_new=&start2=36&page_no2=4&p_idx=12911')

while True:
    try:
        if driver.find_element(By.XPATH, '//*[@id="tab_area"]/a').text != '매진':
            logging.info('매진이 아닙니다. 예매 가능!')
            break
        else:
            time.sleep(5)
            driver.refresh()
    except Exception as e:
        logging.error(f"에러 발생: {e}")
        break