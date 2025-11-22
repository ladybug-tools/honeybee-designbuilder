# coding=utf-8
# import all of the modules for writing geometry to DsbXML
import honeybee.writer.model as model_writer

from .writer import model_to_dsbxml, model_to_dsbxml_file, model_to_dsbxml_element

# add writers to the honeybee-core modules
model_writer.dsbxml = model_to_dsbxml
model_writer.dsbxml_file = model_to_dsbxml_file
model_writer.dsbxml_element = model_to_dsbxml_element
