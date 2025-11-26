# coding=utf-8
"""Room DesignBuilder Properties."""
import math

from ladybug_geometry.geometry3d import Face3D


class RoomDesignBuilderProperties(object):
    """DesignBuilder Properties for Honeybee Room.

    Args:
        host: A honeybee_core Room object that hosts these properties.
        floor_geometry: An optional horizontal Face3D object, which will be used to
            compute block partitions and perimeters during export to dsbXML.
            If None, floor geometry is auto-calculated from the 3D Room geometry.
            Specifying a geometry here can help overcome some limitations of
            this auto-calculation and improve performance of dsbXML
            translation. (Default: None).

    Properties:
        * host
        * floor_geometry
    """
    __slots__ = ('_host', '_floor_geometry')

    def __init__(self, host, floor_geometry=None):
        """Initialize Room DesignBuilder properties."""
        # set the main properties of the Room
        self._host = host
        self.floor_geometry = floor_geometry

    @property
    def host(self):
        """Get the Room object hosting these properties."""
        return self._host

    @property
    def floor_geometry(self):
        """Get or set a horizontal Face3D to set the floor geometry."""
        return self._floor_geometry

    @floor_geometry.setter
    def floor_geometry(self, value):
        if value is not None:
            assert isinstance(value, Face3D), \
                'Expected ladybug_geometry Face3D. Got {}'.format(type(value))
            if value.normal.z < 0:  # ensure upward-facing Face3D
                self._floor_geometry = value.flip()
        self._floor_geometry = value

    def move(self, moving_vec):
        """Move this object along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the object.
        """
        if self.floor_geometry is not None:
            self._floor_geometry = self.floor_geometry.move(moving_vec)

    def rotate(self, angle, axis, origin):
        """Rotate this object by a certain angle around an axis and origin.

        Args:
            angle: An angle for rotation in degrees.
            axis: Rotation axis as a Vector3D.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        if self.floor_geometry is not None:
            self._floor_geometry = \
                self.floor_geometry.rotate(math.radians(angle), axis, origin)

    def rotate_xy(self, angle, origin):
        """Rotate this object counterclockwise in the world XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        if self.floor_geometry is not None:
            self._floor_geometry = \
                self.floor_geometry.rotate_xy(math.radians(angle), origin)

    def reflect(self, plane):
        """Reflect this object across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will
                be reflected.
        """
        if self.floor_geometry is not None:
            self._floor_geometry = self.floor_geometry.reflect(plane)

    def scale(self, factor, origin=None):
        """Scale this object by a factor from an origin point.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        if self.floor_geometry is not None:
            self._floor_geometry = \
                self.floor_geometry.scale(factor, origin)

    @classmethod
    def from_dict(cls, data, host):
        """Create RoomDesignBuilderProperties from a dictionary.

        Args:
            data: A dictionary representation of RoomDesignBuilderProperties with the
                format below.
            host: A Room object that hosts these properties.

        .. code-block:: python

            {
            "type": 'RoomDesignBuilderProperties',
            "floor_geometry": {}  # optional Face3D dictionary
            }
        """
        assert data['type'] == 'RoomDesignBuilderProperties', \
            'Expected RoomDesignBuilderProperties. Got {}.'.format(data['type'])
        new_prop = cls(host)
        if 'floor_geometry' in data and data['floor_geometry'] is not None:
            new_prop.floor_geometry = Face3D.from_dict(data['floor_geometry'])
        return new_prop

    def apply_properties_from_dict(self, data):
        """Apply properties from a RoomDesignBuilderProperties dictionary.

        Args:
            data: A RoomDesignBuilderProperties dictionary (typically coming from a Model).
        """
        if 'floor_geometry' in data and data['floor_geometry'] is not None:
            self.floor_geometry = Face3D.from_dict(data['floor_geometry'])

    def to_dict(self, abridged=False):
        """Return Room DesignBuilder properties as a dictionary."""
        base = {'designbuilder': {}}
        base['designbuilder']['type'] = 'RoomDesignBuilderProperties'
        if self.floor_geometry is not None:
            base['designbuilder']['floor_geometry'] = self.floor_geometry.to_dict()
        return base

    def duplicate(self, new_host=None):
        """Get a copy of this object.

        Args:
            new_host: A new Room object that hosts these properties.
                If None, the properties will be duplicated with the same host.
        """
        _host = new_host or self._host
        new_room = RoomDesignBuilderProperties(_host, self.floor_geometry)
        return new_room

    def ToString(self):
        return self.__repr__()

    def __repr__(self):
        return 'Room DesignBuilder Properties: [host: {}]'.format(self.host.display_name)
