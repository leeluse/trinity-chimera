# LLM Model Roles

> **Last Updated**: 2026-05-11

채팅 파이프라인 및 백테스트 분석의 각 단계에서 목적에 맞는 모델로 라우팅합니다. 모든 설정은 `.env` 파일을 통해 제어됩니다.

---

## 1. 전역 LLM 공급자 설정

`server/shared/llm/client.py` 가 모델 호출을 단일화하여 처리합니다.

| 환경 변수 | 설명 | 기본값 |
|---|---|---|
| `LLM_PROVIDER` | `litellm` (범용 API 프록시) 또는 `ollama` (로컬) | `ollama` |
| `LITELLM_BASE_URL` | OpenAI 호환 엔드포인트 주소 | `http://192.168.0.3:4000/v1` |
| `LITELLM_MODEL` | LiteLLM 사용 시 기본 모델 명 | `gpt-oss:120b-cloud` |
| `OLLAMA_BASE_URL` | Ollama 서버 엔드포인트 | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama 사용 시 기본 로컬 모델 | `gpt-oss:120b-cloud` |
| `LLM_ENABLE_OLLAMA_FALLBACK` | LiteLLM 오류 발생 시 로컬 Ollama 자동 전환 여부 | `0` (False) |

---

## 2. 역할별 오버라이드 모델

기본 모델(Default Model) 외에 파이프라인의 각 단계(Role)별로 다른 모델을 지정할 수 있습니다.

| 역할 | 환경 변수 | 담당 파이프라인 단계 | 권장 모델 특성 |
|---|---|---|---|
| 빠른 응답 | `QUICK_MODEL` | 인텐트 분류, 짧은 요약, 에러 메시지 생성 | 빠르고 가벼운 모델 (예: Qwen 7B) |
| 장문 분석 | `ANALYSIS_MODEL` | Stage 2 (전략 설계/YAML 청사진 생성) | 컨텍스트 윈도우가 크고 추론력이 높은 모델 |
| 코더/툴콜 | `CODE_GEN_MODEL` | Stage 3 (Python 코드 생성) | 코딩 전용 파인튜닝 모델 (예: DeepSeek-Coder) |
| 코더 폴백 | `CODE_GEN_FALLBACK_MODEL` | Stage 3 코드 생성 실패 시 재시도 모델 | 안정성이 높은 모델 |

> **동작 방식**: 각 환경 변수가 비어 있으면, 전역 `LITELLM_MODEL` 또는 `OLLAMA_MODEL` 로 자동 폴백됩니다.

---

## 3. 호출 함수 매핑

`server/shared/llm/client.py` 에 정의된 래퍼(Wrapper) 함수를 통해 호출합니다.

```python
# 1. 기본 대화형 응답 (메인 브레인)
async for chunk in stream_chat_reply(prompt, model=None, temperature=0.2)

# 2. Stage 2 (설계/분석) — ANALYSIS_MODEL 사용
async for chunk in stream_analysis_reply(prompt)

# 3. Stage 3 (코드 생성) — CODE_GEN_MODEL 사용 + 타임아웃/재시도 강화
async for chunk in stream_code_gen_reply(prompt)

# 4. 빠른 응답 — QUICK_MODEL 사용
async for chunk in stream_quick_reply(prompt)
```

---

## 4. Temperature 분리 전략

각 파이프라인 성격에 맞게 Temperature를 다르게 적용합니다.

| 단계 / 목적 | Temperature | 이유 |
|---|---|---|
| Stage 2 설계 (분석) | `0.2` ~ `0.3` | 일관성 있는 구조 설계 |
| Stage 3 코드 생성 | `0.3` | 문법적 정확도 및 구조적 견고함 우선 |
| 일반 채팅 | `0.2` ~ `0.3` | 환각 방지 및 팩트 기반 응답 |
| 인텐트 분류 (빠른 응답) | `0.05` | 결정론적이고 빠르고 정확한 JSON/키워드 추출 |

---

## 5. 코드 생성(Code Gen) 안정화 장치

코드를 생성하는 작업(`stream_code_gen_reply`)은 스트리밍 실패가 빈번할 수 있어, 다음과 같은 3단계 폴백 로직이 내장되어 있습니다.

1. **자동 재시도**: 스트리밍 중 타임아웃 발생 시 지정된 횟수(`CHAT_CODE_GEN_STREAM_RETRIES`)만큼 재시도
2. **Non-Stream 폴백**: 스트리밍이 계속 실패하면 `stream=False` 로 단일 요청 시도 (`CHAT_CODE_GEN_NON_STREAM_FALLBACK`)
3. **모델 폴백**: 주 코딩 모델이 뻗은 경우 `CODE_GEN_FALLBACK_MODEL` 환경 변수에 지정된 백업 모델로 재시도
