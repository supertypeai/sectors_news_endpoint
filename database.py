from supabase import create_client, Client
import os
import json

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase key and URL must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

sectors_data = {}

with open("./data/sectors_data.json", "r") as f:
    sectors_data = json.load(f)

