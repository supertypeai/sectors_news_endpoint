import json
import pandas as pd 


class PriceTransaction:
  def __init__(self, amount_transacted: list[float], prices: list[float], transaction_type: list[str]):
    """
    Initializes the Transaction object.

    @param amount: Amount of the transaction.
    @param price: Price of the transaction.
    """
    self.amount_transacted = amount_transacted
    self.prices = prices
    self.transaction_type = transaction_type

  def calculate_two_transaction_type(self) -> dict:
    """
    Calculates the net transaction details from a dictionary of price transactions.

    @return: Dictionary containing the weighted average price, total transaction value, and overall transaction type.
    """
    df = pd.DataFrame({
        'amount_transacted': self.amount_transacted,
        'prices': self.prices,
        'type': self.transaction_type
    }) 
   
    df['value'] = df['prices'] * df['amount_transacted']

    # Calculate total shares and value for all 'buy' transactions
    total_buy_shares = df[df['type'] == 'buy']['amount_transacted'].sum()
    total_buy_value = df[df['type'] == 'buy']['value'].sum()

    # Calculate total shares and value for all 'sell' transactions
    total_sell_shares = df[df['type'] == 'sell']['amount_transacted'].sum()
    total_sell_value = df[df['type'] == 'sell']['value'].sum()

    # Calculate total shares and value for 'others' transactions
    total_others_shares = df[~df['type'].isin(['buy', 'sell'])]['amount_transacted'].sum()
    total_others_value = df[~df['type'].isin(['buy', 'sell'])]['value'].sum()

    # Check if there are any buy or sell transactions
    has_buy_sell = (total_buy_shares > 0) or (total_sell_shares > 0)

    if has_buy_sell:
        # Calculate the net difference between buys and sells
        net_value = total_buy_value - total_sell_value
        net_shares = total_buy_shares - total_sell_shares

        if net_value > 0:
            transaction_type = 'buy'
        elif net_value < 0:
            transaction_type = 'sell'
        else: 
            transaction_type = 'others'
        
        # Calculate the weighted average price
        if net_shares != 0:
            weighted_average_price = abs(net_value / net_shares)
        else:
            weighted_average_price = 0.0

        result = {
            "price": round(weighted_average_price, 3),
            "transaction_value": abs(int(net_value)),
            "transaction_type": transaction_type
        }

    else:
        # Only "others" transactions exist
        if total_others_shares > 0:
            weighted_average_price = total_others_value / total_others_shares
        else:
            weighted_average_price = 0.0
        
        result = {
            "price": round(weighted_average_price, 3),
            "transaction_value": abs(int(total_others_value)),
            "transaction_type": "others"
        }

    return result.get('price'), result.get('transaction_value'), result.get('transaction_type')
    
  def get_price_transaction_value(self):
    """
    Calculates the price and transaction value of the transaction.
    
    @return: Tuple containing the price and transaction value.
    """
    sum_price_transaction = 0
    sum_transaction = 0  

    for index in range(len(self.prices)):
      sum_price_transaction += self.prices[index] * self.amount_transacted[index]
      sum_transaction += self.amount_transacted[index]

    self.price = sum_price_transaction / sum_transaction if sum_transaction != 0 else 0
    self.transaction_value = sum_price_transaction
    self.price = round(self.price, 3)
    return self.price, self.transaction_value
  
  def to_json(self):
    """
    Converts the Transaction object to a JSON string.

    @return: JSON string representation of the Transaction object.
    """
    return json.dumps(self.__dict__, indent=2)

  @classmethod
  def from_json(cls, json_str):
    """
    Creates a Transaction object from a JSON string.

    @param json_str: JSON string representation of a Transaction object.
    @return: Transaction object.
    """
    data = json.loads(json_str)
    return cls(**data)

# Example usage
# transaction = PriceTransaction(amount_transacted=[100,200], prices=[9.99, 8.99])
# json_str = transaction.to_json()
# print(json_str)

# new_transaction = PriceTransaction.from_json(json_str)
# print(new_transaction.__dict__)
