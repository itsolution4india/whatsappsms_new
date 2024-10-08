import requests
import os

# Constants
API_VERSION = "v20.0"


#ACCESS_TOKEN = "EAAE3ZCQ8LZB48BO9KDbpZCjbM6ZADGoAZANvtahzlAaoRqF24zgwUYsGZCSVpi1IkOhgaGnfCzmh5axAWDrXyomeqmhYUSgofSlIXojlBBCkwguOsFUgeCIaXuUZAsBhMiSTBFwyqZCkFTwGV1n700ef4fe1iZAGqVuBr2x9ZAh8AUz3FxxXIOWfDf6xinJAreZChYwFwZDZD"
# def token_data(waba_id):
#     APP_ID1 = "1002275394751227"
#     APP_ID2 = "465471839698794"
#     APP_ID3 ="1680208702790856"
#     APP_ID4 = '947499260115897'
#     token1="EAAOPkGzfCvsBO5XzFGoAvCFlBdqw436heEJVmk7fsxH6WqXo8wMri5e8SImPpoJivRaITMh7ZAfBnVTmYTAOREpDHQG9jlPANZCrnd5ZBoIZBCZBnzfeqihDjXP2zWl1jwqFxmEsQwZAS7QNxw7bp6YVQj9E1H3KIyVPQhDT1MUyHO42Ifmj7DSOaNtBrYaBJVQeELHhz2UeA4JiDs0hXLSUMt0Lqlvs2a2yRS4ili"
#     token2="EAAGnWBuof2oBO8EUKs94mmrIeQjrneD9A4lAhZCLQXxZB8HyitAxbyGucbYLm8VoSoxeAsyTsBKioFDSktX3tBe8ytWaWHlS7up2m1BDjy5Y0pZAv4JyPMD4Ujfs7hJZAKE5CIzseNHQyImZAzpNol6AUCuYZAfAUzj1ik4TRXj9OuYfwKVOHPznVb5yZCBOpiP2UWZCYIrIGcUan0TKA9axCc1lrkPl9itO7Van2c7j"
#     token3="EAAX4JBLg3MgBOZCXmE6QQncXD0ZBeq4FhpZBkODTfVcBxNdMUDkrT0ZC2jzde323MQAkZBB2ikgkZBbJkZBuWajKmDObk5buKyDeOelq76tf6pCDL7EsfsOp5Vaw2T4cBxOsExvqmKtm8P5h6KmC1sd8iY5sY1J1Ojgsjuv8gAZAETsYThuVhvCQHCCJ7SzuH2bzJ50Uv0wVc0AyCLPExmYGFpVXK60zrjtym7znWWIb"
#     token4 ='EAANdvtzSZB7kBO1tXZBLe8YTsggcBSZAYz3SP12GbKflg7J6PlIbdpdg8JqnpqiYGkkqrJGwyDx0INRKMI9peCLXIooDUJJVdWsEL6scrsyjE77XQZB8V76bDlP2wuPLeQIzoGmy2p6nxtKJxS97psI9aSW1WJY99TZCc3r8Grl3dlgIYb6MZACXPgHraulBZCdmQZDZD'
#     ACCESS_TOKEN=None
#     APP_ID=None
    
#     if waba_id =="332618029945458" or waba_id== "330090043524228" or waba_id =="383548151515080" or waba_id =="391799964022878": 
#         ACCESS_TOKEN=token1
#         APP_ID=APP_ID1
#     elif waba_id=="409990208861505" or waba_id == "397930006742161" or waba_id =="406024185930467" :
#         ACCESS_TOKEN=token3
#         APP_ID=APP_ID3
#     elif waba_id == '277561478782644':
#         ACCESS_TOKEN=token4
#         APP_ID=APP_ID4
        
#     elif waba_id=="389460670923677" or waba_id == "401368339722342":
#         ACCESS_TOKEN=token2
#         APP_ID=APP_ID2
#     return ACCESS_TOKEN ,APP_ID


def header_handle(file_path, ACCESS_TOKEN, APP_ID):
    # ACCESS_TOKEN ,APP_ID=token_data(waba_id)
    file_length = file_path.size
    file_extension = file_path.name.split('.')[-1]
    file_type = get_media_format(file_extension)

    params = {
        'file_length': file_length,
        'file_type': file_type,
        'access_token': ACCESS_TOKEN
    }
    UPLOAD_SESSION_URL = f"https://graph.facebook.com/{API_VERSION}/{APP_ID}/uploads"

    response = requests.post(UPLOAD_SESSION_URL, params=params)
    response.raise_for_status()

    upload_session_id = response.json()['id']
    
    upload_url = f"https://graph.facebook.com/{API_VERSION}/{upload_session_id}"
    file_offset = 0

    headers = {
        'Authorization': f'OAuth {ACCESS_TOKEN}',
        'file_offset': str(file_offset)
    }
    file_data = handle_uploaded_file(file_path)

    with open(file_data, 'rb') as f:
        file_data1 = f.read()

    response = requests.post(upload_url, headers=headers, data=file_data1)
    print(response.json()['h'])
    return response.json()['h']

def get_media_format(file_extension):
    media_formats = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
        'gif': 'image/gif', 'bmp': 'image/bmp', 'svg': 'image/svg+xml',
        'mp4': 'video/mp4', 'avi': 'video/x-msvideo', 'mov': 'video/quicktime',
        'flv': 'video/x-flv', 'mkv': 'video/x-matroska', 'mp3': 'audio/mpeg',
        'aac': 'audio/aac', 'ogg': 'audio/ogg', 'wav': 'audio/wav',
        'pdf': 'application/pdf', 'doc': 'application/msword', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'ppt': 'application/vnd.ms-powerpoint', 'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'xls': 'application/vnd.ms-excel', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'txt': 'text/plain', 'csv': 'text/csv'
    }
    return media_formats.get(file_extension.lower(), 'application/octet-stream')
    
import tempfile

def handle_uploaded_file(file):
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        for chunk in file.chunks():
            tmp_file.write(chunk)
        return tmp_file.name    

''''
def main():
    upload_file('hello_file.png')

if __name__ == "__main__":
    main()
'''