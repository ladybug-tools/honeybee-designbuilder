# coding=utf-8
"""Methods to write Honeybee core objects to dsbXML."""
import os
import math
import datetime
from copy import deepcopy
import xml.etree.ElementTree as ET

from ladybug_geometry.geometry2d import Point2D, Polygon2D
from ladybug_geometry.geometry3d import Vector3D, Point3D, Face3D, Polyface3D
from honeybee.typing import clean_string
from honeybee.aperture import Aperture
from honeybee.face import Face
from honeybee.room import Room
from honeybee.facetype import Floor, RoofCeiling, AirBoundary, face_types
from honeybee.boundarycondition import Outdoors, Surface, Ground, boundary_conditions
from honeybee_energy.boundarycondition import Adiabatic

DESIGNBUILDER_VERSION = '2025.1.0.085'
HANDLE_COUNTER = 1  # counter used to generate unique handles when necessary


def shade_to_dsbxml_element(shade, building_element=None):
    """Generate an dsbXML Plane Element object from a honeybee Shade.

    Args:
        shade: A honeybee Shade for which an dsbXML Plane Element object will
            be returned.
        building_element: An optional XML Element for the Building to which the
            generated plane object will be added. If None, a new XML Element
            will be generated. Note that this Building element should have a
            Planes tag already created within it.
    """
    # create the Plane element
    if building_element is not None:
        planes_element = building_element.find('Planes')
        xml_shade = ET.SubElement(planes_element, 'Plane', type='2')
    else:
        xml_shade = ET.Element('Plane', type='2')
    # add the vertices for the geometry
    xml_geo = ET.SubElement(xml_shade, 'Polygon', auxiliaryType='-1')
    _object_ids(xml_geo, shade.identifier, '0')
    xml_sub_pts = ET.SubElement(xml_geo, 'Vertices')
    for pt in shade.geometry.boundary:
        xml_point = ET.SubElement(xml_sub_pts, 'Point3D')
        xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
    xml_holes = ET.SubElement(xml_geo, 'PolygonHoles')
    if shade.geometry.has_holes:
        flip_plane = shade.geometry.plane.flip()  # flip to make holes clockwise
        for hole in shade.geometry.holes:
            hole_face = Face3D(hole, plane=flip_plane)
            xml_sub_hole = ET.SubElement(xml_holes, 'PolygonHole')
            _object_ids(xml_geo, shade.identifier, '0')
            xml_sub_hole_pts = ET.SubElement(xml_sub_hole, 'Vertices')
            for pt in hole_face:
                xml_point = ET.SubElement(xml_sub_hole_pts, 'Point3D')
                xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
    # add the name of the shade
    xml_shd_attr = ET.SubElement(xml_shade, 'Attributes')
    xml_shd_name = ET.SubElement(xml_shd_attr, 'Attribute', key='Title')
    xml_shd_name.text = str(shade.display_name)
    return xml_shade


def shade_mesh_to_dsbxml_element(shade_mesh, building_element=None, reset_counter=True):
    """Generate an dsbXML Planes Element object from a honeybee ShadeMesh.

    Args:
        shade_mesh: A honeybee ShadeMesh for which an dsbXML Planes Element
            object will be returned.
        building_element: An optional XML Element for the Building to which the
            generated objects will be added. If None, a new XML Element
            will be generated. Note that this Building element should have a
            Planes tag already created within it.
        reset_counter: A boolean to note whether the global counter for unique
            handles should be reset after the method is run. (Default: True).
    """
    global HANDLE_COUNTER  # declare that we will edit the global variable
    # create the Planes element
    xml_planes = building_element.find('Planes') \
        if building_element is not None else ET.Element('Planes')
    # add a plane element for each mesh face
    for i, face in enumerate(shade_mesh.geometry.face_vertices):
        xml_shade = ET.SubElement(xml_planes, 'Plane', type='2')
        xml_geo = ET.SubElement(xml_shade, 'Polygon', auxiliaryType='-1')
        _object_ids(xml_geo, str(HANDLE_COUNTER), '0')
        HANDLE_COUNTER += 1
        xml_sub_pts = ET.SubElement(xml_geo, 'Vertices')
        for pt in face:
            xml_point = ET.SubElement(xml_sub_pts, 'Point3D')
            xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
        ET.SubElement(xml_geo, 'PolygonHoles')
        # add the name of the shade
        xml_shd_attr = ET.SubElement(xml_shade, 'Attributes')
        xml_shd_name = ET.SubElement(xml_shd_attr, 'Attribute', key='Title')
        xml_shd_name.text = '{} {}'.format(shade_mesh.display_name, i)
    if reset_counter:  # reset the counter back to 1 if requested
        HANDLE_COUNTER = 1
    return xml_planes


def sub_face_to_dsbxml_element(sub_face, surface_element=None, sub_face_type=None):
    """Generate an dsbXML Opening Element object from a honeybee Aperture or Door.

    Args:
        sub_face: A honeybee Aperture or Door for which an dsbXML Opening Element
            object will be returned.
        surface_element: An optional XML Element for the Surface to which the
            generated opening object will be added. If None, a new XML Element
            will be generated. Note that this Surface element should have a
            Openings tag already created within it.
        sub_face_type: Text for a particular type of Honeybee sub-face object to
            be written as a DesignBuilder Surface. This is useful in cases of
            modeling radiant ceiling panels or spandrel panels, which have a
            special sub-Surface object used to represent them in DesignBuilder
            instead of splitting the parent Face.
    """
    # determine the opening type
    if isinstance(sub_face, Aperture):
        open_type = 'Window'
    elif sub_face_type == 'OverheadDoors':
        open_type = 'Surface' if sub_face.has_parent and \
            isinstance(sub_face.parent.type, RoofCeiling) else 'Door'
    elif sub_face_type == 'GlassDoors':
        open_type = 'Surface' if sub_face.is_glass else 'Door'
    elif sub_face_type == 'Doors':
        open_type = 'Surface'
    else:
        open_type = 'Door'

    # create the Opening element
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
        flip_plane = sub_face.geometry.plane.flip()  # flip to make holes clockwise
        for hole in sub_face.geometry.holes:
            hole_face = Face3D(hole, plane=flip_plane)
            xml_sub_hole = ET.SubElement(xml_sub_holes, 'PolygonHole')
            _object_ids(xml_sub_geo, '-1', '0',
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
    face, zone_body_element=None, zone_face_indices=None, adjacency_faces=None,
    sub_face_type=None, tolerance=0.01, angle_tolerance=1.0, reset_counter=True
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
        zone_face_indices: An optional tuple of integers for the vertex indices
            of the face in the parent Room Polyface3D. If None, some placeholder
            indices will be generated. (Default: None).
        adjacency_faces: An optional list of Honeybee Faces for sub-elements
            of the input face that specify adjacencies to multiple other
            Faces. When specified, these adjacency faces should be coplanar
            to the input face and should together completely fill its area.
            If None, it will be assumed that the face in dsbXML should
            have only one adjacency. (Default: None).
        sub_face_type: Text for a particular type of Honeybee sub-face object to
            be written as a DesignBuilder Surface. This is useful in cases of
            modeling radiant ceiling panels or spandrel panels, which have a
            special sub-Surface object used to represent them in DesignBuilder
            instead of splitting the parent Face.
        tolerance: The absolute tolerance with which the Room geometry will
            be evaluated. (Default: 0.01, suitable for objects in meters).
        angle_tolerance: The angle tolerance at which the geometry will
            be evaluated in degrees. This is needed to determine whether to
            write roof faces as flat or pitched. (Default: 1 degree).
        reset_counter: A boolean to note whether the global counter for unique
            handles should be reset after the method is run. (Default: True).
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
        'adjacentPartitionHandle': '-1',
        'thickness': '0.0'  # TODO: make better for adjacency
    }
    if face.user_data is not None and 'partition_handle' in face.user_data:
        face_id_attr['adjacentPartitionHandle'] = face.user_data['partition_handle']

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
    if adjacency_faces is not None:
        for a_face in adjacency_faces:
            if a_face.user_data is None:
                a_face.user_data = {'dsb_face_i': str(dsb_face_i)}
            else:
                a_face.user_data['dsb_face_i'] = str(dsb_face_i)

    # add the vertices that define the Face
    if zone_face_indices is None:
        face_indices = [tuple(range(len(face.geometry.boundary)))]
        if face.geometry.has_holes:
            counter = len(face_indices[0])
            for hole in face.geometry.holes:
                face_indices.append(tuple(range(counter, counter + len(hole))))
                counter += len(hole)
    else:
        face_indices = zone_face_indices
    xml_pt_i = ET.SubElement(xml_face, 'VertexIndices')
    xml_pt_i.text = '; '.join([str(i) for i in face_indices[0]])

    # add the holes as duplicated Surfaces
    xml_hole_i = ET.SubElement(xml_face, 'HoleIndices')
    hole_is = None
    if len(face_indices) > 1:  # we have holes to add
        hole_is = []
        for j, (hole_i, hole) in enumerate(zip(face_indices[1:], face.geometry.holes)):
            hole_id_attr = face_id_attr.copy()
            hole_id_attr['type'] = 'Hole'
            hole_geo = Face3D(hole)
            hole_id_attr['area'] = str(hole_geo.area)
            xml_hole = ET.SubElement(surfaces_element, 'Surface', hole_id_attr)
            _object_ids(xml_hole, str(HANDLE_COUNTER), '0', block_handle)
            HANDLE_COUNTER += 1
            xml_hole_pt_i = ET.SubElement(xml_hole, 'VertexIndices')
            xml_hole_pt_i.text = '; '.join([str(i) for i in hole_i])
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
    xml_bc = ET.SubElement(xml_face_attr, 'Attribute', key='AdjacentCondition')
    if isinstance(face.boundary_condition, Outdoors):
        xml_bc.text = '2-Not adjacent to ground'
    elif isinstance(face.boundary_condition, Ground):
        xml_bc.text = '3-Adjacent to ground'
    elif isinstance(face.boundary_condition, Adiabatic):
        xml_bc.text = '4-Adiabatic'
    else:
        xml_bc.text = '1-Auto'

    # add any openings if they exist
    ET.SubElement(xml_face, 'Openings')
    for ap in face.apertures:
        sub_face_to_dsbxml_element(ap, xml_face, sub_face_type=sub_face_type)
    for dr in face.doors:
        sub_face_to_dsbxml_element(dr, xml_face, sub_face_type=sub_face_type)
    # remove the surface handles now that the openings no longer need them
    face_obj_ids.set('zoneHandle', '-1')
    face_obj_ids.set('surfaceIndex', '-1')

    # add the adjacency information
    adjacency_faces = [face] if adjacency_faces is None else adjacency_faces
    xml_face_adjs = ET.SubElement(xml_face, 'Adjacencies')
    for adj_f_obj in adjacency_faces:
        xml_face_adj = ET.SubElement(xml_face_adjs, 'Adjacency',
                                     type=face_type, adjacencyDistance='0.000')
        if isinstance(adj_f_obj.boundary_condition, Surface):
            adj_face, adj_room = adj_f_obj.boundary_condition.boundary_condition_objects
            _object_ids(xml_face_adj, '-1', '-1', '-1', adj_room, adj_face)
        else:  # add a ID object with all -1 for outdoors
            _object_ids(xml_face_adj, '-1')
        xml_adj_geos = ET.SubElement(xml_face_adj, 'AdjacencyPolygonList')
        xml_adj_geo = ET.SubElement(xml_adj_geos, 'Polygon', auxiliaryType='-1')
        if isinstance(adj_f_obj.boundary_condition, Surface):
            _object_ids(xml_adj_geo, '-1')  # add a meaningless ID object
        else:  # add an ID object referencing the self
            _object_ids(xml_adj_geo, '-1', '0',
                        str(block_handle), str(zone_handle), str(dsb_face_i))
        xml_adj_pts = ET.SubElement(xml_adj_geo, 'Vertices')
        for pt in adj_f_obj.geometry.boundary:
            xml_point = ET.SubElement(xml_adj_pts, 'Point3D')
            xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
        xml_holes = ET.SubElement(xml_adj_geo, 'PolygonHoles')
        if adj_f_obj.geometry.has_holes:
            hole_inds = hole_is if hole_is is not None else [-1] * len(adj_f_obj.geometry.holes)
            for hole, hole_i in zip(adj_f_obj.geometry.holes, hole_inds):
                xml_hole = ET.SubElement(xml_holes, 'PolygonHole')
                if isinstance(adj_f_obj.boundary_condition, Surface):
                    _object_ids(xml_hole, '-1')  # add a meaningless ID object
                else:  # add an ID object referencing the self
                    _object_ids(xml_hole, '-1', '0', str(block_handle), zone_handle, str(hole_i))
                xml_hole_pts = ET.SubElement(xml_hole, 'Vertices')
                for pt in hole:
                    xml_point = ET.SubElement(xml_hole_pts, 'Point3D')
                    xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
    if reset_counter:  # reset the counter back to 1 if requested
        HANDLE_COUNTER = 1
    return xml_face


def room_to_dsbxml_element(
    room, block_element=None, sub_face_type=None,
    tolerance=0.01, angle_tolerance=1.0, reset_counter=True
):
    """Generate an dsbXML Zone Element object for a honeybee Room.

    The resulting Element has all constituent geometry (Faces, Apertures, Doors).

    Args:
        room: A honeybee Room for which an dsbXML Zone Element object will be returned.
        block_element: An optional XML Element for the BuildingBlock to which the
            generated zone object will be added. If None, a new XML Element
            will be generated. Note that this BuildingBlock element should
            have a Zones tag already created within it.
        sub_face_type: Text for a particular type of Honeybee sub-face object to
            be written as a DesignBuilder Surface. This is useful in cases of
            modeling radiant ceiling panels or spandrel panels, which have a
            special sub-Surface object used to represent them in DesignBuilder
            instead of splitting the parent Face.
        tolerance: The absolute tolerance with which the Room geometry will
            be evaluated. (Default: 0.01, suitable for objects in meters).
        angle_tolerance: The angle tolerance at which the geometry will
            be evaluated in degrees. (Default: 1 degree).
        reset_counter: A boolean to note whether the global counter for unique
            handles should be reset after the method is run. (Default: True).
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

    # rebuild the faces with holes if any are found
    if any(f.geometry.has_holes for f in room.faces):
        rebuilt_face_3ds = []
        for face in room.faces:
            if face.geometry.has_holes:
                flat_pt_face = Face3D(
                    face.geometry.vertices, plane=face.geometry.plane
                )
                rebuilt_face = flat_pt_face.separate_boundary_and_holes(tolerance)
                face._geometry = rebuilt_face
                rebuilt_face_3ds.append(rebuilt_face)
            else:
                rebuilt_face_3ds.append(face.geometry)
        room._geometry = Polyface3D.from_faces(rebuilt_face_3ds, tolerance)
        if not room._geometry.is_solid:
            room._geometry = room._geometry.merge_overlapping_edges(tolerance)

    # determine whether the room has multiple floor faces to merge
    room_faces, room_geometry = room.faces, room.geometry
    face_adjs = [None] * len(room_faces)
    merge_faces = room.floors
    if len(merge_faces) > 1:
        if room.properties.designbuilder.floor_geometry is not None:
            floor_geos = [room.properties.designbuilder.floor_geometry]
        else:
            f_geos = [f.geometry for f in merge_faces]
            floor_geos = Face3D.join_coplanar_faces(f_geos, tolerance)
        if len(floor_geos) != 0 and len(floor_geos) < len(merge_faces):  # faces were merged
            room_faces, face_adjs = [], []
            apertures, doors = [], []
            for f in merge_faces:
                apertures.extend(f._apertures)
                doors.extend(f._doors)
            for new_geo in floor_geos:
                if len(floor_geos) == 1:
                    prop_fs = merge_faces
                else:  # determine which of the faces corresponds to the merged one
                    prop_fs = []
                    for f in merge_faces:
                        f_pt = f._point_on_face(tolerance)
                        if new_geo.is_point_on_face(f_pt, tolerance):
                            prop_fs.append(f)
                prop_f = prop_fs[0]
                fbc = boundary_conditions.outdoors
                nf = Face(prop_f.identifier, new_geo, prop_f.type, fbc)
                for ap in apertures:
                    if nf.geometry.is_sub_face(ap.geometry, tolerance, angle_tolerance):
                        nf.add_aperture(ap)
                for dr in doors:
                    if nf.geometry.is_sub_face(dr.geometry, tolerance, angle_tolerance):
                        nf.add_door(dr)
                room_faces.append(nf)
                face_adjs.append(prop_fs)
            for f in room.faces:
                if not isinstance(f.type, Floor):
                    room_faces.append(f)
                    face_adjs.append(None)
            room_geometry = Polyface3D.from_faces(
                tuple(face.geometry for face in room_faces), tolerance)
    else:
        floor_geos = [f.geometry for f in merge_faces]

    # create the body of the room using the polyhedral vertices
    hgt = round(room.max.z - room.min.z, 4)
    xml_body = ET.SubElement(
        xml_zone, 'Body', volume=str(room.volume), extrusionHeight=str(hgt))
    _object_ids(xml_body, room.identifier, '0', block_handle)
    xml_vertices = ET.SubElement(xml_body, 'Vertices')
    for pt in room_geometry.vertices:
        xml_point = ET.SubElement(xml_vertices, 'Point3D')
        xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)

    # add the surfaces
    xml_faces = ET.SubElement(xml_body, 'Surfaces')
    for face, fi, f_adj in zip(room_faces, room_geometry.face_indices, face_adjs):
        face_to_dsbxml_element(
            face, xml_body, fi, f_adj, sub_face_type,
            tolerance, angle_tolerance, reset_counter=False
        )

    # if the room floor plate has holes, write them in the void perimeter list
    xml_void = ET.SubElement(xml_body, 'VoidPerimeterList')
    for fli, floor_g in enumerate(floor_geos):
        if floor_g.has_holes:
            flip_plane = floor_g.plane.flip()  # flip to make holes clockwise
            for hole in floor_g.holes:
                xml_v_poly = ET.SubElement(xml_void, 'Polygon', auxiliaryType='-1')
                _object_ids(xml_v_poly, '-1', surface=str(fli))
                hole_face = Face3D(hole, plane=flip_plane)
                for pt in hole_face.boundary:
                    xml_point = ET.SubElement(xml_v_poly, 'Point3D')
                    xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)

    # add the other body attributes
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
    for pt in room_geometry.vertices:
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
    in_xml_void = deepcopy(xml_void)
    xml_in_body.append(in_xml_void)
    ET.SubElement(xml_in_body, 'Attributes')
    if reset_counter:  # reset the counter back to 1 if requested
        HANDLE_COUNTER = 1
    return xml_zone


def room_group_to_dsbxml_block(
    room_group, block_handle, building_element=None, block_name=None, sub_face_type=None,
    tolerance=0.01, angle_tolerance=1.0, reset_counter=True
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
        block_name: An optional text string for the name of the block to be written.
        sub_face_type: Text for a particular type of Honeybee sub-face object to
            be written as a DesignBuilder Surface. This is useful in cases of
            modeling radiant ceiling panels or spandrel panels, which have a
            special sub-Surface object used to represent them in DesignBuilder
            instead of splitting the parent Face.
        tolerance: The absolute tolerance with which the Room geometry will
            be evaluated. (Default: 0.01, suitable for objects in meters).
        angle_tolerance: The angle tolerance at which the geometry will
            be evaluated in degrees. (Default: 1 degree).
        reset_counter: A boolean to note whether the global counter for unique
            handles should be reset after the method is run. (Default: True).
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

    # gather horizontal floor boundaries for the rooms
    floor_geos, floor_z_vals, ceil_z_vals, label_pts = [], [], [], []
    for room in room_group:
        if room.properties.designbuilder.floor_geometry is not None:
            flr_geos = [room.properties.designbuilder.floor_geometry]
        else:
            flr_geos = room.horizontal_floor_boundaries(tolerance=tolerance)
        floor_geos.extend(flr_geos)
        floor_z_vals.extend([flr_geo.min.z for flr_geo in flr_geos])
        ceil_z_vals.append(room.max.z)
        # use the floor geometry to determine the room label point
        if len(flr_geos) != 0:
            label_pt = flr_geos[0].center if flr_geos[0].is_convex else \
                flr_geos[0].pole_of_inaccessibility(0.01)
            label_pts.append(label_pt)
        else:
            label_pts.append(room.geometry.center)
    min_z, max_z = min(floor_z_vals), max(ceil_z_vals)

    # join the flat floors of the rooms together to determine internal partitions
    polygons, is_holes = [], []
    for f_geo in floor_geos:
        is_holes.append(False)
        b_poly = Polygon2D(tuple(Point2D(pt.x, pt.y) for pt in f_geo.boundary))
        polygons.append(b_poly)
        if f_geo.has_holes:
            for hole in f_geo.holes:
                is_holes.append(True)
                h_poly = Polygon2D(tuple(Point2D(pt.x, pt.y) for pt in hole))
                polygons.append(h_poly)
    if any(r.properties.designbuilder.floor_geometry is None for r in room_group):
        polygons = [poly.remove_colinear_vertices(tolerance) for poly in polygons]
        polygons = Polygon2D.intersect_polygon_segments(polygons, tolerance)
    face_pts, flat_flr_geos = [], []
    for poly, is_hole in zip(polygons, is_holes):
        pt_3d = [Point3D(pt.x, pt.y, min_z) for pt in poly]
        if not is_hole:
            face_pts.append((pt_3d, []))
        else:
            face_pts[-1][1].append(pt_3d)
    for f_pts in face_pts:
        flat_flr_geos.append(Face3D(f_pts[0], holes=f_pts[1]))
    flr_polyface = Polyface3D.from_faces(flat_flr_geos, tolerance)

    # add internal partitions to the block
    xml_partitions = ET.SubElement(xml_block, 'InternalPartitions')
    part_height = max_z - min_z
    for part_geo in flr_polyface.internal_edges:
        p_min, p_max = part_geo.min, part_geo.max
        p_min = Point2D(p_min.x, p_min.y)
        p_max = Point2D(p_max.x, p_max.y)
        # find the faces associated with the partition
        rel_faces = []
        for room in room_group:
            for face in room:
                f_min, f_max = face.min, face.max
                f_min = Point2D(f_min.x, f_min.y)
                f_max = Point2D(f_max.x, f_max.y)
                if p_min.is_equivalent(f_min, tolerance) and \
                        p_max.is_equivalent(f_max, tolerance):
                    rel_faces.append(face)
        # identify the two faces that coincide with the partition
        match_faces = None
        for i, i_face in enumerate(rel_faces):
            if match_faces is not None:
                break
            if isinstance(i_face.boundary_condition, Surface):
                for o_face in rel_faces[i + 1:]:
                    if isinstance(o_face.boundary_condition, Surface):
                        bc_obj = o_face.boundary_condition.boundary_condition_object
                        if i_face.identifier == bc_obj:
                            match_faces = (i_face, o_face)
                            break
        # create the internal partition object
        if match_faces is not None:
            part_id = str(HANDLE_COUNTER)
            HANDLE_COUNTER += 1
            for face in match_faces:
                if face.user_data is None:
                    face.user_data = {'partition_handle': part_id}
                else:
                    face.user_data['partition_handle'] = part_id
            part_type = 'Virtual' if isinstance(face.type, AirBoundary) else 'Solid'
            part_id_attr = {
                'type': part_type,
                'height': str(part_height),
                'area': str(part_height * part_geo.length),
                'floatingPartition': 'False',
            }
            xml_part = ET.SubElement(xml_partitions, 'InternalPartition', part_id_attr)
            _object_ids(xml_part, part_id, '0', str(block_handle))
            st_pt, end_pt = part_geo.p1, part_geo.p2
            xml_st_pt = ET.SubElement(xml_part, 'StartPoint')
            xml_point = ET.SubElement(xml_st_pt, 'Point3D')
            xml_point.text = '{}; {}; {}'.format(st_pt.x, st_pt.y, st_pt.z)
            xml_end_pt = ET.SubElement(xml_part, 'EndPoint')
            xml_point = ET.SubElement(xml_end_pt, 'Point3D')
            xml_point.text = '{}; {}; {}'.format(end_pt.x, end_pt.y, end_pt.z)

    # add the rooms to the block
    ET.SubElement(xml_block, 'Zones')
    for room, label_pt in zip(room_group, label_pts):
        xml_room = room_to_dsbxml_element(
            room, xml_block, sub_face_type, tolerance, angle_tolerance,
            reset_counter=False
        )
        xml_label = ET.SubElement(xml_room, 'LabelPosition')
        xml_label_pt = ET.SubElement(xml_label, 'Point3D')
        xml_label_pt.text = '{}; {}; {}'.format(label_pt.x, label_pt.y, label_pt.z)

    # process the faces of the block room to be formatted for a body
    for f in block_room.faces:
        face_matched = False
        for room in room_group:
            for f2 in room:
                if f.identifier == f2.identifier:
                    f.user_data = {
                        'zone_handle': room.identifier,
                        'surface_index': f2.user_data['dsb_face_i']
                    }
                    face_matched = True
                    break
            if face_matched:
                break
        else:
            print('Failed to match the block Face: {}'.format(f.display_name))
        f.remove_sub_faces()
        f.identifier = str(HANDLE_COUNTER)
        HANDLE_COUNTER += 1

    # get a version of the block room with coplanar faces merged
    blk_room = block_room.duplicate()
    blk_room.merge_coplanar_faces(tolerance, angle_tolerance)
    face_adjs = []
    for nf in blk_room.faces:
        nf_adj = []
        for of in block_room.faces:
            if nf.identifier == of.identifier:
                nf_adj.append(of)
            else:
                f_pt = of.geometry._point_on_face(tolerance)
                if nf.geometry.is_point_on_face(f_pt, tolerance):
                    nf_adj.append(of)
        if len(nf_adj) != 0:
            face_adjs.append(nf_adj)
        else:
            face_adjs.append(None)

    # create the body of the block using the polyhedral vertices
    xml_profile = ET.SubElement(
        xml_block, 'ProfileBody', elementSlope='0.0000', roofOverlap='0.0000')
    xml_body = ET.SubElement(
        xml_profile, 'Body', volume=str(block_room.volume), extrusionHeight=str(hgt))
    _object_ids(xml_body, block_room.identifier, '0', str(block_handle))
    xml_vertices = ET.SubElement(xml_body, 'Vertices')
    for pt in blk_room.geometry.vertices:
        xml_point = ET.SubElement(xml_vertices, 'Point3D')
        xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, pt.z)
    ET.SubElement(xml_body, 'Surfaces')
    zip_obj = zip(blk_room.faces, blk_room.geometry.face_indices, face_adjs)
    for face, fi, f_adj in zip_obj:
        face_xml = face_to_dsbxml_element(
            face, xml_body, fi, adjacency_faces=f_adj,
            tolerance=tolerance, angle_tolerance=angle_tolerance, reset_counter=False
        )
        face_xml.set('defaultOpenings', 'True')
        face_xml.set('thickness', '0.1')
        f_obj_ids_xml = face_xml.find('ObjectIDs')
        f_obj_ids_xml.set('zoneHandle', '-1')
        f_obj_ids_xml.set('surfaceIndex', '-1')
        adjs_xml = face_xml.find('Adjacencies')
        if f_adj is None:
            f_adj = [face] * len(adjs_xml)
        for adj_xml, af in zip(adjs_xml, f_adj):
            if 'zone_handle' not in af.user_data:
                continue
            adj_xml.set('type', 'Floor')
            in_adj_ids = adj_xml.find('ObjectIDs')
            in_adj_ids.set('handle', '-1')
            in_adj_ids.set('buildingHandle', '-1')
            in_adj_ids.set('buildingBlockHandle', '-1')
            in_adj_ids.set('zoneHandle', af.user_data['zone_handle'])
            in_adj_ids.set('surfaceIndex', af.user_data['surface_index'])
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
            xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, min_z)
        xml_holes = ET.SubElement(xml_perim_geo, 'PolygonHoles')
        if perim_geo.has_holes:
            flip_plane = perim_geo.plane.flip()  # flip to make holes clockwise
            for hole in perim_geo.holes:
                hole_face = Face3D(hole, plane=flip_plane)
                xml_hole = ET.SubElement(xml_holes, 'PolygonHole')
                _object_ids(xml_hole, '-1')
                xml_hole_pts = ET.SubElement(xml_hole, 'Vertices')
                for pt in hole_face:
                    xml_point = ET.SubElement(xml_hole_pts, 'Point3D')
                    xml_point.text = '{}; {}; {}'.format(pt.x, pt.y, min_z)
    else:
        msg = 'Failed to calculate perimeter around block: {}'.format(block_name)
        print(msg)

    # add the other properties that are usually empty
    ET.SubElement(xml_body, 'VoidPerimeterList')
    ET.SubElement(xml_body, 'Attributes')
    ET.SubElement(xml_block, 'BaseProfileBody')
    xml_block_attr = ET.SubElement(xml_block, 'Attributes')
    xml_block_name = ET.SubElement(xml_block_attr, 'Attribute', key='Title')
    xml_block_name.text = block_name if block_name is not None \
        else 'Block {}'.format(block_handle)
    if reset_counter:  # reset the counter back to 1 if requested
        HANDLE_COUNTER = 1
    return xml_block


def model_to_dsbxml_element(model, xml_template='Default', sub_face_type=None):
    """Generate an dsbXML Element object for a honeybee Model.

    The resulting Element has all geometry (Rooms, Faces, Apertures, Doors, Shades).

    Args:
        model: A honeybee Model for which an dsbXML ElementTree object will be returned.
        xml_template: Text for the type of template file to be used to write the
            dsbXML. Different templates contain different amounts of default
            assembly library data, which may be needed in order to import the
            dsbXML into older versions of DesignBuilder. However, this data can
            greatly increase the size of the resulting dsbXML file. Choose from
            the following options.

            * Default - a minimal file that imports into the latest versions
            * Assembly - the Default plus an AssemblyLibrary with typical objects
            * Full - a large file with all libraries that can be imported to version 7.3

        sub_face_type: Text for a particular type of Honeybee sub-face object to
            be written as a DesignBuilder Surface. This is useful in cases of
            modeling radiant ceiling panels or spandrel panels, which have a
            special sub-Surface object used to represent them in DesignBuilder
            instead of splitting the parent Face. Choose from the following options.

            * None - none of the honeybee objects will be written as a sub-Surface
            * OverheadDoors - Doors in RoofCeilings will be written as Surface
            * GlassDoors - glass Doors will be written as Surface
            * Doors - all Doors will be written as Surface
    """
    global HANDLE_COUNTER  # declare that we will edit the global variable
    # duplicate model to avoid mutating it as we edit it for dsbXML export
    original_model = model
    model = model.duplicate()
    # scale the model if the units are not meters
    if model.units != 'Meters':
        model.convert_to_units('Meters')
    # remove degenerate geometry within DesignBuilder native tolerance
    try:
        model.remove_degenerate_geometry(0.01)
    except ValueError:
        error = 'Failed to remove degenerate Rooms.\nYour Model units system is: {}. ' \
            'Is this correct?'.format(original_model.units)
        raise ValueError(error)
    # auto-assign stories if there are none since these are needed for blocks
    if len(model.stories) == 0 and len(model.rooms) != 0:
        model.assign_stories_by_floor_height(min_difference=2.0)
    # erase room user data and use it to store attributes for later
    for room in model.rooms:
        room.user_data = {'__identifier__': room.identifier}
    # reassign types for horizontal faces; remove any AirBoundaries that are not walls
    z_axis = Vector3D(0, 0, 1)
    for face in model.faces:
        angle = math.degrees(z_axis.angle(face.normal))
        if angle < 60:
            face.type = face_types.roof_ceiling
        elif angle >= 130:
            face.type = face_types.floor

    # set up the ElementTree for the XML
    package_dir = os.path.dirname(os.path.abspath(__file__))
    template_file = os.path.join(package_dir, '_templates', '{}.xml'.format(xml_template))
    xml_tree = ET.parse(template_file)
    xml_root = xml_tree.getroot()
    model_name = clean_string(model.display_name)
    xml_root.set('name', '~{}'.format(model_name))
    xml_root.set('date', str(datetime.date.today()))
    xml_root.set('version', DESIGNBUILDER_VERSION)

    # add the site and the building
    xml_site = xml_root.find('Site')
    xml_bldgs = xml_site.find('Buildings')
    xml_bldg = xml_bldgs.find('Building')

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
    HANDLE_COUNTER = len(block_rooms) + 2
    # convert identifiers to integers as this is the only ID format used by DesignBuilder
    HANDLE_COUNTER = model.reset_ids_to_integers(start_integer=HANDLE_COUNTER)
    HANDLE_COUNTER += 1

    # translate each block to dsbXML; including all geometry
    f_index_map = {}  # create a map between the face handle the face index
    xml_blocks = ET.SubElement(xml_bldg, 'BuildingBlocks')
    for i, (room_group, block_name) in enumerate(zip(block_rooms, block_names)):
        room_group_to_dsbxml_block(
            room_group, i + 2, xml_bldg, block_name, sub_face_type=sub_face_type,
            tolerance=model.tolerance, angle_tolerance=model.angle_tolerance,
            reset_counter=False
        )
        for room in room_group:
            for f in room:
                f_index_map[f.identifier] = f.user_data['dsb_face_i']

    # replace the face handle in the zone XML with the face index
    for xml_block in xml_blocks:
        xml_zones = xml_block.find('Zones')
        for xml_zone in xml_zones:
            xml_zone_body = xml_zone.find('Body')
            for xml_srf in xml_zone_body.find('Surfaces'):
                xml_adjs = xml_srf.find('Adjacencies')
                for xml_adj in xml_adjs:
                    xml_adj_obj_ids = xml_adj.find('ObjectIDs')
                    xml_adj_face_id = xml_adj_obj_ids.get('surfaceIndex')
                    if xml_adj_face_id != '-1':
                        try:
                            xml_adj_obj_ids.set(
                                'surfaceIndex', f_index_map[xml_adj_face_id])
                        except KeyError:  # invalid adjacency; remove the adjacency
                            xml_adj_obj_ids.set('surfaceIndex', '-1')
                            xml_adj_obj_ids.set('zoneHandle', '-1')

    # translate all of the shade geometries into the Planes section
    for shade in model.shades:
        shade_to_dsbxml_element(shade, xml_bldg)
    for shade_mesh in model.shade_meshes:
        shade_mesh.triangulate_and_remove_degenerate_faces(model.tolerance)
        shade_mesh_to_dsbxml_element(shade_mesh, xml_bldg, reset_counter=False)

    # set the handle of the site to the last index and reset the counter
    xml_site.set('handle', '1')
    HANDLE_COUNTER = 1

    return xml_root


def model_to_dsbxml(model, xml_template='Default', sub_face_type=None,
                    program_name=None):
    """Generate an dsbXML string for a Model.

    The resulting string will include all geometry (Rooms, Faces, Apertures,
    Doors, Shades), all fully-detailed constructions + materials, all fully-detailed
    schedules, and the room properties. It will also include the simulation
    parameters. Essentially, the string includes everything needed to simulate
    the model.

    Args:
        model: A honeybee Model for which an dsbXML text string will be returned.
        xml_template: Text for the type of template file to be used to write the
            dsbXML. Different templates contain different amounts of default
            assembly library data, which may be needed in order to import the
            dsbXML into older versions of DesignBuilder. However, this data can
            greatly increase the size of the resulting dsbXML file. Choose from
            the following options.

            * Default - a minimal file that imports into the latest versions
            * Assembly - the Default plus an AssemblyLibrary with typical objects
            * Full - a large file with all libraries that can be imported to version 7.3

        sub_face_type: Text for a particular type of Honeybee sub-face object to
            be written as a DesignBuilder Surface. This is useful in cases of
            modeling radiant ceiling panels or spandrel panels, which have a
            special sub-Surface object used to represent them in DesignBuilder
            instead of splitting the parent Face. Choose from the following options.

            * None - none of the honeybee objects will be written as a sub-Surface
            * OverheadDoors - Doors in RoofCeilings will be written as Surface
            * GlassDoors - glass Doors will be written as Surface
            * Doors - all Doors will be written as Surface

        program_name: Optional text to set the name of the software that will
            appear under a comment in the XML to identify where it is being exported
            from. This can be set things like "Ladybug Tools" or "Pollination"
            or some other software in which this dsbXML export capability is being
            run. If None, no comment will appear. (Default: None).

    Usage:

    .. code-block:: python

        import os
        from honeybee.model import Model
        from honeybee.room import Room
        from honeybee.config import folders

        # Crate an input Model
        room = Room.from_box('Tiny House Zone', 5, 10, 3)
        room.properties.energy.program_type = office_program
        room.properties.energy.add_default_ideal_air()
        model = Model('Tiny House', [room])

        # create the dsbXML string for the model
        xml_str = model.to.dsbxml(model)

        # write the final string into an XML file using DesignBuilder encoding
        dsbxml = os.path.join(folders.default_simulation_folder, 'in_dsb.xml')
        with open(dsbxml, 'wb') as fp:
            fp.write(xml_str.encode('iso-8859-15'))
    """
    # create the XML string
    xml_root = model_to_dsbxml_element(model, xml_template, sub_face_type)
    ET.indent(xml_root, '\t')
    dsbxml_str = ET.tostring(
        xml_root, encoding='unicode', xml_declaration=False
    )

    # add the declaration and a comment about the authoring program
    prog_comment = ''
    if program_name is not None:
        prog_comment = '<!--File generated by {}-->\n'.format(program_name)
    base_template = \
        '<?xml version="1.0" encoding="ISO-8859-15" standalone="yes"?>' \
        '\n{}'.format(prog_comment)
    dsbxml_str = base_template + dsbxml_str
    return dsbxml_str


def model_to_dsbxml_file(model, output_file, xml_template='Default', sub_face_type=None,
                         program_name=None):
    """Write an dsbXML file from a Honeybee Model.

    Note that this method also ensures that the resulting dsbXML file uses the
    ISO-8859-15 encoding that is used by DesignBuilder.

    Args:
        model: A honeybee Model for which an dsbXML file will be written.
        output_file: The path to the XML file that will be written from the model.
        xml_template: Text for the type of template file to be used to write the
            dsbXML. Different templates contain different amounts of default
            assembly library data, which may be needed in order to import the
            dsbXML into older versions of DesignBuilder. However, this data can
            greatly increase the size of the resulting dsbXML file. Choose from
            the following options.

            * Default - a minimal file that imports into the latest versions
            * Assembly - the Default plus an AssemblyLibrary with typical objects
            * Full - a large file with all libraries that can be imported to version 7.3

        sub_face_type: Text for a particular type of Honeybee sub-face object to
            be written as a DesignBuilder Surface. This is useful in cases of
            modeling radiant ceiling panels or spandrel panels, which have a
            special sub-Surface object used to represent them in DesignBuilder
            instead of splitting the parent Face. Choose from the following options.

            * None - none of the honeybee objects will be written as a sub-Surface
            * OverheadDoors - Doors in RoofCeilings will be written as Surface
            * GlassDoors - glass Doors will be written as Surface
            * Doors - all Doors will be written as Surface

        program_name: Optional text to set the name of the software that will
            appear under a comment in the XML to identify where it is being exported
            from. This can be set things like "Ladybug Tools" or "Pollination"
            or some other software in which this dsbXML export capability is being
            run. If None, no comment will appear. (Default: None).
    """
    # make sure the directory exists where the file will be written
    dir_name = os.path.dirname(os.path.abspath(output_file))
    if not os.path.isdir(dir_name):
        os.makedirs(dir_name)
    # get the string of the dsbXML file
    xml_str = model_to_dsbxml(model, xml_template, sub_face_type, program_name)
    # write the string into the file and encode it in ISO-8859-15
    with open(output_file, 'wb') as fp:
        fp.write(xml_str.encode('iso-8859-15', errors='ignore'))
    return output_file


def room_to_dsbxml(room):
    """Generate an dsbXML Zone string object for a honeybee Room.

    The resulting string has all constituent geometry (Faces, Apertures, Doors).

    Args:
        room: A honeybee Room for which an dsbXML Zone string object will be returned.
    """
    xml_root = room_to_dsbxml_element(room)
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


def sub_face_to_dsbxml(sub_face):
    """Generate an dsbXML Opening string from a honeybee Aperture or Door.

    Args:
        sub_face: A honeybee Aperture or Door for which an dsbXML Opening XML
            string will be returned.
    """
    xml_root = sub_face_to_dsbxml_element(sub_face)
    ET.indent(xml_root)
    return ET.tostring(xml_root, encoding='unicode')


def shade_to_dsbxml(shade):
    """Generate an dsbXML Plane string from a honeybee Shade.

    Args:
        shade: A honeybee Shade for which an dsbXML Plane XML string will
            be returned.
    """
    xml_root = shade_to_dsbxml_element(shade)
    ET.indent(xml_root)
    return ET.tostring(xml_root, encoding='unicode')


def shade_mesh_to_dsbxml(shade_mesh):
    """Generate an dsbXML Planes string from a honeybee ShadeMesh.

    Args:
        shade_mesh: A honeybee ShadeMesh for which an dsbXML Planes XML string
            will be returned.
    """
    xml_root = shade_mesh_to_dsbxml_element(shade_mesh)
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
