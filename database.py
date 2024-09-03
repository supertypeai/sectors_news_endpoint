from supabase import create_client, Client
import os
import json

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(os.getenv("SUPABASE_URL"), SUPABASE_KEY)

sectors_data = {}

with open("./data/sectors_data.json", "r") as f:
    sectors_data = json.load(f)

