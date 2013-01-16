from datetime import datetime
from pytz import UTC
from datawinners.entity.import_data import load_all_subjects, load_all_subjects_of_type
from datawinners.entity.views import create_student_type, register_student_subject, create_data_sender_for_student_type
from main.utils import create_views
from mangrove.bootstrap import initializer
from mangrove.datastore.documents import DataRecordDocument
from mangrove.form_model.form_model import  get_form_model_by_code
from mangrove.transport import TransportInfo, Request
from mangrove.transport.player.player import WebPlayer, SMSPlayer
from mangrove.utils.test_utils.mangrove_test_case import MangroveTestCase
from messageprovider.messages import SMS
from project.views import create_student_project

class TestStudentType(MangroveTestCase):

    def setUp(self):
        MangroveTestCase.setUp(self)
        create_views(self.manager)
        initializer.run(self.manager)

    def test_should_create_student_type(self):
        create_student_type(self.manager)
        subjects = load_all_subjects(self.manager)
        self.assertEquals('stu', subjects[0]['code'])

    def test_should_register_a_student_subject(self):
        create_student_type(self.manager)
        register_student_subject(self.manager, ['DGPetrolBunk', 'bangalore', 'karnataka'], short_code="RP007",
            geometry={"type": "Point", "coordinates": [17.2833, 77.35]},
            lastname="RP", firstname="Lakshmi", description="This RP's petrol bunk!!.", mobile_number="9900099000")
        subjects = load_all_subjects(self.manager)
        short_code = subjects[0]['data'][0]['short_code']
        self.assertEquals('RP007', short_code)

    def _create_a_test_data_sender(self):
        name = "Ashwin"
        phone_number = "9900081410"
        location = [u'koramangala', u'jayanagar', u'banashankari']
        coordinates = [17.543211, 65.45632]
        short_code = "stu1"
        create_data_sender_for_student_type(self.manager, phone_number, name, location, short_code, coordinates)

    def test_should_create_a_data_sender(self):
        self._create_a_test_data_sender()
        subjects = load_all_subjects_of_type(self.manager)
        short_code = subjects[0][0]['short_code']
        self.assertEquals('stu1', short_code)

    def test_should_create_questionnaire(self):
        create_student_project(self.manager)
        student_form = get_form_model_by_code(self.manager,"stu001")
        self.assertEquals("EID",student_form.fields[0].code)
        self.assertEquals("STN",student_form.fields[1].code)
        self.assertEquals("RPP",student_form.fields[2].code)
        self.assertEquals("GND",student_form.fields[3].code)
        self.assertEquals("GPS",student_form.fields[4].code)
        self.ClassIsTornDown = True

    def _submit_answers_via_web(self, COORDINATES, GENDER, REPORTING_DATE, STUDENT_NAME):
        self.web_player = WebPlayer(self.manager)
        text = {'form_code': 'stu001', 'EID': 'stu', 'STN': STUDENT_NAME, 'RPP': REPORTING_DATE, 'GND': GENDER,
                'GPS': COORDINATES}
        transport_info = TransportInfo(transport="web", source="tester150411@gmail.com", destination="")
        response = self.web_player.accept(Request(message=text, transportInfo=transport_info))
        return response

    def _get_response_data(self, response):
        self.assertTrue(response.success)
        data_record_id = response.datarecord_id
        data_record = self.manager._load_document(id=data_record_id, document_class=DataRecordDocument)
        data = data_record.data
        return data

    def test_should_submit_answers_using_web(self):
        STUDENT_NAME = 'BHARGHAV'
        REPORTING_DATE = '10.2013'
        date_given = datetime(2013, 10, 1, 0, 0, tzinfo=UTC)
        GENDER = ['a']
        COORDINATES = '-18.1324,27.6547'
        create_student_project(self.manager)
        response = self._submit_answers_via_web(COORDINATES, GENDER, REPORTING_DATE, STUDENT_NAME)
        data = self._get_response_data(response)
        self.assertEquals(STUDENT_NAME,data['What is student\'s name?']['value'])
        self.assertEquals(date_given,data['What is reporting period?']['value'])
        self.assertEquals(['Male'],data['What is your Gender?']['value'])
        self.assertEquals([-18.1324,27.6547],data['What is the GPS code for your house']['value'])

    def test_should_submit_answers_using_sms(self):
        create_student_project(self.manager)
        self._create_a_test_data_sender()
        FROM_NUMBER = '9900081410'
        TO_NUMBER = '919880734937'
        self.sms_player = SMSPlayer(self.manager)
        transport = TransportInfo(SMS, FROM_NUMBER, TO_NUMBER)
        mangrove_request = Request("stu001 stu BHARGHAV 10.2013 a 17.5632,34.5687",
            transport)
        response = self.sms_player.accept(mangrove_request)
        self.assertTrue(response.success)
        data_record_id = response.datarecord_id
        data_record = self.manager._load_document(id=data_record_id, document_class=DataRecordDocument)
        data = data_record.data
        self.assertEquals('BHARGHAV', data['What is student\'s name?']['value'])
        date_given = datetime(2013, 10, 1, 0, 0, tzinfo=UTC)
        self.assertEquals(date_given, data['What is reporting period?']['value'])
        self.assertEquals(['Male'], data['What is your Gender?']['value'])
        self.assertEquals([17.5632,34.5687], data['What is the GPS code for your house']['value'])

    def tearDown(self):
        MangroveTestCase.tearDown(self)

