# GitHub 업로드 안내 - 폴더 없는 버전

이 버전은 `css/`, `js/`, `static/` 같은 폴더를 쓰지 않습니다.
GitHub 웹 업로드에서 폴더가 안 올라가는 경우를 위해 모든 파일을 저장소 맨 바닥(root)에 놓는 버전입니다.

## 올리는 방법

1. 이 ZIP을 압축 해제합니다.
2. `aeo_lab_flat_upload` 폴더 안으로 들어갑니다.
3. 그 안에 보이는 모든 파일을 GitHub 업로드 화면에 한 번에 드래그합니다.
4. GitHub 저장소 맨 바닥에 `index.html`, `main.py`, `js_00_state.js`, `css_00_root_base.css` 등이 바로 보여야 합니다.

## 주의

- `aeo_lab_flat_upload` 폴더 자체를 저장소 안에 넣지 마세요.
- ZIP 파일 그대로 올리지 마세요.
- 기존 큰 `app.js`, 큰 `style.css`는 이 버전에서는 쓰지 않습니다.
- 브라우저에서는 `/assets/js_...`, `/assets/css_...` 주소로 읽지만, 실제 폴더는 없습니다. `main.py`가 루트 파일만 안전하게 서빙합니다.


## 이번 추가 수정
- 새 토론 기본 선택 페르소나를 BrandStrategist에서 AICommerceHacker로 변경했습니다.
- 브랜드 메시지 적합도는 데이터/콘텐츠/AI Commerce/UX와 같은 5개 축 중 하나로 표시됩니다.
