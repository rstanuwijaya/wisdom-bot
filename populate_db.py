import pymongo
import os

from dotenv import load_dotenv
load_dotenv()

mongo_user = os.getenv('MONGODB_USER')
mongo_pass = os.getenv('MONGODB_PASS')
mongo_conn_str = f"mongodb+srv://{mongo_user}:{mongo_pass}@cluster0.ac4ho.mongodb.net/myFirstDatabase?retryWrites=true&w=majority"
client = pymongo.MongoClient(mongo_conn_str)
db_quotes = client['quotes']
collections_images = db_quotes['image']


lao_ping_obj = {
    "name" : "lao_ping",
    "x" : 500,
    "y" : 100,
    "font_size" : 40,
    "image_url": "https://i.imgur.com/OvshW5S.png"
}

lao_tzu_obj = {
    "name" : "lao_tzu",
    "x" : 500,
    "y" : 100,
    "font_size" : 40,
    "image_url": "https://i.imgur.com/N6uYFSO.png"
}


collections_images.insert_many([lao_ping_obj, lao_tzu_obj])
