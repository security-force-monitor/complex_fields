import django.dispatch
from django.utils.translation import get_language
from django.core.exceptions import ObjectDoesNotExist

from source.models import Source

object_ref_saved = django.dispatch.Signal(providing_args=["object_id"])


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

    def object_ref_saved(self):
        if hasattr(self, 'uuid'):
            object_ref_saved.send(sender=self.__class__,
                                  object_id=self.uuid)

        else:
            object_ref_saved.send(sender=self.__class__,
                                  object_id=self.id)

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
        #     'values': <queryset containing saved isntances of PersonAlias>,
        #     'sources': [],
        #     'confidence': 1,
        #     'field_name': 'aliases',
        #     }
        # }

        field_model = complex_list.field_model
        field_key = complex_list.get_field_str_id()

        update_values = set(dict_values[field_key]['values'])
        current_values = set(field_model.objects.filter(object_ref=self))

        if update_values:
            removed_values = current_values - update_values

            for field in removed_values:
                field.delete()

            for field in update_values:
                if field.object_ref.id == complex_list.table_object.id:
                    field.save()
                    field.sources.set(dict_values[field_key]['sources'], clear=True)
                else:
                    new_object = field_model.objects.create(value=field.value,
                                                            object_ref=complex_list.table_object,
                                                            lang=field.lang)
                    new_object.sources.set(dict_values[field_key]['sources'], clear=True)

        else:
            # If update values is empty, that means the user cleared out the
            # field so delete everything.
            for field in current_values:
                field.delete()

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
            if field.get_field_str_id() in dict_values:
                self.update_field(field, dict_values, lang)

        for complex_list in self.complex_lists:
            if complex_list.get_field_str_id() in dict_values:
                self.update_list(complex_list, dict_values, lang)

    @classmethod
    def create(cls, dict_values, lang=get_language()):
        field = cls()
        field.update(dict_values, lang)

        return field

