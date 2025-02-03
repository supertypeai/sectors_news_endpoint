
def notify_subscriber(topic):
  # Topic can be ticker, or subsector
  print(f"Sending notification to subscriber with {topic}")
  
  # subscriber { email: string, topics: [string] }