import os
from llama_index.llms.groq import Groq
import dotenv

dotenv.load_dotenv()

class LLMCollection:
    """
    @brief Singleton class to manage a collection of LLM (Large Language Model) instances.
    This class ensures that only one instance of the LLMCollection exists and provides methods to add and retrieve LLM instances.
    """
    _instance = None

    def __new__(cls):
        """
        @brief Creates a new instance of LLMCollection if it doesn't already exist.
        @return The singleton instance of LLMCollection.
        """
        if cls._instance is None:
            cls._instance = super(LLMCollection, cls).__new__(cls)
            cls._instance._llms = [
                Groq(
                    model="llama3-70b-8192",
                    api_key=os.getenv('GROQ_API_KEY'),
                ),
                Groq(
                    model="gemma2-9b-it",
                    api_key=os.getenv('GROQ_API_KEY'),
                )
            ]
        return cls._instance

    def add_llm(self, llm):
        """
        @brief Adds a new LLM instance to the collection.
        @param llm The LLM instance to be added to the collection.
        """
        self._llms.append(llm)

    def get_llms(self):
        """
        @brief Retrieves the list of LLM instances in the collection.
        @return A list of LLM instances.
        """
        return self._llms

# Example usage:
# llm_collection = LLMCollection()
# llm_collection.add_llm("LLM1")
# llm_collection.add_llm("LLM2")
# print(llm_collection.get_llms())