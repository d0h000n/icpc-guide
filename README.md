# Problem Set Tracker

ICPC 캠프, CERC, WF 등 경쟁 프로그래밍 problem set의 풀이 트래킹 + 퀄리티 평가 서비스.

기능 명세는 `docs/spec.md`, 아키텍처는 `docs/architecture.md`. 작업 가이드는 `CLAUDE.md`.

## 로컬 개발 (단계 0)

```bash
# 1. uv 설치 (한 번만)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 의존성 동기화
uv sync

# 3. .env 준비
cp .env.example .env
# .env 안의 OAuth 자격증명을 채울 것 (아래 OAuth 셋업 참고)

# 4. (선택) Postgres 띄우기 — 처음 시도면 SQLite로도 충분
docker compose up -d postgres
# 그 후 .env에서 DATABASE_URL 주석 해제

# 5. 마이그레이션 + 실행
uv run python manage.py migrate
uv run python manage.py runserver
```

`http://localhost:8000` 접속 → 로그인 → 닉네임 입력 → "Hello, [닉네임]" 노출되면 단계 0 동작 확인 완료.

## 데이터 일괄 입력 (YAML import/export)

Problem set과 문제 데이터는 admin에서 한 줄씩 입력하는 대신 YAML 파일로 한 번에
넣을 수 있다. 트리 구조 그대로 표현 가능하고, 동일 파일을 다시 돌려도 멱등.

```bash
# 단일 파일 import
uv run python manage.py import_problemsets data/example.yml

# 디렉토리 통째 import
uv run python manage.py import_problemsets data/

# 어떤 변경이 일어날지만 출력 (DB는 안 건드림)
uv run python manage.py import_problemsets --dry-run data/example.yml

# 기존 데이터를 YAML로 내보내기 (편집 후 다시 import 사이클)
uv run python manage.py export_problemsets > data/all.yml
uv run python manage.py export_problemsets ICPC > data/icpc.yml         # 특정 루트만
uv run python manage.py export_problemsets --to data/icpc.yml ICPC      # 파일로 직접
```

YAML 형식 예시는 `data/example.yml` 참고. 핵심:

- `categories:` 블록에서 카테고리 선언, `problem_sets:` 블록에서 트리 정의
- 트리는 `children:` 중첩으로 자연스럽게 표현
- 같은 `title`을 가진 Problem은 **canonical로 재사용** (한 문제가 두 set에 등장 = 자동 dedup, 한 번 풀면 양쪽 모두 solved)
- `tier`는 solved.ac 정수(1=Bronze V ~ 30=Ruby I)
- `categories: [japan, icpc]` 처럼 다중 태그 가능. 같은 트리의 조상-자손 관계엔 같은 카테고리 중복 등록 안 됨 (자동 거부)

## 커밋 전 체크

```bash
uv run ruff check .
uv run ruff format .
uv run pytest
```

## OAuth 셋업 (수동)

각각의 콘솔에서 클라이언트 발급 후 `.env`에 입력.

| Provider | 콘솔 | Authorized redirect URI (로컬) |
|---|---|---|
| Google | https://console.cloud.google.com/apis/credentials | `http://localhost:8000/accounts/google/login/callback/` |
| GitHub | https://github.com/settings/developers | `http://localhost:8000/accounts/github/login/callback/` |

프로덕션 도메인이 정해지면 콜백 URI를 추가 등록.

## Fly 배포 (단계 0 — 최초 1회 셋업)

```bash
# 1. fly CLI 설치 후
fly auth login
fly launch --no-deploy   # fly.toml은 이미 있으니 기존 설정 사용
fly postgres create --name ps-tracker-db --region nrt
fly postgres attach ps-tracker-db --app ps-tracker

# 2. 시크릿 주입
fly secrets set \
  SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')" \
  ALLOWED_HOSTS="ps-tracker.fly.dev" \
  CSRF_TRUSTED_ORIGINS="https://ps-tracker.fly.dev" \
  GOOGLE_OAUTH_CLIENT_ID=... \
  GOOGLE_OAUTH_CLIENT_SECRET=... \
  GITHUB_OAUTH_CLIENT_ID=... \
  GITHUB_OAUTH_CLIENT_SECRET=...

# 3. 첫 배포
fly deploy
```

이후 main 브랜치 push 시 GitHub Actions가 자동 배포 (GitHub repo에 `FLY_API_TOKEN` 시크릿 등록 필요).
