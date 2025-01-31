from langchain_community.vectorstores import Chroma
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain.schema.output_parser import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema.runnable import RunnablePassthrough
from langchain.prompts import PromptTemplate
from langchain.vectorstores.utils import filter_complex_metadata


class ChatPDF:
    vector_store = None
    retriever = None
    chain = None


    def __init__(self):
        self.model = ChatOllama(model="deepseek-r1:14b")
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1024, chunk_overlap=100)
        self.prompt = PromptTemplate.from_template(
            """
            <s> [INST] You are an assistant designed to answer questions. Use the information provided in the context below to formulate your response. 
            If you don’t know the answer, simply state that you don’t know. Limit your response to a maximum of three sentences and be concise. [/INST] </s> 
            [INST] Question: {question} 
            Context: {context} 
            Answer: [/INST]
            """
        )


    # The ingest method accepts a file path and loads it into vector storage in two steps: 
    # first, it splits the document into smaller chunks to accommodate the token limit of the LLM; 
    # second, it vectorizes these chunks using Qdrant FastEmbeddings and store into Chroma.
    def ingest(self, pdf_file_path: str):
        docs = PyPDFLoader(file_path=pdf_file_path).load()
        chunks = self.text_splitter.split_documents(docs)
        chunks = filter_complex_metadata(chunks)

        vector_store = Chroma.from_documents(documents=chunks, embedding=FastEmbedEmbeddings())
        self.retriever = vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                "k": 3,
                "score_threshold": 0.5,
            },
        )

        self.chain = ({"context": self.retriever, "question": RunnablePassthrough()}
                      | self.prompt
                      | self.model
                      | StrOutputParser())


    # The ask method handles user queries. Users can pose a question, and then 
    # the RetrievalQAChain retrieves the relevant contexts (document chunks) using vector similarity search techniques.
    def ask(self, query: str):
        if not self.chain:
            return "Please, add a PDF document first."

        return self.chain.invoke(query)


    def clear(self):
        self.vector_store = None
        self.retriever = None
        self.chain = None