import requests

def fetch_templates(waba_id, token):
    
    url = f"https://graph.facebook.com/v20.0/{waba_id}/message_templates"
    # token1="EAAOPkGzfCvsBO5XzFGoAvCFlBdqw436heEJVmk7fsxH6WqXo8wMri5e8SImPpoJivRaITMh7ZAfBnVTmYTAOREpDHQG9jlPANZCrnd5ZBoIZBCZBnzfeqihDjXP2zWl1jwqFxmEsQwZAS7QNxw7bp6YVQj9E1H3KIyVPQhDT1MUyHO42Ifmj7DSOaNtBrYaBJVQeELHhz2UeA4JiDs0hXLSUMt0Lqlvs2a2yRS4ili"
    # token2="EAAGnWBuof2oBO8EUKs94mmrIeQjrneD9A4lAhZCLQXxZB8HyitAxbyGucbYLm8VoSoxeAsyTsBKioFDSktX3tBe8ytWaWHlS7up2m1BDjy5Y0pZAv4JyPMD4Ujfs7hJZAKE5CIzseNHQyImZAzpNol6AUCuYZAfAUzj1ik4TRXj9OuYfwKVOHPznVb5yZCBOpiP2UWZCYIrIGcUan0TKA9axCc1lrkPl9itO7Van2c7j"
    # token3="EAAX4JBLg3MgBOZCXmE6QQncXD0ZBeq4FhpZBkODTfVcBxNdMUDkrT0ZC2jzde323MQAkZBB2ikgkZBbJkZBuWajKmDObk5buKyDeOelq76tf6pCDL7EsfsOp5Vaw2T4cBxOsExvqmKtm8P5h6KmC1sd8iY5sY1J1Ojgsjuv8gAZAETsYThuVhvCQHCCJ7SzuH2bzJ50Uv0wVc0AyCLPExmYGFpVXK60zrjtym7znWWIb"
    # token4="EAANdvtzSZB7kBO1tXZBLe8YTsggcBSZAYz3SP12GbKflg7J6PlIbdpdg8JqnpqiYGkkqrJGwyDx0INRKMI9peCLXIooDUJJVdWsEL6scrsyjE77XQZB8V76bDlP2wuPLeQIzoGmy2p6nxtKJxS97psI9aSW1WJY99TZCc3r8Grl3dlgIYb6MZACXPgHraulBZCdmQZDZD"
    # token=None
    # if waba_id =="332618029945458" or waba_id== "330090043524228" or waba_id =="383548151515080" or waba_id =="391799964022878": 
    #     token=token1
    # elif waba_id == "409990208861505" or waba_id == "397930006742161" or waba_id=="406024185930467":
    #     token=token3
    # elif waba_id == '277561478782644':
    #     token=token4
    # elif waba_id == "389460670923677" or waba_id == "401368339722342":
    #     token=token2
    
    
    params = {
        'access_token': token
    }
    
    try:

        response = requests.get(url, params=params)
        response.raise_for_status() 
        

        data = response.json()
        
        

        templates = []
        for entry in data.get("data", []):
            template_id = entry.get("id", "N/A")
            template_language = entry.get("language", "N/A")
            media_type=entry.get("format", "N/A")
            template_name = entry.get("name", "N/A")
            status = entry.get("status", "N/A")
            category = entry.get("category", "N/A")
            body_component = next((comp for comp in entry.get("components", []) if comp.get("type") == "BODY"), None)
            header_component = next((comp for comp in entry.get("components", []) if comp.get("type") == "HEADER"), None)
            button_component = next((comp for comp in entry.get("components", []) if comp.get("type") == "BUTTONS"), None)
             
            media_link = None
            if header_component and 'example' in header_component:
                media_link = header_component['example'].get('header_handle', [None])[0]
            
            templates.append({
                "template_id": template_id,
                "template_language":template_language,
                "template_name": template_name,
                "media_type":header_component.get("format", "N/A") if header_component else "N/A",
                "media_link":media_link,
                "status": status,
                "category": category,
                "template_data": body_component["text"] if body_component else 'No BODY component found',
                "button":button_component["buttons"] if button_component else None
            })
        
        return templates
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching templates: {e}")
        return None

'''
if __name__ == "__main__":
    waba_id = "330090043524228"
    fetched_templates = fetch_templates(waba_id)
    if fetched_templates:
        print("Fetched templates:")
        for template in fetched_templates:
            print(template)
    else:
        print("Failed to fetch templates.")
'''