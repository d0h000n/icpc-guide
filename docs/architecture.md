# Problem Set 트래커 — 기술 스택 + 아키텍처

**Version:** v0.2
**작성일:** 2026-05-05 (v0.2 갱신: 2026-05-08)

---

## 변경 이력

| 버전 | 일자 | 주요 변경 |
|---|---|---|
| v0.1 | 2026-05-05 | 초기 작성 (spec v0.2 기반) |
| v0.2 | 2026-05-08 | spec v0.4 동기화: Source → Category 리네임 + 의미 변경 (M2M), ProblemAppearance 도입(N—M Problem), Season 제거, 인덱스 표 갱신 |

---

## 1. 의사결정 요약

기능 명세서 v0.4 기반의 기술 선택 결과.

| 계층 | 선택 | 근거 요약 |
|---|---|---|
| 언어 | Python 3.12+ | 1인 개발 + 학습 부담 최소화. AI 출력 정확도 최상. 풍부한 생태계. |
| 웹 프레임워크 | Django 5.x | Admin 자동 생성 (S7 화면이 거의 무료). 인증·ORM·마이그레이션 빌트인. 명세의 폼·CRUD·트리 워크로드와 잘 맞음. |
| 프론트엔드 인터랙션 | HTMX + Alpine.js (선택적) | 별점 토글, 트리 펼치기/접기, 팀 컨텍스트 드롭다운 등 명세의 인터랙션을 SPA 없이 처리. SSR 기본 + 부분 갱신. |
| 인증 | django-allauth | Google + GitHub OAuth. 표준. 마찰 적음. |
| 트리 구조 | django-treebeard (Materialized Path) | ProblemSet의 무제한 깊이 트리. parent_set_id 단순 자기참조 대비 조회 효율 우수. |
| DB | PostgreSQL 16 | 트리 조회·집계 쿼리에 강함. Fly Postgres로 운영. |
| 백그라운드 작업 | django-q2 또는 안 씀(MVP) | 알림·집계는 동기로 충분. 필요 시 후속에 추가. |
| 호스팅 | Fly.io ($5~/월) | Always-on, 콜드 스타트 없음. 1인 운영 부담 낮음. |
| 스토리지 | Fly Volumes (정적 파일) + WhiteNoise | S3 등 외부 스토리지 V1 미사용. |
| CSS / UI 컴포넌트 | Tailwind CSS + DaisyUI | 1인 개발자 친화. JS 빌드 없이 CDN 가능, 또는 django-tailwind. |
| 에러 추적 | Sentry Free | 월 5천 이벤트 무료. 1인 운영 필수. |

---

## 2. 시스템 아키텍처

### 2.1 컴포넌트 다이어그램 (논리)

V1은 단순한 모놀리식 구조. 트래픽 적음 + 1인 개발이라는 제약을 고려한 설계.

```
┌──────────────────────────────────────────────────────────────────┐
│                         Browser (Client)                          │
│   - HTML + HTMX (부분 갱신) + Alpine.js (소규모 클라이언트 상태)  │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────▼─────────────────────────────────────┐
│                       Fly.io Edge / Proxy                         │
│           (TLS 종료, IPv4/IPv6 라우팅, HTTP/2)                    │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│                Django App (Gunicorn, 1~2 worker)                  │
│  ┌─────────────┐ ┌──────────────┐ ┌────────────────────────┐    │
│  │ Public 뷰   │ │ User 뷰      │ │ Admin (Django Admin)   │    │
│  │ (트리/상세) │ │ (별점/팀 등) │ │ (Category/Set CRUD, 검토)│    │
│  └─────────────┘ └──────────────┘ └────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  django-allauth | django-treebeard | WhiteNoise | ORM    │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│                  PostgreSQL (Fly Postgres)                        │
│       동일 organization 내, private network 통해 접근            │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 핵심 설계 원칙

- 단일 모놀리식 Django 앱. 마이크로서비스 분리는 V1 범위 외.
- SSR 기본 + HTMX 부분 갱신. SPA 빌드 파이프라인 없음.
- 모든 동기 처리. 큐/워커 도입은 P3 알림·자동 난이도 산정 단계에서 고려.
- Admin 화면은 Django Admin 활용. 커스텀 어드민 페이지는 "제안 검토 큐" 등 일부만 직접 구현.
- 정적 파일은 WhiteNoise로 Django가 직접 서빙 (CDN 불필요한 트래픽 수준).
- 파일 업로드 없음. 이미지(solved.ac 로고)는 정적 에셋으로 번들.

### 2.3 요청 라이프사이클 (전형 사례)

"ProblemSet 상세에서 별점을 5점으로 변경" 시나리오:

1. 브라우저: 별점 5점 클릭 → HTMX가 `hx-post`로 `/sets/<id>/rate/` 호출.
2. Fly Edge: HTTPS 종료, Django 컨테이너로 라우팅.
3. Django: CSRF 검사 → 인증 체크 → Rating UPSERT → 평균 별점 재계산.
4. Django: 응답으로 별점 영역 + 평균 별점 영역의 부분 HTML만 반환 (HTMX OOB swap).
5. 브라우저: HTMX가 해당 영역만 교체. 페이지 리로드 없음.

---

## 3. Django 앱 구조

### 3.1 프로젝트 레이아웃

```
ps_tracker/                    # Django 프로젝트 루트
├── manage.py
├── pyproject.toml             # uv 또는 poetry
├── Dockerfile
├── fly.toml
├── config/                    # 프로젝트 설정
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/              # User 확장, 프로필, 가시성
│   ├── categories/            # Category CRUD (구 sources/, v0.4에서 리네임)
│   ├── problemsets/           # ProblemSet (트리), Problem
│   ├── solving/               # SolveRecord
│   ├── ratings/               # Rating, Comment
│   ├── teams/                 # Team, TeamMember, TeamInvite
│   ├── proposals/             # CategoryProposal, ProblemSetProposal
│   └── notifications/         # 인앱 알림 (P2)
├── templates/
│   ├── base.html
│   ├── components/            # 재사용 partial (별점 위젯, 트리 노드 등)
│   └── <app>/
├── static/
│   ├── css/                   # tailwind.css 컴파일 산출물
│   ├── js/                    # alpine.min.js, htmx.min.js
│   └── img/solved_ac/         # 티어 로고 정적 에셋
└── tests/
```

### 3.2 앱별 책임

| 앱 | 주요 모델 | 주요 책임 |
|---|---|---|
| accounts | User (확장), ProfileVisibility | OAuth 로그인 후속 처리, 닉네임/외부 핸들 편집, 가시성 설정, 마이페이지 |
| categories | Category, CategoryMembership | Category CRUD (Admin), Category 목록 페이지, ProblemSet과 M2M |
| problemsets | ProblemSet (treebeard), Problem | 트리 조회/상세, 부모-자식 네비게이션, 어드민 트리 관리 |
| solving | SolveRecord | 토글 엔드포인트, 완주율 계산 (개인·팀·내부 노드) |
| ratings | Rating, Comment | 별점 UPSERT, 코멘트 CRUD, 평가자 목록 |
| teams | Team, TeamMember, TeamInvite | 팀 생성/초대/owner 이양, 팀 컨텍스트 보기 |
| proposals | CategoryProposal, ProblemSetProposal | 사용자 제안 폼 + 어드민 검토 큐 |
| notifications | Notification (P2) | 인앱 알림 생성·열람 |

---

## 4. 데이터 액세스

### 4.1 트리 구조 구현

ProblemSet은 무제한 깊이 트리. 단순 parent_set_id 자기참조는 "부모 체인 조회"·"하위 전체 조회"가 N+1 또는 재귀 쿼리가 되어 비용이 크다.

- 선택: django-treebeard의 Materialized Path (MP) 트리.
- 각 노드는 `path` 컬럼(예: `"0001000200030004"`)으로 위치 인코딩.
- 부모 체인: path prefix LIKE 쿼리 1회. 자식 전체: `path LIKE 'PARENT_PATH%'`.
- 이동 시 자식 path 일괄 갱신은 treebeard가 처리.
- 대안 검토: closure table (django-tree-queries) — 더 유연하나 1인 개발자에겐 treebeard가 학습 비용 낮음.

### 4.2 핵심 인덱스

| 테이블 | 인덱스 | 용도 |
|---|---|---|
| problemset | (year) | 연도 범위 필터 (year_from/year_to) |
| categorymembership | (category_id, problem_set_id) UNIQUE | M2M 멤버십 |
| categorymembership | (problem_set_id) | "이 ProblemSet은 어떤 카테고리에 속하나" 조회 |
| problemset | (path) | treebeard 기본 (자동 생성) |
| problemappearance | (problem_set_id, order_index) UNIQUE | set 내 문제 정렬 조회 |
| problemappearance | (problem_set_id, label) UNIQUE | 라벨 중복 방지 |
| problemappearance | (problem_id, problem_set_id) UNIQUE | 같은 set에 같은 Problem 두 번 등장 방지 |
| problemappearance | (problem_id) | "이 문제는 어디에 등장했는가" 조회 |
| solverecord | (user_id, problem_id) UNIQUE | 토글 UPSERT, 개인 완주 조회 |
| solverecord | (problem_id) | 팀 컨텍스트에서 "이 문제를 푼 멤버" 조회 |
| rating | (user_id, problem_set_id) UNIQUE | UPSERT |
| rating | (problem_set_id) | 평균 별점·평가 수 집계 |
| comment | (problem_set_id, created_at DESC) | 코멘트 목록 |
| teammember | (user_id), (team_id) | 내 팀 목록, 팀 멤버 목록 |
| teaminvite | (token) UNIQUE | 초대 링크 검증 |

### 4.3 집계 전략

"평균 별점", "평가 수", "완주율"은 자주 조회되지만 실시간성이 그렇게까지 중요하지 않다.

- V1: 매 요청마다 ORM의 aggregate (AVG, COUNT)로 계산. 트래픽 적음 + 인덱스 충분 → 충분히 빠름.
- Django의 `select_related`/`prefetch_related` 적극 사용.
- 문제가 생기면 P2에서 ProblemSet에 denormalized 컬럼(rating_avg, rating_count) 추가 + signal 또는 주기 batch로 갱신.
- 내부 노드 완주율은 자식 path prefix 쿼리 1회 + Python 측 합산.

### 4.4 마이그레이션 전략

- Django 마이그레이션 파일은 git으로 관리. 수정 금지 원칙 (배포 후엔 새 마이그레이션 추가).
- 프로덕션 배포는 `fly deploy` 시 release_command로 `manage.py migrate` 자동 실행.
- Schema 변경 중 다운타임 회피는 V1에선 신경쓰지 않음 (트래픽 매우 적음).

---

## 5. 인증 / 권한

### 5.1 인증 흐름 (django-allauth)

- `/accounts/google/login/` 또는 `/accounts/github/login/` → OAuth 동의 화면.
- 콜백 후 allauth가 SocialAccount 생성, 이메일 매칭으로 기존 User 연결 또는 신규 생성.
- 최초 가입 시 닉네임·외부 핸들 입력 페이지로 강제 리다이렉트 (signup adapter 커스텀).
- 이후 표준 Django 세션 (HTTP-only, SameSite=Lax 쿠키).
- 로그아웃은 세션 폐기 + OAuth provider 토큰 폐기 (allauth 기본 동작).

### 5.2 권한 체크 위치

| 대상 | 체크 방식 |
|---|---|
| Admin 전용 액션 | `@user_passes_test(lambda u: u.is_staff)` 또는 `PermissionRequiredMixin` |
| 로그인 전용 액션 | `@login_required` (별점, 토글, 코멘트, 팀 작업 등) |
| 자원 소유자 체크 | view 내부에서 user_id 비교 (SolveRecord, Rating, Comment 본인만 수정) |
| 팀 멤버 체크 | `TeamMembershipRequiredMixin` 커스텀 (팀 컨텍스트 보기, 팀 상세 진입) |
| 가시성 체크 | Custom queryset filter + view-level 분기 (§5.3) |

### 5.3 가시성 룰 적용

§4.6.3의 가시성 조합 룰을 코드에 매핑하는 방식.

- 프로필 조회 view: 대상 `User.profile_visibility == public`이거나 본인이면 풀 정보, 아니면 닉네임만.
- 팀 페이지 view: `Team.visibility == public`이거나 멤버이면 진입 허용. private + 비멤버는 404.
- 팀 페이지 내 멤버별 풀이 상세는 (a) 본인이거나 (b) 같은 팀 멤버이거나 (c) 멤버의 `profile_visibility == public`이면 노출.
- 핵심 원칙: "존재 자체 비노출"이 필요한 자원(private 팀)은 "권한 없음 403" 대신 "404 Not Found" 반환.

### 5.4 Admin 권한 모델

- Django의 `is_staff = True`인 사용자가 본 시스템의 Admin.
- 최초 admin은 `manage.py createsuperuser` 또는 `fly secrets`로 시드.
- admin 승격은 Django Admin의 User 편집 화면에서 `is_staff` 체크.
- 감사 로그는 Django의 LogEntry (`django.contrib.admin.models`)로 기본 기록 + 커스텀 액션은 별도 AuditLog 모델로 보강.

---

## 6. 프론트엔드 전략

### 6.1 HTMX 사용 패턴

- `hx-get`/`hx-post`로 부분 HTML 응답을 받아 DOM 영역 교체.
- 주요 인터랙션: 별점 클릭, 해결 토글, 트리 펼치기/접기, 팀 컨텍스트 드롭다운, 평가자 목록 모달, 초대 링크 발급.
- 뷰는 두 가지 모드를 지원: full HTML (직접 URL 접근) vs partial HTML (`HX-Request` 헤더 있을 때). 데코레이터 또는 헬퍼로 추상화.
- `HX-Trigger` 응답 헤더로 다른 영역 동기화 갱신 (예: 별점 변경 시 평균 별점 영역 트리거).

### 6.2 Alpine.js 보조 사용

- 서버 왕복이 불필요한 작은 클라이언트 상태에만 사용 (드롭다운 열림, 모달 열림, 폼 텍스트 카운터).
- 코멘트 입력 박스의 "300자 카운터", "별점 호버 미리보기" 등.
- 필요 없으면 도입 안 함. HTMX만으로 충분한 경우가 많음.

### 6.3 스타일링

- Tailwind CSS + DaisyUI (사전 정의된 컴포넌트 클래스). dark 모드는 V1에선 보류.
- django-tailwind 또는 단순 npm script로 빌드. 결과 css 1개 파일을 WhiteNoise로 서빙.
- 아이콘은 Heroicons 또는 Lucide의 SVG 인라인.

### 6.4 프론트 의존 최소화

- npm/Node 빌드를 가능한 단순화. tailwind 컴파일 외에는 빌드 단계 없음.
- CDN 사용 가능: htmx.org, alpinejs는 production에서도 CDN 권장 (캐시 효과).
- 프론트엔드 라우터/번들러/프레임워크 도입 금지.

---

## 7. 인프라 / 배포

### 7.1 Fly.io 토폴로지

- Fly App 1개 (Django + Gunicorn).
- Fly Postgres 1개 (단일 노드, 같은 region).
- Region: `nrt` (도쿄) 또는 `sin` (싱가포르). 한국 사용자 RTT 고려.
- Machine: shared-cpu-1x, 256~512MB RAM. Django + Gunicorn 1~2 worker에 충분.
- Auto-stop은 끔 (콜드 스타트 회피, 명세의 "항상 가용" 가치 우선). 항상 1대 가동.
- Fly의 IPv4 비용($2/월)은 발생. 총 월 비용 예상 ~$5-7.

### 7.2 컨테이너 / 빌드

- Dockerfile: `python:3.12-slim` 베이스. 멀티스테이지로 빌드 의존성과 런타임 분리.
- 패키지 매니저: `uv` (빠른 설치) 또는 poetry.
- 정적 파일은 빌드 시점 `collectstatic`으로 번들. WhiteNoise가 압축·해시 캐시 헤더 처리.
- Gunicorn: 2 worker, gevent worker class는 안 씀 (sync로 충분).

### 7.3 환경 / 시크릿

- 환경별 settings (`config/settings/dev.py`, `prod.py`). `DJANGO_SETTINGS_MODULE`로 분기.
- 시크릿: `fly secrets set`으로 SECRET_KEY, DATABASE_URL, GOOGLE_OAUTH_*, GITHUB_OAUTH_*, SENTRY_DSN 등 설정.
- 로컬 개발: `.env` (git ignore) + django-environ. dev DB는 sqlite 또는 docker compose의 postgres.

### 7.4 배포 파이프라인

- GitHub Actions: PR 시 lint(ruff) + test(pytest-django) 실행.
- main 브랜치 push 시 `fly deploy` 자동 실행 (FLY_API_TOKEN 시크릿 사용).
- 배포 시 release_command로 `manage.py migrate` 자동 실행. 마이그레이션 실패 시 새 인스턴스 롤아웃 중단.
- 롤백: `fly releases list` + `fly deploy --image <previous_image>`.

### 7.5 백업

- Fly Postgres는 일일 자동 snapshot 제공 (보존 기간 설정 가능).
- 추가로 주 1회 `pg_dump` → 외부 저장소 (예: Backblaze B2 또는 GitHub release 비공개 저장)로 미러 백업 권장.
- 복원 절차는 별도 runbook 문서로 작성 (V1 출시 전 1회 리허설).

### 7.6 관측 / 운영

| 관심사 | 도구 | 설정 |
|---|---|---|
| 에러 추적 | Sentry Free | `sentry-sdk[django]` 설치 + DSN. 5천 이벤트/월. |
| 로그 | Fly logs | stdout/stderr → Fly가 수집. structlog로 JSON 출력 권장. |
| 가용성 모니터링 | UptimeRobot 무료 | 5분 주기 ping. 다운 시 이메일. |
| 성능 (선택) | Django Debug Toolbar | dev only. prod는 PG slow query log. |
| 메트릭 (선택) | Fly metrics | 기본 CPU/RAM/요청. V1엔 충분. |

---

## 8. 보안 체크리스트

- `DEBUG=False`, `ALLOWED_HOSTS` 명시 (prod).
- `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` 모두 True.
- CSRF: Django 기본 동작 사용. HTMX는 csrftoken을 헤더로 자동 전송 설정.
- XSS: 코멘트·메모 출력 시 Django의 자동 escape에 의존. `|safe` 사용 금지. Markdown 도입 시 bleach로 sanitize.
- Rate limit: `django-ratelimit`으로 별점/코멘트/제안 엔드포인트에 적용 (예: 사용자당 분당 30회).
- Brute force: allauth가 OAuth 전용이므로 비밀번호 brute force 위험 없음.
- OAuth callback URL은 Google·GitHub 콘솔에서 정확히 등록 (오픈 리다이렉트 회피).
- 사용자 입력에서 ProblemSet ID·Team ID 등은 정수/UUID 검증.
- Admin URL은 `/admin` 대신 추측 어려운 경로로 변경 (보안 가산점).
- 의존성 업데이트는 dependabot 또는 renovate 권장.

---

## 9. 개발 환경

### 9.1 로컬 셋업

- Python 3.12 + uv 설치.
- docker compose로 postgres 16 띄움 (또는 sqlite로 시작).
- `uv sync` → `manage.py migrate` → `manage.py runserver`.
- OAuth 로컬 테스트: ngrok 또는 cloudflared로 외부 노출 + 콜백 URL 등록.

### 9.2 코드 품질

- Linter: `ruff` (format + lint 통합).
- Type check: `mypy` + django-stubs (선택).
- Pre-commit hook: `ruff` + `django-upgrade` + check migrations.

### 9.3 테스트 전략

- 프레임워크: pytest-django.
- V1 우선 커버: 권한·가시성 룰 (§5.3), Rating UPSERT, SolveRecord 토글, 트리 이동 시 자식 path 갱신.
- UI 테스트는 V1에선 생략. 수동 QA 체크리스트로 갈음.
- 팩토리: factory_boy.

---

## 10. 단계별 구축 계획

MVP까지의 권장 순서. 각 단계는 "배포 가능한 상태"로 종료.

| 단계 | 내용 | 산출물 |
|---|---|---|
| 0. 부트스트랩 | Django 프로젝트 생성, Fly 배포 파이프라인, OAuth 로그인 동작 확인 | "Hello, [닉네임]"이 OAuth 후 보임 |
| 1. 데이터 모델 | Category, ProblemSet (treebeard), Problem, ProblemAppearance 모델 + Django Admin 노출 | Admin에서 트리 입력 + 카테고리 묶기 가능 |
| 2. 공개 조회 | 트리 페이지, 상세 페이지 (Guest 가능). 정렬·필터 일부 | 비로그인으로도 set 열람 가능 |
| 3. 풀이 트래킹 | SolveRecord 토글 (HTMX), 개인 완주율 표시 | 본인 완주 % 표시 |
| 4. 별점·코멘트 | Rating UPSERT, Comment 작성/편집, 평균 별점, 평가자 목록 | S2 화면 핵심 인터랙션 완료 |
| 5. 가시성 | User.profile_visibility, 마이페이지, 가시성 조합 룰 적용 | S4 화면 동작 |
| 6. 팀 | Team CRUD, 초대 링크, 팀 컨텍스트 보기 | S5/S6 화면 동작 |
| 7. 사용자 제안 | CategoryProposal, ProblemSetProposal + 어드민 검토 큐 | S3, S7 탭3 완료 |
| 8. 마무리 | Sentry, 백업 자동화, runbook, 1차 QA 패스 | MVP 출시 가능 |

각 단계가 끝날 때마다 main에 머지 → Fly 자동 배포 → 본인이 실제 사용하면서 검증. 1인 + 학습 중인 점을 고려해 단계별 사이클을 짧게 유지.

---

## 11. 향후 진화 (참고)

- V1.1 인앱 알림 (P2) — 단순 모델 + 폴링 또는 HTMX SSE.
- V1.2 마이페이지 통계 강화 (P2) — 풀이 추세 그래프 등.
- V2 스코어보드 기반 자동 난이도 (P3) — 백그라운드 작업 (django-q2 또는 cron) + 외부 스코어보드 fetcher.
- V2 solved.ac API 연동 (P3) — 야간 batch sync.
- V2 i18n (P3) — 영어 번역.
- 스케일 시 고려사항: 평균 별점·완주율 denormalize, Redis 캐시, 리드 레플리카, S3 이전. 모두 트래픽이 명확히 증가하기 전엔 도입하지 않음.

---

## 12. 위험 요소 / 완화책

| 위험 | 영향 | 완화 |
|---|---|---|
| 1인 개발 시간 부족 | MVP 지연 | 단계별 점진 배포. 매 단계가 "중단해도 쓸 수 있는" 상태. |
| Django + HTMX 학습 곡선 | 초기 진척 느림 | 단계 0에서 OAuth + 한 페이지로 패턴 확립. 이후 복붙 발전. |
| 트리 마이그레이션 실수 | 데이터 깨짐 | treebeard는 검증 명령(`check_consistency`) 제공. 배포 전 dev DB에서 시뮬레이션. |
| Fly $5 한도 초과 (디스크/볼륨/IP) | 예상 외 청구 | `fly billing` 한도 알림 설정. 매월 초 체크. |
| solved.ac 로고 라이선스 | 법적 이슈 | 출시 전 운영자 정책 확인. 불가 시 자체 simplified 아이콘 사용. |
| OAuth 콜백 설정 실수 | 로그인 불가 | dev/staging/prod 콜백 URL을 문서화. allauth 설정 코드 리뷰. |
| 트래픽이 갑자기 늘 경우 | DB 또는 머신 부하 | Fly에서 머신 스케일업은 한 줄. 지표 임계 알림 설정. |

---

## 부록 A. 주요 라이브러리 목록

| 용도 | 패키지 |
|---|---|
| 웹 프레임워크 | `django>=5.1` |
| OAuth | `django-allauth[socialaccount]` (google, github) |
| 트리 구조 | `django-treebeard` |
| 설정/시크릿 | `django-environ` |
| 정적 파일 | `whitenoise` |
| DB 드라이버 | `psycopg[binary]>=3` |
| Rate limit | `django-ratelimit` |
| 에러 추적 | `sentry-sdk[django]` |
| WSGI 서버 | `gunicorn` |
| 테스트 | `pytest`, `pytest-django`, `factory_boy` |
| Lint/Format | `ruff` |
| 타입 체크 (선택) | `mypy`, `django-stubs` |
| 프론트 | `htmx` (CDN 또는 정적), `alpine.js` (CDN) |
| CSS | `tailwindcss` + `daisyui` (django-tailwind 또는 npm script) |