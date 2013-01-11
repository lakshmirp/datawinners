from datawinners.entity.import_data import load_all_subjects
from datawinners.entity.views import create_student_type
from mangrove.bootstrap import initializer
from mangrove.utils.test_utils.mangrove_test_case import MangroveTestCase

class TestStudentType(MangroveTestCase):
    def setUp(self):
        MangroveTestCase.setUp(self)
        initializer.run(self.manager)

    def tearDown(self):
        MangroveTestCase.tearDown(self)

    def test_should_create_student_type(self):
        create_student_type(self.manager)
        subjects = load_all_subjects(self.manager)
        self.assertEquals('stu', subjects[0]['code'])
