# QA Checklist — V1 출시 전 수동 점검

이 체크리스트는 자동 테스트(pytest 246개)로 잡히지 않는 UI/UX·통합·운영 경로를 손으로 한 번 훑는 용도다. 새 배포 직후 1회, 그리고 큰 기능 추가 후 1회씩 돌리면 충분.

각 항목은 [PASS] / [FAIL] / [N/A] 로 마크. FAIL은 GitHub 이슈로 옮기고 마감 전 처리.

---

## 0. 사전 준비

- [PASS] prod 사이트(`https://ps-tracker.fly.dev/`)가 200 응답
- [PASS] `/healthz`가 "ok" 반환
- [PASS] 새 브라우저 시크릿 세션에서 시작 (이전 쿠키 영향 차단)
- [PASS] 테스트용 계정 2개 준비: Google 1개, GitHub 1개

---

## 1. 비로그인 (Guest) 경로

- [PASS] 메인(`/`)이 로그인 없이 열림
- [PASS] 출처(`/sets/`)에서 ProblemSet 트리가 보임
- [FAIL] 트리 노드의 펼치기/접기 버튼이 보이고 클릭 시 자식 노드가 토글됨
- [PASS] 둘러보기(`/categories/`)에서 Category 카드 그리드가 보이고 description이 표시됨
- [PASS] ProblemSet 상세(`/sets/<pk>/`)가 비로그인으로도 열리고, 평균 별점·평가 수가 보임
- [PASS] 별점·코멘트 입력 영역은 "로그인하세요" 안내 또는 비활성
- [PASS] 팀 목록(`/teams/`)에서 public 팀만 보이고, "내 팀" 섹션은 비어있거나 숨김
- [PASS] navbar에 "제안" 링크가 **보이지 않음**
- [PASS] private profile(`/u/<nickname>/`)은 닉네임만 표시

## 2. 로그인 흐름 (allauth + OAuth)

- [PASS] `/accounts/login/`에서 Google·GitHub 버튼이 둘 다 보임
- [PASS] Google OAuth: 동의 후 닉네임 입력 화면으로 진입 (allauth signup form)
- [N/A] 닉네임 중복 시 검증 오류 메시지 노출
- [PASS] 가입 완료 후 `/`로 리다이렉트 + navbar에 닉네임·"마이페이지"·"로그아웃" 보임
- [PASS] **로그아웃**: navbar의 로그아웃 버튼 → 즉시 비로그인 상태로 전환, navbar에 "로그인" 버튼 복귀
- [PASS] 로그아웃 직후 `/admin/`은 로그인 화면으로 리다이렉트
- [PASS] 같은 이메일로 GitHub OAuth 재로그인 시 동일 계정으로 연결 (`SOCIALACCOUNT_EMAIL_AUTHENTICATION=True`)
- [PASS] 2번째 사용자로 가입 → navbar의 본인 닉네임이 다른 값으로 보임

## 3. 마이페이지 / 프로필 가시성

- [PASS] `~~/accounts~~/me/`에서 외부 핸들(BOJ·Codeforces 등) 편집 가능, 저장 시 success 메시지
- [PASS] `profile_visibility = private`로 변경 후, 다른 계정으로 `/u/<my_nickname>/` 접근 → 닉네임만 보임
- [PASS] `profile_visibility = public`로 변경 후, 다른 계정에서 → 통계·푼 set 목록 보임
- [PASS] 비로그인 상태에서 public profile 열람 가능 / private profile은 닉네임만

## 4. 풀이 트래킹 (HTMX)

- [PASS] 리프 ProblemSet 상세에서 "해결" 토글 클릭 → 버튼 즉시 상태 전환 (페이지 새로고침 없음)
- [PASS] 토글 직후 헤더의 본인 완주율 미니바가 같이 갱신됨 (HX-Trigger 동작)
- [PASS] 같은 문제 다시 클릭 → 미해결 상태 복귀
- [PASS] 부모(내부 노드) 상세에서 자식 set의 완주율이 올라간 게 반영됨
- [PASS] SolveRecord 메모 입력 → 저장 후 다시 열어도 메모 남아 있음

## 5. 별점 / 코멘트

- [PASS] 별점 1~5 클릭 시 즉시 반영 (UPSERT)
- [PASS] 별점 등록 후 코멘트 입력란 등장
- [PASS] 같은 사용자가 별점 다시 클릭 → 갈아엎기 (히스토리 없음)
- [PASS] 코멘트 작성 → 코멘트 섹션에 닉네임·별점·본문·작성 시각 표시
- [N/A] 코멘트 편집 → "수정 시각"이 갱신됨
- [PASS] 평가자 목록 모달 (로그인 사용자만): 닉네임·별점·작성 시각 리스트

## 6. 팀

- [PASS] `/teams/create/`로 새 팀 생성 (visibility=public). 생성자가 owner
- [만료 시간은 따로 없음] 팀 상세 페이지에서 "초대 링크 발급" → 만료 시간 설정 → 링크 복사
- [PASS] 다른 계정으로 시크릿 모드에서 초대 링크 클릭 → 수락 화면 → 가입
- [PASS] owner가 멤버 강제 제거 가능, 본인은 못 제거
- [PASS] owner 양도: 다른 멤버 선택 → 양도 → 권한이 즉시 바뀌고 메시지 표시
- [PASS] 팀 정보 편집 (이름·설명·visibility) → 저장 후 반영
- [PASS] visibility=private 팀에 비멤버 접근 → **404** (403 아님)
- [N/A] private 팀 owner가 본인 계정 삭제 → 가장 오래된 멤버에게 자동 이양 (admin에서 user delete 시 검증)
- [N/A] 50명 한도: 50번째 멤버 추가까진 OK, 51번째에서 검증 실패 메시지

## 7. 팀 컨텍스트 (ProblemSet 상세 §4.4.3)

- [PASS] 팀에 속한 사용자가 ProblemSet 상세 열면 "팀 컨텍스트" 드롭다운 노출
- [PASS] 팀 선택 시 멤버별 해결 표시(체크) + 팀 합산 완주율 표시
- [PASS] 비멤버가 URL에 `?team=<slug>` 강제로 붙여도 무시됨
- [N/A] public 팀 + 멤버의 profile_visibility=private 조합에서 비멤버 시점에서는 그 멤버의 개별 해결은 가려짐 (spec §4.6.3)

## 8. 사용자 제안 (S3)

- [PASS] 로그인 후 navbar에 "제안" 링크 노출
- [PASS] `/propose/`에서 두 가지 제안 버튼 + 내 과거 제안 표 (없으면 안내)
- [PASS] 새 카테고리 제안 제출 → success 메시지 + 목록에 PENDING 상태로 노출
- [ ] 새 Problem Set 제안 제출 (parent·카테고리·문제 목록 포함) → 마찬가지로 PENDING
- [ ] 문제 목록 입력 형식 오류 (예: `라벨없이만적기`) → 인라인 에러로 안내
- [ ] 다른 사용자의 제안은 내 목록에 안 보임

## 9. Admin 검토 큐 (S7 탭3)

- [ ] `/admin/proposals/categoryproposal/`에서 PENDING 제안 보임
- [ ] 여러 건 체크 → "선택된 제안 승인 (Category 생성)" 액션 → 실제 Category로 만들어졌는지 `/admin/sources/category/`에서 확인
- [ ] 중복 short_name 제안 승인 시 에러 메시지로 안내 + 상태 PENDING 유지
- [ ] `/admin/proposals/problemsetproposal/`에서도 같은 흐름 (승인 시 ProblemSet 트리 노드 생성, 문제·카테고리·parent 연결 확인)
- [ ] 반려 액션 → 상태 REJECTED, admin_note 필드에 메모 가능 (change 화면)

## 10. 운영 / 모니터링

- [ ] `fly status -a ps-tracker` 모든 머신 "started" / health check 통과
- [ ] Sentry 대시보드에 의도된 ERROR 테스트가 잡히는지 (예: `/admin/__not-a-real-page__/` 같은 404 — 404는 잡히지 않으니, 일시적인 DEBUG 환경에서 raise Exception 트리거 후 원복)
- [ ] `fly logs`에 INFO 이상의 정상 액세스 로그가 흐르는지
- [ ] DB 백업: `fly pg backups list -a <pg-cluster>` 결과에 최근 7일분 snapshot 있는지

## 11. 보안 / 사후

- [ ] OAuth 콜백 URL이 prod 도메인과 일치하는지 (Google + GitHub Developer Console)
- [ ] `.env`·시크릿 키가 git에 들어가지 않았는지 (`git log -p -- .env .env.example | head -50` 확인)
- [ ] `SECRET_KEY`가 dev 기본값(`dev-insecure-change-me`)이 아닌지 (`fly secrets list`)
- [ ] `DEBUG=False`인지 (`/whoami` 페이지가 prod에서 404 — 의도적)
- [ ] HTTPS 강제 (`SECURE_SSL_REDIRECT=True`) 동작 — http로 접근 시 https로 리다이렉트

---

## 결과 정리 (출시 전 채울 것)

- 점검 일자:
- 점검자:
- PASS 항목 수: __ / 총 __
- FAIL 항목 / 후속 이슈 번호:
- 출시 가능 판단: ☐ Go / ☐ No-go

---

## 변경 이력

- 2026-05-17 초안 (Step 8 마무리)
