# mvp-data

주식추천 MVP가 읽어 가는 공개 데이터 저장소입니다.
GitHub Actions가 정해진 시간마다 공공 데이터(DART·한국은행 ECOS·KRX·KDI)를 받아 `data/` 폴더에 JSON으로 저장합니다.
API 키는 저장소 Secrets(`DART_API_KEY`, `ECOS_API_KEY`)에만 보관하며 코드나 데이터에 들어가지 않습니다.
