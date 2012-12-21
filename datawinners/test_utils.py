# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import unittest
from django.test.client import RequestFactory
from mock import Mock
from accountmanagement.models import Organization
from datawinners.tests.data import DEFAULT_TEST_ORG_ID, DEFAULT_TEST_ORG_NAME, RAW_DATA, HEADER_LIST, DEFAULT_TEST_ORG_TEL_NO
from entity.views import add_codes_sheet
import utils

class TestUtils(unittest.TestCase):

    def test_should_generate_excel_sheet(self):
        raw_data = RAW_DATA
        header_list = HEADER_LIST
        raw_data.insert(0,header_list)
        sheet_name = 'test'
        wb = utils.get_excel_sheet(raw_data, sheet_name)
        self.assertEquals(3, len(wb.get_sheet(0).rows))
        self.assertEquals(3, wb.get_sheet(0).row(0).get_cells_count())

    def test_should_write_date_value_to_excel_sheet(self):
         raw_data = RAW_DATA
         wb = utils.get_excel_sheet(raw_data, "test")
         self.assertEquals(3, len(wb.get_sheet(0).rows))
         self.assertEquals(3, wb.get_sheet(0).row(0).get_cells_count())

    def test_should_add_codes_sheet_to_excel(self):
        raw_data = RAW_DATA
        wb = utils.get_excel_sheet(raw_data, "test")
        add_codes_sheet(wb, "form_code", ('q1', 'q2', 'q3'))
        code_sheet = wb.get_sheet(1)
        self.assertEquals(1, len(code_sheet.rows))
        self.assertEquals(4, code_sheet.row(0).get_cells_count())

    def test_should_return_organization(self):
        org_id = DEFAULT_TEST_ORG_ID
        request = self._get_request_mock(org_id)

        organization = utils.get_organization(request)
        self.assertEquals(org_id,organization.org_id)

    def test_convert_to_ordinal(self):
        self.assertEquals('12th',utils.convert_to_ordinal(12))
        self.assertEquals('21st',utils.convert_to_ordinal(21))
        self.assertEquals('32nd',utils.convert_to_ordinal(32))
        self.assertEquals('43rd',utils.convert_to_ordinal(43))
        self.assertEquals('77th',utils.convert_to_ordinal(77))

    def test_generate_document_store(self):
        self.assertEquals(u'hni_testorg_slx364903', utils.generate_document_store_name(DEFAULT_TEST_ORG_NAME,DEFAULT_TEST_ORG_ID))

    def test_should_return_organization_setting(self):
        request = self._get_request_mock(DEFAULT_TEST_ORG_ID)
        org_setting = utils.get_organization_settings_from_request(request)
        self.assertEquals(DEFAULT_TEST_ORG_TEL_NO,org_setting.sms_tel_number)

    def test_should_return_database_manager(self):
        organization = Organization.objects.get(pk=DEFAULT_TEST_ORG_ID)
        dbm = utils.get_database_manager_for_org(organization)
        self.assertEquals(utils.generate_document_store_name(DEFAULT_TEST_ORG_NAME,DEFAULT_TEST_ORG_ID),dbm.database_name)
        
    def _get_request_mock(self,org_id):
        request = RequestFactory().get('/account/')
        request.user = Mock()
        mock_profile = Mock()
        mock_profile.org_id = Mock(return_value=org_id)
        request.user.get_profile = Mock(return_value=mock_profile)
        return request

    def test_should_return_ymd(self):
        result = utils.convert_dmy_to_ymd("06-07-2012")
        self.assertEquals(result, "2012-07-06")

    def test_project_name_generator(self):
        projects_name = [ "test project", "untitled project", "untitled project - 1"]
        generated = utils.generate_project_name(projects_name)
        self.assertEqual("Untitled Project - 2", unicode(generated))

    def test_should_find_changed_questions(self):
        old_questionnaire = [dict({'label': 'question1',  'name': 'quest1', 'type': 'text'}),
                             dict({'label': 'old question1',  'name': 'old1', 'type': 'int'}),
            ]

        self.old_questionnaire = [type('Field', (object, ), question) for question in old_questionnaire]
        
        new_questionnaire = [dict({'label': 'new question1',  'name': 'quest1', 'type': 'text'}),
                dict({'label': 'old question1',  'name': 'old1', 'type': 'int'}),
                dict({'label': 'new question',  'name': 'quest2', 'type': 'text'})
            ]
        self.new_questionnaire = [type('Field', (object, ), question) for question in new_questionnaire]
        changed_questionnaire = utils.get_changed_questions(self.old_questionnaire, self.new_questionnaire, subject=False)
        self.assertEqual(changed_questionnaire["added"], ['new question'])
        self.assertEqual(changed_questionnaire["changed"], ['new question1'])