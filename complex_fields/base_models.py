from django.utils.translation import get_language
from django.core.exceptions import ObjectDoesNotExist

from source.models import Source

class SourceRequiredException(Exception):
    def __init__(self, message):
        super().__init__(message)

class ConfidenceRequiredException(Exception):
    def __init__(self, message):
        super().__init__(message)


class BaseModel(object):
    confidence_required = True

    def __init__(self):
        pass

    @classmethod
    def from_id(cls, id_):
        try:
            object_ = cls.objects.get(id=id_)
            return object_
        except cls.DoesNotExist:
            return None

    def validate(self, dict_values, lang=get_language()):
        errors = {}
        for field in self.complex_fields:
            field_name = field.get_field_str_id()

            if ((field_name not in dict_values or
                 dict_values[field_name]['value'] == "") and
                field_name in self.required_fields):
                errors[field_name] = "This field is required"
            elif field_name in dict_values:
                sources = {
                    'sources': dict_values[field_name].get('sources', []),
                    'confidence': dict_values[field_name].get('confidence', 0),
                }
                (error, value) = field.validate(
                    dict_values[field_name]['value'], lang, sources
                )

                dict_values[field_name]['value'] = value
                if error is not None:
                    errors[field_name] = error

        return (errors, dict_values)

    def update_list(self, complex_list, dict_values, lang):

        # Implies a new format for lists of complex fields
        #
        # {'Person_PersonAlias: {
        #     'values': ['list', 'of', 'string', 'values'],
        #     'sources': [],
        #     'confidence': 1,
        #     'field_name': 'aliases',
        #     }
        # }

        complex_fields = complex_list.get_list()
        field_model = complex_list.field_model
        table_object = complex_list.table_object
        field_key = complex_list.get_field_str_id()

        update_values = set()
        current_values = set()

        import pdb
        pdb.set_trace()

        if complex_fields:

            field_lookup = {v.get_value().value: v for v in complex_fields if v.get_value()}

            current_values = {v.get_value().value for v in complex_fields if v.get_value()}

        for value in dict_values[field_key]['values']:
            try:
                value = field_model.objects.get(id=value)
            except (ObjectDoesNotExist, ValueError):
                value = field_model(value=value,
                                    object_ref=table_object)
                value.save()

            update_values.add(value.value)

        # check for new things
        new_values = update_values - current_values

        for value in new_values:
            field = complex_list.get_complex_field(0)
            field.update_new(value, lang, dict_values[field_key])

        # check for things that were removed
        removed_values = current_values - update_values
        for value in removed_values:
            field = field_lookup[value].get_value()
            if field:
                field.delete()

        unchanged_values = update_values & current_values
        for value in unchanged_values:
            field = field_lookup[value]
            field.update(value, lang, dict_values[field_key])


    def update_field(self, field, dict_values, lang):
        field_name = field.get_field_str_id()

        if field_name in dict_values:

            if field.sourced:

                try:
                    sources = dict_values[field_name]['sources']
                except KeyError:
                    raise SourceRequiredException('The field {} requires a source'.format(field_name))

                try:
                    confidence = dict_values[field_name]['confidence']
                except KeyError:
                    if self.confidence_required:
                        raise ConfidenceRequiredException('The field {} requires a confidence'.format(field_name))

                sources = {
                    'confidence': confidence,
                    'sources': sources,
                }
                field.update(dict_values[field_name]['value'], lang, sources)
            else:
                field.update(dict_values[field_name]['value'], lang)


    def update(self, dict_values, lang=get_language()):
        self.save()
        for field in self.complex_fields:
            self.update_field(field, dict_values, lang)

        for complex_list in self.complex_lists:
            self.update_list(complex_list, dict_values, lang)

    @classmethod
    def create(cls, dict_values, lang=get_language()):
        field = cls()
        field.update(dict_values, lang)

        return field

