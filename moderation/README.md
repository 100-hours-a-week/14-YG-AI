# 익명 채팅 모더레이션 (클린봇))
<p>
    <img alt="Static Badge" src="https://img.shields.io/badge/python-3.11-blue?style=flat&logo=python&logoColor=white">
    <img alt="Static Badge" src="https://img.shields.io/badge/LangChain-1C3C3C?style=flat&logo=langchain&logoColor=white">
    <img alt="Static Badge" src="https://img.shields.io/badge/langsmith-black?style=flat&logo=langsmith&logoColor=white">
    <img alt="Static Badge" src="https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white">
    <img alt="Static Badge" src="https://img.shields.io/badge/vLLM-blue?style=flat&logoColor=white">
    <img alt="Static Badge" src="https://img.shields.io/badge/Hugging face-white?style=flat&logo=huggingface&logoColor=yellow">
</p>

<br>  

![image](https://github.com/user-attachments/assets/2d294ae4-75b3-4983-a025-edd7a568bd8c)
<br>  

## gif 위치   


gpu : nvidia L4  
model : https://huggingface.co/kakaocorp/kanana-safeguard-8b

### 검열 타입
- S1	- 증오	출신, 인종, 외양, 장애 및 질병 유무, 사회 경제적 상황 및 지위, 종교, 연령, 성별·성 정체성·성적 지향 또는 기타 정체성 요인 등을 이유로 특정 대상을 차별하거나, 이러한 차별에 기반해 개인 또는 집단을 공격하는 발화  
- S2	- 괴롭힘, 타인에게 불쾌감이나 굴욕감을 주거나, 위협적이거나, 특정 대상에 대한 괴롭힘을 부추기는 발화  
- S3	- 성적 콘텐츠	성적 행위나 신체를 묘사/암시하거나, 성적 수치심/혐오감을 일으킬 수 있는 발화 (성교육 및 웰빙 제외)  
- S4	- 범죄	불법적인 행위(예: 폭력∙비폭력 범죄, 성범죄, 무기 제작·조달)를 기획하고 준비하는 과정을 담은 발화  
- S5	- 아동 성착취	아동 대상의 성적 학대와 관련된 설명, 격려, 지지 등의 발화 (예: 그루밍, CSAM 관련 텍스트 등)  
- S6 - 자살 및 자해	의도적으로 자신의 생명을 끊거나 자신의 신체를 의도적으로 해치는 행위를 묘사하거나 유도하는 발화  
- S7 - 잘못된 정보	개인이나 집단에게 잘못된 정보를 전파할 수 있는 발화  