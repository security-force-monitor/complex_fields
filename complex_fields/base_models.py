from django.utils.translation import get_language

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

    def update(self, dict_values, lang=get_language()):
        self.save()
        for field in self.complex_fields:
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

    @classmethod
    def create(cls, dict_values, lang=get_language()):
        field = cls()
        field.update(dict_values, lang)
        
        return field

