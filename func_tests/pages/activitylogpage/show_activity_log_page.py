# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import time
from framework.utils.common_utils import by_css
from pages.page import Page
from pages.activitylogpage.show_activity_log_locator import *
import re


class ShowActivityLogPage(Page):
    def __init__(self, driver):
        Page.__init__(self, driver)

    def get_data_on_cell(self, row=0, column=0):
        locator = by_css(FIND_DATA_BY_ROW_AND_COLUMN_NUMBER % (row, column))
        return self.driver.find(locator).text

    def get_number_of_entries_found(self):
        info = self.driver.find(LOG_INFO).text
        numbers = re.findall(r'\d+', info)
        return int(numbers[2])

    def click_on_filter_button(self):
        self.driver.find(FILTER_BUTTON).click()


