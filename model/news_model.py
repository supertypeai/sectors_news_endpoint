import json
from datetime import datetime
from model.filings_model import Filing

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