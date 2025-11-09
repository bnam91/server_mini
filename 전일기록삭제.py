import sys
import os
import time
import datetime
from googleapiclient.discovery import build

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
    print(f"[오류] auth경로.txt 파일을 찾을 수 없습니다.")
    sys.exit(1)
except Exception as e:
    print(f"[오류] auth경로.txt 파일을 읽는 중 오류 발생: {e}")
    sys.exit(1)

from auth import get_credentials

# 구글 시트 URL
url = "https://docs.google.com/spreadsheets/d/1mkaF-DPisWkEaIZYjwdQJGfDykmXIERI3gu_H5pNrSQ/edit?gid=1933253521#gid=1933253521"

# 스프레드시트 ID 추출
spreadsheet_id = url.split('/d/')[1].split('/')[0]

# 로그 파일 경로 설정
log_file_path = os.path.join(os.path.dirname(__file__), "server_log.txt")

def log_message(message):
    """로그 파일에 메시지 기록"""
    try:
        with open(log_file_path, "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        pass  # 로그 기록 실패해도 계속 진행

def safe_print(*args, **kwargs):
    """인코딩 에러가 발생해도 계속 진행하는 안전한 print 함수"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # 이모지 등 인코딩 문제가 있을 경우 이모지 제거 후 출력
        try:
            safe_args = []
            for arg in args:
                if isinstance(arg, str):
                    # 이모지 제거 (유니코드 범위 체크)
                    safe_str = ''.join(char for char in arg if ord(char) < 0x10000)
                    safe_args.append(safe_str)
                else:
                    safe_args.append(arg)
            print(*safe_args, **kwargs)
        except Exception:
            pass  # 출력 실패해도 계속 진행

# 실행 시작 로그
log_message("전일기록삭제.py 실행 시작")

# 인증 정보 가져오기
safe_print("인증 정보를 가져오는 중...")
log_message("인증 정보를 가져오는 중...")
try:
    creds = get_credentials()
    log_message("인증 정보 가져오기 성공")
except Exception as e:
    log_message(f"인증 정보 가져오기 실패: {e}")
    safe_print(f"[오류] 인증 정보를 가져오는 중 오류 발생: {e}")
    sys.exit(1)

# Google Sheets API 서비스 생성
service = build('sheets', 'v4', credentials=creds)
log_message("Google Sheets API 서비스 생성 완료")

# 모든 시트 목록 가져오기
try:
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = spreadsheet.get('sheets', [])
    
    # '매뉴얼'과 '로그' 시트를 제외한 모든 시트 이름 가져오기
    sheet_names = []
    excluded_sheets = ['매뉴얼', '로그']
    for sheet in sheets:
        sheet_name = sheet['properties']['title']
        if sheet_name not in excluded_sheets:
            sheet_names.append(sheet_name)
    
    if not sheet_names:
        log_message("처리할 시트가 없습니다.")
        safe_print("처리할 시트가 없습니다.")
        sys.exit(0)
    
    log_message(f"처리할 시트 목록: {', '.join(sheet_names)}")
    log_message(f"총 {len(sheet_names)}개 시트의 H열 삭제 작업 시작")
    safe_print(f"\n[처리할 시트 목록] {', '.join(sheet_names)}")
    safe_print(f"[총 {len(sheet_names)}개 시트의 H열 삭제 작업]")
    safe_print("=" * 50)
    safe_print("첫 행(헤더)은 유지하고, 2행부터 마지막 행까지 H열 값을 삭제합니다.")
    safe_print("\n[5초 후 삭제를 시작합니다...]")
    log_message("5초 대기 시작")
    
    # 5초 카운트다운
    for remaining in range(5, 0, -1):
        sys.stdout.write(f"\r   {remaining}초 남음...   ")
        sys.stdout.flush()
        time.sleep(1)
    
    safe_print("\r" + " " * 20)  # 이전 출력 지우기
    safe_print("\n[삭제 중...]\n")
    log_message("삭제 작업 시작")
    
    # 각 시트에 대해 H열 삭제 작업 수행
    success_count = 0
    skip_count = 0
    
    for sheet_name in sheet_names:
        try:
            # H열 전체 데이터 확인
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!H:H"  # H열 전체
            ).execute()
            
            values = result.get('values', [])
            
            if not values or len(values) <= 1:
                log_message(f"'{sheet_name}': 삭제할 데이터 없음 (헤더만 있거나 데이터가 없음)")
                safe_print(f"  [건너뜀] '{sheet_name}': 삭제할 데이터 없음 (헤더만 있거나 데이터가 없음)")
                skip_count += 1
            else:
                # 총 행 수 확인
                total_rows = len(values)
                log_message(f"'{sheet_name}': H열 {total_rows}행 확인, 삭제 시작")
                
                # 2행부터 마지막 행까지 H열 값 지우기
                clear_range = f"{sheet_name}!H2:H{total_rows}"
                
                service.spreadsheets().values().clear(
                    spreadsheetId=spreadsheet_id,
                    range=clear_range
                ).execute()
                
                log_message(f"'{sheet_name}': H열 2행부터 {total_rows}행까지 삭제 완료")
                safe_print(f"  [완료] '{sheet_name}': H열 2행부터 {total_rows}행까지 삭제 완료")
                success_count += 1
                
        except Exception as e:
            log_message(f"'{sheet_name}': 오류 발생 - {e}")
            safe_print(f"  [오류] '{sheet_name}': 오류 발생 - {e}")
    
    safe_print("\n" + "=" * 50)
    safe_print(f"[완료] {success_count}개 시트 삭제 완료, {skip_count}개 시트 건너뜀")
    safe_print("=" * 50)
    log_message(f"작업 완료: {success_count}개 시트 삭제 완료, {skip_count}개 시트 건너뜀")
    
except Exception as e:
    error_msg = f"오류 발생: {e}"
    log_message(error_msg)
    safe_print(f"[오류] {error_msg}")
    sys.exit(1)

