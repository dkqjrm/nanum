#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
나눔티켓 모니터링 프로그램
5분마다 새로운 티켓 정보를 확인하고 알림을 보냅니다.
핸드폰 알림 지원: 텔레그램, 디스코드, 이메일
"""

import requests
from bs4 import BeautifulSoup
import time
import json
import hashlib
from datetime import datetime
import logging
from plyer import notification  # 데스크톱 알림용
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class TicketMonitor:
    def __init__(self, url, check_interval=300):  # 300초 = 5분
        self.url = url
        self.check_interval = check_interval
        self.previous_items = set()
        self.data_file = "ticket_data.json"
        self.config_file = "notification_config.json"
        
        # 로깅 설정 (먼저 초기화)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('ticket_monitor.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # 알림 설정 로드 (logger 초기화 후)
        self.notification_config = self.load_notification_config()
        
        # 기존 데이터 로드
        self.load_previous_data()
    
    def load_notification_config(self):
        """알림 설정을 로드합니다."""
        default_config = {
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_id": ""
            },
            "discord": {
                "enabled": False,
                "webhook_url": ""
            },
            "email": {
                "enabled": False,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "sender_email": "",
                "sender_password": "",
                "receiver_email": ""
            },
            "desktop": {
                "enabled": True
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 기본 설정과 병합
                    for key in default_config:
                        if key not in config:
                            config[key] = default_config[key]
                    return config
            else:
                # 설정 파일 생성
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                self.logger.info(f"설정 파일 '{self.config_file}'을 생성했습니다. 알림 설정을 편집해주세요.")
                return default_config
        except Exception as e:
            self.logger.error(f"설정 로드 실패: {e}")
            return default_config
    
    def send_telegram_notification(self, ticket):
        """텔레그램으로 알림을 보냅니다."""
        try:
            config = self.notification_config.get("telegram", {})
            if not config.get("enabled") or not config.get("bot_token") or not config.get("chat_id"):
                return
            
            bot_token = config["bot_token"]
            chat_id = config["chat_id"]
            
            # 마크다운 특수문자 이스케이프 처리
            def escape_markdown(text):
                chars_to_escape = ['*', '_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                for char in chars_to_escape:
                    text = text.replace(char, f'\\{char}')
                return text
            
            title_escaped = escape_markdown(ticket['title'])
            
            message = "🎫 *새로운 나눔티켓 발견\\!*\n\n"
            message += f"*제목:* {title_escaped}\n"
            
            if ticket['date']:
                message += f"*날짜:* {escape_markdown(ticket['date'])}\n"
            if ticket['location']:
                message += f"*장소:* {escape_markdown(ticket['location'])}\n"
            if ticket['tags']:
                message += f"*태그:* {escape_markdown(ticket['tags'])}\n"
            
            message += f"\n[자세히 보기]({ticket['link']})"
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": False
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                self.logger.info("텔레그램 알림 전송 성공")
            else:
                self.logger.error(f"텔레그램 알림 전송 실패: {response.text}")
                
        except Exception as e:
            self.logger.error(f"텔레그램 알림 전송 실패: {e}")
    
    def send_discord_notification(self, ticket):
        """디스코드로 알림을 보냅니다."""
        try:
            config = self.notification_config.get("discord", {})
            if not config.get("enabled") or not config.get("webhook_url"):
                return
            
            webhook_url = config["webhook_url"]
            
            embed = {
                "title": "🎫 새로운 나눔티켓 발견!",
                "description": ticket['title'],
                "url": ticket['link'],
                "color": 0x00ff00,  # 초록색
                "fields": [],
                "timestamp": datetime.now().isoformat()
            }
            
            if ticket['date']:
                embed["fields"].append({"name": "날짜", "value": ticket['date'], "inline": True})
            if ticket['location']:
                embed["fields"].append({"name": "장소", "value": ticket['location'], "inline": True})
            if ticket['tags']:
                embed["fields"].append({"name": "태그", "value": ticket['tags'], "inline": True})
            
            data = {"embeds": [embed]}
            
            response = requests.post(webhook_url, json=data, timeout=10)
            if response.status_code == 204:
                self.logger.info("디스코드 알림 전송 성공")
            else:
                self.logger.error(f"디스코드 알림 전송 실패: {response.text}")
                
        except Exception as e:
            self.logger.error(f"디스코드 알림 전송 실패: {e}")
    
    def send_email_notification(self, ticket):
        """이메일로 알림을 보냅니다."""
        try:
            config = self.notification_config.get("email", {})
            if not config.get("enabled"):
                return
            
            sender_email = config["sender_email"]
            sender_password = config["sender_password"]
            receiver_email = config["receiver_email"]
            
            if not all([sender_email, sender_password, receiver_email]):
                return
            
            # 이메일 구성
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = receiver_email
            msg['Subject'] = f"🎫 새로운 나눔티켓: {ticket['title']}"
            
            body = f"""
새로운 나눔티켓이 등록되었습니다!

제목: {ticket['title']}
날짜: {ticket['date']}
장소: {ticket['location']}
태그: {ticket['tags']}

자세한 정보: {ticket['link']}

- 나눔티켓 모니터링 봇
            """
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Gmail SMTP로 전송
            server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, receiver_email, text)
            server.quit()
            
            self.logger.info("이메일 알림 전송 성공")
            
        except Exception as e:
            self.logger.error(f"이메일 알림 전송 실패: {e}")
    
    def send_desktop_notification(self, ticket):
        """데스크톱 알림을 보냅니다."""
        try:
            config = self.notification_config.get("desktop", {})
            if not config.get("enabled", True):
                return
            
            title = "🎫 새로운 나눔티켓 발견!"
            
            # 데스크톱 알림 (짧게)
            notification.notify(
                title=title,
                message=ticket['title'][:100],  # 너무 길면 잘림
                timeout=10
            )
            
        except Exception as e:
            self.logger.error(f"데스크톱 알림 전송 실패: {e}")
    
    def get_page_content(self):
        """웹페이지 내용을 가져옵니다."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            self.logger.error(f"페이지 로드 실패: {e}")
            return None
    
    def parse_tickets(self, html_content):
        """HTML에서 티켓 정보를 파싱합니다."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            tickets = []
            
            # 실제 티켓 목록만 선택: ul.ticket_list > li
            ticket_list = soup.find('ul', class_='ticket_list')
            
            if not ticket_list:
                self.logger.warning("ticket_list 클래스를 찾을 수 없습니다.")
                return []
            
            ticket_items = ticket_list.find_all('li')
            self.logger.info(f"찾은 티켓 항목 수: {len(ticket_items)}")
            
            for li_element in ticket_items:
                try:
                    # 티켓 제목과 링크 추출 (h4 태그에서)
                    title_element = li_element.find('h4')
                    if not title_element:
                        continue
                        
                    # h4의 부모 a 태그에서 링크 가져오기
                    link_element = title_element.find_parent('a')
                    if not link_element:
                        continue
                    
                    title = title_element.get_text(strip=True)
                    href = link_element.get('href', '')
                    
                    # 상대 URL을 절대 URL로 변환
                    if href.startswith('/'):
                        full_link = 'https://www.nanumticket.or.kr' + href
                    elif href.startswith('http'):
                        full_link = href
                    else:
                        full_link = href
                    
                    # 날짜 정보 추출 (시계 아이콘 다음 p 태그)
                    date_text = ""
                    date_p = li_element.find('p', string=lambda text: text and 'fa-clock' in str(text))
                    if not date_p:
                        # 아이콘을 포함한 p 태그 찾기
                        clock_icon = li_element.find('i', class_='fa-solid fa-clock')
                        if clock_icon:
                            date_p = clock_icon.find_parent('p')
                    
                    if date_p:
                        date_text = date_p.get_text(strip=True)
                        # 아이콘 텍스트 제거
                        date_text = date_text.replace('', '').strip()
                    
                    # 장소 정보 추출 (위치 아이콘 다음 p 태그)
                    location_text = ""
                    location_icon = li_element.find('i', class_='fa-solid fa-location-dot')
                    if location_icon:
                        location_p = location_icon.find_parent('p')
                        if location_p:
                            location_text = location_p.get_text(strip=True)
                    
                    # 태그 정보 추출 (할인/무료 등)
                    tag_info = []
                    tag_elements = li_element.find_all('span', class_=['blue', 'gray', 'orange'])
                    for tag in tag_elements:
                        tag_text = tag.get_text(strip=True)
                        if tag_text:
                            tag_info.append(tag_text)
                    
                    if title and len(title) > 5:  # 실제 공연/전시 제목만
                        ticket = {
                            'title': title,
                            'link': full_link,
                            'date': date_text,
                            'location': location_text,
                            'tags': ', '.join(tag_info),
                            'hash': hashlib.md5(f"{title}{full_link}".encode()).hexdigest()
                        }
                        tickets.append(ticket)
                        
                        # 디버깅용 로그
                        self.logger.debug(f"티켓 파싱: {title[:50]}... | 날짜: {date_text}")
                
                except Exception as e:
                    self.logger.warning(f"개별 티켓 파싱 실패: {e}")
                    continue
            
            return tickets
            
        except Exception as e:
            self.logger.error(f"파싱 실패: {e}")
            return []
    
    def load_previous_data(self):
        """이전 데이터를 로드합니다."""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.previous_items = set(data.get('items', []))
                    self.logger.info(f"이전 데이터 로드: {len(self.previous_items)}개 항목")
        except Exception as e:
            self.logger.error(f"데이터 로드 실패: {e}")
    
    def save_current_data(self, current_items):
        """현재 데이터를 저장합니다."""
        try:
            data = {
                'items': list(current_items),
                'last_update': datetime.now().isoformat()
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"데이터 저장 실패: {e}")
    
    def send_notification(self, ticket):
        """모든 활성화된 채널로 알림을 보냅니다."""
        try:
            # 콘솔 출력 (항상 표시)
            print(f"\n🎫 새로운 티켓 발견!")
            print(f"제목: {ticket['title']}")
            if ticket['date']:
                print(f"날짜: {ticket['date']}")
            if ticket['location']:
                print(f"장소: {ticket['location']}")
            if ticket['tags']:
                print(f"태그: {ticket['tags']}")
            print(f"링크: {ticket['link']}")
            print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("-" * 80)
            
            # 각 알림 채널로 전송
            self.send_telegram_notification(ticket)
            self.send_discord_notification(ticket)
            self.send_email_notification(ticket)
            self.send_desktop_notification(ticket)
            
        except Exception as e:
            self.logger.error(f"알림 전송 실패: {e}")
    
    def check_for_updates(self):
        """업데이트를 확인합니다."""
        self.logger.info("티켓 정보 확인 중...")
        
        html_content = self.get_page_content()
        if not html_content:
            return
        
        current_tickets = self.parse_tickets(html_content)
        if not current_tickets:
            self.logger.warning("티켓 정보를 찾을 수 없습니다.")
            return
        
        current_hashes = {ticket['hash'] for ticket in current_tickets}
        
        # 새로운 항목 찾기
        new_items = current_hashes - self.previous_items
        
        if new_items:
            self.logger.info(f"새로운 티켓 {len(new_items)}개 발견!")
            
            # 새로운 티켓들에 대해 알림 보내기
            for ticket in current_tickets:
                if ticket['hash'] in new_items:
                    self.send_notification(ticket)
        else:
            self.logger.info("새로운 티켓이 없습니다.")
        
        # 현재 상태 저장
        self.previous_items = current_hashes
        self.save_current_data(current_hashes)
    
    def run(self):
        """모니터링을 시작합니다."""
        self.logger.info(f"티켓 모니터링 시작 - {self.check_interval}초마다 확인")
        self.logger.info(f"대상 URL: {self.url}")
        
        try:
            while True:
                self.check_for_updates()
                self.logger.info(f"다음 확인까지 {self.check_interval}초 대기...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            self.logger.info("모니터링이 중단되었습니다.")
        except Exception as e:
            self.logger.error(f"예상치 못한 오류: {e}")

def main():
    """메인 함수"""
    url = "https://www.nanumticket.or.kr/pe/list.html?p_new=1"
    check_interval = 300  # 5분 (300초)
    
    monitor = TicketMonitor(url, check_interval)
    monitor.run()

if __name__ == "__main__":
    # 필요한 패키지 설치 안내
    try:
        import requests
        from bs4 import BeautifulSoup
        from plyer import notification
    except ImportError:
        print("필요한 패키지를 설치해주세요:")
        print("pip install requests beautifulsoup4 plyer")
        exit(1)
    
main()