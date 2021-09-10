import pymongo
import os

from dotenv import load_dotenv
load_dotenv()

mongo_uri = os.getenv('MONGODB_URI')
mongo_conn_str = f"mongodb+srv://{mongo_uri}/myFirstDatabase?retryWrites=true&w=majority"
client = pymongo.MongoClient(mongo_conn_str)
db_quotes = client['quotes']
collections_images = db_quotes['image']


lao_ping_obj = {
    "name" : "lao_ping",
    "x" : 500,
    "y" : 100,
    "width": 40,
    "font_size" : 24,
    "font_family": "TimesNewRoman",
    "image_url": "https://i.imgur.com/OvshW5S.png",
}

lao_tzu_obj = {
    "name" : "lao_tzu",
    "x" : 500,
    "y" : 100,
    "width": 40,
    "font_size" : 24,
    "font_family": "TimesNewRoman",
    "image_url": "https://i.imgur.com/N6uYFSO.png"
}

collections_images.insert_many([lao_ping_obj, lao_tzu_obj])
