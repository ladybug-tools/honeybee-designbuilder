# coding=utf-8
"""Methods to write Honeybee core objects to dsbXML."""
import datetime
import math
import xml.etree.ElementTree as ET

from ladybug_geometry.geometry3d import Face3D
from honeybee.typing import clean_string
from honeybee.facetype import RoofCeiling, AirBoundary
from honeybee.aperture import Aperture
from honeybee.room import Room

DESIGNBUILDER_VERSION = '2025.1.0.085'
HANDLE_COUNTER = 1  # counter used to generate unique handles when necessary


def sub_face_to_dsbxml_element(
    sub_face, surface_element=None,
    block_handle='-1', zone_handle='-1', surface_index=0
):
    """Generate an dsbXML Opening Element object from a honeybee Aperture or Door.

    Args:
        sub_face: A honeybee Aperture or Door for which an dsbXML Opening Element
            object will be returned.
        surface_element: An optional XML Element for the Surface to which the
            generated opening object will be added. If None, a new XML Element
            will be generated. Note that this Surface element should have a
            Openings tag already created within it.
        block_handle: Integer for the handle of the block to which the opening
            belongs. (Default: -1).
        zone_handle: Integer for the handle of the zone to which the opening
            belongs. (Default: -1).
        surface_index: Integer for the index of the surface in the zone to which
            the opening belongs. (Default: 0).
    """
    open_type = 'Window' if isinstance(sub_face, Aperture) else 'Door'
    if surface_element is not None:
        surfaces_element = surface_element.find('Openings')
        xml_sub_face = ET.SubElement(surfaces_element, 'Opening', type=open_type)
        obj_ids = surface_element.find('ObjectIDs')
        block_handle = obj_ids.get('buildingBlockHandle')
        zone_handle = obj_ids.get('zoneHandle')
    else:
        xml_face = ET.Element('Opening', face_id_attr)
        block_handle, zone_handle, surface_index = '-1', '-1', 0
    _object_ids(xml_sub_face, ap.identifier, '0', block_handle, zone_handle, surface_index)


def face_to_dsbxml_element(
    face, zone_body_element=None, face_index=0, angle_tolerance=1.0
):
    """Generate an dsbXML Surface Element object from a honeybee Face.

    The resulting Element has all constituent geometry (Apertures, Doors).

    Args:
        face: A honeybee Face for which an dsbXML Surface Element object will
            be returned.
        zone_body_element: An optional XML Element for the Zone Body to which the
            generated surface object will be added. If None, a new XML Element
            will be generated. Note that this Zone Body element should have a
            Surfaces tag already created within it.
        face_index: An integer for the index of the parent Room Polyface3D
            to which this Face belongs. (Default: 0).
        angle_tolerance: The angle tolerance at which the geometry will
            be evaluated in degrees. (Default: 1 degree).
    """
    global HANDLE_COUNTER  # declare that we will edit the global variable

    # get the basic attributes of the Face
    if isinstance(face.type, RoofCeiling):
        face_type = 'Pitched roof' if face.tilt > angle_tolerance else 'Flat roof'
    elif isinstance(face.type, AirBoundary):
        face_type = 'Wall'
    else:
        face_type = str(face.type)
    face_id_attr = {
        'type': face_type,
        'area': str(face.area),
        'alpha': str(math.pi - face.geometry.tilt),
        'phi': str(face.geometry.azimuth),
        'defaultOpenings': 'False',
        'adjacentPartitionHandle': '-1',  # TODO: make better for adjacency
        'thickness': '0.0'  # TODO: make better for adjacency
    }

    # create the Surface element
    if zone_body_element is not None:
        surfaces_element = zone_body_element.find('Surfaces')
        dsb_face_i = len(surfaces_element.findall('Surface'))
        xml_face = ET.SubElement(surfaces_element, 'Surface', face_id_attr)
        obj_ids = zone_body_element.find('ObjectIDs')
        block_handle = obj_ids.get('buildingBlockHandle')
        zone_handle = obj_ids.get('handle')
    else:
        xml_face = ET.Element('Surface', face_id_attr)
        dsb_face_i, block_handle, zone_handle = 0, '-1', '-1'
    _object_ids(xml_face, face.identifier, '0', block_handle)

    # add the vertices that define the Face
    if face.has_parent:
        face_indices = face.parent.geometry.face_indices[face_index]
    else:
        face_indices = [tuple(range(len(face.geometry.boundary)))]
        if face.geometry.has_holes:
            counter = len(face_indices[0])
            for hole in face.geometry.holes:
                face_indices.append(tuple(range(counter, counter + len(hole))))
                counter += len(hole)
    xml_pt_i = ET.SubElement(xml_face, 'VertexIndices')
    xml_pt_i.text = '; '.join([str(i) for i in face_indices[0]])

    # add the holes as duplicated Surfaces; very stupid
    xml_hole_i = ET.SubElement(xml_face, 'HoleIndices')
    if len(face_indices) > 1:  # we have holes to add
        hole_is = []
        for j, hole in enumerate(face_indices[1:]):
            hole_id_attr = face_id_attr.copy()
            hole_id_attr['type'] = 'Hole'
            hole_geo = Face3D(hole)
            hole_id_attr['area'] = hole_geo.area
            xml_hole = ET.SubElement(surfaces_element, 'Surface', face_id_attr)
            _object_ids(xml_hole, str(HANDLE_COUNTER), '0', block_handle)
            HANDLE_COUNTER += 1
            xml_hole_pt_i = ET.SubElement(xml_hole, 'VertexIndices')
            xml_hole_pt_i.text = '; '.join([str(i) for i in hole])
            ET.SubElement(xml_hole, 'HoleIndices')
            ET.SubElement(xml_hole, 'Openings')
            ET.SubElement(xml_hole, 'Adjacencies')
            ET.SubElement(xml_hole, 'Attributes')
            hole_is.append(dsb_face_i + 1 + j)
        xml_hole_i.text = '; '.join([str(i) for i in hole_is])

    # add the various attributes of the Face
    xml_face_attr = ET.SubElement(xml_face, 'Attributes')
    xml_face_name = ET.SubElement(xml_face_attr, 'Attribute', key='Title')
    xml_face_name.text = str(face.display_name)
    xml_gbxml_type = ET.SubElement(xml_face_attr, 'Attribute', key='gbXMLSurfaceType')
    xml_gbxml_type.text = str(face.gbxml_type)

    # add any openings if they exist
    ET.SubElement(xml_face, 'Openings')
    for ap in face.apertures:
        sub_face_to_dsbxml_element(ap, xml_face, block_handle, zone_handle, dsb_face_i)
    for dr in face.doors:
        sub_face_to_dsbxml_element(dr, xml_face, block_handle, zone_handle, dsb_face_i)

    # TODO: see if adjacencies need to be added for every face
    ET.SubElement(xml_face, 'Adjacencies')

    return xml_face


def room_to_dsbxml_element(
    room, block_element=None, tolerance=0.01, angle_tolerance=1.0
):
    """Generate an dsbXML Zone Element object for a honeybee Room.

    The resulting Element has all constituent geometry (Faces, Apertures, Doors).

    Args:
        room: A honeybee Room for which an dsbXML Zone Element object will be returned.
        block_element: An optional XML Element for the BuildingBlock to which the
            generated zone object will be added. If None, a new XML Element
            will be generated. Note that this BuildingBlock element should
            have a Zones tag already created within it.
        tolerance: The absolute tolerance with which the Room geometry will
            be evaluated. (Default: 0.01, suitable for objects in meters).
        angle_tolerance: The angle tolerance at which the geometry will
            be evaluated in degrees. (Default: 1 degree).
    """
    global HANDLE_COUNTER  # declare that we will edit the global variable

    # create the zone root
    is_extrusion = room.is_extrusion(tolerance, angle_tolerance)
    zone_id_attr = {
        'parentZoneHandle': room.identifier,
        'inheritedZoneHandle': room.identifier,
        'planExtrusion': str(is_extrusion),
        'innerSurfaceMode': 'Deflation'
    }
    if block_element is not None:
        block_zones_element = block_element.find('Zones')
        xml_zone = ET.SubElement(block_zones_element, 'Zone', zone_id_attr)
        obj_ids = block_element.find('ObjectIDs')
        block_handle = obj_ids.get('handle')
    else:
        xml_zone = ET.Element('Zone', zone_id_attr)
        block_handle = '-1'
    # create the body of the room with the polyhedral vertices
    hgt = round(room.max.z - room.min.z, 4)
    xml_body = ET.SubElement(xml_zone, 'Body', volume=room.volume, extrusionHeight=hgt)
    _object_ids(xml_body, room.identifier, '0', block_handle)
    xml_vertices = ET.SubElement(xml_body, 'Vertices')
    for pt in room.geometry.vertices:
        xml_point = ET.SubElement(xml_vertices, 'Point3D')
        xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
    # add the surfaces
    ET.SubElement(xml_body, 'Surfaces')
    for i, face in enumerate(room.faces):
        face_to_dsbxml_element(face, xml_body, i, angle_tolerance)

    return xml_zone


def model_to_dsbxml_element(model):
    """Generate an dsbXML Element object for a honeybee Model.

    The resulting Element has all geometry (Rooms, Faces, Apertures, Doors, Shades).

    Args:
        model: A honeybee Model for which an dsbXML ElementTree object will be returned.
    """
    global HANDLE_COUNTER  # declare that we will edit the global variable

    # duplicate model to avoid mutating it as we edit it for INP export
    original_model = model
    model = model.duplicate()
    # scale the model if the units are not feet
    if model.units != 'Meters':
        model.convert_to_units('Meters')
    # remove degenerate geometry within DesignBuilder native tolerance
    try:
        model.remove_degenerate_geometry(0.01)
    except ValueError:
        error = 'Failed to remove degenerate Rooms.\nYour Model units system is: {}. ' \
            'Is this correct?'.format(original_model.units)
        raise ValueError(error)
    model.shade_meshes_to_shades()
    # auto-assign stories if there are none since these are needed for blocks
    if len(model.stories) == 0 and len(model.rooms) != 0:
        model.assign_stories_by_floor_height(min_difference=2.0)

    # set up the ElementTree for the XML
    model_name = clean_string(model.display_name)
    base_template = \
        '<dsbXML name="~{}" date="{}" version = "{}" objects = "all">\n' \
        '</dsbXML>\n'.format(model_name, datetime.date.today(), DESIGNBUILDER_VERSION)
    xml_root = ET.fromstring(base_template)

    # add the site and the building
    xml_site = ET.SubElement(xml_root, 'Site', handle='-1', count='1')
    ET.SubElement(xml_site, 'Attributes')
    ET.SubElement(xml_site, 'Tables')
    ET.SubElement(xml_site, 'AssemblyLibrary')
    xml_bldgs = ET.SubElement(xml_site, 'Buildings', numberOfBuildings='1')
    bldg_attr = {
        'currentComponentBlockHandle': '-1',
        'currentAssemblyInstanceHandle': '-1',
        'currentPlaneHandle': '-1'
    }
    xml_bldg = ET.SubElement(xml_bldgs, 'Building', bldg_attr)
    _object_ids(xml_bldg, '0')
    ET.SubElement(xml_bldg, 'ComponentBlocks')
    ET.SubElement(xml_bldg, 'AssemblyInstances')
    ET.SubElement(xml_bldg, 'ProfileOutlines')
    ET.SubElement(xml_bldg, 'ConstructionLines')
    ET.SubElement(xml_bldg, 'Planes')
    ET.SubElement(xml_bldg, 'HVACNetwork')
    ET.SubElement(xml_bldg, 'BookmarkBuildings', numberOfBuildings='0')
    xml_bldg_attr = ET.SubElement(xml_bldg, 'Attributes')
    xml_geo_level = ET.SubElement(xml_bldg_attr, 'Attribute', key='GeometryDataLevel')
    xml_geo_level.text = str(3)

    # group the model rooms by story and connected volume so they translate to blocks
    block_rooms, block_names = [], []
    story_rooms, story_names, _ = Room.group_by_story(model.rooms)
    for flr_rooms, flr_name in zip(story_rooms, story_names):
        adj_rooms = Room.group_by_adjacency(flr_rooms)
        if len(adj_rooms) == 1:
            block_rooms.append(flr_rooms)
            block_names.append(flr_name)
        else:
            for i, adj_group in enumerate(adj_rooms):
                block_rooms.append(adj_group)
                block_names.append('{} {}'.format(flr_name, i + 1))

    # give unique integers to each of the building blocks
    HANDLE_COUNTER = len(block_rooms)
    # convert identifiers to integers as this is the only ID format used by DesignBuilder
    HANDLE_COUNTER = model.reset_ids_to_integers(start_integer=HANDLE_COUNTER)
    HANDLE_COUNTER += 1
    # translate each block to dsbXML; including all geometry

    # set the handle of the site to the last index and reset the counter
    xml_site.set('handle', str(HANDLE_COUNTER))
    HANDLE_COUNTER = 1

    return xml_root


def model_to_dsbxml(model, program_name=None):
    """Generate an dsbXML string for a Model.

    The resulting string will include all geometry (Rooms, Faces, Apertures,
    Doors, Shades), all fully-detailed constructions + materials, all fully-detailed
    schedules, and the room properties. It will also include the simulation
    parameters. Essentially, the string includes everything needed to simulate
    the model.

    Args:
        model: A honeybee Model for which an dsbXML ElementTree object will be returned.
        program_name: Optional text to set the name of the software that will
            appear under a comment in the XML to identify where it is being exported
            from. This can be set things like "Ladybug Tools" or "Pollination"
            or some other software in which this dsbXML export capability is being
            run. If None, no comment will appear. (Default: None).

    Usage:

    .. code-block:: python

        import os
        from ladybug.futil import write_to_file
        from honeybee.model import Model
        from honeybee.room import Room
        from honeybee.config import folders

        # Crate an input Model
        room = Room.from_box('Tiny House Zone', 5, 10, 3)
        room.properties.energy.program_type = office_program
        room.properties.energy.add_default_ideal_air()
        model = Model('Tiny House', [room])

        # create the dsbXML ElementTree for the model
        xml_str = model.to.dsbxml(model)

        # write the final string into an XML file
        dsbxml = os.path.join(folders.default_simulation_folder, 'in_dsb.xml')
        write_to_file(dsbxml, xml_str, True)
    """
    # create the XML string
    xml_root = model_to_dsbxml_element(model)
    ET.indent(xml_root)
    dsbxml_str = ET.tostring(xml_root, encoding='unicode')

    # add the declaration and a comment about the authoring program
    prog_comment = ''
    if program_name is not None:
        prog_comment = '<!--File generated by {}-->\n'.format(program_name)
    base_template = \
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{}'.format(prog_comment)
    dsbxml_str = base_template + dsbxml_str
    return dsbxml_str


def _object_ids(
    parent, handle,
    building='-1', block='-1', zone='-1', surface='-1', opening='-1'
):
    """Create a sub element for DesignBuilder ObjectIDs."""
    bldg_id_attr = {
        'handle': handle,
        'buildingHandle': building,
        'buildingBlockHandle': block,
        'zoneHandle': zone,
        'surfaceIndex': surface,
        'openingIndex': opening
    }
    return ET.SubElement(parent, 'ObjectIDs', bldg_id_attr)
