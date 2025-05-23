from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from typing import Dict, Any
from config import node_log, RAG_Query

from langchain_core.prompts import PromptTemplate

prompt_template = PromptTemplate.from_template(RAG_Query)
retriever: Any = None  # ← 전역 변수로 선언


def rag_retrieve(state: Dict) -> Dict:
    """
    • state['page'] → splitter.split_documents → chunks
    • embeddings = OpenAIEmbeddings(...)
    • vs = FAISS.from_documents(chunks, embeddings)
    • retriever = vs.as_retriever(k=6)
    • retrieved_docs = retriever.invoke(query)
    • state['documents'] = retrieved_docs
    """
    # 재실행 시 사용할 검색기 전역변수로 설정
    global retriever
    # 처음 호출이거나 retriever가 없으면 인덱스부터 생성
    if "retriever_query" not in state:
        node_log("RAG RETRIEVE")
        text = state["page"]
        docs = [Document(page_content=text, metadata={"source": state["url"]})]
        if state.get("page_meta") != "":
            page_meta = Document(
                page_content=state["page_meta"], metadata={"source": state["url"]}
            )
            docs.append(page_meta)
            query = prompt_template.format(product_name=state["page_meta"])
        else:
            query = prompt_template.format(product_name=state["page"])

        state["retriever_query"] = query

        # 1) HTML을 청크로 분할
        splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
        chunks = splitter.split_documents(docs)

        # 2) 임베딩 생성 및 FAISS 인덱스 구축
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        vs = FAISS.from_documents(chunks, embeddings)
        retriever = vs.as_retriever(search_type="similarity", search_kwargs={"k": 6})
        state["retriever"] = retriever
    else:
        # 이미 retriever_query와 retriever가 있으면 재검색
        node_log("RETRIEVE AGAIN")
        query = state["retriever_query"]

    # 3) 실제 검색 실행
    retrieved_docs = retriever.invoke(query)
    state["documents"] = retrieved_docs
    return state
