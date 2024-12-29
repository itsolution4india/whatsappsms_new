from .models import UserAccess
from .utils import logger
from .models import Register_TwoAuth

def global_context(request):
    if request.user and str(request.user) != "AnonymousUser":
        user_access = UserAccess.objects.get(user=request.user)
        api_doc_access = getattr(user_access, "can_access_API_doc", False)
        valid_num = getattr(user_access, "can_manage_number_validation", False)
        twofauth_enable = getattr(user_access, "can_enable_2fauth", False)
        
        twofauth = Register_TwoAuth.objects.filter(user=request.user.username).exists()
    else:
        api_doc_access = None
        valid_num = None
        twofauth = False
        twofauth_enable = False
    return {
        'api_doc_access': api_doc_access,
        'valid_num': valid_num,
        'twofauth': twofauth,
        "twofauth_enable": twofauth_enable
    }
