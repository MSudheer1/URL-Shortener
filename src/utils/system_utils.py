import uuid

def get_system_id():
    mac = uuid.getnode()
    return f"{mac:012X}"
