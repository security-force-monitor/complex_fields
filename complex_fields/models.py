import inspect
import reversion
import re

from django.db import models
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError, FieldDoesNotExist
from django.utils.translation import ugettext as _
from django.utils.translation import get_language

from languages_plus.models import Language

from source.models import AccessPoint, Source
from translation.models import get_language_from_iso
from sfm_pc.utils import class_for_name


CONFIDENCE_LEVELS = (
    ('1', _('Low')),
    ('2', _('Medium')),
    ('3', _('High')),
)


class ComplexField(models.Model):
    lang = models.CharField(max_length=5, null=True)
    sources = models.ManyToManyField(Source, related_name="%(app_label)s_%(class)s_related")
    accesspoints = models.ManyToManyField(AccessPoint, related_name="%(app_label)s_%(class)s_related")
    confidence = models.CharField(max_length=1, default=1, choices=CONFIDENCE_LEVELS)

    class Meta:
        abstract = True

    def revert(self, id):
        if hasattr(self, 'versioned'):
            version = reversion.get_for_object(self).get(id=id)
            version.revert()
            return version.field_dict['sources']

    def revert_to_source(self, source_ids):
        if hasattr(self, 'versioned'):
            versions = reversion.get_for_object(self)
            version = None
            max_id = 0
            for vers in versions:
                if vers.field_dict['sources'] == source_ids and vers.id > max_id:
                    version = vers
                    max_id = vers.id

            if version is None:
                for vers in versions:
                    if vers.field_dict['sources'] == [] and vers.id > max_id:
                        version = vers

            if version is not None:
                try:
                    version.revert()
                except IntegrityError:
                    # The original object of this version has been deleted,
                    # we ignore it.
                    pass

    def __str__(self):
        if self.value is None:
            return ""
        return str(self.value)


class ComplexFieldContainer(object):
    def __init__(self, table_object, field_model, id_=None):
        self.table_object = table_object
        self.field_model = field_model
        self.sourced = hasattr(field_model(), 'sourced')
        self.translated = hasattr(field_model(), 'translated')
        self.versioned = hasattr(field_model(), 'versioned')
        self.id_ = id_

    def __str__(self):
        value = self.get_value(get_language())

        if value is None:
            value = self.get_value('en')
            if value is None:
                value = ""
        return str(value)

    @property
    def field_name(self):
        if self.id_ is None:
            if not hasattr(self.field_model(),'field_name'):
                return 'No field model'
            return self.field_model().field_name

        try:
            field = self.field_model.objects.get(pk=self.id_)
            return field.field_name
        except self.field_model.DoesNotExist:
            if not hasattr(self.field_model(),'field_name'):
                return 'No field model'
            return self.field_model().field_name

    def get_attr_name(self):
        table_name = self.table_object.__class__.__name__
        return re.sub(table_name, '', self.field_model.__name__).lower()

    def get_object_id(self):
        if self.table_object.id:
            return self.table_object.id
        else:
            return None

    def get_object_name(self):
        return self.table_object.__class__.__name__.lower()

    def get_field_str_id(self):
        table_name = self.table_object.__class__.__name__
        field_name = self.field_model.__name__
        return table_name + "_" + field_name

    def get_field(self, lang=get_language()):
        if self.id_ == 0:
            return None

        c_fields = self.field_model.objects.filter(object_ref=self.table_object)
        if self.id_:
            c_fields = c_fields.filter(pk=self.id_)

        if self.translated:
            c_fields_lang = c_fields.filter(lang=lang)
            c_field = list(c_fields_lang[:1])

            if not c_field:
                c_fields = c_fields.filter(lang='en')
                c_field = list(c_fields[:1])
        else:
            c_field = list(c_fields[:1])

        if c_field:
            return c_field[0]

        return None

    def get_value(self, lang=get_language()):
        field = self.get_field(lang)
        if field is not None:
            return field
        else:
            field = self.get_field('en')
            if field is not None:
                return field
        return None

    def set_value(self, value, lang=get_language()):
        c_fields = self.field_model.objects.filter(object_ref=self.table_object)
        if self.translated:
            c_fields = c_fields.filter(lang=lang)
        field = list(c_fields[:1])
        if field:
            field = field[0]
        else:
            field = self.field_model()
            if self.translated:
                field.lang = lang
            else:
                field.lang = 'en'

        if field._meta.get_field('value').get_internal_type() == "BooleanField":
            if value == "False":
                value = False
            elif value == "True":
                value = True

        field.value = value
        field.save()

    def get_translations(self):
        translations = []
        if not hasattr(self.field_model, 'translated'):
            return translations

        c_fields = self.field_model.objects.filter(object_ref=self.table_object)
        c_fields = c_fields.exclude(value__isnull=True).exclude(value__exact='')

        for field in c_fields:
            trans = {
                'lang': get_language_from_iso(field.lang),
                'value': field.value
            }
            translations.append(trans)

        return translations

    def get_sources(self):
        sources = []
        if not self.sourced:
            return sources

        c_fields = self.field_model.objects.filter(object_ref=self.table_object)

        source_ids = []
        for field in c_fields:
            source_ids.extend([s.uuid for s in field.sources.all()])

        return Source.objects.filter(uuid__in=source_ids)

    def get_confidence(self):
        field = self.get_field()
        if field is None:
            return '1'
        return field.confidence

    def update(self, value, lang, sources={}):
        if not self.translated:
            c_field = self.get_field(lang)
        else:
            c_field = self.get_field(None)

        if c_field:
            if c_field.source_required:
                c_field.sources.set(sources['sources'], clear=True)

            if self.translated:
                c_field.lang = lang

            c_field.value = value
            c_field.save()
        else:
            self.update_new(value, lang, sources=sources)

    def update_new(self, value, lang, sources={}):
        if self.translated:
            c_field = self.field_model(object_ref=self.table_object, lang=lang)
        else:
            c_field = self.field_model(object_ref=self.table_object)

        c_field.value = value

        if self.translated:
            c_field.lang = lang

        c_field.save()

        if c_field.source_required:
            c_field.confidence = sources['confidence']
            c_field.sources.set(sources['sources'], clear=True)

    def adapt_value(self, value):
        c_field = self.field_model()
        internal_type = c_field._meta.get_field('value').get_internal_type()

        if internal_type.strip() == "BooleanField":
            if value.strip() == "False" or value == "":
                return (False, None)
            elif value.strip() == "True":
                return (True, None)
            else:
                return (None, "Invalid value for this field")
        elif internal_type.strip() == "ForeignKey":
            if value == "":
                return (None, None)

            fk_model = self.get_fk_model()
            value, created = fk_model.objects.get_or_create(value=value)

            #return (object_, None)
            return (value, None)

        elif internal_type.strip() == "IntegerField":
            if value.strip() == "":
                return (0, None)

        return (value, None)

    def update_translations(self, value, lang, sources):
        c_fields = self.field_model.objects.filter(object_ref=self.table_object)
        sources_updated = False

        for field in c_fields:
            # Set translation values to None if the value is changed or False
            # if it's a boolean
            if field is None or field.value != value:
                field.value = None

            # Update sources for all translations if they are not the same
            if self.sourced and not self.has_same_sources(sources):
                sources_updated = True
                field.sources.clear()
                for source in sources['sources']:
                    field.sources.add(source)
                field.confidence = sources['confidence']

            if field.lang != lang:
                field.save()

        return sources_updated

    def translate(self, value, lang):
        c_fields = self.field_model.objects.filter(object_ref=self.table_object)

        if not c_fields.exists():
            raise FieldDoesNotExist("Can't translate a field that doesn't exist")

        c_field = c_fields.filter(lang=lang)
        c_field = list(c_field[:1])
        if not c_field:
            c_field = self.field_model(object_ref=self.table_object, lang=lang)
        else:
            c_field = c_field[0]
            if c_field.value != None:
                raise ValidationError("Can't translate an already translated field")

        c_field.value = value
        c_field.save()

        if hasattr(c_field, 'sourced'):
            with_sources = c_fields.exclude(sources=None)
            sources = with_sources[0].sources.all()
            for src in sources:
                c_field.sources.add(src)

        c_field.save()

    def validate(self, value, lang, sources={}):

        if (hasattr(self.field_model(), "source_required") and
            value != ""):
            if not len(sources['sources']) :
                return ("sources are required to update this field", value)
            elif sources['confidence'] == 0 :
                return ("A confidence must be set for this field", value)


        (value, error) = self.adapt_value(value)
        return (error, value)

    def get_fk_model(self, field_name="value"):
        field_object, model, direct, m2m = (
            self.field_model._meta.get_field_by_name(field_name)
        )
        if not m2m and direct and isinstance(field_object, models.ForeignKey):
            return field_object.rel.to
        return None


    def has_same_sources(self, sources):
        if not self.get_confidence() == sources['confidence']:
            return False

        sources = [
            {"source": src}
            for src in sources['sources']
        ]

        saved_sources = []
        for src in self.get_sources():
            saved_src = {}
            saved_src['source'] = src
            saved_sources.append(saved_src)
        pairs = zip(saved_sources, sources)
        if len(saved_sources) != len(sources) or any(x != y for x, y in pairs):
            return False
        return True

    @classmethod
    def field_from_str_and_id(cls, object_name, object_id, field_name, field_id=None):
        object_class = class_for_name(
            object_name.capitalize(),
            object_name + ".models"
        )

        if object_id == '0':
            object_ = object_class()
        else:
            object_ = object_class.from_id(object_id)
        field = getattr(object_, field_name)

        if isinstance(field, ComplexFieldListContainer):
            container = ComplexFieldListContainer(field.table_object, field.field_model)
            field = container.get_complex_field(field_id)

        return field


class ComplexFieldListContainer(object):
    def __init__(self, table_object, field_model):
        self.table_object = table_object
        self.field_model = field_model

    def get_list(self):
        complex_fields = []
        try:
            fields = self.field_model.objects.filter(object_ref=self.table_object).order_by("value")
        except self.field_model.DoesNotExist:
            return []
        for field in fields:
            complex_fields.append(
                ComplexFieldContainer(self.table_object, self.field_model, field.id)
            )

        return complex_fields

    def get_complex_field(self, id_):
        try:
            field = ComplexFieldContainer(self.table_object, self.field_model, id_)
            return field
        except self.field_model.DoesNotExist:
            return None

    def get_field_str_id(self):
        table_name = self.table_object.__class__.__name__
        field_name = self.field_model.__name__
        return table_name + "_" + field_name
