import json
from datetime import datetime
from model.filings_model import Filing
from database import sectors_data
from scripts.metadata import extract_metadata
from scripts.summary_news import summarize_news
import pytz

timezone = pytz.timezone('Asia/Bangkok')

class News:
    def __init__(self, title, body, source, timestamp, sector, sub_sector, tags, tickers, dimension, score):
        """
        Initializes the News object.

        @param title: Title of the news article.
        @param body: Body content of the news article.
        @param source: Source of the news article.
        @param timestamp: Timestamp of the news article.
        @param sector: Sector of the news article.
        @param sub_sector: Sub-sector(s) of the news article.
        @param tags: Tags associated with the news article.
        @param tickers: Tickers associated with the news article.
        @param dimension: Dimension of the news article.
        @param score: Score of the news article.
        """
        self.title = title
        self.body = body
        self.source = source
        self.timestamp = str(datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp)
        self.sector = sector
        self.sub_sector = sub_sector
        self.tags = tags
        self.tickers = tickers
        self.dimension = dimension
        self.score = score
        
    def to_dict(self):
        """
        Converts the News object to a dictionary.

        @return: Dictionary representation of the News object.
        """
        return {
            "title": self.title,
            "body": self.body,
            "source": self.source,
            "timestamp": self.timestamp,
            "sector": self.sector,
            "sub_sector": self.sub_sector,
            "tags": self.tags,
            "tickers": self.tickers,
            "dimension": self.dimension,
            "score": self.score
        }

    def to_json(self):
        """
        Converts the News object to a JSON string.

        @return: JSON string representation of the News object.
        """
        return json.dumps(self.__dict__, default=dict, indent=4)

    @classmethod
    def from_json(cls, json_str):
        """
        Creates a News object from a JSON string.

        @param json_str: JSON string representation of a News object.
        @return: News object.
        """
        data = json.loads(json_str)
        return cls(**data)

    @classmethod
    def sanitize_article(cls, data: dict, generate: bool = True):
        """
        @helper-function
        @brief Sanitation of article data.
        
        @param data Article to be sanitated.
        
        @return Sanitized article in article format.
        """
        # Sanitization v1.0
        title = data.get("title", "").strip()
        body = data.get("body", "").strip()
        source = data.get("source", "").strip()
        timestamp_str = data.get("timestamp", datetime.now(timezone).isoformat()).strip()
        timestamp_str = timestamp_str.replace("T", " ")
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        score = int(data.get("score")) if data.get("score") else None

        sub_sector = []

        if "sub_sector" in data and isinstance(data.get("sub_sector"), str) and data.get("sub_sector").strip() != "":
            sub_sector.append(data.get("sub_sector").strip())
        elif "subsector" in data and isinstance(data.get("subsector"), str) and data.get("subsector").strip() != "":
            sub_sector.append(data.get("subsector").strip())
        elif "sub_sector" in data and isinstance(data.get("sub_sector"), list):
            sub_sector = data.get("sub_sector")
        elif "subsector" in data and isinstance(data.get("subsector"), list):
            sub_sector = data.get("subsector")

        sector = ""

        if "sector" in data and isinstance(data.get("sector"), str):
            sector = data.get("sector").strip()
        else:
            if len(sub_sector) != 0 and sub_sector[0] in sectors_data.keys():
                sector = sectors_data[sub_sector[0]]
            else:
                sector = ""

        tags = data.get("tags", [])
        tickers = data.get("tickers", [])
        dimension = data.get("dimension", None)

        for i, ticker in enumerate(tickers):
            split = ticker.split(".")
            if len(split) > 1:
                if split[1].upper() == "JK":
                    pass
                else:
                    split[1] = ".JK"
                    tickers[i] = split[0] + split[1]
            else:
                tickers[i] += ".JK"
            tickers[i] = tickers[i].upper()

        if not title or not body:
            generated_title, generated_body = extract_metadata(source)
            if not title:
                title = generated_title
            if not body:
                body = generated_body

        if title == "" or body == "":
            generated_title, generated_body = extract_metadata(source)
            if title == "":
                title = generated_title
            if body == "":
                body = generated_body

        new_article = cls(
            title=title,
            body=body,
            source=source,
            timestamp=timestamp.isoformat(),
            sector=sector,
            sub_sector=sub_sector,
            tags=tags,
            tickers=tickers,
            dimension=dimension,
            score=score
        )

        if generate:
            new_title, new_body = summarize_news(new_article.source)

            if len(new_body) > 0:
                new_article.body = new_body

            if len(new_title) > 0:
                new_article.title = new_title

        return new_article


    @classmethod
    def from_filing(cls, filing):
        """
        Creates a News object from a Filing object.

        @param filing: Filing object.
        @return: News object.
        """
        return cls(
            title=filing.title,
            body=filing.body,
            source=filing.source,
            timestamp=str(filing.timestamp.isoformat()),
            sector=filing.sector,
            sub_sector=[filing.sub_sector],
            tags=filing.tags,
            tickers=filing.tickers,
            dimension=None,
            score=None
        )

# Example usage
# filing = Filing(
#     title="Sample Title",
#     body="Sample Body",
#     source="Sample Source",
#     timestamp=datetime.now().isoformat(),
#     sector="Sample Sector",
#     sub_sector="Sample Sub-sector",
#     tags=["tag1", "tag2"],
#     tickers=["TICKER1", "TICKER2"],
#     transaction_type="buy",
#     holder_type="insider",
#     holding_before=1000,
#     holding_after=1500,
#     amount_transaction=500,
#     holder_name="John Doe",
#     price=10.5,
#     transaction_value=5250,
#     price_transaction={"amount_transacted": [100, 200], "prices": [10, 10.5]}
# )

# news = News.from_filing(filing)
# print(news.to_json())