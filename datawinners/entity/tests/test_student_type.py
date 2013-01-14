from datawinners.entity.import_data import load_all_subjects, load_all_subjects_of_type
from datawinners.entity.views import create_student_type, register_student_subject, create_data_sender_for_student_type
from mangrove.bootstrap import initializer
from mangrove.utils.test_utils.mangrove_test_case import MangroveTestCase

class TestStudentType(MangroveTestCase):
    ClassIsSetup = False
    ClassIsTornDown = False

    def setUp(self):
        if not self.ClassIsSetup:
            MangroveTestCase.setUp(self)
            initializer.run(self.manager)
            self.ClassIsSetup = True

    def test_should_create_student_type(self):
        create_student_type(self.manager)
        subjects = load_all_subjects(self.manager)
        self.assertEquals('stu', subjects[0]['code'])

    def test_should_register_a_student_subject(self):
        register_student_subject(self.manager, ['DGPetrolBunk', 'bangalore', 'karnataka'], short_code="RP007",
            geometry={"type": "Point", "coordinates": [17.2833, 77.35]},
            lastname="RP", firstname="Lakshmi", description="This RP's petrol bunk!!.", mobile_number="9900099000")
        subjects = load_all_subjects(self.manager)
        short_code = subjects[0]['data'][0]['short_code']
        self.assertEquals('RP007', short_code)

    def test_should_create_a_data_sender(self):
        name = "Ashwin"
        phone_number = "9900081410"
        location = [u'koramangala', u'jayanagar', u'banashankari']
        coordinates = [17.543211, 65.45632]
        short_code = "stu1"
        create_data_sender_for_student_type(self.manager,phone_number,name,location,short_code,coordinates)
        subjects = load_all_subjects_of_type(self.manager)
        short_code = subjects[0][0]['short_code']
        self.assertEquals('stu1', short_code)
        self.ClassIsTornDown = True

    def tearDown(self):
        if self.ClassIsTornDown:
            MangroveTestCase.tearDown(self)

