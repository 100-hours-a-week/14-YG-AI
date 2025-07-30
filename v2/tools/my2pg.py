# embedding_pipeline.py
import asyncio
import asyncpg
from openai import AsyncOpenAI
from typing import List, Dict, Any
import logging
import math
import json
import os
from datetime import datetime
import sys

# 기존 MySQL 관련 import들
import pymysql
from sshtunnel import SSHTunnelForwarder

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 상태 저장 파일 경로
STATE_FILE = "embedding_state.json"

# MySQL 설정
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "pass",
    "database": "moongsan_dev_db",
    # "charset": "utf8mb4",
}

# SSH 설정
SSH_CONFIG = {
    "ssh_host": "dev.moongsan.com",
    "ssh_port": 22,
    "ssh_username": "ubuntu",
    "ssh_pkey": "./lsh-study-key",
}

POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "moongsan_admin",
    "password": "PgV3ct0r#2024!",
    "database": "moongsan_dev_db",
    # SSH 설정 추가
    "ssh_host": "dev.moongsan.com",
    "ssh_port": 22,
    "ssh_user": "ubuntu",
    "ssh_pkey": "./lsh-study-key",
}

# Upstage 설정
UPSTAGE_CONFIG = {
    "api_key": "up_YkLK9aJvBbyvTeixF45c5BqlROU8P",
    "base_url": "https://api.upstage.ai/v1",
    "embedding_model": "embedding-query",
    "vector_dimension": 4096,
}

# Upstage 클라이언트 초기화
async_openai_client = AsyncOpenAI(
    api_key=UPSTAGE_CONFIG["api_key"], base_url=UPSTAGE_CONFIG["base_url"]
)


# 상태 관리 함수들
def save_last_processed_id(last_id: int):
    """마지막 처리된 ID를 파일에 저장"""
    state = {"last_processed_id": last_id, "last_updated": datetime.now().isoformat()}

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    logger.info(f"마지막 처리된 ID 저장: {last_id}")


def get_last_processed_id() -> int:
    """마지막 처리된 ID를 파일에서 조회"""
    if not os.path.exists(STATE_FILE):
        logger.info("상태 파일이 없습니다. 처음 실행으로 간주")
        return 0

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

        last_id = state.get("last_processed_id", 0)
        logger.info(f"마지막 처리된 ID: {last_id}")
        return last_id

    except Exception as e:
        logger.error(f"상태 파일 읽기 실패: {e}")
        return 0


def reset_state():
    """상태 파일을 삭제하여 처음부터 다시 시작"""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        logger.info(
            "상태 파일이 삭제되었습니다. 다음 실행 시 전체 데이터를 처리합니다."
        )
    else:
        logger.info("상태 파일이 존재하지 않습니다.")


def show_current_state():
    """현재 상태 정보 출력"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)

            print("=" * 50)
            print("📊 현재 상태 정보")
            print("=" * 50)
            print(f"마지막 처리된 ID: {state.get('last_processed_id', 0)}")
            print(f"마지막 업데이트: {state.get('last_updated', 'N/A')}")
            print("=" * 50)

        except Exception as e:
            logger.error(f"상태 파일 읽기 실패: {e}")
    else:
        print("=" * 50)
        print("📊 현재 상태 정보")
        print("=" * 50)
        print("상태 파일이 없습니다. 처음 실행 상태입니다.")
        print("=" * 50)


# MySQL 연결 함수들
def get_group_buy_data():
    """SSH 터널을 통해 MySQL에 연결하고 group_buy 테이블 모든 데이터를 조회"""

    # SSH 터널 설정
    tunnel = SSHTunnelForwarder(
        (SSH_CONFIG["ssh_host"], SSH_CONFIG["ssh_port"]),
        ssh_username=SSH_CONFIG["ssh_username"],
        ssh_pkey=SSH_CONFIG["ssh_pkey"],
        remote_bind_address=(DB_CONFIG["host"], DB_CONFIG["port"]),
        local_bind_address=("127.0.0.1", 0),  # 자동으로 로컬 포트 할당
    )

    try:
        # SSH 터널 시작
        tunnel.start()
        print(f"SSH 터널이 생성되었습니다. 로컬 포트: {tunnel.local_bind_port}")

        # MySQL 연결
        connection = pymysql.connect(
            host="127.0.0.1",  # SSH 터널을 통해 로컬호스트로 연결
            port=tunnel.local_bind_port,  # SSH 터널의 로컬 포트 사용
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            # charset=DB_CONFIG["charset"],
        )

        print("MySQL 연결 성공!")

        # 쿼리 실행
        with connection.cursor() as cursor:
            sql = "SELECT id, title, name, description FROM group_buy ORDER BY id ASC"
            cursor.execute(sql)
            results = cursor.fetchall()

            print(f"조회된 레코드 수: {len(results)}")
            return results

    except Exception as e:
        print(f"오류 발생: {e}")
        return None

    finally:
        # 연결 종료
        if "connection" in locals():
            connection.close()
            print("MySQL 연결 종료")
        tunnel.stop()
        print("SSH 터널 종료")


def get_new_group_buy_data(last_processed_id: int = 0):
    """SSH 터널을 통해 MySQL에 연결하고 새로운 group_buy 데이터만 조회"""

    # SSH 터널 설정
    tunnel = SSHTunnelForwarder(
        (SSH_CONFIG["ssh_host"], SSH_CONFIG["ssh_port"]),
        ssh_username=SSH_CONFIG["ssh_username"],
        ssh_pkey=SSH_CONFIG["ssh_pkey"],
        remote_bind_address=(DB_CONFIG["host"], DB_CONFIG["port"]),
        local_bind_address=("127.0.0.1", 0),
    )

    try:
        # SSH 터널 시작
        tunnel.start()
        print(f"SSH 터널이 생성되었습니다. 로컬 포트: {tunnel.local_bind_port}")

        # MySQL 연결
        connection = pymysql.connect(
            host="127.0.0.1",
            port=tunnel.local_bind_port,
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            # charset=DB_CONFIG["charset"],
        )

        print("MySQL 연결 성공!")

        # 새로운 데이터만 조회 (ID가 last_processed_id보다 큰 것)
        with connection.cursor() as cursor:
            sql = """
            SELECT id, title, name, description 
            FROM group_buy 
            WHERE id > %s 
            ORDER BY id ASC
            """
            cursor.execute(sql, (last_processed_id,))
            results = cursor.fetchall()

            print(f"새로운 레코드 수: {len(results)}")
            if results:
                print(f"처리할 ID 범위: {results[0][0]} ~ {results[-1][0]}")

            return results

    except Exception as e:
        print(f"오류 발생: {e}")
        return None

    finally:
        # 연결 종료
        if "connection" in locals():
            connection.close()
            print("MySQL 연결 종료")
        tunnel.stop()
        print("SSH 터널 종료")


# 임베딩 관련 함수들
async def embed_text_async(text: str) -> List[float]:
    """Upstage 임베딩 API 호출 (검증 로직 포함)"""
    try:
        response = await async_openai_client.embeddings.create(
            input=text, model=UPSTAGE_CONFIG["embedding_model"]
        )
        embedding = response.data[0].embedding

        # 1. 기본 검증
        if not embedding or not isinstance(embedding, list):
            raise ValueError("임베딩 결과가 비어 있음")

        # 2. 차원 검증
        if len(embedding) != UPSTAGE_CONFIG["vector_dimension"]:
            raise ValueError(
                f"임베딩 차원 불일치: 예상 {UPSTAGE_CONFIG['vector_dimension']}, "
                f"실제 {len(embedding)}"
            )

        # 3. 값 타입 검증
        if not all(isinstance(x, (int, float)) for x in embedding):
            raise ValueError("임베딩에 숫자가 아닌 값이 포함됨")

        # 4. 값 범위 검증
        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude == 0:
            raise ValueError("임베딩 벡터의 크기가 0입니다")

        logger.info(f"✅ 임베딩 검증 완료: 차원={len(embedding)}, 크기={magnitude:.4f}")
        return embedding

    except Exception as e:
        raise RuntimeError(f"임베딩 실패: {e}")


def combine_text_fields(title: str, name: str, description: str) -> str:
    """title, name, description을 하나의 텍스트로 결합"""
    parts = []
    if title:
        parts.append(f"제목: {title}")
    if name:
        parts.append(f"이름: {name}")
    if description:
        parts.append(f"설명: {description}")

    return " | ".join(parts)


# PostgreSQL 관련 함수들
async def create_postgres_connection():
    """SSH 터널을 통한 PostgreSQL 연결 생성"""
    tunnel = None
    conn = None

    try:
        # SSH 터널 설정
        tunnel = SSHTunnelForwarder(
            (POSTGRES_CONFIG["ssh_host"], POSTGRES_CONFIG["ssh_port"]),
            ssh_username=POSTGRES_CONFIG["ssh_user"],
            ssh_pkey=POSTGRES_CONFIG["ssh_pkey"],
            remote_bind_address=(POSTGRES_CONFIG["host"], POSTGRES_CONFIG["port"]),
            local_bind_address=("127.0.0.1", 0),
        )

        # SSH 터널 시작
        tunnel.start()
        logger.info(
            f"PostgreSQL SSH 터널이 생성되었습니다. 로컬 포트: {tunnel.local_bind_port}"
        )

        # PostgreSQL 연결
        conn = await asyncpg.connect(
            host="127.0.0.1",
            port=tunnel.local_bind_port,
            user=POSTGRES_CONFIG["user"],
            password=POSTGRES_CONFIG["password"],
            database=POSTGRES_CONFIG["database"],
        )
        logger.info("PostgreSQL 연결 성공!")

        # 터널과 연결을 튜플로 반환
        return conn, tunnel

    except Exception as e:
        logger.error(f"PostgreSQL 연결 실패: {e}")
        if tunnel:
            tunnel.stop()
        if conn:
            await conn.close()
        raise


async def insert_embedding_to_postgres(conn, id_val: int, embedding: List[float]):
    """PostgreSQL에 임베딩 데이터 삽입"""
    try:
        # pgvector 형식으로 변환
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"

        # 데이터 삽입 (UPSERT - 중복 시 업데이트)
        query = """
        INSERT INTO group_buy_vectors (id, embedding) 
        VALUES ($1, $2::vector)
        ON CONFLICT (id) 
        DO UPDATE SET embedding = $2::vector
        """

        await conn.execute(query, id_val, embedding_str)
        logger.info(f"ID {id_val} 임베딩 저장 완료")

    except Exception as e:
        logger.error(f"ID {id_val} 임베딩 저장 실패: {e}")
        raise


async def process_single_record(conn, record: tuple) -> bool:
    """단일 레코드 처리 (임베딩 생성 및 저장)"""
    try:
        id_val, title, name, description = record

        # 텍스트 결합
        combined_text = combine_text_fields(title or "", name or "", description or "")

        if not combined_text.strip():
            logger.warning(f"ID {id_val}: 빈 텍스트, 건너뜀")
            return False

        # 임베딩 생성
        embedding = await embed_text_async(combined_text)

        # PostgreSQL에 저장
        await insert_embedding_to_postgres(conn, id_val, embedding)

        return True

    except Exception as e:
        logger.error(f"레코드 처리 실패 {record}: {e}")
        return False


# 메인 처리 함수들
async def process_group_buy_embeddings(batch_size: int = 10):
    """MySQL에서 모든 데이터를 가져와 임베딩 처리 후 PostgreSQL에 저장"""

    # 1. MySQL에서 데이터 가져오기
    logger.info("MySQL에서 모든 데이터 조회 시작...")
    mysql_data = get_group_buy_data()

    if not mysql_data:
        logger.error("MySQL 데이터 조회 실패")
        return

    logger.info(f"총 {len(mysql_data)}개 레코드 조회 완료")

    # 2. PostgreSQL 연결
    conn, tunnel = await create_postgres_connection()

    try:
        # 3. 배치 처리로 임베딩 생성 및 저장
        success_count = 0
        total_count = len(mysql_data)

        # 배치 단위로 처리
        for i in range(0, total_count, batch_size):
            batch = mysql_data[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_count + batch_size - 1) // batch_size

            logger.info(
                f"배치 {batch_num}/{total_batches} 처리 시작 ({len(batch)}개 레코드)"
            )

            # 배치 내 레코드들을 비동기 처리
            batch_tasks = [process_single_record(conn, record) for record in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # 결과 집계
            batch_success = sum(1 for result in batch_results if result is True)
            success_count += batch_success

            logger.info(f"배치 {batch_num} 완료: {batch_success}/{len(batch)} 성공")

            # 배치 간 잠시 대기 (API 레이트 리밋 방지)
            if i + batch_size < total_count:
                await asyncio.sleep(1)

        # 전체 처리 완료 시 마지막 ID 저장
        if mysql_data:
            last_id = max(record[0] for record in mysql_data)
            save_last_processed_id(last_id)

        logger.info(f"🎉 전체 처리 완료: {success_count}/{total_count} 성공")

    except Exception as e:
        logger.error(f"처리 중 오류 발생: {e}")

    finally:
        # PostgreSQL 연결 및 SSH 터널 종료
        if conn:
            await conn.close()
            logger.info("PostgreSQL 연결 종료")
        if tunnel:
            tunnel.stop()
            logger.info("PostgreSQL SSH 터널 종료")


async def process_new_group_buy_embeddings(batch_size: int = 10):
    """새로운 group_buy 데이터만 임베딩 처리 후 PostgreSQL에 저장"""

    # 1. 마지막 처리된 ID 조회
    last_processed_id = get_last_processed_id()
    logger.info(f"마지막 처리된 ID: {last_processed_id}")

    # 2. MySQL에서 새로운 데이터만 가져오기
    logger.info("MySQL에서 새로운 데이터 조회 시작...")
    mysql_data = get_new_group_buy_data(last_processed_id)

    if not mysql_data:
        logger.info("처리할 새로운 데이터가 없습니다.")
        return

    if len(mysql_data) == 0:
        logger.info("새로운 데이터가 없습니다.")
        return

    logger.info(f"새로운 레코드 {len(mysql_data)}개 발견")

    # 3. PostgreSQL 연결
    conn, tunnel = await create_postgres_connection()

    try:
        # 4. 배치 처리로 임베딩 생성 및 저장
        success_count = 0
        total_count = len(mysql_data)
        processed_ids = []

        # 배치 단위로 처리
        for i in range(0, total_count, batch_size):
            batch = mysql_data[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_count + batch_size - 1) // batch_size

            logger.info(
                f"배치 {batch_num}/{total_batches} 처리 시작 ({len(batch)}개 레코드)"
            )

            # 배치 내 레코드들을 비동기 처리
            batch_tasks = [process_single_record(conn, record) for record in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # 결과 집계 및 성공한 ID 수집
            batch_success = 0
            for j, result in enumerate(batch_results):
                if result is True:
                    batch_success += 1
                    processed_ids.append(batch[j][0])  # ID 저장

            success_count += batch_success

            logger.info(f"배치 {batch_num} 완료: {batch_success}/{len(batch)} 성공")

            # 배치 간 잠시 대기 (API 레이트 리밋 방지)
            if i + batch_size < total_count:
                await asyncio.sleep(1)

        # 5. 성공적으로 처리된 경우 마지막 ID 업데이트
        if processed_ids:
            max_processed_id = max(processed_ids)
            save_last_processed_id(max_processed_id)
            logger.info(f"마지막 처리된 ID 업데이트: {max_processed_id}")

        logger.info(f"🎉 새로운 데이터 처리 완료: {success_count}/{total_count} 성공")

    except Exception as e:
        logger.error(f"처리 중 오류 발생: {e}")

    finally:
        # PostgreSQL 연결 및 SSH 터널 종료
        if conn:
            await conn.close()
            logger.info("PostgreSQL 연결 종료")
        if tunnel:
            tunnel.stop()
            logger.info("PostgreSQL SSH 터널 종료")


async def main_with_options(mode: str = "incremental", batch_size: int = 5):
    """
    메인 실행 함수 - 전체 또는 증분 처리 선택

    Args:
        mode: "full" (전체 처리) 또는 "incremental" (증분 처리)
        batch_size: 배치 크기
    """
    try:
        if mode == "full":
            logger.info("🔄 전체 데이터 처리 모드")
            await process_group_buy_embeddings(batch_size)
        elif mode == "incremental":
            logger.info("⚡ 증분 데이터 처리 모드")
            await process_new_group_buy_embeddings(batch_size)
        else:
            logger.error(
                f"잘못된 모드: {mode}. 'full' 또는 'incremental'을 사용하세요."
            )
            return

    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")


# 실행 코드
if __name__ == "__main__":
    # 명령행 인자 처리
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "status":
            # 현재 상태 확인
            show_current_state()
            sys.exit(0)

        elif command == "reset":
            # 상태 초기화
            reset_state()
            sys.exit(0)

        elif command == "full":
            # 전체 처리 모드
            mode = "full"

        elif command == "incremental":
            # 증분 처리 모드
            mode = "incremental"

        else:
            print("사용법:")
            print("  python script.py              # 증분 처리 (기본)")
            print("  python script.py incremental  # 증분 처리")
            print("  python script.py full         # 전체 처리")
            print("  python script.py status       # 현재 상태 확인")
            print("  python script.py reset        # 상태 초기화")
            sys.exit(1)
    else:
        # 기본값: 증분 처리
        mode = "incremental"

    print("=" * 60)
    if mode == "full":
        print("🚀 MySQL → 임베딩 → PostgreSQL 파이프라인 시작 (전체 처리)")
    else:
        print("🚀 MySQL → 임베딩 → PostgreSQL 파이프라인 시작 (증분 처리)")
    print("=" * 60)

    # 현재 상태 표시
    show_current_state()

    # 실행
    try:
        asyncio.run(main_with_options(mode=mode, batch_size=5))
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")

    print("=" * 60)
    print("✅ 파이프라인 완료")
    print("=" * 60)

    # 처리 후 상태 표시
    if mode == "incremental":
        show_current_state()
