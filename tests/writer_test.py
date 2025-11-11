"""Test the translators for geometry to INP."""
import xml.etree.ElementTree as ET

from ladybug_geometry.geometry3d import Point3D, Vector3D, Mesh3D
from honeybee.model import Model
from honeybee.room import Room
from honeybee.face import Face
from honeybee.aperture import Aperture
from honeybee.door import Door
from honeybee.shademesh import ShadeMesh
# from honeybee.boundarycondition import boundary_conditions as bcs

from honeybee_designbuilder.writer import sub_face_to_dsbxml, face_to_dsbxml, \
    room_to_dsbxml


def test_aperture_writer():
    """Test the basic functionality of the Aperture dsbXML writer."""
    vertices_parent_wall = [[0, 0, 0], [0, 10, 0], [0, 10, 3], [0, 0, 3]]
    vertices_wall = [[0, 1, 1], [0, 3, 1], [0, 3, 2.5], [0, 1, 2.5]]
    vertices_parent_roof = [[10, 0, 3], [10, 10, 3], [0, 10, 3], [0, 0, 3]]
    vertices_roof = [[4, 1, 3], [4, 4, 3], [1, 4, 3], [1, 1, 3]]

    wf = Face.from_vertices('wall_face', vertices_parent_wall)
    wa = Aperture.from_vertices('wall_window', vertices_wall)
    wf.add_aperture(wa)

    sf_xml = sub_face_to_dsbxml(wa)
    assert isinstance(sf_xml, str)
    assert sf_xml.startswith('<Opening type="Window">')

    rf = Face.from_vertices('roof_face', vertices_parent_roof)
    ra = Aperture.from_vertices('roof_window', vertices_roof)
    rf.add_aperture(ra)

    sf_xml = sub_face_to_dsbxml(ra)
    assert isinstance(sf_xml, str)
    assert sf_xml.startswith('<Opening type="Window">')


def test_door_writer():
    """Test the basic functionality of the Door dsbXML writer."""
    vertices_parent_wall = [[0, 0, 0], [0, 10, 0], [0, 10, 3], [0, 0, 3]]
    vertices_wall = [[0, 1, 0.1], [0, 2, 0.1], [0, 2, 2.8], [0, 1, 2.8]]
    vertices_parent_roof = [[10, 0, 3], [10, 10, 3], [0, 10, 3], [0, 0, 3]]
    vertices_roof = [[4, 3, 3], [4, 4, 3], [3, 4, 3], [3, 3, 3]]

    wf = Face.from_vertices('wall_face', vertices_parent_wall)
    wd = Door.from_vertices('wall_door', vertices_wall)
    wf.add_door(wd)

    sf_xml = sub_face_to_dsbxml(wf)
    assert isinstance(sf_xml, str)
    assert sf_xml.startswith('<Opening type="Door">')

    rf = Face.from_vertices('roof_face', vertices_parent_roof)
    rd = Door.from_vertices('roof_window', vertices_roof)
    rf.add_door(rd)

    sf_xml = sub_face_to_dsbxml(rd)
    assert isinstance(sf_xml, str)
    assert sf_xml.startswith('<Opening type="Door">')


def test_face_writer():
    """Test the basic functionality of the Face dsbXML writer."""
    wall_pts = [[0, 0, 0], [10, 0, 0], [10, 0, 10], [0, 0, 10]]
    roof_pts = [[0, 0, 3], [10, 0, 3], [10, 10, 3], [0, 10, 3]]
    floor_pts = [[0, 0, 0], [0, 10, 0], [10, 10, 0], [10, 0, 0]]

    face = Face.from_vertices('wall_face', wall_pts)
    f_xml = face_to_dsbxml(face)
    assert isinstance(f_xml, str)
    assert f_xml.startswith('<Surface type="Wall"')

    face = Face.from_vertices('roof_face', roof_pts)
    f_xml = face_to_dsbxml(face)
    assert isinstance(f_xml, str)
    assert f_xml.startswith('<Surface type="Flat roof"')

    face = Face.from_vertices('floor_face', floor_pts)
    f_xml = face_to_dsbxml(face)
    assert isinstance(f_xml, str)
    assert f_xml.startswith('<Surface type="Floor"')


def test_room_writer():
    """Test the basic functionality of the Room dsbXML writer."""
    room = Room.from_box('Tiny_House_Zone', 15, 30, 10)
    south_face = room[3]
    south_face.apertures_by_ratio(0.4, 0.01)
    south_face.apertures[0].overhang(0.5, indoor=False)
    south_face.apertures[0].overhang(0.5, indoor=True)
    south_face.apertures[0].move_shades(Vector3D(0, 0, -0.5))

    r_xml = room_to_dsbxml(room)
    assert isinstance(r_xml, str)
    assert r_xml.startswith('<Zone ')


def test_model_writer():
    """Test the basic functionality of the Model writer."""
    room = Room.from_box('Tiny_House_Zone', 5, 10, 3)
    south_face = room[3]
    south_face.apertures_by_ratio(0.4, 0.01)
    south_face.apertures[0].overhang(0.5, indoor=False)
    south_face.apertures[0].overhang(0.5, indoor=True)
    south_face.apertures[0].move_shades(Vector3D(0, 0, -0.5))
    room.display_name = 'Tiny House Zone'
    room.rename_faces_by_attribute()
    room.rename_apertures_by_attribute()

    pts = (Point3D(0, 0, 4), Point3D(0, 2, 4), Point3D(2, 2, 4),
           Point3D(2, 0, 4), Point3D(4, 0, 4))
    mesh = Mesh3D(pts, [(0, 1, 2, 3), (2, 3, 4)])
    awning_1 = ShadeMesh('Awning_1', mesh)

    model = Model('Tiny_House', [room], shade_meshes=[awning_1])

    xml_et = model.to.dsbxml_element(model)
    assert isinstance(xml_et, ET.Element)

    xml_str = model.to.dsbxml(model, program_name='Ladybug Tools')
    assert isinstance(xml_str, str)

    # write the string to a file
    test_file = 'C:/Users/Chris/Documents/GitHub/honeybee-designbuilder/tests/assets/test.xml'
    with open(test_file, 'w') as fp:
        fp.write(xml_str)


def test_model_writer_adjacency():
    """Test the Model writer with a model that has an adjacency."""
    room_1 = Room.from_box('Tiny_House_Zone_1', 5, 10, 3)
    room_1.display_name = 'Tiny House Zone 1'
    room_1.rename_faces_by_attribute()
    room_2 = Room.from_box('Tiny_House_Zone_2', 5, 10, 3, origin=Point3D(5, 0, 0))
    room_2.display_name = 'Tiny House Zone 2'
    room_2.rename_faces_by_attribute()
    Room.solve_adjacency([room_1, room_2])

    model = Model('Tiny_House', [room_1, room_2])

    xml_et = model.to.dsbxml_element(model)
    assert isinstance(xml_et, ET.Element)

    xml_str = model.to.dsbxml(model, program_name='Ladybug Tools')
    assert isinstance(xml_str, str)

    # write the string to a file
    test_file = 'C:/Users/Chris/Documents/GitHub/honeybee-designbuilder/tests/assets/test.xml'
    with open(test_file, 'w') as fp:
        fp.write(xml_str)


def test_model_writer_single_block_hbjson():
    """Test translating a HBJSON of a single block to a dsbXML."""
    standard_test = './tests/assets/small_revit_block.hbjson'
    model = Model.from_file(standard_test)

    xml_str = model.to.dsbxml(model, program_name='Ladybug Tools')
    assert isinstance(xml_str, str)

    # write the string to a file
    test_file = 'C:/Users/Chris/Documents/GitHub/honeybee-designbuilder/tests/assets/test.xml'
    with open(test_file, 'w') as fp:
        fp.write(xml_str)


def test_model_writer_standard_hbjson():
    """Test translating a typical HBJSON to a dsbXML."""
    standard_test = './tests/assets/small_revit_sample.hbjson'
    hb_model = Model.from_file(standard_test)

    xml_str = hb_model.to.dsbxml(hb_model)
    assert isinstance(xml_str, str)
