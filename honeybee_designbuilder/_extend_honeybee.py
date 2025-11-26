# coding=utf-8
# import all of the modules for writing geometry to dsbXML
from honeybee.properties import ModelProperties, RoomProperties
import honeybee.writer.model as model_writer

from .properties.model import ModelDesignBuilderProperties
from .properties.room import RoomDesignBuilderProperties
from .writer import model_to_dsbxml, model_to_dsbxml_file, model_to_dsbxml_element

# set a hidden designbuilder attribute on each core geometry Property class to None
# define methods to produce designbuilder property instances on each Property instance
ModelProperties._designbuilder = None
RoomProperties._designbuilder = None


def model_designbuilder_properties(self):
    if self._designbuilder is None:
        self._designbuilder = ModelDesignBuilderProperties(self.host)
    return self._designbuilder


def room_designbuilder_properties(self):
    if self._designbuilder is None:
        self._designbuilder = RoomDesignBuilderProperties(self.host)
    return self._designbuilder


# add designbuilder property methods to the Properties classes
ModelProperties.designbuilder = property(model_designbuilder_properties)
RoomProperties.designbuilder = property(room_designbuilder_properties)


# add writers to the honeybee-core modules
model_writer.dsbxml = model_to_dsbxml
model_writer.dsbxml_file = model_to_dsbxml_file
model_writer.dsbxml_element = model_to_dsbxml_element
