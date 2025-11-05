# coding=utf-8
"""Methods to write Honeybee core objects to dsbXML."""
import datetime
from copy import deepcopy
import xml.etree.ElementTree as ET

from ladybug_geometry.geometry3d import Face3D
from honeybee.typing import clean_string
from honeybee.facetype import RoofCeiling, AirBoundary
from honeybee.boundarycondition import Surface
from honeybee.aperture import Aperture
from honeybee.room import Room

DESIGNBUILDER_VERSION = '2025.1.0.085'
HANDLE_COUNTER = 1  # counter used to generate unique handles when necessary


def sub_face_to_dsbxml_element(sub_face, surface_element=None):
    """Generate an dsbXML Opening Element object from a honeybee Aperture or Door.

    Args:
        sub_face: A honeybee Aperture or Door for which an dsbXML Opening Element
            object will be returned.
        surface_element: An optional XML Element for the Surface to which the
            generated opening object will be added. If None, a new XML Element
            will be generated. Note that this Surface element should have a
            Openings tag already created within it.
    """
    # create the Opening element
    open_type = 'Window' if isinstance(sub_face, Aperture) else 'Door'
    if surface_element is not None:
        surfaces_element = surface_element.find('Openings')
        xml_sub_face = ET.SubElement(surfaces_element, 'Opening', type=open_type)
        obj_ids = surface_element.find('ObjectIDs')
        block_handle = obj_ids.get('buildingBlockHandle')
        zone_handle = obj_ids.get('zoneHandle')
        surface_index = obj_ids.get('surfaceIndex')
    else:
        xml_sub_face = ET.Element('Opening', type=open_type)
        block_handle, zone_handle, surface_index = '-1', '-1', '0'

    # add the vertices for the geometry
    xml_sub_geo = ET.SubElement(xml_sub_face, 'Polygon', auxiliaryType='-1')
    _object_ids(xml_sub_geo, '-1', '0', str(block_handle), str(zone_handle), surface_index)
    xml_sub_pts = ET.SubElement(xml_sub_geo, 'Vertices')
    for pt in sub_face.geometry.boundary:
        xml_point = ET.SubElement(xml_sub_pts, 'Point3D')
        xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
    xml_sub_holes = ET.SubElement(xml_sub_geo, 'PolygonHoles')
    if sub_face.geometry.has_holes:
        flip_plane = sub_face.geometry.flip()  # flip to make holes clockwise
        for hole in sub_face.geometry.holes:
            hole_face = Face3D(hole, plane=flip_plane)
            xml_sub_hole = ET.SubElement(xml_sub_holes, 'PolygonHole')
            _object_ids(xml_sub_geo, sub_face.identifier, '0',
                        str(block_handle), str(zone_handle), surface_index)
            xml_sub_hole_pts = ET.SubElement(xml_sub_hole, 'Vertices')
            for pt in hole_face:
                xml_point = ET.SubElement(xml_sub_hole_pts, 'Point3D')
                xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)

    # add other required but usually empty tags
    xml_sf_attr = ET.SubElement(xml_sub_face, 'Attributes')
    xml_sf_name = ET.SubElement(xml_sf_attr, 'Attribute', key='Title')
    xml_sf_name.text = str(sub_face.display_name)
    ET.SubElement(xml_sub_face, 'SegmentList')
    return xml_sub_face


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
            be evaluated in degrees. This is needed to determine whether to
            write roof faces as flat or pitched. (Default: 1 degree).
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
        'alpha': str(face.geometry.azimuth),
        'phi': str(face.geometry.altitude),
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
    face_obj_ids = _object_ids(xml_face, face.identifier, '0', block_handle,
                               zone_handle, str(dsb_face_i))
    if face.user_data is None:
        face.user_data = {'dsb_face_i': str(dsb_face_i)}
    else:
        face.user_data['dsb_face_i'] = str(dsb_face_i)

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
        sub_face_to_dsbxml_element(ap, xml_face)
    for dr in face.doors:
        sub_face_to_dsbxml_element(dr, xml_face)
    # remove the surface handles now that the openings no longer need them
    face_obj_ids.set('zoneHandle', '-1')
    face_obj_ids.set('surfaceIndex', '-1')

    # add the adjacency information
    # TODO: consider refactoring so that coplanar faces of the same type are one face
    xml_face_adjs = ET.SubElement(xml_face, 'Adjacencies')
    xml_face_adj = ET.SubElement(xml_face_adjs, 'Adjacency',
                                 type=face_type, adjacencyDistance='0.000')
    if isinstance(face.boundary_condition, Surface):
        adj_face, adj_room = face.boundary_condition.boundary_condition_objects
        _object_ids(xml_face_adj, '-1', '-1', '-1', adj_room, adj_face)
        # TODO: write a face index in the zone XML instead of the face handle
    else:  # add a meaningless ID object
        _object_ids(xml_face_adj, '-1')
    xml_adj_geos = ET.SubElement(xml_face_adj, 'AdjacencyPolygonList')
    xml_adj_geo = ET.SubElement(xml_adj_geos, 'Polygon', auxiliaryType='-1')
    if isinstance(face.boundary_condition, Surface):
        _object_ids(xml_adj_geo, '-1')  # add a meaningless ID object
    else:  # add an ID object referencing the self
        _object_ids(xml_adj_geo, '-1', '0',
                    str(block_handle), str(zone_handle), str(dsb_face_i))
    xml_adj_pts = ET.SubElement(xml_adj_geo, 'Vertices')
    for pt in face.geometry.boundary:
        xml_point = ET.SubElement(xml_adj_pts, 'Point3D')
        xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
    xml_holes = ET.SubElement(xml_adj_pts, 'PolygonHoles')
    if face.geometry.has_holes:
        flip_plane = face.geometry.flip()  # flip to make holes clockwise
        for hole, hole_i in zip(face.geometry.holes, hole_is):
            hole_face = Face3D(hole, plane=flip_plane)
            xml_hole = ET.SubElement(xml_holes, 'PolygonHole')
            if isinstance(face.boundary_condition, Surface):
                _object_ids(xml_hole, '-1')  # add a meaningless ID object
            else:  # add an ID object referencing the self
                _object_ids(xml_hole, '-1', '0', str(block_handle), zone_handle, hole_i)
            xml_hole_pts = ET.SubElement(xml_hole, 'Vertices')
            for pt in hole_face:
                xml_point = ET.SubElement(xml_hole_pts, 'Point3D')
                xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)

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
    # create the zone element
    is_extrusion = room.is_extrusion(tolerance, angle_tolerance)
    zone_id_attr = {
        'parentZoneHandle': room.identifier,
        'inheritedZoneHandle': room.identifier,
        'planExtrusion': str(is_extrusion),
        'innerSurfaceMode': 'Approximate'  # TODO: eventually change to deflation
    }
    if block_element is not None:
        block_zones_element = block_element.find('Zones')
        xml_zone = ET.SubElement(block_zones_element, 'Zone', zone_id_attr)
        obj_ids = block_element.find('ObjectIDs')
        block_handle = obj_ids.get('handle')
    else:
        xml_zone = ET.Element('Zone', zone_id_attr)
        block_handle = '-1'

    # create the body of the room using the polyhedral vertices
    hgt = round(room.max.z - room.min.z, 4)
    xml_body = ET.SubElement(
        xml_zone, 'Body', volume=str(room.volume), extrusionHeight=str(hgt))
    _object_ids(xml_body, room.identifier, '0', block_handle)
    xml_vertices = ET.SubElement(xml_body, 'Vertices')
    for pt in room.geometry.vertices:
        xml_point = ET.SubElement(xml_vertices, 'Point3D')
        xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)

    # add the surfaces
    xml_faces = ET.SubElement(xml_body, 'Surfaces')
    for i, face in enumerate(room.faces):
        face_to_dsbxml_element(face, xml_body, i, angle_tolerance)

    # add the other body attributes
    ET.SubElement(xml_body, 'VoidPerimeterList')
    xml_room_attr = ET.SubElement(xml_body, 'Attributes')
    xml_room_name = ET.SubElement(xml_room_attr, 'Attribute', key='Title')
    xml_room_name.text = str(room.display_name)
    if room.user_data is not None and '__identifier__' in room.user_data:
        xml_room_id = ET.SubElement(xml_room_attr, 'Attribute', key='ID')
        xml_room_id.text = room.user_data['__identifier__']

    # add an inner surface body that is a copy of the body
    # TODO: consider offsetting the room polyface inwards to create this object
    xml_in_body_section = ET.SubElement(xml_zone, 'InnerSurfaceBody')
    xml_in_body = ET.SubElement(
        xml_in_body_section, 'Body', volume=str(room.volume), extrusionHeight=str(hgt))
    _object_ids(xml_in_body, room.identifier, '0', block_handle)
    xml_in_vertices = ET.SubElement(xml_in_body, 'Vertices')
    for pt in room.geometry.vertices:
        xml_point = ET.SubElement(xml_in_vertices, 'Point3D')
        xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
    xml_in_faces = ET.SubElement(xml_in_body, 'Surfaces')
    for xml_face in xml_faces:
        in_face = ET.SubElement(xml_in_faces, 'Surface', xml_face.attrib)
        obj_ids = xml_face.find('ObjectIDs')
        copied_obj_ids = deepcopy(obj_ids)
        in_face.append(copied_obj_ids)
        pt_i = xml_face.find('VertexIndices')
        copied_pt_i = deepcopy(pt_i)
        in_face.append(copied_pt_i)
        hole_i = xml_face.find('HoleIndices')
        copied_hole_i = deepcopy(hole_i)
        in_face.append(copied_hole_i)
        ET.SubElement(in_face, 'Openings')
        ET.SubElement(in_face, 'Adjacencies')
        ET.SubElement(in_face, 'Attributes')
    ET.SubElement(xml_in_body, 'VoidPerimeterList')
    ET.SubElement(xml_in_body, 'Attributes')

    return xml_zone


def room_group_to_dsbxml_block(
    room_group, block_handle, building_element=None, block_name=None,
    tolerance=0.01, angle_tolerance=1.0
):
    """Generate an dsbXML BuildingBlock Element object for a list of honeybee Rooms.

    The resulting Element has all geometry (Rooms, Faces, Apertures, Doors, Shades).

    Args:
        room_group: A list of honeybee Room objects  for which an dsbXML
            BuildingBlock Element object will be returned. Note that these rooms
            must form a contiguous volume across their adjacencies for the
            resulting block to be valid.
        block_handle: An integer for the handle of the block. This must be unique
            within the larger model.
        building_element: An optional XML Element for the Building to which the
            generated block object will be added. If None, a new XML Element
            will be generated. Note that this Building element should
            have a BuildingBlocks tag already created within it.
        tolerance: The absolute tolerance with which the Room geometry will
            be evaluated. (Default: 0.01, suitable for objects in meters).
        angle_tolerance: The angle tolerance at which the geometry will
            be evaluated in degrees. (Default: 1 degree).
    """
    global HANDLE_COUNTER  # declare that we will edit the global variable
    # get a room representing the fully-joined volume to be used for the block body
    block_room = room_group[0].duplicate() if len(room_group) == 1 else \
        Room.join_adjacent_rooms(room_group, tolerance)[0]
    block_room.identifier = str(HANDLE_COUNTER)
    HANDLE_COUNTER += 1

    # create the block element
    is_extrusion = block_room.is_extrusion(tolerance, angle_tolerance)
    block_type = 'Plan extrusion' if is_extrusion else 'General'
    hgt = round(block_room.max.z - block_room.min.z, 4)
    block_id_attr = {
        'type': block_type,
        'height': str(hgt),
        'roofSlope': '30.0000',
        'roofOverlap': '0.0000',
        'roofType': 'Gable',
        'wallSlope': '80.0000'
    }
    if building_element is not None:
        blocks_element = building_element.find('BuildingBlocks')
        xml_block = ET.SubElement(blocks_element, 'BuildingBlock', block_id_attr)
    else:
        xml_block = ET.Element('Zone', block_id_attr)

    # add the extra attributes that are typically empty
    _object_ids(xml_block, str(block_handle), '0')
    ET.SubElement(xml_block, 'ComponentBlocks')
    ET.SubElement(xml_block, 'CFDFans')
    ET.SubElement(xml_block, 'AssemblyInstances')
    ET.SubElement(xml_block, 'ProfileOutlines')
    ET.SubElement(xml_block, 'VoidBodies')

    # add the rooms to the block
    ET.SubElement(xml_block, 'Zones')
    for room in room_group:
        room_to_dsbxml_element(room, xml_block, tolerance, angle_tolerance)

    # process the faces of the block room to be formatted for a body
    for f in block_room.faces:
        for room in room_group:
            for f2 in room:
                if f.geometry.is_centered_adjacent(f2.geometry, tolerance):
                    f.user_data = {
                        'zone_handle': room.identifier,
                        'surface_index': f2.user_data['dsb_face_i']
                    }
                    break
        f.remove_sub_faces()
        f.identifier = str(HANDLE_COUNTER)
        HANDLE_COUNTER += 1

    # create the body of the block using the polyhedral vertices
    xml_profile = ET.SubElement(
        xml_block, 'ProfileBody', elementSlope='0.0000', roofOverlap='0.0000')
    xml_body = ET.SubElement(
        xml_profile, 'Body', volume=str(block_room.volume), extrusionHeight=str(hgt))
    _object_ids(xml_body, block_room.identifier, '0', str(block_handle))
    xml_vertices = ET.SubElement(xml_body, 'Vertices')
    for pt in block_room.geometry.vertices:
        xml_point = ET.SubElement(xml_vertices, 'Point3D')
        xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
    ET.SubElement(xml_body, 'Surfaces')
    for i, face in enumerate(block_room.faces):
        face_xml = face_to_dsbxml_element(face, xml_body, i, angle_tolerance)
        face_xml.set('defaultOpenings', 'True')
        face_xml.set('thickness', '0.1')
        f_obj_ids_xml = face_xml.find('ObjectIDs')
        f_obj_ids_xml.set('zoneHandle', '-1')
        f_obj_ids_xml.set('surfaceIndex', '-1')
        adjs_xml = face_xml.find('Adjacencies')
        adj_xml = adjs_xml.find('Adjacency')
        in_adj_ids = adj_xml.find('ObjectIDs')
        in_adj_ids.set('handle', '-1')
        in_adj_ids.set('buildingHandle', '-1')
        in_adj_ids.set('buildingBlockHandle', '-1')
        in_adj_ids.set('zoneHandle', face.user_data['zone_handle'])
        in_adj_ids.set('surfaceIndex', face.user_data['surface_index'])
        polys_xml = adj_xml.find('AdjacencyPolygonList')
        for poly_xml in polys_xml:
            out_adj_ids = poly_xml.find('ObjectIDs')
            out_adj_ids.set('handle', '-1')
            out_adj_ids.set('buildingHandle', '-1')
            out_adj_ids.set('buildingBlockHandle', '-1')
            out_adj_ids.set('zoneHandle', '-1')
            out_adj_ids.set('surfaceIndex', '-1')

    # add the perimeter to the block
    xml_perim = ET.SubElement(xml_block, 'Perimeter')
    perim_geo = Room.grouped_horizontal_boundary(room_group, tolerance=tolerance)
    if len(perim_geo) != 0:
        perim_geo = perim_geo[0]
        xml_perim_geo = ET.SubElement(xml_perim, 'Polygon', auxiliaryType='-1')
        perim_handle = str(HANDLE_COUNTER)
        HANDLE_COUNTER += 1
        _object_ids(xml_perim_geo, perim_handle, '0',
                    str(block_handle), block_room.identifier)
        xml_perim_pts = ET.SubElement(xml_perim_geo, 'Vertices')
        for pt in perim_geo.boundary:
            xml_point = ET.SubElement(xml_perim_pts, 'Point3D')
            xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
        xml_holes = ET.SubElement(xml_perim_pts, 'PolygonHoles')
        if perim_geo.has_holes:
            flip_plane = perim_geo.flip()  # flip to make holes clockwise
            for hole in perim_geo.holes:
                hole_face = Face3D(hole, plane=flip_plane)
                xml_hole = ET.SubElement(xml_holes, 'PolygonHole')
                _object_ids(xml_hole, '-1')
                xml_hole_pts = ET.SubElement(xml_hole, 'Vertices')
                for pt in hole_face:
                    xml_point = ET.SubElement(xml_hole_pts, 'Point3D')
                    xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
    else:
        msg = 'Failed to calculate perimeter around block: {}'.format(block_name)
        print(msg)

    # TODO: add internal partitions to the block
    ET.SubElement(xml_block, 'InternalPartitions')

    # add the other properties that are usually empty
    ET.SubElement(xml_body, 'VoidPerimeterList')
    ET.SubElement(xml_body, 'Attributes')
    ET.SubElement(xml_block, 'BaseProfileBody')
    xml_block_attr = ET.SubElement(xml_block, 'Attributes')
    xml_block_name = ET.SubElement(xml_block_attr, 'Attribute', key='Title')
    xml_block_name.text = block_name if block_name is not None \
        else 'Block {}'.format(block_handle)

    # TODO: add the perimeter for the block
    return xml_block


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
    # erase room user data and use it to store attributes for later
    for room in model.rooms:
        room.user_data = {'__identifier__': room.identifier}

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

    # give unique integers to each of the building blocks and faces
    HANDLE_COUNTER = len(block_rooms) + 1
    # convert identifiers to integers as this is the only ID format used by DesignBuilder
    HANDLE_COUNTER = model.reset_ids_to_integers(start_integer=HANDLE_COUNTER)
    HANDLE_COUNTER += 1

    # translate each block to dsbXML; including all geometry
    ET.SubElement(xml_bldg, 'BuildingBlocks')
    for i, (room_group, block_name) in enumerate(zip(block_rooms, block_names)):
        room_group_to_dsbxml_block(room_group, i + 1, xml_bldg, block_name)

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


def sub_face_to_dsbxml(sub_face):
    """Generate an dsbXML Opening string from a honeybee Aperture or Door.

    Args:
        sub_face: A honeybee Aperture or Door for which an dsbXML Opening XML
            string will be returned.
    """
    xml_root = sub_face_to_dsbxml_element(sub_face)
    ET.indent(xml_root)
    return ET.tostring(xml_root, encoding='unicode')


def face_to_dsbxml(face):
    """Generate an dsbXML Surface string from a honeybee Face.

    The resulting string has all constituent geometry (Apertures, Doors).

    Args:
        face: A honeybee Face for which an dsbXML Surface string object will
            be returned.
    """
    xml_root = face_to_dsbxml_element(face)
    ET.indent(xml_root)
    return ET.tostring(xml_root, encoding='unicode')


def room_to_dsbxml(room):
    """Generate an dsbXML Zone string object for a honeybee Room.

    The resulting string has all constituent geometry (Faces, Apertures, Doors).

    Args:
        room: A honeybee Room for which an dsbXML Zone string object will be returned.
    """
    xml_root = room_to_dsbxml_element(room)
    ET.indent(xml_root)
    return ET.tostring(xml_root, encoding='unicode')


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
