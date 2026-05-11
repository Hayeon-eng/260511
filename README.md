# AEO Lab — AI 토론 플랫폼

여러 페르소나가 같은 콘텐츠를 동시에 진단하고 토론하는 도구.  
**ChatGPT, Perplexity, Gemini, Google Shopping**이 이 페이지를 얼마나 잘 인용·추천할지를 4가지 축으로 분석합니다.

## 4가지 분석 축

| 축 | 무엇을 본다 |
|---|---|
| 📊 **데이터** | JSON-LD/Schema.org, 메타 태그, 구조화된 정보 — AI가 인용할 수 있는 정량/구조 |
| ✍️ **콘텐츠** | 카피, 메시지, 내러티브, 톤앤매너, 정보 위계 |
| 🛍️ **AI Commerce** | Google Shopping/ChatGPT Shopping/Gemini가 제품을 추천할 때 우리 데이터를 인용할 가능성 |
| 🎨 **UX** | 정보 구조, 탐색 경로, 가독성 (사람과 AI 모두에게 스캐닝 좋은가) |

## 기본 페르소나 9명

| 닉네임 | 축 | 한 줄 소개 |
|---|---|---|
| DataNerd 📊 | 데이터 | 구조화 데이터에만 반응하는 데이터 사이언티스트 |
| SchemaSurgeon 🩺 | 데이터 | 페이지의 구조적 결손을 외과의처럼 짚어내는 SEO/AEO 컨설턴트 |
| 감성젠지 💫 | 콘텐츠 | Z세대 소비자, 카피의 결에 즉각 반응 |
| 카피노예 ✍️ | 콘텐츠 | 10년차 카피라이터, 헤드라인 위계에 집착 |
| AICommerceHacker 🛍️ | AI Commerce | AI가 어떤 제품을 추천하는지 매일 추적 |
| PriceComparer 🔎 | AI Commerce | "이거 사도 돼?"를 AI에 묻는 현실 소비자 |
| UXResearcher 🎨 | UX | 사용성 테스트 200회, 스캐닝 패턴 분석가 |
| SkepticalShopper 🤨 | UX | 첫 화면에서 신뢰 안 가면 닫는 까칠한 소비자 |
| BrandStrategist 🎯 | 콘텐츠·AI Commerce | 브랜드 메시지, 타깃, 포지셔닝 적합도를 보는 마케팅 전략가 |

물론 본인이 직접 페르소나를 추가/수정/삭제할 수 있습니다.


## 브랜드 적합도

브랜드 적합도는 Samsung Galaxy / Apple의 공식 브랜드 아이덴티티와 브랜드 페르소나 기준으로 계산합니다. 검색량 API는 사용하지 않습니다.

점수 가중치:

- 공식 브랜드 아이덴티티 매칭: 15점
- 브랜드 페르소나 적합도: 70점
- 근거 명확성: 15점

앱 화면에서는 `브랜드 페르소나 판단 기준 보기`를 접힌 주석 형태로 제공하며, 클릭하면 Samsung Galaxy / Apple 각각의 판단 기준을 확인할 수 있습니다.

주의: 실제 시장 반응, 검색량, 소비자 선호도, 구매 의향은 포함하지 않습니다. 해당 데이터는 Google Search Console, Google Ads Keyword Planner, Naver DataLab 같은 외부 데이터 연동이 필요합니다.

---

## 🚀 처음부터 끝까지 — 5단계 배포

> **필요한 것**: GitHub 계정, Render 계정, Google 계정. 모두 무료. 카드 등록 불필요.

### 1단계 · Gemini API 키 발급 (2분)

1. [Google AI Studio](https://aistudio.google.com/apikey) 접속
2. Google 계정으로 로그인
3. **"Create API key"** 클릭 → **"Create API key in new project"** 선택
4. 생성된 키(`AIza...`로 시작)를 복사해서 안전한 곳에 저장

> 무료 한도: **분당 15회, 일일 1,500회** — 개인 사용은 한참 남습니다.

### 2단계 · 이 코드를 GitHub에 올리기 (3분)

1. [GitHub](https://github.com/new)에서 새 저장소 만들기 (이름은 자유, 예: `aeo-lab`)
2. 저장소 페이지에서 **"uploading an existing file"** 클릭
3. 이 폴더의 모든 파일을 **드래그&드롭**으로 업로드
4. **"Commit changes"** 클릭

업로드해야 할 파일들 (모두 같은 폴더에, 평평하게):
```
main.py, gemini_llm.py, crawler.py, analyzer.py,
persona.py, discussion.py, database.py, file_handler.py,
index.html, requirements.txt, render.yaml, Dockerfile, README.md
```

총 13개 파일. 폴더 만들 필요 없이 그냥 13개 다 같이 드래그&드롭 하면 됩니다.

### 3단계 · Render에 연결 (3분)

1. [Render](https://render.com)에 가입 (GitHub 계정으로 로그인하면 편함)
2. 대시보드에서 **"New +"** → **"Web Service"** 클릭
3. **"Build and deploy from a Git repository"** 선택
4. 방금 만든 GitHub 저장소 선택 → **"Connect"**
5. 설정값:
   - **Name**: 자유 (예: `aeo-lab`)
   - **Region**: Singapore (한국에서 가장 가까움)
   - **Branch**: main
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free
6. 아직 **"Create Web Service"** 누르지 말기!

### 4단계 · 환경변수 (API 키) 등록 (1분)

1. 같은 화면 아래로 스크롤 → **"Environment Variables"** 섹션
2. **"Add Environment Variable"** 클릭
3. 추가:
   - **Key**: `GEMINI_API_KEY`
   - **Value**: 1단계에서 복사한 키 붙여넣기
4. **"Create Web Service"** 클릭

### 5단계 · 완료 (4~6분 자동 대기)

빌드가 끝나면 페이지 상단의 `https://aeo-lab-xxxx.onrender.com` 같은 주소로 접속.  
바로 사용 가능합니다.

> ⚠️ **Render 무료 플랜 특징**: 15분 동안 사용 안 하면 슬립 모드로 들어가서 첫 접속 시 30초 정도 깨어나는 시간이 필요합니다. 데이터(SQLite)도 슬립/재배포 시 휘발됩니다. 영구 보존이 필요하면 Render Disk(월 $1)를 활성화하세요.

---

## 사용 방법

1. **새 토론 시작** 버튼 클릭
2. 토론 주제 입력 (예: "이 페이지가 ChatGPT 추천에 잘 들어갈까?")
3. 분석할 **URL 또는 PDF/이미지 파일** 업로드
> YouTube URL은 가능한 경우 자막/자동자막과 페이지 메타데이터를 분석합니다. 영상 화면·장면 자체를 Gemini Vision으로 보는 기능은 현재 포함되어 있지 않습니다.

4. **참여 페르소나 3~5명** 선택
5. **분석 시작** → AI가 콘텐츠를 진단
6. **▶ 자동 진행** 또는 **+1 발언** 으로 토론 시작
7. 우측 패널에서 **라이브 다이제스트**(합의/충돌/액션) 실시간 확인
8. 다 끝나면 **⬇ MD** 로 마크다운 리포트 다운로드

---

## 페르소나 답변 구조

모든 발언은 **동일한 양식**으로 나옵니다 (신빙성과 일관성을 위해):

```
[페르소나명 / 입장 / 대상]
"한 줄 종합"

[축1 — 예: 데이터]
근거: (실제 데이터에서 직접 인용)
주장: (왜 그것이 문제/기회인지, 150자+ 분석)
액션: (구체적 실행안, 50자+)

[축2 — 예: AI Commerce]
근거 / 주장 / 액션
```

근거가 없으면 발언 자체가 만들어지지 않습니다. 다른 페르소나가 이미 인용한 데이터·주장과는 중복되지 않습니다.

---

## 로컬에서 돌리기 (개발자용)

```bash
git clone <이 저장소>
cd aeo-lab
cp .env.example .env  # 그리고 GEMINI_API_KEY 채우기
pip install -r requirements.txt
uvicorn main:app --reload
```

http://localhost:8000

## Docker

```bash
docker build -t aeo-lab .
docker run -p 8000:8000 -e GEMINI_API_KEY=<your-key> aeo-lab
```

---

## 비용

| 항목 | 비용 |
|---|---|
| Gemini API | 무료 (분 15회 / 일 1,500회) |
| Render Free Plan | 무료 (월 750시간) |
| GitHub | 무료 |
| **합계** | **0원** |

품질을 올리고 싶으면 `GEMINI_MODEL`을 `gemini-1.5-pro`로 바꾸세요 (한도는 더 적음).

---

## 문제 해결

**Q. 발언이 "응답 생성 실패"로 나옵니다.**  
A. Render 대시보드 → Environment → `GEMINI_API_KEY` 값을 다시 확인하세요. 키 앞뒤 공백도 제거. 또는 일일 한도 1,500회 초과 가능성.

**Q. 분석은 됐는데 토론이 안 시작돼요.**  
A. 페르소나가 1명 이상 선택되어 있는지 확인하세요. **▶ 자동 진행** 버튼이 토론을 시작합니다.

**Q. 페이지 첫 접속이 느려요.**  
A. Render 무료 플랜은 슬립이 있습니다. 30초 정도 기다리면 깨어납니다. 항상 빠르길 원하면 유료 플랜으로.

**Q. 토론 기록이 사라졌어요.**  
A. Render 무료 플랜은 디스크가 휘발성입니다. **⬇ MD** 로 미리 내보내두세요. 영구 보존은 Render Disk(월 $1) 또는 외부 DB 연동 필요.
