# LLM Model Roles

각 파이프라인 단계에서 역할에 최적화된 모델을 라우팅한다.

## 역할별 모델

| 역할 | 모델 | 환경변수 | 담당 파이프라인 |
|---|---|---|---|
| 메인 브레인 | `qwen3.5-122b-a10b` | `LITELLM_MODEL` | Stage 1 추론/일반 대화 |
| 장문 분석 | `kimi-k2.5` | `ANALYSIS_MODEL` + `ANTHROPIC_MODEL` | Stage 2 설계 + Evolution LLM |
| 코더/툴콜 | `deepseek-v3.1-terminus` | `CODE_GEN_MODEL` | Stage 3 코드 생성 |
| 빠른 응답 | `minimax-m2.5` | `QUICK_MODEL` | Stage 4 Tips/요약 |

모든 모델은 `LITELLM_BASE_URL=http://192.168.0.3:4000/v1` 프록시를 통해 호출된다.

## 호출 함수 매핑

```python
# server/shared/llm/client.py

stream_chat_reply(...)         → LITELLM_MODEL (메인 브레인)
stream_analysis_reply(prompt)  → ANALYSIS_MODEL (장문 분석)
stream_code_gen_reply(prompt)  → CODE_GEN_MODEL (코더)
stream_quick_reply(prompt)     → QUICK_MODEL (빠른 응답)
```

## Evolution LLM 라우팅

`server/modules/evolution/llm.py` → `build_default_llm_service()`:

1. `ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY` 있으면 → `LiteLLMProxyService(ANTHROPIC_MODEL)`
2. `OPENAI_BASE_URL` + `OPENAI_API_KEY` 있으면 → `OpenAICompatLLMService`
3. 둘 다 없으면 → None (에러)

현재 설정: `ANTHROPIC_BASE_URL=http://192.168.0.3:4000/v1` + `ANTHROPIC_MODEL=kimi-k2.5`
→ Evolution은 kimi-k2.5 (장문 분석 역할) 사용
