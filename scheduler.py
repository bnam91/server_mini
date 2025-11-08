import sys
import os
import time
import datetime
import subprocess
from googleapiclient.discovery import build

# 기본 설정
CHECK_INTERVAL = 300  # 30분 (초 단위) - 5분 단위로 체크하려면 300으로 변경

# ID 설정 (ID.txt에서 읽기)
id_file_path = os.path.join(os.path.dirname(__file__), "ID.txt")
try:
    with open(id_file_path, "r", encoding="utf-8") as f:
        ID = f.readline().strip()  # 첫 줄만 읽기
    if not ID:
        print(f"❌ 오류: ID.txt 파일이 비어있습니다.")
        sys.exit(1)
except FileNotFoundError:
    print(f"❌ 오류: ID.txt 파일을 찾을 수 없습니다.")
    sys.exit(1)
except Exception as e:
    print(f"❌ 오류: ID.txt 파일을 읽는 중 오류 발생: {e}")
    sys.exit(1)

# auth.py 경로 추가 (auth경로.txt에서 읽기)
auth_path_file = os.path.join(os.path.dirname(__file__), "auth경로.txt")
try:
    with open(auth_path_file, "r", encoding="utf-8") as f:
        auth_path = f.read().strip().strip('"').strip("'")
    # 파일 경로인 경우 디렉토리 경로로 변환
    if os.path.isfile(auth_path):
        auth_path = os.path.dirname(auth_path)
    sys.path.insert(0, auth_path)
except FileNotFoundError:
    print(f"❌ 오류: auth경로.txt 파일을 찾을 수 없습니다.")
    sys.exit(1)
except Exception as e:
    print(f"❌ 오류: auth경로.txt 파일을 읽는 중 오류 발생: {e}")
    sys.exit(1)

from auth import get_credentials

def extract_spreadsheet_info(url):
    """구글 시트 URL에서 스프레드시트 ID와 시트 ID(gid) 추출"""
    # 스프레드시트 ID 추출
    spreadsheet_id = url.split('/d/')[1].split('/')[0]
    
    # 시트 ID(gid) 추출
    gid = None
    if 'gid=' in url:
        gid = url.split('gid=')[1].split('&')[0].split('#')[0]
    
    return spreadsheet_id, gid

def get_sheet_name_by_gid(service, spreadsheet_id, gid):
    """시트 ID(gid)로 시트 이름 찾기"""
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        
        for sheet in sheets:
            if str(sheet['properties']['sheetId']) == str(gid):
                return sheet['properties']['title']
        
        # gid를 찾지 못하면 첫 번째 시트 반환
        if sheets:
            return sheets[0]['properties']['title']
        return None
    except Exception as e:
        print(f"시트 정보를 가져오는 중 오류 발생: {e}")
        return None

def get_sheet_by_id(service, spreadsheet_id, target_id):
    """스프레드시트에서 ID와 일치하는 시트 찾기"""
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        
        for sheet in sheets:
            sheet_name = sheet['properties']['title']
            if sheet_name == target_id:
                return sheet_name
        
        return None
    except Exception as e:
        print(f"시트 정보를 가져오는 중 오류 발생: {e}")
        return None

def get_sheet_data(service, spreadsheet_id, sheet_name):
    """시트의 모든 데이터 가져오기"""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:H"  # A열부터 H열까지 (로그 포함)
        ).execute()
        
        return result.get('values', [])
    except Exception as e:
        print(f"시트 데이터를 읽는 중 오류 발생: {e}")
        return []

def write_log_to_column_h(service, spreadsheet_id, sheet_name, row_index, log_message):
    """시트의 특정 행의 H열에 로그 기록"""
    try:
        # H열에 값 쓰기 (행 인덱스는 1부터 시작하므로 그대로 사용)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!H{row_index}",
            valueInputOption='USER_ENTERED',
            body={
                'values': [[log_message]]
            }
        ).execute()
        return True
    except Exception as e:
        print(f"\033[90m[DEBUG] H열 로그 기록 실패 (행 {row_index}): {e}\033[0m")
        return False

def normalize_time(time_str):
    """시간 문자열을 HH:MM 형식으로 정규화"""
    if not time_str:
        return ""
    
    time_str = time_str.strip()
    
    # 빈 문자열 처리
    if not time_str:
        return ""
    
    # 다양한 시간 형식 처리 (예: "9:5", "09:05", "9:05", "09:5", "09:05:00" 등)
    try:
        # 시간과 분 분리
        parts = time_str.split(':')
        if len(parts) < 2:
            return ""
        
        hour = int(parts[0])
        minute = int(parts[1])
        
        # 범위 검증
        if hour < 0 or hour >= 24 or minute < 0 or minute >= 60:
            return ""
        
        # HH:MM 형식으로 반환
        return f"{hour:02d}:{minute:02d}"
    except (ValueError, IndexError):
        return ""

def get_next_check_time(interval_minutes=5):
    """다음 체크 시간(5분 단위 정시)을 계산하고 반환"""
    now = datetime.datetime.now()
    
    # 현재 분을 interval_minutes 단위로 반올림
    current_minute = now.minute
    next_minute = ((current_minute // interval_minutes) + 1) * interval_minutes
    
    # 다음 체크 시간 생성
    if next_minute >= 60:
        # 다음 시간으로 넘어가는 경우
        next_check = now.replace(hour=(now.hour + 1) % 24, minute=0, second=0, microsecond=0)
        if next_check.hour == 0 and now.hour == 23:
            # 자정을 넘어가는 경우
            next_check = next_check + datetime.timedelta(days=1)
    else:
        next_check = now.replace(minute=next_minute, second=0, microsecond=0)
    
    return next_check

def get_seconds_until_next_check(interval_minutes=5):
    """다음 체크 시간(5분 단위 정시)까지 남은 초를 계산"""
    next_check = get_next_check_time(interval_minutes)
    now = datetime.datetime.now()
    
    # 남은 초 계산
    delta = next_check - now
    seconds_until_next = delta.total_seconds()
    
    return max(1, int(seconds_until_next))  # 최소 1초

def get_next_scheduled_command(rows, next_check_time):
    """다음 체크 시간에 실행될 명령어 찾기"""
    next_time_str = next_check_time.strftime("%H:%M")
    scheduled_jobs = []  # (작업이름, 시간, 명령어) 튜플 리스트
    
    for row in rows[1:]:  # 헤더 건너뛰기
        schedule_time_raw = row[0].strip() if len(row) > 0 else ""
        schedule_time = normalize_time(schedule_time_raw)
        job_name = row[1].strip() if len(row) > 1 else ""  # B열 - 작업이름
        command = row[4].strip() if len(row) > 4 else ""  # E열 - 명령어
        
        if schedule_time == next_time_str and command:
            # 디버깅: 매칭된 경우만 출력
            print(f"\033[90m[DEBUG] 매칭: 시트 시간 '{schedule_time_raw}' -> 정규화 '{schedule_time}' = 다음 체크 '{next_time_str}'\033[0m")
            scheduled_jobs.append((job_name, schedule_time, command))
    
    return scheduled_jobs

def get_earliest_future_command(rows, after_time):
    """지정된 시간 이후 가장 빠른 예약된 명령어 찾기"""
    after_time_str = after_time.strftime("%H:%M")
    earliest_datetime = None
    earliest_time_str = None
    earliest_jobs = []  # (작업이름, 시간, 명령어) 튜플 리스트
    
    # 현재 날짜 기준으로 비교
    today = datetime.datetime.now().date()
    after_datetime = datetime.datetime.combine(today, after_time.time())
    
    # 모든 예약된 명령어 탐색
    for row in rows[1:]:  # 헤더 건너뛰기
        schedule_time_raw = row[0].strip() if len(row) > 0 else ""
        schedule_time = normalize_time(schedule_time_raw)
        job_name = row[1].strip() if len(row) > 1 else ""  # B열 - 작업이름
        command = row[4].strip() if len(row) > 4 else ""  # E열 - 명령어
        
        if schedule_time and command:
            # 시간 파싱
            try:
                hour, minute = map(int, schedule_time.split(':'))
                schedule_datetime = datetime.datetime.combine(today, datetime.time(hour, minute))
                
                # schedule_datetime이 after_datetime보다 작거나 같으면 다음날로 처리
                # (미래의 예약만 찾기 때문)
                if schedule_datetime <= after_datetime:
                    schedule_datetime += datetime.timedelta(days=1)
                
                # 지정된 시간 이후인지 확인
                if schedule_datetime > after_datetime:
                    # 가장 빠른 시간 찾기
                    if earliest_datetime is None or schedule_datetime < earliest_datetime:
                        earliest_datetime = schedule_datetime
                        earliest_time_str = schedule_time
                        earliest_jobs = [(job_name, schedule_time, command)]
                    elif schedule_datetime == earliest_datetime:
                        # 같은 시간에 여러 명령어가 있는 경우
                        earliest_jobs.append((job_name, schedule_time, command))
            except (ValueError, TypeError):
                continue
    
    return earliest_time_str, earliest_jobs

def countdown_sleep(seconds, next_check_time, scheduled_commands, earliest_next_time=None, earliest_next_commands=None):
    """실시간 카운트다운과 함께 대기"""
    # 실행 예정 명령어 출력
    if scheduled_commands:
        print(f"\n☑️  다음 실행 예정 명령어 :")
        for job_idx, (job_name, schedule_time, command) in enumerate(scheduled_commands, 1):
            if job_idx > 1:
                print()  # 작업이 여러 개일 경우 구분
            print(f"\n   1. {job_name if job_name else '(작업이름 없음)'}")
            print(f"   2. {schedule_time}")
            print(f"   3. {command}")
    else:
        print(f"\n☑️  [{next_check_time.strftime('%H:%M')}]에 예약된 명령어가 없습니다.")
        # 가장 빠른 다음 예약 명령어 표시
        if earliest_next_time and earliest_next_commands:
            print(f"\n☑️  가장 빠른 다음 예약:")
            for job_idx, (job_name, schedule_time, command) in enumerate(earliest_next_commands, 1):
                if job_idx > 1:
                    print()  # 작업이 여러 개일 경우 구분
                print(f"\n   1. {job_name if job_name else '(작업이름 없음)'}")
                print(f"   2. {schedule_time}")
                print(f"   3. {command}")
    
    print()  # 빈 줄 추가
    print("-" * 50)  # 구분선 추가
    
    # 카운트다운
    for remaining in range(seconds, 0, -1):
        minutes = remaining // 60
        secs = remaining % 60
        sys.stdout.write(f"\r👉 다음 체크까지: {minutes:02d}:{secs:02d} 남음...   ")
        sys.stdout.flush()
        time.sleep(1)
    
    # 줄바꿈으로 깨끗하게 정리
    print("\r" + " " * 60)  # 이전 출력 지우기
    current_time_str = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"🔄 [{current_time_str}] 시트 확인 중...\n")

def run_scheduler():
    """스케줄러 실행 루프"""
    # server_log.txt를 스크립트와 같은 폴더에 저장
    log_file_path = os.path.join(os.path.dirname(__file__), "server_log.txt")
    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now()}] 스케줄러 실행됨 ✅\n")
    
    # 구글 시트 URL
    url = "https://docs.google.com/spreadsheets/d/1mkaF-DPisWkEaIZYjwdQJGfDykmXIERI3gu_H5pNrSQ/edit?gid=1225124787#gid=1225124787"
    
    # 인증 정보 가져오기
    print("인증 정보를 가져오는 중...")
    creds = get_credentials()
    
    # Google Sheets API 서비스 생성
    service = build('sheets', 'v4', credentials=creds)
    
    # 스프레드시트 ID 추출
    spreadsheet_id, _ = extract_spreadsheet_info(url)
    
    # ID와 일치하는 시트 찾기
    sheet_name = get_sheet_by_id(service, spreadsheet_id, ID)
    
    if not sheet_name:
        print(f"❌ ID '{ID}'와 일치하는 시트를 찾을 수 없습니다.")
        return
    
    print(f"\n📍 시트 '{sheet_name}'을 찾았습니다.")
    print(f"📍 체크주기: 매 5분 단위 (정시)\n")
    print("-" * 50)
    
    # 실행된 명령 추적 (중복 실행 방지)
    executed_commands = set()
    
    while True:
        try:
            now = datetime.datetime.now().strftime("%H:%M")
            current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 시트 데이터 가져오기
            rows = get_sheet_data(service, spreadsheet_id, sheet_name)
            
            if not rows:
                print(f"[{current_datetime}] 시트 데이터를 읽을 수 없습니다.")
                next_check_time = get_next_check_time(interval_minutes=5)
                seconds_to_wait = get_seconds_until_next_check(interval_minutes=5)
                countdown_sleep(seconds_to_wait, next_check_time, [], None, None)
                continue
            
            # 첫 행은 헤더이므로 건너뛰기
            for row_idx, row in enumerate(rows[1:], start=2):
                # A열(시간)과 E열(명령어) 확인
                schedule_time_raw = row[0].strip() if len(row) > 0 else ""
                schedule_time = normalize_time(schedule_time_raw)
                command = row[4].strip() if len(row) > 4 else ""
                
                # 시간과 명령어가 모두 있는 경우에만 처리
                if schedule_time and command:
                    # 시간 형식 검증 (HH:MM 형식) - 실행 시점의 현재 시간으로 다시 확인
                    current_time = datetime.datetime.now().strftime("%H:%M")
                    if schedule_time == current_time:
                        # 중복 실행 방지: 같은 시간과 명령어 조합은 한 번만 실행
                        command_key = f"{schedule_time}:{command}"
                        
                        if command_key not in executed_commands:
                            # 실행 시점의 정확한 시간 가져오기
                            exec_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            print(f"[{exec_datetime}] ⏰ 시간 매칭: {schedule_time}")
                            print(f"[{exec_datetime}] 📝 명령 실행: {command}")
                            
                            try:
                                # 명령어 실행 (백그라운드에서 실행하여 팝업 알림이 있어도 블로킹되지 않도록)
                                # Windows에서는 CREATE_NEW_CONSOLE 플래그 사용
                                if sys.platform == 'win32':
                                    process = subprocess.Popen(
                                        command,
                                        shell=True,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL,
                                        stdin=subprocess.DEVNULL,
                                        creationflags=subprocess.CREATE_NEW_CONSOLE
                                    )
                                else:
                                    # Linux/Mac에서는 nohup과 유사한 방식
                                    process = subprocess.Popen(
                                        command,
                                        shell=True,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL,
                                        stdin=subprocess.DEVNULL,
                                        start_new_session=True
                                    )
                                
                                exec_datetime_end = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                print(f"[{exec_datetime_end}] ✅ 명령 실행 시작 (PID: {process.pid})")
                                
                                # 프로세스가 정상적으로 시작되었는지 확인 (짧은 대기 후 상태 체크)
                                time.sleep(0.5)
                                log_message = ""
                                if process.poll() is None:
                                    # 프로세스가 여전히 실행 중이면 정상적으로 시작된 것으로 간주
                                    print(f"[{exec_datetime_end}] ✅ 프로세스 정상 실행 중 (백그라운드)")
                                    log_message = f"{exec_datetime_end} | 실행 성공 (PID: {process.pid})"
                                else:
                                    # 프로세스가 즉시 종료되었다면 에러 발생 가능성
                                    return_code = process.returncode
                                    print(f"[{exec_datetime_end}] ⚠️ 프로세스 즉시 종료됨 (종료 코드: {return_code})")
                                    log_message = f"{exec_datetime_end} | 실행 실패 (종료 코드: {return_code})"
                                
                                # H열에 로그 기록
                                write_log_to_column_h(service, spreadsheet_id, sheet_name, row_idx, log_message)
                                
                            except Exception as e:
                                exec_datetime_end = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                print(f"[{exec_datetime_end}] ⚠️ 실행 오류: {e}")
                                # 에러 발생 시에도 H열에 로그 기록
                                error_log = f"{exec_datetime_end} | 실행 오류: {str(e)}"
                                write_log_to_column_h(service, spreadsheet_id, sheet_name, row_idx, error_log)
                            
                            # 실행된 명령 기록
                            executed_commands.add(command_key)
                            
                            # 하루가 지나면 실행 기록 초기화 (메모리 절약)
                            if len(executed_commands) > 1000:
                                executed_commands.clear()
            
            # 다음 5분 단위 정시까지 대기
            next_check_time = get_next_check_time(interval_minutes=5)
            seconds_to_wait = get_seconds_until_next_check(interval_minutes=5)
            
            # 디버깅: 다음 체크 시간 출력
            print(f"\033[90m[DEBUG] 현재 시간: {datetime.datetime.now().strftime('%H:%M:%S')}\033[0m")
            print(f"\033[90m[DEBUG] 다음 체크 시간: {next_check_time.strftime('%H:%M:%S')} ({next_check_time.strftime('%H:%M')})\033[0m")
            
            # 다음에 실행될 명령어 찾기
            scheduled_commands = get_next_scheduled_command(rows, next_check_time)
            
            # 다음 체크 시간에 예약이 없으면 가장 빠른 다음 예약 찾기
            earliest_next_time = None
            earliest_next_commands = None
            if not scheduled_commands:
                earliest_next_time, earliest_next_commands = get_earliest_future_command(rows, next_check_time)
            
            # 카운트다운 시작
            countdown_sleep(seconds_to_wait, next_check_time, scheduled_commands, earliest_next_time, earliest_next_commands)
            
        except KeyboardInterrupt:
            print("\n\n스케줄러를 종료합니다.")
            break
        except Exception as e:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ 오류 발생: {e}")
            print("다시 시도합니다...")
            next_check_time = get_next_check_time(interval_minutes=5)
            seconds_to_wait = get_seconds_until_next_check(interval_minutes=5)
            countdown_sleep(seconds_to_wait, next_check_time, [], None, None)

if __name__ == "__main__":
    print("=" * 50)
    print(f"⏱️  {ID} 스케줄러 시작")
    print("=" * 50)
    run_scheduler()
