from .models import UserAccess, Register_TwoAuth
from .utils import logger

def global_context(request):
    context = {
        'api_doc_access': None,
        'valid_num': None,
        'twofauth': False,
        'twofauth_enable': False,
    }

    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            user_access = UserAccess.objects.get(user=request.user)
            context['api_doc_access'] = getattr(user_access, "can_access_API_doc", False)
            context['valid_num'] = getattr(user_access, "can_manage_number_validation", False)
            context['twofauth_enable'] = getattr(user_access, "can_enable_2fauth", False)
            context['twofauth'] = Register_TwoAuth.objects.filter(user=request.user.username).exists()
        except UserAccess.DoesNotExist:
            logger.error(f"UserAccess not found for user: {request.user.username}")

    return context