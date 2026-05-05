MODEL_CONFIG = { 
    'gpt-oss-120b': {
        'model': 'openai/gpt-oss-120b',
        'provider': 'groq', 
        # 'key': GROQ_API_KEY
    },
    'gpt-oss-20b': {
        'model': 'openai/gpt-oss-20b',
        'provider': 'groq', 
        # 'key': GROQ_API_KEY
    },
    'gemini-2.5-flash': {
        'model': 'gemini-2.5-flash',
        'provider': 'google-genai', 
        # 'key': GEMINI_API_KEY
    },
    'llama-3.3-70b': {
        'model': 'llama-3.3-70b-versatile',
        'provider': 'groq', 
        # 'key': GROQ_API_KEY
    }
}

ROTATE_STATUS_CODES = {401, 403, 429, 413}
ABORT_STATUS_CODES = {400, 422, 500, 502, 503, 504}

ROTATE_KEYWORDS = (
    "rate limit", "too many requests", "authentication", "invalid api key", 
    "request too large"
)
ROTATE_400_KEYWORDS = ("organization_restricted",)
ABORT_KEYWORDS = (
    "context length", "max token", "internal server",
    "bad gateway", "service unavailable",
)