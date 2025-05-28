#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
나눔티켓 모니터링 봇 (Render Web Service용)
5분마다 새로운 티켓을 확인하고 디스코드로 알림을 보냅니다.
"""

import requests
from bs4 import BeautifulSoup
import json
import hashlib
from datetime import datetime
import logging
import os
import time
import threading
from flask import Flask

# 환경변수에서 디스코드 웹훅 URL 가져오기
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')

# Flask 앱 생성 (Render가 포트를 감지할 수 있도록)
app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>나눔티켓 모니터링 봇</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .status { color: #00aa00; font-weight: bold; }
            .info { background: #f0f0f0; padding: 10px; border-radius: 5px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>🎫 나눔티켓 모니터링 봇</h1>
        <p class="status">현재 상태: 활성 중 ✅</p>
        <div class="info">
            <p><strong>📍 모니터링 URL:</strong> 나눔티켓 신규 티켓</p>
            <p><strong>⏰ 체크 간격:</strong> 5분마다</p>
            <p><strong>📱 알림 방식:</strong> 디스코드 웹훅</p>
        </div>
        <p><strong>마지막 확인:</strong> <span id="time"></span></p>
        <script>
            document.getElementById('time').textContent = new Date().toLocaleString('ko-KR');
            setTimeout(() => location.reload(), 60000); // 1분마다 새로고침
        </script>
    </body>
    </html>
    '''

@app.route('/status')
def status():
    return {
        "status": "running",
        "service": "나눔티켓 모니터링",
        "last_check": datetime.now().isoformat(),
        "discord_configured": bool(DISCORD_WEBHOOK_URL)
    }

class TicketMonitor:
    def __init__(self):
        self.url = "https://www.nanumticket.or.kr/pe/list.html?p_new=1"
        self.previous_hashes = set()
        self.data_file = "/tmp/ticket_data.json"
        
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("🎨 나눔티켓 모니터링 시작 (Render)")
        self.load_previous_data()
    
    def load_previous_data(self):
        """이전 데이터 로드"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.previous_hashes = set(data.get('hashes', []))
                    self.logger.info(f"📂 이전 데이터 로드: {len(self.previous_hashes)}개")
            else:
                self.logger.info("🆕 첫 실행 - 초기 데이터 수집 중...")
        except Exception as e:
            self.logger.error(f"데이터 로드 실패: {e}")
    
    def save_current_data(self, current_hashes):
        """현재 데이터 저장"""
        try:
            data = {
                'hashes': list(current_hashes),
                'last_update': datetime.now().isoformat()
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"데이터 저장 실패: {e}")
    
    def send_discord_notification(self, ticket):
        """디스코드로 알림을 보냅니다."""
        if not DISCORD_WEBHOOK_URL:
            self.logger.error("❌ DISCORD_WEBHOOK_URL 환경변수가 설정되지 않았습니다!")
            return False
        
        try:
            embed = {
                "title": "🎫 새로운 나눔티켓 발견!",
                "description": ticket['title'],
                "url": ticket['link'],
                "color": 0x00ff00,
                "fields": [],
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": "나눔티켓 모니터 (Render) 🎨"}
            }
            
            if ticket['date']:
                embed["fields"].append({
                    "name": "📅 날짜", 
                    "value": ticket['date'], 
                    "inline": True
                })
            if ticket['location']:
                embed["fields"].append({
                    "name": "📍 장소", 
                    "value": ticket['location'], 
                    "inline": True
                })
            if ticket['tags']:
                embed["fields"].append({
                    "name": "🏷️ 태그", 
                    "value": ticket['tags'], 
                    "inline": True
                })
            
            data = {"embeds": [embed]}
            
            response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=15)
            if response.status_code == 204:
                self.logger.info("✅ 디스코드 알림 전송 성공")
                return True
            else:
                self.logger.error(f"❌ 디스코드 알림 실패: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"디스코드 알림 오류: {e}")
            return False
    
    def get_page_content(self):
        """웹페이지 내용을 가져옵니다."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"페이지 로드 실패: {e}")
            return None
    
    def parse_tickets(self, html_content):
        """HTML에서 티켓 정보를 파싱합니다."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            tickets = []
            
            ticket_list = soup.find('ul', class_='ticket_list')
            if not ticket_list:
                self.logger.warning("ticket_list를 찾을 수 없습니다")
                return []
            
            for li in ticket_list.find_all('li'):
                try:
                    h4 = li.find('h4')
                    if not h4:
                        continue
                    
                    link_elem = h4.find_parent('a')
                    if not link_elem:
                        continue
                    
                    title = h4.get_text(strip=True)
                    href = link_elem.get('href', '')
                    
                    if href.startswith('/'):
                        full_link = 'https://www.nanumticket.or.kr' + href
                    else:
                        full_link = href
                    
                    # 날짜 추출
                    date_text = ""
                    clock_icon = li.find('i', class_='fa-solid fa-clock')
                    if clock_icon:
                        date_p = clock_icon.find_parent('p')
                        if date_p:
                            date_text = date_p.get_text(strip=True)
                    
                    # 장소 추출
                    location_text = ""
                    location_icon = li.find('i', class_='fa-solid fa-location-dot')
                    if location_icon:
                        location_p = location_icon.find_parent('p')
                        if location_p:
                            location_text = location_p.get_text(strip=True)
                    
                    # 태그 추출
                    tags = []
                    for span in li.find_all('span', class_=['blue', 'gray', 'orange']):
                        tag_text = span.get_text(strip=True)
                        if tag_text:
                            tags.append(tag_text)
                    
                    if title and len(title) > 5:
                        tickets.append({
                            'title': title,
                            'link': full_link,
                            'date': date_text,
                            'location': location_text,
                            'tags': ', '.join(tags),
                            'hash': hashlib.md5(f"{title}{full_link}".encode()).hexdigest()
                        })
                
                except Exception as e:
                    continue
            
            return tickets
            
        except Exception as e:
            self.logger.error(f"파싱 실패: {e}")
            return []
    
    def check_tickets(self):
        """티켓을 체크하고 새로운 것이 있으면 알림"""
        self.logger.info("🔍 티켓 체크 중...")
        
        html_content = self.get_page_content()
        if not html_content:
            return
        
        tickets = self.parse_tickets(html_content)
        if not tickets:
            self.logger.warning("티켓을 찾을 수 없습니다")
            return
        
        current_hashes = {ticket['hash'] for ticket in tickets}
        
        # 첫 실행시에는 알림 안 보내고 데이터만 저장
        if not self.previous_hashes:
            self.logger.info(f"📋 초기 로드: {len(tickets)}개 티켓 저장 (알림 X)")
            self.previous_hashes = current_hashes
            self.save_current_data(current_hashes)
            return
        
        # 새로운 티켓 찾기
        new_hashes = current_hashes - self.previous_hashes
        
        if new_hashes:
            self.logger.info(f"🎉 새로운 티켓 {len(new_hashes)}개 발견!")
            
            new_tickets_sent = 0
            for ticket in tickets:
                if ticket['hash'] in new_hashes:
                    self.logger.info(f"🎫 새 티켓: {ticket['title']}")
                    if self.send_discord_notification(ticket):
                        new_tickets_sent += 1
                        time.sleep(1)  # 디스코드 API 제한 방지
            
            self.logger.info(f"📤 총 {new_tickets_sent}개 알림 전송 완료")
        else:
            self.logger.info("새로운 티켓 없음")
        
        # 현재 상태 저장
        self.previous_hashes = current_hashes
        self.save_current_data(current_hashes)
    
    def run_forever(self):
        """무한 루프로 5분마다 체크"""
        while True:
            try:
                self.check_tickets()
                self.logger.info("😴 5분 대기 중...")
                time.sleep(300)  # 5분 = 300초
                
            except KeyboardInterrupt:
                self.logger.info("👋 프로그램 종료")
                break
            except Exception as e:
                self.logger.error(f"❌ 예외 발생: {e}")
                self.logger.info("⏰ 30초 후 재시도...")
                time.sleep(30)

def run_monitor():
    """백그라운드에서 모니터링 실행"""
    if not DISCORD_WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL 환경변수를 설정해주세요!")
        return
    
    monitor = TicketMonitor()
    monitor.run_forever()

if __name__ == "__main__":
    # 백그라운드 스레드로 모니터링 시작
    monitor_thread = threading.Thread(target=run_monitor, daemon=True)
    monitor_thread.start()
    
    # Flask 웹 서버 시작 (Render가 포트를 감지할 수 있도록)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)