from django.template import Library
from django_date_extensions.fields import ApproximateDate

from complex_fields.models import ComplexFieldListContainer
from .viewcomplexfield import view_complex_field

register = Library()

@register.inclusion_tag('view_list.html')
def view_complex_field_list(field_list, object_id, path):
    
    fields = {'field_list': []}

    for field in field_list.get_list():
        
        field_info = view_complex_field(field, object_id, path)

        fields['field_name'] = field_info['field_name']
        fields['field_str_id'] = field_info['field_str_id']

        fields['field_list'].append({
            'value' : field_info['value'],
            'object_id': field_info['object_id'],
            'field_id': field_info['field_id'],
            'path': path,
        })
    
    return fields
