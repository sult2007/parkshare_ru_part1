import os,sys 
sys.path.insert(0,r'c:\Users\Sultan\Downloads\parkshare_ru_part1') 
os.environ.setdefault('DJANGO_SETTINGS_MODULE','backend.backend.settings.local') 
import django;django.setup() 
from parking.models import ParkingSpot 
print(ParkingSpot.objects.count()) 
