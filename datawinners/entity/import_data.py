# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
from collections import OrderedDict
from copy import copy
from datawinners.exceptions import InvalidEmailException
from mangrove.data_cleaner import TelephoneNumber
from mangrove.datastore.documents import  FormModelDocument
from mangrove.datastore.entity_type import get_all_entity_types
import os
from django.conf import settings
from datawinners.location.LocationTree import get_location_tree
from datawinners.main.utils import  include_of_type, exclude_of_type, timebox
from datawinners.entity.entity_exceptions import InvalidFileFormatException
from mangrove.datastore.entity import get_all_entities, Entity
from mangrove.errors.MangroveException import MangroveException, DataObjectAlreadyExists
from mangrove.errors.MangroveException import CSVParserInvalidHeaderFormatException, XlsParserInvalidHeaderFormatException
from mangrove.form_model.form_model import REPORTER, get_form_model_by_code, get_form_model_by_entity_type, \
    NAME_FIELD_CODE, SHORT_CODE, MOBILE_NUMBER_FIELD, FormModel
from mangrove.transport.player.parser import CsvParser, XlsParser, XlsDatasenderParser
from mangrove.transport import Channel, TransportInfo, Response
from mangrove.transport.player.player import Player
from mangrove.utils.types import   is_sequence
from mangrove.datastore import entity
from mangrove.transport.facade import RegistrationWorkFlow, GeneralWorkFlow, ActivityReportWorkFlow
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext

from datawinners.location.LocationTree import get_location_hierarchy
from datawinners.submission.location import LocationBridge
from mangrove.contrib.registration_validators import case_insensitive_lookup
from datawinners.accountmanagement.helper import get_all_registered_phone_numbers_on_trial_account
from mangrove.form_model.form_model import ENTITY_TYPE_FIELD_CODE, MOBILE_NUMBER_FIELD_CODE
from datawinners.utils import get_organization
from django.contrib.auth.models import User, Group
from datawinners.accountmanagement.models import NGOUserProfile
from datawinners.utils import send_reset_password_email
from django.core.validators import email_re

class FormCodeDoesNotMatchException(Exception):
    def __init__(self, message, form_code=None):
        self.message = message
        self.data = form_code

    def __str__(self):
        return self.message

class FilePlayer(Player):
    def __init__(self, dbm, parser, channel_name, location_tree=None):
        Player.__init__(self, dbm, location_tree)
        self.parser = parser
        self.channel_name = channel_name
        self.form_code = None

    @classmethod
    def build(cls, manager, extension, default_parser=None, form_code=None):
        channels = dict({".xls":Channel.XLS,".csv":Channel.CSV})
        try:
            channel = channels[extension]
        except KeyError:
            raise InvalidFileFormatException()
        if default_parser is not None:
            parser = default_parser()
        elif extension == '.csv':
            parser = CsvParser()
        elif extension == '.xls':
            parser = XlsParser()
        else:
            raise InvalidFileFormatException()
        player = FilePlayer( manager, parser, channel, location_tree=LocationBridge( get_location_tree( ),
                                                                                     get_loc_hierarchy=get_location_hierarchy ) )
        player.form_code = form_code
        return player

    def _process(self,form_code, values):
        form_model = get_form_model_by_code(self.dbm, form_code)
        values = GeneralWorkFlow().process(values)
        if form_model.is_registration_form():
            values = RegistrationWorkFlow(self.dbm, form_model, self.location_tree).process(values)
        if form_model.entity_defaults_to_reporter():
            reporter_entity = entity.get_by_short_code(self.dbm, values.get(form_model.entity_question.code.lower()), form_model.entity_type)
            values = ActivityReportWorkFlow(form_model, reporter_entity).process(values)
        return form_model, values

    def appendFailedResponse(self, responses, message, values = None):
        response = Response( reporters=[], submission_id=None )
        response.success = False
        response.errors = dict( error=ugettext( message ), row=values )
        responses.append( response )

    def import_data_sender(self, form_model, organization, registered_emails, registered_phone_numbers, submission,
                           values):
        phone_number = TelephoneNumber( ).clean( case_insensitive_lookup( values, MOBILE_NUMBER_FIELD_CODE ) )
        if phone_number in registered_phone_numbers:
            raise DataObjectAlreadyExists( _( "Data Sender" ), _( "Mobile Number" ), phone_number )
        email = case_insensitive_lookup( values, "email" )
        if email:
            if email in registered_emails:
                raise DataObjectAlreadyExists( _( "User" ), _( "email address" ), email )

            if not email_re.match( email ):
                raise InvalidEmailException( message="Invalid email address." )

            response = self.submit( form_model, values, submission, [] )
            user = User.objects.create_user( email, email, 'password' )
            group = Group.objects.filter( name="Data Senders" )[0]
            user.groups.add( group )
            user.first_name = case_insensitive_lookup( response.processed_data, NAME_FIELD_CODE )
            user.save( )
            profile = NGOUserProfile( user=user, org_id=organization.org_id, title="Mr",
                                      reporter_id=case_insensitive_lookup( response.processed_data,
                                                                           SHORT_CODE ) )
            profile.save( )
            send_reset_password_email( user, ugettext_lazy( "en" ) )
        else:
            response = self.submit( form_model, values, submission, [] )
        return response

    def import_submission(self, form_code, organization, registered_emails, registered_phone_numbers, responses, values):
        transport_info = TransportInfo( transport=self.channel_name, source=self.channel_name, destination="" )
        submission = self._create_submission( transport_info, form_code, copy( values ) )
        try:
            form_model, values = self._process( form_code, values )
            if case_insensitive_lookup( values, ENTITY_TYPE_FIELD_CODE ) == REPORTER:
                response = self.import_data_sender( form_model, organization, registered_emails,
                                                    registered_phone_numbers, submission, values )
            else:
                response = self.submit( form_model, values, submission, [] )
            if not response.success:
                response.errors = dict( error=response.errors, row=values )
            responses.append( response )
        except DataObjectAlreadyExists as e:
            self.appendFailedResponse( responses, "%s with %s = %s already exists." % (e.data[2], e.data[0], e.data[1]), values=values )
        except (InvalidEmailException, MangroveException) as e:
            self.appendFailedResponse( responses, e.message, values=values )

    def accept(self, file_contents):
        responses = []
        from datawinners.utils import get_organization_from_manager
        organization = get_organization_from_manager(self.dbm)
        registered_phone_numbers = get_all_registered_phone_numbers_on_trial_account() \
            if organization.in_trial_mode else get_datasenders_mobile(self.dbm)
        if type(self.parser) == XlsDatasenderParser:
            registered_emails = User.objects.values_list('email', flat=True)
        else:
            registered_emails = []
        submissions = self.parser.parse(file_contents)
        if len(submissions) > 0:
            (form_code, values) = submissions[0]
            if self.form_code is not None and form_code != self.form_code:
                form_model = get_form_model_by_code(self.dbm, self.form_code )
                raise FormCodeDoesNotMatchException(ugettext('The file you are uploading is not a list of [%s]. Please check and upload again.') % form_model.entity_type[0], form_code=form_code)
        for (form_code, values) in submissions:
            self.import_submission( form_code, organization, registered_emails, registered_phone_numbers, responses,
                                   values )
        return responses

#TODO This is a hack. To be fixed after release. Introduce handlers and get error objects from mangrove
def tabulate_failures(rows):
    tabulated_data = []
    for row in rows:
        row[1].errors['row_num'] = row[0] + 2

        if isinstance(row[1].errors['error'], dict):
            errors = ''
            for key,value in row[1].errors['error'].items():
                if 'is required' in value:
                    code = value.split(' ')[3]
                    errors = errors + "\n" + _('Answer for question %s is required')% (code, )
                elif 'xx.xxxx yy.yyyy' in value:
                    errors = errors + "\n" + _('Incorrect GPS format. The GPS coordinates must be in the following format: xx.xxxx,yy.yyyy. Example -18.8665,47.5315')
                elif 'longer' in value:
                    text = value.split(' ')[1]
                    errors = errors + "\n" + _("Answer %s for question %s is longer than allowed.") % (text, key)
                elif 'must be between' in value:
                    text = value.split(' ')[2]
                    low = value.split(' ')[6]
                    high = value.split(' ')[8]
                    errors = errors + "\n" + _("The answer %s must be between %s and %s") % (text, low, high)
                else:
                    errors = errors + "\n" +_(value)
        else:
            errors = _(row[1].errors['error'])

        row[1].errors['error'] = errors
        tabulated_data.append(row[1].errors)
    return tabulated_data


def _tabulate_data(entity, form_model, field_codes):
    data = {'id': entity.id, 'short_code': entity.short_code}

    dict = OrderedDict()
    tuples = [(field.code, field.name) for field in form_model.fields]
    for (code, name) in tuples :
        if name in entity.data:
            dict[code] = _get_field_value(name, entity)
        else:
            dict[code] = _get_field_default_value(name, entity)

    stringified_dict = form_model.stringify(dict)

    data['cols'] = [stringified_dict[field_code] for field_code in field_codes]
    return data

def _get_entity_type_from_row(row):
    type = row['doc']['aggregation_paths']['_type']
    return type

def load_subject_registration_data(manager,
                                   filter_entities=exclude_of_type,
                                   type=REPORTER, tabulate_function=_tabulate_data):
    if type==REPORTER :
        form_model = get_form_model_by_code(manager, 'reg')
    else:
        form_model = get_form_model_by_entity_type(manager, _entity_type_as_sequence(type))

    fields, labels, codes = get_entity_type_fields(manager, type)
    entities = get_all_entities(dbm=manager)
    data = []
    for entity in entities:
        if filter_entities(entity, type):
            data.append(tabulate_function(entity, form_model, codes))
    return data, fields, labels

@timebox
def _get_entity_types(manager):
    entity_types = get_all_entity_types(manager)
    entity_list = [entity_type[0] for entity_type in entity_types if entity_type[0] != 'reporter']
    return sorted(entity_list)

def get_field_infos(fields):
    return zip(*[(field['name'], field['label'], field['code']) for field in fields if field['name'] != 'entity_type'])

def get_entity_type_info(entity_type, manager = None):
    if entity_type == 'reporter':
        form_code = 'reg'
        form_model = manager.load_all_rows_in_view("questionnaire", key = form_code)[0]
    else:
        form_model = get_form_model_by_entity_type(manager, _entity_type_as_sequence(entity_type))

    names, labels, codes = get_field_infos(form_model.value['json_fields'])

    return dict(entity = entity_type,
                   code = form_model.value["form_code"],
                   names = names,
                   labels = labels,
                   codes = codes,
                   data = [])

def _from_row_to_subject(dbm, row):
    return Entity.new_from_doc(dbm=dbm, doc=Entity.__document_class__.wrap(row.get('value')))

def _get_subject_type_infos(subject_types, form_models_grouped_by_subject_type):
    subject_types_dict = {}
    default_form_model = form_models_grouped_by_subject_type.get('registration')

    for subject_type in subject_types:
        form_model = form_models_grouped_by_subject_type.get(subject_type, default_form_model)
        names, labels, codes = zip(*[(field.name, field.label, field.code) for field in form_model.fields])
        subject_types_dict[subject_type] = dict(entity = subject_type,
                                                code = form_model.form_code,
                                                names = names,
                                                labels = labels,
                                                codes = codes,
                                                data = [],)
    return subject_types_dict

@timebox
def get_subject_form_models(manager):
    form_models = {}
    form_model_values = manager.load_all_rows_in_view('questionnaire')
    for each in form_model_values:
        form_model = FormModel.new_from_doc(manager, FormModelDocument.wrap(each['value']))
        if form_model.is_registration_form() and not form_model.entity_defaults_to_reporter():
            form_models[form_model.entity_type[0]] = form_model
    return form_models

@timebox
def get_all_subjects(manager):
    rows = manager.view.all_subjects()
    return [_from_row_to_subject(manager, row) for row in rows]

def _get_all_subject_data(form_models, subject_types, subjects):
    subject_type_infos_dict = _get_subject_type_infos(subject_types, form_models)
    for subject in subjects:
        subject_type = subject.type_string
        if subject_type in subject_type_infos_dict.keys():
            form_model = form_models[subject_type]
            data = _tabulate_data(subject, form_model, subject_type_infos_dict[subject_type]['codes'])
            subject_type_infos_dict[subject_type]['data'].append(data)

    return [subject_type_infos_dict[subject_type] for subject_type in subject_types]

@timebox
def load_all_subjects(manager):
    subject_types = _get_entity_types(manager)
    form_models = get_subject_form_models(manager)
    subjects = get_all_subjects(manager)

    return _get_all_subject_data(form_models, subject_types, subjects)

def load_all_subjects_of_type(manager, filter_entities=include_of_type, type=REPORTER):
    return load_subject_registration_data(manager, filter_entities, type)

def _handle_uploaded_file(file_name, file, manager, default_parser=None, form_code=None):
    base_name, extension = os.path.splitext(file_name)
    player = FilePlayer.build(manager, extension, default_parser=default_parser, form_code=form_code)
    response = player.accept(file)
    return response

def _get_imported_entities(responses):
    short_codes = dict()
    datarecords_id = []
    form_code = []
    for response in responses:
        if response.success:
            short_codes.update({response.short_code: response.entity_type[0]})
            datarecords_id.append(response.datarecord_id)
            if response.form_code not in form_code:
                form_code.append(response.form_code)
    return {"short_codes":short_codes, "datarecords_id": datarecords_id , "form_code": form_code}


def _get_failed_responses(responses):
    return [i for i in enumerate(responses) if not i[1].success]

def import_data(request, manager, default_parser=None, form_code=None   ):
    response_message = ''
    error_message = None
    failure_imports = None
    imported_entities = {}
    try:
        #IE sends the file in request.FILES['qqfile'] whereas all other browsers in request.GET['qqfile']. The following flow handles that flow.
        file_name, file = _file_and_name(request) if 'qqfile' in request.GET else _file_and_name_for_ie(request)
        responses = _handle_uploaded_file(file_name=file_name, file=file, manager=manager, default_parser=default_parser, form_code=form_code)
        imported_entities = _get_imported_entities(responses)
        form_code = imported_entities.get("form_code")[0] if len(imported_entities.get("form_code")) == 1 else None
        if form_code is not None and \
           len(imported_entities.get("datarecords_id")) and settings.CRS_ORG_ID==get_organization(request).org_id:
            from django.core.management import call_command
            datarecords_id = imported_entities.get("datarecords_id")
            call_command('crs_datamigration', form_code, *datarecords_id)
        imported_entities = imported_entities.get("short_codes")
        successful_imports = len(imported_entities)
        total = len(responses)
        if total == 0:
            error_message = _("The imported file is empty.")
        failures = _get_failed_responses(responses)
        failure_imports = tabulate_failures(failures)
        response_message = ugettext_lazy('%s of %s records uploaded') % (successful_imports, total)
    except CSVParserInvalidHeaderFormatException or XlsParserInvalidHeaderFormatException as e:
        error_message = e.message
    except InvalidFileFormatException:
        error_message = _(u"We could not import your data ! You are using a document format we canʼt import. Please use the import template file!")
    except FormCodeDoesNotMatchException as e:
        error_message = e.message
    except Exception:
        error_message = _(u"Some unexpected error happened. Please check the excel file and import again.")
        if settings.DEBUG:
            raise
    return error_message, failure_imports, response_message, imported_entities

def _file_and_name_for_ie(request):
    file_name = request.FILES.get('qqfile').name
    file = request.FILES.get('qqfile').read()
    return file_name, file

def _file_and_name(request):
    file_name = request.GET.get('qqfile')
    file = request.raw_post_data
    return file_name, file


def _entity_type_as_sequence(entity_type):
    if not is_sequence(entity_type):
        entity_type = [entity_type.lower()]
    return entity_type


def get_entity_type_fields(manager, type=REPORTER):
    form_model = get_form_model_by_entity_type(manager, _entity_type_as_sequence(type))
    form_code = "reg"
    if form_model is not None:
        form_code = form_model.form_code
    form_model_rows = manager.load_all_rows_in_view("questionnaire", key=form_code)
    fields, labels, codes = get_field_infos(form_model_rows[0].value['json_fields'])
    return fields, labels, codes


def _get_field_value(key, entity):
    value = entity.value(key)
    if key == 'geo_code':
        if value is None:
            return entity.geometry.get('coordinates')
    elif key == 'location':
        if value is None:
            return entity.location_path

    return value

def _get_field_default_value(key, entity):
    if key == 'geo_code':
        return entity.geometry.get('coordinates')
    if key == 'location':
        return  entity.location_path
    if key == 'short_code':
        return entity.short_code
    return None

def get_datasenders_mobile(manager):
    all_data_senders, fields, labels = load_all_subjects_of_type(manager)
    index = fields.index(MOBILE_NUMBER_FIELD)
    return [ds["cols"][index] for ds in all_data_senders]