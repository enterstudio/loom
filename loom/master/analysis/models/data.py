from django.conf import settings
from django.utils import timezone
import os
import uuid

from analysis.models.base import AnalysisAppInstanceModel, \
    AnalysisAppImmutableModel
from universalmodels import fields


class DataObject(AnalysisAppInstanceModel):
    """A reference to DataObjectContent. While there is only one
    object for each set of content, there can be many references
    to it. That way if the same content arises twice independently 
    we can still keep separate provenance graphs.
    """

    pass

class DataObjectContent(AnalysisAppImmutableModel):
    """A unit of data passed into or created by analysis steps.
    This may be a file, an array of files, a JSON data object, 
    or an array of JSON objects.
    """

    def get_substitution_value(self):
        return self.downcast().get_substitution_value()


class FileDataObject(DataObject):

    NAME_FIELD = 'content__filename'

    content = fields.ForeignKey('FileContent')
    file_location = fields.ForeignKey('FileLocation', null=True)


class FileContent(DataObjectContent):
    """Represents a file, including its content (identified by a hash), its 
    file name, and user-defined metadata.
    """

    filename = fields.CharField(max_length=255)
    unnamed_file_content = fields.ForeignKey('UnnamedFileContent')

    def get_substitution_value(self):
        return self.filename


class UnnamedFileContent(AnalysisAppImmutableModel):
    """Represents file content, identified by a hash. Ignores file name.
    """

    hash_value = fields.CharField(max_length=100)
    hash_function = fields.CharField(max_length=100)


class FileLocation(AnalysisAppInstanceModel):
    """Location of file content.
    """

    unnamed_file_content = fields.ForeignKey(
        'UnnamedFileContent',
        null=True,
        related_name='file_locations')
    url = fields.CharField(max_length=1000)
    status = fields.CharField(
        max_length=256,
        default='incomplete',
        choices=(('incomplete', 'Incomplete'),
                 ('complete', 'Complete'),
                 ('failed', 'Failed'))
    )

    @classmethod
    def get_by_file(self, file_data_object):
        locations = self.objects.filter(unnamed_file_content=file_data_object.content.unnamed_file_content).all()
        return locations

    @classmethod
    def get_location_for_import(cls, file_data_object):
        return cls.create({
            'url': cls._get_url(cls._get_path_for_import(file_data_object)),
            'unnamed_file_content': file_data_object.content.unnamed_file_content.to_struct()
        })

    @classmethod
    def _get_path_for_import(cls, file_data_object):
        if not settings.FILE_ROOT:
            raise Exception('FILE_ROOT is not set')

        if settings.BROWSEABLE_FILE_STORAGE:
            if not settings.IMPORT_DIR:
                raise Exception('IMPORT_DIR is not set')
            return os.path.join(
                '/',
                settings.FILE_ROOT,
                settings.IMPORT_DIR,
                "%s-%s-%s" % (
                    timezone.now().strftime('%Y%m%d%H%M%S'),
                    file_data_object._id,
                    file_data_object.content.filename
                )
            )
        else:
            return os.path.join(
                '/',
                settings.FILE_ROOT,
                '%s-%s' % (
                    file_data_object.content.unnamed_file_content.hash_function,
                    file_data_object.content.unnamed_file_content.hash_value
                )
            )

    @classmethod
    def get_temp_location(cls,):
        return cls.create({
            'url': cls._get_url(cls._get_temp_path_for_import())
        })

    @classmethod
    def _get_temp_path_for_import(cls):
        return os.path.join(
            '/',
            settings.FILE_ROOT,
            'tmp',
            uuid.uuid4().hex
        )

    @classmethod
    def _get_url(cls, path):
        if settings.FILE_SERVER_TYPE == 'LOCAL':
            return 'file://' + path
        elif settings.FILE_SERVER_TYPE == 'GOOGLE_CLOUD':
            return 'gs://' + os.path.join(settings.BUCKET_ID, path)
        else:
            raise Exception('Couldn\'t recognize value for setting FILE_SERVER_TYPE="%s"' % settings.FILE_SERVER_TYPE)


class FileImport(AnalysisAppInstanceModel):
    file_data_object = fields.ForeignKey(
        'FileDataObject',
        related_name = 'file_imports',
        null=True)
    note = fields.TextField(max_length=10000, null=True)
    source_url = fields.TextField(max_length=1000)
    temp_file_location = fields.ForeignKey('FileLocation', null=True, related_name='temp_file_import')
    file_location = fields.ForeignKey('FileLocation', null=True)

    def after_create_or_update(self):
        # If there is no FileLocation, set a temporary one.
        # The client will need this to know upload destination, but we
        # can't create a permanent FileLocation until we know the file hash, since
        # it may be used in the name of the file location.
        if not self.temp_file_location and not self.file_location:
            self._set_temp_file_location()

        # If FileDataObject was added and no permanent FileLocation exists,
        # create one. The client will need this to know upload destination.
        elif self.file_data_object and not self.file_location:
            self._set_file_location()

    def _set_temp_file_location(self):
        """A temp location is used since the hash is used in the final file location,
        and this may not be known at time of upload. This is because the method for 
        copying the file also may also generate the hash.
        """
        self.temp_file_location = FileLocation.get_temp_location()
        self.save()

    def _set_file_location(self):
        """After uploading the file to a temp location and updating the FileImport with the full 
        FileContent (which includes the hash), the final storage location can be determined.
        """
        self.file_location = FileLocation.get_location_for_import(self.file_data_object)
        self.save()


'''    
class DataObjectArray(DataObject):
    """An array of data objects, all of the same type.
    """
    data_objects = fields.ManyToManyField('DataObject',
                                          related_name = 'parent')

    @classmethod
    def create(cls, data):
        o = super(DataObjectArray, cls).create(data)
        cls._verify_children_have_same_type(o)
        return o

    def _verify_children_have_same_type(self):
        child_classes = set()
        for data_object in self.data_objects.all():
            child_classes.add(data_object.downcast().__class__)
            if len(child_classes) > 1:
                raise DataObjectValidationError()
    
    def is_available(self):
        """An array is available if all members are available"""
        return all([member.downcast().is_available() for member in
                    self.data_objects.all()])

class DatabaseDataObject(DataObject):

    def is_available(self):
        """An object stored in the database is always available.
        """
        return True

    class Meta:
        abstract = True


class JSONDataObject(DatabaseDataObject):
    """Contains any valid JSON value. This could be 
    an integer, string, float, boolean, list, or dict
    """

    json_data = fields.JSONField()


class StringDataObject(DatabaseDataObject):

    string_value = fields.TextField()


class BooleanDataObject(DatabaseDataObject):

    boolean_value = fields.BooleanField()


class IntegerDataObject(DatabaseDataObject):

    integer_value = fields.IntegerField()
'''