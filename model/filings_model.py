import json
from datetime import datetime

class Filing:
    def __init__(self, title, body, source, timestamp, sector, sub_sector, tags, tickers, transaction_type, holder_type, holding_before, holding_after, amount_transaction, holder_name, price, transaction_value, price_transaction):
        """
        Initializes the Filing object.

        @param title: Title of the filing.
        @param body: Body content of the filing.
        @param source: Source of the filing.
        @param timestamp: Timestamp of the filing.
        @param sector: Sector of the filing.
        @param sub_sector: Sub-sector of the filing.
        @param tags: Tags associated with the filing.
        @param tickers: Tickers associated with the filing.
        @param transaction_type: Type of the transaction (buy/sell).
        @param holder_type: Type of the holder.
        @param holding_before: Holding amount before the transaction.
        @param holding_after: Holding amount after the transaction.
        @param amount_transaction: Amount of the transaction.
        @param holder_name: Name of the holder.
        @param price: Price of the transaction.
        @param transaction_value: Value of the transaction.
        @param price_transaction: Price transaction details.
        """
        self.title = title
        self.body = body
        self.source = source
        self.timestamp = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp
        self.sector = sector
        self.sub_sector = sub_sector
        self.tags = tags
        self.tickers = tickers
        self.transaction_type = transaction_type
        self.holder_type = holder_type
        self.holding_before = holding_before
        self.holding_after = holding_after
        self.amount_transaction = amount_transaction
        self.holder_name = holder_name
        self.price = price
        self.transaction_value = transaction_value
        self.price_transaction = price_transaction

    def to_json(self):
        """
        Converts the Filing object to a JSON string.

        @return: JSON string representation of the Filing object.
        """
        return json.dumps(self.__dict__, default=str, indent=4)

    @classmethod
    def from_json(cls, json_str):
        """
        Creates a Filing object from a JSON string.

        @param json_str: JSON string representation of a Filing object.
        @return: Filing object.
        """
        data = json.loads(json_str)
        return cls(**data)

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

# json_str = filing.to_json()
# print(json_str)

# new_filing = Filing.from_json(json_str)
# print(new_filing.__dict__)