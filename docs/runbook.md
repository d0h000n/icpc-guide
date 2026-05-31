# Runbook — Problem Set Tracker

운영 중 발생할 수 있는 상황별 대응 매뉴얼. 위급 상황에서 위에서부터 차례로 읽어도 되도록 시간 순으로 정렬했다.

## 0. 좌표

| 항목 | 값 |
|---|---|
| 호스팅 | Fly.io |
| 앱 이름 | `ps-tracker` (fly.toml) |
| 리전 | `nrt` (도쿄) |
| DB | Fly Postgres (별도 cluster) |
| 도메인 | `https://ps-tracker.fly.dev` (커스텀 도메인은 미설정) |
| 에러 추적 | Sentry Free (DSN은 `fly secrets`로 주입) |
| 헬스 체크 | `GET /healthz` → "ok" |
| CI/CD | GitHub Actions (`.github/workflows/ci.yml` + `deploy.yml`) |

## 1. 매일 5분 점검 (수동 또는 봇)

1. `https://ps-tracker.fly.dev/healthz` — 200 OK 인지
2. Sentry 대시보드 — 신규 이슈 알람 있는지
3. `fly status -a ps-tracker` — 모든 machine "started" / 검사 통과
4. `fly logs -a ps-tracker | head -100` — 비정상 ERROR 로그 없는지

## 2. 배포 / 롤백

### 일반 배포
`main` 브랜치에 push 하면 GitHub Actions `Deploy` job이 자동으로 `fly deploy --remote-only` 실행. release command (`python manage.py migrate --noinput`)가 먼저 돌고, 실패 시 새 이미지는 활성화되지 않는다.

### 수동 배포 (로컬에서)
```bash
fly auth login
fly deploy --remote-only -a ps-tracker
```

### 롤백
```bash
fly releases list -a ps-tracker            # 직전 안정 버전의 image 확인
fly deploy --remote-only --image <prev>    # 그 이미지로 재배포
```
release_command 마이그레이션이 깨졌으면 새 머신이 절대 활성화되지 않는다 → 사용자 영향 0. 코드만 되돌리고 다시 push 해도 됨.

### 마이그레이션이 실수로 들어가서 데이터가 망가졌다면
- `pg_dump`로 백업해둔 게 있으면 → §5의 복원 절차
- 없으면 § Fly Postgres snapshot 복원 (역시 §5)

## 3. 시크릿 / 환경 변수

### 현재 등록해야 하는 시크릿 (prod)
| 키 | 용도 |
|---|---|
| `SECRET_KEY` | Django session/CSRF 서명 |
| `DATABASE_URL` | Fly Postgres attach 시 자동 주입 |
| `ALLOWED_HOSTS` | 쉼표 구분 — 보통 `ps-tracker.fly.dev` |
| `CSRF_TRUSTED_ORIGINS` | 쉼표 구분 — `https://ps-tracker.fly.dev` |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` | Google OAuth |
| `GITHUB_OAUTH_CLIENT_ID` / `_SECRET` | GitHub OAuth |
| `SENTRY_DSN` | 에러 추적. 비워두면 Sentry 비활성 |
| `SENTRY_ENVIRONMENT` | (선택) `prod` / `staging` 구분 |
| `DEFAULT_FROM_EMAIL` | (선택) 알림 메일 발송용 |

### 시크릿 설정/회전
```bash
fly secrets set SENTRY_DSN="https://...@sentry.io/..." -a ps-tracker
fly secrets unset SOME_KEY -a ps-tracker
fly secrets list -a ps-tracker            # 값은 가려져 표시됨
```
시크릿 변경 시 자동 재배포된다. 한 번에 여러 개 설정해 재배포 횟수를 줄일 것:
```bash
fly secrets set A=1 B=2 C=3 -a ps-tracker
```

### OAuth 콜백 URL 변경
배포 도메인이 바뀌면 (커스텀 도메인 설정 등) Google / GitHub Developer Console에서 콜백 URL도 같이 바꿔야 한다.
- Google: `https://<domain>/accounts/google/login/callback/`
- GitHub: `https://<domain>/accounts/github/login/callback/`

## 4. 자주 발생하는 오류

### "Forbidden (403) CSRF 검증에 실패했습니다"
- `CSRF_TRUSTED_ORIGINS`에 현재 호스트의 scheme+host가 정확히 포함됐는지 확인. 누락된 origin 추가 후 재배포.
- 사용자 단에서 쿠키 차단된 경우는 우리가 어찌할 수 없음 → 안내.

### 로그인 직후 즉시 로그아웃 / "비로그인"으로 보임 (탭 깜빡임)
- 로컬 Codespaces 환경에서만 재현된다 (relay infra가 HttpOnly 쿠키 wrapping). Fly에선 발생하지 않아야 한다.
- 그래도 재현되면: 브라우저 시크릿 모드에서 재현 시도 → 사용자 환경의 캐시·확장프로그램 이슈일 가능성.
- 코드 측 안전망: `NoStoreMiddleware` (Cache-Control: no-store) + `auth_marker` 쿠키 + `visibilitychange` 리로드 — 모두 `templates/base.html` + `config/middleware.py` 참고.

### DB 마이그레이션이 release_command에서 실패
1. `fly logs -a ps-tracker` 또는 GitHub Actions Deploy 로그에서 실제 에러 메시지 확인.
2. 로컬에서 동일 마이그레이션을 `DATABASE_URL=<prod-clone>` (snapshot 복원본)에서 시뮬레이션.
3. 수정한 마이그레이션을 새 커밋으로 push (이미 적용된 마이그레이션을 수정 금지 — 항상 새 파일 추가).

## 4½. ProblemSet 트리 데이터 동기화 (admin ↔ YAML)

**원칙**: Django **admin이 단일 진실 원천**(canonical source). `data/example.yml`은 admin 상태의 **스냅샷**(version-controlled 백업 + 새 환경 시드용)이며, prod에 변경을 가하는 통로가 아니다.

### 왜 이렇게 정했나
YAML을 양방향 source로 쓰면 충돌이 난다: admin에서 노드를 옮기면 import matcher가 `(parent, title)`로 찾지 못해 같은 제목의 노드를 직속에 또 만든다 (실제로 `ICPC > 1. National > Yokohama Regional`을 옮긴 뒤 `ICPC > Yokohama Regional`로 재import 했더니 dup 발생). admin이 풍부한 구조의 출처라서 admin을 canonical로 잡는 게 자연스럽다.

### 일반 흐름 (admin → YAML 백업)
```bash
# prod admin 상태를 YAML로 dump
fly ssh console -a ps-tracker -C "/app/.venv/bin/python manage.py export_problemsets" 2>/dev/null > data/example.yml
git add data/example.yml && git commit -m "snapshot: prod tree" && git push
```
잡지에 적당히 (주 1~2회 또는 큰 편집 후) 돌리면 git에 백업 + diff로 변경 이력이 남는다.

### 새 환경 (dev 또는 새 prod) 부트스트랩
```bash
uv run manage.py import_problemsets data/example.yml
```
importer는 `(parent, title)` 매칭으로 idempotent — 같은 스냅샷을 두 번 import해도 변화 없음.

### prod에 import 하지 말 것 (주의)
prod에서 admin으로 트리를 바꾼 뒤 `data/example.yml`을 prod에 다시 import 하지 마라. matcher가 옮긴 노드를 못 찾으면 dup을 만든다. prod 변경은 admin에서, 변경 후 위의 export 흐름으로 YAML에 반영.

### 만약 dup이 생겼다면
`fly ssh console -a ps-tracker`에 진입해서 ProblemSet 셸로 직접 삭제:
```python
from apps.problemsets.models import ProblemSet
ProblemSet.objects.get(pk=<dup_pk>).delete()  # cascades subtree
```
ProblemAppearance는 FK CASCADE로 정리되지만 Problem과 SolveRecord는 그대로 (다른 set과 공유 중이면 안전).

## 5. 백업 / 복원

### 자동 백업 (Fly Postgres)
Fly Postgres는 일일 snapshot을 7일간 자동 보관 (Fly 기본 정책). 별도 설정 불필요.

```bash
fly pg list                                 # 클러스터 목록
fly pg backups list -a <pg-cluster>         # 보관 중인 snapshot
```

### 백업본 복원 (catastrophic recovery)
1. 새 Postgres cluster를 snapshot 기반으로 띄움:
   ```bash
   fly pg create --fork-from <snapshot-id>
   ```
2. 새 cluster를 ps-tracker에 attach (기존 DATABASE_URL 덮어쓰기):
   ```bash
   fly pg attach <new-cluster> -a ps-tracker
   ```
3. 앱 재배포 (`fly deploy`).
4. 데이터 검증 — `/admin/`에서 최근 SolveRecord·Rating·Proposal 건수 확인.

### 외부 미러 (권장, 아직 미구현 — backlog)
주 1회 `pg_dump`를 외부 (B2 또는 GitHub release private)로 push 하는 cron이 권장사항이지만 아직 자동화되지 않았다. 출시 후 우선순위 1로 다룰 것.

수동 실행 예 (로컬에서):
```bash
DATABASE_URL=$(fly ssh console -a <pg-cluster> -C 'env' | grep DATABASE_URL)
pg_dump "$DATABASE_URL" | gzip > "ps-tracker-$(date +%Y%m%d).sql.gz"
```

## 6. 모니터링

### Sentry
- 가입 후 새 프로젝트 (Django) 생성 → DSN 복사.
- `fly secrets set SENTRY_DSN=... -a ps-tracker` 적용 후 자동 재배포 시 활성화.
- 검증: 디버그 endpoint를 일시적으로 추가하거나, prod에서 의도된 500을 한 번 트리거 (예: 존재하지 않는 admin URL에 robots-blocked path 호출). 1분 안에 Sentry에 새 이슈가 잡혀야 함.
- 임계: 무료 플랜 월 5000 이벤트. 1인 운영 기준 보수적이지만, ERROR 폭증 시 빠르게 소진될 수 있으므로 알림 채널 설정 권장.

### UptimeRobot (선택)
- `https://ps-tracker.fly.dev/healthz`를 5분 주기 HTTP 모니터로 등록.
- 다운 알림은 이메일로 받도록 설정.

### Fly Logs
```bash
fly logs -a ps-tracker                    # 실시간 stream
fly logs -a ps-tracker --no-tail | tail -200
```
`config/settings/prod.py`의 LOGGING이 stdout로 INFO 이상을 흘리고 있어 모든 줄이 Fly로 수집된다.

## 7. 사용자 제재 / 데이터 정정

### 닉네임 또는 프로필 정정
Admin (`/admin/accounts/user/`) → 해당 user → 필드 편집. 이메일·OAuth 연결은 건드리지 말 것 (allauth 내부 키).

### 부정 사용자 차단
Admin → user → `is_active = False`. 다음 로그인 시 거부된다 (django.contrib.auth 기본 동작).

### 제안 큐가 폭주
`/admin/proposals/categoryproposal/` 또는 `.../problemsetproposal/`에서 bulk reject. 악의적인 제출자는 위 §사용자 제재로.

## 8. 사고 대응 (Incident)

### 사이트 전체 다운
1. `fly status -a ps-tracker` — 머신 상태 확인.
2. `fly logs -a ps-tracker --no-tail | tail -200` — 직전 에러 확인.
3. 직전 배포가 원인 같으면 §2 롤백.
4. Fly 자체 장애면 (`fly status` 명령 자체도 답 없음) status.fly.io 확인.

### 데이터 유실 발견
1. **쓰기 즉시 차단**: 일시적으로 admin이 아닌 일반 사용자의 쓰기 경로를 막을 방법은 현재 없음 → 최악의 경우 머신 정지:
   ```bash
   fly scale count 0 -a ps-tracker
   ```
2. §5 복원 절차로 새 DB cluster 생성, attach.
3. 머신 재시작 (`fly scale count 1`).
4. Sentry·로그·Slack 등으로 사용자 공지 (아직 공식 채널 없음).

## 9. 로컬 개발 셋업 빠른 참조

```bash
git clone <repo>
cd icpc-guide
uv sync
cp .env.example .env       # SECRET_KEY, OAuth 키 등 채워넣기
uv run manage.py migrate
uv run manage.py createsuperuser
uv run manage.py runserver
```

테스트:
```bash
uv run ruff check . && uv run ruff format --check .
DJANGO_SETTINGS_MODULE=config.settings.dev uv run pytest
```

## 10. 변경 이력 (이 파일)

- 2026-05-17 초안 (Step 8 마무리)
