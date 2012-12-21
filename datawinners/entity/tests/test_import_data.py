# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
from collections import OrderedDict
from mangrove.form_model.field import TextField
from mangrove.utils.test_utils.mangrove_test_case import MangroveTestCase
from datawinners.entity.import_data import load_all_subjects, get_field_infos
from datawinners.entity.import_data import FilePlayer
from datawinners.location.LocationTree import get_location_tree
from mangrove.bootstrap import initializer
from mangrove.datastore.datadict import DataDictType
from mangrove.datastore.entity import create_entity
from mangrove.datastore.entity_type import define_type
from mangrove.form_model.form_model import MOBILE_NUMBER_FIELD, NAME_FIELD
from mangrove.transport.player.player import SMSPlayer
from mangrove.transport.player.parser import CsvParser, XlsDatasenderParser
from mangrove.transport.facade import Channel
from mangrove.transport import TransportInfo, Request
from mangrove.transport.submissions import Submission
from mangrove.form_model.form_model import FormModel
from datawinners.location.LocationTree import get_location_hierarchy
from datawinners.entity.helper import create_registration_form
from datawinners.submission.location import LocationBridge
from datawinners.accountmanagement.models import Organization
from mock import Mock, patch
from django.contrib.auth.models import UserManager

class TestImportData(MangroveTestCase):
    def setUp(self):
        MangroveTestCase.setUp(self)
        self._create_entities()
        self.player = SMSPlayer(self.manager, location_tree=LocationBridge(get_location_tree(), get_loc_hierarchy=get_location_hierarchy))
        self.transport = TransportInfo(transport="sms", source="1234", destination="5678")
        initializer.run(self.manager)

    def tearDown(self):
        MangroveTestCase.tearDown(self)

    def test_should_load_all_subjects(self):
        self._register_entities()

        subjects = load_all_subjects(self.manager)

        self.assertEqual(2, len(subjects))
        self.assertEqual(subjects[0]["entity"], "clinic")
        self.assertEqual(subjects[1]["entity"], "waterpoint")
        self.assertEqual(subjects[0]["code"], "cli")
        self.assertEqual(subjects[1]["code"], "wat")
        self.assertEqual(6, len(subjects[0]["names"]))
        self.assertEqual(6, len(subjects[0]["labels"]))

        self.assertEqual(subjects[0]['data'][0]['cols'][0], 'Bhopal')
        self.assertEqual(subjects[0]['data'][0]['cols'][2], 'India')
        self.assertEqual(subjects[0]['data'][0]['cols'][5], 'clb')

        self.assertEqual(subjects[0]['data'][1]['cols'][0], 'Satna')
        self.assertEqual(subjects[0]['data'][1]['cols'][3], '-10.66, 13.1')
        self.assertEqual(subjects[0]['data'][1]['cols'][5], 'cli2')

        self.assertEqual(subjects[1]['data'][0]['cols'][0], 'Ambovombe')
        self.assertEqual(subjects[1]['data'][0]['cols'][3], '-18.16, 14.1')
        self.assertEqual(subjects[1]['data'][0]['cols'][4], '123444')
        self.assertEqual(subjects[1]['data'][0]['cols'][5], 'wat1')

    def _create_entities(self):
        self.entity_type = ['clinic']
        define_type(self.manager, self.entity_type)
        create_registration_form(self.manager, self.entity_type)
        self.entity_type = ['waterpoint']
        define_type(self.manager, self.entity_type)
        create_registration_form(self.manager, self.entity_type)
        define_type(self.manager, ['reporter'])
        self.name_type = DataDictType(self.manager, name='Name', slug='name', primitive_type='string')
        self.telephone_number_type = DataDictType(self.manager, name='telephone_number', slug='telephone_number',
                                                  primitive_type='string')
        rep1 = create_entity(self.manager, ['reporter'], 'rep1')
        rep1.add_data(data=[(MOBILE_NUMBER_FIELD, '1234', self.telephone_number_type),
            (NAME_FIELD, "Test_reporter", self.name_type)], submission=dict(submission_id="2"))


    def _register_entity(self, text):
        self.player.accept(Request(text, self.transport))

    def _register_entities(self):
        self._register_entity('cli Bhopal Clinic India -12.35,49.3 123444 clb')
        self._register_entity('cli Satna Clinic India -10.66,13.1 567223')
        self._register_entity('cli Pune Clinic Yerawada -18.16,14.1 643321')
        self._register_entity('wat Ambovombe Test Androy -18.16,14.1 123444')
        self._register_entity('wat Morondava Test Menabe -15.91,12.67 138866')

def dummy_get_location_hierarchy(foo):
    return [u'arantany']

class DummyLocationTree(object):
    def get_location_hierarchy_for_geocode(self, lat, long ):
        return ['madagascar']

    def get_centroid(self, location_name, level):
        return 60, -12

class TestFilePlayer(MangroveTestCase):

    def setUp(self):
        MangroveTestCase.setUp(self)
        initializer.run(self.manager)

        self.entity_type = ["reporter"]
        self.telephone_number_type = DataDictType(self.manager, name='telephone_number', slug='telephone_number',
                                                  primitive_type='string')
        self.entity_id_type = DataDictType(self.manager, name='Entity Id Type', slug='entity_id', primitive_type='string')
        self.name_type = DataDictType(self.manager, name='Name', slug='name', primitive_type='string')
        self.telephone_number_type.save()
        self.name_type.save()
        self.reporter = create_entity(self.manager, entity_type=self.entity_type,
                                      location=["India", "Pune"], aggregation_paths=None, short_code="rep1",
                                      )
        self.reporter.add_data(data=[(MOBILE_NUMBER_FIELD, '1234', self.telephone_number_type),
            (NAME_FIELD, "Test_reporter", self.name_type)], submission=dict(submission_id="1"))

        question1 = TextField(name="entity_question", code="EID", label="What is associated entity",
                              entity_question_flag=True, ddtype=self.entity_id_type)
        question2 = TextField(name="Name", code="NAME", label="Clinic Name",
                              defaultValue="some default value",
                              ddtype=self.name_type, required=False)
        self.form_model = FormModel(self.manager, entity_type=self.entity_type, name="Dengue", label="Dengue form_model",
                                    form_code="clinic", type='survey', fields=[question1,question2])
        self.form_model.save()

        self.csv_data_for_activity_report = """
                                FORM_CODE,EID,NAME
                                clinic,rep1,XYZ
        """
        self.csv_data_about_reporter = """
                                FORM_CODE,t,n,l,d,m
                                REG,"reporter",Dr. A,Pune,"Description",201
        """
        self.csv_data_with_same_mobile_number = """
                                FORM_CODE,t,n,l,d,m
                                REG,"reporter",Dr. A,Pune,"Description",201
                                REG,"reporter",Dr. B,Pune,"Description",201
        """
        self.csv_data_with_exception = """
                                FORM_CODE,t,n,l,d,m
                                REG,"reporter",Dr. A,Pune,"Description",201
                                REG,"reporter",Dr. B,Pune,"Description",201
                                REG,"reporter",Dr. C,Pune,"Description",202
        """
        self.csv_data_with_missing_name = """
                                FORM_CODE,t,n,l,d,m
                                REG,"reporter",,Pune,"Description",201
        """
        self.csv_data_with_missing_type = """
                                FORM_CODE,t,n,l,d,m
                                REG,,Dr. A,Pune,"Description",201
        """
        self.csv_data_with_incorrect_mobile_number = """
                                FORM_CODE,t,n,l,d,m
                                REG,"reporter",Dr. A,Pune,"Description",2014678447676512
                                REG,"reporter",Dr. A,Pune,"Description",~!@#$%^&*()+|}
                                REG,"reporter",Dr. A,Pune,"Description",
        """
        self.csv_data_with_incorrect_GPS = """
                                FORM_CODE,t,n,g,d,m
                                REG,"reporter",Dr. A,18,"Description",201
        """
        self.csv_data_with_out_of_range_GPS_value = """
                                FORM_CODE,t,n,g,d,m
                                REG,"reporter",Dr. A,-95 48,"Description",201
                                REG,"reporter",Dr. A,-18 184,"Description",201
        """
        self.csv_data_without_form_code= """
                                FORM_CODE,t,n,g,d,m
                                ,"reporter",Dr. A,-95 48,"Description",201
                                ABC,"reporter",Dr. A,-95 48,"Description",201
        """
        self.parser = CsvParser()
        self.file_player = FilePlayer(self.manager,self.parser, Channel.CSV, LocationBridge(DummyLocationTree(),dummy_get_location_hierarchy))

    def tearDown(self):
        MangroveTestCase.tearDown(self)

    def test_should_import_csv_string_if_it_contains_data_about_reporters(self):
        organization = Mock(spec=Organization)
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            responses = self.file_player.accept(self.csv_data_about_reporter)
        self.assertTrue(responses[0].success)
        submission_log = Submission.get(self.manager, responses[0].submission_id)
        self.assertEquals(True, submission_log. status)
        self.assertEquals("csv", submission_log.channel)
        self.assertEquals("reg", submission_log.form_code)
        self.assertDictContainsSubset({'t':'reporter', 'n':'Dr. A','l':'Pune','d':'Description','m':'201'}, submission_log.values)

    def test_should_import_csv_string_if_it_contains_data_for_activity_reporters(self):
        organization = Mock(spec=Organization)
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            responses = self.file_player.accept(self.csv_data_for_activity_report)
        self.assertTrue(responses[0].success)
        submission_log = Submission.get(self.manager, responses[0].submission_id)
        self.assertEquals("csv", submission_log.channel)
        self.assertEquals(u'rep1', responses[0].short_code)

    def test_should_not_import_data_if_multiple_reporter_have_same_mobile_number(self):
        organization = Mock(spec=Organization)
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            responses = self.file_player.accept(self.csv_data_with_same_mobile_number)
        self.assertTrue(responses[0].success)
        self.assertFalse(responses[1].success)
        self.assertEqual(u'Sorry, the telephone number 201 has already been registered',responses[1].errors['error']['m'])

    def test_should_import_next_value_if_exception_with_previous(self):
        organization = Mock(spec=Organization)
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            responses = self.file_player.accept(self.csv_data_with_exception)
        self.assertTrue(responses[0].success)
        self.assertFalse(responses[1].success)
        self.assertTrue(responses[2].success)
        submission_log = Submission.get(self.manager, responses[0].submission_id)
        self.assertDictContainsSubset({'t':'reporter', 'n':'Dr. A','l':'Pune','d':'Description','m':'201'}, submission_log.values)
        self.assertEquals({'error':{'m': u'Sorry, the telephone number 201 has already been registered'}, 'row':{'t':u'reporter', 'n':u'Dr. B','l':[u'arantany'],'d':u'Description','m':u'201','s':u'rep3'}}, responses[1].errors)
        submission_log = Submission.get(self.manager, responses[2].submission_id)
        self.assertDictContainsSubset({'t':'reporter', 'n':'Dr. C','l':'Pune','d':'Description','m':'202'}, submission_log.values)

    def test_should_not_import_data_for_missing_field(self):
        organization = Mock(spec=Organization)
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            responses = self.file_player.accept(self.csv_data_with_missing_name)
            self.assertFalse(responses[0].success)
            self.assertEqual(OrderedDict([('n', 'Answer for question n is required')]),responses[0].errors['error'])

            responses = self.file_player.accept(self.csv_data_with_missing_type)
            self.assertFalse(responses[0].success)
            self.assertEqual(OrderedDict([('t', 'Answer for question t is required')]),responses[0].errors['error'])

    def test_should_not_import_data_for_invalid_mobile_number(self):
        organization = Mock(spec=Organization)
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            responses = self.file_player.accept(self.csv_data_with_incorrect_mobile_number)
        self.assertFalse(responses[0].success)
        self.assertFalse(responses[1].success)
        self.assertFalse(responses[2].success)
        self.assertEqual(OrderedDict([('m', 'Answer 2014678447676512 for question m is longer than allowed.')]),responses[0].errors['error'])
        self.assertEqual(OrderedDict([('m', 'Invalid Mobile Number. Only Numbers and Dash(-) allowed.')]),responses[1].errors['error'])
        self.assertEqual(OrderedDict([('m', 'Mobile number is missing')]),responses[2].errors['error'])

    def test_should_not_import_data_for_incorrect_GPS_format(self):
        organization = Mock(spec=Organization)
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            responses = self.file_player.accept(self.csv_data_with_incorrect_GPS)
        self.assertFalse(responses[0].success)
        error_message = OrderedDict([('g',
            'Incorrect GPS format. The GPS coordinates must be in the following format: xx.xxxx yy.yyyy. Example -18.8665 47.5315')])
        self.assertEqual(error_message,responses[0].errors['error'])

    def test_should_not_import_data_for_out_of_range_GPS_code(self):
        organization = Mock(spec=Organization)
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            responses = self.file_player.accept(self.csv_data_with_out_of_range_GPS_value)
        self.assertFalse(responses[0].success)
        self.assertFalse(responses[1].success)
        error_message1 = OrderedDict([('g',
            'The answer -95 must be between -90 and 90')])
        self.assertEqual(error_message1,responses[0].errors['error'])
        error_message2 = OrderedDict([('g',
            'The answer 184 must be between -180 and 180')])
        self.assertEqual(error_message2,responses[1].errors['error'])

    def test_should_not_import_data_for_invalid_form_code(self):
        organization = Mock(spec=Organization)
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            responses = self.file_player.accept(self.csv_data_without_form_code)
        self.assertFalse(responses[0].success)
        self.assertEqual('The questionnaire does not exist.',responses[0].errors['error'])
        self.assertFalse(responses[1].success)
        self.assertEqual(u'The questionnaire with code abc does not exist.',responses[1].errors['error'])

    def test_should_not_import_ds_if_phone_number_already_registered(self):
        organization = Mock(spec=Organization)
        csv_data = """
                                FORM_CODE,t,n,l,d,m
                                REG,"reporter",used number,Tana,"...",1234567890
        """
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            responses = self.file_player.accept(csv_data)
                
        self.assertFalse(responses[0].success)
        self.assertEqual(responses[0].errors['error'],"Data Sender with Mobile Number = 1234567890 already exists.")

    def test_should_not_import_datasender_when_email_is_not_unique_or_mobile_is_not_unique(self):
        organization = Mock(spec=Organization)
        with patch("datawinners.utils.get_organization_from_manager") as get_organization_from_dbm_mock:
            get_organization_from_dbm_mock.return_value = Mock(return_value=organization)
            with patch.object(XlsDatasenderParser, "parse") as parse_mock:
                parse_mock.return_value = [
                    ("reg", {u"email": u'', u'g': u'-18.13,27.65', u'l': u'Nairobi',u'm': u'1234567890', u'n': u'Thierry Rakoto', u't': 'reporter'}),
                    ("reg", {u"email": u'test@mail.com', u'g': u'-18.13,27.65', u'l': u'Nairobi',u'm': u'033333333', u'n': u'Thierry Rakoto', u't': 'reporter'}),
                    ("reg", {u"email": u'a.com', u'g': u'-18.13,27.65', u'l': u'Nairobi',u'm': u'033333333', u'n': u'Thierry Rakoto', u't': 'reporter'})
                ]
                with patch.object(UserManager, "values_list") as get_ds_mobile:
                    get_ds_mobile.return_value = ["test@mail.com"]
                    file_player = FilePlayer(self.manager,XlsDatasenderParser(), Channel.XLS, LocationBridge(DummyLocationTree(),dummy_get_location_hierarchy))
                    responses = file_player.accept(None)
        self.assertFalse(responses[0].success)
        self.assertEqual(responses[0].errors['error'],"Data Sender with Mobile Number = 1234567890 already exists.")
        self.assertFalse(responses[1].success)
        self.assertEqual(responses[1].errors['error'],"User with email address = test@mail.com already exists.")
        self.assertFalse(responses[2].success)
        self.assertEqual(responses[2].errors['error'],"Invalid email address.")

    def test_should_get_field_infos_of_registration_questionnaire(self):
        registration_form_model = self.manager.load_all_rows_in_view("questionnaire", key="reg")[0].get('value')
        fields, labels, codes = get_field_infos(registration_form_model.get('json_fields'))

        self.assertEqual(('name', 'short_code', 'location', 'geo_code', 'mobile_number'), fields)
        self.assertEqual(("What is the subject's name?", "What is the subject's Unique ID Number", "What is the subject's location?","What is the subject's GPS co-ordinates?", 'What is the mobile number associated with the subject?'), labels)
        self.assertEqual(('n', 's', 'l', 'g', 'm'), codes)