# Problem Set Tracker

ICPC 캠프, CERC, WF 등 경쟁 프로그래밍 problem set의 풀이 트래킹 + 퀄리티 평가 서비스.

## Stack

- Python 3.12 + Django 5.x
- HTMX + Alpine.js (프론트엔드 인터랙션)
- Tailwind CSS + DaisyUI (스타일)
- PostgreSQL 16 (local: docker compose / prod: Fly Postgres)
- django-allauth (Google + GitHub OAuth)
- django-treebeard (ProblemSet 트리)
- 호스팅: Fly.io
- 패키지 매니저: uv

## 핵심 문서

기능을 구현하기 전에 항상 아래 두 문서를 참조한다.

- 기능 명세: `docs/spec.md` (v0.2)
- 아키텍처: `docs/architecture.md` (v0.1)

명세나 아키텍처와 충돌하는 구현은 하지 말 것. 충돌이 보이면 먼저 알릴 것.

## 프로젝트 구조

`docs/architecture.md` §3.1 참조. 핵심만 요약:

```
config/         # 프로젝트 설정 (settings/base.py, dev.py, prod.py 분리)
apps/
  accounts/     # User 확장, 프로필, 가시성
  sources/      # Source CRUD
  problemsets/  # ProblemSet (treebeard 트리), Problem
  solving/      # SolveRecord
  ratings/      # Rating, Comment
  teams/        # Team, TeamMember, TeamInvite
  proposals/    # 사용자 제안 + 어드민 검토 큐
  notifications/ # 인앱 알림 (P2)
templates/
static/
tests/
```

## 컨벤션

### 코드 스타일

- Linter/Formatter: `ruff` (단일 도구, format + lint 통합)
- 모든 함수에 type hint. Optional은 `X | None` 표기.
- import 순서: ruff isort 룰 따름 (자동 정렬됨).
- docstring은 public 함수/클래스에만, 한 줄 요약 + 필요 시 상세.

### Django 관련

- 모델 정의 시 반드시 `Meta.ordering` 명시.
- `null=True`와 `blank=True`는 의미 구분: null=DB, blank=폼.
- 마이그레이션 파일은 **절대 수정하지 말 것**. 변경이 필요하면 새 마이그레이션 추가.
- 템플릿에서 `|safe` 사용 금지 (XSS 위험).
- `@login_required` / 권한 데코레이터는 view 단에서 명시적으로.
- private 자원 비인가 접근은 403이 아니라 **404 Not Found** 반환 (존재 자체 비노출).

### HTMX

- 뷰는 두 가지 모드 지원: full HTML (직접 URL) vs partial HTML (`HX-Request` 헤더 있을 때).
- 응답 헤더 `HX-Trigger`로 다른 영역 동기화 갱신.
- CSRF 토큰은 `htmx.config`에서 자동 헤더 전송 설정.

### 테스트

- Framework: pytest-django.
- 우선 커버 영역: 권한·가시성 룰, Rating UPSERT, SolveRecord 토글, 트리 이동.
- 팩토리는 factory_boy로 작성.
- 테스트는 같은 PR 안에 포함.

## 워크플로우

### 단계별 진행

`docs/architecture.md` §10의 단계 순서를 따른다 (0. 부트스트랩 → 8. 마무리).
각 단계는 **배포 가능한 상태로 종료**. 단계 중간에 다음 단계 작업 섞지 말 것.

### 커밋 전 체크

```bash
ruff check .
ruff format .
uv run pytest
```

위 셋이 모두 통과해야 커밋. 가능하면 pre-commit hook으로 자동화.

### 커밋 메시지

- Conventional Commits 따름 (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).
- 제목은 한 줄 50자 이내, 영문 또는 한글 가능.
- 본문은 "왜"를 적음. "무엇"은 diff에 이미 있음.

### 브랜치

- `main`: 항상 배포 가능한 상태.
- 기능 작업은 `feat/<short-name>` 브랜치에서, PR로 머지.
- 머지 후 main push되면 GitHub Actions가 Fly로 자동 배포.

## 환경 / 시크릿

- 로컬: `.env` 파일 (git ignore). django-environ으로 로딩.
- 프로덕션: `fly secrets set ...`로 주입.
- 절대 시크릿을 코드나 git에 넣지 말 것.

필수 환경 변수:
- `DJANGO_SETTINGS_MODULE` (`config.settings.dev` 또는 `config.settings.prod`)
- `SECRET_KEY`
- `DATABASE_URL`
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`
- `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`
- `SENTRY_DSN` (prod)
- `ALLOWED_HOSTS` (prod, 쉼표 구분)

## 주의 사항

- 새 의존성을 추가하기 전에 `docs/architecture.md` 부록 A의 라이브러리 목록을 확인. 거기 없으면 일단 그 이유를 설명.
- 모델 변경은 마이그레이션을 함께 생성 (`uv run manage.py makemigrations`).
- 트리 구조 변경(treebeard) 시 dev DB에서 `check_consistency` 명령으로 사전 검증.
- Tailwind 클래스 충돌 방지: 컴포넌트는 `templates/components/`에 partial로 분리.
- 1인 개발자 + 학습 중인 점을 고려해 작업을 작은 단위로 쪼갤 것. 한 번에 너무 많은 변경 X.

## 작업 시작 시 확인

새 작업을 시작할 때 다음을 먼저 확인하고 시작:

1. `docs/spec.md`와 `docs/architecture.md`에서 관련 섹션 확인
2. 기존 코드에 비슷한 패턴이 있는지 확인 (있으면 따라할 것)
3. 작업이 여러 단계로 나뉜다면 todo 리스트를 먼저 제시