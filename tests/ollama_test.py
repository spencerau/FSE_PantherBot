import os
import yaml
import pandas as pd
from langchain_community.vectorstores import Chroma
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain.schema.output_parser import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema.runnable import RunnablePassthrough
from langchain.prompts import PromptTemplate


class SimpleRAG:
    def __init__(self, config_filename="config.yaml"):
        pwd = os.getcwd()
        config_path = os.path.join(pwd, "configs", config_filename)
        self.config = self._load_config(config_path)

        self.model = ChatOllama(
            model=self.config["deepseek"]["model_name"],
            temperature=self.config["deepseek"].get("temperature", 0.7),
            top_p=self.config["deepseek"].get("top_p", 0.9),
            max_tokens=self.config["deepseek"].get("max_tokens", 512),
            streaming=True
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config["langchain"]["chunk_size"],
            chunk_overlap=self.config["langchain"]["chunk_overlap"],
        )
        self.prompt = PromptTemplate.from_template(self.config["langchain"]["prompt"])
        self.vector_store = None
        self.retriever = None
        self.chain = None


    def _load_config(self, config_path):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        with open(config_path, "r") as f:
            return yaml.safe_load(f)


    def ingest(self, data_dir="data"):
        pwd = os.getcwd()
        data_path = os.path.join(pwd, data_dir)

        docs = []
        for root, _, files in os.walk(data_path):  
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    if file.endswith(".pdf"):
                        docs.extend(PyPDFLoader(file_path=file_path).load())
                    elif file.endswith(".csv"):
                        docs.extend(self._load_csv(file_path))
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

        if not docs:
            print("No valid documents found in data directory.")
            return

        try:
            chunks = self.text_splitter.split_documents(docs)
            self.vector_store = Chroma.from_documents(
                documents=chunks,
                embedding=FastEmbedEmbeddings(),
                persist_directory=self.config["chroma"]["persist_directory"],
            )
            self.retriever = self.vector_store.as_retriever(
                search_kwargs={"k": self.config["chroma"]["top_k"]}
            )
            self.chain = (
                {"context": self.retriever, "question": RunnablePassthrough()}
                | self.prompt
                | self.model
                | StrOutputParser()
            )
            print("Documents successfully ingested into ChromaDB!")
        except Exception as e:
            print(f"Error during chunking/storage: {e}")


    def _load_csv(self, file_path):
        try:
            df = pd.read_csv(file_path, error_bad_lines=False, warn_bad_lines=True, encoding="utf-8")
            return [" ".join(map(str, row.values)) for _, row in df.iterrows()]
        except pd.errors.ParserError as e:
            print(f"CSV Parsing Error in {file_path}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected Error while loading CSV {file_path}: {e}")
            return []


    def ask(self, query: str):
        if not self.chain:
            return "No documents ingested yet. Please run `ingest()` first."
        for word in self.chain.stream(query):
            print(word, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    rag = SimpleRAG(config_filename="config.yaml")
    rag.ingest(data_dir="data")
    while True:
        user_input = input("\nAsk a question (or type 'exit' to quit): ")
        if user_input.lower() == "exit":
            break
        rag.ask(user_input)