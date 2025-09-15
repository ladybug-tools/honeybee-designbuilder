# coding=utf-8
"""Methods to write Honeybee core objects to DsbXML."""
import datetime
import xml.etree.ElementTree as ET

from honeybee.typing import clean_string
from honeybee.room import Room

DESIGNBUILDER_VERSION = '2025.1.0.085'


def room_to_dsbxml_element(
    room, block_zones_element=None, tolerance=0.01, angle_tolerance=1.0
):
    """Generate an DsbXML Element object of a Zone for a honeybee Room.

    The resulting Element has all constituent geometry (Faces, Apertures, Doors).

    Args:
        room: A honeybee Room for which an DsbXML ElementTree object will be returned.
        block_zones_element: An optional XML Element for BuildingBlock Zones
            to which the generated zone object will be added. If None, a new
            XML Element will be used instead.
        tolerance: The absolute tolerance with which the Room geometry will
            be evaluated. (Default: 0.01, suitable for objects in meters).
        angle_tolerance: The angle tolerance at which the geometry will
            be evaluated in degrees. (Default: 1 degree).
    """
    # create the zone root
    is_extrusion = room.is_extrusion(tolerance, angle_tolerance)
    zone_id_attr = {
        'parentZoneHandle': room.identifier,
        'inheritedZoneHandle': room.identifier,
        'planExtrusion': str(is_extrusion),
        'innerSurfaceMode': 'Deflation'
    }
    zone_root = ET.SubElement(block_zones_element, 'Zone', zone_id_attr) \
        if block_zones_element is not None else ET.Element('Zone', zone_id_attr)
    # create the body of the room
    # add the surfaces

    return zone_root


def model_to_dsbxml_element(model):
    """Generate an DsbXML Element object for a honeybee Model.

    The resulting Element has all geometry (Rooms, Faces, Apertures, Doors, Shades).

    Args:
        model: A honeybee Model for which an DsbXML ElementTree object will be returned.
    """
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
    # convert identifiers to integers as this is the only ID format used by DesignBuilder
    model.shade_meshes_to_shades()
    model.reset_ids_to_integers(start_integer=100)
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
    xml_site = ET.SubElement(xml_root, 'Site', handle=model.identifier, count='1')
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

    # translate each block to dsbXML; including all geometry

    return xml_root


def model_to_dsbxml(model, program_name=None):
    """Generate an DsbXML string for a Model.

    The resulting string will include all geometry (Rooms, Faces, Apertures,
    Doors, Shades), all fully-detailed constructions + materials, all fully-detailed
    schedules, and the room properties. It will also include the simulation
    parameters. Essentially, the string includes everything needed to simulate
    the model.

    Args:
        model: A honeybee Model for which an DsbXML ElementTree object will be returned.
        program_name: Optional text to set the name of the software that will
            appear under a comment in the XML to identify where it is being exported
            from. This can be set things like "Ladybug Tools" or "Pollination"
            or some other software in which this DsbXML export capability is being
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

        # create the DsbXML ElementTree for the model
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
