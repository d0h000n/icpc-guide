# Problem Set 트래커 — 기능 명세서

**Version:** v0.4 (Draft)
**작성일:** 2026-05-05

---

## 변경 이력

| 버전 | 일자 | 주요 변경 |
|---|---|---|
| v0.1 | 2026-05-05 | 초기 초안 작성 |
| v0.2 | 2026-05-05 | 난이도 산정 방식 변경(스코어보드 기반, P3 미룸) / ProblemSet 계층 구조 도입 / 개인·팀 각각 public/private 가시성 분리 / 코멘트 300자 / 팀 최대 50명 / 탈퇴 시 익명화 / SolveRecord note 필드 유지 명시 |
| v0.3 | 2026-05-08 | Problem ↔ ProblemSet 관계를 N—M로 변경 (ProblemAppearance 중계 모델). 한 문제가 여러 set에 등장 가능 (예: ICPC 지역대회 문제가 PTZ Camp에 재출제). SolveRecord는 Problem 단위라서 자동 dedup. 서브트리 완주율 계산은 distinct count 사용. |
| v0.4 | 2026-05-08 | Source → **Category**로 재명명 + 의미 변경. 기존 Source는 ProblemSet의 "출처(원천)" 역할이었으나, Category는 직교적 묶음(예: Japan 카테고리에 Yokohama Regional·JAG·AtCoder·JOI 묶기). ProblemSet의 source FK 제거, Category ↔ ProblemSet **M2M**. ICPC 등 최상위 묶음은 ProblemSet 트리 루트로 표현 (Source 없이 자립). ProblemSet.season 필드 제거 (Season별 쿼리 수요 없음). 연도는 단일값 대신 범위 필터 지원 (year_from / year_to). Category에 사용자 커스텀(owner) 필드는 백로그(단계 6+). |

---

## 1. 개요

### 1.1 목적

본 서비스는 ICPC, ICPC 캠프, 지역 대회 등에서 출제된 problem set을 관리하고, 사용자(주로 경쟁 프로그래밍 팀)가 어떤 set을 풀었는지/풀지 않았는지를 트래킹할 수 있도록 한다. 또한 사용자 평가(별점·코멘트)를 통해 problem set의 추천도(퀄리티)를 공유한다.

### 1.2 핵심 가치

- ICPC/CP 팀이 "다음에 풀 set"을 고를 때 의사결정을 빠르게 한다.
- 팀 단위 진척도를 한눈에 볼 수 있어, 중복 풀이를 줄이고 미해결 set을 식별한다.
- 커뮤니티의 퀄리티 평가(별점·코멘트)로 밸런스가 좋은 set, 피해야 할 set을 빠르게 판별한다.

### 1.3 범위

- ProblemSet 트리는 essential한 대회 위주로 한정 (예: ICPC, AtCoder, JOI 등 — 각 루트 ProblemSet).
- 카테고리(canonical) 및 ProblemSet 트리는 admin이 관리. 사용자는 추가 요청만 가능 (사용자 커스텀 카테고리는 단계 6+ 백로그).
- 공개 서비스이지만 수요가 적어 트래픽 부담은 적은 형태.
- 초기 버전에서는 solved.ac API 연동을 하지 않으며, 난이도 로고만 차용해 개인 메모용으로 사용.

### 1.4 비범위 (Out of Scope)

- 문제 채점 / 코드 제출 / 자동 검증 기능은 제공하지 않음 (외부 저지 사용).
- solved.ac API 연동 (추후 고려).
- 실시간 협업·채팅 기능.
- 랭킹 시스템 (개별 사용자 점수화).
- 스코어보드 기반 자동 난이도 산정 — 설계만 두고 V1에서는 구현하지 않음 (§4.7 참조).

---

## 2. 사용자 및 권한

### 2.1 사용자 유형

| 역할 | 설명 | 주요 권한 |
|---|---|---|
| Guest | 비로그인 방문자 | 공개 problem set 열람, 별점 평균·완주율 등 집계 정보 조회, public 프로필 열람 |
| User | OAuth로 가입한 일반 사용자 | Guest 권한 + 개인 해결 상태 기록, 별점·코멘트 작성, 팀 생성/참여, problem set 제안, 가시성 설정 |
| Admin | 운영자 | User 권한 + 카테고리 관리, problem set 등록/수정/삭제, 사용자 제재, 사용자 제안 검토 |

### 2.2 인증 방식

OAuth 2.0 기반 소셜 로그인을 채택한다. 이메일/비밀번호 방식은 채택하지 않는다.

- 권장 Provider: Google, GitHub
- 선정 이유: (1) 비밀번호 저장·복구 부담 제거, (2) 타겟 사용자(CP 참가자)는 GitHub 계정 보유율이 높음, (3) 가입 마찰이 적음.
- 최초 로그인 시 닉네임(필수, 유일)과 핸들(선택, codeforces/boj 등 외부 핸들)을 입력받는다.

### 2.3 Admin 지정

- 최초 admin은 환경변수/시드 데이터로 지정한다.
- admin이 다른 사용자를 admin으로 승격할 수 있다.

### 2.4 탈퇴 처리

- 사용자가 계정을 삭제하면 본인 식별 정보(닉네임, OAuth ID, 외부 핸들)는 삭제된다.
- 연관 SolveRecord, Rating, Comment, 팀 멤버십은 "deleted_user" 형태의 익명 표식으로 보존된다 (집계 무결성 유지).
- 팀 owner가 탈퇴하는 경우, 멤버 중 가장 오래된 사람에게 owner 권한이 자동 이양된다. 멤버가 없는 팀은 삭제된다.

---

## 3. 데이터 모델 (개념)

아래는 구현 무관한 개념 모델이다. 실제 스키마는 구현 단계에서 별도 정의한다.

### 3.1 엔티티 목록

| 엔티티 | 주요 속성 | 비고 |
|---|---|---|
| User | id, nickname, oauth_provider, oauth_id, external_handles, role, profile_visibility, created_at | role ∈ {user, admin}<br>profile_visibility ∈ {public, private} |
| Category | id, name, short_name, description, url, owner_id (nullable, 백로그) | 직교적 묶음. 예: "Japan", "Korea", "내 즐겨찾기". owner=null이면 admin 관리 canonical, owner 세팅되면 사용자 커스텀 (UI는 단계 6+ 백로그). |
| ProblemSet | id, parent_set_id (nullable), title, year, description, external_url, difficulty_score (nullable), created_by(admin), created_at | parent_set_id로 트리 구조 형성<br>source FK·season 필드 v0.4에서 제거<br>difficulty_score는 자동 계산 (V1 미구현) |
| CategoryMembership | id, category_id, problem_set_id | Category ↔ ProblemSet M2M through. (category, problem_set) 유일. |
| Problem | id, title, external_url, solved_ac_tier_manual (nullable) | 논리 문제 (canonical). 여러 ProblemSet에 등장 가능 (via ProblemAppearance). |
| ProblemAppearance | id, problem_id, problem_set_id, order_index, label(A/B/C…) | 한 Problem이 특정 ProblemSet에 등장하는 인스턴스. set 내 순서·라벨은 등장마다 다를 수 있음. |
| SolveRecord | id, user_id, problem_id, solved_at, note (≤ 200자, 선택) | 개인별 해결 기록<br>record 존재 = solved |
| Team | id, name, slug, description, owner_user_id, visibility, created_at | visibility ∈ {public, private} |
| TeamMember | team_id, user_id, role, joined_at | role ∈ {owner, member}<br>팀당 최대 50명 |
| TeamInvite | id, team_id, invited_by, invitee_user_id (nullable), token, expires_at, status | 초대 링크/요청 |
| Rating | id, user_id, problem_set_id, stars (1~5), created_at, updated_at | 사용자×set 유일 (UPSERT)<br>퀄리티 평가용 |
| Comment | id, user_id, problem_set_id, body (≤ 300자), created_at, updated_at | 사용자×set 당 1개<br>별점이 있어야 작성 가능 |
| CategoryProposal | id, user_id, name, short_name, description, url, status, admin_note | 사용자가 카테고리 제안 (admin 검토 후 canonical로 승격) |
| ProblemSetProposal | id, user_id, payload(JSON), status, admin_note | 사용자가 problem set 제안 |

### 3.2 핵심 관계

- ProblemSet 1—N ProblemSet (parent_set_id, 자기 참조 트리 / 깊이 제한 없음) — ProblemSet은 단일 부모만 가짐
- Category N—M ProblemSet (via CategoryMembership) — 한 Category가 여러 ProblemSet을 묶고, 한 ProblemSet이 여러 Category에 속할 수 있음
- ProblemSet N—M Problem (via ProblemAppearance) — 한 Problem이 여러 set에 등장 가능
- User N—M Problem (via SolveRecord) — 한 번 풀면 모든 등장에 대해 solved 처리
- User N—M Team (via TeamMember, 한 사용자가 여러 팀에 속할 수 있음)
- User 1—1 Rating per ProblemSet (UPSERT)
- User 1—0..1 Comment per ProblemSet (별점 있을 때만 생성/유지)

### 3.3 핵심 제약

- Rating.stars는 정수 1~5만 허용. Rating 없이 Comment 단독 존재 불가 (Rating 삭제 시 Comment도 함께 삭제).
- Comment.body는 300자 이내.
- SolveRecord.note는 200자 이내 (간단한 메모 용도).
- ProblemSet 트리: 순환 참조 금지(부모 체인 확인).
- ProblemAppearance: (problem_set, order_index) 유일, (problem_set, label) 유일, (problem, problem_set) 유일 — 같은 set에 같은 Problem이 두 번 등장 불가.
- 서브트리 완주율은 등장 횟수가 아닌 distinct Problem 수로 집계 (한 문제가 여러 set에 있어도 1로 셈).
- Category 멤버십 제약: 어떤 Category가 ProblemSet A와 B를 동시에 직접 멤버로 가질 때, A와 B는 ProblemSet 트리상의 조상-자손 관계여서는 안 된다 (조상이 이미 자손을 함의하므로 중복). 위반 시 admin 폼에서 거부.
- Category.short_name은 유일 (canonical/owner 무관 전역 유일).
- Team 멤버 수 ≤ 50.
- Team.slug는 유일.
- User는 자신의 SolveRecord, Rating, Comment만 수정/삭제 가능.

---

## 4. 기능 요구사항

### 4.1 Problem Set 관리

#### 4.1.1 계층 구조 (Directory Tree)

Problem set은 트리 구조를 가질 수 있다. 깊이 제한은 없다.

- 리프 노드(자식 없음): 실제 문제 목록을 가질 수 있는 "풀 수 있는 set".
- 내부 노드(자식 있음): 그룹 역할. 일반적으로 문제는 직접 보유하지 않고 자식 set들이 보유.
- 예시: "PTZ Camp" → "PTZ 2024 Summer" → "Day 1 / Day 2 / Day 3". 각 Day가 실제 문제를 가진다.
- UI는 트리/디렉토리 형태로 표시되며, 각 노드는 펼치기/접기가 가능하다.
- 내부 노드에도 별점·코멘트를 남길 수 있다 (대회 시리즈 자체에 대한 평가). 자식 set의 별점은 별도 집계되며 부모 노드에는 자동 평균을 부가 정보로 함께 표시한다.
- 내부 노드의 "완주율"은 자식 set들의 완주 진행도를 합산해 계산한다 (해결 문제 수 합 / 자식 set 전체 문제 수 합).

#### 4.1.2 목록 / 트리 조회 (Guest 이상)

- 기본 화면은 ProblemSet 트리 (루트 = ICPC, AtCoder, JOI 등 최상위 ProblemSet).
- 필터: 카테고리(Category, 다중 선택), 연도 범위 (year_from / year_to), 키워드 검색.
- 정렬: 최신 등록순(기본), 평균 평점 높은순, 평가 수 많은순.
- 리프 set 카드 표시 항목: 제목 / 경로(부모 체인) / 소속 카테고리 / 연도 / 평균 평점 + 평가 수 / (로그인 시) 본인 완주율.
- 페이지네이션 또는 무한 스크롤. 단순 페이지네이션 권장.

#### 4.1.3 상세 조회 (Guest 이상)

- 리프 노드: Problem 목록을 순서대로 표시 (A, B, C…). 각 Problem에는 제목, 외부 링크, solved.ac 티어 로고(있을 시).
- 내부 노드: 자식 set 목록 + 각각의 평균 평점·평가 수·(로그인 시) 본인 완주율 표시. 트리 펼치기/접기 지원.
- set 전체 평균 평점, 평가 수, 완주율 표시.
- 로그인 사용자: 본인 완주율 + 본인 별점 + 본인 코멘트 표시.
- 로그인 사용자: 평가자 목록(누가 몇 점 줬는지) 열람 가능.
- 팀 컨텍스트가 선택된 경우: 팀원별 해결 상태 표시 (자세한 내용 §4.4).

#### 4.1.4 등록 (Admin only)

- 필수 필드: 제목, parent_set_id (선택, 없으면 최상위).
- 선택 필드: 연도, 카테고리(다중), 설명, set 자체의 외부 URL.
- 리프 노드인 경우: 문제 목록(라벨·제목·외부 URL·티어)을 함께 입력.
- 내부 노드와 리프 노드 구분은 "자식 보유 여부"로 결정 (별도 플래그 없음). 자식이 추가되는 순간 리프가 아니게 된다.

#### 4.1.5 수정 / 삭제 (Admin only)

- 수정: 모든 필드 변경 가능. parent 변경 시 순환 참조 검사.
- 삭제: 소프트 삭제. 자식 set이 있는 경우, 자식의 parent를 조부모로 끌어올리는 옵션 또는 함께 소프트 삭제하는 옵션을 제공.
- 연관 SolveRecord/Rating/Comment는 보존되며, 사용자는 "이 set은 삭제됨" 안내와 함께 자기 기록을 계속 볼 수 있다.

#### 4.1.6 사용자 제안

- 로그인 사용자는 새로운 problem set 등록을 제안할 수 있다.
- 제안 폼은 4.1.4와 동일한 필드를 가지나, 즉시 반영되지 않고 admin 검토 큐에 들어간다.
- admin은 승인/반려/수정 후 승인이 가능하며, 제안자에게 결과가 통지된다(인앱 알림).

### 4.2 카테고리(Category) 관리

- admin: CRUD 가능. short_name(예: japan, korea, asia)은 전역 유일해야 한다.
- user (canonical): 카테고리 추가 제안만 가능 (CategoryProposal). admin이 검토 후 canonical로 승격.
- user (custom, 백로그): 본인 소유 사적 카테고리 생성 가능 (단계 6+ 백로그). owner=user 인 카테고리는 생성자 본인 + (옵션) 명시적으로 공유한 사람에게만 보임.
- Guest/User 모두 canonical 카테고리 목록 열람 가능.
- 한 카테고리의 멤버 ProblemSet 사이엔 ProblemSet 트리상 조상-자손 관계가 있어선 안 된다 (조상이 자손을 포함하므로 중복).

### 4.3 해결 상태 (Solve) 관리

#### 4.3.1 개인 단위

- 로그인 사용자는 각 Problem의 "해결"/"미해결" 상태를 토글할 수 있다.
- 토글 시 SolveRecord가 생성/삭제된다. solved_at은 토글 시점.
- SolveRecord에는 200자 이내의 간단한 메모를 남길 수 있다 (선택).
- 문제 단위 토글이 set 단위 완주율에 즉시 반영된다.

#### 4.3.2 Set 단위 완주율

- 리프 set 완주율 = (해결한 문제 수) / (set의 전체 문제 수).
- 내부 노드 완주율 = (자식 set들의 해결 문제 수 합) / (자식 set들의 전체 문제 수 합).
- 개인 화면: 본인의 완주율을 % 또는 N/M 형식으로 표시.
- 팀 화면(§4.4): 팀원별 완주율 + 팀 합산 완주율("팀 중 누군가가 푼 문제 수 / 전체").

### 4.4 팀(Team) 기능

#### 4.4.1 팀 생성/관리

- 로그인 사용자는 팀을 생성할 수 있다. 생성자는 owner가 된다.
- 팀 가시성은 public 또는 private이다. (자세한 의미 §4.6.2)
- owner는 팀명·설명·가시성 변경, 멤버 초대/제거, 다른 멤버에게 owner 권한 양도 가능.
- 한 사용자는 여러 팀에 속할 수 있다.
- 한 팀의 최대 인원은 50명 (owner 포함).

#### 4.4.2 초대

- owner가 초대 링크(토큰 포함)를 생성하여 공유한다. 만료 시간 설정 가능.
- 로그인 사용자가 초대 링크를 수락하면 멤버로 가입된다. 50명 한도 초과 시 거부.
- (선택) 닉네임으로 직접 초대 가능.

#### 4.4.3 팀 컨텍스트 보기

- Problem set 상세 화면 상단에 "팀 선택" 드롭다운(소속 팀 중 하나).
- 팀 선택 시 각 Problem 행에 멤버별 해결 여부가 구체적으로 표시 (예: 닉네임 + Solved 체크).
- 팀 합산 완주율과 멤버 개별 완주율을 모두 노출.
- 팀 컨텍스트는 팀 멤버에게만 의미가 있으며, 팀 가시성과는 별개로 동작한다 (멤버에게는 다른 멤버의 해결 상태가 항상 보인다).

### 4.5 평가 (Rating) 및 코멘트

#### 4.5.1 별점

- 로그인 사용자는 problem set에 1~5의 별점을 줄 수 있다 (퀄리티 평가).
- 별점은 사용자×set 당 1개. 다시 누르면 갱신된다(UPSERT). 별점 삭제 시 코멘트도 함께 삭제.
- set의 평균 별점과 평가 수가 공개적으로 표시된다.
- 로그인 사용자는 "평가자 목록"을 열람할 수 있다 (누가 몇 점을 줬는지).
- Guest는 집계만 본다.

#### 4.5.2 코멘트

- 로그인 사용자는 problem set에 짧은 평(300자 이내)을 남길 수 있다.
- 코멘트는 별점이 존재할 때만 작성 가능하다 (별점 필수, 코멘트 선택).
- 코멘트는 사용자×set 당 1개. 편집/삭제 가능.
- 코멘트는 모두에게 공개된다(작성자 닉네임 포함). Guest도 열람 가능.
- 토론 스레드/대댓글은 제공하지 않는다.

### 4.6 가시성 (Visibility)

개인과 팀 각각 가시성을 독립적으로 설정한다. 두 가시성은 서로 영향을 미치지 않는다.

#### 4.6.1 개인 프로필 가시성 (User.profile_visibility)

| 설정 | 내 SolveRecord 노출 범위 |
|---|---|
| public | 누구나 내 프로필 페이지에서 내가 푼 문제 목록과 통계를 볼 수 있다. |
| private | 나 자신만 볼 수 있다. 단, 내가 속한 팀의 팀원에게는 팀 컨텍스트 안에서 별도로 보인다. |

- 기본값: private.
- 핵심 원칙: "공개 프로필 노출"과 "팀원에게 보임"은 별개의 채널. private이어도 팀 멤버는 팀 컨텍스트에서 내 풀이 상태를 본다.
- Rating·Comment는 가시성 설정과 무관하게 모두에게 공개된다 (퀄리티 신호의 투명성을 위해).

#### 4.6.2 팀 가시성 (Team.visibility)

| 설정 | 팀 정보 노출 범위 |
|---|---|
| public | 팀 페이지가 공개. 누구나 팀명·멤버·팀 통계를 볼 수 있다. |
| private | 초대 링크 또는 멤버에게만 보인다. 검색·디렉토리에 노출되지 않는다. |

- 기본값: private.
- 팀 멤버 개개인의 SolveRecord는 각자의 profile_visibility를 따른다. 팀이 public이라도 멤버 본인이 private이면 팀 페이지에서 그 멤버의 상세 풀이 목록은 노출되지 않을 수 있다 (정확한 노출 룰은 §4.6.3 참조).

#### 4.6.3 가시성 조합 룰

가시성 조합에 따른 정보 노출 정책을 명확히 한다.

| 조회 주체 → 대상 | 조회되는 정보 |
|---|---|
| Guest → public 프로필 | 닉네임, 외부 핸들, 푼 문제 수, 푼 set 목록 |
| Guest → private 프로필 | 닉네임만 표시 가능 (코멘트 등에서). 풀이 통계 비공개 |
| User(비멤버) → public 팀 | 팀명, 설명, 멤버 닉네임 목록, 팀 합산 통계 |
| User(비멤버) → private 팀 | 접근 불가 (직접 URL 접근 시 404) |
| Team 멤버 → 팀의 다른 멤버 | 팀 컨텍스트 안에서는 다른 멤버의 풀이 상태가 항상 보임 (개인 private 무관) |
| public 팀 + private 멤버 | 비멤버는 해당 멤버의 상세 풀이 비공개. 닉네임·소속만 표시 |

### 4.7 난이도 표시

#### 4.7.1 Problem Set 난이도 (자동 산정 — V1 미구현, P3)

난이도는 별점 평가(퀄리티)와 별개의 지표이다. 사용자 투표가 아니라, 대회 당시 스코어보드를 기반으로 자동 산정한다.

- 산정 방식: 대회 당시 스코어보드에서 적당한 구간의 팀(예: 상위 80~20%)이 대회 시간 내에 전체 문제 중 몇 %를 해결했는지로 평가.
- 결과는 단일 숫자 또는 ★ 1~5로 매핑할 수 있다.
- V1에서는 ProblemSet.difficulty_score 필드를 nullable로 두고 표시하지 않는다. 후속 버전에서 스코어보드 데이터 수집·계산 모듈을 추가한다.
- 스코어보드 데이터 수집·정규화 방식, "대회 시간"의 정의(연습용 set의 경우), "적당한 구간"의 정확한 컷오프 등은 별도 설계 문서로 분리한다.

#### 4.7.2 문제별 난이도 (solved.ac 티어)

- 문제마다 solved.ac 티어를 수동으로 메모할 수 있다 (Bronze V ~ Ruby I, Unrated).
- 티어 로고는 정적 에셋으로 번들. solved.ac API는 호출하지 않는다.
- 로고 사용 시 라이선스/저작권 확인 필요 (별도 검증 항목).
- 향후 solved.ac API 연동 시 자동 갱신으로 마이그레이션할 수 있도록 "수동 입력값(solved_ac_tier_manual)"과 "자동 동기화값(solved_ac_tier_synced)" 필드를 분리해 둔다.

### 4.8 검색 / 필터

- 키워드 검색: 제목, 카테고리명, 연도, 부모 set 경로 텍스트.
- 필터: 카테고리(다중 선택), 연도(year_from / year_to 범위), 본인 완주 여부(완주/미완주/시작 안 함).
- 정렬: 최신순 / 평균 평점순 / 평가 수순 / 완주율순 (개인 또는 팀 컨텍스트 기준).
- 난이도 정렬·필터는 §4.7.1 구현 후에 추가.

### 4.9 알림 (가벼운 인앱)

- 내 제안(problem set / category)이 승인 또는 반려됨.
- 팀 초대 수신 / 수락.
- 팀 owner 권한 자동 이양 통지.
- 이메일 발송은 V1에서는 하지 않음. 인앱 배지/리스트로만.

---

## 5. 화면 구성

### 5.1 화면 목록

| # | 화면 | 주요 내용 | 권한 |
|---|---|---|---|
| S1 | 홈 / Problem Set 트리 (탭명: "출처") | ProblemSet 트리 + 카테고리·연도 범위 필터 | All |
| S1' | 카테고리 목록 (탭명: "둘러보기") | Category 카드, 클릭 시 해당 카테고리에 묶인 ProblemSet 진입 | All |
| S2 | Problem Set 상세 | 리프: 문제 리스트 / 내부 노드: 자식 트리. 별점·코멘트·팀 컨텍스트 + 소속 카테고리 뱃지 | All (일부 기능 User+) |
| S3 | Problem Set 제안 폼 | 사용자 제안 입력 | User+ |
| S4 | 마이페이지 / 프로필 | 내 통계, 내 별점·코멘트, 가시성 설정 | User+ (자기) / All (public 프로필 열람) |
| S5 | 팀 목록 / 생성 | 내 팀 보기, 새 팀 생성, public 팀 둘러보기 | User+ / Guest는 public 둘러보기 |
| S6 | 팀 상세 | 멤버 관리, 초대 링크 발급, 팀 통계 | Member+ / public 팀은 일부 정보 All |
| S7 | Admin 대시보드 | Category/ProblemSet CRUD, 제안 검토 | Admin |
| S8 | 로그인 | OAuth Provider 선택 | All |

### 5.2 핵심 화면 상세

#### S1. Problem Set 트리 (탭: "출처")

- 좌측: 검색바 + 필터 패널 (카테고리 다중 선택, 연도 범위, 키워드).
- 중앙: 모든 ProblemSet의 단일 트리. 루트 노드들이 위에서부터 나열 (ICPC, AtCoder, JOI 등). 펼치기/접기 토글.
- 각 노드 행: 제목 / (리프인 경우) 평균 평점 + 평가 수 / (로그인 시) 본인 완주율 미니바.
- 내부 노드 클릭 시 펼치기. 리프 노드 클릭 시 S2로 이동.

#### S1'. 카테고리 목록 (탭: "둘러보기")

- 카드 그리드: 각 Category에 짧은 이름·설명·포함된 ProblemSet 수.
- 카드 클릭 시 해당 카테고리에 묶인 ProblemSet들을 트리 뷰로 표시 (S1 필터에 카테고리 적용된 형태와 동일).

#### S2. Problem Set 상세

- 헤더: 부모 체인 브레드크럼 / 제목 / 소속 카테고리 뱃지 · 연도 / 평균 평점·평가 수 / set의 외부 링크.
- 리프 노드: 문제 테이블 (라벨 / 제목 / solved.ac 티어 / 외부 링크 / 본인 해결 토글 / [팀 컨텍스트 시] 멤버별 상태).
- 내부 노드: 자식 트리 (각 자식의 평균 평점, 본인 완주율 표시, 펼치기/접기).
- 팀 컨텍스트 토글: 소속 팀 드롭다운.
- 하단: 본인 별점(1~5) + (별점 있을 때) 코멘트 입력란(≤ 300자).
- 코멘트 섹션: 다른 사용자의 코멘트 목록(닉네임, 별점, 본문, 작성/수정 시각).
- "평가자 목록 보기"(로그인 사용자만): 모달로 (닉네임, 별점, 작성 시각) 리스트.

#### S4. 마이페이지 / 프로필

- 자기 페이지: 가시성 설정(public/private), 닉네임·외부 핸들 편집, 풀이 통계, 내 별점·코멘트 목록, 팀 목록.
- 타인의 public 프로필: 닉네임, 외부 핸들, 풀이 통계, 푼 set 목록 (단, 코멘트는 항상 공개).
- 타인의 private 프로필: 닉네임만 표시.

#### S6. 팀 상세

- 멤버 목록 + 역할(owner/member). 멤버 수 / 50.
- 초대 링크 발급 영역(owner): 만료 시간 설정 + 복사 버튼.
- 팀 진척도 요약: 풀이한 set 수, 진행 중 set, 멤버별 완주율 평균 등.
- public 팀일 때 비멤버에게는 일부 정보(개별 멤버의 상세 풀이)는 가려짐 (§4.6.3).

#### S7. Admin 대시보드

- 탭1: Category 관리 (CRUD).
- 탭2: ProblemSet 관리 (트리 뷰 + CRUD, parent 변경, 자식 일괄 처리).
- 탭3: 제안 검토 큐 (CategoryProposal, ProblemSetProposal).
- 탭4: 사용자 관리 (역할 변경, 제재).

---

## 6. 비기능 요구사항

### 6.1 성능 / 규모

- 동시 접속자 수 ~수십 명 가정. 트래픽 적음.
- Problem set 누적 ~수천 건, 문제 ~수만 건 규모를 가정.
- 핵심 페이지(트리·상세) p95 응답 < 500ms 목표.
- 트리 조회는 모든 자식 노드의 본인 완주율 계산이 필요하므로, materialized view나 캐시를 고려.

### 6.2 가용성 / 백업

- 단일 인스턴스 배포 허용. 일일 DB 백업 권장.
- 계획 점검 외 SLA는 별도 정의하지 않음.

### 6.3 보안

- OAuth 토큰은 서버에서만 검증/저장. 클라이언트에는 세션 쿠키만 노출.
- CSRF 보호, XSS 방지(코멘트·메모 sanitize), 레이트 리밋(별점·코멘트·제안에 적용).
- Admin 액션은 감사 로그로 남김(누가 언제 무엇을).
- private 자원에 대한 직접 URL 접근은 인가 검사 후 404 (존재 자체를 노출하지 않음).

### 6.4 개인정보 / 탈퇴

- 탈퇴 시 식별 정보(닉네임, OAuth ID, 외부 핸들)는 즉시 삭제.
- 연관 SolveRecord/Rating/Comment는 "deleted_user" 익명 표식으로 보존.
- 탈퇴 후에도 코멘트는 "(탈퇴한 사용자)" 명의로 유지.

### 6.5 접근성 / i18n

- V1 한국어 우선. 영어 토글은 V2에서 고려.
- 기본 키보드 내비게이션과 충분한 색 대비 보장.

### 6.6 라이선스 고려

- solved.ac 티어 로고 사용 가부를 운영 전에 확인 (라이선스 또는 CC 정책).
- 문제 본문은 저장하지 않으며 외부 링크로만 연결한다 (저작권 회피).

---

## 7. 우선순위 (MVP 기준)

| 우선순위 | 기능 | 설명 |
|---|---|---|
| P0 (MVP) | OAuth 로그인 | Google/GitHub |
| P0 | ProblemSet 트리 조회 (Guest 가능) | 카테고리 다중 선택 / 연도 범위 필터, 펼치기·접기 |
| P0 | ProblemSet 상세 (리프/내부 노드 모두) | |
| P0 | Admin: Category/ProblemSet CRUD | 트리 구조 포함, 초기 데이터 입력 |
| P0 | 개인 SolveRecord 토글 + 완주율 | set·문제·내부 노드 단위 표시 |
| P0 | 별점 1~5 + 평균/평가 수 | 퀄리티 핵심 지표 |
| P0 | 코멘트 (별점 있을 때, ≤ 300자) | |
| P0 | 개인 프로필 가시성 (public/private) | 기본 private |
| P1 | 팀 생성·초대·팀 컨텍스트 보기 | 최대 50명, public/private |
| P1 | 사용자 제안 (Category / ProblemSet) | admin 검토 큐 |
| P1 | 평가자 목록 열람 (로그인 사용자) | 투명성 |
| P1 | solved.ac 티어 수동 메모 | 로고 표시 |
| P1 | SolveRecord 메모 (≤ 200자) | 개인용 |
| P2 | 마이페이지 통계 | 내가 푼 set 목록, 평균 평점 등 |
| P2 | 인앱 알림 | 초대/제안 결과/owner 이양 |
| P2 | 탈퇴 시 익명화 처리 | |
| P3 | 스코어보드 기반 자동 난이도 산정 | 별도 설계 문서 필요 |
| P3 | solved.ac API 연동 | 수동 → 자동 마이그레이션 |
| P3 | i18n (영어) | |

---

## 8. 미결 / 결정 필요 항목

> 본 항목들은 v0.2 시점에서 후속 결정으로 미뤄둔 사항이다. 구현 단계에서 필요에 따라 다시 논의한다.

- **Q-A**: 내부 노드(부모 set)에서 별점·코멘트를 허용할 것인가? 본 명세는 "허용"으로 가정.
- **Q-B**: ProblemSet 트리에서 한 노드를 다른 부모로 옮길 때, 자식 set과 연관 SolveRecord/Rating/Comment는 자동으로 따라가는가? 본 명세는 "따라간다"로 가정.
- **Q-C**: 스코어보드 기반 난이도(P3) 구현 시, "적당한 구간" 컷오프는 ProblemSet 루트별로 다를 가능성이 높다. 루트별 설정 필드를 둘 것인가?
- **Q-D**: 팀이 50명에 도달했을 때, 초대 링크는 자동 비활성화되는가, 수락 시점에서만 막히는가? 본 명세는 "수락 시점에서 막힘"으로 가정.
- **Q-E**: "public 팀의 비멤버 조회 시, 멤버 닉네임을 모두 노출"이 옳은가?
- **Q-F**: 코멘트 신고/모더레이션 기능이 필요한가? V1에서는 admin이 직접 수동 삭제로 가정.
- **Q-G**: 동일 problem(서로 다른 set의 같은 문제)을 식별·연결할 필요가 있는가? V1 미지원으로 가정.