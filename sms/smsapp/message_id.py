import random
import string

def generate_pattern(template_name,all_contact, contact_list):
    characters = string.ascii_uppercase + string.ascii_lowercase + string.digits
    data_to_write = []

    for contact in all_contact:
        if contact not in contact_list:
            pattern = "wamid." + ''.join(random.choices(characters, k=50))
            data = f"whatsapp,{template_name},91{contact},{pattern}==,Sent"
            data_to_write.append(data)

   
    with open(f'/home/fedqrbtb/wtsdealnow.com/whatsappsms/sms/media/template/{template_name}.txt', 'a') as file: 
        for line in data_to_write:
            file.write(line + '\n')

    return 