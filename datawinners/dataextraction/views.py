from django.contrib.auth.models import User
from django.http import HttpResponse
from dataextraction.helper import  encapsulate_data_for_subject, encapsulate_data_for_form, convert_to_json_file_download_response, generate_filename
from main.utils import get_database_manager

def get_for_subject(request, subject_type, subject_short_code, start_date=None, end_date=None):
    if request.method == 'GET':
        user = request.user
        dbm = get_database_manager(user)
        subject_type = subject_type.lower()
        data_for_subject = encapsulate_data_for_subject(dbm, subject_type, subject_short_code, start_date, end_date)
        return convert_to_json_file_download_response(data_for_subject, generate_filename('%s_%s' %(subject_type,subject_short_code), start_date, end_date))
    return HttpResponse("Error. Only support GET method.")

def get_for_form(request, form_code, start_date=None, end_date=None):
    if request.method == 'GET':
        user = request.user
        dbm = get_database_manager(user)
        data_for_form = encapsulate_data_for_form(dbm, form_code, start_date, end_date)
        return convert_to_json_file_download_response(data_for_form, generate_filename(form_code, start_date, end_date))
    return HttpResponse("Error. Only support GET method.")