# Sectors News Endpoint

A comprehensive API for Indonesian stock market news processing, analysis, and management. This service provides intelligent news article processing, insider trading filings analysis, and real-time market data classification.

## 🚀 Features

### News Article Processing
- **URL-based Article Extraction**: Extract and process news articles from URLs using advanced AI
- **Intelligent Classification**: Automatic tagging, ticker extraction, and sentiment analysis
- **Content Scoring**: Quality assessment and relevance scoring for articles
- **Batch Processing**: Asynchronous processing of multiple URLs with status tracking
- **Duplicate Detection**: Prevents duplicate articles based on source URLs

### Insider Trading & Filings
- **PDF Processing**: Extract and analyze SEC filings and insider trading documents
- **Transaction Classification**: Categorize insider trading activities
- **Performance Monitoring**: Real-time metrics and monitoring capabilities

### Market Intelligence
- **Sector Classification**: Automatic categorization by Indonesian market sectors
- **Company Mapping**: Integration with top 300 Indonesian companies by market cap
- **Sentiment Analysis**: AI-powered sentiment classification for market impact

### Performance Optimizations
- **Intelligent Caching**: ~90% faster processing for repeated URLs
- **Parallel Processing**: Concurrent LLM operations for ~40-60% performance improvement
- **Async Web Scraping**: Connection pooling and optimized content extraction
- **Real-time Monitoring**: Performance metrics and system health tracking

## 🏗️ Architecture

### Tech Stack
- **Backend**: Flask (Python 3.11)
- **Database**: Supabase (PostgreSQL)
- **AI/ML**: LangChain, Groq LLM, OpenAI
- **Web Scraping**: BeautifulSoup4, Goose3
- **PDF Processing**: PDFPlumber
- **NLP**: NLTK, LangDetect
- **Deployment**: Fly.io, Vercel
- **Documentation**: OpenAPI/Swagger

### Project Structure
```
sectors_news_endpoint/
├── app.py                 # Main Flask application
├── database.py            # Database connection and data loading
├── gunicorn_config.py     # Production server configuration
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── fly.toml              # Fly.io deployment config
├── vercel.json           # Vercel deployment config
├── openapi.yaml          # API documentation
├── handlers/             # API route handlers
│   ├── articles.py       # News article endpoints
│   ├── filings.py        # SEC filings endpoints
│   ├── subscription.py   # Subscription management
│   └── support.py        # Support and logging
├── model/                # Data models
│   ├── news_model.py     # News article model
│   ├── filings_model.py  # Filing data model
│   ├── llm_collection.py # LLM integration
│   └── price_transaction.py
├── scripts/              # Core processing scripts
│   ├── classifier.py     # AI classification logic
│   ├── summary_news.py   # News summarization
│   ├── summary_filings.py # Filing summarization
│   ├── scorer.py         # Content scoring
│   ├── metadata.py       # Metadata extraction
│   ├── pdf_reader.py     # PDF processing
│   └── generate_article.py
├── middleware/           # Middleware components
│   └── api_key.py        # API key authentication
├── data/                 # Static data files
│   ├── sectors_data.json # Sector classifications
│   ├── companies.json    # Company information
│   ├── top300.json       # Top 300 companies
│   └── embeddings/       # AI embeddings
├── utils/                # Utility functions
└── nltk_data/           # NLP data files
```

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.11+
- Supabase account and project
- API keys for Groq/OpenAI

### Environment Variables
Create a `.env` file with the following variables:
```bash
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
API_KEY=your_api_key
GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_api_key
```

### Local Development
```bash
# Clone the repository
git clone <repository-url>
cd sectors_news_endpoint

# Install dependencies
pip install -r requirements.txt

# Download NLTK data
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"

# Run the application
python app.py
```

### Production Deployment
```bash
# Using Gunicorn
gunicorn --config gunicorn_config.py app:app

# Using Docker
docker build -t sectors-news-endpoint .
docker run -p 8080:8080 sectors-news-endpoint
```

## 📚 API Documentation

### Interactive API Documentation
The API includes a built-in Swagger/OpenAPI documentation server:

- **Development**: http://localhost:5000/apidocs
- **Production**: https://sectors-news-endpoint.fly.dev/apidocs

This interactive documentation allows you to:
- Explore all available endpoints
- Test API calls directly from the browser
- View request/response schemas
- Understand authentication requirements

### Authentication
All endpoints (except `GET /articles`) require an API key passed in the `Authorization` header:
```
Authorization: Bearer your_api_key
```

### Key Endpoints

#### News Articles
- `POST /articles` - Insert single news article
- `POST /articles/list` - Insert multiple articles
- `GET /articles` - Retrieve articles (no auth required)
- `PATCH /articles` - Update article
- `DELETE /articles` - Delete articles
- `POST /url-article` - Generate article from URL
- `POST /url-articles/batch` - Batch process URLs (async)
- `GET /url-articles/batch/<task_id>` - Check batch status

#### Filings
- `POST /filings` - Process SEC filings
- `GET /filings` - Retrieve filings
- `POST /filings/upload` - Upload PDF filings

#### Subscriptions
- `POST /subscription` - Manage user subscriptions
- `GET /subscription` - Get subscription status

### Example Usage

#### Process Single URL
```bash
curl -X POST https://sectors-news-endpoint.fly.dev/url-article \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "https://example.com/news-article",
    "timestamp": "2024-01-01 12:00:00"
  }'
```

#### Batch Process URLs
```bash
# Submit batch request
curl -X POST https://sectors-news-endpoint.fly.dev/url-articles/batch \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '[
    {"source": "https://example1.com", "timestamp": "2024-01-01 12:00:00"},
    {"source": "https://example2.com", "timestamp": "2024-01-01 12:00:00"}
  ]'

# Check status
curl -X GET https://sectors-news-endpoint.fly.dev/url-articles/batch/task_id_here \
  -H "Authorization: Bearer your_api_key"
```

## 🚀 Deployment

### Fly.io (Primary)
The application is configured for deployment on Fly.io with automatic CI/CD:

```bash
# Deploy to Fly.io
flyctl deploy
```

**GitHub Actions**: Automatic deployment on push to `main` branch via `.github/workflows/fly-deploy.yml`

### Vercel (Alternative)
Configured for serverless deployment on Vercel:

```bash
# Deploy to Vercel
vercel --prod
```

### Environment Configuration
- **Production URL**: https://sectors-news-endpoint.fly.dev
- **Memory**: 2GB
- **CPU**: 1 shared core
- **Region**: Singapore (SIN)

## 🔧 Configuration

### Gunicorn Settings
- **Workers**: 2 × CPU cores + 1
- **Threads**: 2 per worker
- **Timeout**: 60 seconds
- **Max Requests**: 5000 per worker

### Performance Tuning
- **Connection Pooling**: Optimized for concurrent requests
- **Caching**: Intelligent URL content caching
- **Async Processing**: Background task processing
- **Memory Management**: Efficient data loading and cleanup

## 📊 Monitoring & Logs

### Logging
- **Level**: INFO
- **Format**: Timestamp, Level, Message
- **Output**: Stdout/Stderr

### Performance Monitoring
- Real-time request tracking
- Response time monitoring
- Error rate tracking
- System resource usage

### Access Logs
```bash
# View logs
curl -X GET https://sectors-news-endpoint.fly.dev/logs \
  -H "Authorization: Bearer your_api_key"
```