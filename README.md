# datasphere-mcp

SAP Datasphere 조회 전용 MCP 서버입니다. Python 3.12+, FastMCP, Pydantic,
httpx를 사용하며 `Tool → Service → Adapter → SAP` 구조를 따릅니다.

2026-09-29 실제 DEV의 `BSG_BI / local-tables / T_TEST`에 대해 아래 네 도구의
순차 호출을 검증했습니다. 상세 결과와 분석 범위는 [검증 기록](docs/verification.md)에 있습니다.

현재 범위는 AGENTS.md §30의 Phase 0–3 중 다음 네 도구입니다.

| 도구 | 실제 연결 경로 | 주요 인자 |
|---|---|---|
| `list_spaces` | SAP CLI `spaces list` | environment, limit, offset |
| `list_objects` | SAP CLI `objects <type> list` | environment, space, object_type, limit, offset |
| `get_object` | SAP CLI `objects <type> read` | environment, space, object_type, technical_name |
| `get_dependencies` | 객체 CSN을 읽고 근거가 있는 참조 추출 | 위 인자 + direction, max_depth |

Task 조회·실행, metadata 쓰기·삭제는 이번 범위에 포함하지 않습니다.
DEV/QAS/PRD 모두 READ만 허용하며 서버 설정의 allow_* 값이 true여도 이 버전은
mutation을 허용하지 않습니다. 환경은 모든 도구에서 필수입니다.

## 설치

PowerShell에서 프로젝트 루트로 이동합니다.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e '.[test]'
npm.cmd ci --prefix .tools --ignore-scripts --no-audit --no-fund
Copy-Item .env.example .env  # 최초 한 번만. 기존 .env를 덮어쓰지 마세요.
```

SAP CLI는 `.tools/package-lock.json`의 **2026.19.0**으로 고정합니다.
해당 CLI는 Node 20–24를 지원하며 이 작업 환경에서는 Node 24를 확인했습니다.
Windows에서도 `.cmd` 래퍼 대신 `node terminal.js`를 직접 실행합니다.
Python 런타임 의존성은 AGENTS.md에 지정된 네 라이브러리이며,
pytest / pytest-asyncio는 테스트용입니다.

## DEV 사용자 OAuth 설정

검증 대상: **BSG_BI / local-tables / T_TEST**.

`.env`에 DEV tenant의 **origin URL**과 관리자가 제공한 사용자 기반 OAuth
(Interactive Usage) 정보를 입력합니다. `/dwaas-core/...` 같은 페이지 경로를
BASE_URL에 넣지 않습니다. 비밀값은 채팅이나 MCP 인자로 전달하지 않습니다.

```dotenv
DSP_MOCK_MODE=false
DSP_DEV_BASE_URL=https://YOUR-DEV-TENANT
DSP_DEV_AUTH_MODE=refresh_token
DSP_DEV_TOKEN_URL=https://YOUR-AUTH-HOST/oauth/token
DSP_DEV_CLIENT_ID=YOUR-CLIENT-ID
DSP_DEV_CLIENT_SECRET=YOUR-CLIENT-SECRET
DSP_DEV_REFRESH_TOKEN=YOUR-USER-REFRESH-TOKEN
DSP_DEV_SPACES_BACKEND=cli
```

클라이언트 ID/secret만으로 사용자 로그인이 완료되지는 않습니다. 먼저 사용자가
SAP의 공식 로그인 절차에서 SSO/동의를 완료하고 refresh token을 준비해야 합니다.
기존 CLI 사용자 세션을 가져오는 방법도 지원합니다.

```powershell
# 사용자 터미널에서 실행. 실제 DEV URL로 바꾸세요.
# 비밀값은 CLI의 입력 프롬프트에서 입력합니다.
node .tools/node_modules/@sap/datasphere-cli/terminal.js login --host https://YOUR-DEV-TENANT --authorization-flow authorization_code

# 화면에 토큰을 출력하지 않고, Git에서 제외된 로컬 파일에 저장합니다.
New-Item -ItemType Directory -Force .secrets | Out-Null
node .tools/node_modules/@sap/datasphere-cli/terminal.js config secrets show | Set-Content -Encoding utf8 .secrets/dev.json
```

이 경우 `.env`에 `DSP_DEV_SECRETS_FILE=.secrets/dev.json`을 지정하고
CLIENT_ID/CLIENT_SECRET/TOKEN_URL/REFRESH_TOKEN은 비워둘 수 있습니다.
설정값이 있으면 파일 값보다 우선합니다. 현재 CLI의 secrets export는 배열이며
서버는 BASE_URL과 정확히 일치하는 tenant 세션 하나만 선택합니다.
이 파일은 다른 tenant 세션도 포함할 수 있으므로 소유자 전용으로 보관하세요.
서버는 사용자의 기존 CLI 캐시를 자동 탐색하거나 다른 tenant로 대체하지 않습니다.

인증 토큰은 환경별 메모리에 캐시하고 만료 전에 갱신합니다. 갱신된 refresh token도
메모리에서 교체하지만 파일에 자동 저장하지 않습니다. 토큰 회전을 강제하는 tenant는
서버 재시작 시 새 세션 export가 필요할 수 있습니다. 무인 운영용 암호화 영속 저장소는
향후 범위입니다. 최초 로그인·만료된 사용자 세션의 재인증은 사용자가 수행합니다.

Technical User는 `DSP_DEV_AUTH_MODE=client_credentials`로 선택할 수 있지만,
SAP 문서상 CLI `spaces list`에는 지원 제한이 있습니다. 이 경우 서버 설정으로
`DSP_DEV_SPACES_BACKEND=catalog`를 선택하면 공식 consumption OData catalog를
조회합니다. 이 목록은 consumption에 공개된 범위이므로 전체 modeling space 목록과
같지 않습니다. 권한 오류 시 자동으로 다른 backend로 전환하지 않습니다.

사용자에게 해당 Space 및 모델링 객체의 읽기 권한이 필요합니다. 권한 부족은
서버에서 우회하지 않습니다.

## 실행 및 MCP 연결

```powershell
.venv\Scripts\datasphere-mcp.exe
```

stdio MCP 서버이므로 일반 터미널에서 실행하면 클라이언트 메시지를 기다립니다.
MCP 클라이언트의 서버 설정 예시입니다. 클라이언트가 cwd를 지원하지 않으면
`DSP_ENV_FILE`, `DSP_CLI_ENTRY`, `DSP_DEV_SECRETS_FILE`을 절대 경로로 지정하세요.

### Claude Code
```json
{
  "mcpServers": {
    "datasphere": {
      "command": "C:/Projects/DataSphere/.venv/Scripts/python.exe",
      "args": ["-m", "datasphere_mcp.server"],
      "cwd": "C:/Projects/DataSphere",
      "env": {
        "DSP_ENV_FILE": "C:/Projects/DataSphere/.env",
        "DSP_CLI_ENTRY": "C:/Projects/DataSphere/.tools/node_modules/@sap/datasphere-cli/terminal.js"
      }
    }
  }
}
```

### Codex
```toml
[mcp_servers.datasphere]
command = "C:/Projects/DataSphere/.venv/Scripts/python.exe"
args = ["-m", "datasphere_mcp.server"]
cwd = "C:/Projects/DataSphere"
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 150

[mcp_servers.datasphere.env]
DSP_ENV_FILE = "C:/Projects/DataSphere/.env"
DSP_CLI_ENTRY = "C:/Projects/DataSphere/.tools/node_modules/@sap/datasphere-cli/terminal.js"
DSP_NODE_EXECUTABLE = "C:/Program Files/nodejs/node.exe"
DSP_DEV_SECRETS_FILE = "C:/Projects/DataSphere/.secrets/dev.json"
DSP_MOCK_MODE = "false"
```


호출 순서:

```text
list_spaces(environment="DEV")
list_objects(environment="DEV", space="BSG_BI", object_type="local-tables")
get_object(environment="DEV", space="BSG_BI", object_type="local-tables", technical_name="T_TEST")
get_dependencies(environment="DEV", space="BSG_BI", object_type="local-tables", technical_name="T_TEST", direction="UPSTREAM")
```

지원 object_type enum: local-tables, remote-tables, views, data-flows,
replication-flows, transformation-flows, task-chains, analytic-models,
business-entities, fact-models, consumption-models, data-access-controls, packages.
공식 CLI 문서의 유형 목록을 기준으로 하며, 개별 tenant의 버전·권한에 따라
명령 사용 가능 여부가 다릅니다. tenant discovery는 SAP 공식 CLI에 맡기며
내부 HTTP 엔드포인트를 직접 호출하지 않습니다.

응답은 `success/environment/space/data/warnings` 구조입니다.
`get_object.data.definition`에 SAP CSN/JSON 원본을 보존하되 비밀 필드와
서버가 알고 있는 credential 문자열은 마스킹합니다. 실패는 고정된 안전한
`error.code/error.message`로 반환합니다. 입력 스키마 위반은 MCP 검증 오류입니다.
식별자는 보수적으로 `[A-Za-z_][A-Za-z0-9_.:]*`만 허용합니다.
목록은 `next_offset`으로 다음 페이지를 요청하며 최대 페이지 크기는 200입니다.

## 의존성 분석 범위

확인되지 않은 dependency CLI 명령이나 비공개 API를 만들지 않았습니다.
`get_dependencies`는 **UPSTREAM CSN 메타데이터 분석**입니다.

- CSN `query` / `projection`의 source ref, join, 중첩 SELECT를 추출합니다.
- `cds.Association` / `cds.Composition`의 target을 별도 관계로 표시합니다.
- 컬럼 ref를 객체 의존성으로 잘못 해석하지 않습니다.
- 노드는 `space:technical_name`, 간선은 **의존하는 객체 → 참조 객체**입니다.
- 각 간선에 원본 위치 `evidence`를 제공합니다. 순환은 안전하게 종료합니다.
- Space 내 local/remote table, view, analytic model 목록으로 타입을 확인하고
  제한된 깊이까지 원본 정의를 추가 조회합니다. 존재하지 않는 타입은 추측하지 않습니다.
- 해석할 수 없는 참조는 `resolved=false`, 타입은 null입니다.
- 기본 깊이 3, 최대 10, 기본 노드 한도 100, inventory 한도 500입니다.

항상 `complete=false`입니다. SQL 문자열 파싱, SAP 전용 Analytic Model 형식,
DAC annotation, cross-space 추적의 전체 의미를 보장하지 않습니다. 구조화된 CSN이
없는 객체는 `UNSUPPORTED_CAPABILITY`를 반환하며 빈 그래프로 성공 처리하지 않습니다.
DOWNSTREAM/BOTH도 아직 미지원입니다. SAP 전용 형식 지원은 DEV에서 확보한
비식별 fixture와 공식 사양을 바탕으로 확장해야 합니다.
일반 로컬 테이블의 upstream이 없으면 루트 노드 하나와 빈 간선이 정상입니다.

## 검증

```powershell
.venv\Scripts\python.exe -m pytest -q
```

테스트는 서비스, CLI 인자·격리·타임아웃, OAuth 캐시·갱신·오류, HTTP 제한·재시도,
CSN 분석, FastMCP 인메모리 클라이언트 및 실제 stdio subprocess를 확인합니다.
기본 테스트 실행은 실제 tenant를 호출하지 않습니다.

실제 DEV 검증은 설정을 채운 후 `.env`의 `DSP_RUN_DEV_INTEGRATION=true`로 활성화합니다.

```powershell
.venv\Scripts\python.exe scripts/dev_smoke.py --space BSG_BI --object-type local-tables --technical-name T_TEST --output dev-smoke-result.json
.venv\Scripts\python.exe -m pytest tests/integration -q
```

smoke는 MCP 프로토콜로 네 도구를 순차 호출하고 Space/객체가 목록에 존재하는지도
확인합니다. DEV만 호출하며 mock mode에서는 실패합니다. 보고서에는 원본 메타데이터와
credential을 저장하지 않고 도구별 성공, 안전한 오류 및 dependency 개수만 기록합니다.
테이블 smoke 성공만으로 Analytic Model의 다단계 dependency를 검증했다고 간주하지
마세요. 후속 검증에는 실제 view/model과 알려진 source 관계가 필요합니다.

로컬 개발용 mock 모드:

```powershell
$env:DSP_MOCK_MODE = 'true'
.venv\Scripts\datasphere-mcp.exe
```

fixture는 `BSG_BI: AM_TEST → V_TEST → T_TEST`입니다. AM_TEST는 CSN 동작 테스트를
위한 합성 데이터이며 실제 SAP Analytic Model 형식을 검증한 표본이 아닙니다.
mock 응답에는 항상 명시적인 경고가 붙습니다.

## 보안 및 운용 제한

- shell/SQL/임의 URL/파일경로/CLI option을 받는 MCP 도구는 없습니다.
- 토큰은 CLI argv가 아닌 제한된 자식 환경으로 전달합니다. 매 호출 임시 프로필을
  생성하므로 기존 CLI 캐시의 토큰·환경이 섞이지 않습니다. 정상 종료·실패·취소 시 정리합니다.
- 임시 프로필에서 먼저 공식 CLI `config cache init`으로 tenant 명령 목록을
  받아온 뒤 조회 명령을 실행합니다. 두 프로세스에 공통 CLI 시간 제한을 적용합니다.
  초기화는 임시 로컬 캐시만 생성하며 SAP 객체를 변경하지 않습니다.
- TLS 검증은 끌 수 없습니다. HTTP redirect를 따라가지 않습니다.
- HTTP connect/read 및 전체 작업, CLI process에 시간 제한이 있습니다.
- HTTP GET의 429/502/503/504만 제한적으로 재시도합니다. OAuth POST는 자동 재시도하지 않습니다.
- 기본 최대 응답 크기는 25 MiB입니다. CLI stdout/stderr는 읽는 중 제한하고,
  CLI 결과 파일은 완료 후 크기를 검사합니다. 종료 전 디스크 파일 증가를 실시간 차단하지는 않습니다.
- 로그는 stderr에 구조화된 메타데이터만 기록하며 raw upstream 오류를 출력하지 않습니다.
- 환경변수/세션 파일은 서버 실행 계정이 관리합니다. MCP는 로컬 stdio 전용입니다.

## 인터페이스 근거

2026-09-29에 공식 문서와 설치된 SAP CLI 2026.19.0을 확인했습니다.

- [SAP 모델링 객체 CLI](https://help.sap.com/docs/SAP_DATASPHERE/d0ecd6f297ac40249072a44df0549c1a/e3b2cbef9d1f4b38b51c64fe9e88c0aa.html)
- [SAP Space CLI](https://help.sap.com/docs/SAP_DATASPHERE/d0ecd6f297ac40249072a44df0549c1a/5ce5a2de69f24373a477c5d68e175c64.html)
- [SAP CLI 인증/공통 옵션](https://help.sap.com/docs/SAP_DATASPHERE/d0ecd6f297ac40249072a44df0549c1a/d483a0f480af452e9dda47f885ab87ad.html)
- [공식 CLI 패키지](https://www.npmjs.com/package/@sap/datasphere-cli)
- [공식 consumption OData API](https://help.sap.com/docs/SAP_DATASPHERE/43509d67b8b84e66a30851e832f66911/7a453609c8694b029493e7d87e0de60a.html)
- [SAP CSN](https://cap.cloud.sap/docs/cds/csn) / [CQN](https://cap.cloud.sap/docs/cds/cqn)

REST/OData는 consumption catalog Space 조회에 사용합니다. modeling 객체 정의를
조회하는 동등한 공개 REST 계약은 확인되지 않아 해당 기능은 공식 CLI로 구현했습니다.
