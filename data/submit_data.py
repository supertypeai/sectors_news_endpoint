from supabase import create_client, Client
import os
import dotenv
import json

dotenv.load_dotenv()

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase key and URL must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def update_filing_by_id(filing_id, updated_data):
    """
    Updates a filing in the 'idx_filings' table based on the given ID.

    @param filing_id: The ID of the filing to update.
    @param updated_data: A dictionary containing the updated data.
    @return: The response from the Supabase update operation.
    """
    response = supabase.table('idx_filings').update(updated_data).eq('id', filing_id).execute()
    return response

if __name__ == "__main__":
  filings = supabase.table('idx_filings').select('*').execute().data
  change_data = []
  
  for filing in filings:
    if filing['price'] != 0:
      filing['price_transaction'] = {
        "prices": [filing['price']],
        "amount_transacted": [filing['amount_transaction']]
      }
      change_data.append(filing)
  
  for data in change_data:
    response = supabase.table('idx_filings').update(data).eq('id', data['id']).execute()
    print(response, end=" ")