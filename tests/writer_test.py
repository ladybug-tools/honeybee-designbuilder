"""Test the translators for geometry to INP."""
import xml.etree.ElementTree as ET

from ladybug_geometry.geometry3d import Point3D, Vector3D, Mesh3D

from honeybee.model import Model
from honeybee.room import Room
from honeybee.shademesh import ShadeMesh


def test_model_writer():
    """Test the basic functionality of the Model writer."""
    room = Room.from_box('Tiny_House_Zone', 5, 10, 3)
    south_face = room[3]
    south_face.apertures_by_ratio(0.4, 0.01)
    south_face.apertures[0].overhang(0.5, indoor=False)
    south_face.apertures[0].overhang(0.5, indoor=True)
    south_face.apertures[0].move_shades(Vector3D(0, 0, -0.5))
    pts = (Point3D(0, 0, 4), Point3D(0, 2, 4), Point3D(2, 2, 4),
           Point3D(2, 0, 4), Point3D(4, 0, 4))
    mesh = Mesh3D(pts, [(0, 1, 2, 3), (2, 3, 4)])
    awning_1 = ShadeMesh('Awning_1', mesh)

    model = Model('Tiny_House', [room], shade_meshes=[awning_1])

    xml_et = model.to.dsbxml_element(model)
    assert isinstance(xml_et, ET.Element)

    xml_str = model.to.dsbxml(model, program_name='Ladybug Tools')
    assert isinstance(xml_str, str)
    print(xml_str)


def test_model_writer_from_standard_hbjson():
    """Test translating a HBJSON to an XML ElementTree."""
    standard_test = './tests/assets/small_revit_sample.hbjson'
    hb_model = Model.from_file(standard_test)

    xml_str = hb_model.to.dsbxml(hb_model)
    assert isinstance(xml_str, str)
    print(xml_str)
