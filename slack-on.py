#!/usr/bin/env python3
import os
import time
import json
import logging
import subprocess
from dotenv import load_dotenv
from slack_sdk import WebClient

# ----------------- 디버깅 설정 -----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# -----------------------------------------------

load_dotenv()

CHANNEL_ID = os.getenv("CHANNEL_ID", "C0AQGV7SCQP")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

client = WebClient(token=SLACK_BOT_TOKEN)


import glob

def get_latest_claude_session_id() -> str:
    try:
        pattern = os.path.expanduser("~/.claude/projects/*/*.jsonl")
        files = glob.glob(pattern)
        if not files:
            return ""
        latest_file = max(files, key=os.path.getmtime)
        return os.path.basename(latest_file).replace(".jsonl", "")
    except Exception as e:
        logging.error(f"최근 세션 불러오기 에러: {e}")
        return ""


def ask_claude_agent(user_text: str) -> str:
    logging.info(f"진입: ask_claude_agent() -> 사용자 입력: '{user_text}'")
    
    # 원래 c-nim Alias에서 가져오던 환경변수들을 완벽하게 세팅합니다.
    env = os.environ.copy()
    env["CLAUDE_NIM_MODE"] = "1"
    env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:4000"
    env["ANTHROPIC_API_KEY"] = "sk-litellm-local"
    env["ANTHROPIC_MODEL"] = "claude-3-5-sonnet"

    cmd = [
        "/Users/lsy/.npm-global/bin/claude",
        "--permission-mode", "bypassPermissions",
        "-p",
        "--verbose",
        "--output-format", "stream-json",
        "--include-partial-messages"
    ]

    # 로컬 파일 시스템을 뒤져서 가장 최근에 저장된 에이전트 세션 ID를 가져옵니다.
    latest_session_id = get_latest_claude_session_id()
    if latest_session_id:
        logging.info(f"이전 기억(Context) 복원용 세션 ID 탑재: {latest_session_id}")
        cmd.extend(["--resume", latest_session_id])
    
    cmd.append(user_text)

    try:
        proc = subprocess.Popen(
            cmd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
        )

        final_text = ""
        for line in proc.stdout:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                # 에이전트 도구 수행 과정 전체가 끝나고 출력된 결과값
                if data.get("type") == "result":
                    result_text = data.get("result", "")
                    if result_text and not final_text:
                        final_text = result_text
                
                # 메시지가 스트리밍으로 올 때 차곡차곡 모으기
                elif data.get("type") == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text_chunk = delta.get("text", "")
                        final_text += text_chunk
            except Exception:
                pass
                
        proc.wait()
        
        # CLI 실행 실패 (예: 크레딧 부족 등 에러)
        if proc.returncode != 0:
            err = proc.stderr.read()
            logging.error(f"Claude CLI 호출 실패: {err}")
            return f"🚨 에이전트 구동 실패 (CLI 오류):\n{err.strip()[:500]}"
            
        logging.info(f"성공: Agent 작업/응답 완료 -> '{final_text[:100]}...'")
        return final_text.strip() or "명령이 성공적으로 수행되었으나 출력할 텍스트가 없습니다."

    except Exception as e:
        logging.error(f"서브프로세스(CLI) 실행 중 에러: {str(e)}", exc_info=True)
        return f"🚨 시스템 에러 발생: {str(e)}"


def ask_claude_agent_stream(user_text: str):
    logging.info(f"진입: ask_claude_agent_stream() -> 사용자 입력: '{user_text}'")
    
    env = os.environ.copy()
    env["CLAUDE_NIM_MODE"] = "1"
    env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:4000"
    env["ANTHROPIC_API_KEY"] = "sk-litellm-local"
    env["ANTHROPIC_MODEL"] = "claude-3-5-sonnet"

    cmd = [
        "/Users/lsy/.npm-global/bin/claude",
        "--permission-mode", "bypassPermissions",
        "-p",
        "--verbose",
        "--output-format", "stream-json",
        "--include-partial-messages"
    ]

    latest_session_id = get_latest_claude_session_id()
    if latest_session_id:
        cmd.extend(["--resume", latest_session_id])
    
    cmd.append(user_text)

    try:
        proc = subprocess.Popen(
            cmd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
        )

        accumulated_text = ""
        last_update_time = time.time()
        
        for line in proc.stdout:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                
                # 도구 사용이나 생각 중인 상태를 UI에 반영하고 싶다면 여기서 감지 가능
                if data.get("type") == "thought_delta":
                    pass # 필요시 처리

                if data.get("type") == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text_chunk = delta.get("text", "")
                        accumulated_text += text_chunk
                        
                        # 너무 자주 업데이트하면 Rate Limit 걸리므로 약 1.5초마다 업데이트
                        if time.time() - last_update_time > 1.5:
                            yield {"type": "partial", "text": accumulated_text}
                            last_update_time = time.time()
                
                elif data.get("type") == "result":
                    result_text = data.get("result", "")
                    if result_text:
                        accumulated_text = result_text
            except Exception:
                pass
                
        proc.wait()
        
        if proc.returncode != 0:
            err = proc.stderr.read()
            yield {"type": "error", "text": f"🚨 에이전트 구동 실패:\n{err.strip()[:300]}"}
        else:
            yield {"type": "final", "text": accumulated_text.strip() or "명령이 성공적으로 수행되었습니다."}

    except Exception as e:
        yield {"type": "error", "text": f"🚨 시스템 에러: {str(e)}"}


def main():
    try:
        auth = client.auth_test()
        bot_user_id = auth["user_id"]
        logging.info(f"Slack 봇 인증 성공! 봇 유저: {auth['user']} (ID: {bot_user_id})")
    except Exception as e:
        logging.error(f"Slack 봇 인증 실패: {str(e)}")
        return

    last_ts = str(time.time())

    while True:
        try:
            history = client.conversations_history(channel=CHANNEL_ID, limit=5)
            msgs = history["messages"]

            new_msgs = []
            for msg in msgs:
                if msg.get("user") == bot_user_id or msg.get("subtype") == "bot_message":
                    continue
                if last_ts and msg["ts"] <= last_ts:
                    continue
                text = msg.get("text", "").strip()
                if not text or f"<@{bot_user_id}>" not in text:
                    continue
                new_msgs.append(msg)

            if new_msgs:
                for msg in reversed(new_msgs):
                    text = msg["text"].replace(f"<@{bot_user_id}>", "").strip()
                    user = msg.get("user", "Unknown")
                    logging.info(f"처리 중: '{text}' by {user}")
                    
                    # 프리미엄 UI: Blocks 사용
                    response = client.chat_postMessage(
                        channel=CHANNEL_ID,
                        text="Trinity Agent가 작업을 시작합니다.", # 알림용 텍스트 추가
                        blocks=[
                            {
                                "type": "section",
                                "text": {"type": "mrkdwn", "text": "🚀 *Trinity Agent* 가 작업을 시작합니다..."}
                            },
                            {
                                "type": "context",
                                "elements": [{"type": "mrkdwn", "text": "⏳ 로컬 파일 시스템 및 팀 에이전트 분석 중"}]
                            }
                        ]
                    )
                    ts = response["ts"]
                    
                    final_answer = ""
                    buffer = ""
                    line_buffer = ""  # 현재 만들어지고 있는 줄

                    for update in ask_claude_agent_stream(text):
                        if update["type"] == "partial":
                            new_text = update["text"][len(buffer):]
                            buffer = update["text"]
                            
                            for char in new_text:
                                if char == "\n":
                                    # 줄 완성! ⏺ 있으면 전송
                                    if "⏺" in line_buffer and line_buffer.strip():
                                        client.chat_postMessage(
                                            channel=CHANNEL_ID,
                                            text=line_buffer.strip()
                                        )
                                    line_buffer = ""
                                else:
                                    line_buffer += char

                        elif update["type"] == "final":
                            final_answer = update["text"]
                        elif update["type"] == "error":
                            final_answer = update["text"]
                            
                    # 남은 줄 처리 (마지막 줄이 개행문자로 끝나지 않았을 경우)
                    if "⏺" in line_buffer and line_buffer.strip():
                        client.chat_postMessage(
                            channel=CHANNEL_ID,
                            text=line_buffer.strip()
                        )
                        line_buffer = ""

                    # 최종 결과 전송 (아름다운 포맷으로)
                    client.chat_update(
                        channel=CHANNEL_ID,
                        ts=ts,
                        text="작업이 완료되었습니다.", # 알림용 텍스트 추가
                        blocks=[
                            {
                                "type": "section",
                                "text": {"type": "mrkdwn", "text": "✅ *작업이 완료되었습니다*"}
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "section",
                                "text": {"type": "mrkdwn", "text": final_answer}
                            },
                            {
                                "type": "context",
                                "elements": [{"type": "mrkdwn", "text": "Trinity-Chimera Project Management System"}]
                            }
                        ]
                    )
                last_ts = new_msgs[0]["ts"]

        except Exception as e:
            logging.error(f"메인 루프 에러: {str(e)}")

        time.sleep(3)


if __name__ == "__main__":
    logging.info("🚀 Slack <-> Claude CLI Agent 연결 모드 구동 시작")
    main()