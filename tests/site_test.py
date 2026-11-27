"""Test the translators for site and project information."""
import xml.etree.ElementTree as ET

from ladybug.projectinfo import ProjectInfo
from honeybee_designbuilder.site import modify_template_for_site


def test_modify_template_for_site():
    """Check the epw_to_prn function."""
    project_info_path = './tests/assets/project_info.json'
    project_info = ProjectInfo.from_json(project_info_path)

    template_file = './honeybee_designbuilder/_templates/Default.xml'
    xml_tree = ET.parse(template_file)
    xml_root = xml_tree.getroot()

    xml_template = modify_template_for_site(xml_root, project_info)

    xml_site = xml_template.find('Site')
    xml_attrs = xml_site.find('Attributes')
    xml_lat = xml_attrs.find('.//Attribute[@name="Latitude"]')
    assert xml_lat.text == '40.65'
    xml_lon = xml_attrs.find('.//Attribute[@name="Longitude"]')
    assert xml_lon.text == '-73.8'
    xml_elev = xml_attrs.find('.//Attribute[@name="Elevation"]')
    assert xml_elev.text == '5.0'
