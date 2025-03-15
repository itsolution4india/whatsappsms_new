try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv('TOKEN')
PHONEID = os.getenv('PHONEID')
APPID = os.getenv('APPID')
WABAID = os.getenv('WABAID')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY ='django-insecure-ux$&02l*ri@g!fp$@@8g7kxd4#ix6$_=xo!r+bzmz3@f2&=i@6'
DEBUG = False # Set to False in production

ALLOWED_HOSTS = [
    'www.main.wtsmessage.xyz',
    'www.wtsdealnow.com',
    '.wtsdealnow.com',
    '.wtsmessage.xyz',  # Allow subdomains
    'localhost',
    '127.0.0.1',
    '217.145.69.172',
    '[::1]'
]
# CORS Configuration
'''
CORS_ALLOWED_ORIGINS = [
    "http://13.239.113.104",
    "https://13.239.113.104",
    
]

CSRF_TRUSTED_ORIGINS = ["http://13.239.113.104", 'https://13.239.113.104']
'''
SECURE_HSTS_SECONDS=15780000
SECURE_SSL_REDIRECT=False
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_SECURE=False

SESSION_COOKIE_AGE = 1800
# SESSION_SAVE_EVERY_REQUEST = True

INSTALLED_APPS = [
    'smsapp',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'smsapp.middleware.Log404DetailsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'smsapp.middleware.AutoLogoutMiddleware',
]

ROOT_URLCONF = 'sms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'smsapp.context_processors.global_context',
            ],
        },
    },
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

WSGI_APPLICATION = 'sms.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'adminmain',
        'USER': 'postgres',
        'PASSWORD': 'Solution@97',
        'HOST': '217.145.69.172',
        'PORT': '5432',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'login_attempts_cache',
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'smsapp.CustomUser'

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True


STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]


MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/error.log'),
        },
        '404_file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/404.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['file', '404_file'],  # Both handlers here
            'level': 'WARNING',  # Handles WARNING and above (including ERROR)
            'propagate': False,
        },
        'django.security.DisallowedHost': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

ADMIN_URL = 'skdasfjnkailf/'

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'