'''
Script to read PDF filings with IDX Format
'''
import pdfplumber

def extract_from_pdf(filename):
  text = ""
  try:
      with pdfplumber.open(filename) as pdf:
          for page in pdf.pages:
              page_text = page.extract_text()
              if page_text:
                  text += page_text
  except Exception as e:
      return str(e)
  return text
    
