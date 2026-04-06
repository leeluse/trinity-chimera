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
        # 에이전트가 로컬 파일 전체를 볼 수 있고, 세션도 호환되도록 최상위 루트 폴더 기준(cwd)으로 실행합니다
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        proc = subprocess.Popen(
            cmd, env=env, cwd=project_root,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
        )

        final_text = ""
        raw_output_buffer = []
        for line in proc.stdout:
            if not line.strip():
                continue
            
            # 모든 라인을 혹시 모를 에러 대비용으로 일단 백업합니다
            raw_output_buffer.append(line.strip())
            
            try:
                data = json.loads(line)
                # 에이전트 도구 수행 과정 전체가 끝나고 출력된 결과값
                if data.get("type") == "result":
                    result_text = data.get("result", "")
                    if result_text and not final_text:
                        final_text = result_text
                        
                    # 만약 JSON 결과 객체에 에러 배열이 있다면 포착
                    if data.get("is_error") and data.get("errors"):
                        raw_output_buffer.extend([str(e) for e in data.get("errors")])
                
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
            err = proc.stderr.read().strip()
            if not err:
                err = "\n".join(raw_output_buffer[-10:])  # 마지막 10줄만 출력
            logging.error(f"Claude CLI 호출 실패: {err}")
            return f"🚨 에이전트 구동 실패 (CLI 오류):\n{err[:500]}"
            
        logging.info(f"성공: Agent 작업/응답 완료 -> '{final_text[:100]}...'")
        return final_text.strip() or "명령이 성공적으로 수행되었으나 출력할 텍스트가 없습니다."

    except Exception as e:
        logging.error(f"서브프로세스(CLI) 실행 중 에러: {str(e)}", exc_info=True)
        return f"🚨 시스템 에러 발생: {str(e)}"


def main():
    try:
        auth = client.auth_test()
        bot_user_id = auth["user_id"]
        logging.info(f"Slack 봇 인증 성공! 봇 유저: {auth['user']} (ID: {bot_user_id})")
    except Exception as e:
        logging.error(f"Slack 봇 인증 실패: {str(e)}")
        return

    # 봇이 켜지기 전 과거 메시지 무시
    last_ts = str(time.time())

    while True:
        try:
            history = client.conversations_history(channel=CHANNEL_ID, limit=10)
            msgs = history["messages"]

            new_msgs = []
            for msg in msgs:
                if msg.get("user") == bot_user_id:
                    continue
                if msg.get("subtype") == "bot_message":
                    continue
                if last_ts and msg["ts"] <= last_ts:
                    continue
                if not msg.get("text", "").strip():
                    continue
                new_msgs.append(msg)

            if new_msgs:
                logging.info(f"새로운 Slack 사용자 메시지 {len(new_msgs)}개 감지됨!")
                for msg in reversed(new_msgs):
                    text = msg["text"].strip()
                    user = msg.get("user", "Unknown")
                    logging.info(f"처리 중 - 작성자: {user}, 내용: '{text}'")
                    
                    # 대기 상태를 알리기 위해 '생각 중' 메시지를 먼저 전송합니다.
                    thinking_response = client.chat_postMessage(
                        channel=CHANNEL_ID,
                        text="⏳ *에이전트가 로컬 파일 환경에서 작업 중입니다... 잠시만 기다려주세요*"
                    )
                    
                    # 이제 단순 언어모델이 아닌 Claude CLI Agent 구동 모듈을 호출!!
                    answer = ask_claude_agent(text)
                    
                    # 처리가 끝나면 기존에 보냈던 '생각 중' 메시지의 내용을 실제 답변으로 덮어씌웁니다.
                    client.chat_update(
                        channel=CHANNEL_ID,
                        ts=thinking_response["ts"],
                        text=answer
                    )
                    logging.info(f"채널 답변 전송 완료!")

                last_ts = new_msgs[0]["ts"]

        except Exception as e:
            logging.error(f"메인 루프 에러: {str(e)}")

        time.sleep(3)


if __name__ == "__main__":
    logging.info("🚀 Slack <-> Claude CLI Agent 연결 모드 구동 시작")
    main()
