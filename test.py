import pymongo
import os

from dotenv import load_dotenv
load_dotenv()

client = pymongo.MongoClient(os.getenv('MONGODB_CONN_STRING'))
db_quotes = client['quotes']
collections_images = db_quotes['image']

obj = collections_images.find_one({"name": "lao_ping"})
print(obj['image_url'])