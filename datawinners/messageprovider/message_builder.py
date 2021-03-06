class ResponseBuilder(object):
    def __init__(self, form_model, processed_data):
        self.form_model = form_model
        self.processed_data = processed_data

    def get_expanded_response(self):
        new_dict = self.form_model.stringify(self.processed_data)
        return " ".join([": ".join(each) for each in new_dict.items()])