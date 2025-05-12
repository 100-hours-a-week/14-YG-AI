---
name: trouble shooting template
about: AI trouble shooting template
title: ''
labels: trouble-shooting
assignees: ''

---

## 🐞 에러 내용
예시) 
- 로그인 후 API 요청 시 `401 Unauthorized` 오류 발생

## 🔍 원인 분석
예시)
- 서버에서는 토큰 검증 로직이 있음
- 클라이언트에서 토큰을 Authorization 헤더에 담지 않음

## ✅ 해결 방법
예시)
- axios 인스턴스에 default header 설정 추가

## 회고
- 
