# GitHub 업로드 안내

이 버전은 `static/` 폴더를 쓰지 않습니다.
프로젝트 최상위에 `js/`, `css/` 폴더가 바로 있어야 합니다.

업로드할 때는 이 폴더 안의 전체 내용을 그대로 드래그해서 올리세요.

필수 구조:

```text
aeo_lab_root_split/
  css/
  js/
  analyzer.py
  crawler.py
  database.py
  discussion.py
  Dockerfile
  export.py
  file_handler.py
  gemini_llm.py
  index.html
  main.py
  persona.py
  README.md
  render.yaml
  requirements.txt
```

기존의 큰 `app.js`, 큰 `style.css`는 이 버전에서는 쓰지 않습니다.
`index.html`이 `/css/*.css`, `/js/*.js`를 순서대로 직접 불러옵니다.
