import datetime
import json
import os

import requests
from bs4 import BeautifulSoup
from docx import Document
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- 설정 ---
# 공유된 구글 드라이브 폴더 ID
FOLDER_ID = "1Y0K1FaTb2STwT7Fp6nk-Zlc4AyZfFVRv"
# 서비스 계정 키 파일의 이름 또는 GitHub Secret에서 가져올 이름
# 로컬 테스트 시에는 다운로드한 json 파일의 실제 이름으로 바꾸세요 (예: 'my-key.json')
SERVICE_ACCOUNT_KEY_FILE = "SERVICE_ACCOUNT_KEY"
# --- 설정 끝 ---

SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_drive_service():
    """서비스 계정을 사용하여 Google Drive API 서비스 객체를 생성합니다."""
    try:
        # GitHub Actions 환경에서는 SERVICE_ACCOUNT_KEY가 파일 내용 전체를 담은 문자열입니다.
        if os.environ.get("GITHUB_ACTIONS") == "true":
            key_info = json.loads(os.environ[SERVICE_ACCOUNT_KEY_FILE])
            creds = service_account.Credentials.from_service_account_info(
                key_info, scopes=SCOPES
            )
        # 로컬 환경에서는 파일 경로를 사용합니다.
        else:
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_KEY_FILE, scopes=SCOPES
            )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"Drive 서비스 생성 실패: {e}")
        return None


# scrape_ubf_org, scrape_bs_ubf_kr, create_word_doc, get_or_create_folder_id, upload_to_drive 함수는
# 이전과 거의 동일하므로 생략합니다. main_job 함수만 확인하세요.
# (실제 코드에는 모든 함수가 포함되어야 합니다)
def scrape_ubf_org():
    url = "https://www.ubf.org/daily-breads"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title_tag = soup.find("h3")
        title = title_tag.get_text(strip=True) if title_tag else "No Title Found"
        content_paragraphs = []
        if title_tag:
            for sibling in title_tag.find_next_siblings():
                if sibling.name == "p":
                    content_paragraphs.append(sibling.get_text(strip=True))
                elif sibling.name and (
                    sibling.name.startswith("h") or sibling.name == "hr"
                ):
                    break
        content = "\n\n".join(content_paragraphs)
        if not content:
            content = "본문 내용을 자동으로 추출하지 못했습니다."
        return {"source": "UBF.org", "title": title, "content": content}
    except Exception as e:
        print(f"UBF.org 스크래핑 실패: {e}")
        return None


def scrape_bs_ubf_kr():
    url = "https://bs.ubf.kr/dailybread/dailybread.php"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        full_text = soup.get_text(separator="\n", strip=True)
        try:
            start_index = full_text.index("말씀 :")
            end_index = full_text.index("한마디")
            content = full_text[start_index:end_index]
        except ValueError:
            content = "본문 내용을 자동으로 추출하지 못했습니다."
        return {"source": "BS.UBF.KR", "title": "일용할 양식", "content": content}
    except Exception as e:
        print(f"BS.UBF.KR 스크래핑 실패: {e}")
        return None


def create_word_doc(data_list):
    doc = Document()
    doc.add_heading(f"Daily Bread - {datetime.date.today()}", 0)
    for data in data_list:
        if data:
            doc.add_heading(data["source"], level=1)
            doc.add_heading(data["title"], level=2)
            doc.add_paragraph(data["content"])
            doc.add_page_break()
    # 로컬/클라우드 환경 모두에서 쓰기 가능한 상대 경로 사용
    filename = f"DailyBread_{datetime.date.today()}.docx"
    doc.save(filename)
    print(f"문서 생성 완료: {filename}")
    return filename


def upload_to_drive(filename):
    service = get_drive_service()
    if not service:
        return

    # 폴더 ID를 직접 사용하므로 검색이나 생성이 필요 없습니다.
    folder_id = FOLDER_ID

    file_metadata = {"name": os.path.basename(filename), "parents": [folder_id]}
    media = MediaFileUpload(
        filename,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    try:
        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        print(f"업로드 완료. File ID: {file.get('id')}")
    except Exception as e:
        print(f"업로드 실패: {e}")


def main():
    """메인 실행 함수"""
    print(f"작업 시작: {datetime.datetime.now()}")
    data1 = scrape_ubf_org()
    data2 = scrape_bs_ubf_kr()

    if data1 or data2:
        filename = create_word_doc([data1, data2])
        upload_to_drive(filename)
        if os.path.exists(filename):
            os.remove(filename)
    else:
        print("스크래핑된 데이터가 없습니다.")
    print("작업 완료.")


if __name__ == "__main__":
    main()
