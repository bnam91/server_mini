import sys
import os
import time
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
    print(f"❌ 오류: auth경로.txt 파일을 찾을 수 없습니다.")
    sys.exit(1)
except Exception as e:
    print(f"❌ 오류: auth경로.txt 파일을 읽는 중 오류 발생: {e}")
    sys.exit(1)

from auth import get_credentials

# 구글 시트 URL
url = "https://docs.google.com/spreadsheets/d/1mkaF-DPisWkEaIZYjwdQJGfDykmXIERI3gu_H5pNrSQ/edit?gid=1933253521#gid=1933253521"

# 스프레드시트 ID 추출
spreadsheet_id = url.split('/d/')[1].split('/')[0]

# 인증 정보 가져오기
print("인증 정보를 가져오는 중...")
creds = get_credentials()

# Google Sheets API 서비스 생성
service = build('sheets', 'v4', credentials=creds)

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
        print("처리할 시트가 없습니다.")
        sys.exit(0)
    
    print(f"\n📍 처리할 시트 목록: {', '.join(sheet_names)}")
    print(f"📍 총 {len(sheet_names)}개 시트의 H열 삭제 작업")
    print("=" * 50)
    print("첫 행(헤더)은 유지하고, 2행부터 마지막 행까지 H열 값을 삭제합니다.")
    print("\n⏰ 5초 후 삭제를 시작합니다...")
    
    # 5초 카운트다운
    for remaining in range(5, 0, -1):
        sys.stdout.write(f"\r   {remaining}초 남음...   ")
        sys.stdout.flush()
        time.sleep(1)
    
    print("\r" + " " * 20)  # 이전 출력 지우기
    print("\n🗑️  삭제 중...\n")
    
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
                print(f"  ⏭️  '{sheet_name}': 삭제할 데이터 없음 (헤더만 있거나 데이터가 없음)")
                skip_count += 1
            else:
                # 총 행 수 확인
                total_rows = len(values)
                
                # 2행부터 마지막 행까지 H열 값 지우기
                clear_range = f"{sheet_name}!H2:H{total_rows}"
                
                service.spreadsheets().values().clear(
                    spreadsheetId=spreadsheet_id,
                    range=clear_range
                ).execute()
                
                print(f"  ✅ '{sheet_name}': H열 2행부터 {total_rows}행까지 삭제 완료")
                success_count += 1
                
        except Exception as e:
            print(f"  ❌ '{sheet_name}': 오류 발생 - {e}")
    
    print("\n" + "=" * 50)
    print(f"✅ 완료: {success_count}개 시트 삭제 완료, {skip_count}개 시트 건너뜀")
    print("=" * 50)
    
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    sys.exit(1)

