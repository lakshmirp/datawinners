# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import unittest
from mock import Mock, patch
from datawinners.submission.models import SMSResponse
from mangrove.form_model.form_model import NAME_FIELD, FormModel
from mangrove.transport.facade import  create_response_from_form_submission
from datawinners.messageprovider.tests.test_message_handler import THANKS

class TestSMSResponse(unittest.TestCase):
    def setUp(self):
        self.form_submission_mock = Mock()
        self.form_submission_mock.cleaned_data = {'name': 'Clinic X'}
        self.form_submission_mock.saved.return_value = True
        self.form_submission_mock.short_code = "CLI001"

    def test_should_return_expected_success_response(self):
        self.form_submission_mock.is_registration = False
        response = create_response_from_form_submission(reporters=[{NAME_FIELD: "Mr. X"}], submission_id=123,
            form_submission=self.form_submission_mock)
        dbm_mock = Mock()
        form_model_mock = Mock(spec=FormModel)
        form_model_mock.stringify.return_value = {'name': 'Clinic X'}
        with patch("datawinners.messageprovider.message_handler.get_form_model_by_code") as get_form_model_mock:
            get_form_model_mock.return_value = form_model_mock
            response_text = SMSResponse(response).text(dbm_mock)
        self.assertEqual(THANKS + u" name: Clinic X", response_text)

    def test_should_return_expected_success_response_for_registration(self):
        self.form_submission_mock.is_registration = True

        response = create_response_from_form_submission(reporters=[{NAME_FIELD: "Mr. X"}], submission_id=123,form_submission=self.form_submission_mock)
        dbm_mock = Mock()
        form_model_mock = Mock(spec=FormModel)
        form_model_mock.stringify.return_value = {'name': 'Clinic X'}
        with patch("datawinners.messageprovider.message_handler.get_form_model_by_code") as get_form_model_mock:
            get_form_model_mock.return_value = form_model_mock
            response_text = SMSResponse(response).text(dbm_mock)
        self.assertEqual(u'Registration successful. ID is: CLI001. name: Clinic X',response_text)

    def test_should_return_expected_error_response(self):
        self.form_submission_mock.saved = False
        error_response = "horrible hack. feeling bad about it. But need to change mangrove error handling and error response"
        self.form_submission_mock.errors = error_response

        response = create_response_from_form_submission(reporters=[], submission_id=123,form_submission=self.form_submission_mock)
        self.assertEqual(error_response,SMSResponse(response).text(Mock(spec=FormModel)))
