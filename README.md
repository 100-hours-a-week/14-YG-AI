# 14-YG-AI

<details>
<summary>사용 방법</summary>

> 0. .env(env_sample) 및 gcp api key(.json) 필요

> 1. python3 -m venv venv

> 2. mac: source venv/bin/activate / win(powershell): venv/Scripts/Activate.ps1

> 3. pip install --upgrade pip (생략 가능)

> 4. pip install -r requirements.txt

> 5. python app.py
</details>

## 📘 API 명세서 - 상품 상세 설명 생성

### 🔗 **POST** `/generation/description`

---

### 📌 요청 예시
```json
{
  "url": "https://myprotein/link"
}
```

---

### 📥 요청 파라미터

| 이름       | 타입    | 필수 여부 | 설명                            |
|------------|---------|-----------|---------------------------------|
| `url`      | string  | ✅ 필수   | 상품 페이지의 URL               |

> 선택 파라미터는 없습니다.

---

### 📤 응답 형식

#### ✅ 200 OK

| 필드                       | 타입     | 설명                                                       |
|----------------------------|----------|------------------------------------------------------------|
| `message`                  | string   | 성공 메시지                                                |
| `data.product_name`        | string   | 정식 상품명                                                |
| `data.product_lower_name`  | string   | 상품명 요약 (검색용 이름)                                 |
| `data.total_price`         | number   | 총 가격 (정수, 원 단위)                                   |
| `data.count`               | number   | 총 수량                                                    |
| `data.summary`             | string   | 생성된 마케팅용 상품 설명 (이모지 포함)                  |
| `data.title`             | string   | 생성된 추천 공고 제목 (이모지 포함)                  |

📌 **응답 예시**
```json
{
    "generation": {
        "product_name": "햇반 발아현미밥, 210g, 8개",
        "product_lower_name": "햇반 발아현미밥",
        "total_price": 9400,
        "count": 8,
        "summary": "바쁜 현대인을 위한 최고의 선택! 햇반! 🍚 시간 없을 때 간편하게 즐기는 영양 만점 즉석밥! ✨\n\n특수 용기 포장으로 산소와 수분 차단!  🛡️ 방부제 없이도 안전하고 건강하게    즐길 수 있어요! 😊  찬밥, 따뜻한 밥,  취향 따라 골라 먹는 재미까지!  🍚🧊\n\n\n<br/>\n<br/>\n",
        "title": "햇반 8개 9,400원?!😲 밥 걱정 끝! 😎\n"
    }
}
```

---

### ⚠️ 에러 응답

| 상태 코드         | 설명                          | 예시 메시지                                |
|------------------|-------------------------------|--------------------------------------------|
| `400 Bad Request`| 잘못된 URL 형식                | `"유효하지 않은 URL 형식입니다."`          |
| `500 Server Error`| 서버 내부 오류 발생           | `"서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요."` |

📌 **에러 응답 예시**
```json
// 400 Bad Request
{
  "message": "유효하지 않은 URL 형식입니다.",
  "data": null
}

// 500 Internal Server Error
{
  "message": "서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
  "data": null
}
```
---
# LangGraph
<details><summary>0502 랭그래프 아키텍처</summary>

```mermaid
flowchart TD
subgraph Config[recursion_limit=15]
    end
subgraph Router_graph["Routing"]
    Start(URL) --> Router[/Router/]
    Router --> fetch_html_tool
    Router --> vision_model_parser
end
    direction TB
    hallucination_check1[hallucination_check: Groundedness Evaluator]
    hallucination_check2[hallucination_check: Groundedness Evaluator]
    fetch_html_tool --> clean_html
	vision_model_parser --> split_text
	clean_html --> split_text

subgraph RAG["RAG Pipeline"]
direction TB
    split_text([split_text])
    embed_texts([embed_texts])
    vector_search([vector_search])
    split_text --> embed_texts
    embed_texts --> vector_search
    vector_search --> LLM1(LLM: Product Announcement Parser)
end
    
    
    LLM1 --> hallucination_check1
    hallucination_check1 -->|불만족: rewirte_retrieve_query| vector_search
    hallucination_check1 -->|만족: JSON| web_search
    web_search --> LLM2(LLM: Product Description Generator)
    LLM2 --> hallucination_check2
    hallucination_check2 -->|만족| End(Product Information Summary)
    hallucination_check2 -->|불만족: rewrite_websearch_query| web_search
```

</details>

<details><summary>0513 랭그래프 아키텍처</summary>
	
```mermaid
flowchart TD
subgraph Config[recursion_limit=15]
    end
subgraph Router_graph["Routing"]
    Start(URL) --> Router[/Router/]
    Router --> fetch_html_tool
    Router --> fetch_coupang_tool
    Router --> parse_image_text
end
    direction TB
    hallucination_check1[hallucination_check: Groundedness Evaluator]
    hallucination_check2[hallucination_check: Groundedness Evaluator]
    fetch_html_tool --> clean_html
    fetch_coupang_tool --> split_text
	parse_image_text --> split_text
	clean_html --> split_text

subgraph RAG["RAG Pipeline"]
direction TB
    split_text([split_text])
    embed_texts([embed_texts])
    vector_search([vector_search])
    split_text --> embed_texts
    embed_texts --> vector_search
    vector_search --> LLM1(LLM: Product Announcement Parser)
end
    
    
    LLM1 -->|JSON| hallucination_check1
    hallucination_check1 -->|불만족: rewirte_retrieve_query| vector_search
    hallucination_check1 -->|만족: JSON| web_search
    web_search --> LLM2(LLM: Product Description Generator)
    LLM2 --> hallucination_check2
    hallucination_check2 -->|만족| at(LLM: Announcement Title Generator)
    hallucination_check2 -->|불만족: rewrite_websearch_query| web_search
    at -->|JSON| End(Product Information Summary)

```

</details>

### 0519 랭그래프 아키텍처
```mermaid
flowchart TD
subgraph Config[recursion_limit=15]
    end
subgraph Router_graph["Routing"]
    START([URL])
    START --> route_logic{{route_logic}}
    route_logic -->|fetch_html_tool| fetch_html_tool[fetch_html_tool]
    route_logic -->|fetch_coupang_tool| fetch_coupang_tool[fetch_coupang_tool]
end

subgraph Page_Processing["Page Data Processing"]
    fetch_html_tool --> page_data_gate[page_data_gate]
    fetch_coupang_tool --> page_data_gate
    parse_image_text[parse_image_text] --> page_data_gate
    page_data_gate -->|need parsing| parse_image_text
    page_data_gate -->|ready| rag_retrieve[rag_retrieve]
end

subgraph RAG["RAG + Product Info"]
    rag_retrieve --> product_annc_parser[LLM: Product Announcement Parser]
    product_annc_parser -->|hallucination| transform_retrieve_query[rewrite_retrieve_query]
    product_annc_parser -->|relevant| web_search_tool[web_search_tool]
    transform_retrieve_query --> rag_retrieve
end

subgraph Description_Generation["Product Description Pipeline"]
    web_search_tool --> product_desc_gen[LLM: Product Description Generator]
    product_desc_gen --> product_title_gen[LLM: Product Title Generator]
    product_title_gen --> End(Product Information Summary)
end

```
