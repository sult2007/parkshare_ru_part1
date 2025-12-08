import os,sys
sys.path.insert(0,r'c:\Users\Sultan\Downloads\parkshare_ru_part1') 
os.environ.setdefault('DJANGO_SETTINGS_MODULE','backend.backend.settings.local') 
import django;django.setup() 
from ai.chat.parking_assistant import generate_chat_reply 
reply=generate_chat_reply('Kurskaya parking 9-11 300 rub ev', [], None) 
print(repr(reply)) 
