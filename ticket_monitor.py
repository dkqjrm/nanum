#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
import hashlib
from datetime import datetime
import logging
import os

# 환경변수에서 디스코드 웹훅 URL 가져오기
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')

class TicketMonitor:
    def __init__(self):
        self.url = "https://www.nanumticket.or.kr/pe/list.html?p_new=1"
        self.previous_items = set()
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 이전 데이터는 메모리에만 저장 (Railway는 파일 시스템이 휘발성)
        self.logger.info("🚀 Railway에서 실행 중...")
    
    def send_discord_notification(self, ticket):
        """디스코드로 알림을 보냅니다."""
        if not DISCORD_WEBHOOK_URL:
            self.logger.error("❌ DISCORD_WEBHOOK_URL 환경변수가 설정되지 않았습니다!")
            return
        
        try:
            embed = {
                "title": "🎫 새로운 나눔티켓 발견!",
                "description": ticket['title'],
                "url": ticket['link'],
                "color": 0x00ff00,
                "fields": [],
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": "나눔티켓 모니터 (Railway)"}
            }
            
            if ticket['date']:
                embed["fields"].append({"name": "📅 날짜", "value": ticket['date'], "inline": True})
            if ticket['location']:
                embed["fields"].append({"name": "📍 장소", "value": ticket['location'], "inline": True})
            if ticket['tags']:
                embed["fields"].append({"name": "🏷️ 태그", "value": ticket['tags'], "inline": True})
            
            data = {"embeds": [embed]}
            
            response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
            if response.status_code == 204:
                self.logger.info("✅ 디스코드 알림 전송 성공")
            else:
                self.logger.error(f"❌ 디스코드 알림 실패: {response.text}")
                
        except Exception as e:
            self.logger.error(f"디스코드 알림 오류: {e}")
    
    def get_page_content(self):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"페이지 로드 실패: {e}")
            return None
    
    def parse_tickets(self, html_content):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            tickets = []
            
            ticket_list = soup.find('ul', class_='ticket_list')
            if not ticket_list:
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
    
    def run_once(self):
        """한 번만 체크하고 종료"""
        self.logger.info("🔍 티켓 체크 시작...")
        
        html_content = self.get_page_content()
        if not html_content:
            return
        
        tickets = self.parse_tickets(html_content)
        self.logger.info(f"📋 총 {len(tickets)}개 티켓 발견")
        
        # Railway에서는 매번 새로 시작하므로 모든 티켓을 새 것으로 간주
        # 실제로는 Redis나 외부 DB를 써야 하지만, 일단 최신 3개만 알림
        recent_tickets = tickets[:3]  # 최신 3개만
        
        for ticket in recent_tickets:
            self.logger.info(f"🎫 알림 전송: {ticket['title']}")
            self.send_discord_notification(ticket)
        
        self.logger.info("✅ 완료!")

if __name__ == "__main__":
    monitor = TicketMonitor()
    monitor.run_once()