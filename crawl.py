import os
from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# 크롬 드라이버
driver = webdriver.Chrome()

driver.get('https://www.nanumticket.or.kr/pe/detail.html?p_marking=4&p_new=&start2=36&page_no2=4&p_idx=12911')
while True:
    # //*[@id="tab_area"]/a의 text가 '매진' 이 아니라면 
    if driver.find_element(By.XPATH, '//*[@id="tab_area"]/a').text != '매진':
        os.system('afplay /System/Library/Sounds/Ping.aiff')
        print('매진이 아닙니다.')
        break
    else:
        time.sleep(5)
        driver.refresh()