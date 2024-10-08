import requests
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

def generate_id(phone_number_id, media_type, uploaded_file, access_token):
    #access_token = 'EAAE3ZCQ8LZB48BO9KDbpZCjbM6ZADGoAZANvtahzlAaoRqF24zgwUYsGZCSVpi1IkOhgaGnfCzmh5axAWDrXyomeqmhYUSgofSlIXojlBBCkwguOsFUgeCIaXuUZAsBhMiSTBFwyqZCkFTwGV1n700ef4fe1iZAGqVuBr2x9ZAh8AUz3FxxXIOWfDf6xinJAreZChYwFwZDZD'
    url = f'https://graph.facebook.com/v20.0/{phone_number_id}/media'
    # token1="EAAOPkGzfCvsBO5XzFGoAvCFlBdqw436heEJVmk7fsxH6WqXo8wMri5e8SImPpoJivRaITMh7ZAfBnVTmYTAOREpDHQG9jlPANZCrnd5ZBoIZBCZBnzfeqihDjXP2zWl1jwqFxmEsQwZAS7QNxw7bp6YVQj9E1H3KIyVPQhDT1MUyHO42Ifmj7DSOaNtBrYaBJVQeELHhz2UeA4JiDs0hXLSUMt0Lqlvs2a2yRS4ili"

    # token2="EAAGnWBuof2oBO8EUKs94mmrIeQjrneD9A4lAhZCLQXxZB8HyitAxbyGucbYLm8VoSoxeAsyTsBKioFDSktX3tBe8ytWaWHlS7up2m1BDjy5Y0pZAv4JyPMD4Ujfs7hJZAKE5CIzseNHQyImZAzpNol6AUCuYZAfAUzj1ik4TRXj9OuYfwKVOHPznVb5yZCBOpiP2UWZCYIrIGcUan0TKA9axCc1lrkPl9itO7Van2c7j"
    
    # token3="EAAX4JBLg3MgBOZCXmE6QQncXD0ZBeq4FhpZBkODTfVcBxNdMUDkrT0ZC2jzde323MQAkZBB2ikgkZBbJkZBuWajKmDObk5buKyDeOelq76tf6pCDL7EsfsOp5Vaw2T4cBxOsExvqmKtm8P5h6KmC1sd8iY5sY1J1Ojgsjuv8gAZAETsYThuVhvCQHCCJ7SzuH2bzJ50Uv0wVc0AyCLPExmYGFpVXK60zrjtym7znWWIb"
    
    # token4="EAANdvtzSZB7kBO1tXZBLe8YTsggcBSZAYz3SP12GbKflg7J6PlIbdpdg8JqnpqiYGkkqrJGwyDx0INRKMI9peCLXIooDUJJVdWsEL6scrsyjE77XQZB8V76bDlP2wuPLeQIzoGmy2p6nxtKJxS97psI9aSW1WJY99TZCc3r8Grl3dlgIYb6MZACXPgHraulBZCdmQZDZD"
    # access_token=token1
    # if phone_number_id =="281807641692911" or  phone_number_id == "357081907495865" or phone_number_id == "420031284522217":
    #     access_token=token1
    # elif phone_number_id =="351449328061702" or phone_number_id =="406145919249334"  or phone_number_id =="349045738303256"  or  phone_number_id =="332713753270030":
    #     access_token=token3
    # elif  phone_number_id =="346085425263787" or phone_number_id =="370651892806325" or  phone_number_id =="426676487192267" :
    #     access_token=token2
    # elif phone_number_id == '244226048784189':
    #     access_token=token4
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    data = {
        'type': media_type,
        'messaging_product': 'whatsapp'
    }
    try:
        
        file_content = uploaded_file.read()


        files = {
            'file': ('filename.ext', file_content, media_type)
        }

        
        response = requests.post(url, headers=headers, data=data, files=files)

        # Print status code and response JSON
        #print(f'Status Code: {response.status_code}')
        #print(f'Response: {response.json()}')

        return response.json()

    except Exception as e:
        print(f'Error: {e}')
        return {'error': str(e)}  