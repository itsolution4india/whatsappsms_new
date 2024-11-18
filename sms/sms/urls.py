from django.urls import path
from django.contrib import admin
from smsapp import views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    
    path("admin/", admin.site.urls),
    path("", views.user_login, name="login"),
    path("logout/",views.logout_view,name="logout"),
    path("send-sms/", views.Send_Sms, name="send-sms"),
    path('reports/', views.Reports, name='reports'),
    #path('download_report/<int:report_id>/',views.download_campaign_report, name='report_download'),
    path('download_report/<int:report_id>/', views.download_campaign_report, name='report_download'),
    path('report_insight/<int:report_id>/', views.get_report_insight, name='report_insight'),
    path('campaign/', views.Campaign, name='campaign'),
    # path('campaign/delete/<str:template_id>/', views.delete_campaign, name='delete_campaign'),
    path('media_upload/', views.upload_media, name='upload_media'),
    path('dashboard/', views.user_dashboard, name='dashboard'),
    path('schedules/', views.schedules, name='schedules'),
    path('schedules/delete/<int:schedule_id>/', views.delete_schedule, name='delete_schedule'),
    path("reset-password/", views.initiate_password_reset, name="initiate_password_reset"),
    path("otp-verification/<str:email>/<str:token>/",views.verify_otp,name="otp_verification"),
    path("change-password/<str:email>/<str:token>/",views.change_password, name="change_password"),
    path('facebook-sdk/',views.facebook_sdk_view, name='facebook_sdk'),
    path('user_responses/', views.save_phone_number, name='user_responses'),
    path('create_flow_message/', views.create_flow_message, name='create_flow_message'),
    path('send_flow_message/', views.send_flow_message, name='send_flow_message'),
    path('delete_template/', views.delete_template, name='delete_template'),
    path('link_templates/', views.link_templates, name='link_templates'),
    path('template-linkage/delete/<int:id>/', views.delete_template_linkage, name='delete_template_linkage'),
    path('template-linkage/download/<str:button_name>/<str:start_date>/<str:end_date>/', views.download_linked_report, name='download_linked_report'),
    path('bot-flow/', views.bot_flow, name='bot'),
    path('flows/publish/<str:flow_id>/', views.publish_flow, name='publish_flow'),
    path('flows/deprecate/<str:flow_id>/', views.deprecate_flow, name='deprecate_flow'),
    path('flows/delete/<str:flow_id>/', views.delete_flow, name='delete_flow'),
    path('coins-history/', views.coins_history_list, name='coins_history_list'),
    path('get-preview-url/<int:flow_id>/', views.get_preview_url_view, name='get_preview_url'),
    path('create_template_from_flow/', views.create_template_from_flow, name='create_template_from_flow'),
    path('access_denide/', views.access_denide, name='access_denide'), 
    
    
    path('api/users/', views.customuser_list_view, name='customuser-list'),
    path('api/users/<str:email>/', views.customuser_detail_view, name='customuser-detail'),
    path('update-balance-report/', views.UpdateBalanceReportView.as_view(), name='update_balance_report'),
    path('get-report/', views.GetReportAPI.as_view(), name='get_report_api'),
    path('api_manual/', views.api_manual, name="api_manual")
 
]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
